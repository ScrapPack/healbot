# SESSION.MAP.md — `packages/core/src/session` (v2 core session tree)

Repo `healbot/opencode` @ `0fdcfb6`, branch `healbot`, v1.18.5. Every `file:line` below was opened
and read while writing this map. Tier: **V** = read the code · **I** = inferred, link stated · **O** = open.

> **Provenance — RETRACTED.** This block previously asserted that `docs/SCAN.md` and
> `docs/PROBE.md` "are not in this repo and never were… never committed", and stamped
> **UNVERIFIED** on every SCAN-attributed figure. **That is false.** Both are committed in the
> *other* repo: `git log --stat` in `~/Desktop/healbot` shows `docs/SCAN.md` added by `6f74f2b`
> and `docs/PROBE.md` by `8f34a84`. The `git log --all` search came back empty only because
> `~/Desktop/healbot/.gitignore` excludes `/opencode/`, so this fork cannot see that history.
> Read them at `~/Desktop/healbot/docs/`. They are followable citations.
>
> Treat SCAN's *numbers* with care for a real and different reason: they were measured under
> `anthropic.txt` with cwd inside this fork, so they do not describe the shipped harness. The
> audit is at `~/Desktop/healbot/docs/REVIEW.md`.

> **Path convention.** A citation prefixed `packages/…` is repo-relative. A **bare path** resolves
> against, in order: (1) this file's own directory, (2) the owning package's `src/`, (3) the repo
> root — all three are in use here. A bare **`:NNN`** is a line in the file named by the enclosing
> section heading or table row.

---

## 1. File table

| File | LOC | Owns | Key symbols |
|---|---|---|---|
| `projector.ts` | 458 | **Event → SQL projection. The only *incremental* writer of `session.tokens_*`** (see §2.6 for the one other writer) | `applyUsage` :90 · `usage` :36 · `sessionRow` :44 · `node` :458 |
| `runner/llm.ts` | 432 | The v2 execution turn loop. Builds the LLM request, streams it, settles tools, drives compaction. | `runTurnAttempt` :173 · `runTurn` :369 · `run` :383 · `node` :414 |
| `runner/publish-llm-event.ts` | 423 | Translates `LLMEvent` → durable `SessionEvent.*`. Captures per-step usage. | `createLLMEventPublisher` :54 · `tokens()` :18 · `stepSettlement` :396 |
| `message-updater.ts` | 397 | Applies each v2 `SessionEvent` to the projected message row. Pure over an `Adapter`. | `update` :78 · `Adapter` :10 · `memory` :19 |
| `input.ts` | 288 | Durable prompt queue: admit → promote (steer/queue). | `admit` :41 · `hasPending` :170 · `promoteSteers` :245 · `promoteNextQueued` :268 |
| `compaction.ts` | 241 | **v2 compactor.** Threshold math, summary prompt, `Compaction.Started/Ended`. | `make` :170 · `settings` :114 · `select` :128 · `buildPrompt` :161 |
| `runner/model.ts` | 218 | Resolves `session.model` → a concrete `@opencode-ai/llm` route. | `ModelNotSelectedError` :18 · `ModelUnavailableError` :29 · `node` :218 |
| `sql.ts` | 176 | Drizzle table definitions. | `SessionTable` :22 · `MessageTable` :68 · `PartTable` :82 · `SessionMessageTable` :119 · `SessionInputTable` :140 · `SessionContextEpochTable` :168 |
| `context-epoch.ts` | 174 | System-prompt baseline + `baseline_seq` cut point; reset on move/revert. | `initialize` :23 · `prepare` :31 · `reset` :111 |
| `runner/to-llm-message.ts` | 171 | v2 `SessionMessage` → canonical LLM messages. | `toLLMMessages` :170 |
| `revert.ts` | 121 | Stage/clear/commit revert boundaries. | `stage` :60 · `clear` :98 · `commit` :113 |
| `run-coordinator.ts` | 104 | One active drain per key; wake coalescing; interrupt. | `make` :25 |
| `history.ts` | 101 | **Post-compaction tail queries.** All context reads funnel here. | `load` :66 · `entriesForRunner` :90 · `loadForRunner` :82 · `latestCompaction` :13 · `messageRows` :24 |
| `todo.ts` | 78 | Todo list per session. | `Service` :24 · `node` :78 |
| `store.ts` | 63 | Read façade over the tables. | `get` :34 · `context` :38 · `runnerContext` :42 · `message` :45 · `node` :63 |
| `info.ts` | 50 | `SessionTable` row → `SessionSchema.Info`. **Read side of the token counters.** | `fromRow` :14 |
| `execution/local.ts` | 46 | In-process binding of `SessionExecution` → `SessionRunner`. | `node` :40 |
| `execution.ts` | 34 | `SessionExecution` interface (`active`/`resume`/`wake`/`interrupt`) + `noopLayer`. | `Service` :22 · `node` :23 · `noopLayer` :26 |
| `runner/index.ts` | 28 | `SessionRunner` service tag + `RunError` union. | `Service` :28 · `RunError` :11 |
| `error.ts` | 24 | `MessageDecodeError` :5 · `ContextSnapshotDecodeError` :15 | — |
| `runner/max-steps.ts` | 16 | `MAX_STEPS_PROMPT` string injected on the final step. | :1 |
| `schema.ts` | 9 | Re-export of `@opencode-ai/schema/session`. | `ID`, `Info` |
| `message.ts` | 2 | Re-export of `@opencode-ai/schema/session-message`. | — |
| `event.ts` | 2 | Re-export of `@opencode-ai/schema/session-event`. | — |
| `prompt.ts` | 1 | Re-export of `@opencode-ai/schema/prompt`. | — |

