# SKILL.MAP

Discovers `SKILL.md` files across five root families, dedups them by frontmatter `name`, and exposes them as
(a) an eager `<available_skills>` block in the system prompt and (b) lazy bodies loaded by the `skill` tool.
**Every discovered skill also silently becomes a slash command** — see `../command/COMMAND.MAP.md`.

> **Path convention.** A citation prefixed `packages/…` is repo-relative. A **bare path** resolves
> against, in order: (1) this file's own directory, (2) the owning package's `src/`, (3) the repo
> root — all three are in use here. A bare **`:NNN`** is a line in the file named by the enclosing
> section heading or table row.

## Files

| File | Owns | Key symbols / lines |
|---|---|---|
| `index.ts` (354 L) | Discovery, dedup, the `Skill` service, and the prompt formatter | `Info` schema `:37-43` (`name`, `description?`, `location`, `content`) · patterns `:21-25` · built-in `customize-opencode` name/desc/body `:32-35` · `add()` `:105-140` ← **dedup writes here** · `scan()` `:142-171` · `discoverSkills()` `:173-233` ← **root order** · `loadSkills()` `:235-246` · `Service` `:248` · built-in seeded before disk `:278-283` · `get` `:289-292` · `require` `:294-299` · `all` `:301-304` · `dirs` `:306-308` · `available(agent)` `:310-315` ← **permission filter** · `fmt()` `:321-346` ← **the only thing that reaches the model eagerly** · `node` `:348-352` |
| `discovery.ts` (140 L) | Remote skill packs — `skills.urls` → HTTP pull into cache | `Service` `:27` · `download()` `:37-47` · `pull(url)` `:49-132` — fetches `<url>/index.json` `:51-63`, skips entries without `SKILL.md` `:67-73`, version-gated atomic swap via `.tmp-`/`.old-` dirs `:93-125`, cache root `<Global.Path.cache>/skills` `:35`; concurrency 4 skills / 8 files `:10-11` |

### Discovery roots, in scan order (`index.ts:173-233`)

