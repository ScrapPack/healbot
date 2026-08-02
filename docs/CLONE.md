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

**(b) A timeout raises nothing at all.** `wait_for()` (`rig.py:593-604`) prints
`!! timed out waiting for …` and returns `None`. No exception, so guard (a) would not have caught
it either — the probe runs fewer assertions. This is `probe_headless_arm` reporting
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
not have had it — it had one corpus and no way to tell a stable maximum from an artifact of the
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

---

## 8. The second fresh-clone walk (added 2026-08-02)

A staging-polish pass re-ran §1's experiment against the **public** repo, following
`README.md`'s quickstart exactly as a stranger would: `git clone
github.com/ScrapPack/healbot`, doctor, `core.hooksPath`, checkout reconstitution, venv, env
scripts. Clone at `d36ee31` (local `main` was one unpushed commit ahead at walk time).

Phase 9's picture has **inverted**, and the reason is that the paid corpus is tracked now —
22 `hb/*.db` un-ignored by name. Where Phase 9 measured one probe of ten surviving a fresh
clone, a clone reconstituted per the README runs **19 of 21 green on a settled pass**. §5's
"`probe_error_state` and `probe_focus` are free only if you inherited a paid database" no
longer holds: both run green from a clone that has paid for nothing. §1's portability
sentence is now the outlier rather than the rule.

The two reds are the phase's findings, and only one of them is a repo defect.

| | |
|---|---|
| **The documented reconstitution does not reproduce the overlay, and it BLOCKS THE GATE** | `git apply` reproduces **15 of 17** overlay files byte-for-byte and leaves two behind. Doctor **1 FAIL**, `probe_twin.py` **24/25 exit 1**, `gate/gate.py` **exit 2 BLOCKED**. §8.1 |
| **`probe_backend.py` dies with a raw traceback on any clone with no Claude Code history** | Honest exit 1 and a SHORT RUN, so never a false green — but a `FileNotFoundError` instead of a cause, which is the defect §5 fixed for `probe_twin` and nobody generalized. §8.2 |
| **`. harness/env.sh && opencode` cannot produce the grid, and two documents said it could** | TESTED on the 1.18.5 release: `diff-viewer` and `which-key` present, **zero** `healbot` strings. The harness config still reaches it — the retirement plugin armed at 180,000 on that binary — so everything works except the headline screen. §8.3 |
| **Doctor's claude tier read READY over a red row** | The crew-constraints check names its row for the state it found; the tier guarded one spelling of three. NEGATIVE CONTROL RUN: the old guard prints `[FAIL] crew constraints materialized` and `[READY] claude code workflow` in the same output. §8.4 |
| **One knob still needed manual path config** | `HB_CLAUDE` defaulted to a literal `$HOME/.local/bin/claude` while the doctor's `claude` row resolves through `PATH` — the preflight could pass on a machine where the fleet cannot find the binary. §8.5 |

### 8.1 The patch is a third copy of the overlay, and nothing compared it to `fork/`

`probe_twin.py` asserts `fork/` against `opencode/` across all 17 files with a mutation
control. It has never had anything to say about `fork/healbot-fork.patch`, which is a third
copy of the same 17 files — and the checkout is kept in sync **by hand**. So the guarded
pair stayed green on the machine doing the work while the unguarded pair silently came
apart.

TESTED, by `cmp` over all 17 in the reconstituted clone: 15 identical, and
`packages/core/src/session/SESSION.MAP.md` plus
`packages/tui/src/feature-plugins/FEATURE-PLUGINS.MAP.md` differ. The patch was last cut at
`045e416` (Phase 7). Phase 11 (`16ec8e7`) corrected `file:line` citations inside those two
maps and copied each into the checkout by hand — the exact operation `fork/README.md`'s
Drift section describes itself doing, in a paragraph that names the risk of forgetting one
and does not notice that the patch is a copy too. Only `.MAP.md` prose diverged; every code
path in the overlay is byte-identical, `healbot.tsx`, `builtins.ts` and
`.opencode/opencode.jsonc` included.

What makes it worth a section rather than a line: **a stranger cannot pass the gate on a
clean clone**, for a reason that is not their change and that no message on the way names.
`fork/README.md`'s claim that "every one of the 17 overlay files is byte-identical to
`fork/` afterwards" was TRUE when Phase 11 measured it and is the casualty; it now carries a
dated correction.

**The repair is a step, not a regenerated patch.** `fork/` is the authority — it is what
`probe_twin` and the doctor read — and the patch is the base-relative bootstrap, pinned to a
fork branch that no longer exists as a repository. Regenerating it would trade the only
provenance the artifact has for two lines of prose. Both reconstitution blocks (`README.md`,
`docs/WINDOWS.md`) and `fork/README.md`'s own now end with

```sh
cp -R fork/packages/. opencode/packages/ && cp -R fork/.opencode/. opencode/.opencode/
```

TESTED after adding it, in the same clone: doctor **0 FAIL**, `probe_twin.py` **exit 0**,
`gate/gate.py` **`== PASS ==`**.

Note what is still unguarded and is now written down rather than assumed: the checks read
the **end state**, so the patch may drift again and nothing will say so until someone
reconstitutes without the copy step. That is acceptable only because the copy step is now in
every path that reconstitutes.

### 8.2 `probe_backend.py`'s raw traceback

With no recorded Claude Code session for the checkout — the ordinary state of a fresh clone
— `transcript_path resolves a recorded session` fails with `sid` None, and the next line
builds a path ending `None.jsonl` and raises `FileNotFoundError` from inside `backend.py`.
Reproduced both under the harness `CLAUDE_CONFIG_DIR` and with it unset, so it is what a
stranger sees either way.

Exit was already 1 with a SHORT RUN summary, so this was never in the false-green class —
the same classification §5 gave `probe_twin`'s identical crash. It gets the same repair: a
named diagnostic saying which corpus was searched and what would populate it. Deliberately
**not** converted to a declared skip: the rows below it are the whole probe, and a skip that
large is a green run measuring almost nothing.

**And it is not a fresh-clone condition — it is red in the MAIN checkout too**, which the
walk only noticed because the diagnostic finally said what was missing. TESTED both ways:
the pre-change file prints `FAIL UNEXPECTED EXCEPTION`, 5 rows, exit 1; the changed one
prints the same two real reds plus the cause, exit 1. The cause is that
`harness/claude/projects/` holds transcripts for the two **pool slots** and nothing for the
repo root — every crewmate so far has run in a leased worktree, so the config root the
harness pins has never recorded a session at the path this probe derives. That is a fact
about how the fleet has been used, not a defect, and the repair is one interactive `claude`
run in the main checkout under `env.claude.sh`. Recorded here rather than fixed, because
fixing it means spending a session, and the probe now says so itself.

### 8.3 Which `opencode` the README's own command runs

`harness/env.sh` exports config isolation and the two prompt switches and touches `PATH` not
at all, so `. harness/env.sh && opencode` runs whatever release is installed. `fleet.sh` has
modelled this correctly since it was written — it prefers the checkout, falls back with a
three-line warning, and refuses when there is neither — but `README.md` advertised the grid
in its opening paragraph and never said the grid needs the fork, and `docs/WINDOWS.md` was
worse: step 6 said "the grid is `/healbot`" directly after that command, and its
INFERRED→TESTED conversion checklist asked the PC to verify `/healbot` exists **via a
command that cannot produce it** — on a PC that the prerequisites table never told anyone to
install opencode on.

Both are corrected, and the doctor gained an `opencode CLI` row that names both halves:
which binary a session would get, and that a released one carries the pin, compaction-off
and retirement but no grid. It is never a FAIL and is deliberately **not** wired into the
opencode tier — the fork path runs from source under bun, so a released binary is optional.

### 8.4 The tier summary that outranked its own rows

`tier_summary()`'s claude tier read `st.get("crew constraints STALE") != FAIL`. The
crew-constraints check names its row for the state it found — `materialized`, `STALE`, `not
materialized` — so a symlink pointing at the wrong target FAILs under the *first* name and
the guard never saw it. Now matched on the family, not a spelling.

Both controls run, in the fresh clone with the symlink repointed at `settings.json`:

- **negative** — the pre-fix guard from git prints `[FAIL] crew constraints materialized`
  and `[READY  ] claude code workflow` in the same run;
- **positive** — the fixed guard prints `[NOT YET]` for the same mutation, and `[READY  ]`
  again once the symlink is restored.

Worth naming as a rule, because it is the same shape as §1 one level up: **a row name that
varies with the state it reports cannot be a key.** The green survived a red row, which is
this project's characteristic failure with a summary line instead of an assertion.

### 8.5 The minimal-config inventory

Every knob a fresh user can reach was enumerated and checked for two properties: optional
with a derived default, and documented where it is read.

| Knob | Verdict |
|---|---|
| `HARNESS_ROOT` | derived from `$BASH_SOURCE`, `:-` so an explicit value wins, and the failure is loud. Documented in both env scripts' headers |
| `XDG_CONFIG_HOME` / `CLAUDE_CONFIG_DIR` | set BY the env scripts from `HARNESS_ROOT`, never by the user, `hb_nativepath` at the boundary |
| `HEALBOT_RETIRE_AT` / `HEALBOT_AUTO_RETIRE` / `HARNESS_TRIM_TOOLS` | shipped commented-out in `env.sh` with the derivation beside them |
| `HEALBOT_REVIEW` / `HEALBOT_PUBLISH` / `HEALBOT_GATE*` / `HEALBOT_REVIEW_*` / `HEALBOT_PUBLISH_*` | all `os.environ.get(name, default)` or `${VAR:-default}`; `OPERATIONS.md` carries the two an operator uses |
| `HB_SOCKET` / `HB_RUN` / `HB_FLEET_DIR` / `HB_SPAWN_TIMEOUT` / `HB_*_MARKER` | derived; markers carry their evidence tier inline |
| `HEALBOT_RIG_WORK` / `HEALBOT_VERIFY_SCRATCH` / `HEALBOT_POOL` / `HEALBOT_AB_RUNS` / `HEALBOT_CLAUDE_BIN` | derived; rig-side, documented at the read |
| the LaunchAgent plist | `install-db-backup.sh` substitutes the real `$HOME` for `__HOME__` at install time — no tracked absolute path, no manual edit |
| `core.hooksPath` | one documented command, and the doctor WARNs until it is set |
| **`HEALBOT_OPENCODE`** | optional with a derived default and **undocumented at its point of use** — `fleet.sh` explains at length which opencode it picks and never names the override. Fixed: a comment there and a row in `OPERATIONS.md` |
| **`HB_CLAUDE`** | **the one real defect.** It defaulted to a literal `$HOME/.local/bin/claude` — this machine's installer layout, not a derivation — while `doctor.py`'s `claude` row resolves through `PATH`. So the preflight could report PASS on a machine where every crew spawn fails its ready-wait. Now `command -v claude` with the old path as fallback |

### 8.6 Two controls that refuted the evidence before it was written down

Both belong here because the finding in each case would have been wrong and confident.

**A binary grep with no negative control.** The first attempt at §8.3 ran `grep -c healbot`
over the installed binary, got 0, and was one sentence from being recorded as TESTED. The
control — grep the same binary for `opencode` — also returned 0, which is impossible.
`grep -c` was not reading a 138 MB Mach-O usefully at all. Redone with `strings`, the
controls hold (`diff-viewer` 1, `which-key` 2) and the finding stands. **A negative control
is not a formality when the tool is the thing that might be broken.**

**A hypothesis that fit the evidence and was still wrong.** Booting the installed binary
under `env.sh` produced no `[healbot] headless retirement armed` line, which fit the
harness-plugin-does-not-load story exactly. Booting the **fork** the same way produced no
line either — so the method was wrong, not the binary. The plugin initializes lazily on the
first request for a directory; one `curl` at the server and the arming line appears on the
released binary at the shipped 180,000 gate. Without the positive control this walk would
have reported that the harness does not retire on a released opencode, which is false.

**A fourth, and it left something open.** The front-door paragraph added to `README.md`
claimed "`HARNESS.md` indexes the records newest-first". MEASURED against `docs/`: of the
seventeen dated records, **three are not in that table** — `docs/SHIP.md` (Phase 13, the
newest, reachable only from HARNESS.md's own Phase 13 section) and `docs/AFK.md` and
`docs/REFUSAL-RESCORE.md`, which appear in HARNESS.md **zero** times. HARNESS.md's stated
exit test is *"from this file alone you should be able to name the file that owns any given
behavior"*, and for those two it does not hold. The README now says "most of them" and names
the exceptions, which is honest but is not the repair. **The repair is left undone
deliberately**: adding rows to that table shifts every line under it, and other files point
at those lines. Counted over every tracked file, `HARNESS.md:NNN` appears **22** times
across **7**. Four of those are inside `fork/healbot-fork.patch` and are not pointers at
all — frozen text in a recorded diff, and two of them are the stale pointer at line 316 of
HARNESS.md that §8.1 is about (written out rather than in live `file:line` form, per the
citation-hygiene rule: the probe cannot tell a specimen from a pointer). That leaves **18
live pointers across 6 files**, of which **11 target a line below the table**. Repairing
those means editing two dated phase records during a presentation pass, with a parallel
session already writing to HARNESS.md. Named here so it is a task and not a silence.

The same review also caught `docs/CLONE.md` — this file — being listed as live surface *and*
excluded from "everything else is a dated phase record"; it is both, and the paragraph now
says so.

**And the census above took three tries.** First "seventeen citations from `docs/AFK.md` and
`docs/REVIEW.md`" — a number carried over from a spot-check list run earlier in this session
for a different question and never re-derived, which is the whole of its provenance; no
reading of the citations yields it. Then "18 across six files", from a script whose file
filter (`.md/.py/.ts/.sh`) was real but undeclared, so it silently dropped the patch and
reported a scoped number as a repo-wide one. **An undeclared filter is an unmeasured claim
wearing a measurement's clothes** — the same shape as §8.3's `RELEASED build`, in a
different medium. Both were caught by the push review and neither by the author, in a
paragraph whose subject is wrong counts.

**And a third, from the push review of this very section.** Two findings, both real. The
correction added to `fork/README.md` said "all five code paths in the overlay" while naming
three — a fresh wrong count inside the paragraph that exists to fix a wrong count; the
overlay is 14 maps plus exactly three non-map files. And the doctor's new `opencode CLI` row
called anything on `PATH` a RELEASED build, which is an unmeasured claim about a file: a
`bun link` from the checkout puts a FORK build on `PATH` and would have been reported
grid-less on the doctor's own authority — §8.3's defect, reintroduced by §8.3's own fix. The
row now resolves the symlink chain (the one case settleable for free) and states the
CONDITIONAL for every other, with both branches mutation-controlled. **A pass that corrects
counts and unmeasured claims is exactly where a new one gets written down.**
