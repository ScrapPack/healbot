# session/ — structural map

Owns the v1 session engine: lifecycle (create/prompt/abort/fork/summarize/compact/delete), the
agent loop, system-prompt assembly, token accounting, and the status/idle/error event stream.

Repo `~/Desktop/healbot/opencode` @ `0fdcfb6`, branch `healbot`, v1.18.5. All `file:line` below
re-verified against that commit unless marked otherwise.

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

## File table

| File | LOC | Owns | Key symbols (line) |
|---|---|---|---|
| `prompt.ts` | 1631 | **The agent loop.** Entry point for every turn. | `Interface` 102-109 · `ops()` 144 · `cancel()` 152 · `resolvePromptParts()` 157 · `title()` 193 · `handleSubtask()` 255 · `shellImpl()` 451 · `getModel()` 594 · `createUserMessage()` 635 · **`runLoop()` 1081-1341** · `loop()` 1343 · `command()` 1356 · `PromptInput` 1499 · `createStructuredOutputTool()` 1565 |
| `session.ts` | 1018 | Session record CRUD + events. DB row ⇄ `Info`. | `fromRow()` 59 · `toRow()` 120 · `Info` 224 · `CreateInput` 260-270 · `ForkInput` 273 · `Event{Created,Updated,Deleted,Diff,Error}` 323-329 · `getUsage()` 338 · `BusyError` 409 · `createNext()` 501 · `get/list/listGlobal` 542/548/557 · `children()` 598 · **`remove()` 608-629** · `updateMessage()` 631 · `updatePart()` 637 · `create()` 669 · **`fork()` 693-734** · `patch()` 736 · `setArchived()` 759 · `setPermission()` 780 · `messages()` 830 |
| `processor.ts` | 718 | Per-assistant-message stream consumer. Turns LLM events into parts. **Token write origin.** | `create()` 98 · `updateToolCall()` 144 · `completeToolCall()` 160 · `failToolCall()` 186 · **`step-finish` case 435-484** · `cleanup()` 539 · `halt()` 599 · `process()` 627 |
| `tools.ts` | 590 | Wraps registry tools + MCP tools into AI-SDK `tool()` objects for one request. | **`resolve()` 41-493** · builtin wrap loop 92-134 · `ctx.ask` wiring 81-89 · MCP-resource tools 136-386 · **MCP tool loop 390-490** |
| `compaction.ts` | 562 | Compaction v1 (legacy engine): overflow test, tail selection, prune, summarize-in-place. | `PRUNE_MINIMUM/PROTECT` 28-29 · `isOverflow()` 168 · `estimate()` 180 · `select()` 188 · **`prune()` 243-287** · **`process()` 289-511** · `agents.get("compaction")` 328 · `Event.Compacted` publish 508 · **`create()` 513-536** |
| `system.ts` | 145 | Builds every non-instruction system block. | **`provider(model)` 27-42** (base prompt routing) · `environment()` 60-96 (`<env>`, `<available_references>`) · **`skills()` 98-110** · **`mcp()` 112-128** |
| `instruction.ts` | 237 | AGENTS.md/CLAUDE.md/CONTEXT.md discovery + read. | `globalFiles` 60-63 · `instructionFiles` 64-68 · **`systemPaths()` 110-153** (first-match break 119, 131) · **`system()` 155-169** · `find()` 171 · **`resolve()` 179-221** (walk-up attach for `read`) |
| `llm.ts` | 404 | `LLM.stream()` — the provider call. Native runtime vs ai-sdk fallback. | `StreamInput` 35 · `Interface.stream` 55 · `run()` 85 · `LLMRequestPrep.prepare()` call 106 · native attempt 227-251 · `streamText()` 280 |
| `llm/request.ts` | 226 | **Final system-array + tool-map assembly before the provider call.** | `PrepareInput` 20-36 · `Prepared` 38-51 · **`prepare()` 56-206** · **system concat 58-66 (ternary at :60)** · `experimental.chat.system.transform` 69 · `chat.params` 114 · `chat.headers` 134 · **`resolveTools()` 208-214** |
| `llm/ai-sdk.ts` | 288 | ai-sdk stream → `LLMEvent` adapter. | `adapterState()` 9 · `toLLMEvents()` 76 |
| `llm/native-request.ts` | 196 | Direct provider HTTP request builder. | `model()` 153 · `request()` 181 |
| `llm/native-runtime.ts` | 195 | Native (non-ai-sdk) streaming path + eligibility test. | `status()` 46 · `stream()` 74 · `nativeTools()` 169 |
| `run-state.ts` | 151 | **Busy/idle arbitration.** One `Runner` per session; source of the canonical idle edge. | `assertNotBusy()` 71 · **`runner()` 52-69 (onIdle 60-63, onBusy 64)** · **`cancel()` 77-86** · `ensureRunning()` 88 · `startShell()` 96 · `cancelBackgroundJobs()` 111 |
| `status.ts` | 56 | The `session.status` / `session.idle` publisher and the in-memory status map. | `Info` 8 · `get()` 30 · `list()` 35 · **`set()` 39-48** (idle deletes the key, 42-46) |
| `message-v2.ts` | 734 | Message/part model → `ModelMessage[]`; compaction filtering; paging. | `Event` 55 · **`toModelMessagesEffect()` 131** · `page()` 425 · `stream()` 469 · **`filterCompacted()` 521 / `filterCompactedEffect()` 574** · `latest()` 585 · `fromError()` 603 |
| `message.ts` | 148 | Legacy v1 part schemas (ToolCall/TextPart/…). Schema only. | `ToolInvocation` 39 · `TextPart` 45 · `ReasoningPart` 51 |
| `message-error.ts` | 14 | Shared message error union. | `OutputLengthError` 4 · `AuthError` 6 · `SharedSchema` 12 |
| `overflow.ts` | 34 | Pure context-overflow arithmetic. No I/O. | `COMPACTION_BUFFER = 20_000` 8 · `usable()` 10-20 · **`isOverflow()` 22-34** (auto-off check 28) |
| `reminders.ts` | 92 | Injects synthetic per-turn text parts (plan mode, build switch). | **`apply()` 15-90** · plan reminder push 27-36 · build-switch push 37-47 · experimental plan-mode branch 51-89 |
| `retry.ts` | 201 | Retry classification + backoff. Feeds `status: "retry"`. | `RETRY_INITIAL_DELAY` 26 · `delay()` 35 · `retryable()` 68 · **`policy()` 176-199** |
| `revert.ts` | 146 | Snapshot revert/unrevert of a message range. | `RevertInput` 13 · `Interface` 20 |
| `summary.ts` | 160 | **Git-diff summaries only — no LLM.** Not related to the `summary` agent. | `computeDiff()` 82 · **`summarize()` 102-127** · `diff()` 129 |
| `todo.ts` | 74 | Per-session todo list store + `session.todo` events. | `Interface` 16 |
| `schema.ts` | 26 | Branded ids. | `SessionID` 7 · `MessageID` 10 · `PartID` 19 |
| `prompt/*.txt` | — | Base system prompts, one per model family. See token cost. | — |
| `llm/AGENTS.md` | 7072 B | **Not source.** A nested instruction file — see Gotchas. | — |

