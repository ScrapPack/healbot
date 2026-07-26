# AGENT.MAP

Defines the seven built-in agents (identity + permission ruleset + optional system prompt), merges user
`config.agent[*]` over them, and answers "which agent is default". An agent's `prompt` field is the single
highest-leverage token lever in the codebase — it **replaces** the shipped base prompt rather than appending.

> **Path convention.** A citation prefixed `packages/…` is repo-relative. A **bare path** resolves
> against, in order: (1) this file's own directory, (2) the owning package's `src/`, (3) the repo
> root — all three are in use here. A bare **`:NNN`** is a line in the file named by the enclosing
> section heading or table row.

## Files

| File | Owns | Key symbols / lines |
|---|---|---|
| `agent.ts` (453 L) | Built-in agent table, config merge, default selection, `Agent.generate` | `Info` schema `:35-56` · `Service` `:84` · state builder `:98-353` · skill/reference dirs → read whitelist `:101-113` · `readonlyExternalDirectory` `:114-118` · **`defaults` ruleset** `:119-136` · user overrides `:138` · **`agents` record `:140-265`** · config merge `:267-294` (incl. `disable` `:268-271`) · `Truncate.GLOB` re-allow `:296-310` · `get` `:312-314` · `list` `:316-326` (default agent sorts first) · `defaultInfo` `:328-340` · `generate` `:368-436` · `node` `:447-451` |
| `prompt/compaction.txt` (823 B) | `compaction` agent system prompt | imported `:13`, used `:224` |
| `prompt/explore.txt` (871 B) | `explore` agent system prompt | imported `:14`, used `:214` |
| `prompt/summary.txt` (648 B) | `summary` agent system prompt | imported `:15`, used `:263` — **see gotcha 4** |
| `prompt/title.txt` (2,120 B) | `title` agent system prompt | imported `:16`, used `:248` |
| `generate.txt` (4,994 B) | Meta-prompt for `Agent.generate` (the "write me an agent" flow) | imported `:12`, used `:380` |
| `subagent-permissions.ts` (27 L) | Ruleset a `task`-spawned subagent session inherits | `deriveSubagentSessionPermission()` `:14-27` — inherits **only** parent `deny` + `external_directory` rules `:21-23`; injects `todowrite`/`task` denies unless the subagent explicitly allows them `:24-25` |

### The seven built-ins (`agent.ts:140-265`)

| Agent | Lines | Mode | Prompt | Hidden | Notable permissions | Removal risk |
|---|---|---|---|---|---|---|
| `build` | `:141-155` | primary | **none** → provider `.txt` | no | `question`/`plan_enter` allow | **Structural** — `defaultInfo()` throws `"no primary visible agent found"` `:337-338` if no primary survives |
| `plan` | `:156-181` | primary | none; a reminder is injected per turn instead | no | `edit:"*"→deny`, plan dirs allowed `:171-175`; `task.general` deny `:165-167` | Convenience |
| `general` | `:182-195` | **subagent** | none | no | `todowrite` deny `:188` | Convenience — **pays `task`-description rent** |
| `explore` | `:196-218` | **subagent** | `explore.txt` `:214` | no | `"*"→deny` + read-only allowlist `:200-209` | Convenience — **pays `task`-description rent** |
| `compaction` | `:219-233` | primary | `compaction.txt` `:224` | **yes** | `"*"→deny` | **Structural** — hard-coded `agents.get("compaction")` at `session/compaction.ts:328` |
| `title` | `:234-249` | primary | `title.txt` `:248`, `temperature 0.5` `:240` | **yes** | `"*"→deny` | Soft — `session/prompt.ts:216-217` does `if (!ag) return` |
| `summary` | `:250-264` | primary | `summary.txt` `:263` | **yes** | `"*"→deny` | **Unused in v1** — see gotcha 4 |

## Inputs / Outputs

**In:** `Config.Service` `:91` (`cfg.agent`, `cfg.mode`→agent promotion at `../config/config.ts:536-543`,
`cfg.default_agent`, `cfg.permission`, `cfg.references`) · `Skill.Service` `:94` (dirs → read whitelist `:101,111`) ·
`Plugin.Service` `:93` · `Provider.Service` `:95` · `Auth.Service` `:92` · `LocationServiceMap` `:96`.

**Out:** `Agent.Info[]`. Consumers:

| Consumer | Site | What it does with it |
|---|---|---|
| **`task` tool description** | `tool/registry.ts:260-273`, spliced `:322` | **Eager per-request cost** — every non-primary, non-denied agent contributes `- <name>: <description>` |
| Base prompt selection | `session/llm/request.ts:60` | `input.agent.prompt ? [prompt] : SystemPrompt.provider(model)` |
| **Tool visibility** | `session/llm/request.ts:208-213` (`resolveTools`) | A `deny` drops the tool from the request payload — schema and all. MCP-only variant: `permission/index.ts:216` (`visibleTools`), called `tool/registry.ts:281` |
| Skill visibility | `skill/index.ts:314`, `session/system.ts:99` | |
| Compaction | `session/compaction.ts:161,328,362` | |
| Title generation | `session/prompt.ts:216-221` | |
| Plan reminder | `session/reminders.ts:26-45` | |
| Subagent spawn | `tool/task.ts:84` + `subagent-permissions.ts:14` | |
| HTTP `GET /agent` | `groups/instance.ts:52`, `handlers/instance.ts:80-83` | |
| CLI | `cli/cmd/agent.ts:68,239`, `cli/cmd/run.ts:268`, `cli/cmd/debug/agent.handler.ts:33` | |

## Extension points

| Point | Where |
|---|---|
| `<configdir>/{agent,agents}/**/*.md` — frontmatter = fields, **body = `prompt`** | `../config/agent.ts:13-32` (body at `:27`) |
| `<configdir>/{mode,modes}/*.md` → forced `mode:"primary"` | `../config/agent.ts:34-59` |
| `config.agent[name]` — overridable keys | `agent.ts:281-293`: `model`, `variant`, `prompt`, `description`, `temperature`, `top_p`, `mode`, `color`, `hidden`, `name`, `steps`, `options`, `permission` |
| **Delete a built-in from config** | `config.agent.<name>.disable = true` → `agent.ts:268-271` |
| Define a new agent from config | `agent.ts:273-280` — defaults to `mode:"all"`, `native:false` |
| Pick the default | `config.default_agent` → `agent.ts:330-336` (rejects subagents `:333` and hidden `:334`) |
| Generate an agent with the model | `agent.ts:368-436`, output schema `GeneratedAgent` `:58-62` |
| Plugin hook on the generate system prompt | `agent.ts:381` (`experimental.chat.system.transform`) |

## Token cost

Three distinct behaviours (SCAN §4, measured in this environment):

| Class | Cost | Site |
|---|---|---|
| **Primary agents** | **Zero** until switched to | — |
| **Subagents** | **Eager, every request.** Each non-primary, non-denied agent appends `- <name>: <description>` to the `task` tool description | `tool/registry.ts:260-273` → `:322` |
| An agent's `prompt` | **Replaces** ~2,050 tok of shipped base prompt — a ternary, not an append | `session/llm/request.ts:60` |

**Measured subagent rent: 714 B** for `explore` + `general`. Reconstructed here as
`"Available agent types and the tools they have access to:"` (56 B, `registry.ts:272`) +
`- explore: …` (484 B desc, `agent.ts:213`) + `- general: …` (149 B desc, `agent.ts:184`) = **713 B**. Matches
SCAN to one byte. The runtime `task` description is therefore `task.txt` (2,305 B) + 714 B = 3,019 B — which is
exactly the figure SCAN reports.

**The base-prompt lever, verified:**
```ts
// packages/opencode/src/session/llm/request.ts:60
...(input.agent.prompt ? [input.agent.prompt] : SystemPrompt.provider(input.model)),
```
`build` and `plan` deliberately define no `prompt` (`:141-181`), which is why interactive sessions get the shipped
`.txt`. Provider selection: `session/system.ts:27-42` → `session/prompt/{anthropic,gpt,codex,gemini,beast,kimi,
trinity,meta,default}.txt`. **Those files live in `session/prompt/`, not here** — this directory only holds the four
role prompts for the hidden/subagent roles.

## Gotchas

1. **Cutting `explore` and `general` is a direct token win, cutting `build` breaks startup.** `defaultInfo()` throws
   `"no primary visible agent found"` `:337-338` when no non-subagent, non-hidden agent survives.
2. **`compaction` is hard-coded by name.** `session/compaction.ts:328` does `agents.get("compaction")` with no
   fallback. `title` is safe (`session/prompt.ts:216-217` returns early).
