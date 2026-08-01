"""Generic paid-study driver: a pluggable per-study scorer over frozen synthesized arms.

WHY A SECOND DRIVER INSTEAD OF EDITING THE FIRST. run_refusal.py is pinned by live evidence:
the stranded refusal-full run's meta.json records driver_sha256 over that file's exact bytes,
and resume refuses on drift (run_refusal.py:295-298, 363-367). Editing it to add pluggability
would orphan 24 paid rows to improve a file whose whole value is that it does not move. So
this driver is built ALONGSIDE it, copying the shapes that run proved right — atomic
checkpoint after every row, reserve-before-send, explicit --retry-pending for ambiguous
interrupted spend (run_refusal.py:125-144, 446-504) — per the house rule for pinned code
(ab.serve_arm vs rig.serve): copy the shape, cite the source, own the copy. Three things
change:

1. THE SCORER IS THE STUDY'S, NOT THE DRIVER'S. A study definition is a module named
   study_<name>.py in this directory owning validate()/score()/delivered() (+ optional
   pilot()); study_refusal.py is instance one, delegating to ab.py's shape classifier and
   run_refusal.py's corpus contract without editing either. meta.json pins BEHAVIOR, not a
   wrapper: sources_sha256 records one sha per file the definition declares in SOURCES,
   plus this driver — a scorer whose logic lives in a delegated module cannot drift behind
   an unchanged wrapper hash.

2. ARMS ARE FROZEN, NEVER INHERITED. Every launch goes through arms.py: freeze() at run
   creation snapshots each arm's full config bytes into the run directory; every boot
   re-materializes from that snapshot, byte-verified, refusing on tamper or dependency
   drift. This driver contains no environment arm — ab.ARMS and ab.serve_arm are
   deliberately unreferenced (probe_study_driver.py asserts that from the AST) — because
   environments move mid-study (the 2026-07-31 double drift that stranded refusal-full)
   and synthesized arms are the repair. The CORPUS is frozen the same way: corpus.json is
   written into the run dir at creation and is the only corpus a resume or rescore ever
   reads, so the corpus edit that blocked refusal-full's resume cannot recur here — the
   live studies/ file is read exactly once, at creation. A run tag therefore refuses to
   resume under a directory this driver did not create (a legacy run_refusal tag has no
   frozen corpus and a foreign meta shape; pick a new tag, never adopt an old run).

3. A PROBE MAY CARRY A HIDDEN EXECUTABLE CHECK. Transcript-shape scoring cannot see whether
   the model's work product actually WORKS. A probe with a "check" field (a script starting
   with a shebang, frozen and hashed with the corpus) gets its turn bound to a DISPOSABLE
   WORKSPACE — a pooled worktree slot (harness/pool.py), leased per turn, restored and
   released after — and the script runs AFTER the turn with the workspace as cwd and
   argv[1]; exit 0 means the artifact holds. Binding is the x-opencode-directory header:
   workspace-routing.ts:87 resolves the instance per request and a created session keeps
   its directory (workspace-routing.ts:182), so one arm server hosts sessions in any
   directory while the arm's frozen XDG_CONFIG_HOME applies process-wide and both
   external-skill switches stay pinned off — the workspace opens no skill channel. The
   script body is written to a temp file OUTSIDE the workspace and never enters it: the
   model cannot read the test it is scored by, and a check that asserts tree state is not
   confounded by the harness's own droppings. The result (exit code, output, sha, secs) is
   recorded on the row as raw evidence and handed to score(); --rescore re-reads the
   RECORDED result — a released workspace cannot honestly be re-checked, so the check is
   re-derivable, never re-runnable. Turns are sequential, so at most one slot is leased at
   a time and a check script that boots probes collides with nothing but the arm ports.

  venv/bin/python run_study.py --study refusal --check
  venv/bin/python run_study.py --study refusal --pilot --arms-spec <arms.json>
  venv/bin/python run_study.py --study refusal --tag skills-1 --arms-spec <arms.json>

An arms spec is a JSON list, read once at creation: [{"name": "base"}, {"name": "plus-tdd",
"skill_name": "tdd", "skill_body_path": "harness/skills/tdd.md"}]. After creation the run
directory owns the bytes and --arms-spec is refused on resume.
"""

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import ab  # noqa: E402
import arms  # noqa: E402
from rig import Api, db  # noqa: E402

