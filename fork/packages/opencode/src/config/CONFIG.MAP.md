# CONFIG.MAP

Loads and merges every config source (global files, project files, `.opencode/` dirs, env, remote, MDM) into one
`ConfigV1.Info`, and scans each config dir for markdown-defined commands/agents/modes and file-based plugins.
This is **config v1** only — the v2 system is a separate, location-scoped service at `packages/core/src/config.ts`.

> **Path convention.** A citation prefixed `packages/…` is repo-relative. A **bare path** resolves
> against, in order: (1) this file's own directory, (2) the owning package's `src/`, (3) the repo
> root — all three are in use here. A bare **`:NNN`** is a line in the file named by the enclosing
> section heading or table row.

## Files

| File | Owns | Key symbols / lines |
|---|---|---|
| `config.ts` (681 L) | The whole merge pipeline + the `Config` Effect service | `Interface` `:124-133` · `Service` `:135` · `globalConfigFile()` `:139-147` (probe order `opencode.jsonc` → `opencode.json` → `config.json`) · `loadConfig()` `:213-237` · `loadFile()` `:239-244` · `loadGlobal()` `:246-279` · `loadInstanceState()` `:314-598` ← **the merge order, see table below** · `update()` `:624-631` (writes `<instanceDir>/config.json`) · `updateGlobal()` `:637-660` (JSONC-aware patch) · `invalidate()` `:633-635` · `node` `:675-679` |
| `paths.ts` (45 L) | Which directories/files are searched | `files()` `:10-21` — walk `directory`→`worktree` for `<name>.jsonc\|<name>.json`, root-first · `directories()` `:23-41` — `[Global.Path.config, ...ancestor .opencode, ...$HOME/.opencode, OPENCODE_CONFIG_DIR]` · `fileInDirectory()` `:43-45` |
| `agent.ts` (59 L) | Markdown → agent config | `load(dir)` `:11-32` globs `{agent,agents}/**/*.md`, frontmatter → fields, **body → `prompt`** `:27` · `loadMode(dir)` `:34-59` globs `{mode,modes}/*.md`, forces `mode:"primary"` `:54` |
| `command.ts` (39 L) | Markdown → command config | `load(dir)` `:13-39` globs `{command,commands}/**/*.md`, **body → `template`** `:29`; a bad frontmatter **throws** `InvalidError` `:36` (unlike agents, which skip) |
| `plugin.ts` (79 L) | Plugin spec discovery + provenance | `Scope`/`Origin` types `:7-16` · `load(dir)` `:18-30` globs `{plugin,plugins}/*.{ts,js}` · `pluginSpecifier`/`pluginOptions` `:32-38` · `resolvePluginSpec()` `:42-60` (anchors `./x.ts` to its declaring file) · `deduplicatePluginOrigins()` `:64-77` (last-declared wins) |
| `parse.ts` (79 L) | JSONC parse + schema decode + error shaping | `jsonc()` `:8-33` (allows trailing commas; throws `JsonError` with a caret-pointer message) · `schema()` `:35-72` · `topLevelExtraKeys()` `:74-79` — **unknown top-level keys are a hard failure** |
| `variable.ts` (91 L) | `{env:VAR}` and `{file:path}` substitution inside config text | `substitute()` `:34-91` · env at `:36-38` (missing → empty string) · `{file:...}` at `:40-87`, `~/` expansion `:62-64`, `//`-commented tokens skipped `:53-59`, missing file → `InvalidError` unless `missing:"empty"` `:69` |
| `managed.ts` (69 L) | Enterprise/MDM config | `managedConfigDir()` `:31-33` (`/Library/Application Support/opencode` · `%ProgramData%\opencode` · `/etc/opencode`; overridable by `OPENCODE_TEST_MANAGED_CONFIG_DIR`) · `readManagedPreferences()` `:43-69` (darwin only, `plutil` on `ai.opencode.managed.plist`) |
| `markdown.ts` (36 L) | Frontmatter parse + the two template regexes | `FILE_REGEX` `:5` (`@path`) · `SHELL_REGEX` `:6` (`` !`cmd` ``) · `files()` `:8-10` · `shell()` `:12-14` · `parse()` `:20-34` — **called by `config/agent.ts:19`, `config/command.ts:21`, `skill/index.ts:107`** |
| `entry-name.ts` (19 L) | Path → entry name (dedup key for agents/commands) | `stripPrefix()` `:8-13` · `configEntryNameFromPath()` `:15-19` |
| `tui.ts` (276 L) | **Separate service** for `tui.json` — theme, keybinds, TUI plugins | `Service` `:47` · `loadState()` `:83-226` (precedence comments at `:183`, `:188`, `:195`, `:200`) · `layer` `:228-260` · free functions `get()` `:270-272`, `pluginOrigins()` `:274-276` |
| `tui-migrate.ts` (132 L) | One-shot move of `theme`/`keybinds`/`tui` out of `opencode.json` into `tui.json` | `migrateTuiConfig()` `:29-68` · `backupAndStripLegacy()` `:89-113` (writes `*.tui-migration.bak`) |
| `tui-host-attention.ts` (21 L) | Resolves attention-sound paths relative to the tui config file | `resolveHostAttentionSoundPaths()` `:6-21` |
| `tui-cwd.ts` (5 L) | `CurrentWorkingDirectory` Effect Reference used by `tui.ts:231` | `:3-5` |

