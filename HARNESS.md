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

Phase docs, newest first:

| Doc | Phase | Read it for |
|---|---|---|
| [docs/REVIEW.md](docs/REVIEW.md) | audit | **Read this before trusting any figure below.** Adversarial audit of every phase-0–3 assumption; what held, what did not |
| [docs/STRIP.md](docs/STRIP.md) | 3 | The strip: what was cut, what it measures, how to run the harness |
| [HARNESS.md](HARNESS.md) | 2 | This file |
| [docs/SCAN.md](docs/SCAN.md) | 1 | Architecture scan. **§4's cost table is superseded** — see REVIEW |
| [docs/PROBE.md](docs/PROBE.md) | 0 | Empirical probes F1–F7; the architecture proof |
| [PLAN.md](PLAN.md) | — | **Superseded in parts and never revised.** §1 and §4 describe an Ink/PTY architecture that F7 replaced, and §0.1's switch table has false rows. It carries a rev-3 errata header; read that first |

## The deliverable

`harness/` is the thing this project actually ships. It is not in the map table below because
it is not part of the fork.

```sh
. ~/Desktop/healbot/harness/env.sh   # zsh or bash only — it guards and refuses elsewhere
opencode
```

| File | Owns |
|---|---|
| `harness/env.sh` | The switch set. `XDG_CONFIG_HOME` isolation + the skill switch + the claude-code switch, each with its measured justification and a NOT-SET list of the switches that break things |
| `harness/config/opencode/opencode.jsonc` | Model pin, `compaction.auto=false` and why, plugin registration |
| `harness/config/opencode/agent/build.md` | The 1,715 B prompt that *replaces* `gpt.txt` |
| `harness/config/opencode/plugin/trim-tools.ts` | Tool-description trimming. Ships OFF (`HARNESS_TRIM_TOOLS=1`) |

Three more files exist on disk (`.gitignore`, `package.json`, `package-lock.json`) and are
**untracked** — opencode seeds a self-ignoring `.gitignore` into any config dir at boot
(`config/config.ts:297-303`), which is the "config loading mutates your disk" trap firing on
our own deliverable. A fresh clone gets the harness without its dependency manifest.

---

## The maps

The maps live at [`fork/`](fork/README.md) — the overlay of everything this project contributes
to its opencode checkout (17 files, plus the exact patch against base `7534d23`, v1.18.5). The
checkout itself is at `opencode/` and is gitignored: it is derived, and
[`fork/README.md`](fork/README.md) says how to rebuild it. Links below point at the overlay, so
they resolve here and on GitHub; the same files sit at the matching paths inside the checkout.

### Harness surface — what enters a session

| Map | Owns |
|---|---|
| [config/CONFIG.MAP.md](fork/packages/opencode/src/config/CONFIG.MAP.md) | Config ingress and merge order; `ConfigPaths.directories()`; the env switches; why `OPENCODE_CONFIG_DIR` does **not** isolate |
| [skill/SKILL.MAP.md](fork/packages/opencode/src/skill/SKILL.MAP.md) | Skill discovery across the two external trees; the dedup race; the `/<skill>` permission bypass |
| [command/COMMAND.MAP.md](fork/packages/opencode/src/command/COMMAND.MAP.md) | Command registry. Mostly a *projection of skills* — "20 commands" is 2 builtins + 18 skills |
| [agent/AGENT.MAP.md](fork/packages/opencode/src/agent/AGENT.MAP.md) | The seven built-in agents; which are structural (`build`, `compaction`) vs cuttable |

### Model-facing cost — where the tokens go

| Map | Owns |
|---|---|
| [session/SESSION.MAP.md](fork/packages/opencode/src/session/SESSION.MAP.md) | System-prompt assembly, session lifecycle, compaction, status events. The v1 engine |
| [tool/TOOL.MAP.md](fork/packages/opencode/src/tool/TOOL.MAP.md) | Tool registry and per-tool description costs — **the largest single token line item** |
| [permission/PERMISSION.MAP.md](fork/packages/opencode/src/permission/PERMISSION.MAP.md) | Permission model; which denies actually remove a tool schema |
| [plugin/PLUGIN.MAP.md](fork/packages/opencode/src/plugin/PLUGIN.MAP.md) | Server plugin host; the 21 hooks and which have live trigger sites |

### Control terminal — where healbot is built

