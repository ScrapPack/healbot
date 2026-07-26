# Phase 1 — Architecture scan

Date 2026-07-26 · Target `~/Desktop/healbot/opencode` @ `0fdcfb6` (branch `healbot`, v1.18.5)
Method: four independent fresh-context agents, one per question area, read-only; plus one
follow-up verification run by the synthesizer against a **copy** of the local DB.

Evidence tiers: **VERIFIED** (code read, `file:line` cited) · **TESTED** (executed and
observed) · **INFERRED** (unverified link, stated as such).

> **⚠ Partially superseded.** Audited in [REVIEW.md](REVIEW.md). Most of this document held up
> under adversarial re-derivation. Four things did not, and they are flagged inline below:
> §1's engine conflict (**settled**), §2's `/api/session/{id}/context` advice (**worse than
> stated**), §4's cost table (**wrong model**), §4's `~20 tok/skill` (**5.4x low**), §6's PURPLE
> option 3 (**right conclusion, wrong reason**), and §7's "stop at the FIRST match"
> (**misleading**).

---

## 0. Corrections to Phase 0

Three Phase 0 claims did not survive. Recording them plainly.

### C1 — `OPENCODE_CONFIG_DIR` does **not** isolate config. Phase 0 said it did.

**TESTED.** Two servers from the same neutral cwd, one with `OPENCODE_CONFIG_DIR` pointed at
an empty dir:

```
default    → 18 skills, 20 commands
"isolated" → 18 skills, 20 commands      ← identical
```

Its debug log still shows `~/.config/opencode/opencode.jsonc` being loaded, and `GET /path`
still reports the real global config dir under both.

**Root cause (VERIFIED):** two accessors that disagree. `Global.Path.config` is the raw XDG
path computed at module load with no flag check (`packages/core/src/global.ts:13,26,31`);
`Global.Service.config` is flag-aware (`global.ts:64`). The global-config loader
(`packages/opencode/src/config/config.ts:258-260`) and `ConfigPaths.directories()`
(`packages/opencode/src/config/paths.ts:26`) both use the **raw** one. `OPENCODE_CONFIG_DIR`
merely *appends* a directory to the search list (`paths.ts:39`).

Still inherited despite the flag: `~/.config/opencode/{config.json,opencode.json,opencode.jsonc}`,
`~/.config/opencode/{command,agent,plugin,skills}/`, `~/.claude/skills`, `~/.agents/skills`,
`~/.claude/CLAUDE.md`, `~/.opencode/`. Only the global `AGENTS.md` lookup is correctly
redirected (`session/instruction.ts:61`).

**Consequence for Phase 3:** there is no env var that yields a clean base. Real isolation
needs either a source patch at `config.ts:258-260` + `paths.ts:26`, or `$XDG_CONFIG_HOME`
(**INFERRED**, untested — `global.ts:13` derives from `xdgConfig` at module load, so it
should work; cheapest lever, test it first).

### C2 — `OPENCODE_DISABLE_AUTOCOMPACT` does not settle compaction. Phase 0 called risk (b) "RESOLVED".

**VERIFIED.** It is consumed in exactly one place —
`packages/opencode/src/config/config.ts:579` sets `compaction.auto = false` — and that path
governs the **legacy** compactor only. The v2 compactor reads `compaction.auto` from config
*documents* via `settings()` (`packages/core/src/session/compaction.ts:114-126`), sourced
from files on disk, which the env var never enters.

**The lever that covers both is the config file:** `"compaction": { "auto": false }`.
**Per-session disabling is not supported** — config resolves per *location*
(`packages/core/src/config.ts:223-227`), so the finest granularity is per-directory/worktree.

### C3 — the yellow border is fine. Phase 0 risk (d) was a false alarm.

**TESTED.** `question` is in the live tool list with `OPENCODE_ENABLE_QUESTION_TOOL` unset.
The real gate is `["app","cli","desktop"].includes(flags.client) || flags.enableQuestionTool`
(`packages/opencode/src/tool/registry.ts:202`), and `OPENCODE_CLIENT` defaults to `"cli"`
(`effect/runtime-flags.ts:56`), which is allowlisted. The env var is a fallback for
non-standard clients. `question.ask` publishes `Event.Asked` unconditionally
(`question/index.ts:104`). **YELLOW will fire.**

