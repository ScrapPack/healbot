# The XDG_DATA_HOME assert in arms.py cannot fail

Type: task
Mode: AFK
Status: open
Assignee: -
Blocked by: -

## Question

[arms.py:255](../../../.carryover/verified/arms.py) asserts:

```
assert "XDG_DATA_HOME" not in env or env["XDG_DATA_HOME"] == os.environ.get("XDG_DATA_HOME"), \
    "this function must never introduce XDG_DATA_HOME (auth.json lives there)"
```

Both disjuncts derive from the same source, so the assert cannot fail. `env` is a plain
`dict(os.environ)` copy, and nothing between the copy and the assert sets or pops `XDG_DATA_HOME`.
The keys the function does mutate are `XDG_CONFIG_HOME`, `OPENCODE_DISABLE_EXTERNAL_SKILLS`,
`OPENCODE_DISABLE_CLAUDE_CODE`, `OPENCODE_DB` and `OPENCODE_CLIENT`. None of the five is
`XDG_DATA_HOME`.

Given that: if `XDG_DATA_HOME` is absent from `os.environ` it is absent from `env` and the first
disjunct holds; if it is present it is present with the same value and the second holds.
`git log -S'XDG_DATA_HOME' -- arms.py` returns only the commit that introduced it.

The rule it guards is real and worth guarding. `/paid-run-protocol` states it plainly: never set
`XDG_DATA_HOME`, because `auth.json` lives there and OpenAI is on oauth, so isolate the DB only.
The assert simply cannot notice a violation of it.

This is the class `/rig-assertion-discipline` exists for, and it is roughly the eighth found in this
repo. It was raised as an `error` review finding on 2026-07-31 and never acted on.

## Constraints

- **Invoke `/rig-assertion-discipline` before touching this.** It is the skill written from the
  previous seven.
- Do not delete the assert and call it done. The rule is real; an unguarded real rule is a
  regression, not a cleanup.
- The repair must be TESTED in both directions: red when the rule is violated, green when it is not.
  An assertion that cannot fail is exactly what a green run does not distinguish from a correct one.

## The shape of the repair

The assert needs a reference that is independent of the thing it checks. Capture the value from
`os.environ` BEFORE the copy is built and mutated, then assert the copy against that captured value
rather than against a live re-read of the same source. The mutation test is then trivial: insert an
`env["XDG_DATA_HOME"] = "/tmp/x"` before the assert and confirm it fires.

**Done looks like:** the assert can fail, demonstrated by a deliberate violation that trips it, and
passes on the real path. Recorded wherever this repo records the previous seven.

## Comments

**Repaired and TESTED both directions 2026-08-05 by the overnight AFK loop. No credits spent;
nothing pushed.** `/rig-assertion-discipline` was invoked before the edit, as the Constraints
require.

**The premise needs one correction, and it does not change the repair.** "Both disjuncts derive
from the same source, so the assert cannot fail" is too strong. TESTED against the predicate text
copied verbatim out of `git show HEAD:.carryover/verified/arms.py` at `f173a4e` (a scratch script,
not committed):

| the edit a future session might make | old predicate |
|---|---|
| `env["XDG_DATA_HOME"] = "/tmp/probe-x"` | **fires** |
| the same value written to `os.environ` as well | passes |
| pops an inherited `XDG_DATA_HOME` off the child env | passes |

So it was falsifiable against the one route the ticket proposed as the mutation test, and blind to
the other two — including the worse one, since a write that goes through `os.environ` moves the
data root for this process too, not only the child. The conclusion the ticket draws is unchanged
and the repair it prescribes is the right one: the guard needs a reference the checked dict cannot
supply.

**What was built.** The env construction moved out of `serve()` into `_serve_env(live, db)`
([arms.py:239](../../../.carryover/verified/arms.py)), which captures the inherited value before
the copy ([:252](../../../.carryover/verified/arms.py)) and compares the finished env against that
capture ([:261-266](../../../.carryover/verified/arms.py)). `serve()` now calls it
([:277](../../../.carryover/verified/arms.py)) and is otherwise untouched; `run_study.py:792` is
the only other caller and the signature did not move. Two decisions the ticket does not name:

- **A `RuntimeError`, not an `assert`.** `python -O` strips asserts, and this guard stands between
  a paid run and the OAuth credentials in `auth.json`. It also matches how the rest of this file
  refuses.
- **Extracted rather than fixed in place.** The guard's failure mode is a future edit, so its
  control has to be a future edit. A function that takes two strings can be driven from a probe
  and from a mutated copy of the file; the old inline form could only be reached by booting a
  server behind `fixtures()` and `materialize()`.

**TESTED, all free.**

- `probe_arm_factory.py` at 23/23, exit 0 ([:33](../../../.carryover/verified/probe_arm_factory.py)
  carries the floor, moved 19 to 23). Baseline before the change was 19/19 exit 0 on the same
  machine. The four new rows are at
  [:177-211](../../../.carryover/verified/probe_arm_factory.py): env-unset passes, an inherited
  value passes through untouched (red if a later edit pops it, which the old form allowed), and two
  refusals driven by `mutant_arms` ([:66](../../../.carryover/verified/probe_arm_factory.py)),
  which recompiles `arms.py` with one line inserted. The second of those two is the
  `os.environ` route from the table above. `mutant_arms` raises if its anchor does not match
  exactly once, so a rotted anchor is a red row rather than a vacuous green.
- `gate/gate.py` exit 0 over the change, `rig-contract` 40/40 among it.

**What was NOT done, and is not this ticket.** `ab.serve_arm` builds the same shape of env
([ab.py:113-121](../../../.carryover/verified/ab.py)) and has **no guard at all** — the rule lives
only in its docstring. It is also a harder case than this one, because the harness arm's isolation
is applied by a shell prelude sourced inside the child rather than by the dict Python builds, so a
Python-level guard would not see a `XDG_DATA_HOME` exported by `env.sh`. Worth a ticket; not worth
folding into this one silently.

**Left for a human.** `.scratch/daily-driver/research/16-review-bar-calibration.md` cites this
defect at line 255 of `arms.py` twice (its lines 118 and 276). Line 255 is now the leak-strip
`env.pop(leak, None)` inside `_serve_env`. That file is under a standing instruction not to edit,
so the rot is recorded here rather than repaired. The Question section above is pre-change and was deliberately
left as the record of what was found.
