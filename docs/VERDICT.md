# Phase 10 — six rigs printed the verdict and threw it away

Date 2026-07-28. Nothing was built in the fork and nothing was paid for. Phase 9 fixed the
false-green defect in the ten **free** probes and did not touch the eleven **paid** rigs. This
phase looked at the half that costs money.

The defect was worse there, and older. Phase 9's probes at least honoured `summary()`'s return
value; **six of the paid rigs did not read it at all.**

| | |
|---|---|
| **Six rigs exited 0 on a failing run** | `finally: r.summary(); t.close()` — verdict discarded, no `sys.exit`. `verify_handoff`, `verify_permission`, `verify_question`, `verify_retire`, `verify_surface`, `smoke`; three had no `sys.exit` anywhere in the file. **Scope, measured:** this bites when assertions fail *without* an exception. A crash still exited 1, because the exception propagated through the `finally` — there was no `sys.exit` there to discard it. §1 |
| **`smoke.py` is one of them** | The README tells you to run it FIRST to confirm the provider resolves. It returns success when the provider is broken. §1 |
| **`verify_surface.py` carried a permanently-red assertion for five phases** | Recorded 17/18. `not t.find("blocked")` is False whenever the grid is open, because the footer says `tab next blocked`. Nothing ever surfaced it, because the rig exited 0. §1, §4 |
| **`verify_handoff.py`'s recorded 21/21 is unreachable** | It has **22** unconditional assertions. Phase 5 swapped a vacuous check for two mutation legs and never re-ran it. The 21/21 is Phase **4**'s score, and four documents cite it as the evidence that the Phase 4 exit gate is met. §2 |
| **Phase 8's "the one rig in the suite" was two rigs** | `docs/GROWTH.md:176` claims `verify_control_agent.py` was *the* rig whose recorded score did not match the file as it stood. `verify_handoff.py` had the same property at the same time. §2 |
| **New guard: `probe_rig_contract.py`, free, 22/22** | Asserts the contract from source across all 23 rigs (itself included — a guard that exempts itself is the defect it hunts), so none of this can grow back. Free suite **142 → 164**. §3 |

---

## 1. The verdict was computed, printed, and dropped

`Results.summary()` returns a boolean. Six rigs called it as a statement:

```py
finally:
    r.summary()
    t.close()
```

No `sys.exit`. The process falls off the end and the shell sees **0**, however many assertions
failed. VERIFIED by reading all twelve paid entrypoints; three of them (`verify_retire.py`,
`verify_surface.py`, `smoke.py`) had no `sys.exit` or `SystemExit` anywhere in the file at all.

**The scope is narrower than "these rigs could not fail", and the narrower claim is the one to
carry.** TESTED with a two-line A/B on the shipped `Results`: the old shape, given one failing
assertion and no exception, prints `1/2 passed` and exits **0**; the new shape, same assertions,
exits **1**. But a rig that *crashes* always exited 1 even before this phase — with no `sys.exit`
in the `finally`, the exception simply propagates and Python sets the status itself. So the defect
is exactly: **a clean failing assertion is invisible to the shell.** That is not a lesser bug here,
because it is precisely the state `verify_surface.py` sat in for five phases (17/18, no exception)
and precisely what a wrong model pin does to `smoke.py` — `:27`, `:45` and `:50` are plain
assertions that go false without raising.

This also means the four rigs that *did* exit on their verdict but had **no crash guard**
(`verify_auto_retire`, `verify_cold_question`, `verify_control_agent`, `verify_headless_retire`)
carried the *other* defect — Phase 9's — where a crash exits on a partial green. Two different
faults, six rigs and four rigs, one fix each, and the two must ship together.

Two of the six are worth naming individually.

**`smoke.py`** is the first thing `.carryover/verified/README.md` tells you to run — *"provider/model
config sanity — run this first"*. Its whole job is to fail early and cheaply when the model pin
does not resolve, so you do not discover it forty minutes into a paid rig. It could not fail.

**`verify_surface.py`** is the proof that this was not theoretical. It is recorded as **17/18** —
the suite's one acknowledged failing assertion, documented in the README as a test bug. A rig with
a known-red assertion, returning success, for five phases. The exit code is precisely the channel
that would have surfaced it, and it was disconnected.

