"""The evidence flow: after a push lands, attach the gate and review run records to the
commit on GitHub, so the evidence leaves the machine with the code it vouches for.

WHY THIS SHAPE. This repo pushes a single branch straight to main, so the primary target is
a COMMIT COMMENT on the pushed sha; when an open PR exists for the pushed branch the same
body goes to `gh pr comment` instead. Git has no client-side post-push hook and the sha does
not exist on GitHub until the transfer completes, so gate/hooks/pre-push spawns this script
DETACHED and it retries until the commit appears remotely (a push that fails or is rejected
never produces the sha, and this gives up quietly on record).

THE AUDITABLE PROPERTY, which is the point: the hook is the only thing that runs this, and
`git push --no-verify` skips the hook entirely — so a pushed commit with NO evidence comment
is a commit that shipped unverified. Absence is a signal, not a gap.

WHAT IS PUBLISHED. A markdown summary (gate verdict + per-check table, review findings) plus
the two run records as fenced JSON with their bulky raw-output fields stripped. The comment
states the sha256 of each FULL local record file, so the published summary is pinned to the
untruncated evidence retained in gate/runs/ (per the no-silent-caps rule, every stripped or
truncated field is named). Publishing never blocks or fails a push: every outcome, including
giving up, lands in gate/runs/<ts>-<pid>-publish.json and gate/runs/publish.log.

Seams: HEALBOT_PUBLISH=off (checked by the hook) skips entirely; HEALBOT_PUBLISH_GH
overrides the gh binary for plumbing tests; HEALBOT_PUBLISH_RETRIES / _WAIT bound the
remote-appearance wait (defaults 8 x 8s). --dry-run builds and prints the body and target
decision without posting.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = f"{ROOT}/gate/runs"
GH = os.environ.get("HEALBOT_PUBLISH_GH") or shutil.which("gh")
RETRIES = int(os.environ.get("HEALBOT_PUBLISH_RETRIES", "8"))
WAIT = int(os.environ.get("HEALBOT_PUBLISH_WAIT", "8"))
EMBED_CAP = 20_000          # per embedded record, chars; the full file stays local, hashed
GATE_RE = re.compile(r"^\d{8}-\d{6}(-\d+)?\.json$")

STRIP_KEYS = {"out", "raw", "raw_stderr"}   # bulky raw output; sha256/tails/states remain


def sh(cmd, timeout=60):
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return None, "", f"{exc}"


def newest(match, since):
    """Newest record in gate/runs whose basename satisfies `match` and mtime >= since."""
    best, best_m = None, 0.0
    for name in os.listdir(RUNS):
        path = f"{RUNS}/{name}"
        if not match(name):
            continue
        m = os.path.getmtime(path)
        if m >= since - 1.0 and m > best_m:
            best, best_m = path, m
    return best


def cleaned(path):
    """The record with bulky raw fields stripped, plus the sha256 of the FULL file bytes."""
    with open(path, "rb") as fh:
        raw = fh.read()
    full_sha = hashlib.sha256(raw).hexdigest()
    rec = json.loads(raw)
    stripped = []

    def strip(obj):
        if isinstance(obj, dict):
            for k in list(obj):
                if k in STRIP_KEYS and isinstance(obj[k], str) and obj[k]:
                    stripped.append(k)
                    obj[k] = f"<stripped {len(obj[k])}B; full record retained locally>"
                else:
                    strip(obj[k])
        elif isinstance(obj, list):
            for v in obj:
                strip(v)

    strip(rec)
    body = json.dumps(rec, indent=1)
    truncated = False
    if len(body) > EMBED_CAP:
        body, truncated = body[:EMBED_CAP] + "\n… <truncated>", True
    return rec, body, full_sha, stripped, truncated


def build_body(sha, ref, gate_path, review_path):
    lines = [f"### healbot gate evidence — `{sha[:12]}` → `{ref}`",
             "",
             "Published by `gate/publish.py` from the pre-push hook. A pushed commit with no "
             "evidence comment shipped via `--no-verify`, unverified.",
             ""]
    for label, path in (("gate", gate_path), ("review", review_path)):
        if not path:
            lines += [f"**{label}:** no run record found for this push", ""]
            continue
        rec, body, full_sha, stripped, truncated = cleaned(path)
        if label == "gate":
            lines.append(f"**gate:** `{rec.get('verdict', '?')}` · "
                         f"{len(rec.get('files', []))} changed file(s) · base `{rec.get('base')}`")
            lines.append("")
            lines.append("| check | state | detail | secs |")
            lines.append("|---|---|---|---|")
            for c in rec.get("checks", []):
                tail = "; ".join(c.get("tail", [])) or c.get("why", "")
                lines.append(f"| {c.get('check')} | {c.get('state')} | {tail} | {c.get('secs')} |")
        else:
            fs = rec.get("findings", [])
            state = rec.get("state", "?")
            lines.append(f"**review:** `{state}` ({rec.get('mode')}, {rec.get('secs', '?')}s) · "
                         f"{len(fs)} finding(s)" if state not in ("skipped", "error")
                         else f"**review:** `{state}` — {rec.get('why', '')}")
            for f in fs:
                loc = f"{f.get('file')}:{f['line']}" if f.get("line") else f.get("file")
                lines.append(f"- [{f.get('severity', '?')}] `{loc}` {f.get('summary')}")
        note = f"raw fields stripped: {sorted(set(stripped))}" if stripped else "nothing stripped"
        note += "; embed truncated" if truncated else ""
        lines += ["",
                  f"<details><summary>{os.path.basename(path)} ({note}; full record "
                  f"sha256 {full_sha[:16]}…)</summary>", "",
                  "````json", body, "````", "</details>", ""]
    return "\n".join(lines)


def main():
    args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
    dry = "--dry-run" in sys.argv
    sha, ref = args.get("--sha"), args.get("--ref", "refs/heads/main")
    since = float(args.get("--since", 0))
    rec = {"stage": "publish", "sha": sha, "ref": ref,
           "ts": f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"}
    out_path = f"{RUNS}/{rec['ts']}-publish.json"

    gate_path = newest(lambda n: GATE_RE.match(n) is not None, since)
    review_path = newest(lambda n: n.endswith("-review.json"), since)
    rec.update({"gate_record": gate_path and os.path.basename(gate_path),
                "review_record": review_path and os.path.basename(review_path)})

    if not sha or not GH:
        rec.update({"state": "error", "why": "no --sha given" if not sha else "gh not found"})
    elif dry:
        body = build_body(sha, ref, gate_path, review_path)
        print(body)
        rec.update({"state": "dry-run", "body_bytes": len(body)})
    else:
        for attempt in range(1, RETRIES + 1):
            code, _, _ = sh([GH, "api", f"repos/{{owner}}/{{repo}}/commits/{sha}", "--silent"])
            if code == 0:
                break
            rec["attempts"] = attempt
            if attempt == RETRIES:
                rec.update({"state": "gave-up",
                            "why": f"commit never appeared on the remote after {RETRIES}x{WAIT}s "
                                   "(a failed or rejected push produces exactly this)"})
                break
            time.sleep(WAIT)
        if rec.get("state") != "gave-up":
            body = build_body(sha, ref, gate_path, review_path)
            tmp = f"{RUNS}/{rec['ts']}-publish-body.md"
            with open(tmp, "w") as fh:
                fh.write(body)
            branch = ref.removeprefix("refs/heads/")
            code, pr, _ = sh([GH, "pr", "list", "--head", branch, "--state", "open",
                              "--json", "number", "--jq", ".[0].number"])
            if code == 0 and pr:
                code, url, err = sh([GH, "pr", "comment", pr, "--body-file", tmp])
                rec["target"] = f"pr #{pr}"
            else:
                code, url, err = sh([GH, "api", f"repos/{{owner}}/{{repo}}/commits/{sha}/comments",
                                     "-F", f"body=@{tmp}", "--jq", ".html_url"])
                rec["target"] = "commit comment"
            os.unlink(tmp)
            rec.update({"body_bytes": len(body)}
                       | ({"state": "published", "url": url} if code == 0
                          else {"state": "error", "why": err[:500]}))

    with open(out_path, "w") as fh:
        json.dump(rec, fh, indent=1)
    print(f"{time.strftime('%H:%M:%S')} publish {rec.get('state')}: sha {str(sha)[:12]} "
          f"-> {rec.get('target', '-')} {rec.get('url', '')} ({os.path.basename(out_path)})")
    return 0  # never fail the caller; the record is the outcome


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"publish crashed: {exc!r}", file=sys.stderr)
        sys.exit(0)
