# COMMAND.MAP

Builds the slash-command registry by unioning four sources — two built-ins, config-declared commands, MCP prompts,
and **every discovered skill** — behind lazy `get template()` accessors.
Zero standing token cost; it is the cheapest extension point in the system.

> **Path convention.** A citation prefixed `packages/…` is repo-relative. A **bare path** resolves
> against, in order: (1) this file's own directory, (2) the owning package's `src/`, (3) the repo
> root — all three are in use here. A bare **`:NNN`** is a line in the file named by the enclosing
> section heading or table row.

## Files

| File | Owns | Key symbols / lines |
|---|---|---|
| `index.ts` (177 L) | The whole registry + the `Command` service | `Event.Executed` `:18-20` (= `LegacyEvent.CommandExecuted`) · `Info` schema `:22-32` (note `template: Schema.Unknown` `:29`, retyped `:34` to `Promise<string> \| string`) · `hints()` `:36-44` (`$1..$N`, `$ARGUMENTS`) · `Default` `:46-49` · `Service` `:56` · `init()` `:65-157` ← **the four sources, in precedence order** · `get` `:161-164` · `list` `:166-169` · `node` `:175` (deps `Config`, `MCP`, `Skill`) |
| `template/initialize.txt` (3,492 B) | Body of `/init` — guided `AGENTS.md` setup | imported `index.ts:10`, used `:75,77`; `${path}` → `ctx.worktree` |
| `template/review.txt` (4,707 B) | Body of `/review` — diff review, runs as a **subtask** (`:86`) | imported `index.ts:11`, used `:84,87` |

### Sources, in registration order (later sources **cannot** overwrite earlier ones — `:135`)

| # | Source | Line | `source` tag | Template origin |
|---|---|---|---|---|
| 1 | built-in `init` | `:70-78` | `command` | `template/initialize.txt` |
| 2 | built-in `review` | `:79-88` | `command` | `template/review.txt`, `subtask:true` |
| 3 | `config.command[name]` | `:90-103` | `command` | config value, or an `<dir>/{command,commands}/**/*.md` body (`../config/command.ts:29`) |
| 4 | MCP prompts | `:105-132` | `mcp` | resolved **lazily over the wire** via `mcp.getPrompt` `:111-128`; args become `$1..$N` `:117` |
| 5 | **every skill** | `:134-152` | `skill` | raw `SKILL.md` body + a base-directory footer `:143-148`; **guarded by `if (commands[item.name]) continue` `:135`** |

## Inputs / Outputs

**In:** `Config.Service` `:61` (`cfg.command`) · `MCP.Service` `:62` (`mcp.prompts()`, `mcp.getPrompt`) ·
`Skill.Service` `:63` (`skill.all()`) · `InstanceContext` `:65` (for `ctx.worktree`).

**Out:** `Record<name, Info>`, consumed by:

| Consumer | Site |
|---|---|
| **Execution** — the only place a template becomes a message | `session/prompt.ts:1355-1481` (`SessionPrompt.command`) |
| HTTP `GET /command` | `server/.../groups/instance.ts:51`, handler `handlers/instance.ts:76-79` |
| HTTP `POST /session/:sessionID/command` | `groups/session.ts:97,343`, handler `handlers/session.ts:331-337,433` |
| `/init` auto-run | `handlers/session.ts:243-247` |
| TUI autocomplete (**skips `source:"skill"`**) | `packages/tui/src/component/prompt/autocomplete.tsx:450-451` |
| `opencode run` palettes (**does surface skills**) | `cli/cmd/run/footer.command.tsx:355`, `:783-793`; also `footer.prompt.tsx:406`, `footer.view.tsx:136` |
| ACP | `acp/directory.ts:113`, `acp/service.ts:760` |
| Execution telemetry | `Command.Event.Executed` published `session/prompt.ts:1474-1479`, consumed `project/project.ts:389-391` |

### Execution pipeline — `session/prompt.ts` `SessionPrompt.command()`

| Step | Line |
|---|---|
| Resolve by name; unknown → `Session.Event.Error` + throw | `:1361-1368` |
| Await the lazy template (MCP round-trip happens here) | `:1374` |
| `$1..$N` substitution, last placeholder absorbs the remainder | `:1376-1387` |
| `$ARGUMENTS` substitution; if neither form is present, args are **appended** | `:1389-1394` |
| **`` !`cmd` `` → shell execution, no permission check** | `:1396-1406` |
| Model resolution: `cmd.model` → `cmd.agent`'s model → session model | `:1409-1420` |
| Agent resolution; unknown → error | `:1422-1429` |
| `@file` refs → file parts | `:1431` (`resolvePromptParts`) |
| Subtask decision: subagent target **or** `cmd.subtask === true` | `:1438-1452` |
| `command.execute.before` plugin hook | `:1459-1463` |
| Hand to `prompt()`, then publish `Executed` | `:1466-1479` |

