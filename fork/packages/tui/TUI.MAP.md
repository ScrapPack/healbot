# TUI.MAP.md — `packages/tui`

Structural map of the opencode terminal UI package (v1.18.5, branch `healbot`).
Scope: what owns what, and where the Healbot grid plugs in. Sub-maps:
`src/context/CONTEXT.MAP.md` · `src/plugin/PLUGIN.MAP.md` · `src/feature-plugins/FEATURE-PLUGINS.MAP.md`

> **Provenance — RETRACTED.** This block previously asserted that `docs/SCAN.md` and
> `docs/PROBE.md` "are not in this repo and never were… never committed", and stamped
> **UNVERIFIED** on every SCAN-attributed figure. **That is false.** Both are committed in the
> *other* repo: `git log --stat` in `~/Desktop/healbot` shows `docs/SCAN.md` added by `6f74f2b`
> and `docs/PROBE.md` by `8f34a84`. The `git log --all` search came back empty only because
> `~/Desktop/healbot/.gitignore` excludes `/opencode/`, so this fork cannot see that history.
> Read them at `~/Desktop/healbot/docs/`. They are followable citations.
>
> Treat SCAN's *numbers* with care for a real and different reason: they were measured under
> `anthropic.txt` with cwd inside this fork, so they do not describe the shipped harness. The
> audit is at `~/Desktop/healbot/docs/REVIEW.md`.

> **Path convention.** A citation prefixed `packages/…` is repo-relative. A **bare path** resolves
> against, in order: (1) this file's own directory, (2) the owning package's `src/`, (3) the repo
> root — all three are in use here. A bare **`:NNN`** is a line in the file named by the enclosing
> section heading or table row.

---

## Stack

| Fact | Evidence |
|---|---|
| TypeScript + SolidJS on OpenTUI. **No Go anywhere.** | `package.json` deps: `@opentui/core`, `@opentui/solid`, `@opentui/keymap`, `solid-js`, `effect`, `fuzzysort`, `diff` |
| Reactivity = Solid signals/stores + `createMemo`; render = OpenTUI renderables (`<box>`, `<text>`, `<scrollbox>`) | `src/app.tsx:1087-1133` |
| Bootstrapped inside an Effect scope (renderer acquire/release, finalizers) | `src/app.tsx:186-363` |
| ~31.7k LOC, 33-package monorepo, `bun@1.3.14` + turbo + oxlint | root `package.json` |
| Package is `private: true`, consumed by path via workspace exports | `package.json:5,12-50` |

---

## Entry points

| Step | File:line | Notes |
|---|---|---|
| Public entry | `src/index.tsx:1` | `export { run, type TuiInput } from "./app"` — one line, nothing else |
| Effect wrapper | `packages/opencode/src/cli/tui/layer.ts:6-8` | `run(input)` → `runTui(input).pipe(Effect.provide(...))` |
| Real entry | `src/app.tsx:186` | `export const run = Effect.fn("Tui.run")` |
| Input contract | `src/app.tsx:142-152` | `TuiInput = { url, args, config, onSnapshot?, directory?, fetch?, headers?, events?, pluginHost }` |
| Renderer creation | `src/app.tsx:191-213` | `createCliRenderer` — 60fps, kitty keyboard, mouse gated on `OPENCODE_DISABLE_MOUSE` + `config.mouse` |
| Plugin host boot | `src/app.tsx:408-420` | `props.pluginHost.start({ api, config, runtime, dispose })`; sets `ready()` in `.finally` |
| Plugin host impl | `packages/opencode/src/plugin/tui/runtime.ts:1124-1129` | `createLegacyTuiPluginHost()` — **lives outside this package** |
| Builtin plugin list feed | `packages/opencode/src/plugin/tui/internal.ts:6-10` | `internalTuiPlugins(flags)` → `createBuiltinPlugins(...)` |

### ⚠️ Running from source sees an EMPTY session list — by design

The database filename is **channel-scoped**, and a from-source run is not on a release channel:

| Step | Site | Result |
|---|---|---|
| `OPENCODE_CHANNEL` is a build-time define, absent from source | `packages/core/src/installation/version.ts:7` | `InstallationChannel = "local"` |
| `"local"` is not in `["latest","beta","prod"]` | `packages/core/src/database/database.ts:48-54` | db path = **`opencode-local.db`**, not `opencode.db` |

