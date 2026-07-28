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
| the array | 23-37 | `HomeFooter, HomeTips, SidebarContext, SidebarMcp, SidebarLsp, SidebarTodo, SidebarFiles, SidebarFooter, Notifications, PluginManager, WhichKey, DiffViewer, Healbot` |

Downstream: `packages/opencode/src/plugin/tui/internal.ts:6-10` → host `runtime.ts:1093-1103`
(`enabled: item.enabled ?? true`) → `:1110-1117` activates **sequentially**, skipping
`!plugin.enabled`. Order in this array is therefore the activation order, and route ids are
**last-wins** on collision (`plugin/api.ts:35`).

**The grid is registered.** VERIFIED: `import Healbot from "./system/healbot"` at `builtins.ts:11`,
and `Healbot` is the **last** array entry (`:36`) — so it activates last and wins any route-id
collision. This paragraph used to read "**To add the grid:** import it and append to the array at
`builtins.ts:37`", and the row above used to end `…DiffViewer, HealbotSpike`. Both were
instructions for work completed at fork `26c9316`; this map was written at `c9323db` and not
revised when `builtins.ts` was resynced at `f3c3785`. `HealbotSpike` appears nowhere in the tree.

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
| **Healbot grid** | `system/healbot.tsx` | **not quoted — `wc` it** | `healbot` | **route `"healbot"` + command `healbot.open` / `/healbot`** (`:1223-1245`); 10 in-route commands (`:995-1055`) |

Sidebar `sidebar_content` render order is `context(100) → mcp(200) → lsp(300) → todo(400) → files(500)`.

The grid's row is the one line in this table with no figure in **Lines**, deliberately.
`HARNESS.md:130-132` records that byte and line counts for `healbot.tsx` were stated three times
across this repo and all three were stale within a day; it instructs readers to `wc` the file.
This map obeys that. The row it replaced read `| Healbot spike | system/healbot-spike.tsx | 133 |
healbot-spike | route "healbot-spike" + command healbot.spike … **delete when the real grid
lands** |`. The spike was deleted, at fork `26c9316`, in the commit that landed the grid.

### Two plugin shapes

