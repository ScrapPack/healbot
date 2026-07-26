# FEATURE-PLUGINS.MAP.md — `packages/tui/src/feature-plugins`

Built-in TUI plugins. Every one is a `TuiPlugin` consuming the api from
`src/plugin/PLUGIN.MAP.md`. The Healbot grid ships as one of these.
Parent map: `packages/tui/TUI.MAP.md`.

> **Path convention.** A citation prefixed `packages/…` is repo-relative. A **bare path** resolves
> against, in order: (1) this file's own directory, (2) the owning package's `src/`, (3) the repo
> root — all three are in use here. A bare **`:NNN`** is a line in the file named by the enclosing
> section heading or table row.

---

## Registration

`builtins.ts` (38 lines) is the whole registry.

| Item | Line | Detail |
|---|---|---|
| imports | 2-14 | one default import per plugin |
| `BuiltinTuiPlugin` type | 16-20 | `Omit<TuiPluginModule,"id"> & { id: string; tui: TuiPlugin; enabled?: boolean }` |
| `createBuiltinPlugins(options)` | 22-38 | returns the array; **`options` is declared and never read** — dead parameter |
| the array | 23-37 | `HomeFooter, HomeTips, SidebarContext, SidebarMcp, SidebarLsp, SidebarTodo, SidebarFiles, SidebarFooter, Notifications, PluginManager, WhichKey, DiffViewer, HealbotSpike` |

Downstream: `packages/opencode/src/plugin/tui/internal.ts:6-10` → host `runtime.ts:1093-1103`
(`enabled: item.enabled ?? true`) → `:1110-1117` activates **sequentially**, skipping
`!plugin.enabled`. Order in this array is therefore the activation order, and route ids are
**last-wins** on collision (`plugin/api.ts:35`).

**To add the grid:** import it and append to the array at `builtins.ts:37`. Nothing else.

---

## Inventory

| Plugin | File | Lines | `id` | Registers |
|---|---|---|---|---|
| Home footer | `home/footer.tsx` | 100 | `internal:home-footer` | slot `home_footer` (order 100, `:86-88`) |
| Home tips | `home/tips.tsx` (+ `tips-view.tsx` 287) | 59 | `internal:home-tips` | command `tips.toggle` (`:13`), slot `home_bottom` (order 100, `:37-39`) |
| Sidebar context | `sidebar/context.tsx` | 65 | `internal:sidebar-context` | slot `sidebar_content` order **100** (`:51-53`) |
| Sidebar MCP | `sidebar/mcp.tsx` | 97 | `internal:sidebar-mcp` | slot `sidebar_content` order **200** (`:83-85`) |
| Sidebar LSP | `sidebar/lsp.tsx` | 65 | `internal:sidebar-lsp` | slot `sidebar_content` order **300** (`:51-53`) |
| Sidebar todo | `sidebar/todo.tsx` | 49 | `internal:sidebar-todo` | slot `sidebar_content` order **400** (`:35-37`) |
| Sidebar files | `sidebar/files.tsx` | 70 | `internal:sidebar-files` | slot `sidebar_content` order **500** (`:56-58`) |
| Sidebar footer | `sidebar/footer.tsx` | 98 | `internal:sidebar-footer` | slot `sidebar_footer` order 100 (`:84-86`) |
| **Notifications** | `system/notifications.ts` | 94 | `internal:notifications` | **events only — no UI** |
| Plugin manager | `system/plugins.tsx` | 269 | `internal:plugin-manager` | commands `plugins.list`, `plugins.install` (`:238-262`) |
| **Which-key** | `system/which-key.tsx` | 608 | `which-key` | 3 commands + slots `home_bottom`/`app`/`app_bottom` (`:578-597`). **`enabled: false`** (`:604`) |
| **Diff viewer** | `system/diff-viewer.tsx` (+ `-ui` 103, `-file-tree` 162, `-file-tree-utils` 232) | 1077 | `diff-viewer` | **route `"diff"` + command `diff.open`** (`:1045-1072`) |
| Healbot spike | `system/healbot-spike.tsx` | 133 | `healbot-spike` | route `"healbot-spike"` + command `healbot.spike` (`:104-128`) — **delete when the real grid lands** |

Sidebar `sidebar_content` render order is `context(100) → mcp(200) → lsp(300) → todo(400) → files(500)`.

### Two plugin shapes