So `bun run dev` opens a *different, usually empty* database and the home screen, session
switcher and Healbot grid all correctly show **0 sessions** — your installed opencode's history
lives in `opencode.db`. This is deliberate isolation, not a bug. The `local` token in the boot
footer is this channel indicator.

**To develop against real sessions, never point a source build at `opencode.db` directly** — it
will run migrations on your real history. Snapshot it and use the absolute-path override
(`database.ts:44-46`):

```bash
sqlite3 -readonly ~/.local/share/opencode/opencode.db "VACUUM INTO '/tmp/snap.db';"
OPENCODE_DB=/tmp/snap.db bun run --cwd packages/opencode --conditions=browser src/index.ts <project-dir>
```

`OPENCODE_DISABLE_CHANNEL_DB=1` (`database.ts:50-51`) also forces `opencode.db`, but writes to
the real file. Pass the project directory as the positional `project` arg (`cli/cmd/tui.ts:77-80`)
— `bun --cwd` sets module resolution, not the instance directory, and running bun from the repo
root instead fails with `Cannot find module 'react/jsx-dev-runtime'`.

---

## `src/app.tsx` (1134 lines) — anatomy

| Range | Owns |
|---|---|
| `92-104` | `appGlobalBindingCommands` — session.list/new + 9 quick-switch slots |
| `106-140` | `appBindingCommands` — palette, model, agent, theme, `diff.open`, toggles |
| `154-167` | `errorMessage()` unwrapper |
| `169-184` | `isVersionGreater()` semver compare (update prompt) |
| `186-363` | `run` — Effect scope: renderer, keymap registration, SIGHUP, plugin dispose finalizer, `render()` |
| **`247-349`** | **The provider tree.** Order matters — see below |
| `365-1134` | `function App` — the whole live component |
| `388-406` | `createTuiApi(createTuiApiAdapters({...}))` — **the one place the plugin API is constructed** |
| `423-434` | selection-key intercept + `onCleanup` |
| `447-450` | `terminal_title_enabled` / `paste_summary_enabled` KV signals |
| `453-476` | terminal title effect — branches on `route.data.type` incl. `"plugin"` (`473-475`) |
| `479-499` | `onMount` — apply `--agent`, `--model`, `--session` args |
| `502-538` | `--continue` / `--fork` navigation effects |
| `540-549` | empty-provider → force `DialogProviderList` |
| **`559-960`** | **`appCommands` memo** — every built-in palette command |
| `962-983` | `useBindings` × 4 — command registry, base-mode binds, global binds, exit bind |
| `985-1077` | app-level `event.on(...)`: `tui.command.execute`, `tui.toast.show`, `tui.session.select`, `session.deleted`, `session.error`, `installation.update-available` |
| **`1079-1085`** | **`plugin` memo — resolves the plugin route** |
| `1087-1133` | Render tree |

### Provider nesting (`app.tsx:247-349`), outermost → innermost

```
ExitProvider → EpilogueProvider → ErrorBoundary → TuiPathsProvider →
TuiTerminalEnvironmentProvider → TuiStartupProvider → ClipboardProvider →
OpencodeKeymapProvider → ArgsProvider → KVProvider → ToastProvider →
RouteProvider → TuiConfigProvider → PluginRuntimeProvider → SDKProvider →
PermissionProvider → ProjectProvider → SyncProvider(:307) → DataProvider(:308) →
ThemeProvider → LocalProvider → PromptStashProvider → DialogProvider →
FrecencyProvider → PromptHistoryProvider → PromptRefProvider →
EditorContextProvider → LocationProvider → <App>(:318)
```

**Consequence (load-bearing for Healbot):** `<App>` — and therefore every plugin route rendered by it — sits **inside** `SyncProvider`. A plugin route component may call `useSync()` directly.
*Correction to SCAN.md §6: it cites `app.tsx:306-321`; `<SyncProvider>` is at `:307` (closes `:332`) and `<App .../>` spans `:318-321`.*

### Where a plugin route renders — the critical path

