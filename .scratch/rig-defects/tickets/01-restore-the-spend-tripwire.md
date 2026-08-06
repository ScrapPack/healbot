# A bare run_refusal.py can start a paid study from row zero

Type: task
Mode: AFK
Status: open
Assignee: -
Blocked by: -

## Question

`run_refusal.py` with no arguments will start a fresh paid study from row zero, silently, because
the guard that would have caught it depends on a directory that was renamed away.

The mechanism, verified end to end:

1. The run tag defaults to `full` ([run_refusal.py:334](../../../.carryover/verified/run_refusal.py)).
2. `ab.run_dir` builds `{RUNS}/{study}-{tag}` and calls `os.makedirs(..., exist_ok=True)`
   ([ab.py:398-401](../../../.carryover/verified/ab.py)), so a missing run directory is CREATED
   rather than refused.
3. The plan-compatibility check that would catch a mismatched or already-spent run runs only
   `if meta:` ([run_refusal.py:363](../../../.carryover/verified/run_refusal.py)). A freshly created
   empty directory has no meta, so the check is skipped entirely and the `else` branch writes a new
   meta and begins.

The reason this is live now: the `refusal-full` run directory was renamed to
`refusal-full-archived-20260731` during the archive-by-rename repair. That rename was correct and is
recorded. What it also did was remove the only thing standing between a bare invocation and a fresh
paid run, and `run_refusal.py` has not been touched since 2026-07-31.

This was raised as an `error` finding by the review at the time and never acted on. It is the most
urgent of the three defects because its failure mode is spending money, not reporting a wrong number.

## Constraints

- **This ticket is about the guard, not about running anything.** Do not start a study. Do not
  invoke any `verify_*` rig. `/paid-run-protocol` first if that ever seems necessary, which it
  should not.
- Do not rename the archived directory back. The archive-by-rename is recorded and the corpus is
  evidence.
- Whatever guard is added must fail CLOSED: on doubt it refuses and says why, rather than starting.

## The options, none of them decided

- **Refuse an implicit fresh start.** Require an explicit flag to begin a run that has no existing
  meta, so continuing an existing run stays the zero-argument path and starting a new one is a
  deliberate act.
- **Refuse when an archived sibling exists.** If `{study}-{tag}` is absent but a directory matching
  `{study}-{tag}-archived-*` is present, refuse and name it, on the reasoning that the operator
  almost certainly means the archived one.
- **Make `run_dir` not create.** Split creation from resolution so only the deliberate-start path
  calls `makedirs`.

The first is the smallest and the least magical. The second catches the exact shape that happened
here. They are not exclusive.

**Done looks like:** a bare `run_refusal.py` refuses with a message naming the reason and the
remedy, TESTED both ways: refused when no meta exists, and unchanged when resuming a run that has
one. No API credits spent proving either. A probe row is wanted but the tripwire matters more than
the probe, so ship the guard even if the row lands separately.
