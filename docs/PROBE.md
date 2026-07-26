# Phase 0 — Bootstrap + Probe results

Date: 2026-07-26 · Binary: opencode 1.17.10 (`/opt/homebrew/bin/opencode`)
Clone: `~/Desktop/healbot/opencode` @ `7534d23`, **package version 1.18.5** (clone is ahead
of the installed binary — the API surface probed below is 1.17.10's).

Evidence tier per finding. VERIFIED = read the code or ran it, cited. INFERRED = stated link
is unverified.

---

## Status

| Step | State |
|---|---|
| Project dir + git init | done |
| Clone opencode | done, `--depth 1` |
| Package layout confirmed | done — **rev-2 plan was wrong, see F1** |
| P3 config/skill switches | **VERIFIED** — see F5 |
| P5 default model | **RESOLVED** — `openai/gpt-5.6-sol`, see F6 |
| P1 token semantics | **NOT RUN** |
| P2 question tool gating | **NOT RUN** |
| P4 SDK on Node | **MOOT if F4 adopted** |
| bun install / fork build | **not done — F4 moves this onto the critical path** |

---

## F1 — Package layout (VERIFIED, corrects rev-2 plan)

Not "TS core + Go TUI + SDK". **33 packages**, no Go anywhere
(`find . -name "*.go"` → zero hits).

| Package | LOC | Note |
|---|---|---|
| `opencode` | 175,377 | |
| `app` | 113,589 | web app |
| `core` | 67,533 | |
| `console` | 41,210 | |
| **`tui`** | **31,729** | **TypeScript + SolidJS, not Go** |
| `sdk` | 30,324 | + `sdk-next` |
| `ui` | 24,465 | |
| `session-ui` | 21,019 | SolidJS session components |
| `llm` | 20,526 | |

Also: `client`, `plugin`, `protocol`, `schema`, `server`, `desktop`, `codemode`, `identity`,
`enterprise`, `slack`, `stats`, `storybook`, and more.

Toolchain: `packageManager: bun@1.3.14`, turbo, oxlint. Root `AGENTS.md` and `CONTEXT.md` exist.

---

## F2 — The TUI stack is SolidJS on OpenTUI (VERIFIED)

`packages/tui/package.json` deps: `@opentui/core`, `@opentui/solid`, `@opentui/keymap`,
`solid-js`, `effect`, `fuzzysort`, `diff`.

`packages/tui` exports a **large public surface**, including `./plugin/runtime`,
`./plugin/slots`, `./context/sdk`, `./context/sync`, `./context/theme`, `./attention`,
`./keymap`, `./ui/dialog`, `./ui/toast`, `./component/spinner`.

**Consequence: the rev-2 recommendation of TypeScript + Ink is wrong.** Building on Ink
would mean reimplementing, in a foreign framework, UI that already exists here and is
importable.

---

## F3 — opencode already implements the Healbot attention model (VERIFIED)

`packages/tui/src/attention.ts` has a built-in sound pack keyed by exactly the states this
project derived independently from the event stream:

```
default · question · permission · error · done · subagent_done
```

Plus terminal focus/blur tracking (`FocusState = "unknown" | "focused" | "blurred"`) and
desktop notifications (`triggerNotification(message, title)`).

So the "which states deserve a distinct signal" question is already answered upstream, and
the taxonomy matches the border design. Reuse it rather than re-deriving it.

---

## F4 — The grid can be a TUI plugin, not a separate app (VERIFIED — architecture change)

`packages/tui/src/plugin/slots.tsx` implements a real SolidJS plugin slot registry
(`createSolidSlotRegistry`, `TuiSlotMap`, per-plugin error isolation).

**Slot inventory** (VERIFIED by grep of render sites):

| Slot | Site |
|---|---|
| **`app`** | `packages/tui/src/app.tsx:1127` — **top level, sibling of the route switch** |
| `app_bottom` | `app.tsx:1125` |
| `home_logo`, `home_prompt` | `routes/home.tsx:76,82` — support `mode="replace"` |
| `home_prompt_right`, `home_bottom`, `home_footer` | `routes/home.tsx:83,86,91` |
| `session_prompt_right` | `routes/session/index.tsx:1316` |
| `sidebar_content`, `sidebar_footer` | `routes/session/sidebar.tsx:85,90` — receive `session_id` |

`app.tsx:1110-1127` shows the router is a `<Switch>` over `home` | `session` — **the TUI
displays one session at a time** — but the `app` slot renders *outside* that switch, so a
plugin can draw a full-screen overlay across all sessions.

**Existing prior art to build from:**
- `packages/tui/src/component/dialog-session-list.tsx` — session list that already reads
  session status. This is the seed of the grid.
- `packages/tui/src/routes/session/permission.tsx` and `question.tsx` — existing UI for the
  two blocked states → click-to-act.
- `packages/tui/src/context/sync.tsx` — the shared all-session state store.
- `packages/tui/src/feature-plugins/system/notifications.ts` — reference feature-plugin shape.

**Proposed architecture (supersedes rev 2 §1 and §4):**

> The Healbot grid is an **opencode TUI plugin rendering into the `app` slot**, reading
> all-session state from `context/sync`, seeded from `dialog-session-list.tsx`, with
> click-to-act reusing `permission.tsx` / `question.tsx`. **Focus is route navigation to the
> native session route** — not a PTY, not a child process, not a suspend/resume.

**What this eliminates:** the entire PTY hand-off hybrid; Ink; and any reimplementation of
the command palette, file picker, diff viewer, model switcher, or markdown/tool renderers.
You are already inside the native TUI.

**What this costs:** bun and a working fork build move from "deferred, conditional" to **on
the critical path**. Stack becomes SolidJS + OpenTUI.

**Update: PROVEN, and by a better mechanism than the `app` slot — see F7.**

---

## F5 — The strip is two env vars (VERIFIED by measurement)

Baseline vs. `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 OPENCODE_DISABLE_EXTERNAL_SKILLS=1`:

| | Skills | Commands |
|---|---|---|
| Default | **18** | **20** |
| With both switches | **1** (`customize-opencode`) | **3** (`init`, `review`, `customize-opencode`) |

Survivors are all opencode built-ins. **The entire inherited harness is removable by
configuration.** Phase 3 starts from this clean floor and deliberately re-adds only what
earns its place, rather than deleting and hoping.

Traced sources of the 18 (VERIFIED, arithmetic confirmed):

| Source | Count |
|---|---|
| `~/.claude/skills/` | 16 |
| `~/.agents/skills/` | 16 — near-duplicate tree, 15 overlap, adds `setup-matt-pocock-skills` |
| opencode built-in | 1 (`customize-opencode`) |
| union after dedup | **18** ✓ |

---

## F6 — Model decision (RESOLVED)

Default for managed sessions: **`openai/gpt-5.6-sol`** (user decision, 2026-07-26).

- VERIFIED present in the catalog. Variants also available: `-sol-fast`, `-sol-pro`.
- VERIFIED authenticated: `opencode providers list` → OpenAI, `oauth`,
  creds at `~/.local/share/opencode/auth.json`.
- Retires risk (c) from the rev-2 plan — N-session concurrency no longer bottlenecks on one
  local Ollama. Local models stay available as explicit per-session opt-in.

---

## F7 — Plugins register ROUTES, not just slots (VERIFIED by reading + running)

The `app` slot is not the right mechanism. `packages/tui/src/feature-plugins/system/diff-viewer.tsx`
shows the real one — a plugin registers a **full-screen route**:

```ts
const tui: TuiPlugin = async (api) => {
  api.route.register([{ name: ROUTE, render: () => <View api={api} /> }])
  api.keymap.registerLayer({
    commands: [{
      name: "diff.open", title: "Open diff viewer", slashName: "diff",
      category: "VCS", namespace: "palette",
      run() {
        api.route.navigate(ROUTE, { ...params, returnRoute: api.route.current })
        api.ui.dialog.clear()
      },
    }],
  })
}
export default { id: "diff-viewer", tui }
```

`route.register` is on the **public** API at `packages/plugin/src/tui.ts:595`, so external
plugins get the same capability as built-ins — not a builtin-only privilege.

**`TuiPluginApi` covers the entire project** (`packages/plugin/src/tui.ts:582`):
`route` (register/navigate/current) · `keymap.registerLayer` · `client: OpencodeClient` ·
`event: TuiEventBus` · `attention` · `theme` · `ui.{Dialog,DialogSelect,toast,dialog,Prompt}` ·
`state` · `kv` · `renderer` · `plugins` · `lifecycle` · `mode` · `slots`.

Every element of the Healbot design maps onto it:

| Design element | API |
|---|---|
| the grid | `route.register("healbot")` |
| open it | `keymap.registerLayer` → `/healbot` in the palette |
| border states | `event.on("session.status" \| "session.idle" \| "permission.asked" \| "question.asked")` |
| session data | `client.session.list()` / `.status()` / `.todo()` |
| click-to-act | `client` permission + question reply |
| **focus a session** | `route.navigate("session", { sessionID })` — native route, no PTY |
| back out | `returnRoute: api.route.current` |
| colors | `theme.current.{primary,error,warning,success,accent,textMuted,border}` |
| sound/desktop notify | `attention` (F3) |

### The spike (TESTED)

`packages/tui/src/feature-plugins/system/healbot-spike.tsx`, registered in
`feature-plugins/builtins.ts`. Typechecks clean (`bun run typecheck`, tui package).

Run from source (`bun dev`) inside a pty via `script`, driven by scripted keystrokes:
ctrl+p → `healbot` → Enter → left, right, up arrows.

Captured frames prove all five:

| # | Claim | Evidence |
|---|---|---|
| 1 | route renders full-screen | `HEALBOT SPIKE — plugin route renders full-screen` + bordered boxes drawn |
| 2 | **route owns keyboard focus** | `PROBE_KEYS=1 …[left]`, `=2 …[right]`, `=3 …[up]` — arrows counted by the plugin, not swallowed by the prompt |
| 3 | client data path | `PROBE_SESSIONS_PENDING` → `PROBE_SESSIONS_OK=[0]` — `client.session.list()` resolved (0 = correct, fresh project) |
| 4 | event subscriptions | 4 `event.on(...)` handlers registered, no errors; log idle (no session activity to fire them) |
| 5 | palette registration | `/healbot   Healbot spike` rendered in the command palette |

Note on method: OpenTUI emits **incremental cell diffs** after the first paint, so later
state appears as fragments (`OK=[0] 1left]  2right]3up]`) rather than whole lines. The probe
tokens were designed to be unambiguous under that constraint. An earlier run's "client ok"
was **not** valid evidence — it rendered before the promise resolved; `PROBE_SESSIONS_OK`
replaced it for that reason.

Also learned: `POST /tui/execute-command` returned `true` for `healbot.spike` but did **not**
navigate — it appears to accept only built-in TUI commands. Driving the palette by keystroke
works. Worth confirming in Phase 1 if remote control of a running TUI matters.

**Architecture is settled:** the grid is a plugin-registered route inside the fork's TUI.
No PTY, no Ink, no separate app, no suspend/resume, and the native command palette, file
picker, diff viewer and model switcher all remain available because you never leave the TUI.

---

## Toolchain (done)

- `bun 1.3.14` installed via homebrew — **exact match** for the repo's `packageManager` pin.
- `bun install` at repo root: 4694 packages, 21.65s, clean.
- `bun dev` runs the TUI from source and boots to the home route.
- `bun run typecheck` works per-package (`packages/tui`).

---

## Open, carried into the next phase

| Id | Question | Why it matters |
|---|---|---|
| P1 | Is `tokens{}` on `GET /session` lifetime or last-message? | Sets the 350K retirement trigger. |
| P2 | Does `question.asked` fire without `OPENCODE_ENABLE_QUESTION_TOOL`? | The yellow border depends on it. |
| — | Clone is 1.18.5, binary is 1.17.10 | Confirm no API drift. The spike ran against **source**, so the fork is the safe target regardless. |
| — | Does `/tui/execute-command` reach plugin commands? | Only matters if remote-controlling a running TUI is wanted. |

Closed this phase: **F4-proof** (F7, TESTED) · bun/build (toolchain, done) · P3 (F5) · P5 (F6).