```
route.navigate({ type:"plugin", id, data })        context/route.tsx:37-39
        ↓
plugin memo                                        app.tsx:1079-1085
  if (!ready()) return                             :1080   ← plugins still loading
  if (route.data.type !== "plugin") return         :1081
  const render = pluginRuntime.routes.get(id)      :1082   ← plugin/api.ts:33-36
  if (!render) return <PluginRouteMissing/>        :1083   ← component/plugin-route-missing.tsx
  return render({ params: route.data.data })       :1084
        ↓
{plugin()}                                         app.tsx:1122
```

`{plugin()}` is a **sibling of the route `<Switch>`** inside `<box flexGrow={1} minHeight={0}>` (`app.tsx:1111-1123`). The `<Switch>` only matches `"home"` (`:1113`) and `"session"` (`:1116`) — on a plugin route **neither `<Match>` fires**, so the plugin component is the sole occupant of the flex-grow box → genuinely full-screen. Rendering order also puts it *above* `app_bottom` (`:1125`) and *below* the `app` slot (`:1127`).

---

## Routes (`src/routes/`)

| File | Lines | Owns |
|---|---|---|
| `home.tsx` | 95 | `Home()` — logo + prompt landing. Slot host: `home_logo`:76, `home_prompt`:82, `home_prompt_right`:83, `home_bottom`:86, `home_footer`:91 |
| `home/session-destination.tsx` | 41 | `HomeSessionDestinationProvider` / `useHomeSessionDestination` |
| `session/index.tsx` | 2710 | `Session()` (`:178`) — the transcript route. Also exports all part/tool renderers (`PART_MAPPING`:1564, `ToolPart`:1702, `InlineToolRow`:1907, `Shell`/`Write`/`Glob`/`Read`/`Grep`/`WebFetch`/`WebSearch`) |
| `session/permission.tsx` | 718 | `PermissionPrompt({ request, directory })` (`:111`) — **the RED click-to-act UI** |
| `session/question.tsx` | 514 | `QuestionPrompt({ request, directory })` (`:14`) — **the YELLOW click-to-act UI** |
| `session/sidebar.tsx` | 103 | `Sidebar({ sessionID })`. Slot host: `sidebar_title`:50, `sidebar_content`:85, `sidebar_footer`:90 |
| `session/footer.tsx` | 91 | status/model footer |
| `session/subagent-footer.tsx` | 132 | shown when `session.parentID` set (`index.tsx:1295`) |
| `session/dialog-timeline.tsx` / `dialog-message.tsx` / `dialog-subagent.tsx` / `dialog-fork-from-timeline.tsx` | 47/109/26/76 | in-session dialogs |

Session-route facts the grid depends on:

| Fact | file:line |
|---|---|
| **Historical backfill fires here and nowhere else** — `await sync.session.sync(sessionID)` | `routes/session/index.tsx:306` |
| Permission prompt render (first request only, `permissions()[0]`) | `routes/session/index.tsx:1283-1288` |
| Question prompt render (only when no permission pending) | `routes/session/index.tsx:1289-1294` |
| Reply calls are keyed by `requestID` alone | `permission.tsx:168-172,180-184`; `question.tsx:50-54,74-78` |

---

## Components (`src/component/`)

**Dialogs** (all rendered via `dialog.replace(() => <X/>)` from `app.tsx:559-960`):

| File | Lines | Command that opens it |
|---|---|---|
| `command-palette.tsx` | 79 | `command.palette.show` (`app.tsx:562-569`) |
| **`dialog-session-list.tsx`** | **364** | `session.list` (`app.tsx:571-580`) — **grid seed; reads `sync.data.session_status` at `:237`** |
| `dialog-model.tsx` | 197 | `model.list` |
| `dialog-agent.tsx` | 31 | `agent.list` |
| `dialog-provider.tsx` | 469 | `provider.connect` |
| `dialog-mcp.tsx` | 85 | `mcp.list` |
| `dialog-status.tsx` / `dialog-debug.tsx` | 168 / 90 | `opencode.status` / `opencode.debug` |
| `dialog-theme-list.tsx` | 50 | `theme.switch` |
| `dialog-variant.tsx` | 39 | `variant.list` |
| `dialog-console-org.tsx` | 135 | `console.org.switch` |
| `dialog-workspace-list.tsx` / `-create.tsx` / `-file-changes.tsx` / `-unavailable.tsx` | 112/308/144/69 | `workspace.list` (flag-gated) |
| `dialog-move-session.tsx` / `-rename.tsx` / `-session-delete-failed.tsx` / `-stash.tsx` / `-skill.tsx` / `-tag.tsx` / `-retry-action.tsx` | 353/31/99/87/70/47/160 | session-route + prompt commands |

