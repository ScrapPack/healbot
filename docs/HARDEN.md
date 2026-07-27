# Phase 5 — harden the grid, and build the fleet

Date 2026-07-27. Phase 5 did not exist in `PLAN.md`, which stops at Phase 4. It was created out
of the residue of an adversarial audit of Phase 4's completeness, and has two halves:

**A.** Fix what the audit found, and repair the instrument that failed to find it.
**B.** Build `opencode serve` + `opencode attach` — the long-lived-server architecture
`PLAN.md:378` assumed from the start and that `HARNESS.md` had recorded as **blocked**.

---

## 1. The audit, and the honest answer on Phase 4

67 agents across five dimensions, every finding put to an adversarial verifier that defaulted to
refuting it. 61 findings, **56 survived**, 5 refuted.

**Is the Phase 4 exit gate met? Yes — on outcome. The instrument was weaker than its numbers.**

Both clauses genuinely happened, and the artefacts in the run databases confirm it: four turns
in flight at once, a permission answered from the grid with the answer reaching the model, and a
handoff that carried the objective, both open todos into the successor's own list and a changed
file, at occupancy 90,310 → 5,649. None of that is in doubt.

What is in doubt is the evidence that was written to prove it:

| Claim | Assertion that carried it | Verdict |
|---|---|---|
| "continuity 1/3 — handed the objective" | `"Original instruction" in seed` | **Tautology.** `healbot.tsx` emits that heading into *every* document unconditionally, and an assertion 33 lines earlier already entailed it |
| "continuity 3/3 — handed a changed file" | `"stage1.txt" in seed` | **Collision.** The objective is echoed verbatim into the same document and it names `stage1.txt`. Stripping the entire file section left the predicate green |
| "started at its OWN occupancy" | `r.check(..., True, "see figure below")` | **A literal constant.** The headline 21/21 is 20 substantive + 1 label |
| "the route never changed" ×9 | `t.find("Healbot")` | **True on every screen.** `Term.find` lowercases and the run's own project path contains `healbot`. Measured `True` on home, on the grid, on the session route, and on home again after quitting |

That makes **eight** bad assertions across this effort against four real defects found by tests.
The pattern is stable enough to name: *this project's tests fail by passing.* Every fix below
that touches the rig is aimed at that, not at coverage.

**Gate ≠ build order**, and conflating them is the error this project keeps catching in itself.
The gate names three behaviours and they are met. The build order names seven steps: three
built, two partial, two absent. Step 5 (the control agent) does not exist; step 4 (focus) is
three lines of code with no test. Neither is in the gate. `HARNESS.md` was scrupulous about
this distinction; `docs/VERIFY.md` was not, and its top-line Result still declared the handoff
clause *unbuilt* 310 lines above §10 reporting it built and passing.

---

## 2. Six defects, fixed

Ranked as the audit ranked them. All in `healbot.tsx` unless noted.

**1. A hard-errored session rendered GREEN `done`.** The one that matters most, because the
product actively lied. Every v1 error path ends `status.set(idle)` (`processor.ts:611` for the
context overflow this project's whole retirement threshold exists to prevent, `:623` for
everything else); `status.ts:41` publishes that idle *before* `:44` deletes the key;
`sync.tsx:310` stores it; `stateOf` had six outcomes and no error branch, so it returned `done`
→ `theme.success`. Expired credential, crashed tool, aborted run, filled window — all green.
Fixed with an `errored` state fed from `session.error` and cleared on the next busy (idiom from
`notifications.ts:59-65`), ranked directly under the blocked states, carrying the reason on the
cell and a `N failed` count in the header. `retry` split out of `busy` at the same time, which
is the other half of `PLAN.md:369`'s border row.

**2. `reload()` turned any list failure into an uncaught `TypeError`.** The SDK resolves rather
than rejects (no `throwOnError`, `sdk.tsx:25-31`), so `(result?.data ?? result ?? [])` fell
through to the error envelope and `[...envelope]` threw — on the one path the fallback existed
to protect. Four `void reload()` call sites, no handler, and under Bun an unhandled rejection
exits the process: a control terminal that dies when the server it is watching hiccups. Now an
`Array.isArray` guard plus try/catch that keeps the previous roster and puts the failure in the
footer where `r` retries it.

