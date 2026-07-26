# PLUGIN.MAP.md — `packages/tui/src/plugin`

The TUI plugin runtime: route registry, slot registry, and the `TuiPluginApi` bridge that
exposes host state to plugins. Parent map: `packages/tui/TUI.MAP.md`.
Consumers: `packages/tui/src/feature-plugins/FEATURE-PLUGINS.MAP.md`.

> **Path convention.** A citation prefixed `packages/…` is repo-relative. A **bare path** resolves
> against, in order: (1) this file's own directory, (2) the owning package's `src/`, (3) the repo
> root — all three are in use here. A bare **`:NNN`** is a line in the file named by the enclosing
> section heading or table row.

---

## File table

| File | Lines | Owns | Key symbols |
|---|---|---|---|
| `api.ts` | 52 | **Route registry** + api completion | `createPluginRoutes` `:11`, `RouteMap` `:9`, `PluginRoutes` `:40`, `createTuiApi` `:42` |
| **`adapters.tsx`** | **355** | **The host→plugin bridge.** Every `api.*` member is constructed here | `createTuiApiAdapters` `:173`, `stateApi` `:98`, `routeNavigate` `:41`, `routeCurrent` `:57`, `appApi` `:165` |
| `slots.tsx` | 65 | Slot registry over `@opentui/solid`'s `createSolidSlotRegistry` | `createSlots` `:25`, `HostSlots` `:11`, `HostSlotPlugin` `:9`, `isHostSlotPlugin` `:19` |
| `runtime.tsx` | 81 | Runtime container + Solid context + host contract | `createPluginRuntime` `:12`, `PluginRuntime` `:59`, **`TuiPluginHost`** `:61`, `PluginRuntimeProvider` `:73`, `usePluginRuntime` `:77` |
| `command-shim.ts` | 109 | Deprecated `api.command` v1 bridge → `keymap.registerLayer` | `createCommandShim` `:85`, `toCommand` `:49`, `toBindings` `:67` |

**Type source of truth is outside this package:** `packages/plugin/src/tui.ts` —
`TuiPluginApi` `:581`, `route.register` `:595`, `TuiState` `:375-399`, `TuiEventBus` `:519-521`,
`TuiRouteDefinition` `:69`.

---

## Construction chain

```
app.tsx:388-406
  createTuiApi(                        ← plugin/api.ts:42   adds lifecycle stub
    createTuiApiAdapters({ … })        ← plugin/adapters.tsx:173
  )
        ↓ api
props.pluginHost.start({ api, config, runtime, dispose })     app.tsx:409-414
        ↓
packages/opencode/src/plugin/tui/runtime.ts  (createLegacyTuiPluginHost :1124-1129)
  pluginApi(runtime, plugin, scope, base)     :572-650
    → re-wraps route/event/keymap/mode/attention/theme/slots/plugins PER PLUGIN
    → passes `state: api.state` THROUGH UNCHANGED                :624
        ↓
const tui: TuiPlugin = async (api) => { … }   ← what a feature-plugin receives
```

---

# `api.ts` — the route registry

| Symbol | Line | Behaviour |
|---|---|---|
| `RouteEntry = { key: symbol; render }` | 4-7 | `key` is a fresh `Symbol()` per `register()` call, used for unregistration |
| `routes: Map<string, RouteEntry[]>` | 12 | plain Map — **not reactive** |
| `revision` signal | 13 | the reactivity carrier |
| `register(list)` | 16-32 | **appends** to the array for each name (`:18`); bumps revision; returns an unregister closure (`:21-31`) that filters by `key` and deletes the name when empty |
| `get(name)` | 33-36 | `revision()` read for tracking, then **`routes.get(name)?.at(-1)?.render`** — **last registration wins** |
| `createTuiApi(input)` | 42-52 | spreads input and appends a **stub `lifecycle`**: fresh `AbortController().signal`, `onDispose` returns a no-op (`:45-50`). The real lifecycle comes from the host's per-plugin scope (`runtime.ts:649`) |

---

# `adapters.tsx` — the bridge

## Member map (`createTuiApiAdapters`, `:173-355`)