Sibling that owns session CRUD (not in this dir): `packages/core/src/session.ts` — `create` :242, `prompt` :360,
`context` :342, `compact` :417, `resume` :426, `interrupt` :431.

---

## 2. TOKEN ACCOUNTING — basis of the 350K retirement trigger

### 2.1 Storage

`SessionTable` columns, `sql.ts:43-47` — five `integer().notNull().default(0)` counters plus `cost real() :42`:

```
tokens_input · tokens_output · tokens_reasoning · tokens_cache_read · tokens_cache_write
```

### 2.2 The single write path

| Step | Site | What |
|---|---|---|
| accumulator | **`projector.ts:96-109`** | `db.update(SessionTable).set({ ... })`, `where(eq(SessionTable.id, sessionID))` |
| the `+=` for input | **`projector.ts:100`** | `` tokens_input: sql`${SessionTable.tokens_input} + ${value.tokens.input * sign}` `` |
| same shape, other four | `projector.ts:101-104` | output / reasoning / cache.read / cache.write |
| `time_updated` pinned | `projector.ts:105` | `` sql`${SessionTable.time_updated}` `` — an accumulate does **not** bump `time_updated` |
| usage extractor | **`projector.ts:36-42`** | returns `undefined` unless `value.type === "step-finish"` (guard at **`:39`**) and both `cost` and `tokens` present (`:40`) |
| streaming re-update | **`projector.ts:325-328`** | reads the pre-existing `PartTable` row (`:318`), then `if (previous) applyUsage(..., -1)` (**`:327`**) then `if (next) applyUsage(..., +1)` (**`:328`**) — subtract-then-add, so re-emitted `step-finish` parts do not double-count |

`applyUsage` has exactly **four** call sites, all in this file: `:286`, `:304`, `:327`, `:328`
(verified by `grep -rn applyUsage packages --include=*.ts`). There is no other writer anywhere.

### 2.3 The four `applyUsage` triggers

