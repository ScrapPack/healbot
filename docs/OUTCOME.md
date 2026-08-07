# Phase 12 — the box that could not fail

**The finding, up front.** `rig.py`'s `fire()` records a turn that **threw** and a turn that
**finished** in the same 3-tuple, and no rig in this suite has ever read the element that tells
them apart. Four `r.check` rows were phrased as claims about turns completing and were really
counting threads that had stopped. **TESTED:** three `fire()` calls aimed at a port with nothing
listening filled a box with three `URLError`s in **9 milliseconds**, and that satisfied every
completion predicate in the suite.

One of the four — `verify_question.py`'s concurrency row — had **no independent evidence anywhere
else in its file**. The other three sit next to a transcript check that carries the real weight.

This is Phase 9's defect, in the half Phase 9 could not reach. Phase 9 found vacuous passes by
running the suite from a fresh clone; a paid rig cannot run from a clone, so the paid half never
got the chance to report its false green. Phase 10 then read all twelve paid entrypoints as source
— and looked at *exit codes and floors*, which is a question about whether a rig can **report** a
failure, not about whether it can **see** one.

Method tags: **VERIFIED** (read the file, cite `file:line`) / **TESTED** (ran it) / **INFERRED** /
**SUSPECTED**.

---

## 1. The mechanism

`fire()` puts each prompt on a thread because `POST /session/{id}/message` blocks until the turn
completes. The thread appends its outcome to a caller-supplied list:

```python
out = api("POST", f"/session/{sid}/message", body)
if box is not None:
    box.append((label or sid, time.time() - started, out))
except Exception as exc:
    if box is not None:
        box.append((label or sid, time.time() - started, exc))
```

Both branches append. Same list, same arity, same first two elements. So `len(box)` answers *how
many turns ENDED*, and nothing in the tuple's shape tells a reader that it is not the answer to
*how many turns RAN*.

**The hazard was documented and unhandled.** `fire()`'s docstring has said `box` collects
`result_or_exception` since the day it was written. The library named the trap and every caller
walked into it.

VERIFIED across all 28 files in `.carryover/verified/`, and the negative is worth stating precisely
because "nothing reads it" is the kind of claim that needs an exhaustive search rather than a
confident one:

- No rig references `b[2]` or any index-2 read of a box entry.
- No rig tests a box payload against `Exception`. The only `Exception` tokens in the paid rigs are
  the thirteen `except Exception:` **crash guards** — Phase 10's mechanism, a different thing
  entirely, and the coincidence of vocabulary is part of why this stayed invisible.
- The box is destructured at exactly **four** sites, and every one of them is
  `for n, d, _ in box` / `for n, d, _ in workers` — the outcome bound to `_` and thrown away.

So the element that distinguishes a completed turn from a crashed one was, in every case, explicitly
discarded.

*(The docstring also said the tuple was `(elapsed, result_or_exception)` — two elements, where the
code appends three. Corrected.)*

### The measurement

`fire()` at port 9, three labelled turns, no server anywhere:

```
box has 3 entries
   worker1: elapsed=0.009s  payload=URLError: <urlopen error [Errno 61] Connection refused>
   worker2: elapsed=0.009s  payload=URLError: <urlopen error [Errno 61] Connection refused>
   worker0: elapsed=0.009s  payload=URLError: <urlopen error [Errno 61] Connection refused>

len(workers) == 3                          -> True
any(b[0] == "blocker" for b in box)        -> True
wait_for(lambda: len(box) == 3, ...)       -> True
```

Every completion predicate the suite owns, satisfied in nine milliseconds by three turns that never
reached a server.

---

## 2. Blast radius, stated exactly

The four rows are not equally load-bearing, and saying so is the point — this project's rule is
that a failing assertion gets the same scrutiny as a passing one, and an inflated finding is its
own kind of false green.