| `api.*` | Line | Backed by |
|---|---|---|
| `app.version` | 174 → `appApi` `:165-171` | `InstallationVersion` (`app.tsx:390`) |
| `attention` | 175 | passed straight through from `createTuiAttention` (`app.tsx:385`) |
| `command` | 178 | `createCommandShim(keymap, dialog, tuiConfig.keybinds)` — **deprecated** |
| `keys.formatSequence` / `.formatBindings` | 179-186 | `Keymap.formatKeySequence` / `formatKeyBindings` |
| `keymap` | 187 | `useOpencodeKeymap()` passthrough (host re-scopes it) |
| `mode.current` / `.push` | 188-195 | `Keymap.getOpencodeModeStack(keymap)` |
| **`route.register`** | 197-199 | `input.routes.register(list)` → `api.ts:16` |
| **`route.navigate`** | 200-202 | `routeNavigate(...)` — **special-cased, see below** |
| `route.current` | 203-205 | `routeCurrent(...)` `:57-73` |
| `ui.Dialog` / `DialogAlert` / `DialogConfirm` / `DialogPrompt` / `DialogSelect` | 208-238 | wraps `ui/dialog*.tsx`; option mapping `:75-96` |
| `ui.Slot` | 239-241 | `pluginRuntime.Slot` |
| `ui.Prompt` | 242-256 | the real `component/prompt` |
| `ui.toast` | 257-264 | `useToast().show`, defaults `variant:"info"` |
| `ui.dialog.{replace,clear,setSize,size,depth,open}` | 265-284 | `depth`/`open` derived from `dialog.stack.length` |
| `tuiConfig` | 286-288 | `TuiConfig.Resolved` |
| `kv.{get,set,ready}` | 289-299 | `useKV()` |
| **`state`** | **300** | **`stateApi(input.sync)` — `:98-163`** |
| `client` | 301-303 | `input.sdk.client` (`OpencodeClient`) |
| `event` | 304 | `useEvent()` passthrough |
| `renderer` | 305 | `CliRenderer` |
| `slots.register` | 306-310 | **throws `"slots.register is only available in plugin context"`** — host overrides (`runtime.ts:603-610`) |
| `plugins.*` | 311-330 | **all stubs returning `[]` / `false`** — host overrides (`runtime.ts:631-648`) |
| `theme.{current,selected,has,set,mode,ready}` | 331-353 | `useTheme()`; `theme.install` throws here, host overrides (`runtime.ts:589-591`) |

## `routeNavigate` — the special-casing (`:41-55`)

```ts
if (name === "home")     route.navigate({ type: "home" });                    return   // :42-45
if (name === "session") {
  const sessionID = params?.sessionID
  if (typeof sessionID !== "string") return          // silently drops the nav          // :49
  route.navigate({ type: "session", sessionID });    return                            // :50
}
route.navigate({ type: "plugin", id: name, data: params })                             // :54
```

**Only `params.sessionID` is read for the `session` case. Every other param is discarded** —
you cannot pass e.g. `returnRoute` or `prompt` into the session route through this API.
For plugin routes, the whole `params` object survives as `route.data.data`.

`routeCurrent` (`:57-73`) is the inverse: `home` → `{name:"home"}`;
`session` → `{name:"session", params:{sessionID, prompt}}`; plugin → `{name: id, params: data}`.

## `api.state` — exact surface (`stateApi`, `:98-163`)

| Member | Line | Returns |
|---|---|---|
| `ready` | 100-102 | `sync.ready` |
| `config` | 103-105 | `sync.data.config` |
| `provider` | 106-108 | `sync.data.provider` |
| `path` | 109-111 | `sync.path` |
| `vcs` | 112-118 | `{ branch, default_branch }` or `undefined` |
| `session.count()` | 120-122 | `sync.data.session.length` |
| `session.get(id)` | 123-125 | `sync.session.get(id)` → `Session \| undefined` |
| `session.diff(id)` | 126-130 | `session_diff[id]`, filtered to entries with a `file` |
| `session.todo(id)` | 131-133 | `todo[id] ?? []` |
| `session.messages(id)` | 134-136 | `message[id] ?? []` |
| `session.status(id)` | 137-139 | `session_status[id]` (**may be `undefined`**) |
| `session.permission(id)` | 140-142 | `permission[id] ?? []` |
| `session.question(id)` | 143-145 | `question[id] ?? []` |
| `part(messageID)` | 147-149 | `part[messageID] ?? []` |
| `lsp()` | 150-152 | `{id, root, status}[]` |
| `mcp()` | 153-161 | `{name, status, error?}[]`, sorted by name |

### ⚠️ THERE IS NO `api.state.session.list()`

Confirmed at both ends: the implementation (`adapters.tsx:119-146`) and the type
(`packages/plugin/src/tui.ts:386-395`) expose `count / get / diff / todo / messages / status /
permission / question` and nothing else. **A plugin cannot enumerate session IDs from
`api.state`.** `count()` gives a number with no way to get the ids behind it.

**The fix the Healbot grid uses — direct import:**

```ts
import { useSync } from "../../context/sync"
const sync = useSync()          // sync.data.session : Session[]  — reactive
```

Legitimate because:
1. The grid ships as a **builtin** inside `packages/tui`, so relative imports resolve.
2. Precedent exists — `feature-plugins/system/diff-viewer.tsx:13` imports `useTheme` from
   `../../context/theme`, and `:12` imports `useBindings` from `../../keymap`.
