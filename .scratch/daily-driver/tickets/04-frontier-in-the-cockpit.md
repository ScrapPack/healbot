# Frontier as a cockpit view

Type: task
Mode: AFK
Status: open
Assignee: -
Blocked by: 03

## Question

`/wayfinder` wants the frontier rendered visually so the captain sees what is takeable without
opening the map, and it uses the tracker's native blocking to get that. Local markdown has no such
UI, so the frontier is a command instead, documented and working in
`docs/agents/issue-tracker.md`.

A command is not a view. The healbot-native answer is the cockpit, not a browser: `harness/hb-fleet.sh`
already renders fleet state, and the frontier belongs beside crew occupancy where the captain is
already looking.

The work, once ticket 03 has settled who claims and who closes:

- A `map` verb on `hb-fleet.sh` that prints the frontier next to `ls` and `state`, so takeable work
  and crew capacity read together.
- Show the claim. An assigned ticket is not on the frontier, but the captain needs to see who holds
  what, and a stale claim is the failure mode worth surfacing.
- The blocking rule is implemented in exactly one place. The documented query owns it; the verb calls
  it or shares its implementation. Two implementations of the same rule will disagree.

Not in this ticket: any change to the map format, and any automation of claiming. Both are ticket 03's.

**Done looks like:** `hb-fleet.sh map` prints every open, unblocked, unassigned ticket by title with
its effort, plus every claimed ticket with its holder, and its output agrees with the documented query
on the same tree. A probe row guarding the agreement is welcome and is not required to close this.

## Comments

**2026-08-06, unattended loop (gnhf, branch `gnhf/you-are-an-unattende-e196d4`).** Half of this
ticket is built and committed. The other half is written, measured, and NOT in the tree, because
shipping it would break a document this loop is forbidden to repair. Both halves are below.

### What shipped

**The shared query grew the mode a renderer needs.** `.scratch/frontier.awk` now takes
`-v mode=claims` and prints every OPEN ticket that IS assigned, with its holder in `[brackets]`,
blocked or not. Default output is unchanged: TESTED byte-identical against `git show HEAD:` on the
live tree before and after. An unrecognised mode REFUSES at exit 2 instead of falling back to the
frontier — TESTED, deleting that guard prints 13 frontier rows at exit 0, which is a typo turning
takeable work into claimed work in silence.

This is the ticket's third bullet honoured ahead of its first. The claims half had to live in the
query, not in the caller: the header block gets one reader, or the two disagree about what
`Assignee:` means on the day someone writes it with nothing after it.

**Six probe rows, `probe_fleet_claude.py` floor 116 to 122, exit 0 at 122/122.** They drive the
shipped query over a five-ticket fixture whose blocker is ITSELF takeable, so flipping one
`Status:` moves two tickets in opposite directions. TESTED red in both directions: deleting the
blocker check takes the first row red, and the unknown-mode row goes red against a query with no
`BEGIN` guard. One row is scoped honestly rather than optimistically — the closing-the-blocker
control is a control for a rule that ignores `Status: closed`, NOT for the blocking rule existing,
and it stays green when the rule is deleted. The row above it is what catches that.

`docs/agents/issue-tracker.md` documents the second form and says plainly that no renderer calls
it yet.

### What did NOT ship, and why

`hb-fleet.sh map` is written, runs, and agrees with the documented query. It is reverted.

The verb needs one line on the command card, and that card is a LINE RANGE into the script's own
header (`hb_header`), so the entry cannot go anywhere but above every line in the file. One
inserted line shifts `resolve_pane` from line 276 to 277 — and line 276 is then blank. **A `grilling`/HITL
ticket cites that exact line**, and `probe_citations.py` goes red on a citation landing on a blank
line, which takes `gate/gate.py` to BLOCKED. Repairing it means editing a HITL ticket, which this
loop is prohibited from touching for any reason. TESTED both states: with the verb, 19/21 and exit
1; reverted, 21/21 and exit 0.

That is a real constraint and not a technicality. Every option that keeps the verb also games the
checker — compensating deletions above line 276, or merging two commands onto one card row — and
the citations would still be semantically wrong afterwards. Deferring the verb to whoever may edit
the ticket is the honest answer.

### Applying it, and what must move with it

Three edits to `harness/hb-fleet.sh`, then repair nine citations.

1. One card line, immediately after the `ls` row in the header comment:

       #   map                                       tracker frontier + claims, beside the census

2. `hb_header() { sed -n '4,25p' "$0"; }` becomes `'4,26p'`. The running tally of past bumps that
   sat in the comment above it is a number with nothing computing it and should go; the probe row
   `hb_header() still prints the whole header` is what actually holds the bound.

