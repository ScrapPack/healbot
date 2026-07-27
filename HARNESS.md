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
| [NEXT.md](NEXT.md) | 8 | **Start here if you are a fresh session.** The prompt to continue the build, and the traps that silently produce wrong results instead of errors |
| [docs/RELAY.md](docs/RELAY.md) | 7 | **The gate was never per-turn.** `finished()` read a per-step field, so the soft gate aborts the turn in flight and `RETIRE_HARD` is inert — five load-bearing sentences corrected. Plus the double-retire race closed by deleting the grid's copy of `retire()`: `x` now relays a request and the server plugin is the only implementation |
| [docs/HEADLESS.md](docs/HEADLESS.md) | 6 | Automatic retirement moved to a **server** plugin so it runs with no client attached — and why "move it to plugin scope" was the wrong mechanism for the right goal. Plus focus and `question.rejected` closed, and the control agent built |
| [docs/HARDEN.md](docs/HARDEN.md) | 5 | The Phase 4 audit and what it forced: six defects fixed, the rig's vacuous assertions replaced, and `serve` + `attach` built — which closed the cold-start reconcile that was recorded here as *blocked* |
| [docs/VERIFY.md](docs/VERIFY.md) | 4 | The control terminal, verified on `gpt-5.6-sol`: answering a blocked session from the grid. What is TESTED, what is unreachable, and why the first attempt was void |
| [docs/REVIEW.md](docs/REVIEW.md) | audit | **Read this before trusting any figure below.** Adversarial audit of every phase-0–3 assumption; what held, what did not |
| [docs/STRIP.md](docs/STRIP.md) | 3 | The strip: what was cut, what it measures, how to run the harness |
| [HARNESS.md](HARNESS.md) | 2 | This file |
| [docs/SCAN.md](docs/SCAN.md) | 1 | Architecture scan. **§4's cost table is superseded** — see REVIEW |
| [docs/PROBE.md](docs/PROBE.md) | 0 | Empirical probes F1–F7; the architecture proof |
| [PLAN.md](PLAN.md) | — | **Superseded in parts and never revised.** §1 and §4 describe an Ink/PTY architecture that F7 replaced, and §0.1's switch table has false rows. It carries a rev-4 errata header; read that first |

## The deliverable

`harness/` is the thing this project actually ships. It is not in the map table below because
it is not part of the fork.

```sh
. ~/Desktop/healbot/harness/env.sh   # zsh or bash only — it guards and refuses elsewhere
opencode
```

For a **fleet** — one long-lived server, the control terminal as a client, sessions that outlive
the terminal — use `fleet.sh` instead. It is the architecture `PLAN.md` assumed all along:

```sh
~/Desktop/healbot/harness/fleet.sh [project-dir] [port]   # default port 4096
```

| File | Owns |
|---|---|
| `harness/env.sh` | The switch set. `XDG_CONFIG_HOME` isolation + the skill switch + the claude-code switch, each with its measured justification and a NOT-SET list of the switches that break things |
| `harness/fleet.sh` | `opencode serve` + `opencode attach`: sessions survive the terminal, and the cold-start reconcile becomes reachable. TESTED 10/10 end to end, plus 21/21 on the reconcile itself (`docs/HARDEN.md`). Resolves the fork checkout automatically — the released binary has no grid |
| `harness/config/opencode/opencode.jsonc` | Model pin, `compaction.auto=false` and why, plugin registration, and the global `healbot_*: deny` that keeps the control tools out of every other session's prompt |
| `harness/config/opencode/agent/build.md` | The 1,715 B prompt that *replaces* `gpt.txt` |
| `harness/config/opencode/agent/control.md` | **The control agent** — build-order step 5. `mode: primary`, and the `healbot_*: allow` that wins back the globally denied tools. TESTED 14/14 + 15/16 (`docs/HEADLESS.md` §3) |
| `harness/config/opencode/plugin/healbot.ts` | **ALL retirement, and the control tools.** Since Phase 7 this is the only implementation of retirement anywhere: the automatic gate, the operator's `x` (relayed as a metadata request), and `healbot_retire` all run the same `retire()` in this one process. It runs headless, so a fleet with no client attached still retires. TESTED 20/20 end to end with no TUI in the process table (`docs/HEADLESS.md`), plus 9/9 on the relay (`docs/RELAY.md`) |
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
| session token accounting / the retirement trigger | `core/session/SESSION.MAP.md` + `session/SESSION.MAP.md` |
| what drives a grid border color | `tui/context/CONTEXT.MAP.md` (store) + `session/SESSION.MAP.md` (event origins) |
| how to register the grid route | `tui/plugin/PLUGIN.MAP.md` + `plugin/src/PLUGIN-API.MAP.md` |
| what to copy when building the grid | `tui/feature-plugins/FEATURE-PLUGINS.MAP.md` |