3. Provider nesting puts every plugin route inside `<SyncProvider>` (`app.tsx:307` → `:318`),
   so `useSync()` resolves in the route component's render scope.
4. It is the **only** route to a *reactive* all-session list.

Non-reactive fallbacks, if a direct import is ever unacceptable:
`api.client.session.list()` polled with `api.state.session.count()` as a change tripwire;
`api.client.permission.list()` / `api.client.question.list()` for cold-start RED/YELLOW reconcile.

---

# `slots.tsx`

| Symbol | Line | Detail |
|---|---|---|
| `HostSlotPlugin<Slots>` | 9 | `SolidPlugin<TuiSlotMap<Slots>, TuiSlotContext>` |
| `HostSlots = { register, dispose }` | 11-17 | what `setup()` hands back to the host |
| `isHostSlotPlugin(value)` | 19-23 | requires `id: string` **and** `slots` record — **invalid plugins get a silent no-op unregister (`:53`)** |
| `createSlots()` | 25-65 | returns `{ Slot, setup(api), clear() }` |
| `Slot` indirection | 27-28 | `view` signal starts as `() => null`; `Slot` = `(props) => view()(props)` — slots render nothing until `setup()` runs |
| `createSolidSlotRegistry` | 33-47 | context = `{ theme: api.theme }`; **`onPluginError` logs and isolates** (`:37-45`) — one broken slot cannot take down the app |
| `setup(api)` | 32-60 | builds registry, installs `slot` as the view, returns `{register, dispose}` |

# `runtime.tsx`

| Symbol | Line | Detail |
|---|---|---|
| `createPluginRuntime()` | 12-35 | `{ Slot, routes, commands, status, update, clear, setupSlots }` |
| `routes` | 19 | `createPluginRoutes()` — **the registry `app.tsx:1082` reads** |
| `commands` / `status` signals | 13-14 | plugin-manager data |
| `update({commands,status})` / `clear()` | 22-30 | `clear()` also calls `slots.clear()` |
| `PluginRuntimeCommands` | 37-42 | `activate / deactivate / add / install` |
| `emptyCommands` | 44-57 | all no-ops until the host supplies real ones |
| **`TuiPluginHost`** | **61-69** | **the contract `app.tsx` requires**: `start({api, config, runtime, dispose?}): Promise<void>` + `dispose(): Promise<void>` |
| `PluginRuntimeProvider` / `usePluginRuntime` | 73-81 | Solid context; `usePluginRuntime` throws outside the provider |

# `command-shim.ts` (deprecated path)

`createCommandShim(keymap, dialog, keybinds)` `:85-109` returns `{register, trigger, show}`.
Each warns **once** (`warnOnce` `:43-47`, module-level `warned` Set `:7`) and forwards to
`keymap.registerLayer` / `dispatchCommand`. `toCommand` `:49-65` maps v1
`{value,title,slash,onSelect}` → v2 `{name,title,slashName,run}` with `namespace:"palette"`.
`toBindings` `:67-83` resolves `item.keybind` through `TuiKeybind.CommandMap`.
**New plugins should use `api.keymap.registerLayer` directly** and never touch `api.command`.

---

# Host-side per-plugin scoping (`packages/opencode/src/plugin/tui/runtime.ts`)

Not in this package, but it decides what a plugin actually receives.

| `api.*` | Line | Wrapping |
|---|---|---|
| `route.register` | 578-580 | `scope.track(...)` — auto-unregistered on deactivate |
| `route.navigate` / `.current` | 581-586 | passthrough |
| `theme` | 589-591 | prototype-chained onto host theme, `install` bound to the plugin root |
| `event.on` | 593-597 | `scope.track(...)` |
| `keymap` | 599 | `createScopedKeymap` `:143-160` |
| `mode` | 619 | `createScopedMode` `:193-201` |
| `attention` | 614 | `createScopedAttention` `:162-191`, sound paths rooted at `plugin_root` |
| `slots.register` | 603-610 | **auto-suffixes ids**: `base`, `base:1`, `base:2`… (`:605`) |
| **`state`** | **624** | **`state: api.state` — no wrapping. What `adapters.tsx:98-163` builds is exactly what plugins get** |
| `client` | 626-628 | passthrough via a `get client()` accessor |
| `plugins.*` | 632-648 | real implementations replacing the `adapters.tsx` stubs |
| `lifecycle` | 649 | real scope, replacing the `api.ts:45-50` stub |
| enable filter | 1102, 1111 | `enabled: item.enabled ?? true`; `if (!plugin.enabled) continue` |
| activation is **sequential** | 1110-1117 | `for (const plugin of next.plugins)`; comment at `:1112-1115` — command order affects keybind precedence, **route registration is last-wins on id collision** |

