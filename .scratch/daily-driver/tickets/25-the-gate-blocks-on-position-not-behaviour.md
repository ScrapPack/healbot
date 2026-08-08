# The gate blocks on documentation position while the only judge of behaviour cannot refuse

Type: grilling
Mode: HITL
Status: open
Assignee: -
Blocked by: -

## Question

The push exit's severity ordering is inverted, and it is inverted by construction rather than by
accident.

**Four Tier-1 rows block every push** (`gate/gate.py:175`-`184`): `rig-contract`, `citations`,
`twin`, `review-parse`. All four are deterministic, free and fast, which is why they can block.
One of them, `citations`, refuses a push because a `file:line` pointer landed on the wrong line.

**The only judge of behaviour cannot refuse anything.** `gate/review.py:46` defaults `MODE` to
`advisory`, and it has been advisory for essentially every review ever run.

So a push that moves a citation by one line is refused, and a push that ships a logic defect the
reviewer explicitly flagged as `error` proceeds. That is the ordering, stated plainly. It is not
obviously wrong — determinism is a real reason to let something block, and nondeterminism is a real
reason to withhold that power, which `gate/review.py` argues in its own header. But nobody has
decided it as a question; it fell out of two independently reasonable choices.

**The blocking row is also partially blind.** `gate/citegraph.py:214` skips every file that does
not end in `.md`, so citations written in hand-written source are outside the sweep entirely. A
measurement on 2026-08-07 put that at 247 of 895 citations (28%) and found one real broken pointer
among them, in `gate/gate.py` itself; that count needs re-running before it is quoted as current,
and the point that survives without it is the VERIFIED one: the walk gates on `.md`, so source
citations are checked by nothing.

## The question

Not "switch blocking on" — that ruling is carried on
[a blocked review's diff reaches the nvim pane](13-blocked-diff-reaches-nvim.md) and is not this
ticket's to take. The question here is narrower and prior to it:

**Should a deterministic check that measures document POSITION hold refusal power that no check of
BEHAVIOUR holds, and if so, is that a principle or an accident we are living with?**

Three positions:

1. **It is correct and should be said out loud.** Only reproducible checks may refuse; a
   nondeterministic judge advises. The gate already argues this. Then the fix is documentation, and
   the honest consequence is that behaviour is never gated at push time by anything.
2. **The asymmetry is real and should narrow.** Either the citation row stops refusing for
   positional rot alone, or some deterministic behaviour check earns Tier 1. The staleness stage is
   the obvious candidate and is the subject of
   [the staleness stage never left shadow mode](26-staleness-never-left-shadow-mode.md): it is
   deterministic, free, runs in a median 0.21 s, and unlike the review it is silent on most pushes.
3. **The inversion is the point.** Positional rot is cheap to fix and expensive to accumulate,
   behaviour defects are the reverse, and gating the cheap thing is how the corpus stayed
   navigable. Then it is a principle, and it should be written down as one.

## Why it belongs to the push exit

Because it decides what "the push passed" means. Everything in
[a push declares what it closes](22-a-push-declares-what-it-closes.md) is built on the idea that
obligations can be graded and discharged. If the grading at the bottom of the stack says a moved
line refuses and a logic defect does not, then the checkout counter is tallying against a scale
nobody chose.
