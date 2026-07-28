# Phase 9 — the suite could not tell "everything passed" from "almost nothing ran"

Date 2026-07-28. Nothing was built in the fork and nothing was paid for. The phase did the one
free thing `NEXT.md` put at the top — re-run the ten probes, then run them from a **fresh clone**,
which had never been done — and the fresh clone broke the suite open.

The headline is not that the suite fails on a fresh clone. It is that **three of the ten probes
reported success on a fresh clone while having proven nothing**, and that the probe Phase 8 built
to stop a number resting on one unverified measurement **reports a safer gate as its own evidence
disappears**.

| | |
|---|---|
| **Three probes exited 0 having run a fraction of their assertions** | `probe_on_grid` `2/2`, `probe_control_wiring` `7/7`, `probe_headless_arm` `1/1` *after printing a 90-second timeout*. All exit 0. `Results.summary()` returns `not failed` over whatever happened to be appended, and has no idea what should have been. §1 |
| **`probe_turn_growth`'s two load-bearing assertions get EASIER as the evidence vanishes** | On a fresh clone it reports the gate clearing its ceiling by **173,357 tokens (48.2%)** instead of 4,852 (1.3%), and prints the bound as **353,357** instead of 184,852 — **in green**, while its own detail string still quotes 175,148. §2 |
| **The real corpus is REQUIRED, and this probe's docstring and `NEXT.md` both said optional** | TESTED by running with it absent: **exit 1, 12/14**. The `[NOT EXERCISED: …]` string is the detail on a *failing* row. §3 |
| **The corpus moved 86 → 94 turns, and the cause is the suite writing to the corpus it measures** | `hb/control.db`, written by `verify_control_agent.py` six minutes after Phase 8 recorded its figures. Every load-bearing number is unchanged — which is the first evidence the derivation is stable under corpus growth. §4 |
| **Free suite: 141/141 → 142/142** | One assertion added. Both gates clean. §5 |

---

## 1. A probe that crashes reports the assertions it got through, and exits 0

`rig.py`'s own comment, written in Phase 5, says the fresh-clone problem was solved:

> *"Previously every `verify_*.py` hardcoded an absolute scratchpad path belonging to the session
> that wrote it; those directories are gone, so the suite could not be re-run from a fresh clone —
> which for a project whose only mechanism for proving anything is this rig is a defect in the
> evidence, not just an inconvenience."* (`rig.py:27-30`)

**That fixed the paths. It did not make the suite runnable from a fresh clone, and nobody checked.**
Same shape as Phase 8's `verify_control_agent.py` finding: a comment asserting a property that had
never been executed against.

TESTED — `git clone` this repo into a scratch directory, `python3 -m venv venv && pip install pyte`
exactly as `.carryover/verified/README.md` says, and run the ten free probes:

| probe | real repo | fresh clone, BEFORE | exit |
|---|---|---|---|
| `probe_on_grid` | 4/4 | **2/2** | **0** |
| `probe_error_state` | 10/10 | clean diagnostic | 1 |
| `probe_focus` | 24/24 | clean diagnostic | 1 |
| `probe_fleet` | 10/10 | 5/7 | 1 |
| `probe_control_wiring` | 14/14 | **7/7** | **0** |
| `probe_twin` | 23/23 | raw `FileNotFoundError` | 1 |
| `probe_headless_arm` | 14/14 | **1/1**, after `!! timed out … after 90s` | **0** |
| `probe_request_channel` | 9/9 | 0/1 | 1 |
| `probe_turn_predicate` | 18/18 | **18/18** | 0 |
| `probe_turn_growth` | 15/15 | 13/15 | 1 |

The cause is one line: `opencode/` is the derived checkout and is **gitignored**, so `OC`'s
`bun run --cwd {REPO}/packages/opencode` dies with
`ENOENT: Could not change directory to …/freshclone/opencode/packages/opencode` and no server ever
starts. Every screen is then blank or an error message.

### The two escape routes, and why the fix is in `Results` rather than in a guard

**(a) `sys.exit()` inside a `finally` DISCARDS the in-flight exception.** Nine probes carry the
identical shape:

```py
finally:
    ok = r.summary()
    sys.exit(0 if ok else 1)
```