---

## Gotchas

| # | Gotcha | Evidence |
|---|---|---|
| P1 | **No `api.state.session.list()`.** Enumerating sessions requires `useSync` (builtin) or `client.session.list()` (non-reactive). | `adapters.tsx:119-146`; `packages/plugin/src/tui.ts:386-395` |
| P2 | `route.navigate("session", params)` **reads only `sessionID`**; all other params are dropped. | `adapters.tsx:47-52` |
| P3 | Route ids are **last-wins** (`.at(-1)`). Two plugins claiming `"healbot"` — the later-activated one silently wins. | `api.ts:35`; `runtime.ts:1114` (the comment), loop `:1110-1117` |
| P4 | `createTuiApi`'s `lifecycle` is a **dead stub** (fresh AbortController, no-op `onDispose`). Only the host-scoped api has a working one. Do not rely on `api.lifecycle` in code paths reachable outside the host. | `api.ts:45-50` vs `runtime.ts:649` |
| P5 | `api.slots.register` and `api.plugins.*` and `api.theme.install` **throw or return falsy** in the adapters layer. They only work inside a host-activated plugin. | `adapters.tsx:306-310, 311-330, 344-346` |
| P6 | `api.state.session.status(id)` returns `SessionStatus \| undefined` — `undefined` is meaningful (never-started, or finished before this process started). Do not `??` it into `"idle"`. | `adapters.tsx:137-139`; `context/CONTEXT.MAP.md` G3 |
| P7 | `TuiEventBus` declares a **one-arg** handler; the runtime passes `(event, {directory, workspace})`. Cross-directory replies need a cast to reach the metadata. | `packages/plugin/src/tui.ts:519-521` vs `context/event.ts:12-20` |
| P8 | `slots.register` silently no-ops on a malformed plugin object (`isHostSlotPlugin` fails ⇒ returns `() => {}`). No error surfaces. | `slots.tsx:19-23,53` |
| P9 | Slot render errors are caught and **logged only** (`console.error("[tui.slot] plugin error")`). A blank slot is the failure mode. Route render errors are **not** covered by this — they hit the app-level `ErrorBoundary` (`app.tsx:255`). | `slots.tsx:37-45` |
| P10 | Everything under `api.state` is a **getter over a Solid store**. Reads outside a tracking scope (`createMemo`/JSX/`createEffect`) are snapshots, not subscriptions. | `adapters.tsx:98-163` |

---

## Build levers

| Need | Lever | file:line |
|---|---|---|
| Register the grid route | `api.route.register([{ name: "healbot", render: () => <Grid api={api}/> }])` | `adapters.tsx:197-199` → `api.ts:16-32` |
| Open it from the palette | `api.keymap.registerLayer({ commands: [{ name, title, slashName, category, namespace:"palette", run(){…} }] })` | `adapters.tsx:187`; pattern `feature-plugins/system/diff-viewer.tsx:1053-1071` |
| Stash the return route | `api.route.navigate(ROUTE, { returnRoute: api.route.current })` then read it back from `api.route.current.params` | `adapters.tsx:200-205`, `:57-73`; pattern `diff-viewer.tsx:1062-1066, 95-103, 439-445` |
| Focus a session | `api.route.navigate("session", { sessionID })` | `adapters.tsx:47-52` |
| **All-session list** | `import { useSync } from "../../context/sync"` inside the route component | `context/sync.tsx:54-56`, store `:83` |
| Per-session border inputs | `api.state.session.{status,permission,question,todo}(id)` | `adapters.tsx:137-145` |
| Reply to blocked sessions | `api.client.permission.reply({requestID, reply})` / `api.client.question.reply({requestID, answers})` | `adapters.tsx:301-303` |
| PURPLE / new-session events | `api.event.on("message.part.updated" \| "session.created" \| "session.status", …)` | `adapters.tsx:304`; scoped at `runtime.ts:593-597` |
| Colors | `api.theme.current.{error,warning,success,primary,textMuted,border,borderActive}` | `adapters.tsx:331-337` |
| Persist grid prefs | `api.kv.get/set` | `adapters.tsx:289-299` |
| Toast / dialog for confirmations | `api.ui.toast`, `api.ui.DialogConfirm`, `api.ui.dialog.replace/clear` | `adapters.tsx:257-284` |
| Sound + desktop notify | `api.attention.notify({...})` (plugin-root-scoped sound paths) | `adapters.tsx:175`; `runtime.ts:614` |
| Terminal size for grid layout | `useTerminalDimensions()` from `@opentui/solid` (not on the api) | pattern `diff-viewer.tsx:14,92,138` |