**3. `retire()` archived the source on unverified success.** Neither `session.create`,
`promptAsync` nor either `session.update` had its `.error` read, so a 4xx anywhere left the
predecessor archived, the successor unseeded and the footer reporting `handed off N open items`.
Every call now goes through `ok()`, and the ordering is inverted: the seed is confirmed *before*
the source is retired. Failing that way round is recoverable — an unarchived predecessor still
has a cell.

**4. The handoff's "Original instruction" was the first user message of the last 100.**
`sync.data.message` holds the newest 100 (`sync.tsx:597, :618-619, :334-336`), so on any longer
session the document labelled an arbitrary mid-conversation turn as the founding intent — and
told the successor to treat it as such. Retirement targets long sessions, so the bug lived
exactly where the feature is meant to fire; the §10 run could not see it because it ran at
`HEALBOT_RETIRE_AT=20000` on an 8-message session. Now fetched from the server:
`GET /session/{id}/message` **without** a `limit` returns the whole history oldest-first
(`handlers/session.ts:119-121` → `session.ts:837-852`), where `[0]` really is message one.

**5. Retiring a busy session orphaned it.** Archiving is a bare DB patch
(`session.ts:759-761`) and aborts nothing, while the grid deliberately renders `RETIRE ·
working` — so `x` there left the predecessor editing the same directory as its successor, with
no cell anywhere and possibly parked forever on a permission (`permission/index.ts:96-105` has
no timeout). `retire()` now aborts first, unconditionally and idempotently.

**6. A stale cursor left the grid inert.** `selected` lives in the plugin closure so it survives
navigation, which means it also survives sessions vanishing under it. `reload()` now clamps.

Plus one in the harness: `env.sh` documented "set `HARNESS_ROOT` yourself before sourcing" and
then overwrote it unconditionally on the next line. Now `${HARNESS_ROOT:-…}`.

**Gates.** `tsgo --noEmit -p packages/tui/tsconfig.json` → exit 0, zero output. `oxlint` on
`healbot.tsx` → exit 0, **3 warnings**, down from the committed baseline of 4.

---

## 3. The rig, made able to fail

**Re-runnable at all.** Every `verify_*.py` hardcoded an absolute scratchpad path belonging to
the session that wrote it; those directories no longer exist, and nothing generated the fixtures
they prompt against. For a project whose only mechanism for proving anything is this rig, that
is a defect in the evidence. Everything now derives from `__file__`, and `rig.fixtures()`
generates the payload files and the 130 KB ledgers.

**A screen predicate that discriminates.** `on_grid(t)` matches `Healbot\s+\d+\s+sessions?` —
the grid's own header, case-sensitively — replacing `t.find("Healbot")` at all nine sites.
`probe_on_grid.py` proves it in both directions with **no model turn**: false on home, true on
the grid, false again after `q`, and it prints the old predicate returning `True` on the home
screen so the collision is on the record rather than merely argued. **4/4.** Every rig that
asserts `on_grid` now also asserts `not on_grid` somewhere it must be false.

**Continuity legs that can fail.** Leg 1 asserts a sentinel (`ORCHID-7742`) that appears in the
predecessor's first message and nowhere else, scoped to the document's *objective section*. Leg
3 asserts against the *file section* rather than the whole document. Both are followed by
**mutation checks** that re-run the predicate on a document with that material stripped and
require it to fail. The constant-`True` check is deleted; the real occupancy comparison two
lines below it always did that job.

**Roster ordering, fixed at the source instead of compensated for.** Session ids are descending
identifiers, so ascending sort is already newest-first; the grid sorted `b.localeCompare(a)`
under a comment claiming that gave newest-first, and rendered oldest-first. The rigs compensated
by creating the interesting session last. Both are corrected together — the grid sorts ascending
and the rigs create it first — because a fix on one side alone would have made three navigation
assertions pass for the wrong reason.

---

## 4. The fleet — `serve` + `attach`

