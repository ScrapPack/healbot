# HARNESS.md — root index

Navigation layer for the healbot fork. One `.MAP.md` per core subsystem, living **inside**
the directory it describes. This file indexes them.

**Exit test:** from this file alone you should be able to name the file that owns any given
behavior. If you can't, the map is wrong — fix the map, not your memory.

**Naming:** map files are `<DIR>.MAP.md`. The `.MAP` infix is not cosmetic — `SKILL.md`
collides with opencode's skill-manifest glob (`**/SKILL.md`), and `AGENTS.md` / `CLAUDE.md` /
`CONTEXT.md` are auto-ingested into the model's context window
(`packages/opencode/src/session/instruction.ts:64-68`), which is the exact cost this project
exists to remove. **Never create those four filenames anywhere in this tree.**

Phase docs: [PLAN.md](PLAN.md) · [docs/PROBE.md](docs/PROBE.md) (phase 0) ·
[docs/SCAN.md](docs/SCAN.md) (phase 1)

---

## The maps

### Harness surface — what enters a session

| Map | Owns |
|---|---|
| [config/CONFIG.MAP.md](opencode/packages/opencode/src/config/CONFIG.MAP.md) | Config ingress and merge order; `ConfigPaths.directories()`; the env switches; why `OPENCODE_CONFIG_DIR` does **not** isolate |
| [skill/SKILL.MAP.md](opencode/packages/opencode/src/skill/SKILL.MAP.md) | Skill discovery across the two external trees; the dedup race; the `/<skill>` permission bypass |
| [command/COMMAND.MAP.md](opencode/packages/opencode/src/command/COMMAND.MAP.md) | Command registry. Mostly a *projection of skills* — "20 commands" is 2 builtins + 18 skills |
| [agent/AGENT.MAP.md](opencode/packages/opencode/src/agent/AGENT.MAP.md) | The seven built-in agents; which are structural (`build`, `compaction`) vs cuttable |

### Model-facing cost — where the tokens go

| Map | Owns |
|---|---|
| [session/SESSION.MAP.md](opencode/packages/opencode/src/session/SESSION.MAP.md) | System-prompt assembly, session lifecycle, compaction, status events. The v1 engine |
| [tool/TOOL.MAP.md](opencode/packages/opencode/src/tool/TOOL.MAP.md) | Tool registry and per-tool description costs — **the largest single token line item** |
| [permission/PERMISSION.MAP.md](opencode/packages/opencode/src/permission/PERMISSION.MAP.md) | Permission model; which denies actually remove a tool schema |
| [plugin/PLUGIN.MAP.md](opencode/packages/opencode/src/plugin/PLUGIN.MAP.md) | Server plugin host; the 21 hooks and which have live trigger sites |

### Control terminal — where healbot is built

| Map | Owns |
|---|---|
| [tui/TUI.MAP.md](opencode/packages/tui/TUI.MAP.md) | The TUI package: SolidJS + OpenTUI, `app.tsx` structure, routes, slot render sites |
| [tui/context/CONTEXT.MAP.md](opencode/packages/tui/src/context/CONTEXT.MAP.md) | `sync.tsx` all-session store, sdk, theme, route, event. **The grid's data source** |
| [tui/plugin/PLUGIN.MAP.md](opencode/packages/tui/src/plugin/PLUGIN.MAP.md) | TUI plugin runtime: `route.register`, the `api.state` bridge, slots |
| [tui/feature-plugins/FEATURE-PLUGINS.MAP.md](opencode/packages/tui/src/feature-plugins/FEATURE-PLUGINS.MAP.md) | Builtin plugins. `diff-viewer` = route pattern, `notifications` = state discriminator |

### v2 tree and public contract

| Map | Owns |
|---|---|
| [core/session/SESSION.MAP.md](opencode/packages/core/src/session/SESSION.MAP.md) | The v2 engine; `projector.ts` token accumulation; v2 compaction |
| [plugin/src/PLUGIN-API.MAP.md](opencode/packages/plugin/src/PLUGIN-API.MAP.md) | The **public** plugin contract — `TuiPluginApi`, server hooks. What healbot is built against |

---

## Behavior → file

| To find… | Go to |
|---|---|
| why a skill/command appears at all | `skill/SKILL.MAP.md` → `command/COMMAND.MAP.md` |
| what text the model receives before you type | `session/SESSION.MAP.md` (assembly chain) + `tool/TOOL.MAP.md` |
| how to cut standing token cost | `tool/TOOL.MAP.md` (biggest), then `agent/AGENT.MAP.md` (prompt replacement) |
| how config is loaded / how to isolate it | `config/CONFIG.MAP.md` |
| session token accounting / the 350K trigger | `core/session/SESSION.MAP.md` + `session/SESSION.MAP.md` |
| what drives a grid border color | `tui/context/CONTEXT.MAP.md` (store) + `session/SESSION.MAP.md` (event origins) |
| how to register the grid route | `tui/plugin/PLUGIN.MAP.md` + `plugin/src/PLUGIN-API.MAP.md` |
| what to copy when building the grid | `tui/feature-plugins/FEATURE-PLUGINS.MAP.md` |

---

## Load-bearing facts

Established across phases 0–2. Each is cited in the map named.

**Architecture.** The grid is a plugin-registered **route**, not an `app`-slot overlay and not
a separate app (`tui/plugin`). Focus is `api.route.navigate("session", {sessionID})` — no PTY,
no Ink, no suspend/resume. Proven by running spike, `feature-plugins/system/healbot-spike.tsx`.