so a probe that raises on line 28 still exits on `summary()`'s verdict over the rows it appended
before raising. `probe_on_grid` is the clean demonstration: on the fresh clone its **first**
assertion (`on_grid is FALSE on the home screen`) passes **vacuously** — nothing is on screen —
and its **second** (`the OLD predicate t.find("Healbot") is TRUE`) passes because the ENOENT path
printed to the dead terminal contains the string. That is the substring collision the probe exists
to expose, satisfied here by an error message. Then `t.send()` raises into the dead terminal, the
`finally` swallows it, and the summary reads `2/2 passed`.

**This was already known and never propagated.** `probe_request_channel.py:151-153` says it
outright — *"Failures must look like failures. `sys.exit()` in a `finally` swallows an escaping
exception and the rig reports a green summary of whatever happened to run first — see
`verify_cold.py`, where this guard was written."* It was written in Phase 5, restated in Phase 7,
and present in exactly **3 of 10** probes. The seven without it were the seven older ones.

**(b) A timeout raises nothing at all.** `wait_for()` (`rig.py:259-270`) prints
`!! timed out waiting for …` and returns `None`. No exception, so guard (a) would not have caught
it either — the probe simply runs fewer assertions. This is `probe_headless_arm` reporting
`1/1 passed` and exit 0 after ninety seconds of waiting for a server that could never start.

Two different mechanisms, one symptom, so the fix goes where the symptom is: **`Results` now takes
an assertion floor.**

```py
r = Results(expect=14)          # a MINIMUM, not an equality
```

`summary()` returns `not failed and not short`. Adding an assertion must not turn a probe red;
losing one must. `rig.py`'s docstring carries the measurement that motivated it.

### Both controls run

- **Positive** — the real repo: **142/142, every probe exit 0**, no `SHORT RUN`. The floor does not
  fire where it should not.
- **Negative** — the same fresh clone, after the fix: **9 of 10 exit 1**, with `SHORT RUN` on the
  four that stop early and `UNEXPECTED EXCEPTION` rows where they crash.

| probe | fresh clone, BEFORE | fresh clone, AFTER |
|---|---|---|
| `probe_on_grid` | **2/2, exit 0** | 2/3 `SHORT RUN`, exit 1 |
| `probe_control_wiring` | **7/7, exit 0** | 7/8 `SHORT RUN`, exit 1 |
| `probe_headless_arm` | **1/1, exit 0** | 1/2 `SHORT RUN`, exit 1 |
| `probe_request_channel` | 0/1, exit 1 | 0/1 `SHORT RUN`, exit 1 |
| `probe_twin` | raw traceback | named diagnostic, exit 1 |
| `probe_turn_growth` | 13/15, exit 1 | 13/16, exit 1, **new fixture check red** |
| `probe_turn_predicate` | 18/18, exit 0 | **18/18, exit 0** |

`probe_turn_predicate` is the one probe that genuinely survives a fresh clone, and it is worth
saying why: it depends only on **tracked** repo files — `harness/config/opencode/plugin/healbot.ts`
— plus `node`. It needs no server, no checkout and no inherited database. That is the portability
bar, and one probe out of ten clears it.

---

## 2. The assertion that gets easier as its evidence disappears

This is the more serious finding, because it does not need a fresh clone to be dangerous — it needs
only that somebody, someday, runs `probe_turn_growth.py` without the rig corpus and believes it.

The two load-bearing assertions in the file are:

```py
retire_at + worst_sol < CEILING          # "on the PINNED model the shipped gate survives"
retire_at < CEILING - worst_sol          # "the gate's own ceiling is 184,852"
```

**Both get easier as `worst_sol` gets smaller, and nothing put a floor under `worst_sol`.**

`worst_turn = 175,148` — the number `docs/GROWTH.md` §1, `HARNESS.md` and `docs/RELAY.md` §5 all
derive the 184,852 bound from — exists **only** in `hb/*.db`, which `.gitignore:13` excludes. A
fresh clone has no rig corpus at all, so the pinned-model population collapses to the real corpus's
short `gpt-5.6-sol` sessions, whose worst turn is **6,643**.

MEASURED, on the fresh clone, before the fix:

```
     worst turn on the PINNED gpt-5.6-sol: 180,000 + 6,643 = 186,643   OK   (n=15, margin 173,357 = 48.2%)
     RETIRE_AT implied by each:  < 136,742 (any turn) / < 353,357 (pinned model) / < 289,296 (near-gate)
  [PASS] on the PINNED model the shipped gate survives — but by 173,357 tokens, 48.2% of the ceiling
  [PASS] the gate's own ceiling is 353,357, not the ~190,000 on record — the shipped 180,000 clears it by 173,357
```