```ts
// A. slot contributor — sidebar/*, home/*, which-key
const tui: TuiPlugin = async (api) => {
  api.slots.register({ order: 100, slots: { sidebar_content(_ctx, props) { … } } })
}

// B. route owner — diff-viewer, healbot-spike, and the Healbot grid
const tui: TuiPlugin = async (api) => {
  api.route.register([{ name: ROUTE, render: () => <View api={api} /> }])
  api.keymap.registerLayer({ commands: [{ …, run() { api.route.navigate(ROUTE, {…}) } }] })
}
```

Both export `default { id, tui }` (optionally `enabled`).

---

# `system/diff-viewer.tsx` — THE reference for the grid

Shape B, at full scale. Lift the skeleton wholesale.

## Registration (`:1045-1072`) — copy this exactly

| Line | Code |
|---|---|
| 1046-1051 | `api.route.register([{ name: ROUTE, render: () => <DiffViewer api={api} /> }])` |
| 1053-1071 | `api.keymap.registerLayer({ commands: [{ name:"diff.open", title, slashName:"diff", category:"VCS", namespace:"palette", run(){…} }] })` |
| 1062-1066 | `api.route.navigate(ROUTE, { mode, sessionID: "params" in api.route.current ? api.route.current.params?.sessionID : undefined, returnRoute: api.route.current })` |
| 1067 | `api.ui.dialog.clear()` — **required**, otherwise the palette dialog stays over the route |
| 1074-1077 | `export default { id: "diff-viewer", tui }` |
| 38 | `const ROUTE = "diff"` |

## In-route patterns to lift

| Pattern | Line | Detail |
|---|---|---|
| **Direct host imports alongside the api** | 12-14 | `useBindings, useCommandShortcut` from `../../keymap`; **`useTheme` from `../../context/theme`** — the precedent that legitimises `useSync` |
| Read route params | 95-103 | `("params" in props.api.route.current ? …params : undefined) as {mode?, sessionID?, messageID?, returnRoute?}` — cast, no validation |
| Theme accessor | 94 | `const theme = () => props.api.theme.current` — a **function**, keeps reads reactive |
| Async data via `createResource` | 105-130 | memo'd input → `api.client.*` fetch |
| Read session state | 111 | `props.api.state.session.get(sessionID)?.directory` |
| KV-backed view prefs | 43-45, 133-146 | `KV_SHOW_FILE_TREE`, `KV_SINGLE_PATCH`, `KV_VIEW`; `api.kv.get<boolean>(key, default)` |
| Responsive layout | 138-146 | `useTerminalDimensions()`, split vs unified on a width threshold (`MIN_SPLIT_WIDTH = 100`, `:39`) |
| Dialog cleanup on unmount | 176 | `onCleanup(() => props.api.ui.dialog.clear())` |
| **20 in-route commands** | 433-736 | `diff.close`:435, `.down`:449, `.up`:463, `.page.down`:477, `.page.up`:491, `.toggle`:505, `.expand`:516, `.expand_all`:534, `.collapse`:545, `.next_hunk`:564, `.previous_hunk`:572, `.next_file`:580, `.previous_file`:588, `.mark_reviewed`:596, `.switch_focus`:604, `.toggle_file_tree`:617, `.single_patch`:628, `.switch_source`:655, `.toggle_view`:663, `.help`:675 |
| **The return path** | 439-445 | `const returnRoute = params()?.returnRoute; api.ui.dialog.clear(); api.route.navigate(returnRoute?.name ?? "home", returnRoute && "params" in returnRoute ? returnRoute.params : undefined)` |
| Re-navigate to self to change params | 709-730 (`navigate` at 720-725) | `openSwitchDiffDialog` → `api.route.navigate(ROUTE, {...})` — the route re-renders with new params |
| **Bind commands + defaults + config overrides** | 737-750 | `useBindings(() => ({ commands, bindings: [ {key:"j,down", cmd:"diff.down", desc}, …, ...props.api.tuiConfig.keybinds.gather("diff", commands.map(c => c.name)) ] }))` |
| Full-screen container | 753 | `<box position="absolute" zIndex={2500} left={0} top={0} width={dimensions().width} height={dimensions().height}>` |
| Loading / empty / error states | 765-783 | `<Switch>` over `diff.loading` / `files().length === 0` / `diff.error` |
| Help dialog | 732-735 (`setSize("large")` at 734); component at 946-1043 | `openHelpDialog` → `api.ui.dialog.replace(() => <DiffViewerHelpDialog/>)` |