| # | Root | Glob | Line | Killed by |
|---|---|---|---|---|
| 1 | `$HOME/.claude`, `$HOME/.agents` | `skills/**/SKILL.md` (dot) | `:187-194` | `OPENCODE_DISABLE_EXTERNAL_SKILLS`; `.claude` alone by `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS` / `OPENCODE_DISABLE_CLAUDE_CODE` |
| 2 | ancestor `.claude` / `.agents` between cwd and worktree | `skills/**/SKILL.md` (dot) | `:196-202` | `OPENCODE_DISABLE_EXTERNAL_SKILLS` |
| 3 | every `ConfigPaths.directories()` entry | `{skill,skills}/**/SKILL.md` | `:205-208` | — (this is where opencode's own skills live) |
| 4 | `config.skills.paths[]` (`~/` and relative expanded) | `**/SKILL.md` | `:211-220` | remove from config |
| 5 | `config.skills.urls[]` → `discovery.pull()` | `**/SKILL.md` | `:222-227` | remove from config |
| — | built-in `customize-opencode` (in-memory, no file) | — | `:278-283` | source edit only |

Flag definitions: `../effect/runtime-flags.ts:21` (`disableExternalSkills`), `:27-30` (`disableClaudeCodeSkills`,
also triggered by the broad `OPENCODE_DISABLE_CLAUDE_CODE`).

## Inputs / Outputs

**In:** `Config` (`:254`, for `directories()` and `skills.{paths,urls}`) · `Discovery` (`:253`) ·
`FSUtil` (`:256`) · `Global` (`:257`, for `home`) · `RuntimeFlags` (`:258`) · `EventV2Bridge` (`:255`, publishes
`Session.Event.Error` on a malformed frontmatter, `:113-115`).

**Out:** `Info[]`. Three consumers, three very different costs:

| Consumer | Site | Cost |
|---|---|---|
| System prompt `<available_skills>` | `session/system.ts:98-110` → `Skill.fmt(list,{verbose:true})` `:108`; assembled at `session/prompt.ts:1258` | **eager**, metadata only |
| `skill` tool body injection | `tool/skill.ts:45-66`, body at `:51` | lazy, on tool call |
| **Slash command** — full body as message template | `command/index.ts:134-152`, body at `:141-149` | lazy, **and it skips the permission gate** |
| Agent permission whitelist (skill dirs become readable) | `agent/agent.ts:101,111` | — |
| HTTP `GET /skill` | `server/.../groups/instance.ts:53`, handler `handlers/instance.ts:84-87` | — |
| CLI | `cli/cmd/debug/skill.ts:11` | — |

## Extension points

| Point | Where |
|---|---|
| Drop a `SKILL.md` in any root above | `index.ts:21-25` patterns |
| Frontmatter contract: `name` (required, **the dedup key**), `description` (optional) | `isSkillFrontmatter()` `:53-59` |
| Skill without a `description` is **hidden from the prompt but still loadable/invocable** | `fmt()` `:322` filters, `require()` `:294` does not |
| Sibling files (`scripts/`, `references/`) surfaced to the model | `tool/skill.ts:36-43` (rg, `limit: 10`), path advertised `:53` |
| Per-agent gating | `permission: {skill: {"<name>": "deny"}}` → `available()` `:314` and `system.ts:99` |
| Remote skill pack | `config.skills.urls[]` → `discovery.ts:49-132`; server must publish `index.json` with `{skills:[{name,files,version?}]}` (`discovery.ts:13-21`) |

## Token cost

**Eager: metadata only, ~108 tok/skill** — measured on the wire, 433 B/skill.

> **Corrected.** This line used to read "~20 tok/skill (SCAN §4 — measured ~1,930 tok for 19
> skills)", which contradicts itself: 1,930/19 = 101.6. Two independent wire captures put the
> `<available_skills>` block at 7,794–7,798 B for 18 entries = **433 B/skill ≈ 108 tok/skill**.
> The block totals were right; the per-skill unit price was 5.4x low. Cause: descriptions run
> long (438 / 426 / 386 B for the three largest) and every entry carries a full absolute-path
> `<location>` line. This is the number the keep/cut test prices decisions with — re-adding 10
> skills costs ~1,080 tokens, not ~200.
Emitted by `fmt(list,{verbose:true})` `index.ts:324-338` as
`<available_skills><skill><name>…</name><description>…</description><location>…</location></skill>…`,
plus a 2-line preamble at `session/system.ts:103-105`.

**Lazy:** the body (`content`) reaches the model only via `tool/skill.ts:51` or the slash-command path
`command/index.ts:141-149`.

Baseline in this environment (SCAN F5, measured): 18 skills → 1 with
`OPENCODE_DISABLE_EXTERNAL_SKILLS=1`. Sources: `~/.claude/skills` 16, `~/.agents/skills` 16 (15 overlapping),
opencode built-in 1.

## Gotchas

1. **Dedup is a race** (SCAN §7, TESTED). Key = frontmatter `name`, last writer wins (`index.ts:125-139`), and all
   matches are loaded with `concurrency:"unbounded"` (`:240-243`). Across two boots the winner for `to-issues`
   flipped between `~/.claude` and `~/.agents`. It logs a warning (`:126-131`) but does not fail. Harmless while
   the trees are symlinked; a silent correctness bug the moment they diverge.
2. **`/<skill-name>` bypasses the permission gate** (SCAN §7). The `skill` tool asks
   (`tool/skill.ts:27-32`, `permission:"skill"`); the slash path does not — `command/index.ts:141-149` hands the
   raw SKILL.md body to `SessionPrompt.command` (`session/prompt.ts:1355-1481`), which never calls `ctx.ask`.
   Reachable via `POST /session/:sessionID/command`
   (`server/.../groups/session.ts:97,343`, handler `handlers/session.ts:331-337`).
   **Refinement found here, not in SCAN:** the main TUI's slash autocomplete *hides* skill commands
   (`packages/tui/src/component/prompt/autocomplete.tsx:451`), but `opencode run` surfaces them in a dedicated
   skill palette (`cli/cmd/run/footer.command.tsx:783-793`), and the HTTP route accepts any name regardless.