---

## Load-bearing facts

Established across phases 0–2. Each is cited in the map named.

**Architecture.** The grid is a plugin-registered **route**, not an `app`-slot overlay and not
a separate app (`tui/plugin`). Focus is `api.route.navigate("session", {sessionID})` — no PTY,
no Ink, no suspend/resume. Proven by a running spike (PROBE F7), and now **built**:
`feature-plugins/system/healbot.tsx` landed at fork `26c9316` and retired the spike. **Byte and
line counts are deliberately not quoted here** — they were stated three times across this repo
and all three were stale within a day. `wc` the file.

**Answering from the grid works — TESTED, and it is the feature the project exists for.** Four
sessions on one server, three finishing real tool-using turns in 6.1 s wall while the fourth sat
blocked; `a` docks the session route's own `PermissionPrompt` / `QuestionPrompt` **below** the
grid, which keeps rendering; the reply clears the block server-side *and* the answer reaches the
model, which resumes and acts on it. The route never changes. Same result for a `question` the
model chose to ask unforced. See `docs/VERIFY.md`.

**Grid keybindings must be `OPENCODE_BASE_MODE` + `enabled: !answering()` — both, not either.**
`mode` is a *require*-condition (`keymap.tsx:56-60`), so a mode-less binding set is live in
**every** mode. `QuestionPrompt` pushes its own mode and binds `tab/h/l/j/k/return/escape` plus
digits (`question.tsx:129-134, :227-264`); `PermissionPrompt` pushes no mode and binds
`h/l/return/escape` in base mode (`permission.tsx:568-608`). Base mode handles the first,
`enabled` handles the second. TESTED under both prompts: `j/k/l/h` leave the grid cursor still.

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
- *Headroom* — **this row was wrong and the correction is the most important number in this
  file.** It used to read: "`gpt-5.6-sol` is context 1,050,000 / `limit.input` 922,000. A 350K
  threshold leaves ~570K before the hard ceiling." **MEASURED at the shipped default: the real
  ceiling is ~360K.** A session driven up took its last successful turn at occupancy **359,829**
  and then failed **25 consecutive turns** with the provider's `ContextOverflowError` ("Your
  input exceeds the context window of this model"). The registry's 922,000 does not describe
  this provider path. Actual margin at a 350K threshold: **~10K, under 3%** — roughly one large
  tool result. Since `compaction.auto:false` disables opencode's own overflow check
  (`overflow.ts:28`), nothing catches it before the provider does, and by then the turn is lost.
  **The 350K default fired too late to be a guard. Lowered to 256,000**, with a second HARD gate
  at 330,000 — see the retirement rows below. (`docs/HARDEN.md` §6, §8)
- *`session.tokens` is still useful* — for cost, and it is genuinely cumulative and monotonic
  through compaction (VERIFIED + TESTED, 40/40 sessions match `SUM(step-finish)` exactly). Just
  not for retirement.
- *If you do threshold cumulative spend anyway*: `input + output` crosses 350K at turn 90 of
  101; `input + output + reasoning` — the rule this file used to recommend — crosses at
  **turn 77**, not turn 90. The old text attached SCAN's turn-90 measurement to a different
  formula.

