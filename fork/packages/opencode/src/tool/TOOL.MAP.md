# tool/ — structural map

Owns every builtin tool: definition shape, the registry that assembles the per-request live list,
description text, parameter schemas, and output truncation.

**This subsystem is the single largest line item in the model's standing context.**
**Re-measured 2026-07-26 by execution** (importing this package's own `ShellPrompt.render` and
`ToolJsonSchema.fromSchema`), superseding SCAN.md §4's unverifiable `~5,740 tok / ≈23 KB`:

| Live tool set | desc + JSON schema | @4 B/tok |
|---|---|---|
| **`openai/gpt-5.6-sol` — the harness default**, pinned in `.opencode/opencode.jsonc` (**11** tools: `apply_patch`, no `edit`/`write`, **no `websearch`**) | **19,903 B = 19.4 KB** | **~4,976 tok** |
| the same 11 + `websearch`, i.e. provider `opencode` or `enableExa`/`enableParallel` | 21,725 B = 21.2 KB | ~5,431 tok |
| any non-`gpt-` model (13 tools: `edit`+`write`, no `apply_patch`) | 23,216 B = 22.7 KB | ~5,804 tok |

> **Corrected: the first row previously said 12 tools / 21,725 B and counted `websearch`.** The
> harness provider is `openai`, and `websearch` is gated to provider `opencode` **or**
> `enableExa` **or** `enableParallel` (`registry.ts:58-59`, applied at `:288-290`); `env.sh` sets
> neither flag. So `websearch` (1,822 B) is never registered here. Removing it from this file's
> own per-tool table gives exactly 11 tools / 19,903 B — within 5 B of STRIP.md's independently
> measured 19,898 B, which reconciles the two documents. The gate is correctly described at the
> per-request conditionals table below; only the headline double-counted it.
>
> **The model id was also wrong** (`opencode/gpt-5.6-sol`), which is not a naming nit: that
> provider prefix does not exist in the catalog, so every session started anywhere in this repo
> died with `Model not found` before its first turn. Fixed to `openai/`. Any measurement in this
> file attributed to the pinned default was necessarily taken under some *other* model.

⚠️ **SCAN's `~5,740 tok` measured the _non-gpt_ branch** (within ~1% of the second row) — it does
not describe the harness default, which pays **~370 tok less** because `apply_patch` (1,316 B)
replaces `edit`+`write` (2,807 B). See gotcha 3 for the mutual exclusion.

**The default is pinned deliberately.** Without an explicit `model` in `.opencode/opencode.jsonc`
the harness inherits the *global* config's default, which on a machine set to a non-`gpt-` model
silently flips **both** the base prompt (`gpt.txt` 9,284 B → `default.txt` 8,528 B) **and** the
live tool set (row 1 → row 2). Both rows are correct; which one you get is a config question, not
a code question.