Read the second line against its own detail string, which is unchanged and still reads *"The
measured worst turn on the pinned model is 175,148, so the true bound is lower than every document
says."* **The assertion contradicts its own detail text, reports a bound 168,505 tokens higher than
every document says, and passes.** The summary read 13/15 — and the two reds are the *rig corpus*
rows, which look exactly like the known "the optional corpus is missing" condition. A reader would
have to notice that a 48.2% margin had replaced a 1.3% one to catch it.

That is this project's characteristic failure — **passing** — sitting in the single most
load-bearing assertion in the suite, in the probe written specifically to stop a number from
resting on evidence nobody had checked.

**Fix: a fixture check on the pinned-model population**, the direct analogue of the existing
677/56/733 fixture check on the real corpus:

```py
r.check(
    f"fixture check: the pinned-model worst turn is the one on record — {worst_sol:,.0f} >= 175,148",
    worst_sol >= 175_148, …)
```

`>=` is deliberate and the direction is the whole point. A **larger** worst turn is new evidence and
must not fail here — it correctly tightens the two assertions below instead, which is the change-rule
`docs/RELAY.md` §5 already states. This catches only the corpus going *missing*, which is the
direction nothing else guarded. TESTED red on the fresh clone (`6,643 >= 175,148` FAIL) and green on
the real repo.

---

## 3. "Optional" was wrong, and the failure it hides is not the obvious one

`probe_turn_growth.py`'s docstring said:

> *"It is optional; if absent, this prints NOT EXERCISED rather than passing quietly."*

`NEXT.md` inherited the claim verbatim, and flagged that nobody had tested it. TESTED — run with
`HOME` pointed at an empty directory so `os.path.expanduser` resolves to nothing:

**Exit 1. 12/14.** The check is `r.check(…, have_real, …)`, so absence is a **FAIL**; the
`[NOT EXERCISED: …]` text is the *detail string on a failing row*, not a pass. And a second
assertion goes red with it — *"…and that risk is REAL, not hypothetical — **0** turn(s) off the
pinned model exceed the pinned model's worst case"* — because the 223,258-token `gpt-5.6-terra`
turn that makes `RETIRE_AT` model-specific lives in that file too.

So the corpus dependencies are **both required and required for opposite reasons**, which is now
written into the docstring:

- **without the real corpus** the probe goes loudly red, and loses the evidence for Phase 8's
  model-specificity constraint;
- **without the rig corpus** it goes quietly *greener*, per §2.

The second is the dangerous one, and it is the one that had no guard.

---

## 4. The corpus moved, 86 → 94, and the suite is what moved it

`NEXT.md` said: *"probe_turn_growth.py is new; if its corpus figures have moved, something changed
under it and that is itself the finding."* They moved.

| | Phase 8 | Phase 9 |
|---|---|---|
| completed turns | 86 | **94** |
| rig corpus | 228 msgs | **280** |
| real corpus | 822 msgs | 822 |
| unterminated / negative | 21 / 3 | 21 / 3 |

TESTED, by removing one file and re-running: **the entire delta is `hb/control.db`.** With it
hidden the probe reports **82** turns and reproduces Phase 8's percentiles *exactly* — ALL p90
136,640, rig p90 90,089, rig p95 96,700, rig p75 22,152. It holds 12 turn-producing sessions; 4 of
them were present when Phase 8 measured, 8 were not (82 + 4 = 86, 82 + 12 = 94).

The cause is mundane and the consequence is not: `hb/control.db` has mtime **19:50** on 2026-07-27,
`probe_turn_growth.py` has mtime **19:44**. Phase 8 recorded its figures and *then* ran
`verify_control_agent.py` twice (§2 of `docs/GROWTH.md`), which wrote eight more sessions into the
corpus the probe measures.

**The suite writes to the corpus it measures.** `probe_turn_growth.py` globs `hb/*.db`, and every
paid rig run writes there. Its percentiles are therefore a function of how many paid rigs have been
run since — a snapshot, not a constant. The recorded figures in `docs/GROWTH.md` should be read that
way, and a future phase seeing them drift must not read that as a signal about the model.

**What did NOT move is the finding.** Across +12 turns (+14%), all on the pinned model:

