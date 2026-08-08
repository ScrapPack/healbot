# A push declares what it closes, and a checkout stage tallies it

Type: task
Mode: AFK
Status: open
Assignee: -
Blocked by: -

## Question

The push exit has no exit condition. `gate.py` has one and it is deterministic. Everything after
it reports: the review is advisory (`gate/review.py:46`), staleness is shadow, prose never
refuses. The push always leaves. What never terminates is the OPERATOR's loop, and it never
terminates because the review emits obligations and nothing in the system can discharge one.

Three facts, all VERIFIED by reading the code:

1. The `gate/runs/` rule in `.gitignore` means a finding does not survive a worktree, a machine,
   or a fresh clone. (Cited as rule text, not `file:line`: `.gitignore` is an extensionless
   dotfile, so the sweep's pattern at `gate/citegraph.py:91` cannot see a citation into it and
   would run green over the rot forever.)
2. `gate/review.py` never reads a prior record. `RUNS` appears at `gate/review.py:45`,
   `gate/review.py:285` and `gate/review.py:286` — define, mkdir, write. The store is write-only.
3. Nothing else consumes findings either. The only reader of any review record is
   `gate/publish.py:154`, which takes the newest one to attach as a comment.

So the only move available to an agent reading the terminal is to fix the finding and push. That
push is new reviewable surface, which draws its own findings, which are new obligations. Measured
over the window, **77% of every reviewed push is a repair of a prior review** (56 of 73) and no
substantive push in the window ever came back clean (0 of 17). Expected repairs per chain: 4.0.
The in-repo skill `citation-hygiene` measured the same shape independently on 2026-08-05 and got
17 chains, median 3 rounds, max 8.

**There is no dedup ledger in this design, and that is a measured decision rather than an
omission.** Findings do not recur: 148 findings in the window, 148 distinct (file, normalised
summary) keys, zero seen twice. The reviewer is not nagging about old material, it is generating
new material against whatever surface it is handed. A ledger keyed on finding identity would
therefore buy nothing.

## What to build

**A `Review-chain:` commit trailer.** A commit that closes findings from a prior review names that
review's record id:

```
Review-chain: 20260807-193224-8334
```

Git-native, parsed by `git interpret-trailers --parse`, declarative rather than guessed. Fifty-four
commits already carry this relationship in prose ("review findings from the a2594f8 push"); the
trailer makes it machine-readable. A push whose commits all carry the trailer is CLOSING. Any push
with at least one commit that does not is OPENING new surface, which is the fail-closed direction:
a hybrid commit gets the full bar.

**`gate/checkout.py`, a pure function over the review record and the push class.** It does not
call a model and it does not re-prompt the reviewer. The reviewer keeps emitting its quota; this
stage decides what the quota obligates. That is what makes the whole thing testable — the predicate
replays deterministically over every record already on disk, which is what
[21-push-exit-backtest.py](../research/21-push-exit-backtest.py) does.

The predicate. A push is DISCHARGED when no obligation is open, where an obligation is:

- error-grade, fail-closed exactly as `gate/review.py:262` already defines it (anything not
  explicitly `warning` or `info`, so `critical` and untagged both count); or
- on an OPEN push, a `warning`; or
- on a CLOSING push, a finding on an escalation path — **pending
  [does the path escalation apply to a push that only closes findings](21-escalation-on-a-closing-push.md).**
  Build it behind that switch and default to ticket 12's rule as it stands. Do not decide 21 here.

Everything else leaves as a stub under
[a non-blocking finding leaves as a proposed stub](23-findings-leave-as-stubs.md).

**Three outcomes to print, never two.** `discharged`, `owes` (obligations open), and `unmeasured`
(the review could not run — `gate/review.py` already returns that state and it must not render as
either of the others). Same rule ticket 12 set for the crewmate path.

**The attempt cap.** Ticket 12 decided three attempts per objective then the captain. The pre-push
chain has no cap at all today. The third closing push on one chain discharges regardless, its
remaining obligations become stubs, and it says so in one line.

## Advisory first

Captain's ruling 2026-08-08: this lands advisory. No exit code changes and the blocking ruling
stays open on
[a blocked review's diff reaches the nvim pane](13-blocked-diff-reaches-nvim.md). The scope rule
alone is the loop-breaker, because in advisory mode the obligation was always on the agent reading
the terminal rather than on `git push`, and that is exactly what this stage changes.

## Done looks like

A repair push carrying a `Review-chain:` trailer prints its obligations and its stubs, and the
count of obligations is lower than the count of findings on the same record. TESTED with a control
in the other direction: the same diff pushed WITHOUT the trailer is classed as opening new surface
and obligates more. Both directions, because a stage that always says "discharged" would pass the
first test alone.

A probe covers the predicate against fixture records, per `rig-assertion-discipline`. The predicate
is pure, so the probe needs no fleet, no network and no credits — which means there is no excuse
for the assertions being incapable of failing.
