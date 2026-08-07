#!/bin/sh
# Orientation channel: this project's settled decisions -> a fresh Claude Code session's context.
#
# The Claude-side twin of the opencode plugin's `experimental.chat.system.transform` injection.
# Both read the SAME rendered block from `harness/memory.py orient`, and neither renders it
# itself. That is the point: heads-only, VERIFIED-or-TESTED-only, deterministic sort and
# truncation at a record boundary are the rules, and a rule implemented once in TypeScript and
# once in shell is a rule that will disagree with itself on the day it matters.
#
# A SECOND SessionStart ENTRY, not an addition to fleet-state.sh. That script's contract is
# fail-open state reporting for the fleet supervisor, and it is asserted as such by
# probe_fleet_claude.py. Loading a second responsibility onto a fail-open script means a failure
# in either half is silent in both, and it makes the existing probe's green ambiguous about
# which half it proved.
#
# CONTRACT, and its confidence is stated rather than assumed: a SessionStart hook's
# `hookSpecificOutput.additionalContext` is added to the starting session's context. This is
# INFERRED from Claude Code's documented hook interface, not TESTED here — driving a real
# SessionStart requires starting a session, which this repo's free suite cannot do. What IS
# tested is everything on this side of that boundary: that the block renders, that it holds only
# what it should, and that this script emits well-formed JSON carrying it. If the contract is
# wrong the failure is a session that starts without orientation, which is where every session
# started before this file existed.
#
# FAIL-OPEN, same as fleet-state.sh: every path exits 0 and emits nothing rather than something
# malformed. A hook that breaks session startup to deliver a memory has inverted its own value.

[ "${HEALBOT_ORIENT:-on}" = "off" ] && exit 0

# The cwd is the session's project directory, which is the whole input this needs — memory.py
# resolves the project from it. `git rev-parse --show-toplevel` rather than the cwd itself so a
# session started in a subdirectory orients to the same store as one started at the root.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
[ -n "$ROOT" ] || exit 0

# memory.py is found relative to THIS SCRIPT, not relative to $ROOT. The two are the same only
# when the project being worked on is healbot itself; in any other project $ROOT/harness/ does
# not exist, and that is the case the store was moved out of the repository to serve.
HERE="$(cd "$(dirname "$0")" 2>/dev/null && pwd)" || exit 0
MEM="$HERE/../../memory.py"
[ -f "$MEM" ] || exit 0

PYBIN="$(command -v python3 2>/dev/null || command -v python 2>/dev/null)"
[ -n "$PYBIN" ] || exit 0

BLOCK="$("$PYBIN" "$MEM" orient --dir "$ROOT" 2>/dev/null)" || exit 0
[ -n "$BLOCK" ] || exit 0

# json.dumps rather than hand-rolled quoting: the block carries prose with quotes and newlines in
# it, and a sed-escaped heredoc is how a valid block becomes invalid JSON that the harness drops
# in silence. The payload goes through the environment for the same reason the fleet-state hook
# does it — a heredoc would be read as the program.
HB_BLOCK="$BLOCK" "$PYBIN" -c '
import json
import os

print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": os.environ["HB_BLOCK"],
}}))
' 2>/dev/null || exit 0
exit 0