---

## System-prompt assembly chain (the entire standing cost)

Ordered, per request. Nothing else contributes system text.

```
prompt.ts:1226  SessionTools.resolve(...)        → tools map        (tools.ts:41)
prompt.ts:1257  Effect.all([...])                 ┐
   sys.skills(agent)            → system.ts:98-110   <available_skills>
   sys.environment(model)       → system.ts:60-96    <env> + <available_references>
   instruction.system()         → instruction.ts:155-169  AGENTS.md bodies
   sys.mcp(agent, permission)   → system.ts:112-128  <mcp_instructions>
   MessageV2.toModelMessages…   → message-v2.ts:131  conversation
prompt.ts:1264-1269  const system = [env, instructions, mcp, skills]
prompt.ts:1272-1286  handle.process({ system, tools:1283, messages, … })
processor.ts:640     llm.stream(streamInput)
llm.ts:106           LLMRequestPrep.prepare({ system, tools, agent, … })
llm/request.ts:58-66 FINAL system array:
      [ agent.prompt ? [agent.prompt] : SystemPrompt.provider(model),   ← :60  TERNARY
        ...input.system,                                                ← the 4 blocks above
        ...(user.system ? [user.system] : []) ].join("\n")
llm/request.ts:69    plugin hook "experimental.chat.system.transform"
llm/request.ts:148   resolveTools() → :208-214 permission subtraction
llm/request.ts:99    (OpenAI OAuth only) system moves to options.instructions
llm/request.ts:101-112  system blocks become role:"system" ModelMessages
```

