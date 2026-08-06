# Firstmate drives the cockpit

Type: task
Mode: AFK
Status: open
Assignee: -
Blocked by: 03

## Question

Decided 2026-08-05: the captain does not learn to operate the cockpit. Firstmate operates it on the
captain's behalf, and the only thing the captain learns is how to talk to firstmate.

This came out of the grilling as the actual blocker. Asked why stock Claude Code was still the daily
driver, the answer was "I don't know how to operate within the harness." `docs/E2E.md` is already a
written operator walk and it did not close the gap, so a second document is not the fix. The fix is
that there is less to know.

It is feasible because `harness/hb-fleet.sh` already owns the tmux topology. Pane selection is another
verb alongside `spawn`, `peek` and `state`, not a new mechanism.

The verbs to add, each one a thing the captain currently has to do with tmux keys:

- **focus a crewmate**: bring its pane to the front so "show me what crewmate 3 is doing" is a
  sentence rather than a chord.
- **open a diff in the nvim pane**: the handoff ticket 13 needs, and useful on its own.
- **rearrange**: whatever minimum lets firstmate put the right two panes side by side.

Three constraints that are not negotiable:

1. `/firstmate`'s hard rules still hold. Driving the cockpit is not editing a crewmate's files, and a
   captain typing directly into a crew pane stays authoritative intervention to reconcile with, never
   to fight.
2. Every verb is idempotent and names its skips. `hb-fleet.sh start` already works this way: absent
   capabilities are named skips, never refusals. Match it.
3. Anything firstmate can drive on the captain's behalf comes **off** the `C-b ?` command card. The
   card is a scarce, non-scrolling popup whose geometry has already caused one measured failure, and
   the point of this ticket is that there is less to remember, not more.

Blocked by ticket 03 because the firstmate contract settles what the first mate is allowed to do
before new powers are added to it.

**Done looks like:** the captain can say "show me crewmate 3" and "open that diff" to firstmate and
the cockpit does it, with no tmux keys pressed by the captain, TESTED against a live fleet rather than
argued from the script.

## Comments

Overlaps ticket 04, which renders the frontier in the cockpit. Same file, different verbs. Whoever
takes the second one should read the first one's resolution.