| Projection | Line | Sign | Effect on the counter |
|---|---|---|---|
| `SessionV1.Event.PartUpdated` | `:312-329` | −1 then +1 | replaces the prior contribution of that part |
| `SessionV1.Event.PartRemoved` | `:295-311` | −1 | **decrements** |
| `SessionV1.Event.MessageRemoved` | `:276-294` | −1 per part | **decrements** |

All three are **v1** event types.

### 2.4 ⚠️ Which engine actually feeds the counters — read this before trusting `session.tokens`

**V.** The only publisher of `SessionV1.Event.PartUpdated` in the entire repo is the **legacy v1 engine**:
`packages/opencode/src/session/session.ts:637-645` (`updatePart`). `MessageRemoved` / `PartRemoved` likewise:
`session.ts:859` / `:871`. `EventV2Bridge` (`packages/opencode/src/event-v2-bridge.ts`) is a
location-annotating pass-through — it does **not** translate v2 events into v1 ones.

**The v2 runner records usage somewhere else entirely:**

| Step | Site |
|---|---|
| provider usage captured | `runner/publish-llm-event.ts:396-400` → `stepSettlement = { finish, tokens: tokens(event.usage) }` |
| usage shape built | `runner/publish-llm-event.ts:18-27` → `{ input, output, reasoning, cache: { read, write } }` |
| published | `runner/llm.ts:325-336` → `SessionEvent.Step.Ended` with `tokens: stepSettlement.tokens` and **`cost: 0` hard-coded (`:331`)** |
| projected | `projector.ts:382` → `run(db, event)` → `message-updater.ts:208-221` → `draft.tokens = event.data.tokens` on the **assistant row in `SessionMessageTable`** |

That path never calls `applyUsage`. **Consequence: a session driven only through
`POST /api/session/{id}/prompt` accumulates usage on its assistant message rows but leaves
`SessionTable.tokens_*` at 0 forever — `GET /session/{id}` and `GET /api/session/{id}` both report
`{0,0,0,0,0}` for it.** Tier: **V** on every write path read (exhaustive grep on both `applyUsage`
call sites and `PartUpdated` publishers); **not TESTED at runtime**. SCAN.md §2's TESTED numbers came
from a TUI-driven session, i.e. the v1 engine — consistent, but not evidence about the v2 path.

**Action for the control terminal:** either drive sessions through the v1 `/session/*` family, or sum
`SessionMessageTable.data.tokens` over `type='assistant'` rows instead of reading `session.tokens`.
Settling this by running one v2 prompt and re-reading the row is ~5 minutes and is the highest-value
open check in this tree.

### 2.5 Read side — both API families read the same columns

| Family | Site |
|---|---|
| v2 `/api/session/*` | `info.ts:28-36` (`cost` :28, `tokens` :29-37) via `fromRow` :14 |
| v1 `/session/*` | `packages/opencode/src/session/session.ts:97-105` |

Identical column set ⇒ identical number. (SCAN.md cited `info.ts:29-37` and `session.ts:97-106`;
corrected to `:28-36` / `:97-105`.)

### 2.6 Cumulative and monotonic — with two exceptions

**Cumulative — with one exception.** Every write on the *live* path is `column + delta`, never
`column = value` (`projector.ts:99-104`).

The exception is the **import CLI**: `Session.toRow()`
(`packages/opencode/src/session/session.ts:120-158`, tokens at `:140-144`) emits literal
`tokens_* = <value>`, and its **sole** caller `packages/opencode/src/cli/cmd/import.ts:186-193`
inserts it. Two reasons this does not break the monotonicity conclusion:

1. It runs only on an explicit `opencode import`, never during a session.
2. Its `onConflictDoUpdate` `set` clause (`import.ts:191`) lists **only** `project_id`,
   `directory`, `path` — so re-importing an existing session id **cannot overwrite counters**.
   The literal write lands only on a first insert, seeding an imported session's totals.

`toRow` is also the v1 writer of `time_compacting` (`:156`) — see
`packages/opencode/src/session/SESSION.MAP.md` gotcha 11.