**Non-dialog:**

| File | Lines | Owns |
|---|---|---|
| `prompt/index.tsx` | 1713 | `Prompt` — the editor. Re-exported to plugins as `api.ui.Prompt` (`plugin/adapters.tsx:242-256`) |
| `prompt/autocomplete.tsx` | 781 | `@`-file / `/`-command completion. **Only consumer of `context/data.tsx`** (`:12,:90`) |
| `prompt/move.tsx` · `workspace.tsx` | 205 · 137 | `usePromptMove`, `usePromptWorkspace` |
| `error-component.tsx` | 240 | `ErrorBoundary` fallback (`app.tsx:255`) |
| `plugin-route-missing.tsx` | 14 | rendered when a plugin route id has no registered render (`app.tsx:1083`) |
| `startup-loading.tsx` | 63 | boot overlay (`app.tsx:1129-1131`) |
| `spinner.tsx` · `register-spinner.ts` | 26 · — | `SPINNER_FRAMES`; `registerOpencodeSpinner()` called at module load (`app.tsx:90`) |
| `bg-pulse.tsx` + `bg-pulse-render.ts` | 99 | animated background |
| `todo-item.tsx` · `logo.tsx` · `workspace-label.tsx` · `use-connected.tsx` | 32/61/19/12 | small leaves |

## UI primitives (`src/ui/`)

| File | Lines | Exports |
|---|---|---|
| `dialog.tsx` | 231 | `Dialog`, `DialogProvider`, `useDialog` — the modal stack (`replace/clear/setSize/stack`) |
| `dialog-select.tsx` | 790 | `DialogSelect` — fuzzy list picker; the workhorse |
| `dialog-alert.tsx` / `-confirm.tsx` / `-prompt.tsx` / `-help.tsx` / `-export-options.tsx` | 66/108/126/40/217 | leaf dialogs; `DialogAlert.show`/`DialogConfirm.show` are promise-returning |
| `toast.tsx` | 102 | `Toast`, `ToastProvider`, `useToast` |
| **`border.ts`** | **21** | **`EmptyBorder`, `SplitBorder`** — custom border char sets; relevant to grid frames |
| `spinner.ts` | 368 | frame/color derivation |
| `link.tsx` | 34 | OSC-8 hyperlink |

## Utilities (`src/util/`)

`locale.ts` (`time`, `truncate*`, `pluralize`) · `format.ts` (`formatDuration`) · `session.ts` (`isDefaultTitle`) · `model.ts` (`parse`, `name`) · `error.ts` (`cliErrorMessage`, `errorFormat`) · `scroll.ts` (`CustomSpeedScroll`, `getScrollAcceleration`) · `selection.ts` (`copy`, `handleSelectionKey`) · `renderer.ts` (`destroyRenderer`) · `layout.ts` · `path.ts` · `record.ts` (`isRecord`) · `signal.ts` (`createDebouncedSignal`, `createFadeIn`) · `filetype.ts` · `tool-display.ts` · `transcript.ts` · `presentation.ts` · `revert-diff.ts` · `collapse-tool-output.ts` · `persistence.ts` · `system.ts` · `provider-origin.ts`

---

## Keymap (`src/keymap.tsx`, 290 lines)