| Map | Owns |
|---|---|
| [tui/TUI.MAP.md](fork/packages/tui/TUI.MAP.md) | The TUI package: SolidJS + OpenTUI, `app.tsx` structure, routes, slot render sites |
| [tui/context/CONTEXT.MAP.md](fork/packages/tui/src/context/CONTEXT.MAP.md) | `sync.tsx` all-session store, sdk, theme, route, event. **The grid's data source** |
| [tui/plugin/PLUGIN.MAP.md](fork/packages/tui/src/plugin/PLUGIN.MAP.md) | TUI plugin runtime: `route.register`, the `api.state` bridge, slots |
| [tui/feature-plugins/FEATURE-PLUGINS.MAP.md](fork/packages/tui/src/feature-plugins/FEATURE-PLUGINS.MAP.md) | Builtin plugins. `diff-viewer` = route pattern, `notifications` = state discriminator |

### v2 tree and public contract

| Map | Owns |
|---|---|
| [core/session/SESSION.MAP.md](fork/packages/core/src/session/SESSION.MAP.md) | The v2 engine; `projector.ts` token accumulation; v2 compaction |
| [plugin/src/PLUGIN-API.MAP.md](fork/packages/plugin/src/PLUGIN-API.MAP.md) | The **public** plugin contract — `TuiPluginApi`, server hooks. What healbot is built against |

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
no Ink, no suspend/resume. Proven by a running spike (PROBE F7), and now **built**:
`feature-plugins/system/healbot.tsx` (12.8 KB) landed at fork `26c9316` and retired the spike.

**Concurrency — TESTED, the founding premise holds.** Four sessions fired simultaneously at one
`opencode serve` finished in 5.72s wall, exactly the slowest single turn, vs 10.45s serially.
The server does not serialize. Per-turn latency degrades under load (2.4–2.7s solo → 2.8–5.7s
at 4-way), so budget ~1.8x throughput at N=4, not 4x. And a session parked on
`permission.asked` does **not** stall the others — three concurrent sessions completed while
the blocked one hung indefinitely.

**Token accounting — the retirement trigger measures OCCUPANCY, not cumulative spend.**
Corrected; the earlier rule here was wrong for its own stated purpose.

- *Why the limit exists*: model quality degrades as the context window bloats. So the quantity
  to threshold is **how full the window is right now**, not what the session has spent over its
  life. `session.tokens` is lifetime spend and answers a different question — the reference
  101-turn session shows 652K input against 8.7M `cache.read`, which says nothing about
  occupancy.
- *What to read*: the assistant message's own `tokens` (`schema/src/v1/session.ts:472-481`),
  delivered on every `message.updated`. Occupancy is `total`, or
  `input + output + cache.read + cache.write` — the same expression `isOverflow` uses
  (`session/overflow.ts:21-33`). **`cache.read` is included**: it is the cached prompt prefix,
  and it is part of the window.
- *Headroom*: `gpt-5.6-sol` is context 1,050,000 / `limit.input` 922,000. A 350K threshold
  leaves ~570K before the hard ceiling.
- *`session.tokens` is still useful* — for cost, and it is genuinely cumulative and monotonic
  through compaction (VERIFIED + TESTED, 40/40 sessions match `SUM(step-finish)` exactly). Just
  not for retirement.
- *If you do threshold cumulative spend anyway*: `input + output` crosses 350K at turn 90 of
  101; `input + output + reasoning` — the rule this file used to recommend — crosses at
  **turn 77**, not turn 90. The old text attached SCAN's turn-90 measurement to a different
  formula.

**Compaction is off, so overflow is a HARD ERROR.** `overflow.ts:28` returns `false` outright
when `compaction.auto === false`, and `processor.ts:607-613` then sets `finish: "error"` and
status idle. The grid must render that as its own state; it arrives looking like an ordinary
idle-after-error.

**Handoff.** `fork` is disqualified — TESTED, a fork reports 0 tokens at creation then climbs
to exactly the parent's total within ~3s. `summarize` mutates in place and adds tokens. Only
`POST /session` + a seed prompt yields a zero-token session. Retire with
`PATCH time.archived`, never `DELETE` (hard recursive delete) — **but see the trap below:
archiving hides a session from nothing.**

**Engine choice is load-bearing, not a preference.** v1 (`POST /session/{id}/message`) and v2
(`POST /api/session/{id}/prompt`) have incompatible token accounting *and* incompatible event
vocabularies. Both are mounted on the same port by the shipped binary. **Use v1.** See the two
traps below.

