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

PID="${1:?usage: gnhf-watch.sh <gnhf-pid>   (STALL_MIN, MAX_HOURS, COST_MAX via env)}"
STALL_MIN="${STALL_MIN:-25}"
MAX_HOURS="${MAX_HOURS:-8}"
COST_MAX="${COST_MAX:-0}"          # US dollars, decimal ok. 0 disables the spend cap.

ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "gnhf-watch: not a git repo" >&2; exit 1; }
RUNS="$ROOT/.gnhf/runs"
RUN_DIR=""                         # resolved lazily from PID; see the scoping note below
T0=$(date +%s)
say() { echo "gnhf-watch: $*" >&2; }

# ARGUMENT VALIDATION, AND WHY IT IS FATAL. The argument is a PID, but every launch recipe in
# docs/AFK.md passes gnhf's own flags here instead. With `--agent` as $1, `kill -0 --agent`
# fails, the while loop never runs, and the script falls through to "exited on its own" and
# exits 0 -- a no-op that is INDISTINGUISHABLE from a successful watch. That is the worst
# possible failure for a watchdog, so it dies loudly instead.
case "$PID" in
  ''|*[!0-9]*) say "FATAL: '$PID' is not a pid. Start gnhf first, then pass its pid."
               say "  gnhf ... & ; STALL_MIN=25 harness/gnhf-watch.sh \$!"
               exit 1 ;;
esac
kill -0 "$PID" 2>/dev/null || { say "FATAL: no live process with pid $PID"; exit 1; }

# BILL_MAX was tokens and over-counted ~2.8x. Refuse it rather than reinterpret a stale number
# as dollars, which would silently turn a 3000000-token cap into a $3M one.
[ -z "${BILL_MAX:-}" ] || { say "FATAL: BILL_MAX is gone; it over-counted ~2.8x. Use COST_MAX (US dollars)."; exit 1; }

# The accountant must not fail open, in EITHER direction. A missing file is caught here; a
# helper that is present but exits non-zero is caught at the call site. The first version of
# this guarded only the missing file and left `|| echo "0 0"` at the call site, which reports
# zero spend on any runtime failure and reads as "well under budget" for the rest of the night.
# TESTED: a helper stubbed to exit 3 yielded exact=0, so COST_MAX could never fire.
SPEND="$ROOT/harness/gnhf-spend.py"
SPEND_FAIL_MAX="${SPEND_FAIL_MAX:-3}"   # WHICH consecutive failure stops the run, not how many
spend_fails=0
if [ "$(awk -v c="$COST_MAX" 'BEGIN{print (c>0)?1:0}')" = 1 ] && [ ! -f "$SPEND" ]; then
  say "FATAL: COST_MAX is set but $SPEND is missing; the cap would silently never fire."
  exit 1
fi

say "watching pid $PID (stall ${STALL_MIN}m, wall ${MAX_HOURS}h, cap \$${COST_MAX}, runs $RUNS)"