### Merge order — `config.ts` `loadInstanceState()` (later wins)

| # | Source | Line | Plugin scope |
|---|---|---|---|
| 1 | `.well-known/opencode` per authenticated `wellknown` entry (+ its `remote_config` URL) | `:356-396` | global |
| 2 | Global files: `<Global.Path.config>/{config.json, opencode.json, opencode.jsonc}` | `:398-399` ← `loadGlobal` `:258-260` | global |
| 3 | `$OPENCODE_CONFIG` (single file) | `:401-404` | inferred |
| 4 | Project `opencode.{jsonc,json}` walking `directory`→`worktree`, root-first | `:406-410` ← `paths.ts:10-21` | local |
| 5 | Per-dir pass over `ConfigPaths.directories()`: `.opencode/opencode.{json,jsonc}`, then `ConfigCommand.load`, `ConfigAgent.load`, `ConfigAgent.loadMode`, `ConfigPlugin.load` | `:416`, `:424-466` (`:459-465`) | local/global by path |
| 6 | `$OPENCODE_CONFIG_CONTENT` (inline JSON) | `:468-476` | local |
| 7 | Active console org config (`<url>/api/config`) | `:478-514` | global |
| 8 | Managed config dir `opencode.{json,jsonc}` | `:516-522` | global |
| 9 | **macOS MDM `.mobileconfig` — overrides everything** | `:524-534` | — |
| 10 | `mode.*` promoted into `agent.*` with `mode:"primary"` | `:536-543` | — |
| 11 | `$OPENCODE_PERMISSION` (JSON) merged into `permission` | `:545-551` | — |
| 12 | `tools: {x:bool}` translated to `permission: {x:"allow"\|"deny"}`; `write\|edit\|patch` all collapse to `edit` | `:553-564` | — |
| 13 | `username` default from `os.userInfo()` | `:566-573` | — |
| 14 | `autoshare:true` → `share:"auto"` | `:575-577` | — |
| 15 | `$OPENCODE_DISABLE_AUTOCOMPACT` → `compaction.auto=false`; `$OPENCODE_DISABLE_PRUNE` → `compaction.prune=false` | `:579-584` | — |

Array fields do **not** replace — `instructions` is set-unioned (`mergeConfigConcatArrays` `:45-51`); everything else is
`mergeDeep` (`:41-43`).

## Inputs / Outputs

**In:** files above · env `OPENCODE_CONFIG`, `OPENCODE_CONFIG_CONTENT`, `OPENCODE_CONFIG_DIR`,
`OPENCODE_DISABLE_PROJECT_CONFIG`, `OPENCODE_PERMISSION`, `OPENCODE_DISABLE_AUTOCOMPACT`, `OPENCODE_DISABLE_PRUNE`,
`OPENCODE_TUI_CONFIG` (all declared `packages/core/src/flag/flag.ts:15-78`) · services `FSUtil`, `Auth`, `Account`,
`Env`, `Npm`, `HttpClient` (`config.ts:675-679`).

**Out:** `ConfigV1.Info` + `plugin_origins` (type `config.ts:111-115`). Schema:
`packages/core/src/v1/config/config.ts` (field list `:23-190`; `compaction` `:149-168`; `skills` → `v1/config/skills.ts`).

**Depends on it:** `Skill` (`skill/index.ts:254`, `:205-227`) · `Command` (`command/index.ts:61`, `:90-103`) ·
`Agent` (`agent/agent.ts:91`, `:267-294`) · `Instruction` (`session/instruction.ts:55`) · `ToolRegistry`
(`tool/registry.ts:201`) · HTTP `GET/PATCH /config` (`server/routes/instance/httpapi/groups/config.ts:10-40`).

**Side effects on load:** seeds `~/.config/opencode/opencode.jsonc` with `$schema` if absent (`:250-257`); injects
`$schema` into any config file missing it (`:232-234`); writes `.gitignore` into every config dir (`:295-312`);
forks a background `bun install @opencode-ai/plugin` per config dir (`:438-457`).

## Extension points

| Point | Where |
|---|---|
| `<dir>/{command,commands}/**/*.md` → slash command | `command.ts:15` |
| `<dir>/{agent,agents}/**/*.md` → agent (body = system prompt) | `agent.ts:13,27` |
| `<dir>/{mode,modes}/*.md` → primary agent | `agent.ts:36,54` |
| `<dir>/{plugin,plugins}/*.{ts,js}` → auto-loaded plugin | `plugin.ts:21` |
| `plugin: []` in config (npm spec or path) | `plugin.ts:42-60` |
| `{env:VAR}` / `{file:./x.md}` in any config value | `variable.ts:36,40` |
| `instructions: []` (globs, `~/`, http URLs) | consumed `session/instruction.ts:135-150` |
| `skills.paths` / `skills.urls` | consumed `skill/index.ts:211-227` |
| Remote: `.well-known/opencode`, console org config, MDM plist | `config.ts:356-396`, `:478-514`, `managed.ts:43-69` |