3. **A SKILL.md body containing `` !`cmd` `` executes that shell command on slash-invoke.** Command templates run
   `ConfigMarkdown.shell()` matches through `Process.text` with no permission check
   (`session/prompt.ts:1397-1408`; regex `config/markdown.ts:6`). Skill bodies become templates verbatim
   (`command/index.ts:142`). **TESTED, not just read** — a body containing
   ``!`echo MARKER_$((3*13))_END` `` came back on the wire as `MARKER_39_END`; the arithmetic
   expansion proves a real shell ran. It ran **with `permission: {skill: "deny"}` set**, in a
   process where that deny was provably effective elsewhere (no `skill` tool in the request, no
   `<available_skills>` block at all). So this is not "no gate" — it is "executes despite the
   operator's explicit deny".
4. **`OPENCODE_DISABLE_CLAUDE_CODE_SKILLS` is nearly redundant.** It only drops `.claude` (`index.ts:187`);
   `OPENCODE_DISABLE_EXTERNAL_SKILLS` drops both trees plus the ancestor scan (`:186-203`). The measured
   18→1 belongs to the latter.
5. **The built-in `customize-opencode` skill survives every env flag** — it is seeded in memory at `:278-283`
   *before* discovery, precisely so a disk skill can shadow it. Removing it needs a source edit.
6. **A skill's location dir is added to the agent's read whitelist** (`agent/agent.ts:101,111`) — a skill root
   silently widens `external_directory` permissions.
7. **`skills.urls` fetches and executes-adjacent content over the network at startup** (`discovery.ts:49-132`),
   cached under `<Global.Path.cache>/skills`, version-gated only if the index supplies `version`.
8. **Frontmatter failure is loud but non-fatal**: publishes a session error event and logs, then skips
   (`index.ts:110-119`).

## Strip levers

| Lever | Change at | Effect |
|---|---|---|
| Kill all inherited skills (no source change) | `OPENCODE_DISABLE_EXTERNAL_SKILLS=1` → `index.ts:186` | **−7,112 B ≈ −1,778 tok** (two independent wire captures). 18 → 1 skill, 20 → 3 commands **in a neutral directory only** — the config-directory scan at `:205-208` is unconditional and `config/paths.ts:23-41` walks `.opencode` up from cwd, so in this fork the floor is **2 skills / 12 commands / 9 agents** (TESTED) |
| Kill them properly (survives flag drift) | Delete roots 1–2 at `index.ts:187-202` | same, permanent |
| Remove the last built-in | `index.ts:278-283` | −1 skill, −1 command |
| Stop the eager block entirely | `session/system.ts:98-110` — return early, or `permission: {skill: "deny"}` (`:99` short-circuits) | −all skill metadata; the `skill` tool schema also drops, via `resolveTools()` at `session/llm/request.ts:208-213`. **⚠ This is a token lever, NOT a security lever** — TESTED, `/<skill-name>` still executes the skill (and its shell substitutions) with the deny in force. Only removing skills from disk, or closing the slash bypass below, actually stops execution |
| Cheaper eager format | `index.ts:324-338` — drop `<location>` (absolute paths, ~40 % of each entry) or switch to the terse branch `:340-345` | proportional |
| Close the slash bypass | `command/index.ts:134-152` — skip `source:"skill"` registration, or add an `ctx.ask` in `session/prompt.ts:1355` | removes gotchas 2 and 3 |
| Make dedup deterministic | `index.ts:240-243` — set `concurrency: 1`, or sort `discovered.matches` before `loadSkills` | removes gotcha 1 |