`HARNESS.md` recorded this as **blocked**, on the reasoning: `--port` is "port to listen on"
(`cli/network.ts:9`), so the TUI always hosts its own server, so no client can meet a block that
predates it, so the cold-start reconcile is unreachable and two shipped defect fixes sit on a
dead path.

**The premise is true. The conclusion was false, and had been for three phases.**
`opencode attach <url>` is a registered, unhidden command (`cli/cmd/attach.ts:7-16`,
`index.ts:84`) whose non-`--mini` branch calls the same `run()` from `cli/tui/layer` with the
same `createLegacyTuiPluginHost()` as `cli/cmd/tui.ts:271-296` — the full TUI, Healbot builtin
included. `PLAN.md`'s own errata had said as much in passing and nothing followed it up. Nobody
checked the rest of the command surface; the cost was an architecture step written off as
impossible.

`harness/fleet.sh` ships it: reuse-or-start a server, attach a control terminal, and leave the
server running when the terminal closes.

### `verify_cold.py` — 21/21, the reconcile finally exercised

The ordering is the whole test: start a headless server, raise a permission with **nothing
rendering**, wait until it exists, and only then start the client. At that point the live SSE
store cannot know about the block — it is populated only by events seen in-process — so if the
cell renders `PERMISSION`, `reconcile()` is the only thing that can have put it there.

| | |
|---|---|
| block raised before any client existed | **37 s** |
| grid on first paint | `PERMISSION`, `1 blocked` |
| panel mounted from the reconciled request | carried the real `Patterns / - /etc/*` |
| reply → block cleared → answer reached the model | `/bin/zsh` in the transcript, `gpt-5.6-sol` |
| server after the client exits | still serving, session intact |

That panel line upgrades **"the reconcile carries full request bodies, not just ids"** from
INFERRED (`VERIFY.md:198-200`) to TESTED. Colouring a border needs an id; mounting a prompt
needs the request.

### `probe_fleet.py` — 10/10, the script an operator actually runs

`verify_cold.py` proves the architecture; this proves the deliverable. It found a real defect:
**the server died with the terminal.** A plain `&` background job is HUP'd by the shell on exit
and shares the terminal's stdin — so closing the control terminal took the whole fleet down,
which is the precise failure the fleet exists to prevent. `nohup … </dev/null & disown` fixes
it, and reuse is now asserted on **pid identity** rather than on a message the TUI scrolls away.

### The trap that cost a run

The first attempt failed with the grid reporting `0 sessions` while every API call succeeded and
`GET /session` returned the session. `workspace-routing.ts:87` resolves an instance as
`?directory || x-opencode-directory || process.cwd()`; the rig sent no header, so it addressed
the *server's* cwd — which `bun run --cwd` had set to `packages/opencode`, not the project —
while the client asked for `--dir <project>`. Two different instances, both answering happily.
`Api` now sends the header like a real client (`sdk/js/src/client.ts:49`).

---

## 5. What this changes elsewhere

Per the process rule from `docs/REVIEW.md` — every phase revises the artifacts it contradicts:

- **`PLAN.md`** — all 14 ERRATA citations were off by exactly **+31**, because inserting the
  errata block shifted the body it cites and nothing re-derived them. Re-derived, verified row
  by row, and pinned with a note. Three rows added: the forbidden `AGENTS.md`/`SKILL.md`
  filenames §3 still prescribes, the unbuilt control agent and untested focus, and the fleet.
- **`docs/VERIFY.md`** — the Result block now reads 128/129 and reports both gate clauses met,
  with §10's caveat attached; §6's four "not established" items are struck through with their
  outcomes.
- **`HARNESS.md`** — the attach trap is marked REFUTED, the cold-reconcile row moves out of
  *Still open*, the `session.list` row is corrected to say it is about *projects* and not
  directories, three new traps are added (the directory header, the dying background job, and
  the error state), and the stale byte counts are removed rather than re-stated.
- **`fork/README.md`** — same, plus the later commits it never recorded.