Base-prompt routing, `system.ts:27-42` — substring match on `model.api.id`:

| Match | File | Bytes |
|---|---|---|
| `muse-spark` | `prompt/meta.txt` | 9,151 |
| `gpt-4` \| `o1` \| `o3` | `prompt/beast.txt` | 11,080 |
| `gpt` + `codex` | `prompt/codex.txt` | 7,390 |
| `gpt` | `prompt/gpt.txt` | **9,284** |
| `gemini-` | `prompt/gemini.txt` | 15,372 |
| `claude` | `prompt/anthropic.txt` | 8,212 |
| `trinity` | `prompt/trinity.txt` | 7,748 |
| `kimi` | `prompt/kimi.txt` | 8,695 |
| fallthrough | `prompt/default.txt` | 8,528 |

---

## Session lifecycle

| Operation | HTTP | Route table | Handler | Engine entry |
|---|---|---|---|---|
| create | `POST /session` | `groups/session.ts:87,203` | `handlers/session.ts:155-176` | `session.ts:669` → `createNext()` 501 → publishes `Created` **537** |
| prompt | `POST /session/:id/message` | `:95,316` | `handlers/session.ts` `prompt` | `prompt.ts:635` `createUserMessage` → `loop()` 1343 → `runLoop()` 1081 |
| prompt (async) | `POST /session/:id/prompt_async` | `:96,329` | — | same, forked |
| abort | `POST /session/:id/abort` | `:91,253` | **`handlers/session.ts:232-235`** | `prompt.ts:152` `cancel` → `run-state.ts:77-86` |
| fork | `POST /session/:id/fork` | `:90,240` | `handlers/session.ts:206-229` | **`session.ts:693-734`** |
| summarize | `POST /session/:id/summarize` | `:94,303` | **`handlers/session.ts:273-291`** | `compaction.create()` 513 **+ `promptSvc.loop()`** — i.e. a real compaction turn |
| compact (auto) | — | — | — | `prompt.ts:1161-1168` (pre-turn overflow) · `prompt.ts:1320-1328` (post-turn `result === "compact"`) · `processor.ts:477-482` (sets `needsCompaction`) |
| delete | `DELETE /session/:id` | `:88,215` | `handlers/session.ts:178-179` | **`session.ts:608-629` — recursive over `children()`, publishes `Deleted` 624** |
| archive | `PATCH /session/:id` `{time:{archived}}` | `:89,227` | — | `session.ts:759-761` `setArchived` → `patch()` 736 → publishes `Updated` 748 |
| shell | `POST /session/:id/shell` | `:98,356` | — | `prompt.ts:451` `shellImpl` → `run-state.ts:96` `startShell` |
| command | `POST /session/:id/command` | `:97,343` | — | `prompt.ts:1356` |
| revert / unrevert | `POST …/revert`,`…/unrevert` | `:99,100` | — | `revert.ts` |
| permission reply | `POST …/permissions/:permissionID` | `:101,395` | — | see `../permission/PERMISSION.MAP.md` |

Full path table: `packages/opencode/src/server/routes/instance/httpapi/groups/session.ts:78-105`.
Endpoint declarations: same file `:108-445`.

---

## Token accounting path

**The counters are cumulative over the session's whole life and are never reset.**

```
processor.ts:438   Session.getUsage({model, usage, metadata})     ← session.ts:338-…
processor.ts:445   ctx.assistantMessage.tokens = usage.tokens
processor.ts:446-455  session.updatePart({type:"step-finish", tokens, cost})
session.ts:637-645    updatePart → publish SessionV1.Event.PartUpdated
core/src/session/projector.ts:312   project(PartUpdated)
core/src/session/projector.ts:39    usage() returns only for type === "step-finish"
core/src/session/projector.ts:327-328  applyUsage(previous,-1); applyUsage(next,+1)
core/src/session/projector.ts:90-105   UPDATE session SET tokens_input = tokens_input + …
```