**ALL retirement is a SERVER plugin, not part of the grid — automatic since Phase 6, manual since Phase 7.**
`harness/config/opencode/plugin/healbot.ts` runs inside `opencode serve`, driven off
`message.updated` (whose `properties.info` is the whole assistant message, tokens included). The
grid keeps painting `RETIRE` off `RETIRE_AT` and keeps the `x` binding, but owns no retirement
logic: its `createEffect` was deleted in Phase 6 and its copy of `retire()` in Phase 7. `x` now
writes `metadata.healbot.retireRequested` via `session.update`, which reaches the plugin as an
ordinary `session.updated` event (`session.ts:748` publishes the whole session from the shared
`patch()`), and the plugin performs it. No endpoint was registered because none can be — the server
plugin surface is hooks only and `event` is receive-only. Consequence, and it is bigger than Phase
6's: **run the fork without the harness config and NEITHER automatic nor manual retirement works** —
the border still goes purple, `x` still writes its request, and nothing is listening.
`docs/RELAY.md`.

**The gate fires at a STEP boundary, not at the end of a turn — and there is only ONE live gate.**
Corrected in Phase 7 after a review; every artifact in this repo asserted the opposite, including
the two rows in *Still open* below. `processor.ts:443-445` writes `finish` and `tokens` in the same
mutation at every `step-finish`, and `:445` is the ONLY site in the session tree that writes a
non-zero `tokens`. So every `message.updated` that carries occupancy also carries a set `finish` —
usually `"tool-calls"`, i.e. mid-turn. MEASURED on 733 real assistant messages with occupancy > 0:
**zero** had a null `finish` (677 `tool-calls`, 56 `stop`).

- *What actually happens*: the gate fires at the first step boundary above `RETIRE_AT` and
  `retire()` aborts the turn in flight. Overshoot is bounded by one STEP (~65K) rather than one
  turn (~170K) — **better** than the behaviour that was designed and documented, arrived at by
  accident.
- *`RETIRE_HARD` is INERT.* Its only consumer is `consider()`'s `if (!stepOver && !hard) return`,
  and `stepOver` is true on 733/733, so `hard` is dominated and never decides anything. No rig has
  executed the branch. `HEALBOT_RETIRE_HARD` is a knob with no effect. It is kept, and documented
  as dead, because it becomes load-bearing again the day `stepFinished()` is made per-turn.
- *The hinge is one function.* `stepFinished()` (`healbot.ts`) vs opencode's own `prompt.ts:1295`,
  which excludes `["tool-calls","unknown"]`. Swapping them switches the whole harness to per-turn
  retirement and resurrects the hard gate. Nothing else changes.
- *What this does NOT change*: the ~360K ceiling, the 256,000 default, or the handoff. The abort
  discards the in-flight step, so everything handed over comes from what is already persisted —
  todos, diffs, last completed text. It does.

**Compaction is off, so overflow is a HARD ERROR — and the grid now renders it. Built in Phase
5; before that it painted GREEN.** `overflow.ts:28` returns `false` outright when
`compaction.auto === false`, and `processor.ts:607-613` then sets `finish: "error"` and status
idle. That idle is the trap: `status.ts:41` publishes `{type:"idle"}` *before* `:44` deletes the
key, `sync.tsx:310` stores it, and the grid's `stateOf` had no error branch — so a session that
died on an expired credential, a crashed tool or a filled window was pixel-identical to one that
finished its task, in `theme.success`, labelled `done`. On a terminal whose whole premise is that
border colour carries truth, that is the worst available failure: silent, and biased toward
"everything finished". The state is tracked out of band from `session.error` (the only event that
carries the fact — `session-status-event.ts` has no `error` member) and cleared when the session
next goes busy. `retry` is split out of `busy` at the same time, per `PLAN.md:384`'s border table.

**Handoff.** `fork` is disqualified — TESTED, a fork reports 0 tokens at creation then climbs
to exactly the parent's total within ~3s. `summarize` mutates in place and adds tokens. Only
`POST /session` + a seed prompt yields a zero-token session. Retire with
`PATCH time.archived`, never `DELETE` (hard recursive delete) — **but see the trap below:
archiving hides a session from nothing.**