### Why Phase 9 did not catch it

Phase 9's evidence was a fresh clone, and a fresh clone cannot run a paid rig — it has no
`hb/*.db`, no `opencode/` checkout, and running one costs money. So the paid half was never
executed, never crashed, and never had the chance to report a false green in front of anybody. The
defect was only ever visible **in the source**, which is why the guard this phase adds reads source
rather than running anything.

### The fix, and what tier it is

All twelve now carry the three-part contract Phase 9 established for the probes:

- `Results(expect=N)` — an assertion floor
- an `except` handler that turns a crash into a FAILED row
- `sys.exit(0 if ok else 1)` — the exit status depends on the verdict

**The guard and the exit line must ship together**, and that is not a stylistic point: adding
`sys.exit()` to a `finally` *without* the guard creates the Phase 9 defect, because `sys.exit()`
inside a `finally` discards the in-flight exception. Six rigs got both; four more got the guard
they were missing.

**These fixes are VERIFIED, and three of them are now TESTED.** They are read-and-reasoned changes
to files this phase cannot execute in a working environment without spending — but they *can* be
executed in one where they fail fast. A fresh clone has no `opencode/` checkout, so a paid rig dies
before it ever reaches a model call, and running one there costs nothing. TESTED that way on
`smoke.py`, `verify_surface.py` and `verify_handoff.py`: each loads, the guard converts the crash
into a FAILED row, the floor reports `SHORT RUN — only 2 of 6 / 18 / 22 assertions ran`, and each
exits **1**. `verify_handoff.py` printing `expected at least 22` is also independent confirmation
that the floor derived from the AST is the one the file now declares.

What remains genuinely unbought is whether each rig, in a *working* environment, runs all the way
to its floor. That needs the model. What *is* TESTED is the mechanism — `Results`'s floor semantics
are driven directly in `probe_rig_contract.py` (§3), and the identical change was controlled in both
directions on the free probes in Phase 9. What remains unproven is that each paid rig still runs to
its floor. The floors are set conservatively for exactly that reason: each is the count of
assertions that are **unconditional** in the AST, so a rig whose conditional legs do not fire still
clears its floor. `verify_permission.py` is the widest gap — floor 35 against a recorded 40/40 —
and that slack is deliberate. A floor that false-fails a good run is worse than no floor, because
it teaches the reader to ignore the one signal it exists to send.

---

## 2. A recorded score that no execution of the file has produced

`verify_handoff.py` is the rig behind the second clause of the Phase 4 exit gate — *"one driven
past the threshold and handed off with continuity intact"*. It is cited as **21/21** in
`HARNESS.md`, `docs/VERIFY.md` §10 and its own table, and `.carryover/verified/README.md`.

It has **22** assertions, all unconditional, none inside the guard. TESTED by AST walk; a complete
run cannot produce 21.

The history, from git:

| commit | phase | `r.check` sites |
|---|---|---|
| `cdd1096` "phase 4 EXIT GATE MET" | 4 | **21** ← the score was recorded here |
| `823d7a2` "phase 5: harden the grid…" | 5 | **22** |
| now | — | **22** |

Phase 5 removed one check and added two. `docs/HARDEN.md:30` records the removal in its own audit
table — *"started at its OWN occupancy | `r.check(..., True, "see figure below")` | **A literal
constant.** The headline 21/21 is 20 substantive + 1 label"* — so Phase 5 knew it was changing the
assertion set, replaced a vacuous check with two real mutation legs, and left `21/21` standing in
four documents as the evidence for an exit gate.

**Nothing re-ran it.** The 21/21 is a true record of a Phase 4 execution of a Phase 4 file, cited
ever since as though it described the current one.

### The claim this disproves

`docs/GROWTH.md:176` opens Phase 8 §2 with:

> *"`verify_control_agent.py` was **the one rig in the suite** whose recorded score did not
> correspond to an execution of the file as it stood — its single failing assertion had been
> rewritten **twice** without a run."*

The finding about `verify_control_agent.py` was correct and its consequences stand. The
**uniqueness** was not checked, and it is false: `verify_handoff.py` had the identical property at
the identical time, and had had it two phases longer. It is the same failure the same document
names one section later — *a claim that sounded verified and had only been reasoned* — applied to
the sentence that introduces the finding.