3. The branch, placed after the `ls)` arm and before `state)`. That position is load-bearing:
   `probe_fleet_claude.py`'s screen-reader census partitions the source on `\nstate)`…`\nsend)`, so
   an arm dropped between them silently joins what that predicate calls state's block.

   ```sh
   map)
     # The tracker's frontier and its claims, rendered beside the census so takeable work and crew
     # capacity read together. THIS VERB RENDERS; IT DOES NOT DECIDE. The blocking rule and the
     # header-block parse both live in .scratch/frontier.awk, which docs/agents/issue-tracker.md
     # names as their only implementation, and this branch calls it twice rather than owning a copy
     # of either.
     AWKF="$REPO/.scratch/frontier.awk"
     [ -f "$AWKF" ] || { echo "hb-fleet: no frontier query at $AWKF — this verb renders that file and holds no copy of its rule" >&2; exit 2; }
     # find -exec + rather than a shell glob: an unmatched glob expands to its own literal pattern
     # and awk would report "no such file" for a tracker that is merely empty.
     TCOUNT="$(find "$REPO/.scratch" -type f -path '*/tickets/*.md' | wc -l | tr -d ' ')"
     if [ "$TCOUNT" -eq 0 ]; then
       echo "hb-fleet: no tickets under $REPO/.scratch/*/tickets/ — nothing to render"
       exit 0
     fi
     echo "== frontier: open, unblocked, unassigned ($TCOUNT tickets read) =="
     FRONTIER="$(find "$REPO/.scratch" -type f -path '*/tickets/*.md' -exec awk -f "$AWKF" {} + | sort)"
     if [ -n "$FRONTIER" ]; then echo "$FRONTIER"; else echo "(nothing takeable — every open ticket is blocked or claimed)"; fi
     echo "== claims: open and assigned =="
     CLAIMS="$(find "$REPO/.scratch" -type f -path '*/tickets/*.md' -exec awk -v mode=claims -f "$AWKF" {} + | sort)"
     if [ -n "$CLAIMS" ]; then echo "$CLAIMS"; else echo "(nothing claimed)"; fi
     echo "== crew =="
     # The manifest is intent, exactly as `Assignee:` is (ticket 03 keeps liveness off the claim
     # line). So this prints the roster and sends the reader to `state` for liveness rather than
     # growing a second reading of it here.
     NAMES="$(manifest_names)"
     if [ -n "$NAMES" ]; then
       echo "$(echo "$NAMES" | wc -w | tr -d ' ') in the manifest: $NAMES"
     else
       echo "(no crewmates in $MANIFEST)"
     fi
     echo "liveness is '$0 state' — a claim whose holder is not a live crewmate is a stale claim"
     ;;
   ```

Then the citations. Each was re-derived against its own verbatim line, not by one offset — the
shifts are +1, +2 and +41 in the same file:

Every row below is a line of `harness/hb-fleet.sh`, and the numbers are written out rather than in
`file:line` form on purpose: a citation quoted as broken, written live, is indistinguishable from a
pointer to both a reader and to `probe_citations.py`.

| Cited in | was line | becomes line |
|---|---|---|
| ticket 12 | 69 | 70 |
| ticket 12 | 118 | 119 |
| ticket 17 (HITL) | 276 | 277 |
| ticket 17 (HITL) | 643 | 645 |
| ticket 17 (HITL) | 722 | 763 |
| ticket 17 (HITL) | 765 | 806 |
| ticket 17 (HITL) | 821 | 862 |
| ticket 17 (HITL) | 1023 | 1064 |
| ticket 17 (HITL) | 1033 | 1074 |

Only the 276 row is a gate failure; the other six in that ticket are semantic rot the probe cannot
see, and they are wrong all the same.

### What was verified about the verb before it was reverted

TESTED on this tree, all free, no credits:

- `sh -n` clean; `hb-fleet.sh map` exit 0, printing 13 frontier rows over 21 tickets read, an empty
  claims section, and the two-name crew roster from the live manifest.
- Its frontier section compared EQUAL to `awk -f .scratch/frontier.awk .scratch/*/tickets/*.md |
  sort`, the command `docs/agents/issue-tracker.md` gives a human. That is this ticket's
  done-condition, and it held.
- The comparison was measured over a non-empty list (13 rows), because two empty lists compare
  equal and would have passed for nothing.
- Controlled red: a verb piped through `tail -n +2` took the agreement row red, so the row
  discriminates rather than decorates.

Five further probe rows go with the verb and are not in the tree either — two holding the branch
onto the shared query from comment-stripped source (the mutation being a branch that greps
`Status: open` itself), and three running the shipped verb against the documented command. They
were green at 127/127 with the verb applied.

### Left open

- The verb itself, blocked as above. Nothing about it needs a decision except who may edit ticket
  17's citations.
- The crew section prints the manifest roster and points at `state` for liveness. It does not
  cross-reference a holder against live crewmates, so a stale claim is still a human read of two
  lists rather than a flagged row. Ticket 17's identity question sits underneath that, and this
  ticket should not pre-empt it.
- Effort is not printed, because the ticket header block has no effort key to print. The output's
  first column is the EFFORT DIRECTORY (`daily-driver`, `rig-defects`), which is what this
  ticket's "with its effort" reads as against the format `docs/agents/issue-tracker.md` defines.
  If a size estimate was meant, that is a format change and this ticket puts format changes in
  ticket 03.
