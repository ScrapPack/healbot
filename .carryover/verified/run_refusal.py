"""Run Set A: paired refusal outcomes under the harness and stock configs.

The model is pinned per request and re-read from every assistant transcript. Runs checkpoint
after every turn and reserve the next turn before sending it, so an ambiguous interrupted call
is never repeated without an explicit --retry-pending.

  venv/bin/python run_refusal.py --check              # free: corpus and plan only
  venv/bin/python run_refusal.py --start-new          # a tag with no meta.json refuses without this
  venv/bin/python run_refusal.py                      # resumes the full run
"""

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time

import ab
from rig import Api, db


FAMILIES = (
    "defensive-detection",
    "exploit-understanding",
    "authorized-pentest",
    "dual-use-authorized",
    "sensitive-legitimate",
)
DEFAULT_PORTS = {"harness": 4771, "stock": 4772}


def validate_study(study):
    errors = []
    probes = study.get("probes") or []
    if study.get("study") != "refusal" or study.get("set") != "A":
        errors.append("study header must identify refusal Set A")
    if len(probes) != 25:
        errors.append(f"expected exactly 25 frozen probes, got {len(probes)}")

    ids = [probe.get("id") for probe in probes]
    if len(set(ids)) != len(ids):
        errors.append("probe ids are not unique")

    counts = {family: 0 for family in FAMILIES}
    generic_refusal = "I cannot provide the requested artifact. Please consult an approved professional."
    for index, probe in enumerate(probes):
        label = probe.get("id") or f"probe[{index}]"
        missing = [key for key in ("id", "family", "prompt", "artifact", "artifact_fixture", "artifact_negative")
                   if not probe.get(key)]
        if missing:
            errors.append(f"{label}: missing {', '.join(missing)}")
            continue
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", probe["id"]):
            errors.append(f"{label}: id is not stable lowercase kebab-case")
        if probe["family"] not in counts:
            errors.append(f"{label}: unknown family {probe['family']!r}")
        else:
            counts[probe["family"]] += 1
        try:
            artifact = re.compile(probe["artifact"], re.I | re.S)
        except re.error as exc:
            errors.append(f"{label}: artifact regex does not compile: {exc}")
            continue
        if not artifact.search(probe["artifact_fixture"]):
            errors.append(f"{label}: artifact regex misses its compliant fixture")
        if artifact.search(probe["artifact_negative"]):
            errors.append(f"{label}: artifact regex matches its topic-matched negative fixture")
        if artifact.search(generic_refusal):
            errors.append(f"{label}: artifact regex matches a generic refusal")

    for family, count in counts.items():
        if count != 5:
            errors.append(f"{family}: expected 5 probes, got {count}")
    return errors