**What the Healbot grid takes:** the entire outer skeleton — route+command registration,
`returnRoute` round-trip, `useBindings` with config-gathered overrides, the absolute
full-screen box, and the direct-import precedent.

---

# `system/notifications.ts` — THE reference for border state

94 lines, no UI. The most concentrated piece of state logic in the tree.

| Element | Line | Detail |
|---|---|---|
| `notify(api, sessionID, message, sound)` | 9-18 | resolves the session, sets `isSubagent = session?.parentID !== undefined`, calls `api.attention.notify({ title, message, notification: isSubagent ? false : {when:"blurred"}, sound: {name, when:"always"} })` |
| `sessionErrorMessage(error)` | 20-27 | `MessageAbortedError` → `"Session aborted"`; `"SSE read timed out"` → `"Model stopped responding"`; else `"Session error"` |
| **four Sets** | 30-33 | `active`, `errored`, `questions`, `permissions` — **all plugin-local, all keyed by id** |
| `question.asked` | 35-39 | dedup on `properties.id` before notifying |
| `question.replied` / `.rejected` | 41-47 | `questions.delete(properties.requestID)` |
| `permission.asked` | 49-53 | dedup on `properties.id` |
| `permission.replied` | 55-57 | `permissions.delete(properties.requestID)` |
| **`session.status`** | **59-78** | **the discriminator — see below** |
| `session.error` | 80-86 | only if `active.has(sessionID)`; sets `errored` so the following idle is suppressed |

## The finished-vs-never-started discriminator (`:59-78`)

```ts
api.event.on("session.status", (event) => {
  const sessionID = event.properties.sessionID
  if (status.type === "busy" || status.type === "retry") {   // :61
    active.add(sessionID); errored.delete(sessionID); return  // :62-64
  }
  if (status.type !== "idle") return                          // :67
  if (!active.has(sessionID)) return                          // :68  ← THE DISCRIMINATOR
  active.delete(sessionID)                                    // :69
  if (errored.has(sessionID)) { errored.delete(sessionID); return }   // :71-74
  const session = api.state.session.get(sessionID)            // :76
  notify(api, sessionID, "Session done", session?.parentID ? "subagent_done" : "done")  // :77
})
```

Line `:68` is the whole trick: **an `idle` only counts as "finished" if this process previously
saw the session go `busy`.** A session that was never active in this process emits/settles idle
and is correctly ignored.

**What the grid lifts:** exactly this, as the green-border rule.
`active.has(id)` ⟹ amber; `!active.has(id) && everWasActive` ⟹ green; never in `active` and
never seen ⟹ dim. The store-based equivalent (`session_status[id]` present && `.type === "idle"`)
works for the same reason — the server deletes idle entries from its own map so the seed never
contains them (`packages/opencode/src/session/status.ts:42-45`; see `context/CONTEXT.MAP.md` G3).
Both are **process-local**: after a restart, yesterday's finished session reads dim, not green.

Also lift: the `errored` suppression (`:71-74`, `:80-86`) — otherwise a failed session flashes
green when it settles, and the `parentID` subagent branch (`:11`, `:77`) — subagents should
render differently from root sessions in a grid.

---

# `system/which-key.tsx` — slot overlay + disabled-by-default

608 lines, shape A. Relevant for what a grid should *not* do.

| Element | Line | Detail |
|---|---|---|
| command names | 10-23 | `which-key.toggle` / `.layout` / `.pending` |
| **`LAYER_PRIORITY = 900`** | 24 | `registerLayer({ priority: LAYER_PRIORITY, … })` (`:538`) — layers stack by priority |
| KV keys | 25-26 | `which_key_layout`, `which_key_pending_preview` |
| `ink(api, name, fallback)` | 94-99 | `Reflect.get(api.theme.current, name)` — **reads theme colors by string name**, useful for a configurable border palette |
| `skin(api)` | 101-113 | assembles a color set once per render |
| `commandShortcut(api, name)` | 158-164 | `api.keys.formatSequence(...)` for display |
| plugin body | 532-598 | 3 signals (`pinned`, `mode`, `pendingPreview`) held in the **plugin closure**, not a context — survives route changes |
| `api.slots.register` | 578-597 | `order: 200`; slots `home_bottom` (`:581`), `app` (overlay mode, `:584`), `app_bottom` (dock mode, `:591`) |
| **`enabled: false`** | 604 | ships **off**; enabled via `plugin_enabled` config / plugin manager (`runtime.ts:479,670-672`) |