Phase 0's F5 measurement (18→1 skills, 20→3 commands) **stands**, but the credit belongs to
`OPENCODE_DISABLE_EXTERNAL_SKILLS`, which alone drops both trees plus project-local
`.claude`/`.agents` (`skill/index.ts:186-203`). `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS` is
largely redundant with it.

---

## 1. Unresolved conflict — which session engine runs?

The two agents that touched this disagree, and it is worth one direct check rather than a
guess.

- **Config agent:** `opencode serve` runs v1 (`packages/opencode/src`); `packages/core/src`
  (v2) is reachable only via the separate `lildax` bin (`packages/cli/package.json:7-9` vs
  `packages/opencode/package.json:17-19`).
- **Lifecycle agent:** one port mounts **both** — legacy `InstanceHttpApi` at `/session` and
  v2 `ServerApi` at `/api/session` (`packages/opencode/src/server/routes/instance/httpapi/api.ts:78-83`).

**My own Phase 0 evidence supports the lifecycle agent on routes**: the 1.17.10 OpenAPI dump
contains both families (`/session/*` and `/api/session/*`) on a single port. The open
question is narrower — whether POSTing to `/api/session/{id}/prompt` on the `opencode` binary
actually drives the **v2 core runner**, or whether that engine is live only under `lildax`.

**Why it matters:** it decides which compaction implementation governs. **Why it is not
blocking:** the config-file setting from C2 disables both. Use that, and the conflict stops
mattering for Phase 3. Resolve it in Phase 4 if the retirement policy needs engine-specific
behavior.

> **SETTLED — the lifecycle agent was right, and the config agent's claim is refuted.** The
> `opencode` binary mounts the v2 API **with real handlers backed by an in-process v2 runner**:
> `server/routes/instance/httpapi/server.ts:102` imports `handlers` from
> `@opencode-ai/server/handlers`, `:177-181` wires them, and `:299-302` provides
> `SessionExecutionLocal` whose drain calls `SessionRunner.Service.use(...)` in-process
> (`core/src/session/execution/local.ts:16-28`). TESTED: `POST /api/session/{id}/prompt`
> produced a complete assistant turn in ~1.2s. "Reachable only via `lildax`" is wrong.
>
> This is not academic, and it is not a compaction question. The v2 engine **never writes
> `session.tokens`** (see HARNESS.md), so a session driven through `/api/session` is invisible
> to any retirement trigger — and it is one path segment away on the same port. **Drive v1.**
> The `fork`/`summarize` row of the table below is correct: v2 has neither.

Practical split, if it holds:

| | Legacy `/session` | V2 `/api/session` |
|---|---|---|
| Engine | `packages/opencode/src/session/prompt.ts` | `packages/core/src/session/runner/` |
| Compaction | `session/overflow.ts` | `core/src/session/compaction.ts` |
| `fork` / `summarize` | **yes** | **no** |

---

## 2. Token accounting — settles the 350K trigger

**`session.tokens` is CUMULATIVE over the session's entire life.** VERIFIED **and** TESTED.

The write is an accumulator — `packages/core/src/session/projector.ts:100`:
```ts
tokens_input: sql`${SessionTable.tokens_input} + ${value.tokens.input * sign}`
```
Only `step-finish` parts carry usage (`projector.ts:39`). Streaming re-updates subtract the
previous value before adding the new one (`projector.ts:327-328`), so no double-counting.
Both API families read the same DB columns (`core/src/session/info.ts:29-37`,
`opencode/src/session/session.ts:97-106`) — **they report the same number**.

**TESTED** against the local DB: session `ses_0b535115bffe…` row = `652218 / 32583 / 8688640`;
SUM over its 101 `step-finish` parts = **exact match**. A `cache.read` of 8.7M on one session
is by itself proof this is not context occupancy.