Read back: `session.ts:98-106` (`fromRow`) and `core/src/session/info.ts:29-37`. **Both API
families read the same columns — same number.**

The projector is shared by the v1 binary: imported at
`packages/opencode/src/effect/app-runtime.ts:56` and
`packages/opencode/src/server/routes/instance/httpapi/server.ts:65`. So token accounting is
engine-independent, whichever way SCAN.md §1 resolves.

Removal paths subtract: `projector.ts:286` (MessageRemoved), `:304` (PartRemoved).

**Control-terminal trigger — use `input + output + reasoning`, exclude `cache.read`.**
SCAN.md §2 measured 350K crossed at turn 90/101 vs turn 17/101 depending on which fields you
sum. `cache.read` re-counts the whole cached prefix every turn.

**Fork inherits.** `fork()` (`session.ts:693-734`) replays every part through `updatePart()`
(:730), each of which re-runs `applyUsage(+1)`. A fresh fork reads `0` for ~3s then climbs to
the parent's exact total (SCAN.md §3, TESTED). Fork also creates a **root** session — no
`parentID` in the `createNext` call at `:697-703`.

---

## Compaction

| Concern | Where |
|---|---|
| Overflow arithmetic | `overflow.ts:10-34`; `usable()` reserves `cfg.compaction.reserved` or `min(20_000, maxOutputTokens)` |
| Overflow check (pre-turn) | `prompt.ts:1161-1168` via `compaction.isOverflow` (`compaction.ts:168-178`) |
| Overflow check (in-stream) | `processor.ts:477-482` sets `ctx.needsCompaction`; `process()` returns `"compact"` at `:679` |
| Enqueue | **`compaction.ts:513-536`** — writes a `type:"compaction"` user part |
| Dequeue / run | `prompt.ts:1149-1159` → `compaction.process()` `compaction.ts:289-511` |
| Agent used | `compaction.ts:328` — hard-coded `agents.get("compaction")` |
| Tail preservation | `compaction.ts:188-239` `select()`; `DEFAULT_TAIL_TURNS = 2` (:32) |
| Tool-output pruning | `compaction.ts:243-287`; gated on `cfg.compaction.prune` (:245); `skill` protected (:31) |
| Auto-continue prompt | `compaction.ts:451-503` |
| Completion event | **`compaction.ts:508`** `session.compacted` |
| Disable | `cfg.compaction.auto === false` → `overflow.ts:28` and `processor.ts:608`. **Config file only** — the env var only reaches the legacy path (SCAN.md C2) |

**Compaction never deletes messages or parts.** No `removeMessage`/`removePart` call exists in
`compaction.ts` (verified); it marks `part.state.time.compacted` (`compaction.ts:281`) and
filtering happens at read time in `message-v2.ts:521/574`. This is why the token counters are
monotonic.

---

## Event origins (the control terminal depends on these)

| Event | Published at | Trigger |
|---|---|---|
| `session.status` `{type:"busy"}` | `status.ts:41` ← `run-state.ts:64` | Runner goes busy |
| | `status.ts:41` ← `prompt.ts:1089` | every loop step |
| | `status.ts:41` ← `processor.ts:639` | every provider stream start |
| `session.status` `{type:"idle"}` + **`session.idle`** | `status.ts:41,43` ← **`run-state.ts:62`** | Runner drains — the canonical finish |
| | ← `run-state.ts:82` | `cancel()` with no live runner |
| | ← `processor.ts:612` | context overflow with auto-compaction off |
| | ← `processor.ts:624` | any other terminal error |
| `session.status` `{type:"retry"}` | `status.ts:41` ← **`processor.ts:665-671`** | `retry.ts:176-199` policy fires |
| `session.error` | `session.ts:328` `Event.Error`; published at `prompt.ts:1175` (agent not found), `prompt.ts:1306` (content filter), **`processor.ts:611, 616, 620`** | |
| `session.created` | **`session.ts:537`** | every `createNext` |
| `session.updated` | `session.ts:748` (`patch`) | title/archive/metadata/permission/model change |
| `session.deleted` | `session.ts:624` | recursive delete |
| `session.compacted` | `compaction.ts:508` | compaction **finished** |
| `message.updated` | `session.ts:633` | |
| `message.part.updated` | `session.ts:639` | every part write, including `type:"compaction"` |
| `session.diff` | `summary.ts:114` | |