| Symbol | Line | Role |
|---|---|---|
| `LEADER_TOKEN` / `OPENCODE_BASE_MODE` / `COMMAND_PALETTE_COMMAND` | 20/21/22 | `"leader"` / `"base"` / `"command.palette.show"` |
| `OpencodeKeymapProvider`, `useOpencodeKeymap` | 26-27 | re-exports of `@opentui/keymap` provider/hook |
| **`useBindings`, `useKeymapSelector`** | **29** | **the in-component registration hook** — scoped to component lifetime |
| `createOpencodeModeStack` / `useOpencodeModeStack` / `getOpencodeModeStack` | 53/102/106 | mode stack (`base` ⇄ pushed modes) |
| `formatKeySequence` / `formatKeyBindings` | 206/210 | surfaced to plugins as `api.keys.*` (`adapters.tsx:179-186`) |
| `registerOpencodeKeymap` | 214 | called once in `run` (`app.tsx:217`) |
| `useCommandShortcut` / `useCommandSlashes` / `useLeaderActive` | 250/260/246 | display helpers |

Binding sources are merged from config: `tuiConfig.keybinds.gather(section, commandNames)` (`app.tsx:968,972,982`; `config/index.tsx:110`; parser in `config/keybind.ts`).

## Theme (`src/context/theme.tsx` + `src/theme/`)

| Item | file:line |
|---|---|
| `Theme` type — `primary, accent, error, warning, success, text, textMuted, border, borderActive, borderSubtle`, … | `theme/index.ts:36-53` |
| 32 bundled themes (JSON) | `theme/assets/*.json`; registry `theme/index.ts:130-190` |
| `resolveTheme(json, mode)` | `theme/index.ts:241` |
| `generateSystem(colors, mode)` — terminal-derived theme | `theme/index.ts:360` |
| `useTheme()` return: `theme` (Proxy, always current), `selected`, `mode()`, `locked()`, `lock/unlock/setMode`, `set(name)`, `syntax`, `subtleSyntax`, `ready` | `context/theme.tsx:274-301` |
| `theme` is a **Proxy over `values()`** — property reads are reactive, destructuring is not | `context/theme.tsx:275-280` |

## Attention (`src/attention.ts`, 260 lines)

| Item | Line |
|---|---|
| `FocusState = "unknown" \| "focused" \| "blurred"` | 24 |
| Sound-pack names: `default · question · permission · error · done · subagent_done` | 46 (`BUILTIN_PACK`); schema `config/index.tsx:8-16` |
| `createTuiAttention({ renderer, config, kv })` | 114 |
| `notify(request)` — `{ title, message, notification: {when}, sound: {name, when} }` | 170 |
| Desktop notify via `renderer.triggerNotification` | 185 |
| Constructed once in `App` and handed to the plugin API | `app.tsx:385,403` |

---

## Plugin slot render sites (complete)

| Slot | Render site | Props passed |
|---|---|---|
| `app` | `app.tsx:1127` | — (outside the flex-grow box; overlays everything) |
| `app_bottom` | `app.tsx:1125` | — |
| `home_logo` | `routes/home.tsx:76` | `mode="replace"` |
| `home_prompt` | `routes/home.tsx:82` | `mode="replace"`, `ref` |
| `home_prompt_right` | `routes/home.tsx:83` | — |
| `home_bottom` | `routes/home.tsx:86` | — |
| `home_footer` | `routes/home.tsx:91` | `mode="single_winner"` |
| **`sidebar_title`** | `routes/session/sidebar.tsx:50` | `single_winner`, `session_id`, `title`, `share_url` |
| `sidebar_content` | `routes/session/sidebar.tsx:85` | `session_id` |
| `sidebar_footer` | `routes/session/sidebar.tsx:90` | `single_winner`, `session_id` |
| **`session_prompt`** | `routes/session/index.tsx:1299-1300` | `replace`, `session_id`, `visible`, `disabled`, `on_submit`, `ref` |
| `session_prompt_right` | `routes/session/index.tsx:1316` | `session_id` |

*Correction to PROBE.md F4: its slot inventory omits `sidebar_title` and `session_prompt`.*

---

## Package exports (`package.json:12-50`) — what an external consumer can import

`.` · `./builtins` · `./config` · `./config/keybind` · `./context/{args,epilogue,exit,kv,project,runtime,sdk,sync,theme,editor,clipboard}` · `./attention` · `./editor` · `./editor-zed` · `./runtime` · `./terminal-win32` · `./keymap` · `./prompt/display` · `./plugin/{runtime,slots,command-shim}` · `./parsers-config` · `./util/{error,locale,persistence,record}` · `./logo` · `./ui/{dialog,spinner,toast}` · `./component/{spinner,register-spinner}`