**Token accounting.** `session.tokens` is cumulative and monotonic — compaction never resets
it (`core/session`). Threshold on `input + output + reasoning` and **exclude `cache.read`**:
including it crosses 350K at turn 17 of 101 instead of turn 90.

**Handoff.** `fork` is disqualified — TESTED, a fork reports 0 tokens at creation then climbs
to exactly the parent's total within ~3s. `summarize` mutates in place and adds tokens. Only
`POST /session` + a seed prompt yields a zero-token session. Retire with
`PATCH time.archived`, never `DELETE` (hard recursive delete).

**Where the tokens actually are.** Tool definitions dominate (~5,740 tok), ahead of
instructions (~2,360), base prompt (~2,050), skills (~1,930). Measured under
`anthropic.txt` — **re-measure under `gpt-5.6-sol`**, which routes to `gpt.txt` (9,284 B) and
swaps `edit`+`write` out for `apply_patch` (`tool/TOOL.MAP.md`).

**Cheapest strip levers**, in order:
1. `tool.definition` plugin hook rewrites any builtin tool's description and schema — zero
   source change, aimed at the biggest block (`plugin/PLUGIN.MAP.md`).
2. An agent's own `prompt` **replaces** the base prompt (ternary, not append) — one
   `agent/*.md` drops ~2,050 tok (`agent/AGENT.MAP.md`).
3. `OPENCODE_DISABLE_EXTERNAL_SKILLS` — 18 skills → 1, 20 commands → 3 (measured, phase 0).

---

## Traps

Things that will silently cost correctness. All cited in the maps.

| Trap | Where |
|---|---|
| **An "always" permission applies to every session in the process** — approvals are instance-wide, never persisted, no sessionID filter. Directly hostile to a multi-session terminal | `permission/PERMISSION.MAP.md` |
| **No timeout on a pending permission** — a client that ignores `permission.asked` hangs that tool call forever | `permission/PERMISSION.MAP.md` |
| **RED never fires under `--auto`** — `sync.tsx` auto-replies before writing to the store | `tui/context/CONTEXT.MAP.md` |
| **`session.created` is not handled** by the sync store — freshly spawned sessions don't appear until a later `session.updated` | `tui/context/CONTEXT.MAP.md` |
| **`listSessions()` has a 30-day window + current-subdirectory filter** — a cross-directory grid silently misses sessions | `tui/context/CONTEXT.MAP.md` |
| **`store.message[sid]` caps at 100 and drops evicted parts**, grid-wide | `tui/context/CONTEXT.MAP.md` |
| **There is no `api.state.session.list()`** — the grid must direct-import `useSync`; it cannot be patched at the host layer | `tui/plugin/PLUGIN.MAP.md` |
| **`route.navigate("session", …)` discards every param but `sessionID`** | `tui/plugin/PLUGIN.MAP.md` |
| **Scoped denies do NOT remove a tool schema** — only blanket `*` denies do, and a later narrow allow un-hides a blanket-denied tool | `permission/PERMISSION.MAP.md` |
| **`tool/read.ts` attaches nearby `AGENTS.md` on every file read** — unbounded cost, invisible to standing-context measurement | `session/SESSION.MAP.md` |
| **`bash`'s description is generated at runtime**, not stored — editing `shell.txt` looks like the fix and does almost nothing | `tool/TOOL.MAP.md` |
| **Skill dedup is a race** — winner varies by I/O completion order across boots | `skill/SKILL.MAP.md` |
| **`` !`cmd` `` in a SKILL.md body shell-executes on slash-invoke**, no permission check | `skill/SKILL.MAP.md` |
| **The built-in agent table exists twice** (v1 and v2) — editing one does not change the other | `agent/AGENT.MAP.md` |
| **Config loading mutates your disk every boot** — `$schema` injection, file seeding, `.gitignore` writes | `config/CONFIG.MAP.md` |
| **`api.event` metadata arg works but is untyped** — needs a cast; the grid needs it for cross-directory routing | `plugin/src/PLUGIN-API.MAP.md` |
| `permission.ask` plugin hook is **dead** — declared, zero trigger sites | `plugin/PLUGIN.MAP.md` |
| `healbot-spike` occupies `/healbot` in the palette until removed | `tui/feature-plugins/FEATURE-PLUGINS.MAP.md` |

---

## Open

| Question | Status |
|---|---|
| **Does the v2 engine write `session.tokens`?** Two agents contradict each other: one says only v1 calls `applyUsage`, so v2-driven sessions stay at zero forever; the other says accounting is engine-independent because the v1 binary imports the same projector. **Unresolved.** My empirical attempt was inconclusive — see below | **OPEN** |
| Does `$XDG_CONFIG_HOME` fully redirect global config? Cheapest path to real isolation | untested |
| Re-measure standing context under `gpt-5.6-sol` (`gpt.txt`, `apply_patch` swap) | not done |

### On the v2 token question — what I actually established

I tried to settle it and could not. Recording the negative result rather than a guess.

- On the **1.17.10 binary**: `POST /api/session/{id}/prompt` returns `admittedSeq: 1`, then
  produces **zero messages**. Nothing executes.
- On the **1.18.5 source build** (`bun dev`): the same call stores the **user** message and
  still produces **no assistant turn** after 60s. No errors in the log.
- `session.tokens` stayed `{0,0,0,0,0}` throughout — but since **no LLM step ever completed**,
  that zero is not evidence about accounting.

**Practical resolution:** drive sessions through the **v1** path
(`POST /session/{id}/message`), where token accumulation is TESTED working (phase 1, exact
DB-sum match on a real 101-turn session). That sidesteps the contradiction entirely. Revisit
only if the control terminal needs v2-specific behavior.