**Idle vs never-started is distinguishable** because `status.ts:42-46` *deletes* the key on idle,
so a server-side seed (`GET /session/status`) only ever contains busy/retry. A client that writes
on receipt and never removes can treat key-present-and-idle as "ran and finished in this process".

**PURPLE / compacting — resolved beyond SCAN.md.** `session.time.compacting` is **dead**, but not
because it is untouched — because **nothing ever originates a value for it.** Both engines
round-trip the column and neither writes a timestamp into it:

| Site | Direction |
|---|---|
| `core/src/session/projector.ts:73` | `time_compacting: info.time.compacting` — v2 row build |
| **`session.ts:156`** (in `toRow`, `:120-158`) | same copy, **v1 row build** — reached only from `cli/cmd/import.ts:186` |
| **`session.ts:114`** (in `fromRow`) | reads the column back into `info.time.compacting` |
| `core/src/session/info.ts:44-48` | v2 read-back **omits it** — `created`/`updated`/`archived` only |
| `tui/src/context/sync.tsx:581` | the only *consumer*, and it is itself dead code (zero call sites) |
| `schema/src/v1/session.ts:563`, `session.ts:205`, `sql.ts:58` | schema/column declarations |

Every write above copies a field that no production code assigns; the only assignments anywhere
are test fixtures (`test/session/schema-decoding.test.ts:68`). So the round-trip preserves
`undefined` forever. Use instead:
`message.part.updated` where `part.type === "compaction"` — **VERIFIED emitted at start**, not
completion: `compaction.ts:528-535` writes the part inside `create()`, which runs *before*
`prompt.ts:1149` dequeues and processes it. Pair it with `session.compacted`
(`compaction.ts:508`) as the end edge. This upgrades SCAN.md §6's "INFERRED" to VERIFIED.

---

## Inputs / outputs

**Feeds in:** `Config.Service` (`config/config.ts`) · `Agent.Service` (`agent/agent.ts:140-265`
builtin defs) · `Provider.Service` · `ToolRegistry.Service` (`../tool/registry.ts`) ·
`Permission.Service` (`../permission/index.ts`) · `Plugin.Service` (`../plugin/index.ts`) ·
`MCP.Service` · `Skill.Service` (`../skill/index.ts`) · `Truncate.Service` (`../tool/truncate.ts`)
· `Database.Service` · `EventV2Bridge.Service`. Wiring: `prompt.ts:115-143`, dep graph
`prompt.ts:1598-1630`, `processor.ts:699-716`.

**Produces:** rows in `session` / `message` / `part` (via events → `core/session/projector.ts`) ·
the event stream above · files under `Global.Path.data/tool-output` (truncation) and
`.opencode/plans` (`session.ts:331-336`).

**Depends on it:** `server/routes/instance/httpapi/{groups,handlers}/session.ts` · `tui/src/context/sync.tsx`
· `tool/task.ts` (subagent sessions via `TaskPromptOps`, `prompt.ts:144-150`) · `tool/read.ts:300`
(`Instruction.resolve`).

---

## Extension points

| Point | Hook / field | Site |
|---|---|---|
| Replace the whole base prompt | `agent.prompt` | **`llm/request.ts:60`** |
| Append system text | `user.system` on the prompt payload | `llm/request.ts:62` |
| Mutate the assembled system array | plugin `experimental.chat.system.transform` | `llm/request.ts:69-73` |
| Mutate temperature/topP/options | plugin `chat.params` | `llm/request.ts:114-132` |
| Add request headers | plugin `chat.headers` | `llm/request.ts:134-146` |
| Rewrite messages pre-send | plugin `experimental.chat.messages.transform` | `prompt.ts:1255`, `compaction.ts:350` |
| Replace the compaction prompt / inject context | plugin `experimental.session.compacting` | **`compaction.ts:343-348`** |
| Suppress the auto-continue turn | plugin `experimental.compaction.autocontinue` | `compaction.ts:454-471` |
| Add instruction files | `config.instructions[]` (paths, globs, `http(s)://`) | `instruction.ts:135-150`, fetch 95-103 |
| Per-turn synthetic text | `reminders.ts:15-90` | |
| Structured output | `format: {type:"json_schema"}` on the prompt | `prompt.ts:1243-1250`, `1565-1590` |
| Tool subtraction | session/agent permission ruleset | **`llm/request.ts:208-214`** |