## Token cost

**Zero directly.** Nothing in this directory is inlined into a prompt. Two config fields *cause* prompt text elsewhere:

| Field | Where it lands | Measured (SCAN §4) |
|---|---|---|
| `instructions[]` + discovered `AGENTS.md`/`CLAUDE.md` | `session/instruction.ts:155-169` → `session/prompt.ts:1260` | ~2,360 tok |
| `agent.<name>.prompt` (`config.ts:283`) | `session/llm/request.ts:60` — **replaces** the shipped base prompt | −~2,050 tok when set |

## Gotchas

1. **`OPENCODE_CONFIG_DIR` does not isolate config** (SCAN C1, TESTED). Two accessors disagree:
   `Global.Path.config` is the raw XDG path computed at module load, flag-blind
   (`packages/core/src/global.ts:13,26,31`); `Global.Service.config` is flag-aware (`global.ts:64`).
   The global loader (`config.ts:258-260`) and `paths.ts:26` both use the **raw** one, and `paths.ts:39` only
   *appends* the dir to the search list. `GET /path` also reports the raw one
   (`server/routes/instance/httpapi/handlers/instance.ts:29-37`, esp. `:34`) — **not in SCAN, verified here**.
   Only the global `AGENTS.md` lookup is correctly redirected (`session/instruction.ts:61`).
   Untested cheapest lever: `$XDG_CONFIG_HOME` (`global.ts:13` reads `xdgConfig` at module load).
2. **`OPENCODE_DISABLE_AUTOCOMPACT` only reaches the v1 compactor** (SCAN C2). It is consumed at exactly one site,
   `config.ts:579-581`. The v2 compactor reads `compaction.auto` from config *documents*
   (`packages/core/src/session/compaction.ts:114-126`), which the env var never enters. Use the config **file**.
3. **Two config systems, two `compaction` schemas.** v1 = `core/src/v1/config/config.ts:149-168`
   (`tail_turns`, `preserve_recent_tokens`, `reserved`); v2 = `core/src/config/compaction.ts:9-15`
   (`keep.tokens`, `buffer`). Only `auto` and `prune` are common to both.
4. **No per-session config.** v2 config is *location*-scoped (`core/src/config.ts:140` + `makeLocationNode` `:223-227`);
   v1 is instance-scoped (`config.ts:600-604`). Finest granularity is per-directory/worktree.
5. **An unrecognized top-level key is fatal**, not ignored (`parse.ts:35-53`). A typo bricks startup.
6. **Legacy key silently dropped**: `theme`/`keybinds`/`tui` in `opencode.json` are stripped by
   `normalizeLoadedConfig` `:53-62` and only survive if `tui-migrate.ts:29-68` already moved them to `tui.json`.
7. **Config load mutates your files**: `$schema` injection `:232-234`, global seed `:250-257`, `.gitignore` write
   `:295-312`, legacy TOML `config` → `config.json` + `unlink` `:262-276`, and the migration backup
   `tui-migrate.ts:90-96`.
8. **`tools: {write:false}` also denies `edit` and `patch`** — all three map onto the single `edit` permission
   (`:557-560`).
9. **A bad command markdown throws; a bad agent markdown is skipped.** `command.ts:36` vs `agent.ts:19`.
10. **`{env:MISSING}` becomes an empty string, not an error** (`variable.ts:36-38`) — silently produces `""` values.

## Strip levers

| Lever | Change at | Effect |
|---|---|---|
| Real config isolation | `config.ts:258-260` and `paths.ts:26`: swap `Global.Path.config` → `Global.Service.config` (flag-aware). Try `$XDG_CONFIG_HOME` **first** — no source change. | Cuts inherited global agents/commands/plugins/skills wholesale |
| Kill auto-compaction | Config file `"compaction": {"auto": false}` — **not** the env var (gotcha 2) | Governs both engines |
| Drop project config discovery | `OPENCODE_DISABLE_PROJECT_CONFIG=1` → `config.ts:406`, `paths.ts:27`, `instruction.ts:123` | Removes ancestor `opencode.json`, `.opencode/`, and project `AGENTS.md`/`CLAUDE.md` |
| Base-prompt replacement (largest win/effort, SCAN §4) | Ship one `<dir>/agent/<name>.md`; body lands as `prompt` (`agent.ts:27`) and **replaces** the shipped `.txt` at `session/llm/request.ts:60` | −~2,050 tok, no source change |
| Instruction-file cost | `instructions: []` in config, or delete the repo `AGENTS.md` | −~2,360 tok |
| Tool-schema cost (biggest line item, ~5,740 tok) | `permission: {"<tool>": "deny"}` — permissions are **subtractive**; `resolveTools()` at `session/llm/request.ts:208-213` drops denied tools from the request payload. The `bash` description is assembled at runtime, not a static file: `tool/shell/prompt.ts:273` (`render()`) over `tool/shell/shell.txt` | Directly cuts the largest block |
| Stop the background npm installs | `config.ts:438-457` (and the tui twin `tui.ts:234-250`) | Startup latency, not tokens |