HEALBOT = os.path.dirname(os.path.dirname(SP))
POOL_PY = f"{HEALBOT}/harness/pool.py"
BASE_PORT = 4791  # 4791+i per arm; distinct from run_refusal's 4771-4772 and the rigs' 4141-4782

# Row keys the driver owns. A study scorer returning any of these would silently overwrite
# spend evidence (cost, the raw transcript, the pin verdict), so scored_row refuses them.
DRIVER_KEYS = frozenset({
    "arm", "probe", "repeat", "models", "providers", "pin_ok", "tokens", "token_totals",
    "cost", "elapsed", "session", "recovered", "workspace_check", "messages", "score_history",
})
REQUIRED_SCORE_KEYS = ("outcome", "needs_review")
CHECK_TIMEOUT_DEFAULT = 600


# ==========================================================================================
# STUDY DEFINITIONS
# ==========================================================================================
def load_studydef(name):
    """study_<name>.py in this directory IS the definition. Module-shaped on purpose: a file
    has bytes, bytes have a sha, and sources_sha() below is how the run's meta pins what the
    scorer actually was — including every file the definition declares it delegates to."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", name):
        raise RuntimeError(f"study name {name!r} is not a stable module suffix")
    import importlib
    try:
        module = importlib.import_module(f"study_{name}")
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"no study definition study_{name}.py in {SP}") from exc
    missing = [attr for attr in ("NAME", "DEFAULT_PART", "SOURCES", "validate", "score", "delivered")
               if not hasattr(module, attr)]
    if missing:
        raise RuntimeError(f"study_{name}.py is not a study definition — missing {', '.join(missing)}")
    if module.NAME != name:
        raise RuntimeError(f"study_{name}.py declares NAME={module.NAME!r}; the mismatch would "
                           f"desync the corpus dir from the meta header")
    return module


def file_hash(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def sources_sha(studydef):
    """One sha per behavior-bearing file: everything the definition declares, plus this
    driver. Keyed by repo-relative path so two files may share a basename."""
    files = [os.path.abspath(p) for p in studydef.SOURCES] + [os.path.abspath(__file__)]
    return {os.path.relpath(path, HEALBOT): file_hash(path) for path in files}


def corpus_hash(study):
    frozen = json.dumps(study, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(frozen).hexdigest()


def validate_generic(studydef, study):
    """The driver's own corpus contract — what ANY study must satisfy before the study's
    validate() adds its domain rules. The check-field rules live here because the check
    machinery is the driver's: a checkless study never meets them."""
    errors = []
    if study.get("study") != studydef.NAME:
        errors.append(f"corpus header says study={study.get('study')!r}, expected {studydef.NAME!r}")
    probes = study.get("probes") or []
    if not probes:
        errors.append("corpus has no probes")
    ids = [probe.get("id") for probe in probes]
    if len(set(ids)) != len(ids):
        errors.append("probe ids are not unique")
    for index, probe in enumerate(probes):
        label = probe.get("id") or f"probe[{index}]"
        if not probe.get("id") or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(probe.get("id"))):
            errors.append(f"{label}: id missing or not stable lowercase kebab-case")
        if not str(probe.get("prompt") or "").strip():
            errors.append(f"{label}: prompt is missing or empty")
        check = probe.get("check")
        if check is not None:
            if not isinstance(check, str) or not check.startswith("#!"):
                errors.append(f"{label}: check must be an executable script text starting with a "
                              f"shebang — the driver execs the file directly")
            timeout = probe.get("check_timeout", CHECK_TIMEOUT_DEFAULT)
            if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 1:
                errors.append(f"{label}: check_timeout must be a positive integer of seconds")
        elif "check_timeout" in probe:
            errors.append(f"{label}: check_timeout without a check does nothing — remove one")
    return errors