**Where the tokens actually are.** Under `openai/gpt-5.6-sol` in a neutral directory: tool
definitions ~19,900 B dominate, then base prompt 9,284 B (`gpt.txt`), skills ~7,900 B,
instructions, `<env>` ~957 B, `<mcp_instructions>` 0 B. The stripped harness serves ~21.3 KB
against a ~36.7 KB baseline. **Both figures are neutral-directory measurements** — in the fork
the project AGENTS.md adds ~9 KB to *both* arms, so the percentage drops from ~41% to ~33%
while the absolute saving stays ~15.4 KB. Earlier `anthropic.txt` figures (~5,740 / ~2,360 /
~2,050 / ~1,930 tok) described a model this harness does not run; they are superseded.

**Cheapest strip levers**, in order of measured value:
1. An agent's own `prompt` **replaces** the base prompt (ternary, not append) — one
   `agent/*.md` drops 7,569 B (`agent/AGENT.MAP.md`). **Per-agent**: `build`, `plan` and
   `general` each define no `prompt` (`agent/agent.ts:141,156,182`), so overriding `build`
   leaves every `plan` session and every `general` subagent on the full `gpt.txt`.
2. `OPENCODE_DISABLE_EXTERNAL_SKILLS` — measured Δ **7,112 B** (two independent wire captures
   agreed exactly). 18 skills → 1 and 20 commands → 3 *in a neutral directory*; in the fork the
   floor is 2 skills / 12 commands, because the config-directory scan is unconditional.
3. `tool.definition` plugin hook rewrites any builtin tool's description — zero source change,
   aimed at the biggest block, but it recovered only 506 B and ships OFF
   (`plugin/PLUGIN.MAP.md`). Most of that block turned out to be load-bearing.

---

## Traps

Things that will silently cost correctness. All cited in the maps.

| Trap | Where |
|---|---|
| **The whole `session.next.*` event family is v2-only.** Zero publishers in `packages/opencode/src` (4 hits, all consumers); the sole publisher factory is `core/src/session/runner/publish-llm-event.ts`, imported once by the v2 runner. So on the v1 path — the one you must use — `session.next.tool.called`, `.context.updated` and `.compaction.started/.ended` never fire. `PLAN.md:57-59` lists them as "verified event types" and builds frame contents on them | REVIEW |
| **The v2 engine never writes `session.tokens`.** `applyUsage` has 5 call sites, all in v1 projections; v2 usage lands on the message row instead. TESTED — a v2 turn burned 3,399 tokens and left the session row at `{0,0,0,0,0}`. A v2-driven session is invisible to any retirement trigger | `core/session/SESSION.MAP.md` |
| **`GET /api/session/{id}/context` returns an EMPTY array for v1 sessions.** It reads `SessionMessageTable`, which v1 never writes. TESTED: the 101-turn reference session has 0 `session_message` rows and 738 `part` rows. `PLAN.md:143-144` names this endpoint as the token source | REVIEW |
| **`PATCH time.archived` hides a session from nothing.** `ListInput` has no `archived` field; `listByProject` (behind `GET /session`) has no `time_archived` predicate; the v2 list does not filter; `grep -rn archived packages/tui/src` → zero hits. Only `listGlobal` filters, reachable solely via `GET /experimental/session`. **The grid must filter retired sessions itself** | REVIEW |
| **`client.session.list()` cannot enumerate across projects** — hard-scoped to `ctx.project.id` (`session.ts:548-555`), and `ListInput` has no `projectID` to widen it. Worse, the documented tripwire `api.state.session.count()` reads `sync.data.session.length` — the *same narrowed store*, so it can never detect the misses. Use `client.experimental.session.list()` (cursor-paginated) | `tui/context/CONTEXT.MAP.md` |
| **An "always" permission applies to every session in the process** — approvals are instance-wide, never persisted, no sessionID filter. Directly hostile to a multi-session terminal | `permission/PERMISSION.MAP.md` |
| **No timeout on a pending permission** — a client that ignores `permission.asked` hangs that tool call forever. TESTED: it hangs indefinitely, but it does **not** stall other sessions | `permission/PERMISSION.MAP.md` |
| **`permission: {skill: "deny"}` does not stop a skill.** TESTED in one process: the deny removes the `skill` tool *and* the whole `<available_skills>` block, yet `/<skill-name>` still executes the skill to completion, shell substitutions included. Only removing skills from the prompt closes it | `skill/SKILL.MAP.md` |
| **Instruction files do NOT stop at the first ancestor.** The `break` is over the *filename* list; `fs-util.ts:154-166` collects every `AGENTS.md` up to the worktree root. The source comment at `instruction.ts:123` claims the opposite and is wrong. In the fork, a session under `src/session/llm` ingests 22,273 B of AGENTS.md | `session/SESSION.MAP.md` |
| **The 18→1 skill floor is cwd-dependent** — the config-directory scan is unconditional. In the fork the harness delivers 2 skills / 12 commands / 9 agents, readmitting upstream repo tooling | `skill/SKILL.MAP.md` |
| **`OPENCODE_CONFIG_DIR` merges rather than isolates** — it is worse than a no-op. Same for `OPENCODE_CONFIG` and `OPENCODE_CONFIG_CONTENT`. Only `XDG_CONFIG_HOME` replaces | `config/CONFIG.MAP.md` |
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
| ~~`healbot-spike` occupies `/healbot` in the palette~~ — resolved at fork `26c9316`: the spike was deleted in the same commit that added the real grid, so `/healbot` now belongs to `healbot.tsx` | `tui/feature-plugins/FEATURE-PLUGINS.MAP.md` |