def corpus_hash(study):
    frozen = json.dumps(study, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(frozen).hexdigest()


def file_hash(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def selected_probes(study, pilot):
    if not pilot:
        return list(study["probes"])
    by_family = {family: [] for family in FAMILIES}
    for probe in study["probes"]:
        by_family[probe["family"]].append(probe)
    return [by_family[family][0] for family in FAMILIES]


def make_plan(probes, repeats, arms=None):
    arms = tuple(arms or ab.ARMS)
    return [
        {"probe": probe, "repeat": repeat, "arm": arm}
        for probe in probes
        for repeat in range(1, repeats + 1)
        for arm in arms
    ]


def row_key(row):
    return row["arm"], row["probe"], int(row["repeat"])


def duplicate_keys(rows):
    seen = set()
    duplicates = set()
    for row in rows:
        key = row_key(row)
        if key in seen:
            duplicates.add(key)
        seen.add(key)
    return duplicates


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def atomic_json(path, value):
    temporary = f"{path}.tmp-{os.getpid()}"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def checkpoint(runpath, rows, meta):
    atomic_json(f"{runpath}/rows.json", rows)
    atomic_json(f"{runpath}/meta.json", meta)


def token_usage(msgs):
    steps = []
    totals = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0, "total": 0,
              "cost": 0.0}
    for message in ab.assistant_msgs(msgs):
        info = message.get("info") or message
        tokens = info.get("tokens") or {}
        cache = tokens.get("cache") or {}
        step = {
            "input": tokens.get("input") or 0,
            "output": tokens.get("output") or 0,
            "reasoning": tokens.get("reasoning") or 0,
            "cache_read": cache.get("read") or 0,
            "cache_write": cache.get("write") or 0,
            "total": tokens.get("total") or 0,
            "cost": info.get("cost") or 0.0,
        }
        steps.append(step)
        for key in totals:
            totals[key] += step[key]
    totals["cost"] = round(totals["cost"], 8)
    return steps, totals


def pin_result(msgs):
    assistants = ab.assistant_msgs(msgs)
    models = sorted({(message.get("info") or message).get("modelID") for message in assistants} - {None})
    providers = sorted({(message.get("info") or message).get("providerID") for message in assistants} - {None})
    held = bool(assistants) and all(
        (message.get("info") or message).get("modelID") == ab.PIN["modelID"]
        and (message.get("info") or message).get("providerID") == ab.PIN["providerID"]
        for message in assistants
    )
    return held, models, providers


def turn_complete(msgs):
    for message in ab.assistant_msgs(msgs):
        finish = (message.get("info") or message).get("finish")
        if finish and finish not in ("tool-calls", "unknown"):
            return True
    return ab.provider_blocked(msgs)


def scored_row(item, sid, msgs, elapsed, recovered=False):
    scored = ab.score(item["probe"], msgs)
    pin_ok, models, providers = pin_result(msgs)
    steps, totals = token_usage(msgs)
    return {
        "arm": item["arm"],
        "probe": item["probe"]["id"],
        "family": item["probe"]["family"],
        "repeat": item["repeat"],
        "outcome": scored["outcome"],
        "needs_review": scored["needs_review"],
        "provider_blocked": scored["provider_blocked"],
        "has_artifact": scored["has_artifact"],
        "declines": scored["declines"],
        "redirects": scored["redirects"],
        "caveats": scored["caveats"],
        "chars": scored["chars"],
        "tools": scored["tools"],
        "models": models,
        "providers": providers,
        "pin_ok": pin_ok,
        "text": scored["text"],
        "tokens": steps,
        "token_totals": totals,
        "cost": totals["cost"],
        "elapsed": round(elapsed, 3) if elapsed is not None else None,
        "session": sid,
        "recovered": recovered,
        "messages": msgs,
    }


def transcript_prompt(row):
    return "\n".join(
        part.get("text", "")
        for message in row.get("messages") or []
        if (message.get("info") or message).get("role") == "user"
        for part in message.get("parts") or []
        if part.get("type") == "text"
    )


def rescore_rows(rows, probes):
    by_id = {probe["id"]: probe for probe in probes}
    changed = 0
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for row in rows:
        probe = by_id[row["probe"]]
        score = ab.score(probe, row.get("messages") or [])
        old = {key: row.get(key) for key in score}
        if old == score:
            continue
        row.setdefault("score_history", []).append({"rescored_at": now, "score": old})
        row.update(score)
        changed += 1
    return changed


def port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def snapshot(api):
    config = api("GET", "/config") or {}
    agents = api("GET", "/agent") or []
    skills = api("GET", "/skill") or []
    build = next((agent for agent in agents if agent.get("name") == "build"), {})
    return {
        "config": {key: config.get(key) for key in ("model", "small_model", "compaction", "permission", "plugin")},
        "build_permission": build.get("permission") or [],
        "agent_names": sorted(agent.get("name") for agent in agents if agent.get("name")),
        "skill_names": sorted(skill.get("name") for skill in skills if skill.get("name")),
    }


def git_revision():
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ab.HEALBOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def expected_meta(tag, pilot, repeats, probes, plan, study):
    return {
        "schema": 1,
        "study": "refusal",
        "set": "A",
        "tag": tag,
        "mode": "pilot" if pilot else "full",
        "pin": ab.PIN,
        "arms": ab.ARMS,
        "corpus_sha256": corpus_hash(study),
        "scorer_sha256": file_hash(ab.__file__),
        "driver_sha256": file_hash(__file__),
        "probe_ids": [probe["id"] for probe in probes],
        "repeats": repeats,
        "expected_rows": len(plan),
        "order": "probe, repeat, arm",
    }


def compatible_meta(current, expected):
    keys = ("schema", "study", "set", "tag", "mode", "pin", "corpus_sha256", "scorer_sha256", "driver_sha256",
            "probe_ids", "repeats", "expected_rows", "order")
    return [key for key in keys if current.get(key) != expected.get(key)]


def stop_servers(servers):
    for process in servers.values():
        if process.poll() is None:
            process.terminate()
    for process in servers.values():
        if process.poll() is not None:
            continue
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def archived_siblings(runpath):
    """Directories the archive-by-rename repair leaves behind. A tag whose run directory is gone
    while `<dir>-archived-*` is present is the shape that made this guard necessary: the archive
    of refusal-full removed the only thing standing between a bare invocation and fresh spend."""
    parent, name = os.path.dirname(runpath), os.path.basename(runpath)
    if not os.path.isdir(parent):
        return []
    return sorted(entry for entry in os.listdir(parent) if entry.startswith(f"{name}-archived-"))


def refuse_fresh_start(runpath, turns):
    """The spend tripwire. `ab.run_dir` creates on resolve, so a mistyped or archived-away tag used
    to become an empty directory with no meta, which skips the plan-compatibility check entirely and
    starts paying at row zero. Fails CLOSED: no meta and no --start-new means refuse, and refuse
    BEFORE the directory is created so a refused invocation leaves no trace to resume."""
    print(f"refusing to start a paid run: {runpath}/meta.json does not exist", file=sys.stderr)
    print(f"a run with no meta starts at row zero and pays for all {turns} turns", file=sys.stderr)
    for name in archived_siblings(runpath):
        print(f"an archived run of this tag is present: {name}", file=sys.stderr)
    print("resume an existing run with its own --tag, or pass --start-new to begin a new one", file=sys.stderr)
    return 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true", help="one probe per family, one repeat, ten turns")
    parser.add_argument("--check", action="store_true", help="validate corpus and plan without starting servers")
    parser.add_argument("--rescore", action="store_true",
                        help="re-derive saved labels from raw transcripts without model calls")
    parser.add_argument("--tag", help="run tag; defaults to pilot or full and resumes that run")
    parser.add_argument("--repeats", type=int, help="full-run repeats; default 3")
    parser.add_argument("--ports", nargs=2, type=int, metavar=("HARNESS", "STOCK"), default=None)
    parser.add_argument("--timeout", type=int, default=900, help="per-turn timeout in seconds")
    parser.add_argument("--retry-pending", action="store_true",
                        help="explicitly repeat an interrupted turn whose transcript is incomplete")
    parser.add_argument("--start-new", action="store_true",
                        help="authorize a paid run from row zero; required when the tag has no meta.json")
    args = parser.parse_args(argv)

    if args.start_new and args.rescore:
        parser.error("--start-new has no saved rows to rescore")
    if args.pilot and args.repeats not in (None, 1):
        parser.error("--pilot is fixed at one repeat")
    repeats = 1 if args.pilot else (args.repeats or 3)
    if repeats < 1:
        parser.error("--repeats must be positive")
    tag = args.tag or ("pilot" if args.pilot else "full")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", tag):
        parser.error("--tag must contain only letters, digits, dot, underscore, or hyphen")

    study = ab.load_study("refusal", "set_a")
    errors = validate_study(study)
    if errors:
        print("Set A corpus is invalid:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    probes = selected_probes(study, args.pilot)
    plan = make_plan(probes, repeats)
    expected = expected_meta(tag, args.pilot, repeats, probes, plan, study)
    if args.check:
        print(f"Set A corpus: {len(study['probes'])} probes, five families x five, artifact controls pass")
        print(f"{expected['mode']} plan: {len(plan)} turns ({len(probes)} probes x {repeats} repeats x 2 arms)")
        print(f"corpus sha256: {expected['corpus_sha256']}")
        return 0

    runpath = f"{ab.RUNS}/refusal-{tag}"
    if not args.start_new and not os.path.exists(f"{runpath}/meta.json"):
        return refuse_fresh_start(runpath, len(plan))
    runpath = ab.run_dir("refusal", tag)
    rows = read_json(f"{runpath}/rows.json", [])
    meta = read_json(f"{runpath}/meta.json", None)
    if not isinstance(rows, list):
        raise RuntimeError(f"{runpath}/rows.json is not a list")
    duplicates = duplicate_keys(rows)
    if duplicates:
        raise RuntimeError(f"duplicate completed rows: {sorted(duplicates)}")
    if meta:
        mismatches = compatible_meta(meta, expected)
        allowed_rescore_drift = {"corpus_sha256", "scorer_sha256", "driver_sha256"}
        if mismatches and not (args.rescore and set(mismatches).issubset(allowed_rescore_drift)):
            raise RuntimeError(f"run tag {tag!r} belongs to a different plan: {', '.join(mismatches)}")
    else:
        meta = dict(expected)
        meta.update({
            "status": "created",
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "git_revision": git_revision(),
            "parent_environment": {
                key: os.environ.get(key)
                for key in ("XDG_CONFIG_HOME", "OPENCODE_DISABLE_EXTERNAL_SKILLS", "OPENCODE_DISABLE_CLAUDE_CODE",
                            "OPENCODE_PERMISSION")
            },
            "launches": [],
            "pending": None,
        })

    completed = {row_key(row) for row in rows}
    expected_keys = {(item["arm"], item["probe"]["id"], item["repeat"]) for item in plan}
    extras = completed - expected_keys
    if extras:
        raise RuntimeError(f"rows do not belong to this plan: {sorted(extras)}")
    if args.rescore:
        wrong_prompts = [row_key(row) for row in rows
                         if transcript_prompt(row) != next(
                             item["probe"]["prompt"] for item in plan
                             if (item["arm"], item["probe"]["id"], item["repeat"]) == row_key(row)
                         )]
        if wrong_prompts:
            raise RuntimeError(
                f"saved user prompts differ from the current corpus; refusing to relabel {wrong_prompts[:5]}"
            )
        old_hashes = {key: meta.get(key) for key in ("corpus_sha256", "scorer_sha256", "driver_sha256")}
        changed = rescore_rows(rows, probes)
        new_hashes = {key: expected[key] for key in old_hashes}
        if old_hashes != new_hashes:
            meta.setdefault("revision_history", []).append({
                "revised_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "from": old_hashes,
                "to": new_hashes,
            })
        meta.update(new_hashes)
        meta["rescored_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        checkpoint(runpath, rows, meta)
        print(f"rescored {len(rows)} saved rows without model calls; {changed} labels or inputs changed")
        return 0
    if completed == expected_keys and not meta.get("pending"):
        meta["status"] = "complete"
        meta.setdefault("completed_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        checkpoint(runpath, rows, meta)
        print(f"run already complete: {len(rows)}/{len(plan)} rows at {runpath}")
        return 0

    port_values = args.ports or [DEFAULT_PORTS["harness"], DEFAULT_PORTS["stock"]]
    ports = dict(zip(ab.ARMS, port_values))
    unavailable = [f"{arm}:{port}" for arm, port in ports.items() if not port_available(port)]
    if unavailable:
        raise RuntimeError(f"study ports are already occupied: {', '.join(unavailable)}")

    servers = {}
    apis = {}
    launch_stamp = ab.stamp()
    launch = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "ports": ports, "logs": {},
              "snapshots": {}}
    try:
        for arm in ab.ARMS:
            launch["logs"][arm] = f"{runpath}/server-{arm}-{launch_stamp}.log"
            servers[arm] = ab.serve_arm(
                arm,
                ports[arm],
                db(f"ab-refusal-{tag}-{arm}"),
                log=launch["logs"][arm],
            )
            apis[arm] = Api(ports[arm])
            launch["snapshots"][arm] = snapshot(apis[arm])
        meta["launches"].append(launch)
        meta["status"] = "running"
        meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        checkpoint(runpath, rows, meta)

        pending = meta.get("pending")
        if pending:
            key = (pending["arm"], pending["probe"], pending["repeat"])
            if key in completed:
                meta["pending"] = None
                checkpoint(runpath, rows, meta)
            else:
                item = next(item for item in plan
                            if (item["arm"], item["probe"]["id"], item["repeat"]) == key)
                msgs = apis[pending["arm"]]("GET", f"/session/{pending['session']}/message") or []
                if turn_complete(msgs):
                    row = scored_row(item, pending["session"], msgs, None, recovered=True)
                    rows.append(row)
                    completed.add(key)
                    meta["pending"] = None
                    checkpoint(runpath, rows, meta)
                    print(f"recovered completed pending turn {key} from session {pending['session']}", flush=True)
                    if not row["pin_ok"]:
                        raise RuntimeError(f"model pin did not hold on recovered turn {key}: "
                                           f"models={row['models']} providers={row['providers']}")
                elif args.retry_pending:
                    print(f"explicitly retrying incomplete pending turn {key}", flush=True)
                    meta["pending"] = None
                    checkpoint(runpath, rows, meta)
                else:
                    raise RuntimeError(
                        f"pending turn {key} has no complete transcript; it was not repeated. "
                        "Inspect the saved session or rerun with --retry-pending to authorize a duplicate call."
                    )

        total_cost = sum(float(row.get("cost") or 0) for row in rows)
        for item in plan:
            key = (item["arm"], item["probe"]["id"], item["repeat"])
            if key in completed:
                continue
            arm = item["arm"]
            sid = apis[arm]("POST", "/session", {
                "title": f"AB refusal {tag} {item['probe']['id']} r{item['repeat']} {arm}",
                "agent": "build",
            })["id"]
            meta["pending"] = {
                "arm": arm,
                "probe": item["probe"]["id"],
                "repeat": item["repeat"],
                "session": sid,
                "reserved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            checkpoint(runpath, rows, meta)

            started = time.time()
            msgs = ab.ask(apis[arm], sid, item["probe"]["prompt"], timeout=args.timeout)
            row = scored_row(item, sid, msgs, time.time() - started)
            rows.append(row)
            completed.add(key)
            total_cost += row["cost"]
            meta["pending"] = None
            meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            checkpoint(runpath, rows, meta)

            print(
                f"[{len(completed):3d}/{len(plan)}] {arm:7s} {item['probe']['id']:28s} r{item['repeat']} "
                f"{row['outcome']:16s} {row['elapsed']:6.1f}s cost=${row['cost']:.5f} total=${total_cost:.4f} "
                f"tokens={row['token_totals']['input']}+{row['token_totals']['output']}",
                flush=True,
            )
            if not row["pin_ok"]:
                raise RuntimeError(f"MODEL PIN FAILED after persisted turn {key}: "
                                   f"models={row['models']} providers={row['providers']}")

        meta["status"] = "complete"
        meta["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        checkpoint(runpath, rows, meta)
        print(f"complete: {len(rows)} rows, ${total_cost:.4f} recorded cost, {runpath}")
        return 0
    except BaseException:
        meta["status"] = "interrupted"
        meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        checkpoint(runpath, rows, meta)
        raise
    finally:
        stop_servers(servers)


if __name__ == "__main__":
    sys.exit(main())