**Deliberately not quoting sizes any more.** `fork/README.md` said "24.1 KB, 566 lines" and
`HARNESS.md` said "12.8 KB" for one file that was 878 lines at the time. The audit's diagnostic
is worth keeping: citations into **upstream** opencode held at 59/64, every miss off by one
line; citations into this project's **own** moving files were 0/17 and 0/4. Only the former has
a stable target, so the latter should be section names, quoted text, or a command you can run —
not numbers.

---

## 6. Retirement at the shipped 350,000 default — 25/25, and it changed a load-bearing number

Every retirement result before this ran at `HEALBOT_RETIRE_AT=20000` against an eight-message
session. This is the shipped default firing for the first time, with `HEALBOT_RETIRE_AT`
asserted absent from the environment so the threshold under test is the code's own.

The run puts two conditions in one session deliberately: **occupancy ≥ 350,000**, so `RETIRE`
fires at the real default, and **>100 messages**, so the store has evicted message one and the
handoff objective can only be right if it came from the server.

| | |
|---|---|
| occupancy at retirement | **359,829** after 104 messages, 259 s of growth |
| `?limit=100` window (what `sync.tsx:597` hydrates) | no longer held the original instruction |
| unlimited fetch | still did |
| cell / header at the default | over-threshold state rendered, `1 to retire` |
| handoff objective | carried the sentinel from the **true first message** |
| open todos into the successor's own list | **2/2** |
| changed file handed over | `- findings.txt`, created on **turn 1** |
| occupancy after | 359,829 → **7,666 (2%)** |

`findings.txt` is the one that proves the diff fan-out change: created on turn one of a
104-message session, it sits outside the store's 100-message window and far outside the old
last-20-user-message slice, so only a head-and-tail fan-out over the server's full history
finds it.

### The ceiling is ~360K, not 922,000

The run kept prompting after it crossed the threshold, to reach the message count. It should
not have been able to: **37 turns succeeded and then 25 consecutive turns failed** with the
provider's `ContextOverflowError` — *"Your input exceeds the context window of this model."*

`HARNESS.md` had recorded, and this file's own `RETIRE_AT` comment had repeated, that
`gpt-5.6-sol` offers 922,000 `limit.input` and that "a 350K threshold leaves ~570K of headroom".
**Measured, the margin is ~10K — under 3%.** One large tool result is ~10K, so a single read can
carry a session from "should be retired" to "cannot run another turn". `compaction.auto:false`
disables opencode's own overflow check (`overflow.ts:28`), so nothing catches it before the
provider does. The threshold exists to fire *before* the hard error, and at 350K it does not.

Consequence, and it is a decision rather than a measurement: **the default should probably come
down to 200–250K.** It is left at 350,000 because that number is the project owner's to choose.

> **Superseded — 350,000 is not the shipped default and has not been since later in this same
> phase.** This paragraph is left standing because it records the moment the decision was still
> open, but read as a statement about the product it is now false: the owner took the decision
> inside Phase 5 and the default is **256,000** (§7 sets it, §8 lists it, `healbot.ts:110` and
> `healbot.tsx:53` both carry it). Nothing else in this section changes — the ~360K ceiling and
> the 359,829 measurement are what forced the number down, and they still hold.

A second consequence: at this default a session cannot reach both ≥350K occupancy and >100
messages without failing turns on the way, so the rig's over-threshold assertion accepts either
`RETIRE` or `ERROR` and leans on the occupancy-derived header count, which does not depend on
state precedence.

### And it caught a hole in the error state

The grid rendered that session — dead for 25 turns — as `RETIRE`, not `ERROR`. The error state
built earlier in this phase subscribes to `session.error` **inside the route component**, so it
only ever knew about failures that happened while the grid was open. Every one of those 25
failures predated the operator opening it.

That is the same cold-start hole `reconcile()` exists to plug for permissions, and the fix is
the same shape: derive the state from stored messages (`storedErrorOf`) rather than from having
witnessed the event. Scanning backwards for the most recent assistant message also gives
clear-on-recovery for free. `probe_error_state.py` proves it by replaying the real overflow
session out of the run's own database — **10/10, and free**, because the expensive part
(producing a genuine overflow) was already paid for.