3. **The built-in agent table exists twice.** v1 here (`agent.ts:140-265`, prompts as `.txt` imports); v2 at
   `packages/core/src/plugin/agent.ts:100-206` (same seven, prompts as **inline TS string literals** `:12-98`,
   e.g. `explore` `:15`, `compaction` `:33`, `title` `:43`, `summary` `:88`). **Editing one does not change the
   other.** Not in SCAN — found here. Which one is live depends on the unresolved v1/v2 engine question (SCAN §1).
4. **`summary` appears unused in v1.** `session/summary.ts:95-126` computes git diffs and never calls an LLM
   (grepped for `llm`/`generateText`/`streamText`/`agents.` — zero hits in that file), and there is no
   `agents.get("summary")` anywhere in `packages/opencode/src`. **But** `core/src/plugin/agent.ts:198` still
   defines it for v2. SCAN rated this medium-high; independently confirmed for the v1 tree.
5. **A subagent's description is a per-request tax paid by every session**, including ones that never call `task`
   (`tool/registry.ts:322`). Adding one subagent with a 500 B description costs ~125 tok on every turn forever.
6. **Permission is subtractive and layered.** Order: `defaults` `:119-136` → per-agent literal → `user`
   (`cfg.permission`) `:138` → `config.agent[x].permission` `:293`. A `deny` removes the tool from the request
   payload entirely — `resolveTools()` at `session/llm/request.ts:208-213` — so denies are *also* a token lever.
7. **`Truncate.GLOB` is force-re-allowed** after all merging (`:296-310`) unless you deny it *explicitly by that
   exact pattern* `:302`. A blanket `external_directory: {"*": "deny"}` will not stick.
8. **Skill directories silently widen `external_directory`** — `:101,111` add every skill dir to the allowlist.
   More skills ⇒ more readable paths.
9. **Subagent sessions do not inherit the parent's allows**, only its denies and `external_directory` rules
   (`subagent-permissions.ts:21-23`). Tightening a parent does not tighten the child's own grants.
10. **`config.mode.*` becomes an agent** with `mode:"primary"` forced (`../config/config.ts:536-543`,
    `../config/agent.ts:54`) — a second, non-obvious way primary agents appear.

## Strip levers

| Lever | Change at | Effect |
|---|---|---|
| **Replace the base prompt** (largest win per unit of effort, SCAN §8) | Ship `<configdir>/agent/build.md` with a body → `../config/agent.ts:27` → `session/llm/request.ts:60`. **No source change.** | −~2,050 tok/request |
| **Cut the subagent rent** | `config.agent.explore.disable = true` + `config.agent.general.disable = true` → `agent.ts:268-271`; or delete `:182-218`; or `permission: {task: {explore:"deny", general:"deny"}}` → filtered at `tool/registry.ts:263` | −714 B (~180 tok)/request |
| Shorten rather than remove | `agent.ts:213` (explore desc, 484 B) and `:184` (general desc, 149 B) | proportional |
| Kill the `task` tool outright | `permission: {task: "deny"}` — subtractive, drops `task.txt` (2,305 B) *and* the 714 B rent | −~750 tok/request |
| Drop unused role prompts | **Both halves, or the surface survives:** v1 `agent.ts:250-264` + `prompt/summary.txt` (648 B) **and** v2 `packages/core/src/plugin/agent.ts:198-203` + its inline `PROMPT_SUMMARY` at `:88` (gotcha 4) | 0 tokens; removes dead surface |
| Retire `plan` | `config.agent.plan.disable=true`; also stops the per-turn reminder at `session/reminders.ts:26-45` | −`plan.txt` per turn in plan mode |
| Trim the shipped prose (SCAN §4) | `session/prompt/anthropic.txt` etc. — SCAN's read: cut persona framing, generic thoroughness, the two long TodoWrite few-shots (~45 lines); keep output-format constraints (CLI monospace, `file:line`) | −~2,050 tok, but the config-file lever above achieves it without a source change |
| Orphan files to delete while here | `session/prompt/copilot-gpt-5.txt` (14,241 B) and `session/prompt/plan-reminder-anthropic.txt` (4,056 B) — zero importers (SCAN §7). **They are in `session/prompt/`, not this directory.** | 0 tokens; binary size only |