---

## Token cost — what this subsystem puts in the context window

### Fully measured — 47.1 KB ≈ ~12,053 tok at the repo root

**Every block re-measured 2026-07-26**, replacing SCAN.md's unverifiable ≈49 KB / ~12,000 tok.
Config-driven blocks (`<env>`, `<available_skills>`, `<mcp_instructions>`) were rendered from
live on-disk state through this repo's own formatters; the rest by executing the builders.
Model is `opencode/gpt-5.6-sol`, pinned in `.opencode/opencode.jsonc`.

| Block | Assembled at | Measured |
|---|---|---|
| Tool defs (desc + schema) | `prompt.ts:1283` ← `tools.ts:41` | **21,725 B** ≈ ~5,431 tok — `apply_patch` branch, see `../tool/TOOL.MAP.md` |
| Base/provider prompt | `system.ts:27-42` → **`llm/request.ts:60`** | **9,284 B** ≈ ~2,321 tok — `gpt.txt`, via the `gpt` branch `system.ts:31-36` |
| Instruction files | `instruction.ts:155-169` | **8,824 B** ≈ ~2,206 tok at root — **stacks with depth**, 22,273 B from `src/session/llm/` (gotcha 13) |
| **`<available_skills>`** | `system.ts:98-110` → `skill/index.ts:321-338` | **7,422 B** ≈ ~1,856 tok — **18** skills, not 19 |
| **`<env>` + `<available_references>`** | `system.ts:60-96` | **957 B** ≈ ~239 tok (`<env>` 399 + 2 refs 558) |
| **`<mcp_instructions>`** | `system.ts:112-128` | **0 B** — no MCP server configured anywhere, so `:117` returns `undefined` and the block is omitted entirely |
| **TOTAL (repo root)** | | **48,212 B = 47.1 KB ≈ ~12,053 tok** |

**SCAN.md's ≈49 KB / ~12,000 tok is confirmed** — within ~4 % on bytes and under 1 % on tokens.

But it is a point value, and the total **moves with the session's directory** because `fs.findUp`
returns *every* ancestor match (gotcha 13):

| Session location | Total | @4 B/tok |
|---|---|---|
| repo root | 48,212 B = **47.1 KB** | ~12,053 tok |
| `packages/opencode/src/session/llm/` | 61,815 B = **60.4 KB** | ~15,454 tok |

**A 13.6 KB / ~3,400 tok swing from location alone.** Budget against the range.

Token figures use **4 B/token** — SCAN's own implied ratio, kept for comparability. No tokenizer
is installed in this repo, so **tokens are estimates; every byte count is exact.**
| Plan reminder (plan agent only) | `reminders.ts:27-36` | `prompt/plan.txt` 1,484 B | ~370 tok/turn |
| Build-switch reminder | `reminders.ts:37-47` | `prompt/build-switch.txt` 233 B | ~58 tok, once |
| Max-steps nudge (last step only) | `prompt.ts:1281` | `core/session/runner/max-steps` | small |
| Structured-output preamble | `prompt.ts:1271` (const at `:82`) | inline | ~60 tok, conditional |
| Nested `AGENTS.md` on `read` | `instruction.ts:179-221` ← `tool/read.ts:300` | 14 nested `AGENTS.md` in repo; `session/llm/AGENTS.md` = 7,072 B | **unbounded, per-read** |

Byte counts for all base prompts are in the routing table above. `prompt/` totals 110,021 B on
disk; exactly one file ships per request.

---

## Gotchas

1. **`agent.prompt` REPLACES the base prompt; it does not append.** `llm/request.ts:60` is a
   ternary. Built-in `build` and `plan` deliberately define no `prompt`, which is why interactive
   sessions get the `.txt`.
2. **Instruction discovery stops at the FIRST match.** `instruction.ts:64-68` orders
   `["AGENTS.md","CLAUDE.md","CONTEXT.md"]` and `:131` breaks after the first file with any
   `findUp` hit. In this repo `AGENTS.md` (8,748 B) is injected and **`CONTEXT.md` (32,094 B) is
   silently ignored**. The global loop at `:115-120` breaks the same way. Verified: no `CLAUDE.md`
   at repo root.
