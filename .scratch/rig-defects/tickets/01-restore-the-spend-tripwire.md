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

## Comments

**Guard built and TESTED 2026-08-05 by the overnight AFK loop. No credits spent; nothing pushed.**

Option one of the three was implemented, which is the one this ticket calls the smallest and the
least magical: an explicit `--start-new` is now required to begin a run that has no `meta.json`
([run_refusal.py:350](../../../.carryover/verified/run_refusal.py) declares it,
[:383-384](../../../.carryover/verified/run_refusal.py) refuses without it). Two details that were
not in the option as written and that the ticket's own constraints force:

- The refusal lands BEFORE `ab.run_dir` is called, so a refused invocation creates nothing. Resolving
  through `ab.run_dir` first would leave the empty directory that this defect is made of, and the
  second invocation would then be resuming it.
- Option two's evidence is folded into the message rather than into a second refusal: any
  `<dir>-archived-*` sibling is named ([:315-322](../../../.carryover/verified/run_refusal.py)),
  which is what points an operator at `refusal-full-archived-20260731`. Option two as a separate
  refusal, and option three (splitting creation from resolution in `ab.run_dir`), were NOT done.

TESTED, all free, both directions:

- `probe_refusal_driver.py` carries six new rows and its floor moved 24 to 30; it exits 0 at 30/30.
  Every row runs `main()` with `ab.run_dir` poisoned, so the paid path cannot be reached even if the
  guard fails: a guard that stops firing turns the refusal rows red instead of spending. Two of the
  six are negative controls — `--start-new` gets past the guard, and a tag whose `meta.json` exists
  is handed to the resume path untouched — so the refusals cannot be green for an unrelated reason.
- `gate/gate.py` exits 0 over the change.

**What the captain should know before the next paid run.** Editing this file moves
`driver_sha256`, which `compatible_meta` checks
([:391-397](../../../.carryover/verified/run_refusal.py)). MEASURED: that orphans no resumable run,
because the live `ab.py` hash already matched neither run's recorded `scorer_sha256`
(`refusal-full-archived-20260731` records `7517efb9…`, `refusal-pilot-v2` records `3723984e…`,
live is `9de89aa1…`), so both were already refusing to resume before this change. `--rescore` is
unaffected either way: it allows drift in all three hashes. `run_study.py`'s "why a second driver"
docstring said this file does not move and now says it moved once, and why.

**Left for a human.** `.scratch/daily-driver/research/16-review-bar-calibration.md` line 285 cites
`run_refusal.py:334` and `363-369` for this defect; the tag default is now at line 361 and the
`if meta:` check at 393. That file is under a standing instruction not to edit, so the rot is
recorded here rather than repaired. The Question section above is also pre-change and was left
as the record of what the defect looked like. Same shape, unguarded, in two other drivers:
`run_study.py:689` and `verify_refusal_b.py:135` both resolve through `ab.run_dir`, which creates.
Whether they get the same tripwire is a separate ticket, not this one.
