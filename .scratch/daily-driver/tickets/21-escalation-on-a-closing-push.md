# Does the path escalation apply to a push that only closes findings

Type: grilling
Mode: HITL
Status: open
Assignee: -
Blocked by: -

## Question

[When does the automatic review run](12-when-does-the-review-run.md) narrowed the path
escalation to `gate/`, `fork/` and `.carryover/verified/probe_*`, dropping plain `harness/`
because it fired on 25 of the last 60 commits.

**The narrowing went the wrong way: it dropped the narrower path and kept the wider one.**
Measured in ticket 12's own unit, commits that touch the path, over one identical 60-commit
window:

| escalation set | commits touched |
|---|---|
| `gate/` \| `fork/` \| `probe_*` — the set ticket 12 KEPT | **33/60 (55%)** |
| `harness/` — the set ticket 12 DROPPED for firing too often | 19/60 (32%) |

Both rows are printed by [21-push-exit-backtest.py](../research/21-push-exit-backtest.py). An
earlier draft of this ticket claimed 38% against 42%, which compared a share of pushes where a
finding LANDED on an escalation path against a share of commits that TOUCH one — two different
quantities. The model review of the 4c60a9e push caught it. The corrected comparison is the
stronger claim, not a weaker one.

That is tolerable on a push opening new surface. On a push whose entire content is a correction of
the previous review it is the loop:

| finding on a repair push | count | share |
|---|---|---|
| warning/info elsewhere | 44 | 51% |
| warning/info on an escalation path | 34 | 40% |
| error-grade (blocks under every rule) | 8 | 9% |

The escalation rule obligates 4.25x more repair work than severity does, and it does so on the
class of push that carries no new engineering. It is structural rather than accidental: `gate/`,
`fork/` and `.carryover/verified/probe_*` is precisely where this repo does its gate and probe
work, so a correction to the gate is escalated by the rule the gate wrote about itself.

**The decision.** Does the escalation apply to what a CLOSING push must repair before it may
leave, or only to the bar at which an OPEN push is reviewed?

| rule applied to a repair push | discharges first try | expected repairs per chain |
|---|---|---|
| today: every finding obligates | 25% | 4.0 |
| error-grade + escalation paths | 62% | 1.6 |
| error-grade only | 88% | 1.1 |

## What argues each way

**For dropping it on a closing push.** The escalation exists to protect things that can make the
measurement lie, and that protection was already spent: the material got a full-bar review on the
open push. A second full-bar review of the correction is what generates the chain. Error-grade
findings still refuse regardless of path, so the 8 findings in the window that named a real defect
on an escalation path are unaffected. What is dropped is 34 warning/info findings, and they do not
vanish — they leave as stubs under
[a non-blocking finding leaves as a proposed stub](23-findings-leave-as-stubs.md), which is more
durable than today, where they live in a gitignored record nothing reads.

**Against, and this is the strongest argument.**
[Were the review's error findings ever right](16-calibrate-the-review-bar.md) measured that
severity as the reviewer assigns it did NOT predict what the captain acted on: one review had both
`error` findings left open to this day while its `warning` and `info` were fixed in four minutes.
Any rule that keys on severity inherits that noise, and this one keys on severity twice. A real
gate defect graded `warning` would leave as a stub rather than being repaired before the push.

**The honest size of the risk.** Over the window, dropping escalation on closing pushes moves 34
findings from "repair now" to "tracked stub". Nobody has read those 34 to see how many were real.
That read is a day's work over records already on disk and would settle this ticket with evidence
rather than argument, the way ticket 16 settled its own question. It costs no credits.

## Not in scope here

Whether `blocking` mode goes on. That ruling is still the captain's and is carried on
[a blocked review's diff reaches the nvim pane](13-blocked-diff-reaches-nvim.md). This ticket is
about which findings obligate a repair, which is a live question in advisory mode too: in advisory
mode the obligation is on the agent reading the terminal, and that agent has been discharging it
by pushing again.

## Numbers in this ticket

Every figure above is printed by
[21-push-exit-backtest.py](../research/21-push-exit-backtest.py), read from the main checkout's
`gate/runs/`. Re-run it rather than trusting the table; the records grow with every push and these
are a record of the run on 2026-08-08, not a standing expectation. The script's own docstring
carries the one approximation it makes, which is that the open/closing split is inferred from
commit subjects because the `Review-chain:` trailer does not exist yet.