# ==========================================================================================
# PLAN AND LEDGER — run_refusal.py:91-144's shapes, generalized to N named arms
# ==========================================================================================
def make_plan(probes, repeats, arm_names):
    return [
        {"probe": probe, "repeat": repeat, "arm": arm}
        for probe in probes
        for repeat in range(1, repeats + 1)
        for arm in arm_names
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


# ==========================================================================================
# READING A TURN — run_refusal.py:147-230's shapes
# ==========================================================================================
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


def transcript_prompt(row):
    return "\n".join(
        part.get("text", "")
        for message in row.get("messages") or []
        if (message.get("info") or message).get("role") == "user"
        for part in message.get("parts") or []
        if part.get("type") == "text"
    )


# ==========================================================================================
# SCORING — the study's verdict on the driver's evidence
# ==========================================================================================
def _vet_score(studydef, scored):
    if not isinstance(scored, dict):
        raise RuntimeError(f"{studydef.NAME}.score returned {type(scored).__name__}, not a dict — "
                           f"a bare label loses the inputs a disagreement is settled from")
    missing = [key for key in REQUIRED_SCORE_KEYS if key not in scored]
    if missing:
        raise RuntimeError(f"{studydef.NAME}.score omitted required keys: {', '.join(missing)}")
    clash = sorted(DRIVER_KEYS & set(scored))
    if clash:
        raise RuntimeError(f"{studydef.NAME}.score returned driver-reserved keys {clash} — "
                           f"those rows are spend evidence and no scorer may overwrite them")
    return scored


def scored_row(studydef, item, sid, msgs, elapsed, check=None, recovered=False):
    scored = _vet_score(studydef, studydef.score(item["probe"], msgs, check=check))
    pin_ok, models, providers = pin_result(msgs)
    steps, totals = token_usage(msgs)
    return {
        "arm": item["arm"],
        "probe": item["probe"]["id"],
        "repeat": item["repeat"],
        **scored,
        "models": models,
        "providers": providers,
        "pin_ok": pin_ok,
        "tokens": steps,
        "token_totals": totals,
        "cost": totals["cost"],
        "elapsed": round(elapsed, 3) if elapsed is not None else None,
        "session": sid,
        "recovered": recovered,
        "workspace_check": check,
        "messages": msgs,
    }


def rescore_rows(studydef, rows, probes):
    """Re-derive saved labels from raw evidence without model calls. The recorded
    workspace_check result is part of that evidence: the check itself is NOT re-run — its
    workspace was restored and released, so a re-execution would measure a clean tree and
    file the number under this turn's name."""
    by_id = {probe["id"]: probe for probe in probes}
    changed = 0
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for row in rows:
        probe = by_id[row["probe"]]
        score = _vet_score(studydef, studydef.score(probe, row.get("messages") or [],
                                                    check=row.get("workspace_check")))
        old = {key: row.get(key) for key in score}
        if old == score:
            continue
        row.setdefault("score_history", []).append({"rescored_at": now, "score": old})
        row.update(score)
        changed += 1
    return changed


# ==========================================================================================
# HIDDEN WORKSPACE CHECKS — the probe's own test, run where the model cannot see it
# ==========================================================================================
def run_check(probe, workspace):
    """Execute the probe's check AFTER the turn: cwd and argv[1] are the workspace, exit 0
    means the artifact holds. The script body lands in a temp file outside the tree —
    hidden means the model never reads the test, and a check asserting tree state is not
    confounded by the harness writing into the tree it is about to judge. Failure shapes
    are recorded, never raised: a red check is a RESULT (that is the measurement), and a
    check that could not run records code=None, which no scorer may read as a pass."""
    body = probe["check"]
    timeout = probe.get("check_timeout", CHECK_TIMEOUT_DEFAULT)
    fd, script = tempfile.mkstemp(prefix="study-check-")
    started = time.time()
    try:
        if os.path.realpath(script).startswith(os.path.realpath(workspace) + os.sep):
            raise RuntimeError("check script landed inside the workspace (TMPDIR points into "
                               "it?) — hidden means hidden; refusing to run the check")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(body)
        os.chmod(script, 0o700)
        try:
            proc = subprocess.run([script, workspace], cwd=workspace,
                                  capture_output=True, text=True, timeout=timeout)
            code, out = proc.returncode, proc.stdout + proc.stderr
        except subprocess.TimeoutExpired:
            code, out = None, f"TIMEOUT after {timeout}s"
        except OSError as exc:
            code, out = None, f"could not execute check: {exc}"
    finally:
        os.unlink(script)
    return {
        "script_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "code": code,
        "secs": round(time.time() - started, 3),
        "out": out,
    }


def acquire_workspace(owner, purpose):
    """Lease a disposable workspace from the pool. A subprocess, not an import: pool.py's
    CLI is its contract ("the path IS the interface") and its exit lattice is typed — a
    refusal (2, no leasable slot) and an error both surface here as a raise, because a
    checked probe without a workspace has nothing to measure."""
    result = subprocess.run([sys.executable, POOL_PY, "acquire", "--owner", owner, "--purpose", purpose],
                            capture_output=True, text=True, timeout=120)
    path = result.stdout.strip().splitlines()[-1].strip() if result.stdout.strip() else ""
    if result.returncode != 0 or not os.path.isdir(path):
        raise RuntimeError(f"no disposable workspace for a checked probe — pool acquire exited "
                           f"{result.returncode}: {(result.stdout + result.stderr).strip()[:300]}")
    return path


def release_workspace(workspace, owner):
    """Restore and free the slot. The turn's work product is disposable BY DESIGN once
    measured — the row keeps the transcript and the check result; the tree keeps nothing.
    A failed release raises with the slot still leased to `owner`: an unrestorable slot is
    a finding for a human, and pool.py status will keep saying so."""
    result = subprocess.run([sys.executable, POOL_PY, "release", os.path.basename(workspace),
                             "--if-owner", owner, "--discard-work"],
                            capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"workspace release failed (exit {result.returncode}) — the slot stays "
                           f"leased to {owner!r} for inspection: "
                           f"{(result.stdout + result.stderr).strip()[:300]}")


def workspace_lease_owner(workspace):
    """Who holds the slot NOW, per the pool's own lease record. None when unleased or the
    record is unreadable — which the recovery logic treats as evidence LOST, never held."""
    if not workspace:
        return None
    sys.path.insert(0, f"{HEALBOT}/harness")
    import pool
    lease = pool.read_json(pool.lease_path(workspace))
    return (lease or {}).get("owner")


def pending_disposition(pending, probe, msgs, retry, lease_owner, run_owner):
    """What a saved reservation means, decided with no side effects so the decision itself
    is testable. run_refusal.py:446-474's lattice plus one new refusal: a checked probe
    whose transcript survived but whose WORKSPACE did not (lease gone, or re-leased to
    someone else) cannot be recovered — the hidden check would measure a restored tree and
    record the number as this turn's. Returns "recover" | "retry" | "refuse-incomplete" |
    "refuse-lost-workspace"; both refusals are overridden only by --retry-pending, which
    authorizes a duplicate paid call out loud."""
    complete = turn_complete(msgs)
    if complete and probe.get("check") and (not pending.get("workspace") or lease_owner != run_owner):
        return "retry" if retry else "refuse-lost-workspace"
    if complete:
        return "recover"
    return "retry" if retry else "refuse-incomplete"


# ==========================================================================================
# FROZEN ARMS AND CORPUS — the run directory is the authority for everything but code
# ==========================================================================================
def load_armspec(path):
    """Parse an arms spec and read every delta body, ONCE. After freeze() the run dir owns
    the bytes; this function is never called on a resume."""
    spec = read_json(path)
    if spec is None or not isinstance(spec, list) or not spec:
        raise RuntimeError(f"arms spec {path!r} must be a non-empty JSON list")
    defs = []
    for entry in spec:
        if not isinstance(entry, dict) or not entry.get("name"):
            raise RuntimeError(f"arms spec entry needs at least a name: {entry!r}")
        unknown = set(entry) - {"name", "skill_name", "skill_body_path"}
        if unknown:
            raise RuntimeError(f"arms spec entry {entry['name']!r} has unknown keys: {sorted(unknown)}")
        body = None
        if "skill_name" in entry or "skill_body_path" in entry:
            if not {"skill_name", "skill_body_path"} <= set(entry):
                raise RuntimeError(f"arm {entry['name']!r}: a delta needs skill_name AND skill_body_path")
            body_path = entry["skill_body_path"]
            if not os.path.isabs(body_path):
                body_path = f"{HEALBOT}/{body_path}"
            if not os.path.isfile(body_path):
                raise RuntimeError(f"arm {entry['name']!r}: skill_body_path {body_path!r} does not exist")
            with open(body_path, encoding="utf-8") as handle:
                body = handle.read()
        defs.append(arms.define(entry["name"], skill_name=entry.get("skill_name"), skill_body=body))
    return defs


def manifest_digest(manifest):
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def arms_meta(manifests):
    return {
        name: {
            "delta": manifest["delta"],
            "lockfile_sha256": manifest["lockfile_sha256"],
            "manifest_sha256": manifest_digest(manifest),
        }
        for name, manifest in manifests.items()
    }


def verify_frozen_arms(runpath, meta):
    """Resume-side: the manifests on disk must be the ones this run recorded at freeze.
    materialize() already refuses per-file tamper; this refuses MANIFEST tamper — the
    authority being edited to bless a different config is the one move materialize alone
    cannot see, because it verifies files against the manifest it was handed."""
    recorded = meta.get("arms") or {}
    if not recorded:
        raise RuntimeError("meta.json records no frozen arms — not a run_study run directory")
    for name, entry in sorted(recorded.items()):
        manifest = arms.read_manifest(runpath, name)
        got = manifest_digest(manifest)
        if got != entry.get("manifest_sha256"):
            raise RuntimeError(f"arm {name!r}: frozen manifest digest {got[:12]} != recorded "
                               f"{str(entry.get('manifest_sha256'))[:12]} — the run's arm authority "
                               f"was edited after launch; refusing")


def frozen_corpus_path(runpath):
    return f"{runpath}/corpus.json"


def create_run(runpath, study, armdefs, expected):
    """Constitute a new run directory: frozen corpus first, then frozen arms, then meta.
    Called once, before any spend — the paid-run-protocol freeze-at-launch rule as code.
    freeze() may refuse (unconstituted base) with the corpus already written; a re-create
    over that half-made dir is idempotent because both freezes are deterministic."""
    with open(frozen_corpus_path(runpath), "w", encoding="utf-8") as handle:
        json.dump(study, handle, indent=2)
        handle.write("\n")
    manifests = arms.freeze(armdefs, runpath)
    meta = dict(expected)
    meta.update({
        "arms": arms_meta(manifests),
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
    return meta


# ==========================================================================================
# META — run_refusal.py:276-298's shapes, arms recorded at freeze rather than declared
# ==========================================================================================
def expected_meta(studydef, tag, pilot, repeats, part, probes, plan, study, arm_names):
    return {
        "schema": 1,
        "driver": "run_study",
        "study": studydef.NAME,
        "part": part,
        "tag": tag,
        "mode": "pilot" if pilot else "full",
        "pin": ab.PIN,
        "arm_names": list(arm_names),
        "corpus_sha256": corpus_hash(study),
        "sources_sha256": sources_sha(studydef),
        "probe_ids": [probe["id"] for probe in probes],
        "repeats": repeats,
        "expected_rows": len(plan),
        "order": "probe, repeat, arm",
    }


COMPAT_KEYS = ("schema", "driver", "study", "part", "tag", "mode", "pin", "arm_names",
               "corpus_sha256", "sources_sha256", "probe_ids", "repeats", "expected_rows", "order")


def compatible_meta(current, expected):
    return [key for key in COMPAT_KEYS if current.get(key) != expected.get(key)]


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
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HEALBOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


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


# ==========================================================================================
# REPORTING — per-arm delivered rates; exact McNemar when the study is a two-arm A/B
# ==========================================================================================
def compare(studydef, rows, arm_names):
    out = {}
    for name in arm_names:
        got = [row for row in rows if row["arm"] == name]
        delivered = sum(1 for row in got if studydef.delivered(row["outcome"]))
        lo, hi = ab.wilson(delivered, len(got))
        out[name] = {"n": len(got), "delivered": delivered,
                     "rate": round(delivered / len(got), 4) if got else 0.0,
                     "ci95": (round(lo, 4), round(hi, 4))}
    if len(arm_names) == 2:
        first, second = arm_names
        keyed = {}
        for row in rows:
            keyed.setdefault((row["probe"], row["repeat"]), {})[row["arm"]] = row
        pairs = {key: value for key, value in keyed.items() if len(value) == 2}
        b = sum(1 for value in pairs.values()
                if studydef.delivered(value[first]["outcome"]) and not studydef.delivered(value[second]["outcome"]))
        c = sum(1 for value in pairs.values()
                if studydef.delivered(value[second]["outcome"]) and not studydef.delivered(value[first]["outcome"]))
        out["paired"] = {"pairs": len(pairs), f"{first}_only": b, f"{second}_only": c,
                         "agree": len(pairs) - b - c, "p": ab.mcnemar_exact(b, c)}
    return out


def print_report(studydef, rows, arm_names):
    report = compare(studydef, rows, arm_names)
    for name in arm_names:
        entry = report[name]
        print(f"  {name}: {entry['delivered']}/{entry['n']} delivered "
              f"(rate {entry['rate']}, ci95 {entry['ci95']})", flush=True)
    if "paired" in report:
        print(f"  paired: {report['paired']}", flush=True)


# ==========================================================================================
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", required=True, help="study_<name>.py owns the scorer")
    parser.add_argument("--part", help="corpus part under studies/<study>/; default the study's")
    parser.add_argument("--pilot", action="store_true", help="the study's pilot subset, one repeat")
    parser.add_argument("--check", action="store_true", help="validate corpus, plan and arms spec; no servers")
    parser.add_argument("--rescore", action="store_true",
                        help="re-derive saved labels from raw evidence without model calls")
    parser.add_argument("--tag", help="run tag; defaults to pilot or full and resumes that run")
    parser.add_argument("--repeats", type=int, help="full-run repeats; default 3")
    parser.add_argument("--arms-spec", help="JSON arm definitions; required at creation, refused on resume")
    parser.add_argument("--ports", nargs="+", type=int, help="one port per arm; default 4791+i")
    parser.add_argument("--timeout", type=int, default=900, help="per-turn timeout in seconds")
    parser.add_argument("--retry-pending", action="store_true",
                        help="explicitly repeat an interrupted turn whose evidence is incomplete")
    args = parser.parse_args(argv)

    studydef = load_studydef(args.study)
    part = args.part or studydef.DEFAULT_PART
    if args.pilot and args.repeats not in (None, 1):
        parser.error("--pilot is fixed at one repeat")
    repeats = 1 if args.pilot else (args.repeats or 3)
    if repeats < 1:
        parser.error("--repeats must be positive")
    tag = args.tag or ("pilot" if args.pilot else "full")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", tag):
        parser.error("--tag must contain only letters, digits, dot, underscore, or hyphen")

    if args.pilot and not hasattr(studydef, "pilot"):
        parser.error(f"study {studydef.NAME!r} defines no pilot selection")

    if args.check:
        study = ab.load_study(studydef.NAME, part)
        errors = validate_generic(studydef, study) + list(studydef.validate(study))
        if errors:
            print(f"{studydef.NAME}/{part} corpus is invalid:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 1
        probes = studydef.pilot(study) if args.pilot else list(study["probes"])
        armdefs = load_armspec(args.arms_spec) if args.arms_spec else None
        arm_names = [arm["name"] for arm in armdefs] if armdefs else ["<arm>", "<arm>"]
        plan = make_plan(probes, repeats, arm_names)
        checked = sum(1 for probe in probes if probe.get("check"))
        print(f"{studydef.NAME}/{part}: {len(study['probes'])} probes valid, {checked} carrying a workspace check")
        print(f"{'pilot' if args.pilot else 'full'} plan: {len(plan)} turns "
              f"({len(probes)} probes x {repeats} repeats x {len(arm_names)} arms)")
        print(f"corpus sha256: {corpus_hash(study)}")
        for rel, sha in sorted(sources_sha(studydef).items()):
            print(f"source {rel}: {sha}")
        if armdefs:
            print(f"arms: {', '.join(arm['name'] for arm in armdefs)} (definitions valid; not frozen)")
        return 0

    runpath = ab.run_dir(studydef.NAME, tag)
    rows = read_json(f"{runpath}/rows.json", [])
    meta = read_json(f"{runpath}/meta.json", None)
    if not isinstance(rows, list):
        raise RuntimeError(f"{runpath}/rows.json is not a list")
    if meta is not None and not os.path.exists(frozen_corpus_path(runpath)):
        raise RuntimeError(f"run tag {tag!r} exists but has no frozen corpus.json — this driver did "
                           f"not create it (a legacy run_refusal tag?). Pick a new --tag; never adopt "
                           f"an old run's directory")

    frozen_exists = os.path.exists(frozen_corpus_path(runpath))
    study = read_json(frozen_corpus_path(runpath)) if frozen_exists else ab.load_study(studydef.NAME, part)
    errors = validate_generic(studydef, study) + list(studydef.validate(study))
    if errors:
        print(f"{studydef.NAME}/{part} corpus is invalid:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    probes = studydef.pilot(study) if args.pilot else list(study["probes"])

    if meta:
        if args.arms_spec:
            parser.error(f"run tag {tag!r} already froze its arms at creation — drop --arms-spec")
        arm_names = list(meta.get("arm_names") or [])
        if not arm_names:
            raise RuntimeError(f"run tag {tag!r} records no arm_names — not a run_study run")
        armdefs = None
    else:
        if not args.arms_spec:
            parser.error("a new run needs --arms-spec (a resumed run refuses it)")
        armdefs = load_armspec(args.arms_spec)
        arm_names = [arm["name"] for arm in armdefs]

    plan = make_plan(probes, repeats, arm_names)
    expected = expected_meta(studydef, tag, args.pilot, repeats, part, probes, plan, study, arm_names)

    duplicates = duplicate_keys(rows)
    if duplicates:
        raise RuntimeError(f"duplicate completed rows: {sorted(duplicates)}")
    if meta:
        mismatches = compatible_meta(meta, expected)
        allowed_rescore_drift = {"sources_sha256"}
        if mismatches and not (args.rescore and set(mismatches).issubset(allowed_rescore_drift)):
            raise RuntimeError(f"run tag {tag!r} belongs to a different plan: {', '.join(mismatches)}")
    else:
        meta = create_run(runpath, study, armdefs, expected)
        checkpoint(runpath, rows, meta)

    completed = {row_key(row) for row in rows}
    expected_keys = {(item["arm"], item["probe"]["id"], item["repeat"]) for item in plan}
    extras = completed - expected_keys
    if extras:
        raise RuntimeError(f"rows do not belong to this plan: {sorted(extras)}")

    if args.rescore:
        by_id = {probe["id"]: probe for probe in probes}
        wrong_prompts = [row_key(row) for row in rows
                         if transcript_prompt(row) != by_id[row["probe"]]["prompt"]]
        if wrong_prompts:
            raise RuntimeError(
                f"saved user prompts differ from the frozen corpus; refusing to relabel {wrong_prompts[:5]}"
            )
        old_sources = meta.get("sources_sha256")
        changed = rescore_rows(studydef, rows, probes)
        if old_sources != expected["sources_sha256"]:
            meta.setdefault("revision_history", []).append({
                "revised_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "from": {"sources_sha256": old_sources},
                "to": {"sources_sha256": expected["sources_sha256"]},
            })
        meta["sources_sha256"] = expected["sources_sha256"]
        meta["rescored_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        checkpoint(runpath, rows, meta)
        print(f"rescored {len(rows)} saved rows without model calls; {changed} labels or inputs changed")
        return 0

    if completed == expected_keys and not meta.get("pending"):
        meta["status"] = "complete"
        meta.setdefault("completed_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
        checkpoint(runpath, rows, meta)
        print(f"run already complete: {len(rows)}/{len(plan)} rows at {runpath}")
        print_report(studydef, rows, arm_names)
        return 0

    ports = args.ports or [BASE_PORT + i for i in range(len(arm_names))]
    if len(ports) != len(arm_names):
        parser.error(f"--ports needs exactly {len(arm_names)} value(s), one per arm")
    port_map = dict(zip(arm_names, ports))
    unavailable = [f"{arm}:{port}" for arm, port in port_map.items() if not port_available(port)]
    if unavailable:
        raise RuntimeError(f"study ports are already occupied: {', '.join(unavailable)}")

    verify_frozen_arms(runpath, meta)
    owner = f"study-{studydef.NAME}-{tag}"
    servers = {}
    apis = {}
    launch_stamp = ab.stamp()
    launch = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "ports": port_map,
              "logs": {}, "snapshots": {}}
    try:
        for arm in arm_names:
            launch["logs"][arm] = f"{runpath}/server-{arm}-{launch_stamp}.log"
            servers[arm] = arms.serve(
                runpath,
                arm,
                port_map[arm],
                db(f"study-{studydef.NAME}-{tag}-{arm}"),
                log=launch["logs"][arm],
            )
            apis[arm] = Api(port_map[arm])
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
                workspace = pending.get("workspace")
                api = Api(port_map[pending["arm"]], directory=workspace) if workspace else apis[pending["arm"]]
                msgs = api("GET", f"/session/{pending['session']}/message") or []
                disposition = pending_disposition(pending, item["probe"], msgs, args.retry_pending,
                                                  workspace_lease_owner(workspace), owner)
                if disposition == "recover":
                    check = run_check(item["probe"], workspace) if item["probe"].get("check") else None
                    row = scored_row(studydef, item, pending["session"], msgs, None,
                                     check=check, recovered=True)
                    rows.append(row)
                    completed.add(key)
                    meta["pending"] = None
                    checkpoint(runpath, rows, meta)
                    if workspace:
                        release_workspace(workspace, owner)
                    print(f"recovered completed pending turn {key} from session {pending['session']}", flush=True)
                    if not row["pin_ok"]:
                        raise RuntimeError(f"model pin did not hold on recovered turn {key}: "
                                           f"models={row['models']} providers={row['providers']}")
                elif disposition == "retry":
                    print(f"explicitly retrying pending turn {key}", flush=True)
                    if workspace and workspace_lease_owner(workspace) == owner:
                        release_workspace(workspace, owner)
                    meta["pending"] = None
                    checkpoint(runpath, rows, meta)
                elif disposition == "refuse-lost-workspace":
                    raise RuntimeError(
                        f"pending turn {key} has a complete transcript but its disposable workspace "
                        f"was released — the hidden check cannot honestly run against a restored "
                        f"tree. Rerun with --retry-pending to authorize a duplicate call."
                    )
                else:
                    raise RuntimeError(
                        f"pending turn {key} has no complete transcript; it was not repeated. "
                        f"Inspect the saved session or rerun with --retry-pending to authorize a duplicate call."
                    )

        total_cost = sum(float(row.get("cost") or 0) for row in rows)
        for item in plan:
            key = (item["arm"], item["probe"]["id"], item["repeat"])
            if key in completed:
                continue
            arm = item["arm"]
            workspace = None
            if item["probe"].get("check"):
                workspace = acquire_workspace(owner, f"{item['probe']['id']} r{item['repeat']} {arm}")
                api = Api(port_map[arm], directory=workspace)
            else:
                api = apis[arm]
            try:
                sid = api("POST", "/session", {
                    "title": f"study {studydef.NAME} {tag} {item['probe']['id']} r{item['repeat']} {arm}",
                    "agent": "build",
                })["id"]
                meta["pending"] = {
                    "arm": arm,
                    "probe": item["probe"]["id"],
                    "repeat": item["repeat"],
                    "session": sid,
                    "workspace": workspace,
                    "reserved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                checkpoint(runpath, rows, meta)
            except BaseException:
                # Nothing paid happened yet; free the slot rather than strand the lease.
                if workspace:
                    release_workspace(workspace, owner)
                raise

            started = time.time()
            msgs = ab.ask(api, sid, item["probe"]["prompt"], timeout=args.timeout)
            check = run_check(item["probe"], workspace) if workspace else None
            row = scored_row(studydef, item, sid, msgs, time.time() - started, check=check)
            rows.append(row)
            completed.add(key)
            total_cost += row["cost"]
            meta["pending"] = None
            meta["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            checkpoint(runpath, rows, meta)
            if workspace:
                release_workspace(workspace, owner)

            check_note = "" if not check else f" check={'ok' if check['code'] == 0 else check['code']}"
            print(
                f"[{len(completed):3d}/{len(plan)}] {arm:12s} {item['probe']['id']:28s} r{item['repeat']} "
                f"{row['outcome']:16s}{check_note} {row['elapsed']:6.1f}s cost=${row['cost']:.5f} "
                f"total=${total_cost:.4f} "
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
        print_report(studydef, rows, arm_names)
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