**`prompt_async` works — the audit's "defect" is REFUTED, TESTED.** It acks in 0.01s against
5.1s for the synchronous `POST /session/{id}/message`, and the turn completes ~2s after the ack
with `finish: "stop"` and the same answer, same model, tokens accrued, no error published. The
spawn-and-seed path of `PLAN.md:356` can be built on it as written. See the row in Traps for the
race that made it look broken. A freshly spawned + seeded session starts at its **own**
occupancy — measured floor ~4.8K total on turn one, almost all `cache.read`, which is the
standing-context prefix. Any retirement threshold set for testing must clear that floor.

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
| **TUI plugin scope has NO Solid owner.** `plugin/tui/runtime.ts`'s `load()` crosses an `await` before `activatePluginEntry` invokes `tui(api)` at `:529`, so the synchronous `createRoot` window has closed. TESTED: `getOwner()` is `null` there. `createSignal`/`createMemo` work (they never touch the owner), but a `createEffect` is **never disposed** and a bare `onCleanup` is a **silent no-op**. This is why "move the retirement trigger to plugin scope" was rejected — and it would not have made it headless anyway, since a TUI plugin needs a TUI | `docs/HEADLESS.md` |
| **The retirement gate fires per STEP and aborts the turn in flight; `RETIRE_HARD` is INERT.** Anything reasoning about "the turn is allowed to finish" is reasoning about a design that was never built. `processor.ts:443-445` writes `finish` and `tokens` in one mutation at every `step-finish`, and `:445` is the only non-zero `tokens` write in the tree, so `stepFinished()` is true on 733/733 real messages carrying occupancy and the hard gate is dominated. The hinge back to per-turn is one function — opencode's own `prompt.ts:1295` | `docs/RELAY.md` §1 |
| **Retirement happens in exactly ONE process, and the grid's `x` is only a request.** It writes `metadata.healbot.retireRequested` and returns; if the harness config is not loaded, `x` looks like it worked and nothing retires. Before Phase 7 `x` worked without the harness. The coupling is untyped in both directions — a rename on either side silently stops manual retirement, with no error and no log — which is why `probe_twin.py` mutates both ends | `docs/RELAY.md` §2 |
| **`verify_headless_retire.py` cannot be pointed at the shipped threshold.** It hardcodes `THRESHOLD = 20_000` at `:52` and forces it into the SERVER's env at `:96-103`, and `rig.py:159` applies `env_extra` last — there is no override to remove. Its one prompt reads ≤50 KB (`read.ts:16`) and it asserts `len(user_turns) == 1`, so editing the constant just times out after 15 minutes. The arming half is covered free by `probe_headless_arm.py` instead | `docs/RELAY.md` §4 |
| **A server plugin gets the v1 SDK client; the TUI gets the v2 one, and they diverge silently.** The v1 client has **no `permission` and no `question` sub-client at all**; its `SessionUpdateData["body"]` is `{title?}` with no `time.archived`; its `SessionCreateData["body"]` has no `directory`. The SERVER accepts all three (`groups/session.ts:53-57`, `handlers/session.ts:200-201`) — the generated v1 types are narrower than the routes. `healbot.ts` writes the requests out with `fetch` rather than casting past the types three times | `docs/HEADLESS.md` |
| **The session-route sidebar is gated on `width > 120`** (`routes/session/index.tsx:264`), and it is the only thing that renders a session's id. The navigation rigs use exactly 120 so cells cannot fit one row — so a focus assertion written at that width measures terminal geometry, not behaviour. TESTED, it reported a failure that way | `docs/HEADLESS.md` §2 |
| **There is no key that returns from a session to the grid.** `healbot.open` is namespace `palette` / slashName `healbot` with no binding anywhere; the routes back are `ctrl+p` or typing `/healbot`. `returnRoute` cannot help — `adapters.tsx:47-52` drops every param but `sessionID`. The selection index does survive, in the plugin closure | `docs/HEADLESS.md` §2 |
| **A plugin module may export ONLY functions.** `getLegacyPlugins` (`plugin/index.ts:95-108`) iterates `Object.values(mod)` and throws `TypeError: Plugin export is not a function` on the first that is not — so one exported constant disables the whole plugin, at load time, in a log line nobody reads. `applyPlugin` catches and publishes rather than crashing, so the symptom is a healthy server with a missing feature | `docs/HEADLESS.md` |
| **The whole `session.next.*` event family is v2-only.** Zero publishers in `packages/opencode/src` (4 hits, all consumers); the sole publisher factory is `core/src/session/runner/publish-llm-event.ts`, imported once by the v2 runner. So on the v1 path — the one you must use — `session.next.tool.called`, `.context.updated` and `.compaction.started/.ended` never fire. `PLAN.md:115-117` lists them as "verified event types" and builds frame contents on them | REVIEW |
| **The v2 engine never writes `session.tokens`.** `applyUsage` has 5 call sites, all in v1 projections; v2 usage lands on the message row instead. TESTED — a v2 turn burned 3,399 tokens and left the session row at `{0,0,0,0,0}`. A v2-driven session is invisible to any retirement trigger | `core/session/SESSION.MAP.md` |
| **`GET /api/session/{id}/context` returns an EMPTY array for v1 sessions.** It reads `SessionMessageTable`, which v1 never writes. TESTED: the 101-turn reference session has 0 `session_message` rows and 738 `part` rows. `PLAN.md:96` names this endpoint as the token source | REVIEW |
| **`PATCH time.archived` hides a session from nothing.** `ListInput` has no `archived` field; `listByProject` (behind `GET /session`) has no `time_archived` predicate; the v2 list does not filter; `grep -rn archived packages/tui/src` → zero hits. Only `listGlobal` filters, reachable solely via `GET /experimental/session`. **The grid must filter retired sessions itself** | REVIEW |
| **`client.session.list()` cannot enumerate across PROJECTS** — hard-scoped to `ctx.project.id` (`session.ts:548-555`), and `ListInput` has no `projectID` to widen it. Worse, the documented tripwire `api.state.session.count()` reads `sync.data.session.length` — the *same narrowed store*, so it can never detect the misses. Use `client.experimental.session.list()` (cursor-paginated). **Note the axis**: this is about projects, not directories. `scope: "project"` IS a real query param (`groups/session.ts:32` declares it, `handlers/session.ts:67-68` drops the directory filter for it) and is what the grid uses to escape the current-subdirectory filter | `tui/context/CONTEXT.MAP.md` |
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
| **The grid's roster renders OLDEST first, and its comment claims the opposite.** `healbot.tsx:203-204` says "ids are monotonic-ascending … newest first" and sorts `b.id.localeCompare(a.id)`. Session ids are **descending** identifiers (`schema/src/session-id.ts:8` → `identifier.ts:22`, `descending ? ~current : current`), so they already sort newest-first ascending and that comparator reverses them. TESTED both ways. Cosmetic, but cell order is what an operator builds muscle memory on | `docs/VERIFY.md` §7 |
| **`escape` is destructive on both prompts and there is no back-out key** — `escapeKey="reject"` (`permission.tsx:406`) and question's escape calls `reject()` (`question.tsx:280`). TESTED: escape rejected, the tool never ran. Worse, the labels disagree on screen — the grid footer says `esc reject`, the question panel it docks says `esc dismiss` (`question.tsx:508`, upstream) | `docs/VERIFY.md` §5, §7 |
| ~~**The TUI cannot attach to an external server**~~ — **REFUTED, TESTED.** `--port` really is "port to listen on" (`cli/network.ts:9`), but that was never the whole CLI: `opencode attach <url>` is a registered command (`cli/cmd/attach.ts:7-16`, `index.ts:84`) whose non-`--mini` branch calls the same `run()` with the same `createLegacyTuiPluginHost()` as `cli/cmd/tui.ts:271-296`, so the grid loads on it. `harness/fleet.sh` ships the pairing and the cold-start reconcile is now TESTED 21/21. **A true premise carried a false conclusion for three phases because nothing checked the rest of the command surface** | `docs/HARDEN.md` |
| **A client and the rig must agree on `x-opencode-directory`** — `workspace-routing.ts:87` resolves the instance as `?directory \|\| x-opencode-directory \|\| process.cwd()`, and under `serve` the cwd is wherever the launcher put it, not your project. Get this wrong and every API call succeeds, `GET /session` returns your sessions, and the grid renders `0 sessions` — two different instances. TESTED, it cost a whole run | `docs/HARDEN.md` |
| **A backgrounded server dies with the shell that launched it** — plain `&` is not enough; the shell HUPs its jobs on exit and the job shares the terminal's stdin. `nohup … </dev/null & disown` is the working form. TESTED: without it, closing the control terminal took the whole fleet down, which is the exact failure the fleet exists to prevent | `harness/fleet.sh` |
| **`GET /session/{id}/diff` returns `[]` without a `messageID`** — `summary.ts:130` returns `[]` outright when none is given, and `:133` returns `[]` again unless that message is a **user** message. It is a per-user-message endpoint; the diffs live on the user message's `summary.diffs`. `PLAN.md:398` says "its `/diff`" as though one call covered the session. Fan out over user messages and union | `docs/VERIFY.md` §10 |
| **There are TWO `summarize`s.** `POST /session/{id}/summarize` → `compactSvc.create` (`handlers/session.ts:273-283`) is **compaction**, an LLM turn — that is the one that "mutates in place and adds tokens". `SessionSummary.summarize` (`summary.ts:102-127`) computes git diffs, calls no LLM, and already runs on the prompt path (`prompt.ts:1253`). Do not reach for the route to get diff data | `docs/VERIFY.md` §10 |
| **An assistant message row exists ~20 ms after `prompt_async` acks, and is EMPTY until the turn runs.** Polling "does an assistant message exist" returns true immediately with no content. The completion signal is the message's own `time.completed` / `finish`. This produced a false "prompt_async executes nothing" defect report in the audit, and fooled the verification session again before it was caught | `docs/REVIEW.md` |
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
| Is the yellow border gated behind `OPENCODE_ENABLE_QUESTION_TOOL`? | **No** (SCAN C3) |
| Does `flags.client` land in the `["app","cli","desktop"]` allowlist? | **Yes**, TESTED. `OPENCODE_CLIENT` defaults to `"cli"` (`core/src/flag/flag.ts:75-76`) and `tool/registry.ts:202` admits it. A real `question` fired unforced on `gpt-5.6-sol` and was answered from the grid. YELLOW fires (`docs/VERIFY.md` §4) |
| Has `healbot.tsx` actually been **run**? | **Yes**, TESTED on `gpt-5.6-sol` — rendering, live session state, keyboard ownership, and clearing both a permission and a question block from the grid without focusing. 90/91 assertions (`docs/VERIFY.md`) |
| Does a session need `permission: {question: "allow"}` to ask? | **No.** `question` is `"deny"` in the shared default block (`agent/agent.ts:127`), but `build` and `plan` each merge `question: "allow"` on top (`agent/agent.ts:141-152`). Only `general` and `explore` subagents inherit the deny |
| Is `prompt_async` broken? | **No** — REFUTED, TESTED. Acks in 0.01s, turn completes ~2s later, same answer/model/tokens as the sync path. The audit polled a row that exists ~20ms before it fills. Build the spawn-and-seed path on it (`docs/VERIFY.md` §9) |
| Make the retirement threshold configurable | **Done.** `HEALBOT_RETIRE_AT`, default **256,000** (was 350,000); the grid renders `RETIRE` + `N to retire` + a share-of-threshold figure. TESTED at 20,000 against a session grown to 37,179 while quiet ones sat at 4,969. **Not 5K** — a fresh session's floor is ~4.8K, so 5K fires on turn one |
| What counts as "continuity intact" for a handoff? | **Defined and TESTED.** The successor must be handed the objective, carry the predecessor's **open** todos in its own list, and be handed a file the predecessor changed — all asserted on artefacts, never on the successor's prose. Retirement is **automatic on the gate**, with `x` as the manual override (`docs/HARDEN.md` §8). 21/21, occupancy 90,310 → 5,649 (`docs/VERIFY.md` §10) |
| Is the Phase 4 exit gate met? | **Yes**, both clauses, TESTED on `gpt-5.6-sol`. Four concurrent with one answered from the grid without focusing (§2–§5); one driven past the threshold and handed off with continuity intact (§10) |
| Does auto-retirement work headless? | **Yes**, TESTED 20/20 with no TUI in the process table. It is a **server** plugin, not a TUI one — "move it to plugin scope" would not have achieved it, because a TUI plugin needs a TUI. `docs/HEADLESS.md` |
| Does `enter` focus the selected session? | **Yes**, TESTED 24/24 and free. Asserted on the session id the sidebar renders, cell 0 then cell 1, so the predicate runs twice with opposite expectations. Also: focusing does **not** clear ERROR cells — `storedErrorOf` re-derives them |
| Is the `question.rejected` half of the cold reconcile exercised? | **Yes**, TESTED 22/22. Question raised unforced with no client, cell renders `QUESTION` on first paint, panel mounts from the reconciled request with real options, `escape` rejects, block clears. The plain session route could not have shown it at all — `sync.data.question` is event-fed only |
| **Is the control agent built?** | **Yes** — build-order step 5, the last non-optional unbuilt step. Five tools on the server plugin's `tool` hook plus `agent/control.md`. 14/14 wiring (free) and 15/16 runtime: the same instruction under `control` calls `healbot_list`/`healbot_spawn` and produces a real seeded session; under `build` it calls none of them. See the honest note on the 15/16 in `docs/HEADLESS.md` §3 |

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
| Can an **external** plugin register a route, or only a builtin? | F7 proved a builtin can and that `route.register` is on the public API. The external case is untested, and it decides whether the grid must live inside the fork | ~20 min |
| Can an external plugin's route survive a real workload? | The grid is a builtin. Everything TESTED here was measured on the builtin path | ~20 min |
| **Cold start on the retirement gate.** | The trigger is purely event-driven — `consider()` has exactly one call site and there is no polling and no startup sweep — so a server that restarts with a session already over the threshold does nothing until that session's next event. It is then caught at that turn's FIRST step boundary, by the soft gate (**not** by `RETIRE_HARD`, which this row used to credit and which is inert). A startup sweep would close it properly. Deliberately not built: a restart causing mass retirement is a policy decision | policy |
| ~~The double-retire window~~ | **CLOSED in Phase 7, by subtraction.** Both halves are gone: the grid no longer runs `retire()` at all (`x` writes `metadata.healbot.retireRequested` and the server plugin serves it), and `consider()` now claims `busy` synchronously before its first await instead of four awaits later. One writer, one document, one flag that means something. TESTED 9/9 free (`probe_request_channel.py`), and TESTED to fail — renaming the key drops it to 5/9. See `docs/RELAY.md` §2 | closed |
| `verify_control_agent.py` has not been re-executed since its one assertion was corrected | It reported 15/16; the failure was a mis-specified assertion counting the build agent's `task` subagent. The corrected predicate was evaluated against the run's persisted DB and is True, but the file has not been re-run end to end | ~4 turns |
| The session route does not surface a **dismissed question** on screen | The text is in the session's parts over HTTP (asserted, passing) but not on the visible viewport. Scroll position, how an errored tool part renders, or both — unexamined. A property of the session route, not of the reconcile | ~20 min |
| Does the grid handle the **remaining** traps? | Sessions created while the grid is open **do** appear (TESTED, VERIFY §5) — but that does not isolate the grid's `session.created → reload()` from the store's `session.updated` path, so the trap is mitigated in behaviour, not proven closed. Still unexercised: RED silent under `--auto`, and archived sessions never leaving the list. *(The project-scoped `session.list()` is now exercised on both the hosted and attached paths.)* | review |
| Is 256,000 the right gate for *heavy-read* workloads? | **Decided at 256,000 by the owner, and the margin is much better than this row used to claim.** The worry was that one turn measured ~170K of growth, so a session just under the gate could finish near 426K — past the ~360K ceiling — and this row credited `RETIRE_HARD` (330,000) with stopping it. It does not; it is inert. What actually stops it is that the gate fires per STEP, so the exposure is one step (~65K), not one turn (~170K): a session crossing at 256,000 is retired by ~321,000 worst case, inside the ceiling. Re-tune only if a single step is ever measured above ~100K | tune |
| The **256K gate** has never been exercised at its real value | Automatic retirement is TESTED at 20,000 and the comparison is a single `>=`, so the risk is low — but the full-scale run at 256,000 has not been paid for | ~$ |
| **Phase 3's exit gate is still unmet** — `/code-review ultra` on the `harness/` diff | `PLAN.md:354` makes "code-review ultra findings triaged" an explicit clause. It is user-triggered and billed; it cannot be launched from an agent session. Run it from `~/Desktop/healbot` | user action |

~~Can the **cold-start reconcile** ever be tested?~~ **Closed, TESTED 21/21** — see the refuted
trap above and [docs/HARDEN.md](docs/HARDEN.md). It was never blocked; the CLI already had
`attach`.
