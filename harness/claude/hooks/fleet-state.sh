#!/bin/sh
# Fleet state channel: Claude Code lifecycle hooks -> one JSON state file per session.
#
# Registered in ../settings.json for SessionStart, Stop, and Notification. Claude Code
# hands hook commands a JSON object on stdin (session_id, cwd, transcript_path among its
# fields); this script records {event, at, cwd, transcript} at
# $HB_FLEET_DIR/state/<session_id>.json, last event wins. The fleet supervisor
# (harness/hb-fleet.sh) reads these files as its event channel and falls back to
# tmux capture-pane classification when a file is absent or stale — the same
# push-preferred, poll-backstop shape as firstmate's backend contract (docs/SHIP.md §3).
#
# State vocabulary the supervisor derives: session-start = booted, stop = idle (turn
# ended), notification = needs-attention (permission prompt or idle nag). Busy is the
# absence of a fresh stop/notification while the pane shows a spinner; the screen check
# owns that case, not this file.
#
# Stdin is captured in shell BEFORE python runs: `python3 - <<heredoc` would feed the
# heredoc to python AS its program via stdin, so the hook payload would be unreadable
# from inside it. TESTED both ways; the heredoc form silently wrote nothing.
#
# FAIL-OPEN IS THE CONTRACT. This script must never break a session: every failure path
# exits 0, and without HB_FLEET_DIR it is a no-op — so interactive harness sessions
# (e.g. the one-time login) run hook-silent. probe_fleet_claude.py feeds it garbage stdin
# and asserts exit 0 with no state written.

EVENT="${1:-unknown}"
[ -n "${HB_FLEET_DIR:-}" ] || exit 0
mkdir -p "$HB_FLEET_DIR/state" 2>/dev/null || exit 0
PAYLOAD="$(cat 2>/dev/null || true)"

HB_EVENT="$EVENT" HB_STATE_DIR="$HB_FLEET_DIR/state" HB_PAYLOAD="$PAYLOAD" python3 -c '
import json
import os
import sys
import time

try:
    payload = json.loads(os.environ.get("HB_PAYLOAD", ""))
except Exception:
    payload = {}
if not isinstance(payload, dict):
    payload = {}
sid = payload.get("session_id")
if not sid or not isinstance(sid, str) or "/" in sid:
    # No usable session id: nothing to key a state file on. Recording under a guessed
    # key would give the supervisor a confident wrong belief; silence keeps it on the
    # capture-pane fallback, which is the honest channel here.
    sys.exit(0)
rec = {
    "event": os.environ["HB_EVENT"],
    "at": int(time.time()),
    "cwd": payload.get("cwd"),
    "transcript": payload.get("transcript_path"),
}
path = os.path.join(os.environ["HB_STATE_DIR"], sid + ".json")
tmp = path + ".tmp"
with open(tmp, "w") as f:
    json.dump(rec, f)
os.replace(tmp, path)
' 2>/dev/null || exit 0
exit 0
