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
