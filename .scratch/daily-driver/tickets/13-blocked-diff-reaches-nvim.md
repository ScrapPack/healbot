# A blocked review's diff reaches the nvim pane

Type: task
Mode: AFK
Status: open
Assignee: -
Blocked by: 11, 12, 16

## Question

This is the missing half of the whole destination. The routing rule exists and the review exists;
nothing carries a blocked diff to the captain's eyes.

Today `gate/review.py` in `blocking` mode exits 2 and records findings to
`gate/runs/<timestamp>-review.json`. That is a file the captain has to know to go and read, which is
precisely the operator-knowledge problem ticket 01 diagnosed. The destination says neovim shows the
diffs a human must judge, so the review's verdict has to arrive in the nvim pane by itself.

The path, once tickets 11 and 12 have settled the verbs and the trigger:

- A blocked review hands its diff and its findings to firstmate.
- Firstmate opens the diff in the nvim pane using ticket 11's verb, and says in one line what blocked
  and why, naming the crewmate and the objective.
- Findings are anchored so the captain lands on the cited line rather than on the top of a file. The
  review already produces file and line citations, so this is a formatting decision, not a new
  capability.
- Everything that passes clears silently. Silence is the signal that the bar worked, so it must not be
  cluttered with reports of things that went fine.

Two things to get right rather than to discover later:

1. **Do not lose the verdict when the captain is away.** The cockpit is one terminal and the captain
   is not always at it. A blocked diff that nobody looked at has to still be blocked in the morning,
   and findable, which argues for the review record staying authoritative and the nvim pane being a
   view of it rather than the only copy.
2. **A crewmate must not clear its own block.** Same reasoning as a crewmate never closing its own
   ticket: a claim of done is a claim, not a result.

**Done looks like:** a crewmate produces a diff that trips the bar, and without the captain running
anything, the nvim pane shows that diff at the cited line with one line of explanation. TESTED
end to end against a live fleet, with a control in the other direction: a diff below the bar clears
and the pane stays untouched.

## What ticket 12 settled, and what it hands here

Ticket 12 closed 2026-08-05. Read its Resolution before starting; the trigger, the mode split, the
attempt cap, the refusal-over-truncation rule and the narrowed path escalation are all decided there
and are not to be re-opened here. Three things land directly on this ticket:

1. **A third collect mode is required.** A completion review run with no base against a crewmate
   that committed its work reviews an EMPTY diff and passes. Take the slot's recorded baseline sha
   as `--base` and review baseline...HEAD plus whatever is uncommitted on top. Ticket 12 carries the
   evidence.
2. **Run the slot's own copy of `review.py`.** `ROOT` is `__file__`-derived, so the main checkout's
   copy reviews the main checkout however the refs are aimed.
3. **Three outcomes to render, not two.** `blocked` (a reviewer said no), `unmeasured` (nothing
   could measure it, exit 3) and pass. Only pass clears silently. `unmeasured` must never render as
   either of the other two.

Ticket 16 closed 2026-08-05 and delivered the measurement: 18 real, 0 wrong, 7 unacted, a 0%
false-positive rate over the acted-on findings, with the caveats in its resolution. **What 16 did
NOT deliver is the ruling.** The captain has not decided whether that rate clears `blocking` to be
switched on, and this ticket's done-condition cannot be met until it does, because the done-condition
is a crewmate's diff actually tripping the bar. Build against a `blocking` review by all means; do
not read a closed 16 as permission to switch it on, and do not switch it on here.

Take 16's finding with you: severity as the reviewer assigns it did not predict what the captain
acted on. In one review both `error` findings were left unrepaired and are still open, while the
`warning` and `info` from the same review were fixed within four minutes. That is the ordering this
ticket renders to the captain.