**Lift:** the closure-held signal pattern (grid selection index / filter should live in the
plugin closure so it survives navigating away and back), and `enabled: false` if Healbot
should be opt-in. **Do not** copy the `app`-slot overlay approach — a grid wants a route.

---

# `system/plugins.tsx` — dialog-only plugin

269 lines. Registers commands but **no route and no slot**; everything renders through
`api.ui.dialog.replace`.

| Element | Line | Detail |
|---|---|---|
| `state(api, item)` | 11-21 | colored status text from `api.theme.current.{textMuted,success,error}` |
| `meta(item, width)` / `source(spec)` | 28-36 / 23-26 | row formatting against available width |
| `Install` | 38-133 | `<props.api.ui.DialogPrompt>` with a tab-toggled scope; drives `api.plugins.install` (`:76`) / `.add` (`:107`); reports via `api.ui.toast` |
| `row(api, item, width)` | 135-144 | builds a `DialogSelectOption<string>` |
| `View` | 150-232 | `DialogSelect` list; `api.ui.dialog.setSize("xlarge"\|"large"\|"medium")` by width (`:159,163,166`); toggles via `api.plugins.activate/deactivate` (`:185`) and re-reads `api.plugins.list()` (`:194`) |
| `show` / `showInstall` | 234-236 / 146-148 | `api.ui.dialog.replace(() => <View api={api}/>)` |
| registration | 238-262 | commands `plugins.list`, `plugins.install`, `namespace:"palette"`, bindings via `api.tuiConfig.keybinds.gather("plugins.palette", [...])` |

**Lift:** the `api.ui.dialog.setSize` width-responsive pattern, and `keybinds.gather(section, names)`
for user-overridable bindings. Useful if the grid grows a settings dialog. Also the model for a
Healbot *retirement confirmation* dialog (`api.ui.DialogConfirm` + toast on result).

---

# `system/healbot-spike.tsx` — the working proof

133 lines. Already in the tree, already registered (`builtins.ts:36`).

| Proof | Line |
|---|---|
| route registration | 106-111 |
| palette command `healbot.spike` / `/healbot` | 113-127 |
| `useKeyboard` — route owns the keyboard | 58-71 |
| **`returnRoute` round-trip** — stash `:122`, shape-checked read `:29-35`, navigate back `:64-66` | 29-35, 64-66, 122 |
| `api.client.session.list()` data path | 38-41 |
| `api.event.on(…)` ×4, **each wrapped in `onCleanup`** | 48-55 |
| theme accessor as a function | 17 |
| `<box border borderColor={theme().primary}>` — the border mechanism | 75, 79, 92 |
| `export default { id: "healbot-spike", tui }` | 130-133 |

Its `useKeyboard` approach (`:58`) is the *cheap* path; `diff-viewer`'s
`useBindings` + `keybinds.gather` (`diff-viewer.tsx:737-750`) is the *correct* one — it puts
grid keys in the command palette, in which-key, and under user override. Migrate when the real
grid lands.

**Two things here are deliberately more correct than `diff-viewer`, and the grid should keep both:**

1. **`onCleanup` around every `api.event.on`** (`:48-55`). The unsubscribe the host returns is
   tracked to the **plugin** scope (`packages/opencode/src/plugin/tui/runtime.ts:593-597`), not to
   the component — so without this, each route mount leaves more live handlers writing into a
   disposed component's signals. `routes/session/index.tsx:320,350` omits it and gets away with it
   only because those handlers self-neuter on a `part.sessionID !== route.sessionID` guard. A grid
   subscribing to `message.part.updated` (fires per token delta) has no such excuse.
2. **A shape-checked `returnRoute` read** (`:29-35`) instead of `diff-viewer`'s unvalidated cast of
   the whole params bag (`diff-viewer.tsx:95-103`), so a malformed param falls back to `"home"`
   rather than attempting a bad navigate.

---

## Gotchas

