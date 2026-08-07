---
name: rig-assertion-discipline
description: Assertion discipline for healbot's test rig. Invoke BEFORE creating or editing any probe_*.py or verify_*.py under .carryover/verified/, before adding or changing any r.check row, and before trusting or quoting a green run. Distilled from eight assertions found incapable of failing across phases 5-12.
---

# Rig assertion discipline

This suite's characteristic failure is PASSING. Eight assertions across the effort were found
incapable of failing, against four real defects that tests actually caught. Treat that as the
house style to guard against. The deep source is `.carryover/verified/README.md`, section
"Assertion discipline"; this skill is the working checklist.

## Before writing an assertion

- **Green is not evidence until you know what would have made it red.** Every new assertion
  needs a negative control or a mutation check. An assertion about ORDERING needs a workload
  that could have violated the order.
- **A count is not an outcome.** Ask of every predicate: what value reaching it would turn
  this red? If the honest answer is "nothing the workload can produce", the row is decoration
  no matter how load-bearing its name is.
- **When a predicate reads a shared helper, read the helper.** `fire()` documented its own
  hazard in its docstring and twenty-four rigs walked into it anyway.

## The fire() rule: gate on ENDED, assert on RAN

`fire()` appends a turn that THREW and a turn that FINISHED in the same 3-tuple, so
`len(box)` counts turns that ended, never turns that ran. TESTED: three calls at a dead port
satisfied every completion predicate the suite owned, in 9 ms.

```python
wait_for(lambda: len([b for b in box if b[0].startswith("worker")]) == 3, 300, "worker turns")
workers = rig.completed(box, "worker")      # NOT len(box)
r.check("the workers ran to completion", len(workers) == 3, ...)
```

Waiting on the raw box is correct (a thrown turn releases the gate fast, so the red is
immediate instead of a timeout). Asserting on the raw box is what could not fail. Contract 6
in `probe_rig_contract.py` enforces this from source across every rig.

## Execution is a claim too

- **A green run is not evidence that the run happened.** An assertion that never ran is True
  on exactly the runs that did not evaluate it. `Results(expect=N)` catches both known routes
  (an exception swallowed by `sys.exit` inside a `finally`, and `wait_for` timing out, which
  raises nothing and runs fewer assertions). The floor is a MINIMUM, not an equality:
  adding assertions is safe, removing them is not.
- **Exit on `summary()`'s verdict, last in the `finally`.** Six paid rigs once printed the
  verdict and threw it away; a failing run exited 0.
- **Capture the real exit code.** `python probe.py | tail -4; echo $?` reports tail's status.
  Assign the output first, or use PIPESTATUS / pipestatus.

## Scores and evidence

- **A recorded score is a claim about a file at a moment.** Re-run a rig before quoting its
  number, or say which execution the number came from. Counting `r.check(` sites proves a
  score is arithmetically REACHABLE, never ACHIEVABLE: verify_question.py reconciled
  perfectly at 27 sites against a recorded 27/27 while three assertions had been red for
  seven phases, because the behaviour under test changed and the count did not. Only running
  it shows that.
- **A failing assertion needs the same scrutiny as a passing one.** Before writing down a
  red, ask whether it is an artifact of your own grouping or fixture.
- **A number is not evidence, and repeating it does not make it more evidence.**
- **When a predicate's inputs come from a corpus, the corpus needs a fixture check** as much
  as the predicate needs a mutation check. Losing the evidence and passing the test can be
  the same event (measured: a fresh clone made the retirement bound look 48.2% comfortable
  instead of 1.3%, in green).

## The contract

`probe_rig_contract.py` sweeps every rig entrypoint (itself included; a guard that exempts
itself is the defect it hunts) and asserts the contracts named in its own source. A new rig must
satisfy the contract or the probe goes red. Its negative controls are the actual pre-fix
sources recovered from git history.