**Never reset by compaction — V.** Neither compactor removes messages or parts. The v2 compactor
publishes only `Compaction.Started` (`compaction.ts:186-191`) and `Compaction.Ended`
(`compaction.ts:215-222`); `message-updater.ts:377-389` handles `session.next.compaction.ended` by
**appending** a `type: "compaction"` row. History exclusion is a *query filter*, not a delete
(§4). No `applyUsage` on any compaction path.

**Non-monotonic edge cases (2):**

| Path | Site | Note |
|---|---|---|
| `PartRemoved` / `MessageRemoved` | `projector.ts:295-311`, `:276-294` | decrement. Published only by the v1 engine at `packages/opencode/src/session/session.ts:859,871` |
| v2 `RevertEvent.Committed` | `projector.ts:415-454` | deletes `SessionMessageTable` + `SessionInputTable` rows above the boundary — **does not** call `applyUsage`, so counters survive a v2 revert intact |

Treat as monotonic **unless** the v1 revert/remove path is exercised.

### 2.7 Which fields to threshold

`cache.read` re-counts the entire cached prefix on every turn — it is not context occupancy.
**Sum `input + output + reasoning`; exclude `cache.read` (and `cache.write`).** SCAN.md §2's measured
consequence stands: including `cache.read` retires at ~17% of a session's useful life.

---

## 3. Compaction — `compaction.ts`

### 3.1 Config, not env var

| Concern | Site |
|---|---|
| settings resolver | **`compaction.ts:114-126`** — filters `Config.Entry` to `type === "document"` (`:116`), reduces `entry.info.compaction` over defaults |
| defaults | `{ auto: true, buffer: 20_000, tokens: 8_000 }` — `compaction.ts:124`; constants at `:12-13` |
| the `auto` gate | **`compaction.ts:226`** — `if (!config.auto) return false` |

`compaction.auto` comes from config **documents** on disk. `OPENCODE_DISABLE_AUTOCOMPACT` is consumed
in exactly one place — `packages/opencode/src/config/config.ts:579` — and governs the **legacy**
compactor only; it never reaches `settings()`. **The lever that covers both engines is the config
file: `"compaction": { "auto": false }`.**

⚠️ **Snapshot at construction, not per-request.** `runner/llm.ts:109`:

```ts
const compaction = SessionCompaction.make({ events, llm, config: yield* config.entries() })
```

`config.entries()` is read once when the runner layer is built, so `settings()` runs once. Editing
`compaction.auto` mid-process does not take effect until the runner layer is rebuilt. **V.**

### 3.2 Trigger math

`compactIfNeeded` — `compaction.ts:225-236`:

```
context = model.route.defaults.limits.context              # :227, bail if undefined or <= 0 (:228)
output  = request.generation.maxTokens ?? limits.output ?? 0   # :229
fire when:  estimate({system, messages, tools}) > context - max(output, config.buffer)   # :230-234
```

`estimate` = `Token.estimate(JSON.stringify(value))` (`compaction.ts:74`), and
`Token.estimate = round(len / 4)` (`packages/core/src/util/token.ts:5`). **Character-count heuristic,
not a tokenizer.**

### 3.3 `compactAfterOverflow` — `compaction.ts:172-224`

The overflow-recovery variant. **Does not check `config.auto`** — it is passed explicitly by
`runTurn` (`runner/llm.ts:370`) and withheld by `runAfterOverflowCompaction` (`:356`) so one
post-compaction attempt cannot recurse.

| Stage | Line |
|---|---|
| split history into `head` (summarize) / `recent` (keep verbatim) | `select` :128-159, budget = `config.tokens` (8K) |
| prior summary picked up | `:177` (`entry.message.type === "compaction"`) |
| prompt assembled | `buildPrompt` :161-168 + `SUMMARY_TEMPLATE` :16-46 |
| refuse if the summary prompt itself overflows | `:184` |
| publish start | `:186-191` (`reason: "auto"`) |
| one LLM call, tools `[]`, `maxTokens ≤ 4096` | `:195-212`, cap const `:15` |
| bail on empty/failed summary | `:214` |
| publish end with `text` + `recent` | `:215-222` |