| | Phase 8 | Phase 9 |
|---|---|---|
| worst turn, pinned model | 175,148 | **175,148** |
| bound on `RETIRE_AT` | 184,852 | **184,852** |
| margin | 4,852 (1.3%) | **4,852 (1.3%)** |
| worst turn anywhere | 223,258 | **223,258** |
| negative control, per-step | 141,412 | **141,412** |
| max, start ≥ 50K / 100K / 150K | 70,704 / 70,704 / 32,673 | **identical, same n** |

This is the first evidence that the derivation is **stable under corpus growth**, and Phase 8 could
not have had it — it had one corpus and no way to tell a robust maximum from an artifact of the
particular sessions on disk. Twelve new turns moved three percentiles by a few hundred tokens and
moved no maximum, no bound and no conditional. That is a genuinely better position than a re-run
that merely reproduced the same digits, and it was free.

---

## 5. Two smaller things, both worth knowing

**`probe_error_state` and `probe_focus` are "free" only if you inherited a paid database.** Both are
listed in `README.md` under *"free — no model turns, no API credits"*. On a fresh clone both exit 1
with `hb/retire350.db not found — run verify_retire_350k.py first` — and `verify_retire_350k.py` is
the ~5M-token full-scale run. The diagnostic is honest and actionable, which is why this is a
documentation correction and not a defect: the probes are free **to re-run**, not free **to run for
the first time**. `README.md` now says so.

**`probe_twin` died with a raw `FileNotFoundError`** from a module-level call, because it reads the
gitignored checkout. Exit code was already 1, so this was never in the false-green class; it now
prints the cause and points at `fork/README.md`.

---

## 6. Still open after Phase 9

Unchanged and still unbought — neither was touched, and no API credits were spent this phase:

- **The 180,000 gate has never been fired at its real value.** ~$2.60, `~6-11` min. Offered and
  declined in Phase 8 on the grounds that a `>=` against a variable is threshold-independent by
  inspection. Still the cheapest paid item.
- **An external plugin's route has never been rendered.** VERIFIED at source in Phase 8 §4;
  *does it, under a real workload* is unbought.
- **Phase 3's exit gate** — `/code-review ultra` on the `harness/` diff. User-triggered and billed.

Decided in Phase 8 and **not** re-opened here: `RETIRE_AT` stays at 180,000, and there is no startup
sweep. §4 strengthens the first — the margin it accepts is now measured against a 14%-larger corpus
and is unchanged.

New, and small: **the suite is not portable, and one probe out of ten is.** Rebuilding `opencode/`
from `fork/README.md` is a documented step, and `hb/*.db` can only be rebuilt by paying for the rigs
that wrote it. That is a fact about the evidence, not a task — but it is now written down instead of
being discovered by the next person who clones the repo and gets three green exit codes.

---

## 7. The method note

Phase 7's characteristic failure was *claims that sounded verified and had only been reasoned*.
Phase 8's was *a number is not evidence, and repeating it does not make it more evidence*. Phase 9's
is one level under both:

**A green run is not evidence that anything ran.**

Every assertion-discipline rule in `README.md` is about whether a predicate can distinguish true from
false. Not one of them was about whether the predicate **executed**. So the suite grew ten probes,
each carefully built with negative controls and mutation checks, sitting on a summary function that
could not tell 2 assertions from 24 — and the first time anything ran it in an environment it had not
been developed in, three probes said `passed` and exited 0.

The sharper form, because it is what makes it survive review: **the vacuous pass and the missing
assertion are the same defect wearing different clothes.** This project has hunted the first since
Phase 4 — `all()` over an empty list, `t.find("Healbot")` true on every screen, `finishes[-1] ==
"stop"` over a fixture that could not violate it. A probe that never reaches assertion 3 is the
purest case of it: assertion 3 is `True` on exactly the runs that did not evaluate it. It just did
not look like one, because the vacuity was in the *control flow* rather than in the predicate, and
every rule on the books was pointed at predicates.

And §2 is the same thing once more, one level up again: an assertion whose predicate is
`retire_at + worst_sol < CEILING` cannot fail when `worst_sol` goes to zero, because losing the
evidence and passing the test are the same event. **When a predicate's inputs come from a corpus,
the corpus needs a fixture check as much as the predicate needs a mutation check.** The real corpus
had one, since Phase 8, and it is why the missing-real-DB case fails loudly. The rig corpus did not,
and it is why the missing-rig-DB case reported 48.2%.