3. **`read` attaches nested instruction files.** `tool/read.ts:300` calls
   `Instruction.resolve` (`instruction.ts:179-221`), which walks from the read file up to the
   worktree root and attaches every `AGENTS.md`/`CLAUDE.md`/`CONTEXT.md` it finds, once per
   assistant message (`claims` map, `:201-211`). There are 14 nested `AGENTS.md` under
   `packages/`; `session/llm/AGENTS.md` alone is 7,072 B. This cost is invisible in a
   standing-context measurement.
4. **`summary.ts` is not the `summary` agent.** `SessionSummary.summarize` (`summary.ts:102-127`)
   computes git diffs and never calls an LLM. The `summary` *agent* is **never invoked** —
   no `agents.get("summary")` or equivalent lookup exists in either engine. **This closes
   SCAN.md's open question #5: the `summary` agent is genuinely unused.** It is `hidden: true`
   and `mode: "primary"`, so it does not inflate the `task` description either.

   ⚠️ **It is nonetheless *defined twice*, once per engine** — so "unused" is not "absent", and a
   deletion has two halves:

   | Engine | Definition | Prompt |
   |---|---|---|
   | v1 | `agent/agent.ts:250-263` | `agent/prompt/summary.txt`, 648 B (imported `agent.ts:15`) |
   | **v2** | **`packages/core/src/plugin/agent.ts:198-203`** | **inline `PROMPT_SUMMARY` at `core/src/plugin/agent.ts:88`** — a *different* prompt, not `summary.txt` |

   Dropping the v1 half leaves the v2 registration and its inline prompt intact. See
   `../agent/AGENT.MAP.md` gotcha 4, which scopes its grep to `packages/opencode/src` and flags
   the v2 site correctly.
5. **Base-prompt routing is substring matching on the model id** (`system.ts:28-41`). A model id
   containing `o1` or `o3` anywhere routes to `beast.txt` (11,080 B). The project default
   `opencode/gpt-5.6-sol` routes to **`gpt.txt` (9,284 B ≈ 2,321 tok)**, *not* `anthropic.txt` —
   SCAN.md §4's ~2,050 tok figure and its "what `anthropic.txt` contains" analysis apply to
   `claude-*` models only.
6. **Orphan prompt files.** `prompt/copilot-gpt-5.txt` (14,241 B) and
   `prompt/plan-reminder-anthropic.txt` (4,056 B) have zero importers (verified by grep across
   `packages/**/*.ts`).
7. **`fork` yields a root session, not a child** (`session.ts:697-703` passes no `parentID`), and
   its token count climbs to the parent's total within seconds. Not a handoff mechanism.
8. **`summarize` is compaction.** `handlers/session.ts:273-291` calls `compaction.create()` then
   `promptSvc.loop()` — an LLM call that *adds* to the same cumulative counter and mutates in
   place.
9. **`DELETE /session/:id` is recursive** (`session.ts:619-622`) and swallows its own errors
   (`:626-628` logs and returns). Use `PATCH` + `time.archived` for retirement.
10. **`session.idle` is deprecated** (`schema/src/session-status-event.ts:43`) and redundant with
    `session.status`. `status.ts:39-48` publishes both with no dedup, and error paths call
    `status.set(idle)` after the runner may already have.
11. **`session.time.compacting` is never assigned a value.** Four sites copy or read the field
    (`projector.ts:73`, `session.ts:114`, `session.ts:156`, `tui/src/context/sync.tsx:581`) but
    none originates one, so it is `undefined` for the life of every session. Dead field — see
    Event origins above for the table and the working alternative.
12. **`OPENCODE_DISABLE_AUTOCOMPACT` does not cover this engine's config-document path.** Set
    `"compaction": {"auto": false}` in the config file (SCAN.md C2). Granularity is
    per-directory/worktree, not per-session.