### 3.4 There is no manual v2 compact

`packages/core/src/session.ts:417-420` — `V2Session.compact` unconditionally returns
`OperationUnavailableError`. So `POST /api/session/{id}/compact` always fails; v2 compaction is
auto-only, fired from inside `runTurnAttempt`. Same for `shell` (:386), `skill` (:389), `wait` (:421).

### 3.5 Where the *other* compactor lives

SCAN.md §5 (`compaction.ts:328`) and §6 (`compaction.ts:508`) cite **`packages/opencode/src/session/compaction.ts`**
(562 LOC — the legacy compactor), **not** this file (241 LOC). Confirmed: `agents.get("compaction")`
is at `packages/opencode/src/session/compaction.ts:328`. The v2 compactor here uses **no agent** —
it builds its own prompt and calls `llm.stream` directly.

---

## 4. `history.ts` / `store.ts` — why `GET /api/session/{id}/context` is a tail, not a history

Chain, end to end (**V**):

| # | Site | What |
|---|---|---|
| 1 | `packages/protocol/src/groups/session.ts:292` | route `GET /api/session/:sessionID/context` |
| 2 | `packages/server/src/handlers/session.ts:305-308` | handler → `session.context(sessionID)` |
| 3 | `packages/core/src/session.ts:342` | `V2Session.context` |
| 4 | `store.ts:38-40` | `SessionStore.context` → `SessionHistory.load` |
| 5 | `history.ts:66-80` | `load` — resolves epoch baseline (`:69-74`) and `latestCompaction` (`:75`) concurrently |
| 6 | `history.ts:13-22` | `latestCompaction` = max `seq` where `type = 'compaction'` |
| 7 | **`history.ts:36-42`** | **the cut:** `` compaction ? or(gte(seq, compaction.seq), <system rows above baseline>) : undefined `` |
| 8 | `history.ts:44-46` | second filter drops `system` rows at or below `baseline_seq` |

**Rows below the latest compaction marker are still in `session_message`; they are simply excluded by
the `WHERE`.** Hence: summing tokens from `/context` under-reports after any compaction, while
`SessionTable.tokens_*` (§2) does not — the two disagree by construction, and that is intended.

Two variants:

| Fn | Site | Difference |
|---|---|---|
| `load` | `history.ts:66` | epoch baseline looked up from the DB. Used by `/context`. |
| `entriesForRunner` / `loadForRunner` | `history.ts:90` / `:82` | caller passes `baselineSeq`; `entriesForRunner` also returns `seq` (the compactor needs it) |

`SessionMessageTable` shape: `sql.ts:119-138` — unique index on `(session_id, seq)` `:132`.

---

## 5. `runner/` — the v2 execution path

Wake-to-turn chain:

```
POST /api/session/:id/prompt
  → packages/server/src/handlers/session.ts:139-170       "session.prompt" handler
  → packages/core/src/session.ts:360-384                   V2Session.prompt
      SessionInput.admit                                   input.ts:41
      execution.wake(sessionID)          if resume !== false   session.ts:382
  → SessionExecution.Service                               execution.ts:21 (unbound tag, :23)
  → execution/local.ts:11-29                               drain → SessionRunner.Service.run
  → run-coordinator.ts:25                                  one active drain per sessionID
  → runner/llm.ts:383-406                                  run()
```

`run` — `runner/llm.ts:383-406`:

| Line | Behavior |
|---|---|
| :387-389 | `hasPending(steer)` else `hasPending(queue)`; return early unless `force` |
| :390 | `failInterruptedTools` (`:119-139`) — closes tools left pending/running by a prior crash |
| :393-405 | outer `queue` loop wrapping an inner `needsContinuation` step loop; `promotion` becomes `"steer"` after the first turn (`:400`) |

`runTurnAttempt` — `runner/llm.ts:173-348`, one provider turn:

| Line | Behavior |
|---|---|
| :180-181 | **location guard** — interrupts if the session moved off this Location |
| :183 | `SessionContextEpoch.initialize` — system-prompt baseline |
| :187-196 | promote steers/queued input; any promotion resets `currentStep = 1` (`:195`) |
| :199-201 | resolve model; load history via `entriesForRunner(baselineSeq)` |
| :202-203 | last-step check → tools withheld entirely (`toolMaterialization = undefined`) |
| :204 | `promptCacheKey` = session id minus the `ses_` prefix |
| :205-214 | build `LLM.request`; `system = [agent.info.system, epoch baseline]` |
| **:215-216** | **`compaction.compactIfNeeded(...)` → on true, `die(continueAfterCompaction)`** |
| :232-275 | stream the turn; each non-provider-executed `tool-call` forks into `toolFibers` (`:271`) |
| :277-347 | settlement: overflow recovery (`:282-288`), interrupt handling, `Step.Ended` publish (`:325-336`) |

Turn transitions are signalled as **defects**, caught by the wrappers:

| Wrapper | Site | Passes `compactAfterOverflow`? |
|---|---|---|
| `runTurn` | `:369-381` | yes (`:370`) |
| `runAfterOverflowCompaction` | `:355-367` | no (`:356`) — a second overflow is fatal (`:361`) |

Layer wiring (`runner/llm.ts:414-432`) is a **Location** node — one runner per directory/workspace.

---

## 6. §1 SETTLED — the v2 tree **does** execute under the `opencode` binary

SCAN.md §1 left this open. **Resolved by reading the wiring. Tier: V (code chain complete,
not runtime-observed).**

| # | Evidence |
|---|---|
| 1 | `packages/opencode/src/server/routes/instance/httpapi/api.ts:79-83` — `OpenCodeHttpApi` mounts `RootHttpApi`, `EventApi`, `InstanceHttpApi` (:82, legacy `/session`) **and** `ServerApi` (:83, v2 `/api/session`) on one API. (SCAN cited `:78-83`; the block starts at `:79`.) |
| 2 | `packages/protocol/src/groups/session.ts:205` — `session.prompt` is bound to `POST /api/session/:sessionID/prompt` |
| 3 | `packages/opencode/src/server/routes/instance/httpapi/server.ts:102` imports `handlers` from `@opencode-ai/server/handlers`; `:177-181` provides it into `serverRoutes`; `:281` includes `serverRoutes` in the served router |
| 4 | `packages/server/src/handlers.ts:24` includes `SessionHandler`; `packages/server/src/handlers/session.ts:19` builds it over `SessionV2.Service` (`:21`) |
| 5 | `packages/server/src/handlers/session.ts:139-149` — the `session.prompt` handler calls `session.prompt({...})` |
| 6 | `packages/core/src/session.ts:382` — `V2Session.prompt` calls `execution.wake(...)` |
| 7 | **`packages/opencode/src/server/routes/instance/httpapi/server.ts:298-302`** — `AppNodeBuilderV1.build(SessionV2.node, [..., [SessionExecution.node, SessionExecutionLocal.node]])` binds the abstract `SessionExecution` tag to the **local** implementation in this process |
| 8 | `execution/local.ts:21-23` — that implementation calls `SessionRunner.Service.use((runner) => runner.run(...))` |
| 9 | `server.ts:236` registers `SessionProjector.node` in the same process |

**Verdict: `POST /api/session/{id}/prompt` on the `opencode` binary drives `packages/core/src/session/runner/`
in-process. The v2 compactor in this directory governs those requests.** `lildax` is not required.