### Three test defects this run exposed, all mine

- **The prompt was too easy to satisfy.** "Reply with the final ACCT number" let the model read
  with an offset near the end — 1,386 chars instead of 25,000, occupancy growing a flat 816
  tokens per turn. If the point of a turn is to put bytes *into* the window, the prompt must not
  leave room to be efficient about it. The tool parameters are now dictated.
- **Successor detection grabbed a subagent.** "Any new non-archived session" matched the
  successor's own `@general` subagent; `retire()` had worked perfectly and the rig graded a
  440-char model-written task prompt as the handoff document. Now matched on `parentID == null`
  **and** the seed text. Note the irony: session ids are descending, so the newest sorts first —
  the same ordering fact the grid was fixed for, tripping the rig.
- **An empty file list I misdiagnosed.** I attributed it to the fan-out window and was wrong:
  the rig's project directory is inside this repo and gitignored by `.gitignore`'s
  `.carryover/verified/hb/`, and `SessionSummary.summarize` computes diffs with git — so no file
  there could ever produce one. `rig.git_baseline()` now gives the project its own inner repo.
  The fan-out change is still right, but it had not fixed what I said it fixed.

---

## 7. Two gates, and automatic retirement — 13/13

The 350K run's 25 dying turns were not a rig artifact. Nothing in the code stopped them: the
threshold was **advisory**, because a previous pass made retirement operator-initiated (`x`)
against `PLAN.md:381`'s automatic design, reasoning that the grid should never act on its own.
That reasoning is sound in isolation and wrong in context — an advisory threshold cannot do the
one job it has, and the ceiling below it is a cliff rather than a slope.

The lifecycle now implemented, in the owner's words: **the gate is met, the agent finishes what
it is doing, a handoff goes to a fresh session, the old session is retired, and the successor
picks the work up immediately — with no turn consumption after the gate.**

`verify_auto_retire.py`, **13/13**, at a low threshold because the path is threshold-independent:

| | |
|---|---|
| retired itself | `x` never pressed |
| the turn was allowed to finish | `tool-calls` ×5 then **`stop`**, no error |
| turns accepted after the gate | **1 user turn total** — nothing new was taken |
| successor | seeded, ran unprompted, **2/2** open todos in its own list |
| chaining | none — the successor starts near the ~5K floor |

### Why one gate is not enough

The same run measured the cost of "let it finish", and it is much larger than it looks:

| step | occupancy |
|---|---|
| 3 | 5,216 |
| 4 — one tool result | **70,898** |
| 6 — `stop` | **175,090** |