13. **Ancestor `AGENTS.md` files STACK — the source comment says otherwise and is wrong.**
    `systemPaths()` (`instruction.ts:110-153`) calls `fs.findUp(file, ctx.directory, ctx.worktree)`,
    and `findUp` (`packages/core/src/fs-util.ts:154-161`) pushes a hit at **every** level from the
    session directory up to the worktree root — then `matches.forEach((item) => paths.add(...))`
    adds all of them. The `break` above it, and its comment *"The first project-level match wins so
    we don't stack AGENTS.md/CLAUDE.md from every ancestor"*, only stop **`AGENTS.md` vs
    `CLAUDE.md`** from both loading; they do **not** stop ancestor stacking.

    **Measured in this repo:** a session in `packages/opencode/src/session/llm/` loads
    `session/llm/AGENTS.md` (7,072 B) **+** `packages/opencode/AGENTS.md` (6,453 B) **+** root
    `AGENTS.md` (8,748 B) = **22,273 B**, versus 8,748 B at the root — a ~13.5 KB / ~3,400 tok
    swing driven purely by session location. This is the single largest source of variance in
    standing context, and it is invisible in any point measurement.

    **For the Healbot grid:** a control terminal that spawns sessions in different directories
    gives them materially different context budgets. If that matters, pin `ctx.directory` or set
    `config.instructions` explicitly.
14. **Skill dedup is LAST-wins, and the log message implies the opposite.** `skill/index.ts:125-131`
    logs `"duplicate skill name"` with `existing` and `duplicate` fields — then `:134` does
    `state.skills[md.data.name] = {…}`, **overwriting** with the incoming file. So the *later* scan
    wins and the entry logged as the "duplicate" is the one that ends up live. Scan order is
    `~/.claude/skills` → `~/.agents/skills` → project walk-up → `config.directories()`
    (`index.ts:185-227`), so a project skill silently overrides a global one of the same name.

    **Measured here:** 33 `SKILL.md` files collapse to **18** skills — `~/.claude/skills` is mostly
    symlinks into `~/.agents/skills`, so 15 names collide and the `.agents` copy wins every time.
    A naive file count over-reports the `<available_skills>` block by ~1.8×.
15. **No MCP server is configured, so `<mcp_instructions>` costs exactly 0 B.** `system.ts:117`
    returns `undefined` when `mcp.instructions()` is empty and the block is omitted outright — not
    emitted empty. Global config has no `mcp` key; `.opencode/opencode.jsonc` has `"mcp": {}`.
    Adding one server moves this from 0 to the server's full instruction text, wrapped per
    `:119-127`.

---

## Strip levers

| Lever | Site | Effect |
|---|---|---|
| **Define `agent.prompt`** in an `agent/*.md` | consumed at **`llm/request.ts:60`** | removes the whole base `.txt` (~2,050-2,321 tok). **No source change.** Largest win per unit of effort |
| Trim/replace the shipped base prompts | `prompt/*.txt`; routing `system.ts:27-42` | source-level alternative to the above |
| Delete orphan prompts | `prompt/copilot-gpt-5.txt`, `prompt/plan-reminder-anthropic.txt` | 18,297 B of dead weight, zero risk |
| Drop `<available_skills>` | short-circuit `system.ts:98-110` (or deny the `skill` tool — `:99` already early-returns on that) | ~1,930 tok |
| Drop `<available_references>` | `system.ts:77-94` | ~small |
| Trim `<env>` | `system.ts:65-76` | ~small; keep cwd/git/platform |
| Point instructions at a smaller file | `instruction.ts:64-68` ordering, or `config.instructions` (`:135-150`) | ~2,360 tok. Reordering to put a short file first flips which one wins |
| Suppress nested-AGENTS.md attach | `instruction.ts:179-221`, called from `tool/read.ts:300` | removes an unbounded per-read cost |
| Drop the plan reminder | `reminders.ts:27-36` | ~370 tok/turn on the `plan` agent |
| Disable auto-compaction | config `compaction.auto=false`; honored at `overflow.ts:28`, `processor.ts:608` | removes surprise LLM calls; makes the token counter a clean monotonic trigger |
| Turn off prune | config `compaction.prune`; `compaction.ts:245` | |
| Tool subtraction (biggest lever, lives next door) | `llm/request.ts:208-214` ← `permission/index.ts:204-214` | see `../tool/TOOL.MAP.md` and `../permission/PERMISSION.MAP.md` |