---

## Closed

| Was open | Answer |
|---|---|
| Does the v2 engine write `session.tokens`? | **No.** Settled at TESTED tier — see below. Drive v1 |
| Does `$XDG_CONFIG_HOME` fully redirect global config? | **Yes**, TESTED. It is the harness's isolation mechanism (`docs/STRIP.md`) |
| Re-measure standing context under `gpt-5.6-sol` | **Done** (`docs/STRIP.md`), corrected in `docs/REVIEW.md` |
| Do N sessions actually run concurrently on one server? | **Yes**, TESTED. And a blocked permission does not stall the others |
| Is the yellow border gated behind `OPENCODE_ENABLE_QUESTION_TOOL`? | **No** (SCAN C3). But confirm `flags.client` for a non-CLI client — the gate is an allowlist |

### The v2 token question — settled

Earlier this file recorded an inconclusive result: `POST /api/session/{id}/prompt` "produces no
assistant turn after 60s". **That is not reproducible.** A retry got a complete turn in ~1.2s;
the earlier failures are still in the DB, each holding only `agent-switched` + `model-switched`
rows pinning `gpt-5.6-sol`. The negative was model-specific, not structural — v2 is live.

The answer, from source and confirmed by execution: **v2 does not write `session.tokens`.**
`applyUsage` is called only from `SessionV1` projections (`core/src/session/projector.ts:90,
286, 304, 327, 328`). The v2 runner publishes `SessionEvent.Step.Ended`
(`runner/publish-llm-event.ts:396-400` → `runner/llm.ts:326-333`), which projects to the
message row via `message-updater.ts:209-214`. TESTED: a v2 prompt burned
`{input: 3381, output: 4, reasoning: 14}` and left the session row at `{0,0,0,0,0}`.

**So `v1 only` is a hard constraint, not a workaround.** Also note `docs/SCAN.md:79-81`'s
"v2 is reachable only via the separate `lildax` bin" is refuted — the `opencode` binary wires
the v2 handlers with an in-process execution backend (`server.ts:102, :177-181, :299-302`).
The v2 endpoint is one typo away on the same port.

If you ever must use v2, sum `SessionMessageTable.data.tokens`; `message-updater.ts:185-206`
appends a new assistant message per step, so the `draft.tokens =` assignment cannot lose
multi-step turns.

---

## Still open

| Question | Why it matters | Cost |
|---|---|---|
| Does `flags.client` land in the `["app","cli","desktop"]` allowlist when the grid drives sessions? | If not, the `question` tool is never registered and YELLOW never fires — for exactly the use case this project exists for | ~10 min |
| Can an **external** plugin register a route, or only a builtin? | F7 proved a builtin can and that `route.register` is on the public API. The external case is untested, and it decides whether the grid must live inside the fork | ~20 min |
| Has `healbot.tsx` actually been **run**? | It replaced the spike at fork `26c9316` and is 2.5x its size. F7's TESTED evidence covers the spike at `0fdcfb6`, not this. Nothing in the tree records the grid rendering, owning the keyboard, or reading live session state | ~15 min |
| Does the grid handle the traps above? | Especially: `session.created` unhandled, RED silent under `--auto`, the project-scoped `session.list()`, and archived sessions never leaving the list | review |
| What exactly counts as "continuity intact" for a handoff? | It is a Phase 4 exit-gate clause with no definition and no check | design |
| Make the retirement threshold configurable | The gate says "driven past the retirement threshold"; at 350K on a frontier model that is expensive to exercise. A config key lets it be tested at 5K | small |