Line numbers below are **pre-Phase-12 specimens** — the state at commit `16ec8e7`, which this phase
edited. They are written without a colon on purpose: a citation quoted as broken must not be
spelled like a live pointer, or `probe_citations.py` cannot tell a specimen from a target
(`docs/CITE.md` §2's editorial rule). Follow the row names, not the numbers.

| Row (at `16ec8e7`) | Claim | Independent evidence? |
|---|---|---|
| `verify_question.py` line 87 | "the other sessions ran to completion alongside the blocked one" | **NONE.** This file never touched the worker sessions again — no transcript read, no payload check. This row was the whole evidence, and it could not fail |
| `verify_permission.py` line 85 | "the other three sessions completed while one stayed blocked" | Yes — three `payload-{i}` transcript rows two lines below. The row was a restatement of its own gate |
| `verify_question.py` line 150 | "the previously blocked turn ran to completion" | Yes — the next row finds the question tool's result in the transcript |
| `verify_permission.py` line 179 | "the previously blocked turn ran to completion" | Yes — the next row finds `/bin/zsh` in the transcript |

**So the honest summary is: one row with no backstop, three rows weaker than their own wording.**
The founding concurrency premise itself is *not* in doubt — `verify_permission.py` proves it with
fixture payloads pulled from the server, which is evidence a thrown turn cannot manufacture.

### What is NOT claimed

- **Five `wait_for` gates read the raw box too** (`verify_surface.py:45`, `verify_retire.py:84`,
  `verify_retire.py:130`, `verify_cold.py:124`, `verify_permission.py:224`). These are **sequencing**, not
  assertions. A thrown turn releases them early, and what follows then measures a screen that never
  got its workload — which produces a **RED downstream**, not a green. That is the correct outcome
  already, so they were left alone. `verify_retire.py:130` is the weakest of them: its next
  assertion is about a cell rendering `RETIRE`, which a thrown turn would not change. Noted, not
  fixed, because the claim it makes is about the grid rather than about the turn.
- **Four rigs never read the box at all** — `verify_handoff.py`, `verify_auto_retire.py`,
  `verify_headless_retire.py`, `verify_cold_question.py` construct it, pass it to `fire()`, and
  discard it. They take their evidence from server state and plugin logs instead. Write-only, not
  wrong.
- **`completed()` cannot see a turn that failed *inside* the model.** It distinguishes a request
  that threw from one that returned. A turn that returns HTTP 200 carrying an error is a completed
  request, and catching that is the transcript rows' job, not this one's.

---

## 3. The fix

**`rig.completed(box, prefix="")`** — the entries whose payload is not an exception.
`isinstance(b[2], BaseException)`, deliberately not a truthiness test: `None` and `[]` are what this
API returns for an empty body and an empty list, and a truthy filter would discard two real
completions.

The rule the four rows now follow: **gate on ENDED, assert on RAN.** `wait_for` still counts the raw
box, so a thrown turn releases the gate immediately; the assertion then counts `completed()`, so the
row goes red **fast** instead of green. Waiting for a completion that already failed would have
turned a false green into a seven-minute timeout, which is a worse trade than it looks.

Each detail string now prints `N/3 completed of M ended` and, when they differ, the exceptions
themselves — because the detail string is what a human reads when a row goes red, and that is
exactly where the raw box belongs.

**`verify_question.py` also got the backstop it never had:** three `payload-{i}` transcript rows,
copied from `verify_permission.py`'s known-good pattern. A turn that threw leaves no payload, so the
claim now rests on evidence from the **server** rather than on the rig's own thread bookkeeping.
Floor 27 → **30**.

---

## 4. The guard — contract 6

`probe_rig_contract.py` gains a sixth contract, free, and it is a different animal from the first
five. Contracts 1–5 ask whether a rig can *report* a failure. Contract 6 asks whether it can *see*
one:

> **No `r.check` predicate may decide that a turn completed by counting `fire()`'s box.**

Implemented as taint analysis over the AST. `box` is the seed; a name bound from a tainted
expression is tainted (`ended = [b for b in box ...]`, and `threw` through it), **unless the binding
routes through `completed()`**. Iterated to a fixpoint, because `ast.walk` is not source order.

Three scoping decisions, each of which could have made the guard useless:

- **Scoped to `args[1]`, the predicate — never the detail string.** `args[2]` *should* mention the
  raw box and the exceptions in it. A guard that flagged the detail string would have driven the
  evidence out of the error message.
- **Absence claims are exempt.** `not any(b[0] == "blocker" for b in box)` claims a turn has **not**
  ended; a thrown turn puts an entry in the box and makes it False — red, which is right. Only
  *positive* completion claims are the defect. Detected as: every tainted read sits under a `not`.
- **The exemption is counted out loud** and asserted to be non-empty and ≤ 3
  (`{'verify_permission.py': [93]}`). An exemption nobody exercises is dead text; one that grows
  unwatched is how a guard stops guarding.

### Controls

Seven new assertions, and the ones that matter are the negative ones:

- **The live sweep on the real tree**: 24 entrypoints, zero violations.
- **MUTATION** — reverting a fixed row to the raw-count form is detected.
- **MUTATION (inverted)** — the same claim routed through `completed()` is *not* reported.
- **MUTATION** — stripping the `not` off an exempted predicate turns it into a violation. Without
  this leg the exemption could be widening to cover everything and the sweep would still read green.
- **RUNTIME** — `completed()` really rejects an exception and really keeps `None` and `[]`.
- **NEGATIVE CONTROL ON THE REAL FILES, not synthetics.** The finished guard, run against the
  pre-Phase-12 source recovered from git `HEAD`, reports **exactly four violations at exactly the
  four lines named in §2** — `verify_permission.py` 85 and 179, `verify_question.py` 87 and 150 —
  one exemption at `verify_permission.py` line 87, and **zero** against the fixed source. The guard was
  written from the finding and then made to rediscover it.

`probe_rig_contract.py`: 22/22 → **29/29**, floor 29.

---

## 5. Corrections to the record

- **The rig sweep is 24 entrypoints, not 23.** `NEXT.md` and `docs/VERDICT.md` both say 23; the
  sweep is 12 probes + 11 `verify_*` + `smoke.py`. `probe_rig_contract.py`'s own detail string also
  read *"all twenty end on it"*, hardcoded from Phase 10 — now `len(names)`.
- **`fire()`'s docstring had the wrong arity** — `(elapsed, result_or_exception)` for a 3-tuple.
- **Free suite: 180 → 187.**

## 6. What was checked and found healthy

Stated because a phase that only reports defects gives no sense of what "looked at" means.

- **Every rig's assertion floor is tight, and the one exception is deliberate.** Computed floor vs.
  statically reachable count across all 24. Twenty have a static bound; **19 of those 20 have
  `floor == unconditional count`** — zero slack, so nothing can silently skip an assertion and still
  clear its floor. `verify_cold.py` (floor 17, reachable 21) and `verify_control_agent.py` (15 / 16)
  look slack and are not: the difference is exactly their conditional rows.
  The exception is `probe_turn_growth.py`, floor **16** against an unconditional count of **15** — it
  requires a *conditional* row to fire, the fixture check guarded by `if have_real`. That is not an
  oversight: the real corpus is REQUIRED (`docs/CLONE.md`), and its absence already fails the
  unconditional row above it at `probe_turn_growth.py:295`. The remaining four rigs emit checks from
  inside loops, so no static bound exists and their floors are verified only by running them — which
  the free suite does every phase, and which this phase's paid run did for `verify_question.py`.
- **`term.py` is clean.** 115 lines, no swallowed failures; `pump()` sets `alive = False` rather
  than raising, which is deliberate and read by callers.
- **The twelve free probes still hold every load-bearing figure.** `probe_turn_growth.py`'s maximum
  (175,148), bound (184,852) and margin (4,852 / 1.3%) are unchanged, and the model pin still
  resolves.

## 7. The second finding — three paid rigs are SINGLE-USE, and nothing said so

Found by running one. **VERIFIED + TESTED.**

`rig.db(name)` returns `{WORK}/{name}.db` and **never resets it** (`rig.py:42-49`). The file
persists across runs by design — the retirement corpus depends on that. But the grid header counts
*every session in the DB*, and four assertion sites compare it against a **literal**:

| Site | Literal |
|---|---|
| `verify_permission.py:116` | `t.find("4 sessions")` |
| `verify_permission.py:143` | `t.find("4 sessions")` |
| `verify_question.py:135` | `t.find("4 sessions")` |
| `verify_cold.py:102` | `t.find("1 session")` |

So each of those rigs passes **only on a pristine database**. Run it a second time and the header
reads `8 sessions`, the row goes red, and the redness has nothing to do with the code under test.

**TESTED, the expensive way and by accident.** This phase's first execution of `verify_question.py`
was killed mid-run by a tool timeout, leaving four sessions in `hb/quest.db`. The next run created
four more, the grid header rendered `Healbot  8 sessions  1 blocked`, and line 135 went red.

The consequence is bigger than one red row. **The recorded scores for these three rigs were
reachable only on their first-ever execution**, which makes them the same class of claim Phase 10
named — a score that is true of a file at a moment — with a second clock on it. Re-running one now
requires archiving its DB first, and nothing in the rig, the README or the docs said so.

**Not fixed here, deliberately.** The obvious repair is to derive the expected count from what the
rig created instead of hardcoding it. Doing that *after* paying for a run would edit the file the
new score describes, which is precisely the defect Phase 10 recorded. The rigs are frozen at the
version that produced this phase's score, and the repair is handed to Phase 13 with the sites named.

*Archiving, not deleting, is the right move when clearing a DB:* `hb/*.db` is the corpus
`probe_turn_growth.py` derives `worst_turn` from (`docs/CLONE.md` §4), so a cleared DB should be
renamed to something that still matches the glob — `quest.db` → `quest-phase12a.db` — or the act of
making a rig re-runnable quietly deletes the evidence that sizes `RETIRE_AT`.

### The fixture was restored at the end of the phase — 94 MB → 1.8 MB

Done **after** the re-derivation and the commit that recorded it, on the owner's instruction, so no
number in this document depends on it. `hb/project` is back to exactly the seven entries the rig
declares: `worker0-2.txt`, `ledger0-2.txt` and `.git`. Seventy-nine were removed — 70 `chunk*.txt`,
`node_modules`, and the `package.json` / `package-lock.json` / `vitest.config.ts` / `biome.json` /
`findings.txt` / `hello.txt` / `notes.txt` a model created during a run.

**It deleted no measurement, and that was verified rather than assumed:** `probe_turn_growth.py`
re-run afterwards reports every figure unchanged — 107 turns, in-scope maximum 70,704, out-of-scope
maximum 299,326, 19/19. The evidence was always in `hb/*.db`; the project directory only ever held
the *workload*. Free suite 190/190 after the clean, ledgers verified at 130,025 bytes (above
`fixtures()`'s 130,000 regeneration threshold, so it left them alone) and worker payloads intact.
`git_baseline()` re-ran to commit the deletions, so the worktree is clean and a session's diffs
start from a known tree again.

**One consequence, introduced deliberately and worth knowing.** The removed set included a
`.gitignore` holding `node_modules/`, which was itself model-created residue and not declared. If a
future rig run shells out to `npm install`, `git_baseline()`'s `git add -A` will now commit
`node_modules` into `hb/project/.git` and bloat it — the old `.gitignore` was the only thing
preventing that, and it is gone because it was never part of the fixture. The principled repair is
to make it declared: `rig.fixtures()` should write the `.gitignore` alongside the other six files.
Not done here for the reason in §7 — `rig.py` is imported by the rigs whose scores this phase
records.

**REPAIRED 2026-08-07, and more broadly than the paragraph above proposes.** A `.gitignore` would
only ever have covered the residue somebody thought to name. The fix instead removes the mechanism:
`rig.py` now declares the fixture set once as `FIXTURE_FILES`, and `git_baseline()` adds *only
declared* files rather than `git add -A`. A rig that creates baseline content on purpose declares
it through `git_baseline(also=)` — `verify_retire_350k.py` passes `chunk*.txt`, because it writes
70 chunk files before the baseline so a session can read them without every read counting as a
diff, and deletes `findings.txt` immediately after so that creating it *is* one. Anything undeclared stays out of the baseline and therefore stays
visible as a change, which is the property this function exists to provide. It also self-heals a
baseline that is already contaminated — undeclared tracked files are dropped from the index with
`git rm --cached`, so nothing leaves the disk and a paid run's evidence survives — and it prints
the residue rather than absorbing it. TESTED both ways on an isolated fixture, including a path
with spaces.

The claim above that `hb/project` is "back to exactly the seven entries the rig declares" was no
longer true when this was written: the directory held 12 entries and its inner repo tracked four
undeclared files — `.gitleaks.toml`, `dns_tunnel_detector.py`, `linux_triage.sh` and
`requirements.txt` — all committed by the old `git add -A`. The next rig run untracks them
automatically.

## 8. A third thing, found while diagnosing — `wait_for`'s timeout does not bound

**VERIFIED by reading; NOT TESTED** — it did not fire in either run this phase, and it is recorded
at the tier it was established at.

`wait_for(fn, timeout, label)` checks its deadline only *between* calls to `fn` (`rig.py:630`), and
`Api.__call__` defaults to **`timeout=900`** (`rig.py:383`). So:

```python
wait_for(lambda: api("GET", "/question"), 300, "question.asked")
```

advertises a 300-second budget that a single hung HTTP call can hold for **900** — a worst case of
roughly 1,200s against a stated 300. Every `wait_for` in the suite that wraps an `Api` call has this
shape.

It is the same defect as the rest of this phase wearing different clothes: **a number that reads as
a guarantee and is not one.** A call site passes `300` and a later reader takes that as the bound;
nothing enforces it. That it has never fired is not evidence it cannot — the servers in this suite
have always either answered fast or refused the connection outright, and neither of those is the
case the 900 covers.

Not fixed here for the same reason as §7: `rig.py` is imported by the rigs whose scores this phase
records, and editing it after paying for a run makes the score a claim about a file that no longer
exists. Handed to Phase 13. The likely repair is that `Api` should take its timeout from the
`wait_for` budget that wraps it, or default to something far below the smallest budget in use.

## 9. The fourth finding — `verify_question.py` has been three assertions RED since Phase 5, and Phase 10's method could not have found it

**TESTED.** Running the rig produced **27/30, exit 1**, on a clean database. This is its first
execution since Phase 4.

Three rows are red, and they are **not** fixture contamination — they survived a pristine DB:

| Row | Why it fails |
|---|---|
| `'a' on an unblocked cell opens no panel` | The cursor is **on** the blocked cell, so `a` opens the panel |
| `tab moved the cursor onto the blocked cell` | It is already there; `tab` has nowhere to move (`(2,2) -> (2,2)`) |
| `the grid is still rendered while answering` | `t.find("4 sessions")` — the header read `6 sessions` |

### The chain, from git

1. **Phase 4** (`90e3d37`) wrote all three assertions and recorded **27/27** in the rig README. They
   passed: auto-surface did not exist yet.
2. **Phase 5** (`823d7a2`) *built* auto-surface — a block moves the cursor onto itself — and added a
   comment to this very file saying so: the asker *"lands in cell 0 — the initial cursor position.
   This rig therefore asserts the cursor SURFACES onto the block (an event-driven move), **not that
   `tab` reached it**."* It then **left the three assertions that assume the opposite in place**, and
   never re-ran the rig. The comment and the code have contradicted each other ever since.
3. It would not have mattered if it *had* been run: at Phase 5 this file ended `finally: r.summary()`
   with **no `sys.exit`** — one of the six rigs Phase 10 caught. A red run exited 0.
4. **Phase 10** (`b036968`) added the verdict exit but did not run the rig; its paid-rig fixes are
   VERIFIED, not TESTED.
5. **Phase 12** is the first execution in eight phases.

### Why this is a limit on Phase 10's guard, not just another stale score

Phase 10 reconciled every rig by counting `r.check(` sites against the recorded score, and wrote
that the command *"reconciles every other rig in one command."* `verify_question.py` has **27 static
sites and a recorded 27/27** — it reconciles *perfectly*, and it was three assertions red the whole
time.

**Counting proves a score is arithmetically reachable, not that it is achievable.** Phase 5 changed
the *behaviour under test*, not the assertion count, and no static method can see that. The only
instrument that detects it is running the rig — which is the one thing the paid half structurally
resists, and precisely why these findings keep surviving for phases at a time.

The product is **not** at fault. Auto-surface is the intended Phase 5 feature and
`verify_surface.py` exists to test it. The three assertions are stale, and the correct repair is to
assert the surfacing behaviour the file's own comment describes.

**Not repaired here**, for the reason given in §7: this phase finally has a *real* recorded score for
`verify_question.py` — the first since Phase 4 — and editing the file now would make that score a
claim about something that no longer exists. Recorded as **27/30**, three known reds, named.

## 10. The fifth finding — `worst_turn` is a fact about the WORKLOAD too, and the workload is an undeclared artifact that grows every time anyone pays

**TESTED, and it leaves the free suite RED at 184/187.** `probe_turn_growth.py` reports **13/16,
exit 1**. This is the probe working exactly as designed; the number it guards moved.

A single turn on the pinned `gpt-5.6-sol` measured **299,326** tokens of growth — **71% above the
175,148** that every document derives `RETIRE_AT` from. The rule is
`RETIRE_AT + worst_turn < ceiling`:

```
180,000 + 299,326 = 479,326   against a ~360K ceiling   →   margin -119,326 (-33.1%)
```

### It is a real turn, not an artifact of the killed run

The obvious hypothesis was fixture damage — the session came from a run a tool timeout killed
mid-flight. The message-level accounting refutes it. One user message opens the turn, seventeen
assistant steps follow, and occupancy climbs monotonically:

```
#   role        finish        err     occupancy   turnOver
0   user        None          False           0   False
1   assistant   tool-calls    False       5,067   False
4   assistant   tool-calls    False     106,832   False
8   assistant   tool-calls    False     270,291   False
…
17  assistant   stop          True      299,326   True
```

That is **one turn**, closed by the shipped `turnFinished()` predicate. The kill set the error on the
final step, which is why the turn closed at all — so 299,326 is a **lower bound**: the turn was still
growing when the process died.

### What actually made it that big

The rig's project directory has accumulated across every paid run in this project's history:

| | |
|---|---|
| entries | **84** |
| total size | **94 MB** |
| `node_modules` | **present** — a model in an earlier run ran `npm install` |
| other | 70 `chunk*.txt` (≈2.4 MB), three 130 KB ledgers, a 48 KB `package-lock.json` |

`rig.fixtures()` is idempotent for the files *it* creates, but the sessions create files nobody
cleans, and `git_baseline()` commits them into the baseline so they are invisible as *changes*
forever after. The directory only ever grows.

**Excluding this phase's two runs, the corpus maximum is still exactly 175,148.** Two runs in a
polluted directory moved the load-bearing figure by 71%.

### Why this is a methodological finding and not just a bigger number

`HARNESS.md` says `worst_turn` "is a fact about a **MODEL's** tool-calling behaviour, not about
opencode." That is incomplete. It is also a fact about the **workload** — and the workload is an
**undeclared** artifact that grows whenever anyone runs a paid rig. Phase 8 discovered the figure
was model-specific and pinned the model so changing it goes red. Nothing pins the *directory*, so
the same class of silent invalidation is wide open on the other axis, and it moves on its own.

It also breaks a second claim as collateral: the assertion that off-pin turns exceed the pinned
model's worst case now fails, because the pinned model's new maximum (299,326) exceeds the
`gpt-5.6-terra` turn (223,258) that was the *evidence* for model-specificity. The probe says so out
loud rather than dropping it — *"if this ever goes empty, the model-specificity warning above has
lost its evidence and should be re-argued rather than inherited."*

### Where this went

Two readings were put to the owner — *the measurement is representative* versus *the fixture is
unrepresentative* — and the answer was neither: **define what is in scope and re-derive.** §11 is
that work, and it found the corpus had never had a scope at all.

## 11. The re-derivation — the corpus gets a declared scope, and the rule stops answering a question the gate never asks

**The scope was already argued in the probe and never applied.** `probe_turn_growth.py` carries a
comment headed *THE DECISIVE CUT*:

> *"The gate only ever faces a turn that STARTS just under `RETIRE_AT`. A 223K first turn out of an
> empty session is a true observation about turn growth and a poor proxy for that scenario, so
> condition on where the turn started."*

It then conditioned the *printout* and left the load-bearing assertions on the unconditioned
maximum. Every number in every document derives from that unconditioned maximum.

### The measurement that settles it

**All four of the largest turns in the corpus start at zero** — 299,326, 223,258, 182,918, 177,110.
So does 175,148, the figure five documents derive the old bound from. Condition on where the turn
began and the distribution is a different shape:

| start ≥ | n | max delta | bound on `RETIRE_AT` | margin at 180,000 |
|---|---|---|---|---|
| 0 (the old rule) | 107 | 299,326 | 60,674 | **−119,326** |
| 25,000 | 35 | 70,704 | 289,296 | +109,296 |
| **100,000** | **20** | **70,704** | **289,296** | **+109,296 (30.4%)** |
| 180,000 | 10 | 32,673 | 327,327 | +147,327 |

### Why the exclusion is sound and not a convenience

A turn that starts at 0 and grows 299,326 **ends at 299,326** — under the ~360K ceiling — and is
retired at its end. **It was never a cliff.** The rule `RETIRE_AT + worst_turn < ceiling` exists for
one scenario: a session that has accumulated to just under the gate takes one more turn. A
first-turn-from-empty is not that scenario, and including it conflated the gate's job with a failure
mode **no value of `RETIRE_AT` can prevent** — a single turn from an empty session that exceeds the
ceiling on its own dies whatever the gate is set to. That conflation is the whole reason the margin
read 1.3%.

The rule is asserted to be honest rather than argued to be: **`probe_turn_growth.py` now checks that
the scope throws out 175,148 too.** A scope invented to protect the old number would have kept it.
The excluded population and its maximum are printed on every run.

### The scope, as declared

A turn is in scope for sizing `RETIRE_AT` iff **(1)** it completed under the shipped
`turnFinished()` predicate, **(2)** it started at or above `GATE_FLOOR = 100,000`, and **(3)**
compaction was off — the regime the harness ships. Condition 3 is currently free (all 20 in-scope
turns are already compaction-off) and is stated so it cannot drift in unnoticed.

### The re-derived answer

```
IN SCOPE:  180,000 + 70,704 = 250,704 < 360,000        margin 109,296  =  30.4% of the ceiling
bound on RETIRE_AT:  289,296     (supersedes 184,852, and the ~190,000 before it)
```

**`RETIRE_AT = 180,000` is well justified** — by a 30.4% margin rather than the 1.3% on record. The
decision §0 records was right; the derivation under it was answering the wrong question, in the
conservative direction.

### The real evidence gap, which is not the threshold

The in-scope maximum of 70,704 is a **cross-model** figure (`gpt-5.5`). On the pinned `gpt-5.6-sol`
there are 12 near-gate turns and **eleven of them are `verify_retire_350k.py`'s fixed
22,152-per-turn synthetic loop**; the single non-synthetic one is 109 tokens. So:

> **No real near-gate turn has ever been measured on the pinned model.**

Using the all-model maximum is the conservative choice — 70,704 against the pinned model's 22,152 —
and the probe asserts that direction so it cannot silently invert. But Phase 8 established the
threshold is model-specific, and the population that now carries it has almost no pinned-model
evidence in it. **That is the outstanding work**, and it is a measurement, not a decision.

`probe_turn_growth.py`: 16/16 → **19/19**. Free suite **190/190**, every probe exit 0. Nothing was
deleted: `hb/quest-phase12a.db` still holds the 299,326 turn, and the probe still prints it.

## 12. The pattern, now five phases old

Each phase's free finding has come from looking at a surface nobody had looked at **as an artifact**:
the derivation under a number (8), the suite from a fresh clone (9), the paid rigs as source (10),
the prose as pointers (11) — and now **the library the whole suite stands on**. `rig.py` and
`term.py` are the two files `probe_rig_contract.py` explicitly excludes, for a reason that is
correct as far as it goes (they own no assertions of their own) and that left the file defining
every rig's evidence semantics as the one thing nothing read.
