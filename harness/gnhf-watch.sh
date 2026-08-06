#!/bin/bash
# The clock gnhf does not have.
#
# WHY THIS EXISTS. docs/AFK.md 1.5 is the measured finding: gnhf has SIX stop conditions and
# none of them is a clock. There is no wall-clock timeout, no per-iteration timeout and no
# inactivity detector (grepping the bundle for `inactivity` and `idleTimeout` returns zero
# hits; the only withTimeout is on the ACP path, not on ClaudeAgent). The consequence is the
# load-bearing one: a PARKED ITERATION DEFEATS BOTH CAPS AT ONCE. --max-iterations is only
# checked between iterations so it cannot interrupt one, and --max-tokens needs usage events
# that a parked process never emits. Unattended, that is a run that hangs until morning.
#
# So the AFK loop gets wrapped rather than trusted. This is the primary stop condition
# (docs/AFK.md 3.6), not a backstop.
#
# WHY IT IS IN THE REPO. A previous version was written 2026-07-31 into a session scratchpad
# and never committed. The scratchpad is gone and it had to be written again from the spec,
# which is the same lesson the review-fix chains keep teaching: a thing that lives only in a
# session artifact is a thing you will rebuild.
#
# USAGE
#     harness/gnhf-watch.sh <gnhf-pid>            # STALL_MIN and MAX_HOURS via env
#
# SIZING. Defaults STALL_MIN=25, MAX_HOURS=8. Tune the stall window ABOVE the slowest
# legitimate single operation, never below ~20 minutes or it kills working runs. Two measured
# ones to size against, both from the healbot-traps skill: verify_question.py polls three
# framings at 300 s each, so a run whose first two framings miss takes ~10 minutes before it
# reaches the grid and that is the rig working; and rig.py's wait_for checks its deadline only
# between calls while Api.__call__ defaults to timeout=900, so a 300 s budget can be held for
# 900.
#
# A forced stop leaves the current iteration uncommitted. That is intentional: the evidence of
# what it was doing when it hung is worth more than a clean tree.
set -u

PID="${1:?usage: gnhf-watch.sh <gnhf-pid>   (STALL_MIN, MAX_HOURS, BILL_MAX via env)}"
STALL_MIN="${STALL_MIN:-25}"
MAX_HOURS="${MAX_HOURS:-8}"
BILL_MAX="${BILL_MAX:-0}"          # 0 disables the billable cap

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "gnhf-watch: not a git repo" >&2; exit 1; }
RUNS="$ROOT/.gnhf/runs"
T0=$(date +%s)
say() { echo "gnhf-watch: $*" >&2; }

say "watching pid $PID (stall ${STALL_MIN}m, wall ${MAX_HOURS}h, runs $RUNS)"

reason=""
while kill -0 "$PID" 2>/dev/null; do
  sleep 60
  now=$(date +%s)

  if [ "$(( (now - T0) / 3600 ))" -ge "$MAX_HOURS" ]; then
    reason="wall clock: ${MAX_HOURS}h elapsed"
    break
  fi

  # .gnhf/runs/**/iteration-*.jsonl is the agent's live output stream (docs/AFK.md 1.4), so its
  # mtime is the only free liveness signal gnhf offers. Two finds rather than a stat, because
  # stat's mtime flag is not portable and -newermt is: if iteration files EXIST but none is
  # fresh, the run is stalled. An empty runs directory is a run that has not started writing
  # yet and must NOT fire -- that case is the one a naive check gets wrong.
  any=$(find "$RUNS" -name 'iteration-*.jsonl' -type f 2>/dev/null | head -1)
  [ -n "$any" ] || continue
  fresh=$(find "$RUNS" -name 'iteration-*.jsonl' -type f -newermt "-${STALL_MIN} minutes" 2>/dev/null | head -1)
  if [ -z "$fresh" ]; then
    reason="stalled: no iteration write in ${STALL_MIN}m"
    break
  fi

  # BILLABLE CAP. gnhf's own --max-tokens counts cache reads at FULL weight (docs/AFK.md 1.6),
  # and MEASURED on this repo 2026-08-05 that runs 10.2x ahead of billable usage: one iteration
  # reported 3,281,270 counted against 256,693 billable. So gnhf's cap cannot express "spend at
  # most N". This does. Billable is fresh input + cache WRITE + output; cache reads are what you
  # already paid to write, so they are excluded.
  if [ "$BILL_MAX" -gt 0 ]; then
    bill=$(python3 - "$RUNS" <<'PY' 2>/dev/null || echo 0
import json, sys, glob, os
t = 0
for f in glob.glob(os.path.join(sys.argv[1], "**", "iteration-*.jsonl"), recursive=True):
    for l in open(f, errors="replace"):
        try: d = json.loads(l)
        except Exception: continue
        u = (d.get("message") or {}).get("usage") or d.get("usage")
        if not u: continue
        t += u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("output_tokens", 0)
print(t)
PY
)
    if [ "${bill:-0}" -ge "$BILL_MAX" ]; then
      reason="billable cap: ${bill} >= ${BILL_MAX} tokens (fresh input + cache write + output)"
      break
    fi
  fi
done

if [ -z "$reason" ]; then
  say "gnhf pid $PID exited on its own; nothing to stop"
  exit 0
fi

say "STOPPING -- $reason"
kill -TERM "$PID" 2>/dev/null || true      # gnhf treats SIGTERM as an immediate force stop
sleep 10
if kill -0 "$PID" 2>/dev/null; then
  say "pid $PID survived SIGTERM; sending SIGKILL"
  kill -KILL "$PID" 2>/dev/null || true
fi

# gnhf spawns the backend detached:true, so killing gnhf does NOT necessarily take the agent
# with it. Report rather than kill: a surviving claude may be mid-write, and the operator
# deciding is better than this script guessing at 3am.
#
# Matched on gnhf's OWN invocation signature, not on the word "claude". A bare
# `pgrep -fl claude` was the first version and it was useless: MEASURED, it returned ten
# Claude.app Electron helpers plus the captain's live crewmate, burying the one line that
# matters under a page of --field-trial-handle. gnhf's buildClaudeArgs (docs/AFK.md 1.7)
# always passes --output-format stream-json together with --json-schema, which no
# interactive session and no hb-fleet crewmate does.
leftover="$(pgrep -fl -- '--output-format stream-json' 2>/dev/null || true)"
if [ -n "$leftover" ]; then
  say "SURVIVING claude process(es) -- gnhf spawns detached, so check these by hand:"
  printf '%s\n' "$leftover" >&2
fi
say "stopped. The current iteration is uncommitted BY DESIGN; read it before cleaning up."
exit 2