reason=""
while kill -0 "$PID" 2>/dev/null; do
  sleep 60
  now=$(date +%s)

  if [ "$(( (now - T0) / 3600 ))" -ge "$MAX_HOURS" ]; then
    reason="wall clock: ${MAX_HOURS}h elapsed"
    break
  fi

  # SCOPE TO THIS RUN, NOT TO EVERY RUN EVER. .gnhf/runs is never pruned, so a glob over all of
  # it charges this run for every prior run's tokens and lets a PRIOR run's files answer the
  # "has anything been written yet" question -- which would fire the stall detector during this
  # run's bootstrap. gnhf's run:start line carries both its pid and its runDir, so the mapping
  # is exact. Resolved inside the loop because gnhf has not written the log yet at second 0.
  if [ -z "$RUN_DIR" ]; then
    RUN_DIR=$(python3 - "$RUNS" "$PID" <<'PY' 2>/dev/null || true
import json, sys, glob, os
# Parse rather than string-match the line. A prefilter like `'"event":"run:start"' in line`
# silently misses the moment gnhf emits JSON with spaces after its colons, and the failure mode
# is the watchdog never resolving a run dir and never checking spend at all.
runs, pid = sys.argv[1], int(sys.argv[2])
for lg in glob.glob(os.path.join(runs, "*", "gnhf.log")):
    for line in open(lg, errors="replace"):
        try: d = json.loads(line)
        except Exception: continue
        if d.get("event") == "run:start" and d.get("pid") == pid:
            print(os.path.dirname(lg)); sys.exit(0)
PY
)
    [ -n "$RUN_DIR" ] && say "run dir: $RUN_DIR"
  fi
  [ -n "$RUN_DIR" ] || continue    # gnhf has not started writing; nothing to judge yet

  # iteration-*.jsonl is the agent's live output stream (docs/AFK.md 1.4), so its mtime is the
  # only free liveness signal gnhf offers. Two finds rather than a stat, because stat's mtime
  # flag is not portable and -newermt is: if iteration files EXIST but none is fresh, the run is
  # stalled. No iteration file yet is a run still starting up and must NOT fire.
  any=$(find "$RUN_DIR" -name 'iteration-*.jsonl' -type f 2>/dev/null | head -1)
  [ -n "$any" ] || continue
  fresh=$(find "$RUN_DIR" -name 'iteration-*.jsonl' -type f -newermt "-${STALL_MIN} minutes" 2>/dev/null | head -1)
  if [ -z "$fresh" ]; then
    reason="stalled: no iteration write in ${STALL_MIN}m"
    break
  fi

  # SPEND CAP, IN DOLLARS. gnhf's own --max-tokens counts cache reads at FULL weight
  # (docs/AFK.md 1.6), so it cannot express "spend at most N". The previous version of this
  # block tried to, in tokens, and was wrong four ways. All four are MEASURED against
  # .gnhf/runs/you-are-an-unattende-e196d4 on 2026-08-06, where it reported 2,717,201 against a
  # true $29.92:
  #
  #   1. It summed `assistant` EVENTS. Claude Code emits one per content block, all carrying the
  #      same message id and a byte-identical usage object (50 of 74 ids in iteration 1 repeat,
  #      one 3x). Raw 1,732,432 vs deduped 742,405 = 2.33x.
  #   2. It then ALSO summed `result` events, which are each iteration's cumulative total. The
  #      two together double-count. 1+2 compound to 2.76x.
  #   3. It globbed every run dir ever created, so a prior run's tokens were charged to this one.
  #   4. Its formula excluded cache reads on the theory that they were "already paid to write".
  #      They are not: they bill at 0.1x input, and on this run they were 55% of the real cost
  #      ($16.32 of $29.92). A cost metric that omits the largest cost component is not one.
  #
  # So: take gnhf's own total_cost_usd per finished iteration, which is exact and needs no price
  # table, and add a floor for the iteration still running. TESTED both directions.
  if [ "$(awk -v c="$COST_MAX" 'BEGIN{print (c>0)?1:0}')" = 1 ]; then
    # Fail CLOSED. If spend cannot be measured, the cap is not being enforced, and continuing
    # is spending blind. A few consecutive failures are tolerated so a transient blip does not
    # kill an 8-hour run; at the measured burn of ~$29/hr, three minutes of blindness is ~$1.50.
    # Garbage output counts as a failure too: a non-numeric field would reach awk as 0 and read
    # as zero spend, which is the same fail-open one layer down.
    if spend_out=$(python3 "$SPEND" "$RUN_DIR" 2>&1) \
       && [ "$(awk '{print (NF==2 && $1+0==$1 && $2+0==$2) ? 1 : 0}' <<<"$spend_out")" = 1 ]; then
      spend_fails=0
      read -r spent_exact spent_floor <<<"$spend_out"
    else
      spend_fails=$((spend_fails + 1))
      say "spend accounting failed ${spend_fails}/${SPEND_FAIL_MAX}: ${spend_out}"
      if [ "$spend_fails" -ge "$SPEND_FAIL_MAX" ]; then
        reason="spend accounting failed ${spend_fails}x running; cannot measure spend, so stopping rather than spending blind"
        break
      fi
      continue
    fi
    if [ "$(awk -v a="${spent_exact:-0}" -v b="${spent_floor:-0}" -v c="$COST_MAX" 'BEGIN{print (a+b>=c)?1:0}')" = 1 ]; then
      reason=$(printf 'spend cap: $%.2f (>= $%s) -- $%.2f billed over finished iterations, $%.2f floor for the one in flight' \
               "$(awk -v a="$spent_exact" -v b="$spent_floor" 'BEGIN{print a+b}')" "$COST_MAX" "$spent_exact" "$spent_floor")
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
# Matched on gnhf's OWN flag PAIR, not on the word "claude" and not on the first flag alone.
# Both earlier versions over-matched. `pgrep -fl claude` came first and was useless: MEASURED, it
# returned ten Claude.app Electron helpers plus the captain's live crewmate, burying the one line
# that matters under a page of --field-trial-handle. `--output-format stream-json` alone replaced
# it and read as narrow, but the comment here claimed a discriminator the pattern did not carry:
# the reasoning was about that flag TOGETHER WITH --json-schema, and only the first half was in
# the pgrep. MEASURED 2026-08-06 with no gnhf agent running, it matched five processes and every
# one was an interactive Claude Code session, which passes --output-format stream-json too.
#
# The pair is safe to require. buildClaudeArgs (docs/AFK.md 1.7) emits
# `--output-format stream-json --json-schema <schema>` adjacently and unconditionally, and
# isReservedAgentArg refuses both flags in agentArgsOverride, so no config can reorder, split or
# duplicate them. MEASURED the same day against a process wearing that documented shape: the pair
# matched it and skipped all five interactive sessions.
#
# The residual risk is SILENT, so it is written down rather than papered over: if a future gnhf
# reorders those flags the pair matches nothing, and nothing is also what a clean reap looks like.
# Re-check against buildClaudeArgs when gnhf moves off 0.1.43. A widening fallback was considered
# and rejected -- it would fire on every successful stop, since a correct reap and a stale pattern
# are the same empty match, and it would reprint the noise this narrowing exists to remove.
leftover="$(pgrep -fl -- '--output-format stream-json --json-schema' 2>/dev/null || true)"
if [ -n "$leftover" ]; then
  say "SURVIVING claude process(es) -- gnhf spawns detached, so check these by hand:"
  printf '%s\n' "$leftover" >&2
fi
say "stopped. The current iteration is uncommitted BY DESIGN; read it before cleaning up."
exit 2