> **The data is right; the reasoning built on it was not.** Note the column header: this is
> **per-STEP** occupancy, and it was read as though it were per-turn. Phase 7 measured that the
> *shipped* gate is evaluated at every step boundary rather than at the end of a turn (see the
> note below §7's two-gate paragraph), so the row that matters for sizing it is the step-to-step
> delta — **5,216 → 70,898 is ~65K of single-step growth** —
> not the 5,216 → 175,090 span of the whole turn. That is the measurement which, read correctly,
> shows the per-step gate has adequate margin: crossing at 256,000 exposes one more step, ~65K,
> and lands near 321,000, inside the ~360K ceiling. See `HARNESS.md`, "The gate fires at a STEP
> boundary".

**One turn added ~170K.** Apply that to a 256,000 soft gate: a session sitting just under it
that starts one more read-heavy turn finishes near **426,000** — past the ~360K ceiling, dead,
having obeyed the finish-first rule the whole way. The soft gate alone cannot prevent the
failure it exists to prevent.

So there are two. `RETIRE_AT` (**256,000**) is soft: cross it and the turn in flight completes,
then the handoff runs. `RETIRE_HARD` (**330,000**) is hard: cross it *during* a turn and the
session is retired immediately, aborting it. That abort is not weighed against finishing — it is
weighed against `ContextOverflowError`, which discards the same work, spends the tokens first,
and produces no handoff.

> **Still a true record of Phase 5, and no longer a description of the shipped harness. There is
> one live gate now, not two, and it aborts.** Nothing above is retracted: the grid's
> `createEffect` really did wait for the turn, because it gated on the **session's** status
> (`status?.type === "busy" || "retry"`), which stays busy for the whole turn. Finish-first was
> implemented and TESTED as written.
>
> What changed it was Phase 6, silently. Moving retirement into the server plugin replaced that
> session-status check with a check on the **message** — and `processor.ts:443-445` writes
> `finish` and `tokens` in one mutation at every `step-finish`, with `:445` the only site in the
> session tree writing a non-zero `tokens`. So every event carrying occupancy also carries a set
> `finish`, usually `"tool-calls"`. MEASURED in Phase 7 on 733 real assistant messages with
> occupancy > 0: **zero** had a null `finish`. The gate now fires at the first STEP boundary past
> `RETIRE_AT` and aborts the turn in flight, and `RETIRE_HARD` is **inert** — its only consumer is
> dominated by a condition true on 733/733, and no rig has executed the branch.
>
> The outcome is better than the design, not worse, and it was arrived at by accident: exposure is
> one step (~65K) rather than one turn (~170K). The hard-gate constant is kept in the code and
> documented as dead, because the hinge is a single function — swap the plugin's `stepFinished()`
> for opencode's own per-turn predicate and both the finish-first semantics above and this hard
> gate come back the same day. `HARNESS.md` carries the load-bearing facts.

`HEALBOT_AUTO_RETIRE=0` restores the operator-initiated behaviour.

### A limitation to know about

The trigger is a `createEffect` **inside the route component**, so auto-retirement only runs
while the grid is open. Under `harness/fleet.sh` that is the normal operating state — the
control terminal is the thing you leave running — but it is not headless, and a fleet left
running with no client attached will not retire anything. Moving the trigger to plugin scope
(driven off `message.updated`, which carries the tokens) would fix it and is the natural next
step. It is listed in *Still open*.

### Correcting the premise this started from

The question that prompted the change was whether original context is *lost* at 350K. **It is
not, and the distinction matters for choosing a number.** There is no history truncation on the
v1 prompt path, `compaction.auto:false` disables compaction, and `compaction.prune` is unset so
`compaction.ts:245` returns early — opencode sends the **entire** history every turn until the
provider refuses it. Nothing degrades; the session works perfectly and then hits a wall. The
case for lowering the threshold is not context loss, it is that **~360K is a cliff and 350K left
~10K of margin**.

What *was* being lost is a different thing entirely: the **TUI store's** 100-message window,
which is client-side and is what corrupted the handoff document. That is fixed by reading from
the server (§2, §6), not by the threshold.

---

## 8. Still open after Phase 5

Unchanged and honest, in `HARNESS.md`'s *Still open* table: the control agent (build-order step
5) is not built; focus has never been tested; the `question.rejected` half of the cold reconcile
is source-reading only; external plugin route registration is untested; and **Phase 3's exit
gate is still unmet** — the `/code-review ultra` pass on the `harness/` diff is user-triggered
and cannot be launched from an agent session.

Added by this phase:

- **Auto-retirement is not headless.** The trigger lives in the route component, so it only runs
  while the grid is open (§7). Moving it to plugin scope off `message.updated` is the fix.
- **The soft gate is workload-dependent.** 256,000 is right if turns add ~50K; a turn that adds
  ~170K needs the hard gate to catch it. If `RETIRE_HARD` fires routinely for a given workload,
  the soft gate is too high for that workload rather than the hard gate being too low.
  > **Corrected in Phase 7.** The dependence is real but the unit is wrong, and so is the
  > remedy. The gate fires per STEP, so what has to fit in the margin is one **step**, not one
  > turn — ~65K measured, against ~104K of headroom below the ~360K ceiling. `RETIRE_HARD` can
  > never catch anything; it is inert. Re-tune 256,000 only if a single step is ever measured
  > above ~100K. `HARNESS.md`.
- **The 256K gate has not been exercised end to end at its real value.** Automatic retirement is
  TESTED at 20,000 and the threshold comparison is a single `>=`, so the risk is low — but the
  full-scale run at 256,000 has not been paid for.