## Extension points

| Point | Where |
|---|---|
| `<configdir>/{command,commands}/**/*.md` — frontmatter = `Info` fields, body = template | `../config/command.ts:13-39` |
| `config.command[name]` inline | `index.ts:90-103` |
| Frontmatter keys honoured: `description`, `agent`, `model`, `subtask` | `index.ts:92-100` |
| `$1..$N` / `$ARGUMENTS` placeholders → completion hints | `hints()` `:36-44`; substitution `session/prompt.ts:1376-1394` |
| `@path` file references in a template | regex `../config/markdown.ts:5`, expanded `session/prompt.ts:1431` |
| `` !`cmd` `` shell interpolation | regex `../config/markdown.ts:6`, executed `session/prompt.ts:1396-1406` |
| `subtask: true` → runs in a child session instead of inline | `index.ts:30`, `session/prompt.ts:1438` |
| MCP server prompts (auto) | `index.ts:105-132` |
| `command.execute.before` plugin hook | `packages/plugin/src/index.ts:262-265`; fired `session/prompt.ts:1459` |

## Token cost

**Zero standing cost — the cheapest point in the system** (SCAN §4). Every template sits behind a getter
(`index.ts:74, 83, 97, 110, 141`); nothing is read until `session/prompt.ts:1374` awaits it, and even then the text
enters as a *user message*, never the system prompt. Adding commands does not grow the context window.

Counts observed (SCAN F5, measured): 20 commands default (`init` + `review` + 18 skills) → 3 with
`OPENCODE_DISABLE_EXTERNAL_SKILLS=1`. **The command count tracks the skill count** because of source 5.

## Gotchas

1. **Skills silently become commands.** `index.ts:134-152` registers every `skill.all()` entry. This is why
   "20 commands" is really "2 + 18 skills" — cutting skills cuts commands, and no command config explains it.
2. **`/<skill-name>` bypasses the `skill` permission gate** (SCAN §7). `tool/skill.ts:27-32` asks; this path never
   does. Hidden in the main TUI's autocomplete (`tui/src/component/prompt/autocomplete.tsx:451`) but **fully
   reachable** via `POST /session/:sessionID/command` and via `opencode run`'s skill palette
   (`cli/cmd/run/footer.command.tsx:783-793`).
3. **Any template can execute shell** — `` !`cmd` `` is run with `Process.text(..., {nothrow:true})` and the result
   spliced in, with no permission prompt (`session/prompt.ts:1396-1406`). Because of gotcha 1 this reaches
   third-party `SKILL.md` bodies. *Code path read end-to-end; not executed.*
4. **First-writer-wins, opposite of the config merge.** `index.ts:135` skips a skill whose name is already taken,
   and MCP prompts (`:106`) *do* clobber config commands. Ordering: built-ins < config < MCP, then skills fill gaps.
5. **`template` is `Schema.Unknown`** `:29` — MCP templates are promises. Anything reading `Info.template`
   synchronously gets a `Promise`; `session/prompt.ts:1374` is the only correct read. The OpenAPI schema is
   hand-patched to `string` at `server/routes/instance/httpapi/public.ts:264`.
6. **MCP templates cost a network round-trip at invoke time** (`index.ts:111-128`), inside the user's keystroke path.
7. **Args with no placeholder are appended, not dropped** (`session/prompt.ts:1392-1394`).
8. **A malformed command markdown throws and fails startup** (`../config/command.ts:36`); agents in the same scan
   only get skipped.

## Strip levers

| Lever | Change at | Effect |
|---|---|---|
| Sever skills→commands (closes gotchas 1–3) | `index.ts:134-152` — delete the loop | 20 → 2 commands; no token change; removes the permission bypass |
| Drop the two built-ins | `index.ts:70-88` + imports `:10-11` | −8,199 B of shipped `.txt` from the binary; **0 tokens** (never eager) |
| Disable shell interpolation | `session/prompt.ts:1396-1406`, or empty `SHELL_REGEX` at `../config/markdown.ts:6` | removes gotcha 3 |
| Gate the slash-skill path | add `ctx.ask({permission:"skill"})` equivalent in `session/prompt.ts:1355`, or filter `source==="skill"` in `handlers/session.ts:331` | removes gotcha 2 |
| Drop MCP prompts | `index.ts:105-132` | removes the invoke-time round-trip |

**Do not strip this directory for token reasons.** Commands are free (`get template()`); the measured cost is in
tool definitions (~5,740 tok), the base prompt (~2,050 tok), and instruction files (~2,360 tok) — SCAN §4.
This subsystem is the right place to *add* harness capability without paying context.
