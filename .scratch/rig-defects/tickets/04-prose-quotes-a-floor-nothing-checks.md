# Prose quotes probe scores and nothing checks them against the floor

Type: task
Mode: AFK
Status: open
Assignee: -
Blocked by: -

## Question

A sweep of every `probe_*.py` score quoted in the prose, compared against that probe's own
`Results(expect=N)`, found **29 mismatches across 14 documents**. Four were operator-facing and are
fixed; the rest are still there.

The fixed four were in the rig manual's run list, which is a "what you should see" block:

| doc said | live floor |
|---|---|
| `probe_control_wiring.py # 14/14` | 16 |
| `probe_pool.py # 24/24` | 33 |
| `probe_arm_factory.py # 19/19` | 23 |
| `probe_gate_scope.py # 30/30` | 32 |

An operator who ran `probe_pool.py`, saw `33/33 passed`, and compared it against the manual had a
manual telling them to expect 24. That is the whole failure: not a wrong number in a report, but a
wrong number in an instruction.

The other 25 sit in phase-outcome documents and are mostly legitimate history — "documented RED at
13/16" describes an incident and should stay. **The open question is how to tell those two apart
mechanically**, because a reader cannot, and the ratio is bad: 4 real failures in 29 hits.

One case is neither, and it is the reason this is a ticket rather than a cleanup:
[docs/CITE.md](../../../docs/CITE.md) §6 says *"`verify_handoff.py` must be re-run before 21/21 can
be quoted"* and, two words later, *"Its floor is 22."* `verify_handoff.py` really does declare
`Results(expect=22)`, so the 21/21 that sentence is waiting to quote would be a SHORT RUN. The
document is holding open an item whose stated success condition is a failure.

## What would close it

A probe leg, not a cleanup pass. The data is already computable: parse `Results(expect=N)` from
each `probe_*.py`, find every `probe_x.py ... N/M` in the prose, and flag the ones that disagree.
`probe_citations.py` already walks every document and already resolves paths, so it is the natural
host, and `gate/citegraph.py`'s owned-file scoping already exists.

The design question this ticket exists to settle: **what distinguishes a quoted score that is an
instruction from one that is history?** Options worth weighing:

- A date or phase marker on the sentence ("documented RED at 13/16" vs a bare `# 13/16`).
- Position: inside a fenced command block is an instruction; inside prose is history.
- An explicit opt-out marker, the way `docs/OUTCOME.md` §2 already writes broken citations without a
  colon so `probe_citations.py` cannot mistake a specimen for a target.

The third is the repo's existing answer to exactly this problem and is probably the cheapest.

Whatever the rule, the sweep should print what it skipped. A checker that silently narrows is the
defect this repo keeps re-finding.