Cheap to check, too: counting `r.check(` per file and comparing against the recorded scores is one
command, and it reconciles every other rig in the suite. `verify_cold.py` (22 sites, 21 recorded)
and `verify_retire_350k.py` (26 sites, 25 recorded) both differ by exactly their guard's own
`r.check("UNEXPECTED EXCEPTION", …)`, which fires only on a crash. `verify_control_agent.py` (16
sites, 15 recorded) differs by one conditional. Only `verify_handoff.py` has no such account.

**`verify_handoff.py` needs to be re-run before its number can be quoted again.** It is paid, it is
not urgent, and the honest position until then is that the Phase 4 exit gate's second clause rests
on a score from a file that has since changed. That is now what the artifacts say.

---

## 3. `probe_rig_contract.py` — the guard that makes this unrepeatable

Free, **22/22**, and it executes no rig. It parses all 23 entrypoints (itself included) and asserts the four
properties above from source:

1. every rig declares `Results(expect=N)`, and `N >= 1`
2. every statically boundable floor is satisfiable
3. no rig has a `finally` that exits without a handler recording the crash
4. every rig's exit status depends on `summary()`

Plus five **runtime** checks that drive `Results` directly — a full pass returns True, a short run
returns False *with zero failures*, a failing row returns False, `expect=None` keeps the legacy
behaviour, and the floor is a minimum rather than an equality. The source contract and the
behaviour it is chosen to produce are asserted in the same file, which is what stops the two
drifting.

Every predicate has a mutation check, and each corrupts a copy of a **real** rig and pushes it
through the same function the live sweep calls — this suite's rule that a mutation check
re-implementing its predicate inline proves only that the inline copy discriminates. There is also
an **inverted** leg: a module with no `try` block must **not** be reported as swallowing, because
`probe_twin.py` is that shape and an absence predicate that fires on everything is as useless as
one that fires on nothing.

### Two things it caught immediately, both mine

Worth recording, because they are the argument for the probe existing rather than for trusting the
sweep that produced this phase's findings.

- **A false negative in its own first predicate.** `floor_of` matched only `Results(...)` and not
  `rig.Results(...)`, so it reported five probes as floorless that were not. A sweep that
  under-reports is the same defect as a vacuous assertion with the polarity reversed, and it would
  have sent the next reader to "fix" five correct files.
- **A scripted patch of mine that destroyed `verify_retire.py`.** The regex that inserted
  `import sys` spliced from the first top-level `import` to the last — and that file has an
  `import os` at `:63`, mid-body, so 32 lines including its `Results()` construction were replaced.
  The contract probe surfaced it as a missing floor within a minute. `git checkout` restored it and
  it was redone by hand; the other five files were diffed line-by-line and lost nothing. The
  general point is the specific one this phase is about: **the check that catches you is the one
  that reads the artifact rather than the intent.**

### What the review pass added

Reviewing Phase 9 and 10 before moving on produced two corrections to this document and one to the
probe, all of them the same species as the findings above.

- **This document said the six rigs "always exited 0", and that over-claims.** TESTED with a
  two-line A/B on the shipped `Results`: the old shape with one failing assertion and no exception
  prints `1/2 passed` and exits **0**; the new shape exits **1**. But a rig that *crashes* always
  exited 1 even before Phase 10 — with no `sys.exit` in the `finally` there was nothing to discard
  the exception. The defect is exactly *a clean failing assertion is invisible to the shell*, which
  is the state `verify_surface.py` sat in for five phases and what a wrong model pin does to
  `smoke.py`. Narrower than first written, and unchanged in consequence.
- **A fifth contract property, because the fourth was weaker than it read.** `acts_on_verdict` asks
  only whether a verdict-bearing exit exists *anywhere* in the file — a stray or unreachable one
  satisfies it. That all twenty rigs actually *end* their `finally` on that exit was verified by
  hand during the review, and being verified by hand is precisely what should not stay that way.
  `finally_ends_on_verdict` now asserts it, with a mutation check that appends `t.close()` after the
  exit and requires the probe to trip. **22/22.**