| # | Gotcha | Evidence |
|---|---|---|
| F1 | `createBuiltinPlugins(options)` **ignores its `options` argument**. Anything flag-gated must read the flag itself. | `builtins.ts:22-38` |
| F2 | Activation is **sequential and order-dependent** — commands registered earlier win keybind precedence; routes are **last-wins** on id collision. Array position in `builtins.ts:23-37` is meaningful. | `packages/opencode/src/plugin/tui/runtime.ts:1110-1117`; `plugin/api.ts:35` |
| F3 | `enabled: false` (which-key) means the plugin never runs at boot; users flip it via `plugin_enabled` config or the plugin manager. | `which-key.tsx:604`; `runtime.ts:479,670-672,1102` |
| F4 | Opening a route from a palette command **must** call `api.ui.dialog.clear()` or the dialog stays layered over the route. | `diff-viewer.tsx:1067`; `healbot-spike.tsx:123` |
| F5 | Route params are read via `"params" in api.route.current ? …` and cast without validation. A missing param is `undefined`, not an error. | `diff-viewer.tsx:95-103` |
| F6 | `notifications.ts` state is **plugin-local Sets, lost on restart**. Any "finished" signal derived from it — or from `session_status` — is process-local. | `notifications.ts:30-33`; `context/CONTEXT.MAP.md` G3 |
| F7 | Feature-plugins freely import host internals with relative paths (`../../keymap`, `../../context/theme`, `../../ui/dialog-select`). This is builtin-only; external plugins get `api` and the `package.json` exports map. | `diff-viewer.tsx:11-20`; `plugins.tsx:5,7` |
| F8 | Only `sidebar_*` slot handlers receive `props.session_id` (`(_ctx, props)`); `app`/`app_bottom`/`home_*` handlers take no session. A slot-based grid would have no session context — another reason to use a route. | `sidebar/context.tsx:53` vs `which-key.tsx:584,591` |
| F9 | `healbot-spike.tsx` is registered in `builtins.ts:36` and will keep appearing as `/healbot` in the palette until removed. Pick a **different** route name and slash name for the real grid, or delete the spike in the same change. | `builtins.ts:11,36`; `healbot-spike.tsx:14,118` |

---

## Build levers — Healbot grid assembly

| Step | Lift from | file:line |
|---|---|---|
| 1. Create `system/healbot.tsx` with shape B | `diff-viewer.tsx:1045-1072` | route + palette command + `dialog.clear()` |
| 2. Register it | `builtins.ts:37` | append to the array (and drop `HealbotSpike` at `:11,:36`) |
| 3. All-session list | **direct import** `useSync` — precedent is the `useTheme` import | `diff-viewer.tsx:13`; store `context/sync.tsx:83` |
| 4. Border: amber / green / dim | the `active` Set discriminator | `notifications.ts:59-78` (esp. `:68`) |
| 5. Border: RED / YELLOW | `api.state.session.permission(id)` / `.question(id)` length | `plugin/adapters.tsx:140-145` |
| 6. Border: red-flash on error | `errored` Set + `session.error` handler | `notifications.ts:80-86` |
| 7. Border: PURPLE | `api.event.on("message.part.updated")`, `part.type === "compaction"`, `part.sessionID` | `context/CONTEXT.MAP.md` build levers |
| 8. Subagent cells render differently | `session?.parentID !== undefined` | `notifications.ts:11,77` |
| 9. New sessions appear | `api.event.on("session.created", …)` → `useSync().session.refresh()` | GAP-1, `context/CONTEXT.MAP.md` |
| 10. Cold cell content | `useSync().session.sync(id)` inside a guarded `onMount` — copy the shape of `routes/session/index.tsx:2213-2222` (its `stringValue` helper is module-local and unnecessary here: grid cells already hold typed `Session.id`s) | GAP-2, `context/sync.tsx:588-660` |
| 11. Click/key to act | reuse `<PermissionPrompt request directory/>` / `<QuestionPrompt request directory/>` | `routes/session/permission.tsx:111`; `question.tsx:14` |
| 12. Focus a session | `api.route.navigate("session", { sessionID })` | `plugin/adapters.tsx:47-52`; `returnRoute` variant `healbot-spike.tsx:64-66` |
| 13. Return out | `returnRoute` round-trip | `diff-viewer.tsx:1065` + `:439-445` |
| 14. Grid keys in the palette / user-overridable | `useBindings` + `keybinds.gather` | `diff-viewer.tsx:737-750` |
| 15. Responsive columns | `useTerminalDimensions()` + width threshold | `diff-viewer.tsx:92,138-146` |
| 16. Persist layout / filters | `api.kv.get/set` | `diff-viewer.tsx:43-45,133-146` |
| 17. Selection state that survives navigation | signals in the plugin closure | `which-key.tsx:533-535` |
| 18. Retirement confirm + result toast | `api.ui.DialogConfirm` / `api.ui.toast` | `plugins.tsx:68-99` |
| 19. Sound + desktop notify on state change | `api.attention.notify({...})` with the 6 sound names | `notifications.ts:9-18`; `src/attention.ts:46,170` |