**`GET /api/session/{id}/context` does NOT give a lifetime total** — it returns the live
post-compaction tail (`core/src/session/history.ts:36-38`). Summing it under-reports after
any compaction.

> **Worse than this says.** `SessionHistory` reads `SessionMessageTable` **exclusively**, and
> the v1 engine never writes that table. So for a v1-driven session the endpoint returns an
> **empty array** — not an under-report, zero. TESTED on the reference 101-turn session:
> `session_message` = 0 rows, `part` = 738, `message` = 109. Repo-wide, 40/40 sessions have
> `part` rows but only 25 have any `session_message` rows. `PLAN.md:143-144` names this
> endpoint as the token source for the retirement trigger; on the prescribed engine it would
> read 0 forever and the trigger would never fire.

**Counters never reset through compaction.** VERIFIED (no message/part removal anywhere in
either compactor) and TESTED (a compacted session's row equals the full pre+post sum).
Good news for the trigger: it is **monotonic**, so it is clean to threshold on.

### Which fields to sum — this changes the retirement point ~5x

TESTED on a real 101-turn session:

| Definition | 350K crossed at | Final |
|---|---|---|
| `input + output` | **turn 90 of 101** | 684,801 |
| all four incl. `cache.read` | **turn 17 of 101** | 9,373,441 |

`cache.read` re-counts the whole cached prefix every turn. **Recommend
`input + output + reasoning`, excluding `cache.read`** — otherwise you retire sessions at
~17% of their useful life.

> **Superseded — this recommendation answers the wrong question, and mis-cites its own table.**
>
> Two corrections. First, arithmetic: the turn-90 row above is `input + output` **without**
> reasoning. The rule recommended here, `input + output + reasoning`, crosses 350K at
> **turn 77**, not turn 90 (recomputed against a DB copy; turn 76 = 341,999, turn 77 = 352,880).
> The turn-90 figure is also fragile — turns 86–89 sit at 341K–347K and only clear on a 154K
> input spike, so any additive term moves the crossing into the 70s.
>
> Second, and larger: 350K is a **quality** limit on context bloat, so the quantity to threshold
> is live **occupancy**, not lifetime spend — and for occupancy `cache.read` is *included*,
> because it is the cached prompt prefix sitting in the window. The premise that forced the
> cumulative reading (`PLAN.md:142-144`: "the model caps at 256K, a session can never hold
> 350K") died with F6's model decision — `gpt-5.6-sol` is context 1,050,000 / `limit.input`
> 922,000. See HARNESS.md "Token accounting". The measurements in this section are all correct;
> it is the recommendation drawn from them that changed.

---

## 3. Fork inherits the parent's token count — TESTED, and it is a race

The lifecycle agent flagged this as its one code-chain-only claim and asked for a live check.
I ran it against a **copy** of the DB (`OPENCODE_DB` → scratch copy; real DB confirmed
untouched afterward: identical size/mtime, fork absent).

```
parent  ses_0b535115bffe…  {input:652218, output:32583, reasoning:45958, cache.read:8688640}
fork    ses_062fa46bdffe…  at creation:  {input:0, output:0, reasoning:0, cache.read:0}
                           after ~3s:    {input:652218, output:32583, reasoning:45958, cache.read:8688640}
                           stable at 8s and 15s.
```

**Confirmed — and worse than static inheritance.** The fork reports **0 at creation**, then
climbs to exactly the parent's total as the part-replay publishes `PartUpdated` →
`applyUsage(+1)`. Reading tokens immediately after forking gives a clean-looking 0 that is a
lie three seconds later.

Also VERIFIED: fork creates a **root** session, not a child — no `parentID` is passed
(`session/session.ts:697-703`), title becomes `"<title> (fork #N)"`. Zero LLM calls.

**Consequence: `fork` is disqualified as the handoff mechanism.** A fork of a 350K session
starts at 350K and re-trips the threshold immediately. `summarize` is also wrong — it mutates
in place, costs an LLM call, and *adds* to the same counter.

**The only thing that yields a genuinely zero-token session is `POST /session`** seeded with
a handoff document as its first prompt (`CreateInput` accepts `parentID, title, agent, model,
metadata, permission, workspaceID` — `session/session.ts:260-270`).

Retirement should be `PATCH /session/{id}` with `time.archived` (soft), **not** `DELETE` —
delete is a hard recursive delete that removes all child sessions (`session/session.ts:608-626`).

---

## 4. What a session actually costs before you type anything

**TESTED** in this environment: **≈49 KB ≈ ~12,000 tokens** of standing context per request.

> **⚠ Wrong model, and measured inside the fork.** These figures are `anthropic.txt` with 14
> tools. The harness runs `openai/gpt-5.6-sol`, which routes to `gpt.txt` and swaps
> `edit`+`write` for `apply_patch` — **11 live tools**, since `websearch` is additionally gated
> out for provider `openai` (`tool/registry.ts:58-59, 288-290`). The block sizes below do not
> describe the shipped harness; see [STRIP.md](STRIP.md).
>
> The ≈49 KB *total* does independently reproduce for the fork under `gpt-5.6-sol` (48,212 B),
> so the headline is not wrong — but it was measured with cwd **inside the fork**, which is why
> the skill count here is 19 and STRIP's is 18. Both are right for their directory. Standing
> context is cwd-dependent throughout; always state the directory.

| Block | Where built | Cost |
|---|---|---|
| **All tool defs (desc + JSON schema)** | `session/prompt.ts:1283` ← `session/tools.ts` | **~5,740 tok (14 tools)** |
| Instruction files (AGENTS.md etc.) | `session/instruction.ts:155-169` | ~2,360 tok |
| Base/provider prompt | `session/system.ts:27-42` → `llm/request.ts:60` | ~2,050 tok |
| `<available_skills>` | `session/system.ts:98-110` | ~1,930 tok (19 skills) |
| `<env>`, `<available_references>` | `session/system.ts:65-94` | ~190 tok |
| `<mcp_instructions>` | `session/system.ts:112-128` | 0 here (no MCP) |

**The single biggest line item is tool definitions, not skills.** That reframes Phase 3:
`bash` alone is 4,672 B of description, `task` 3,019 B, `todowrite` 2,012 B.

### Lazy vs eager — the rule that governs the keep/cut test

| Extension point | Cost |
|---|---|
| **Commands** | **Zero.** Templates sit behind `get template()`; nothing reaches the model until invoked (`command/index.ts`). Cheapest point in the system. |
| **Skills** | **Metadata eager, body lazy.** Only `<name>/<description>/<location>` per skill (`skill/index.ts:321-338`); the body is injected only when the `skill` tool runs (`tool/skill.ts:51`). ~~~20 tok/skill~~ → **~108 tok/skill** — see below. |
| **Subagents** | **Eager.** Every non-primary agent appends `"- <name>: <description>"` to the `task` tool description on every request (`tool/registry.ts:260-273`) — measured 714 B for 2 subagents. |
| **Primary agents** | Zero until switched to. |
| **MCP servers** | **Eager and heavy.** Every tool from every server registered with full schema, no per-tool allowlist, `concurrency:"unbounded"` connect (`session/tools.ts:390-490`, `mcp/index.ts:505-529`). |
| **Plugins** | Zero unless they contribute a `tool`. |
| **Formatters / LSP** | Zero prompt text (LSP diagnostics ride tool *output*). |
| **Permissions** | Subtractive — a deny removes the tool schema entirely. **But it does not stop a skill**: `permission: {skill: "deny"}` removes the `skill` tool and the whole `<available_skills>` block while `/<skill-name>` still executes it, shell substitutions included (TESTED in one process). |

> **The ~20 tok/skill unit price is wrong by 5.4x.** Two independent wire captures measured the
> `<available_skills>` block at 7,794–7,798 B for 18 entries = **433 B/skill ≈ 108 tok/skill**.
> The mechanism (metadata eager, body lazy) is confirmed; only the number is broken. Note the
> row above contradicted itself — the block total it cites, ~1,930 tok for 19 skills, is
> 101.6 tok/skill. Descriptions are long and each entry carries a full absolute-path
> `<location>` line. This matters because STRIP's keep/cut test prices *individual* skills:
> re-adding 10 costs ~1,080 tokens, not ~200.

### The cheapest lever, by a wide margin

**VERIFIED, `llm/request.ts:60`:** an agent's own `prompt` **replaces** the shipped base
prompt — it is a ternary, not an append.

```ts
...(input.agent.prompt ? [input.agent.prompt] : SystemPrompt.provider(input.model))
```

So a single `agent/*.md` removes ~2,050 tokens of shipped prose with **no source change**.
Built-in `build` and `plan` deliberately define no `prompt`, which is why interactive
sessions get the `.txt`.

What `anthropic.txt` actually contains: a persona line ("You are OpenCode, the best coding
agent on the planet"), a URL-guessing prohibition, a feedback/docs block, Tone and style,
Professional objectivity, Task Management with two long TodoWrite few-shot examples (~45
lines), Doing tasks, Tool usage policy, Code References. Against the governing rule most of
this is **CUT** — persona framing, generic thoroughness, restated procedure. The load-bearing
remainder is small: output-format constraints (CLI monospace, `file:line`) and a couple of
project-specific URLs.

---

## 5. Built-in agents

VERIFIED, all seven at `packages/opencode/src/agent/agent.ts:140-265`.

| Agent | Prompt | Removal risk |
|---|---|---|
| `build` | none → provider prompt | **Structural.** `defaultInfo()` throws "no primary visible agent found" if no primary survives (`:337-338`) |
| `compaction` | `compaction.txt` | **Structural.** Hard-coded `agents.get("compaction")` (`session/compaction.ts:328`) |
| `title` | `title.txt` | Soft — `prompt.ts:216-217` does `if (!ag) return` |
| `plan` | none + `plan.txt` reminder each turn (`session/reminders.ts:27-36`) | Convenience |
| `explore` / `general` | `explore.txt` / none | Convenience — **but they are the only things paying rent in the `task` description (714 B/request)**, so cutting them is a direct token win |
| `summary` | `summary.txt` | **Appears unused** — `session/summary.ts:102-126` computes git diffs and never invokes an LLM; no `agents.get("summary")` found. Confidence medium-high |

---

## 6. Grid state plumbing

**Store:** `packages/tui/src/context/sync.tsx:64-138`, one Solid store, event-driven off the
**global** SSE feed — so events for every session arrive regardless of which is open
(`context/sdk.tsx:91`). Per-session: `session`, `session_status`, `permission`, `question`,
`message`/`part`, `todo`, `session_diff`.

**Plugin exposure:** a curated slice is bridged as `api.state`
(`packages/tui/src/plugin/adapters.tsx:98-163`) — `session.get/status/permission/question/
messages/todo/diff` and `session.count()`. Reads inside `createMemo`/JSX are reactive.

> **There is no `api.state.session.list()`.** A plugin cannot enumerate session IDs from
> state. Since the grid ships as a **builtin**, the clean fix is a direct import —
> `import { useSync } from "../../context/sync"` — which is already precedent
> (`diff-viewer.tsx:13` imports `useTheme` the same way), and provider nesting puts plugin
> routes inside `<SyncProvider>` (`app.tsx:306-321`). That is the only route to a *reactive*
> all-session list. Fallbacks: `client.session.list()` polled off `api.state.session.count()`
> as a tripwire; `client.permission.list()` / `client.question.list()` for cold-start
> reconciliation of RED/YELLOW.

### Border mapping

| Border | Signal | Status |
|---|---|---|
| dim | `session_status[id]` **absent** | VERIFIED |
| amber | `session_status[id].type === "busy"` | VERIFIED |
| **RED** | `api.state.session.permission(id).length > 0` | VERIFIED |
| **YELLOW** | `api.state.session.question(id).length > 0` | VERIFIED |
| green (finished) | key **present** and `.type === "idle"` | VERIFIED |
| **purple (compacting)** | **GAP** | see below |
| red-flash | `session_status[id].type === "retry"`; plus `session.error`, which `sync.tsx` does **not** store — track it yourself | VERIFIED |

**"Finished" vs "never started" is reliably distinguishable** — the server deletes idle
entries from its map (`session/status.ts:42-46`) so the HTTP seed only ever contains
busy/retry, while the TUI's handler writes and never removes (`sync.tsx:310-313`). Therefore
key-present-and-idle ⟹ it ran and finished **in this TUI process**. Caveat: process-local —
after a restart, yesterday's finished session reads dim, not green.
`notifications.ts:67-78` already implements this exact discriminator with an `active` Set;
lift it.

**PURPLE is a genuine gap.** `SessionStatus` has only `idle | retry | busy` — no compacting
variant. `session.time.compacting` exists in the schema and is read at `sync.tsx:581` but has
**no writer anywhere in the tree**, and its only consumer (`sync.session.status()`) has zero
call sites — dead code. Options, ranked:
1. `message.part.updated` where `part.type === "compaction"` — parts stream grid-wide; best
   available start signal. (**INFERRED** that it is emitted at start rather than completion.)
2. `session.compacted` (`session/compaction.ts:508`) — **end only**, no matching start.
3. `session.next.compaction.started`/`.ended` — clean pair, but gated behind
   `OPENCODE_EXPERIMENTAL_EVENT_SYSTEM`.

> **Option 3 is unusable, but not for the reason given.** There is no such gate: the publishers
> at `core/src/session/compaction.ts:186` and `:215` are unconditional, and an exhaustive search
> for `OPENCODE_EXPERIMENTAL_EVENT_SYSTEM` finds three non-test hits, none of them an event
> filter (`createBuiltinPlugins` discards the flag outright, `builtins.ts:22-38`). The real
> reason is architectural: those publishers live in the **v2** compactor, invoked only from
> `core/src/session/runner/llm.ts`. The live v1 prompt path runs a different compactor that
> publishes exactly one event, `session.compacted` (`opencode/src/session/compaction.ts:508`).
>
> **This generalises, and it is the important part:** the *entire* `session.next.*` family is
> v2-only. Zero publishers in `packages/opencode/src`. On the v1 path — the one you must use —
> `session.next.tool.called`, `.context.updated` and the compaction pair never fire, under any
> flag. Anyone chasing an env var will burn time and still get no purple.

**Two traps:**
- **RED never fires in auto-approve mode** — `sync.tsx:191-199` auto-replies `"once"` *before*
  writing to the store when `permission.mode === "auto"` (set by `--auto`).
- **`session.created` is not handled** by `sync.tsx` (VERIFIED absent from the switch) even
  though the server publishes it (`session/session.ts:537`). New sessions appear only on a
  later `session.updated` or an explicit `sync.session.refresh()`. The grid must handle this
  or freshly-spawned sessions won't show up.

Also: `session.idle` is **deprecated** (`schema/src/session-status-event.ts:43`) and redundant
with `session.status`. Drive off `session.status`. It double-fires on error paths with no
dedup (`status.ts:39-48`).

### Click-to-act and focus — both confirmed

Replies are keyed by **`requestID` alone**; no sessionID needed:
```ts
api.client.permission.reply({ requestID, reply: "once"|"always"|"reject", message?, directory?, workspace? })
api.client.question.reply({ requestID, answers, directory?, workspace? })   // answers: string[][], one inner array per question
```
Get the id from `api.state.session.permission(sessionID)[0].id`. For a grid spanning
directories, capture `{directory, workspace}` from the **event metadata** on
`permission.asked`/`question.asked` — the auto-approve path does exactly this
(`sync.tsx:193-197`). ⚠️ The metadata second arg works at runtime but `TuiEventBus` declares a
single-arg handler (`plugin/src/tui.ts:519-521`) — needs a cast.

Focus: `api.route.navigate("session", { sessionID })`. **Only `sessionID` is read**; other
params are dropped (`adapters.tsx:48-51`). Confirms the spike.

---

## 7. Incidental findings worth acting on

- **Skill dedup is a race.** Keyed on frontmatter `name`, last-writer-wins, loaded with
  `concurrency:"unbounded"` (`skill/index.ts:125-139, 240-243`). **TESTED:** across two boots
  the winner for `to-issues` flipped between `~/.claude` and `~/.agents`. Harmless while the
  trees are symlinked; a silent correctness bug the moment they diverge.
- **`/<skill-name>` bypasses the permission gate.** Slash-invoking a skill injects the whole
  SKILL.md body as the message template (`command/index.ts:141-149`) instead of going through
  the `skill` tool and its permission check.
- **Instruction files stop at the first matching FILENAME, not the first ancestor**
  (`instruction.ts:122-133`). In this repo `AGENTS.md` (8,748 B) is injected and
  **`CONTEXT.md` (32,094 B) is silently ignored** — that half is right. But the `break` is over
  the filename list; `fs.findUp` (`fs-util.ts:154-166`) collects **every** `AGENTS.md` from cwd
  up to the worktree root and adds them all. TESTED with a synthetic 3-level repo: all three
  loaded, each under its own `Instructions from:` header. The source comment at
  `instruction.ts:123` claims the opposite and is wrong about its own code. Consequence: a
  session at `packages/opencode/src/session/llm` ingests 22,273 B of `AGENTS.md`, not 8,748.
- **The `permission.ask` plugin hook is dead** — declared (`plugin/src/index.ts:261`), zero
  trigger sites repo-wide. Implementing it is a no-op.
- **Orphan prompt files:** `copilot-gpt-5.txt` (14,241 B) and `plan-reminder-anthropic.txt`
  (4,056 B) have zero importers.
- **`createBuiltinPlugins(options)` ignores its `options` argument** entirely
  (`builtins.ts:22-38`).

---

## 8. What this changes

**Phase 3 (strip)** — reprioritized by measured cost:
1. Tool definitions (~5,740 tok) are the biggest line item. Permissions are subtractive, so
   denying unused tools removes their schemas outright.
2. A custom `agent/*.md` `prompt` (~2,050 tok) — no source change, largest single win per
   unit of effort.
3. `OPENCODE_DISABLE_EXTERNAL_SKILLS` (~1,930 tok) — already measured in Phase 0.
4. Cutting `explore`/`general` subagents reclaims the 714 B `task`-description rent.
5. Real config isolation needs `$XDG_CONFIG_HOME` (test first) or a source patch — **not**
   `OPENCODE_CONFIG_DIR` (C1).
6. Set `"compaction": {"auto": false}` in the config file, not the env var (C2).

**Phase 4 (control terminal)** — design constraints now fixed:
- Retirement trigger: `session.tokens.input + output + reasoning`, **excluding `cache.read`**.
- Handoff: **`POST /session` + seed prompt.** Not `fork` (inherits the count, §3), not
  `summarize` (mutates in place, costs a call, adds tokens).
- Retire with `PATCH time.archived`, never `DELETE`.
- Grid reads all-session state via direct `useSync` import; must handle the missing
  `session.created` case itself.
- PURPLE needs `message.part.updated`/`compaction`; verify emit timing before relying on it.
- RED silently never fires under `--auto`.

## Still open

| Question | Why it matters | Cost to settle |
|---|---|---|
| Does `/api/session/*` drive the v2 engine on the `opencode` binary? (§1) | Which compactor governs | ~5 min; de-risked by using the config-file setting |
| Does `$XDG_CONFIG_HOME` fully redirect global config? | The cheap path to real isolation | ~10 min |
| Is the `compaction` message part emitted at start or completion? | PURPLE correctness | ~10 min |
| Live busy→idle→permission cycle observed end-to-end | Border state machine is read-from-source, not observed in flight | ~15 min + a few model calls |
| Is the `summary` agent genuinely unused? | Cut candidate | ~5 min |