Not exported: `./context/data`, `./context/local`, `./context/route`, `./context/event`, `./plugin/api`, `./plugin/adapters`, `./routes/*`, `./component/*` (except spinner). Builtins live *in* the package, so they bypass this list with relative imports.

---

## Gotchas (living here)

| # | Gotcha | Evidence |
|---|---|---|
| G1 | `{plugin()}` returns `undefined` until `ready()` — the plugin host finishes loading. A route navigated to before then renders **nothing**, not an error. | `app.tsx:1080`, `:407,418-420` |
| G2 | Unknown plugin route id ⇒ `<PluginRouteMissing>`, not a crash. Route ids are **last-wins on collision**. | `app.tsx:1083`; `plugin/api.ts:35` (`.at(-1)`) |
| G3 | The `app` slot (`:1127`) renders **outside** `<box flexGrow={1}>`, so it does not participate in the route box's layout — it draws over/after. Use a plugin **route**, not the `app` slot, for a full-screen grid. | `app.tsx:1111-1127` |
| G4 | Terminal title effect has a `"plugin"` branch — a Healbot route will set the title to `OC \| healbot` automatically. | `app.tsx:473-475` |
| G5 | `session.error` events surface as a **toast only** (`app.tsx:1018-1029`). Nothing writes error state into a store — the grid must track it itself for red-flash. | `app.tsx:1018` |
| G6 | `--auto` silently auto-replies permissions before they reach the store ⇒ **RED never fires**. | `context/permission.tsx:12`; `context/sync.tsx:192-199` |
| G7 | `mouse` support is conditional (`OPENCODE_DISABLE_MOUSE` flag + `config.mouse`). Click-to-act must have a keyboard equivalent. | `app.tsx:202` |
| G8 | Route params survive as `route.data.data` (`Record<string, unknown>`), untyped. `useRouteData` casts without validation. | `context/route.tsx:19-20,57-60` |
| G9 | `OPENCODE_ROUTE` env var can deep-link the initial route, but `initialRoute()` only rehydrates `{type:"plugin", id}` — **it drops `data`**. | `context/route.tsx:50-52`; `context/runtime.tsx` (`TuiStartupProvider`, `app.tsx:275-280`) |

---

## Build levers — what the Healbot grid touches in this package

| Lever | file:line | Action |
|---|---|---|
| Register the route | `src/feature-plugins/builtins.ts:23-37` | add `Healbot` to the returned array (see FEATURE-PLUGINS.MAP.md) |
| Route renders here | `src/app.tsx:1084` | `render({ params: route.data.data })` — params arrive as the plugin's only input |
| Full-screen box to fill | `src/app.tsx:1111` | `flexGrow={1} minHeight={0} flexDirection="column"` — mirror this in the grid root |
| Focus a session | `src/context/route.tsx:37-39` via `plugin/adapters.tsx:47-52` | `api.route.navigate("session", { sessionID })` |
| Return path | `src/app.tsx:1122` ← `route.navigate({type:"home"})` | stash `returnRoute: api.route.current` on entry (pattern: `diff-viewer.tsx:1065`) |
| Border colors | `src/theme/index.ts:36-53` | `api.theme.current.{error,warning,success,primary,textMuted,border,borderActive}` |
| Frame chars | `src/ui/border.ts:1-21` | `EmptyBorder`/`SplitBorder` for non-default frames |
| In-route keybindings | `src/keymap.tsx:29` | `useBindings(() => ({ commands, bindings }))` inside the route component |
| Seed the grid cell list/sort | `src/component/dialog-session-list.tsx:80-81,195,237-238` | already merges `sync.data.session` + `session_status` and derives "working" |
| Reuse blocked-state UI | `src/routes/session/permission.tsx:111`, `question.tsx:14` | both take `{ request, directory }` only — **directly reusable in a grid cell** |
| Sound / desktop notify | `src/attention.ts:170` | `api.attention.notify({ title, message, notification, sound })` |
| Backfill a cold session | `src/routes/session/index.tsx:306` | the only existing caller of `sync.session.sync(id)`; grid must call it itself |