Token figures use 4 B/token (SCAN's implied ratio, kept for comparability); **no tokenizer is
installed in this repo, so tokens are estimates — the byte counts are exact.** The per-tool byte
table below is `wc -c`, all 16 files exact.

Repo `~/Desktop/healbot/opencode` @ `0fdcfb6`, branch `healbot`, v1.18.5.

> **Provenance — RETRACTED.** This block previously asserted that `docs/SCAN.md` and
> `docs/PROBE.md` "are not in this repo and never were… phase-1 working notes that were never
> committed", and on that basis stamped **UNVERIFIED** on every SCAN-attributed number across
> seven maps. **That is false.** Both files are committed — in the *other* repo:
> `git log --stat` in `~/Desktop/healbot` shows `docs/SCAN.md` added by `6f74f2b` and
> `docs/PROBE.md` by `8f34a84`. The `git log --all` search returned empty only because this
> fork cannot see that repo's history: `~/Desktop/healbot/.gitignore` excludes `/opencode/`, so
> the two artifact sets live in repos neither of which can resolve the other's paths.
>
> They are at `~/Desktop/healbot/docs/SCAN.md` and `~/Desktop/healbot/docs/PROBE.md` —
> followable citations, not an audit trail. SCAN's figures should be treated with care for a
> different and real reason: **they were measured under `anthropic.txt` with cwd inside this
> fork**, so they do not describe the shipped harness. See `~/Desktop/healbot/docs/REVIEW.md`.
>
> Standing risk, documented nowhere else: this fork's only remote is
> `https://github.com/sst/opencode`, so branch `healbot` — which holds all 14 maps and the
> spike — **has no valid push destination and exists on one disk, unbacked.**

> **Path convention.** A citation prefixed `packages/…` is repo-relative. A **bare path** resolves
> against, in order: (1) this file's own directory, (2) the owning package's `src/`, (3) the repo
> root — all three are in use here. A bare **`:NNN`** is a line in the file named by the enclosing
> section heading or table row.

---

## File table

| File | LOC | Owns | Key symbols (line) |
|---|---|---|---|
| **`registry.ts`** | 450 | **Assembles the live tool list.** Discovery, gating, description composition. | `webSearchEnabled()` 58-60 · `Interface` 72-82 · `Service` 84 · `fromPlugin()` 120-176 · filesystem custom-tool discovery 178-192 · plugin tools 194-199 · **`questionEnabled` 202** · `Tool.init` block 203-221 · **builtin array 226-244** · `all()` 251 · `ids()` 256 · **`describeTask()` 260-273** · `describeCodeMode()` 275-284 · **`tools()` 286-335** · `named()` 337 · `node` 422-448 |
| `tool.ts` | 183 | The `Tool.Def` / `Tool.Info` contract + auto-truncate wrapper. | `DynamicDescription` 16 · `InvalidArgumentsError` 24-34 · `Context<M>` 36-46 · `ExecuteResult` 48-53 · **`Def` 55-65 (`id` 59, `description: string` 60, `parameters` 61, `jsonSchema?` 62, `execute` 63)** · `Info` 71-77 · `wrap()` 99-149 (truncate 131-144) · **`define()` 151-169** · `init()` 171-181 |
| `json-schema.ts` | 164 | Effect `Schema` → `JSONSchema7` for the wire contract. Memoized. | `fromSchema()` 8-22 · **`fromTool()` 24-26** · `normalize()` 28-88 · `inlineLocalReferences()` 121-144 · `ToolJsonSchema` 164 |
| `schema.ts` | 14 | `ToolID` branded id. | `toolIdSchema` 6 · `ToolID.ascending()` 12 |
| `truncate.ts` | 156 | Tool-output size cap + on-disk overflow store. | `RETENTION` 13 · `MAX_LINES=2000` 15 · `MAX_BYTES=50KB` 16 · `hasTaskTool()` 28-31 · `write()` 68-73 · `limits()` 75-83 · **`output()` 85-141** (hint 129-131) · cleanup fiber 143-148 |
| `truncation-dir.ts` | 4 | One constant, split out to break a cycle. | `TRUNCATION_DIR` 4 |
| `external-directory.ts` | 49 | Not a tool. Shared out-of-worktree guard. | `assertExternalDirectoryEffect()` 15-45 (ask 35-43) · `assertExternalDirectory()` 47-49 |
| `mcp-websearch.ts` | 96 | Not a tool. Exa/Parallel MCP HTTP client. | `SearchArgs` 43 · `McpRequest` 58 |
| `shell/id.ts` | 19 | Shell kind union + **`ToolID = "bash"`** 16. | `toKind()` 10 |
| `shell/prompt.ts` | 293 | Renders the bash description from a template + platform sections. | `parameterSchema()` 15-23 · `renderPrompt()` 28-34 · `bashCommandSection` 78 · `powershellCommandSection` 121 · `cmdCommandSection` 172 · `profile()` 221-271 · **`render()` 273-291** |
| `shell/shell.txt` | 1269 B | The `${…}` template for the bash description. | — |

---

## Per-tool table — id, description source, schema location

| File | Tool id (line) | Description source | Params schema | `ctx.ask` permission |
|---|---|---|---|---|
| `shell.ts` (645) | **`bash`** — `ShellID.ToolID` (`shell/id.ts:16`), define 338 | **template** `shell/shell.txt` → `ShellPrompt.render()` (`shell/prompt.ts:273-291`); consumed `shell.ts:603,607` | `shell/prompt.ts:15-23`, used `shell.ts:608` | `external_directory` 270 · `bash` 283 |
| `task.ts` (360) | `task` — `id` 24, define 81 | `task.txt` (import 2) **+** inline `BACKGROUND_DESCRIPTION` 25-30, concatenated 351-353 **+ subagent list appended at `registry.ts:320-326`** | `BaseParameterFields` 43-52 · `Parameters` 56-62 · `jsonSchema` override 355 | `task` 120 |
| `todo.ts` (46) | `todowrite` 15 | `todowrite.txt` (import 3) → used 20 | `Schema.Struct` 6-8 | `todowrite` 24 |
| `edit.ts` (737) | `edit` 59 | `edit.txt` (import 11) → used 67 | `Schema.Struct` 47-56 | `edit` 102, 145 |
| `read.ts` (386) | `read` 69 | `read.txt` (import 7) → used 380 | `Schema.Struct` 28-36 | `read` 255 |
| `write.ts` (104) | `write` 28 | `write.txt` (import 7) → used 36 | `Schema.Struct` 20-25 | `edit` 54 |
| `apply_patch.ts` (313) | `apply_patch` 23 | `apply_patch.txt` (import 13) → used 307 | `Schema.Struct` 18-20 | `edit` 206 |
| `grep.ts` (115) | `grep` 21 | `grep.txt` (import 7) → used 26 | `Schema.Struct` 10-18 | `grep` 39 |
| `glob.ts` (76) | `glob` 18 | `glob.txt` (import 7) → used 23 | `Schema.Struct` 10-15 | `glob` 28 |
| `webfetch.ts` (192) | `webfetch` 25 | `webfetch.txt` (import 6) → used 31 | `Schema.Struct` 13-22 | `webfetch` 39 |
| `websearch.ts` (143) | `websearch` 100 | `websearch.txt` (import 5) via **getter 106-108** that templates `{{year}}` | `Schema.Struct` 10-25 | `websearch` 119 |
| `skill.ts` (70) | `skill` 13 | `skill.txt` (import 6) → used 19 | `Schema.Struct` 8-10 | `skill` 27 |
| `question.ts` (44) | `question` 15 | `question.txt` (import 4) → used 20 | `Schema.Struct` 6-8 | — (uses `question` service) |
| `invalid.ts` (21) | `invalid` 10 | **inline literal `"Do not use"`** 12 | `Schema.Struct` 4-7 | — |
| `lsp.ts` (113) | `lsp` 38 | `lsp.txt` (import 5) → used 43 | `Schema.Struct` 23-35 | `lsp` 56 |
| `plan.ts` (79) | `plan_exit` 16 | `plan-exit.txt` (import 11) → used 23 | `Schema.Struct({})` 13 — empty | — |
| `code-mode.ts` (310) | `execute` — `CODE_MODE_TOOL` 12, define 188 | **inline const 14** + `describeCatalog()` 58-66 appended at `registry.ts:322` | `Schema.Struct` 16-20 | dynamic key 147 |

---

## Which tools are live, and when

Runtime-flag defaults: `effect/runtime-flags.ts` — `client` = `"cli"` (:56), all `experimental*`
false (:42-55).

**IN by default (14):** `invalid` · `question` · `bash` · `read` · `glob` · `grep` · `edit` ·
`write` · `task` · `webfetch` · `todowrite` · `websearch`\* · `skill` · `apply_patch`\*

**OFF by default (3):**

| Tool | Gate | Condition |
|---|---|---|
| `execute` (code-mode) | `registry.ts:113-114`, `:221`, `:241`, emptiness check `:300-303` | `OPENCODE_EXPERIMENTAL_CODE_MODE` **and** a non-empty visible MCP catalog |
| `lsp` | `registry.ts:242` | `flags.experimentalLspTool` |
| `plan_exit` | `registry.ts:243` | `flags.experimentalPlanMode && client === "cli"` |

**Per-request conditionals (in `builtin`, dropped in `tools()`):**

| Tool | Gate | Condition |
|---|---|---|
| `question` | **`registry.ts:202`** | `["app","cli","desktop"].includes(flags.client) \|\| flags.enableQuestionTool` — **`cli` is allowlisted, so it is ON without the env var** (SCAN.md C3) |
| `websearch` | `registry.ts:288-290` ← `:58-60` | provider is `opencode`, **or** `enableExa`, **or** `enableParallel` |
| `apply_patch` | `registry.ts:292-294` | `modelID.includes("gpt-") && !includes("oss") && !includes("gpt-4")` |
| `edit`, `write` | `registry.ts:295` | the **inverse** of `apply_patch` — mutually exclusive |

**Consequence for this project.** The harness default is `openai/gpt-5.6-sol`, pinned at
`.opencode/opencode.jsonc`. `"gpt-5.6-sol".includes("gpt-")` is true → **`apply_patch` is live and
`edit`+`write` are dropped**. The provider is `openai`, not `opencode`, so **`websearch` is
dropped too**. Live set is **11 tools, not 14** — `all()` counts both branches (gotcha 5).
Re-measured totals in the header. Do not attribute savings to `edit`/`write`: under this default
they were never in the payload.

---

## Token cost — where every byte comes from

Assembly path: `registry.ts:286-335` → `session/tools.ts:92-134` (wraps into AI-SDK `tool()`,
schema via `ToolJsonSchema.fromTool` at `tools.ts:98`) → `session/prompt.ts:1283` →
`session/llm/request.ts:148` → `:184`.

### Measured description bytes (`wc -c` on this commit — VERIFIED)

| File | Bytes | File | Bytes |
|---|---|---|---|
| `task.txt` | **2,305** | `apply_patch.txt` | 1,098 |
| `todowrite.txt` | **2,012** | `websearch.txt` | 1,033 |
| `edit.txt` | 1,369 | `webfetch.txt` | 750 |
| `lsp.txt` | 1,303 | `grep.txt` | 657 |
| `shell/shell.txt` | 1,269 *(template)* | `question.txt` | 657 |
| `read.txt` | 1,158 | `write.txt` | 623 |
| `plan-exit.txt` | 579 | `glob.txt` | 517 |
| `skill.txt` | 399 | `plan-enter.txt` | 613 **(orphan)** |
| | | **`*.txt` total (all 16)** | **16,342** |
| | | *…minus the `shell.txt` template* | *15,073* |

### Measured *runtime* payload — description + JSON Schema, per tool (TESTED)

Produced by importing each tool's `Parameters` and running this package's own
`ToolJsonSchema.fromSchema`; `bash` via `ShellPrompt.render("zsh","darwin",…)`. This is what
actually ships, not what is on disk.

| Tool | desc B | schema B | total | Tool | desc B | schema B | total |
|---|---|---|---|---|---|---|---|
| **`bash`** | **4,672** | 492 | **5,164** | `websearch` | 1,029 | 793 | 1,822 |
| `task` | 3,018 | 724 | 3,742 | `read` | 1,158 | 479 | 1,637 |
| `todowrite` | 2,012 | 536 | 2,548 | `apply_patch` | 1,098 | 218 | 1,316 |
| `question` | 657 | 760 | 1,417 | `webfetch` | 750 | 443 | 1,193 |
| `grep` | 657 | 431 | 1,088 | `glob` | 517 | 510 | 1,027 |
| `skill` | 399 | 194 | 593 | `invalid` | 10 | 168 | 178 |
| *(`edit`)* | *1,369* | *498* | *1,867* | *(`write`)* | *623* | *317* | *940* |

**`gpt-5.6-sol` live set (12, italics excluded): 15,977 B desc + 5,748 B schema = 21,725 B.**

Three composition facts the on-disk table cannot show:

1. `bash` is **4,672 B composed** — not `shell.txt`'s 1,269 B. Per shell: `zsh`/darwin **4,672**,
   `bash`/linux **4,672**, `cmd`/win32 4,675, `powershell`/win32 5,280. Only one ever ships.
2. `task` is **3,018 B** = `task.txt` 2,305 + **713 B subagent rent** appended at
   `registry.ts:320-326`. `BACKGROUND_DESCRIPTION` (`task.ts:25-30`) is **not** included —
   it is gated on `flags.experimentalBackgroundSubagents`, off by default (`task.ts:351-353`).
3. `task`'s schema is **724 B, not 902 B**: with that flag off, `task.ts:355` sets
   `jsonSchema: fromSchema(BaseParameters)`, which omits the `background` property.

Excludes the AI-SDK tool-name and JSON wrapper overhead (~30-40 B/tool, ≈500 B total), so treat
these as a slight *under*-estimate of the wire payload.

### Reconciled against SCAN.md §4 — every figure now independently re-derived

SCAN.md is at `~/Desktop/healbot/docs/SCAN.md` (see the retracted provenance note above), and its
per-tool numbers proved re-derivable. Verdict per row:

| Tool | SCAN.md said | Re-measured | Verdict |
|---|---|---|---|
| `bash` | 4,672 B | **4,672 B** | **exact.** `shell.txt` 1,269 B is only the template; `render()` `:273-291` substitutes the section constants at `:65-220` — **cut the sections, not the .txt** |
| `task` | 3,019 B | **3,018 B** | within 1 B. `task.txt` 2,305 + subagent rent from `registry.ts:320-326` ← `describeTask()` `:260-273`, reconstructed at **713 B** from `explore` (484 B) + `general` (149 B) + header. Confirms `BACKGROUND_DESCRIPTION` was not in scope — it is flag-gated off |
| `todowrite` | 2,012 B | **2,012 B** | exact; no runtime composition |
| **tool set total** | ~5,740 tok (≈23 KB) | **23,216 B ≈ ~5,804 tok** for the `edit`+`write` branch | **exact to ~1% — but of the _non-gpt_ branch.** The project default pays **21,725 B ≈ ~5,431 tok** (see header) |

### Description composition — the three runtime append sites

`registry.ts:317-326`:
```
description: [ output.description,                                        ← the .txt / inline string
               tool.id === TaskTool.id  ? describeTask(agent)  : undefined,  ← subagent rent
               tool.id === "execute"    ? codeModeDescription  : undefined ]
             .filter(Boolean).join("\n")
```
Plus `registry.ts:313` — the `tool.definition` plugin hook can rewrite `description`,
`parameters`, and `jsonSchema` of **any** tool before this.

**Subagent rent (`describeTask`, `registry.ts:260-273`).** Every non-`primary` agent that is not
permission-denied contributes `- <name>: <description>` to the `task` description on **every
request** — 714 B for 2 subagents. `explore` and `general` are the only two by default
(`agent/agent.ts:185-209`). Cutting them removes the whole block including its
`"Available agent types and the tools they have access to:"` header (`:272`).

---

## Inputs / outputs

**Feeds in:** `Config.Service` (custom tool dirs via `config.directories()`, `registry.ts:179-181`)
· `Plugin.Service` (`registry.ts:194-199`) · `Agent.Service` (`describeTask`) ·
`Permission.Service` (`registry.ts:263, 280-281`) · `MCP.Service` (`registry.ts:281`) ·
`Truncate.Service` (`tool.ts:163`) · `RuntimeFlags.Service` · `Instruction.Service`
(`registry.ts:44,436` → `read.ts:300`). Full dep list `registry.ts:422-448`.

**Produces:** `Tool.Def[]` consumed only by `session/tools.ts:92`; truncated output files under
`Global.Path.data/tool-output` (`truncation-dir.ts:4`).

**Depends on it:** `session/tools.ts:92-134` · `session/prompt.ts:1226,1283` ·
`session/llm/request.ts:148` · `tool/code-mode.ts` (child-tool invocation).

---

## Extension points

| Point | Mechanism | Site |
|---|---|---|
| Add a tool from a plugin | plugin `tool` field (`packages/plugin/src/index.ts:226-228`) | `registry.ts:194-199` → `fromPlugin()` 120-176 |
| Add a tool from a file | `{tool,tools}/*.{js,ts}` in any config dir | `registry.ts:178-192`; id = `namespace` or `namespace_export` (`:190`) |
| Rewrite any tool's description/schema | plugin `tool.definition` hook | **`registry.ts:313`** |
| Remove a tool from the model's view | blanket permission deny | `permission/index.ts:204-214` → `session/llm/request.ts:208-214` |
| Per-message tool disable | `user.tools[name] === false` | `session/llm/request.ts:213` |
| Change output caps | config `tool_output.max_lines` / `max_bytes` | `truncate.ts:75-83` |
| Per-tool `execute` interception | plugin `tool.execute.before` / `.after` | `session/tools.ts:106,121` |

---

## Gotchas

1. **`edit`/`write` and `apply_patch` are mutually exclusive and model-selected.**
   `registry.ts:292-295`. A substring match on `modelID` silently swaps which file-mutation tool
   the model sees. `gpt-4` and `oss` are carved back out.
2. **`question` is live without `OPENCODE_ENABLE_QUESTION_TOOL`.** `registry.ts:202` allowlists
   `client === "cli"`, which is the default (`effect/runtime-flags.ts:56`). SCAN.md C3 confirmed
   by test. The env var is a fallback for non-standard clients.
3. **A blanket deny removes the schema; a scoped deny does not.** `permission/index.ts:211`
   requires `rule.pattern === "*" && rule.action === "deny"`. `bash: {"rm -rf *": "deny"}` leaves
   the full bash schema in context and only blocks at call time. See
   `../permission/PERMISSION.MAP.md`.
4. **Tool-name aliasing in the deny check.** `permission/index.ts:205-206`: `edit`, `write`, and
   `apply_patch` all resolve against the **`edit`** permission; the three `*_mcp_resource*` tools
   resolve against **`read`**. Denying `write` alone does nothing.
5. **`all()` (`registry.ts:251-254`) is NOT the live list** — it is unfiltered. Only
   `tools()` (`:286-335`) applies gating. Anything reading `all()`/`ids()` over-reports.
6. **`bash`'s description is generated, not stored.** Editing `shell/shell.txt` only touches the
   scaffolding; the bulk lives in the section constants at `shell/prompt.ts:65-220` and is
   selected per-platform by `profile()` (`:221-271`).
7. **`plan-enter.txt` (613 B) is an orphan** — `plan.ts:11` imports only `./plan-exit.txt`; no
   import site anywhere under `packages/opencode/src` (verified by grep).
8. **`code-mode` self-disables.** Even with the flag on, `registry.ts:300-303` drops `execute`
   when `describeCodeMode` returns nothing, which happens whenever there are no permission-visible
   MCP tools (`registry.ts:281-282`).
9. **The registry has no `agent.tools` allow/deny map.** `Agent.Info` has no `tools` field. All
   agent-scoped tool removal happens downstream at `session/llm/request.ts:208-214`. Do not look
   for it here.
10. **Auto-truncation is universal.** `tool.ts:131-144` truncates every tool's output unless the
    tool already set `metadata.truncated`. Plugin tools get it separately at `registry.ts:154`.

---

## Strip levers

Ranked by measured bytes removed. This is the largest-yield subsystem in the fork.

| Lever | Site | Yield |
|---|---|---|
| **Blanket-deny unused tools** (config `permission: {"<tool>": "deny"}`) | enforced `permission/index.ts:204-214` → `session/llm/request.ts:208-214` | **schema + description removed outright.** No source change |
| Trim the bash description sections | **`shell/prompt.ts:65-220`.** `render()` `:273-291` interpolates whatever `profile(name, platform, …)` `:221-271` selects, so **exactly one** command section ships per request: `bashCommandSection` :78 on macOS/Linux. `:121` (powershell) and `:172` (cmd) are **binary weight only — deleting them saves 0 context tokens.** Cut from the *selected* section to move the number. | **4,672 B — MEASURED**, see below. Still the single biggest tool |
| Cut `explore` + `general` subagents | `agent/agent.ts:185-209`; rent charged at **`registry.ts:320-326`** ← `:260-273` | 714 B **per request** |
| Trim `task.txt` | `task.txt` (2,305 B), used `task.ts:351-353` | up to 2,305 B |
| Trim `todowrite.txt` | `todowrite.txt` (2,012 B) — two long few-shot examples | up to 2,012 B |
| Trim `edit.txt` / `read.txt` / `lsp.txt` | 1,369 / 1,158 / 1,303 B | ~3.8 KB |
| Delete the orphan | `plan-enter.txt` | 613 B, zero risk |
| Shrink schemas | `json-schema.ts:28-88` `normalize()` already strips `additionalProperties`, nullable branches, `allOf`; descriptions inside `Schema.Struct` fields are the remaining lever (e.g. `edit.ts:47-56`, `websearch.ts:10-25`) | closes the 15 KB→23 KB gap |
| Rewrite descriptions without forking | a plugin implementing `tool.definition` | `registry.ts:313` — the zero-source-change path |
| Prune the builtin array outright | **`registry.ts:226-244`** | source change; use permissions first |