- **Mechanical audit of the scripted patch.** Every line removed across all twelve paid rigs was
  diffed: only the intended `r = Results()`, `r.summary()` and the one `verify_surface` assertion.
  Every handler chain is the uniform `SystemExit->raise | Exception->traceback`, and every `finally`
  ends on `sys.exit(0 if ok else 1)`.

A first version of predicate 3 demanded a guard unconditionally and flagged `probe_twin.py`, which
has no `try` at all and is therefore safe — an exception simply propagates. Satisfying that check
would have meant reindenting 190 lines to fix nothing. The predicate now states the defect exactly:
the danger is the **combination** of a `finally` that exits and no handler recording the crash.

Predicate 2 carries a visible exclusion rather than a quiet widening. Three rigs emit assertions
from inside a loop — `probe_turn_predicate.py` drives an 11-case table through a single call site —
so no static upper bound exists for them. The check reports `[NOT EXERCISED for 3 rig(s) …]` and
names them, instead of relaxing until everything passes.

---

## 4. The five-phase-old test bug, fixed

With the exit-code fix in place, `verify_surface.py`'s recorded 17/18 stops being a footnote and
becomes a hard failure, so it had to be dealt with rather than inherited.

The assertion was `not t.find("blocked")` under the label *"nothing is blocked yet"*. `find()` is
case-insensitive substring, and the grid's footer reads
`a answer · x retire · tab next blocked · enter focus · …` (`healbot.tsx:997`) — so the substring is
on screen whenever the grid is open and the predicate was False by construction.

The header is the thing that counts blocks, and VERIFIED at source it is wrapped in
`<Show when={blocked() > 0}>` (`healbot.tsx:963`) — so `\d+ blocked` is on screen exactly when
something is blocked and absent otherwise. That is the shape `search()` exists for, and `1 blocked`
/ `2 blocked` / `3 blocked` are what the rig's own later legs assert. The cell-label half moved from
`find` to `exact`, which is strictly narrower and so cannot turn a passing leg red.

**VERIFIED and statically controlled, not TESTED.** The regex was checked in both directions —
it matches `Healbot  4 sessions  3 blocked` and does not match the footer alone — but the rig is
paid and was not run. Its floor is 18, so if the fix is right it reports 18/18, and if it is wrong
it now says so instead of exiting 0.

---

## 5. Still open after Phase 10

- **`verify_handoff.py` must be re-run before 21/21 can be quoted.** New, and the only new item.
  It is the same spend as any single paid rig. Until then the Phase 4 exit gate's second clause is
  cited from a superseded file, which the artifacts now state.
- **Every paid-rig fix in this phase is VERIFIED, not TESTED.** The next paid run of any rig is also
  the first execution of its floor. They are set conservatively so this should be uneventful.
- **The 180,000 gate has never been fired at its real value.** ~$2.60. Offered and declined in
  Phase 8, unchanged.
- **An external plugin's route has never been rendered.** VERIFIED at source in Phase 8 §4.
- **Phase 3's exit gate** — `/code-review ultra` on the `harness/` diff. User-triggered and billed.

Decided in Phase 8 and not re-opened: `RETIRE_AT` stays at 180,000; no startup sweep.

---

## 6. The method note

Phase 9's lesson was *a green run is not evidence that the run happened*. Phase 10 is the same
sentence with one word changed:

**A green run is not evidence when there was no run at all.**

Every finding here lived in source that had been read many times, in files whose recorded scores
were quoted across four documents as evidence. None of it was reachable by running anything,
because the rigs that held it are the rigs nobody runs — they cost money, so they are executed once,
their score is written down, and the number outlives the file. `verify_handoff.py` went two phases
past an edit that changed its assertion count. `verify_surface.py` went five phases with an
assertion that could not pass.

The generalisable form, and it is the one this project keeps rediscovering at a higher level each
time: **a recorded number is a claim about a file at a moment, and nothing in this repo tied the two
together.** Phase 8 found one instance and called it unique. That uniqueness claim was itself an
unverified assertion, sitting in the sentence that introduced the finding — and checking it was one
`grep -c` away.

So the fix is not another correction. It is `probe_rig_contract.py`: the first check in this suite
that asserts a property of **every** rig rather than of one, and the first that reads the rigs as
artifacts instead of trusting what they printed the last time somebody paid to run them.