Residual **O**: not runtime-observed. The cheap confirmation is a single prompt against `/api/session`
followed by checking whether `session_message` gained assistant rows — which also settles §2.4.

Corrected split (SCAN.md §1's table):

| | Legacy `/session` | V2 `/api/session` |
|---|---|---|
| Engine | `packages/opencode/src/session/prompt.ts` | `packages/core/src/session/runner/` |
| Both live on the `opencode` binary | yes | **yes** (was "unresolved") |
| Compaction | `packages/opencode/src/session/compaction.ts` (562 LOC, agent-driven) | `packages/core/src/session/compaction.ts` (241 LOC, no agent) |
| Manual compact endpoint | yes | **no** — `packages/core/src/session.ts:417-420` returns `OperationUnavailableError` |
| Writes `SessionTable.tokens_*` | **yes** (`session.ts:637-645` → `projector.ts:328`) | **no** (writes `session_message.data.tokens`) |
| `fork` / `summarize` | yes | no |

---

## 7. Retirement-policy quick reference

| Need | Answer |
|---|---|
| Cumulative counter | `SessionTable.tokens_input/output/reasoning/cache_read/cache_write`, `sql.ts:43-47` |
| Sole writer | `applyUsage`, `projector.ts:90-110`; call sites `:286 :304 :327 :328` |
| Fields to sum | `input + output + reasoning`. **Exclude `cache.read`.** |
| Reset by compaction? | No — `compaction.ts` appends only; exclusion is a `WHERE` (`history.ts:36-42`) |
| Reset by revert? | v2 revert: no (`projector.ts:415-454`, no `applyUsage`). v1 remove: yes, decrements |
| Read via | `info.ts:14` `fromRow` → `SessionSchema.Info.tokens` |
| ⚠️ Populated only when | the **v1** engine drives the session — see §2.4 |
| Archive (soft retire) | `time_archived` column `sql.ts:59`; surfaced at `info.ts:47` |
| `time_compacting` | column `sql.ts:58`; `projector.ts:73` passes it through, but **nothing anywhere sets `info.time.compacting`** — and `info.ts:44-48` does not even read it back. Dead. (Confirms SCAN.md §6's PURPLE gap.) |

---

## 8. Corrections to `docs/SCAN.md`

`docs/SCAN.md` is **not in this repo** (see Provenance at the top). The left column restates each
claim in full, so this table is readable without it — but the claims themselves cannot be
re-checked against the original wording. Verdicts in the right column were re-derived from the
code and stand on their own.

| SCAN claim | Status |
|---|---|
| `projector.ts:100` is the accumulator | **correct, exact** |
| `projector.ts:39` = only `step-finish` carries usage | **correct, exact** |
| `projector.ts:327-328` = sign-flip re-update | **correct, exact** |
| `compaction.ts:114-126` = `settings()` reads config documents | **correct, exact** |
| `history.ts:36-38` = post-compaction tail | correct in substance; the full predicate is `:36-42`, and a second baseline filter follows at `:44-46` |
| `core/src/session/info.ts:29-37` = token read | off by one — actual `:28-36` (`tokens` block `:29-37` if `cost` excluded) |
| `opencode/src/session/session.ts:97-106` = token read | off by one — actual `:97-105` |
| `protocol/src/api.ts:78-83` = one port mounts both | block starts at `:79`; substance correct |
| `session/compaction.ts:328` (agent) and `:508` (`session.compacted`) | these are **`packages/opencode/src/session/compaction.ts`**, not this file (241 LOC) |
| §1 "unresolved — which engine runs" | **settled: both, see §6** |
| §2 "Both API families read the same DB columns — they report the same number" | true for **reads**; **materially incomplete** — only the v1 engine *writes* those columns. See §2.4 |
| §2 "counters never reset through compaction" | correct, and now verified on the v2 side too |
| §6 `session.time.compacting` has no writer | **correct** |