```ts
// A. slot contributor — sidebar/*, home/*, which-key
const tui: TuiPlugin = async (api) => {
  api.slots.register({ order: 100, slots: { sidebar_content(_ctx, props) { … } } })
}

// B. route owner — diff-viewer and the Healbot grid
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

# `system/healbot.tsx` — the grid, the control terminal

**This section used to document `system/healbot-spike.tsx` — "the working proof", 133 lines,
"already registered (`builtins.ts:36`)". That file no longer exists.** It was deleted at fork
`26c9316`, in the commit that landed the real grid; `find . -name 'healbot-spike*'` returns
nothing, and `HARNESS.md`'s **Traps** table records the same resolution. Everything below is the shipped grid.

Shape B, built from `diff-viewer`'s skeleton. **No line or byte count is quoted here** — see the
inventory note above and `HARNESS.md:130-132`. `wc` it.

| Element | Line | Detail |
|---|---|---|
| `const ROUTE = "healbot"` | 15 | |
| plugin body | 1218-1246 | the `selected` signal lives in the **plugin closure** (`:1221`), not the component — the which-key pattern (`which-key.tsx:533-535`), so selection survives focusing a session and coming back |
| route registration | 1223-1228 | `render: () => <Healbot api selected setSelected />` |
| palette command `healbot.open` / `/healbot` | 1230-1245 | `namespace:"palette"`; stashes `returnRoute: api.route.current` (`:1239`), then `api.ui.dialog.clear()` (`:1241`, F4) |
| `export default { id: "healbot", tui }` | 1248-1251 | |
| **10 in-route commands** | 995-1055 | `healbot.close`:996, `.left`:997, `.right`:998, `.up`:999, `.down`:1000, `.refresh`:1001, `.focus`:1003, `.answer`:1016, `.retire`:1027, `.next-blocked`:1039 |
| **`useBindings` + `keybinds.gather("healbot", …)`** | 1057-1085 | the `diff-viewer` path, not the spike's `useKeyboard` — grid keys are in the palette, in which-key, and user-overridable |
| **`mode: OPENCODE_BASE_MODE` + `enabled: !answering()`** | 1064-1065 | the part `diff-viewer` has no equivalent for: it hands the keyboard to the docked answer panel, which collides on almost every key (j/k/h/l, 1-9, return, escape) |
| shape-checked `returnRoute` read | 958-964 | `leave()` at `:966-970` falls back to `"home"` on a malformed param |
| **every `api.event.on` wrapped in `onCleanup`** | 665, 677-678, 707, 714-715, 976-977, 992-993 | nine subscriptions, all released on unmount |
| direct host imports | 4, 6 | `useTerminalDimensions` from `@opentui/solid`; **`useSync` from `../../context/sync`** — the direct-import precedent (F7) cashed in |

**Two things the spike did better than `diff-viewer`, and the grid kept both:**

1. **`onCleanup` around every `api.event.on`.** The unsubscribe the host returns is tracked to the
   **plugin** scope (`packages/opencode/src/plugin/tui/runtime.ts:593-597`), not to the component —
   so without this, each route mount leaves more live handlers writing into a disposed component's
   signals. `routes/session/index.tsx:320,350` omits it and gets away with it only because those
   handlers self-neuter on a `part.sessionID !== route.sessionID` guard. The grid subscribes nine
   times and has no such excuse; `:972-975` says so in place.
2. **A shape-checked `returnRoute` read** (`:958-964`) instead of `diff-viewer`'s unvalidated cast
   of the whole params bag (`diff-viewer.tsx:95-103`), so a malformed param falls back to `"home"`
   rather than attempting a bad navigate.

## The grid does not own automatic retirement

Since Phase 6 it does not, and this map is the last place that had not been told. `RETIRE_AT`
(`:53`, default 256,000, `HEALBOT_RETIRE_AT`) survives in this file for **presentation only** —
the `RETIRE` border (`:411`), the header's `N to retire` count, and each cell's
share-of-threshold figure (`:509`). Manual retirement, `x` → `healbot.retire` (`:1027-1037`), is
still here. The automatic gate moved to the **server** plugin
(`harness/config/opencode/plugin/healbot.ts`) because a `createEffect` in this component could
only run while the route was mounted: `enter` unmounts the route (`app.tsx:1079-1085` recomputes
the plugin route and returns `undefined` once `route.data.type !== "plugin"`), and a fleet left
running with no client attached retired nothing at all. **Exactly one process may own the gate** —
the effect was deleted here rather than kept as a fallback, so an operator's `x` and the server
plugin cannot each spawn a successor. Reasoning in full at `healbot.tsx:55-83`.

**The gate fires at a STEP boundary, not at the end of a turn** — VERIFIED. `processor.ts:435` is
the `step-finish` case; `:443-445` assign `finish`, `cost` and `tokens` in the same mutation, and
`:445` is the only site in the session tree that writes a non-zero `tokens`. So every
`message.updated` that carries occupancy at all also carries a set `finish` — usually
`"tool-calls"`, i.e. mid-turn. MEASURED across 733 real assistant messages with occupancy > 0:
zero had a null `finish` (677 `tool-calls`, 56 `stop`).

Two consequences reach this file. The turn in flight **is** aborted, so overshoot past the gate is
bounded by one step (~65K measured) rather than one whole turn (~170K measured) — better than the
behaviour that was designed and documented, and arrived at by accident. What that looks like on
screen is a cell going `RETIRE` and then gone mid-turn rather than at a turn boundary. And the
server plugin's `RETIRE_HARD` (330,000, `HEALBOT_RETIRE_HARD`) is **inert** — its only consumer is
dominated by the per-step predicate, which is true 733/733 — so a reader who comes here looking
for a second threshold to tune will not find one, in this file or in effect. The hinge is one
function: the server plugin's `stepFinished()` versus opencode's own per-turn predicate at
`prompt.ts:1295` (`finish && !["tool-calls","unknown"].includes(finish)`). Swapping them switches
the harness to per-turn retirement and makes the hard gate load-bearing again. Unchanged by any of
this: the ~360K ceiling, the 256,000 default, and the handoff document.

---

## Gotchas

| # | Gotcha | Evidence |
|---|---|---|
| F1 | `createBuiltinPlugins(options)` **ignores its `options` argument**. Anything flag-gated must read the flag itself. | `builtins.ts:22-38` |
| F2 | Activation is **sequential and order-dependent** — commands registered earlier win keybind precedence; routes are **last-wins** on id collision. Array position in `builtins.ts:23-37` is meaningful. | `packages/opencode/src/plugin/tui/runtime.ts:1110-1117`; `plugin/api.ts:35` |
| F3 | `enabled: false` (which-key) means the plugin never runs at boot; users flip it via `plugin_enabled` config or the plugin manager. | `which-key.tsx:604`; `runtime.ts:479,670-672,1102` |
| F4 | Opening a route from a palette command **must** call `api.ui.dialog.clear()` or the dialog stays layered over the route. | `diff-viewer.tsx:1067`; `healbot.tsx:1090` |
| F5 | Route params are read via `"params" in api.route.current ? …` and cast without validation. A missing param is `undefined`, not an error. | `diff-viewer.tsx:95-103` |
| F6 | `notifications.ts` state is **plugin-local Sets, lost on restart**. Any "finished" signal derived from it — or from `session_status` — is process-local. | `notifications.ts:30-33`; `context/CONTEXT.MAP.md` G3 |
| F7 | Feature-plugins freely import host internals with relative paths (`../../keymap`, `../../context/theme`, `../../ui/dialog-select`). This is builtin-only; external plugins get `api` and the `package.json` exports map. | `diff-viewer.tsx:11-20`; `plugins.tsx:5,7` |
| F8 | Only `sidebar_*` slot handlers receive `props.session_id` (`(_ctx, props)`); `app`/`app_bottom`/`home_*` handlers take no session. A slot-based grid would have no session context — another reason to use a route. | `sidebar/context.tsx:53` vs `which-key.tsx:584,591` |

**F9 is gone.** It read: "`healbot-spike.tsx` is registered in `builtins.ts:36` and will keep
appearing as `/healbot` in the palette until removed. Pick a **different** route name and slash
name for the real grid, or delete the spike in the same change." The second option is what
happened, at fork `26c9316`, so `/healbot` belongs to `healbot.tsx:1082-1084` and there is nothing to
collide with. `HARNESS.md`'s **Traps** table already carried this as struck-through and resolved.

---

## How the grid was built — a record, not a to-do list

**This table used to be a set of instructions.** The work is done; it is kept because each row
names where a pattern was lifted from, which is the provenance a reader of `healbot.tsx` will
want. Read it as history. Rows 16 and 18 are the two that were **not** taken — see the note below
the table.

| Step | Lift from | file:line |
|---|---|---|
| 1. Create `system/healbot.tsx` with shape B | `diff-viewer.tsx:1045-1072` | route + palette command + `dialog.clear()` → shipped at `healbot.tsx:1072-1090` |
| 2. Register it | `builtins.ts` | shipped: import at `:11`, last array entry at `:36`; `HealbotSpike` dropped in the same commit |
| 3. All-session list | **direct import** `useSync` — precedent is the `useTheme` import | `diff-viewer.tsx:13`; store `context/sync.tsx:83` |
| 4. Border: amber / green / dim | the `active` Set discriminator | `notifications.ts:59-78` (esp. `:68`) |
| 5. Border: RED / YELLOW | `api.state.session.permission(id)` / `.question(id)` length | `plugin/adapters.tsx:140-145` |
| 6. Border: red-flash on error | `errored` Set + `session.error` handler | `notifications.ts:80-86` |
| 7. Border: PURPLE | `api.event.on("message.part.updated")`, `part.type === "compaction"`, `part.sessionID` | `context/CONTEXT.MAP.md` build levers |
| 8. Subagent cells render differently | `session?.parentID !== undefined` | `notifications.ts:11,77` |
| 9. New sessions appear | `api.event.on("session.created", …)` → `useSync().session.refresh()` | GAP-1, `context/CONTEXT.MAP.md` |
| 10. Cold cell content | `useSync().session.sync(id)` inside a guarded `onMount` — copy the shape of `routes/session/index.tsx:2213-2222` (its `stringValue` helper is module-local and unnecessary here: grid cells already hold typed `Session.id`s) | GAP-2, `context/sync.tsx:588-660` |
| 11. Click/key to act | reuse `<PermissionPrompt request directory/>` / `<QuestionPrompt request directory/>` | `routes/session/permission.tsx:111`; `question.tsx:14` |
| 12. Focus a session | `api.route.navigate("session", { sessionID })` | `plugin/adapters.tsx:47-52`; `returnRoute` variant shipped at `healbot.tsx:958-970` |
| 13. Return out | `returnRoute` round-trip | `diff-viewer.tsx:1065` + `:439-445` |
| 14. Grid keys in the palette / user-overridable | `useBindings` + `keybinds.gather` | `diff-viewer.tsx:737-750` |
| 15. Responsive columns | `useTerminalDimensions()` + width threshold | `diff-viewer.tsx:92,138-146` |
| 16. Persist layout / filters | `api.kv.get/set` | `diff-viewer.tsx:43-45,133-146` |
| 17. Selection state that survives navigation | signals in the plugin closure | `which-key.tsx:533-535` |
| 18. Retirement confirm + result toast | `api.ui.DialogConfirm` / `api.ui.toast` | `plugins.tsx:68-99` |
| 19. Sound + desktop notify on state change | `api.attention.notify({...})` with the 6 sound names | `notifications.ts:9-18`; `src/attention.ts:46,170` |

**Two levers were not taken.** VERIFIED by grep over `healbot.tsx`: there is no `api.kv.` call
(16) and no `DialogConfirm` or `api.ui.toast` (18) — `x` retires without a confirmation step, and
nothing about the layout persists across a restart. Both remain open if wanted; the citations
above still point at working examples. Lever 18's premise has also narrowed since it was written:
automatic retirement is the server plugin's now, so a confirm dialog here would gate only the
manual `x` path.
