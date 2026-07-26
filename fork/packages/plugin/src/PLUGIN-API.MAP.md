# PLUGIN-API.MAP.md — `packages/plugin/src` (the public plugin contract)

Package `@opencode-ai/plugin` v1.18.5, repo `healbot/opencode` @ `0fdcfb6`. Every `file:line`
below was opened and read. Tier: **V** = read the code · **I** = inferred · **O** = open.
Bare line refs are within the file named by the section heading.

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

## 0. Entry points — `package.json` `exports`

| Import specifier | File | Surface |
|---|---|---|
| `@opencode-ai/plugin` | `index.ts` (335) | **Server plugin.** `Plugin`, `PluginInput`, `Hooks` (the ~21 hooks) |
| `@opencode-ai/plugin/tui` | `tui.ts` (634) | **TUI plugin.** `TuiPlugin`, `TuiPluginApi`, all `Tui*` types |
| `@opencode-ai/plugin/tool` | `tool.ts` (54) | `tool()` builder, `ToolDefinition`, `ToolContext`, `ToolResult` |
| `@opencode-ai/plugin/v2/effect` | `v2/effect/index.ts` | **Separate v2-core plugin system** — `define`, `PluginContext`, `Plugin` |
| `@opencode-ai/plugin/v2/effect/integration` · `/plugin` | — | narrower v2 entry points |
| `@opencode-ai/plugin/v2/promise` | `v2/promise/index.ts` | promise-flavored mirror of `v2/effect` |

Not exported (internal to the package): `shell.ts` (136, `BunShell` type), `example.ts`,
`example-workspace.ts`.

`@opentui/{core,keymap,solid}` are **optional peer deps** (`package.json` `peerDependenciesMeta`) —
`tui.ts` is types-only against them except for three value re-exports (`tui.ts:32`, `:34`, `:46`).

⚠️ **Two unrelated plugin systems live in this package.** `index.ts`'s `Hooks` is consumed *only* by
the legacy v1 engine — **zero `plugin.trigger` call sites exist in `packages/core/src` or
`packages/server/src`** (V, exhaustive grep). The v2 core uses `v2/effect` / `v2/promise` instead,
whose `PluginContext` (`v2/effect/context.ts:13-21`) exposes registration domains
`options · agent · aisdk · catalog · command · integration · plugin · reference · skill` — no
request-time hooks at all. See §2.4.

---

# PART A — `tui.ts` (the TUI plugin API)

## A1. Plugin module shape

| Symbol | Line | Signature |
|---|---|---|
| `TuiPluginModule` | **630-634** | `{ id?: string; tui: TuiPlugin; server?: never }` — default export shape |
| `TuiPlugin` | **628** | `(api: TuiPluginApi, options: PluginOptions \| undefined, meta: TuiPluginMeta) => Promise<void>` |
| `TuiPluginMeta` | 547-549 | `TuiPluginEntry & { state: "first" \| "updated" \| "same" }` |
| `TuiPluginEntry` | 532-545 | `id, source: "file"\|"npm"\|"internal", spec, target, version?, fingerprint, load_count, …` |

`server?: never` / `tui?: never` (`index.ts:79`) make server and TUI modules mutually exclusive at
the type level.

## A2. `TuiPluginApi` — full surface, declared at **`tui.ts:581-626`**

| Member | Decl | Type | Host impl (`packages/tui/src/plugin/adapters.tsx`) | Per-plugin impl (`packages/opencode/src/plugin/tui/runtime.ts`) |
|---|---|---|---|---|
| `app` | 582 | `TuiApp` (427-429) — `{ version }` | `:175` via `appApi` `:165` | `:613` pass-through |
| `attention` | 583 | `TuiAttention` (298-301) | `:176` | `:614` `createScopedAttention` |
| `command?` | **590** | `TuiCommandApi` (113-120) — **`@deprecated`** | `:178` `createCommandShim` | `:616` |
| `keys` | 591 | `TuiKeys` (74-77) — key-sequence formatters | `:179-186` | `:617` |
| `keymap` | 592 | `TuiKeymap` = `Keymap<Renderable, KeyEvent>` (79) | `:187` | `:618` `createScopedKeymap` (`:599`) |
| `mode` | 593 | `TuiModeApi` (81-84) — `current()`, `push(mode) => dispose` | `:188-195` | `:619` `createScopedMode` |
| **`route`** | **594-598** | `register(TuiRouteDefinition[]) => dispose` **:595** · `navigate(name, params?)` **:596** · `readonly current: TuiRouteCurrent` **:597** | `:196-206` | `:620` |
| `ui` | 599-609 | `Dialog` 600 · `DialogAlert` 601 · `DialogConfirm` 602 · `DialogPrompt` 603 · `DialogSelect` 604 · `Slot` 605 · `Prompt` 606 · `toast` 607 · `dialog: TuiDialogStack` 608 | `:207-285` | `:621` |
| `tuiConfig` | 610 | `Frozen<TuiConfigView>` (419-425) — deep-readonly config incl. `keybinds` lookup | `:286-288` | `:622` |
| `kv` | 611 | `TuiKV` (369-373) — `get<V>(key, fallback?)`, `set`, `ready` | `:289-299` | `:623` |
| **`state`** | **612** | `TuiState` (375-399) — see A4 | `:300` via `stateApi` **`:98-163`** | `:624` |
| `theme` | 613 | `TuiTheme` (359-367); palette `TuiThemeCurrent` (303-357) | `:331+` | `:625` scoped |
| **`client`** | **614** | `OpencodeClient` (from `@opencode-ai/sdk/v2`) — the full HTTP SDK | `:301-303` getter | `:626-628` getter |
| **`event`** | **615** | `TuiEventBus` (519-521) — see A5 | `:304` `input.event` (straight pass-through) | `:629` → `:593-597` scoped |
| `renderer` | 616 | `CliRenderer` (from `@opentui/core`) | `:305` | `:630` |
| `slots` | 617 | `TuiSlots` (512-517) — `register(TuiSlotPlugin) => id` | `:306-310` **throws** "only available in plugin context" | `:631` → real impl `:603-610` |
| `plugins` | 618-624 | `list()` · `activate(id)` · `deactivate(id)` · `add(spec)` · `install(spec, opts?)` | `:311-330` **all no-op/false** | `:632-648` real |
| `lifecycle` | 625 | `TuiLifecycle` (525-528) — `signal: AbortSignal`, `onDispose(fn) => off` | — (`adapters.tsx:173` returns `Omit<TuiPluginApi,"lifecycle">`) | `:649` `scope.lifecycle`, built `:389-421` |

⚠️ **Three members are stubs on the bare-host path.** `packages/tui/src/plugin/api.ts:42-52`
(`createTuiApi`, called from `packages/tui/src/app.tsx:388`) supplies a **fake lifecycle**:
`signal: new AbortController().signal` (never aborted) and `onDispose()` that returns a no-op and
discards `fn`. `slots.register` throws and `plugins.*` are inert on that path too. Real
implementations are installed per-plugin by `packages/opencode/src/plugin/tui/runtime.ts:612-650`.
**Builtins go through the real path** — `packages/opencode/src/plugin/tui/internal.ts:1,7` calls
`createBuiltinPlugins` from `packages/tui/src/feature-plugins/builtins.ts:22`. **V.**

## A3. `TuiRouteDefinition` and routing

| Symbol | Line |
|---|---|
| `TuiRouteDefinition` | **69-72** — `{ name: string; render: (input: { params?: Record<string, unknown> }) => JSX.Element }` |
| `TuiRouteCurrent` | 53-67 — `{name:"home"} \| {name:"session", params:{sessionID, prompt?}} \| {name:string, params?}` |

| Concern | Site |
|---|---|
| route registry (last-registered wins) | `packages/tui/src/plugin/api.ts:11-37` — `get()` returns `routes.get(name)?.at(-1)?.render` (`:34`) |
| `navigate` translation | `packages/tui/src/plugin/adapters.tsx:41-55` |
| ⚠️ **`navigate("session", …)` reads only `sessionID`** | `adapters.tsx:48-51` — any other param is dropped |
| anything else → plugin route | `adapters.tsx:54` — `route.navigate({ type: "plugin", id: name, data: params })` |
| plugin route rendered | `packages/tui/src/app.tsx:1078-1084` (memo) and **`:1122`** — `{plugin()}` sits *beside* the `<Switch>` (`:1112-1121`), not inside it, so it draws full-screen over home/session |
| unknown route id | `app.tsx:1082` → `<PluginRouteMissing>` |

`register` is on the public type, so external plugins get it too (not a builtin privilege) — **V**,
`tui.ts:595` + `runtime.ts:620`.

## A4. `TuiState` — **`tui.ts:375-399`**

| Member | Line | Backing store (`packages/tui/src/plugin/adapters.tsx`) |
|---|---|---|
| `ready` | 376 | `:100` |
| `config: SdkConfig` | 377 | `:103` |
| `provider` | 378 | `:106` |
| `path {state,config,worktree,directory}` | 379-384 | `:109` |
| `vcs {branch?, default_branch?}` | 385 | `:112` |
| **`session.count()`** | 388 | `:120` → `sync.data.session.length` |
| `session.get(id)` | 388 | `:123` |
| `session.diff(id)` | 389 | `:126` |
| `session.todo(id)` | 390 | `:132` |
| `session.messages(id)` | 391 | `:135` |
| **`session.status(id)`** | 392 | `:138` → `sync.data.session_status[id]` |
| **`session.permission(id)`** | 393 | `:141` → RED border source |
| **`session.question(id)`** | 394 | `:144` → YELLOW border source |
| `part(messageID)` | 396 | `:148` |
| `lsp()` / `mcp()` | 397-398 | `:151` / `:154` |

⚠️ **There is no `session.list()`.** The underlying store *is* an array — `adapters.tsx:120` reads
`sync.data.session.length` — but only the count is exposed. A grid needs a direct
`import { useSync } from "../../context/sync"` (precedent: `feature-plugins/system/diff-viewer.tsx`
imports `useTheme` the same way) or `api.client.session.list()` polled off `count()`.

Sidebar item types: `TuiSidebarMcpItem` 439 · `TuiSidebarLspItem` 445 · `TuiSidebarTodoItem` 447 ·
`TuiSidebarFileItem` 449.

## A5. `TuiEventBus` — **`tui.ts:519-521`** — ⚠️ KNOWN TYPE GAP

**Declared (single-arg handler):**

```ts
export type TuiEventBus = {
  on: <Type extends Event["type"]>(type: Type, handler: (event: Extract<Event, { type: Type }>) => void) => () => void
}
```

**Actual runtime (two-arg handler):** `packages/tui/src/context/event.ts`

| Line | Code |
|---|---|
| **4-7** | `type EventMetadata = { directory: string; workspace: string \| undefined }` |
| **22-24** | `function on<T>(type: T, handler: (event: Extract<Event,{type:T}>, metadata: EventMetadata) => void)` |
| **26-29** | inner subscribe invokes `handler(event as …, metadata)` |
| **12-19** | `subscribe` fills metadata from `{ event.directory, event.workspace }` on the SSE envelope |

Pass-through is unbroken end to end (**V**): `adapters.tsx:304` assigns `event: input.event`
(= `useEvent()`'s return value verbatim), and the per-plugin scope at
`packages/opencode/src/plugin/tui/runtime.ts:593-597` forwards `handler` untouched into
`api.event.on(type, handler)`.

**⇒ `metadata` reaches a plugin handler at runtime but the public type erases it. Cross-directory
routing in the grid needs a cast**, e.g.

```ts
;(api.event.on as (t: "permission.asked", h: (e: PermissionAsked, m: { directory: string; workspace?: string }) => void) => () => void)(...)
```

Prior art doing exactly this data flow (though from inside the TUI, not through the plugin type):
`packages/tui/src/context/sync.tsx:193-197` (auto-approve capture of `{directory, workspace}`).

## A6. `TuiSlotMap` and slots

| Symbol | Line | Note |
|---|---|---|
| `TuiHostSlotMap` | **455-486** | host-provided slot names → their prop shapes |
| `TuiSlotMap<Slots>` | **488** | `TuiHostSlotMap & Slots` — plugins widen it with their own slots |
| `TuiSlotShape` | 490-494 | resolves a name against host map, then plugin map, else `Record<string, unknown>` |
| `TuiSlotProps` | 496-500 | `{ name, mode?: SlotMode, children? } & TuiSlotShape` |
| `TuiSlotContext` | 502-504 | `{ theme: TuiTheme }` |
| `TuiSlotPlugin<Slots>` | 508-510 | `Omit<SolidPlugin<TuiSlotMap<Slots>, TuiSlotContext>, "id"> & { id?: never }` |
| `TuiSlots` | 512-517 | `register(plugin) => id` (overloaded for generic slot maps) |

Host slots with their prop shapes (`tui.ts:455-486`) and render sites:

All render sites verified by grep of `<pluginRuntime.Slot name=…>`; paths relative to `packages/tui/src/`.

| Slot | Props (`tui.ts`) | Rendered at | Mode |
|---|---|---|---|
| **`app`** | `{}` :456 | **`app.tsx:1127`** — outside the route `<Switch>` (`:1112-1121`) | — |
| `app_bottom` | `{}` :457 | `app.tsx:1125` | — |
| `home_logo` | `{}` :458 | `routes/home.tsx:76` | `replace` |
| `home_prompt` | `{ ref? }` :459-461 | `routes/home.tsx:82` | `replace` |
| `home_prompt_right` | `{}` :462 | `routes/home.tsx:83` | — |
| `home_bottom` | `{}` :473 | `routes/home.tsx:86` | — |
| `home_footer` | `{}` :474 | `routes/home.tsx:91` | `single_winner` |
| `session_prompt` | `{ session_id, visible?, disabled?, on_submit?, ref? }` :463-469 | `routes/session/index.tsx:1300` | — |
| `session_prompt_right` | `{ session_id }` :470-472 | `routes/session/index.tsx:1316` | — |
| `sidebar_title` | `{ session_id, title, share_url? }` :475-479 | `routes/session/sidebar.tsx:50` | — |
| `sidebar_content` | `{ session_id }` :480-482 | `routes/session/sidebar.tsx:85` | — |
| `sidebar_footer` | `{ session_id }` :483-485 | `routes/session/sidebar.tsx:90` | `single_winner` |

Registry impl + per-plugin error isolation: `packages/tui/src/plugin/slots.tsx`.
`slots.register` assigns the id from the plugin's base id, suffixing on repeat
(`packages/opencode/src/plugin/tui/runtime.ts:603-610`).

## A7. Remaining `tui.ts` types by concern

| Concern | Symbols (lines) |
|---|---|
| keybindings | `createBindingLookup` **46-51** (value export) · re-exports 31-44 · `TuiKeys` 74 · `TuiKeymap` 79 |
| deprecated command API | `TuiCommand` 91-105 · `TuiCommandApi` 113-120 — "Remove in v2" (87, 108) |
| dialogs | `TuiDialogProps` 122 · `TuiDialogStack` 128-135 · `Alert` 137 · `Confirm` 143 · `Prompt` 150 · `SelectOption` 161 · `SelectProps` 171 |
| prompt widget | `TuiPromptInfo` 183-199 · `TuiPromptRef` 201-209 · `TuiPromptProps` 211-224 |
| toast | `TuiToast` 226-231 |
| **attention** | `TuiAttentionSoundNames` **235** (value) = `["default","question","permission","error","done","subagent_done"]` · `TuiAttentionWhen` 233 · `Sound` 238 · `Notification` 246 · `SoundPack` 252 · `Soundboard` 269-274 · `NotifyInput` 276 · `NotifySkipReason` 283 · `NotifyResult` 291 · `TuiAttention` 298-301 |
| theme | `TuiThemeCurrent` 303-357 (RGBA palette + `thinkingOpacity` 356) · `TuiTheme` 359-367 |
| kv / state / app | `TuiKV` 369 · `TuiState` 375 · `TuiApp` 427 |
| internal views | `TuiBindingLookupView` 401 · `TuiAttentionConfigView` 410 · `TuiConfigView` 419 · `Frozen<>` 431-437 |
| plugin mgmt | `TuiPluginState` 530 · `TuiPluginEntry` 532 · `TuiPluginMeta` 547 · `TuiPluginStatus` 551 · `TuiPluginInstallOptions` 560 · `TuiPluginInstallResult` 564 |
| workspace | `TuiWorkspace` 576-579 — **declared but not a member of `TuiPluginApi`** |
| lifecycle | `TuiDispose` 523 · `TuiLifecycle` 525-528 |

---

# PART B — `index.ts` (the server plugin API)

## B1. Module shape

| Symbol | Line | Signature |
|---|---|---|
| `PluginModule` | 76-80 | `{ id?: string; server: Plugin; tui?: never }` |
| `Plugin` | **74** | `(input: PluginInput, options?: PluginOptions) => Promise<Hooks>` |
| `PluginInput` | 56-66 | `client` 57 · `project` 58 · `directory` 59 · `worktree` 60 · `experimental_workspace` 61-63 · `serverUrl` 64 · `$: BunShell` 65 |
| `PluginOptions` | 68 | `Record<string, unknown>` |
| `Config` | 70-72 | `Omit<SDKConfig,"plugin"> & { plugin?: Array<string \| [string, PluginOptions]> }` |
| `Hooks` | **222-335** | the ~21 hooks — see B2 |

Supporting: `ProviderContext` 20 · `WorkspaceInfo` 26 · `WorkspaceTarget` 36 · `WorkspaceAdapter` 47-54 ·
`AuthHook` 88-163 · `AuthOAuthResult` 165-208 · `ProviderHookContext` 210 · `ProviderHook` 214-217 ·
`AuthOuathResult` 220 (`@deprecated` typo alias). `export * from "./tool.js"` at :18.

## B2. The 21 hooks — declaration and live trigger sites

Dispatcher: `packages/opencode/src/plugin/index.ts` — `trigger` **:280-293** (loops every loaded
hook set, `await fn(input, output)`, returns the mutated `output`); `list` :295; `Interface` :44-57;
`TriggerName` :40-42 selects only `(input, output) => Promise<void>` members.

### Lifecycle hooks (not `trigger`-dispatched)

| Hook | Decl | Fired from | Live |
|---|---|---|---|
| `dispose` | 223 | `packages/opencode/src/plugin/index.ts:262-275` (scope finalizer) | ✅ |
| `event` | 224 | `plugin/index.ts:251-257` — `events.listen`, filtered to `event.location?.directory === ctx.directory` (**:252**) | ✅ |
| `config` | 225 | `plugin/index.ts:240-249` — once, at plugin-state init, before providers read config | ✅ |

### Registration hooks (read via `plugin.list()`, not triggered)

| Hook | Decl | Consumed at | Live |
|---|---|---|---|
| `tool` | 226-228 | `packages/opencode/src/tool/registry.ts:194-198` | ✅ |
| `auth` | 229 | `packages/opencode/src/provider/auth.ts:116-122`; `provider/provider.ts:1545-1556` | ✅ |
| `provider` | 230 | `packages/opencode/src/provider/provider.ts:1379,1393` | ✅ |

### `trigger`-dispatched hooks

| Hook | Decl | Live trigger site(s) | Live |
|---|---|---|---|
| `chat.message` | **234** | `session/prompt.ts:999-1000` | ✅ |
| `chat.params` | **247** | `session/llm/request.ts:114-115` | ✅ |
| `chat.headers` | **257** | `session/llm/request.ts:134-135` | ✅ |
| **`permission.ask`** | **261** | **NONE** | ❌ **DEAD** |
| `command.execute.before` | **262** | `session/prompt.ts:1460-1461` | ✅ |
| `tool.execute.before` | **266** | `tool/code-mode.ts:141-142` · `session/prompt.ts:307-308` · `session/tools.ts:107` | ✅ |
| `shell.env` | **270** | `plugin/pty-environment.ts:18` · `server/routes/instance/httpapi/handlers/pty.ts:71` · `tool/shell.ts:417-418` · `session/prompt.ts:554-555` | ✅ |
| `tool.execute.after` | **274** | `tool/code-mode.ts:180-181` · `session/prompt.ts:389-390` · `session/tools.ts:122,209` | ✅ |
| `experimental.chat.messages.transform` | **282** | `session/compaction.ts:350` · `session/prompt.ts:1255` | ✅ |
| `experimental.chat.system.transform` | **291** | `agent/agent.ts:381` · `session/llm/request.ts:69-70` | ✅ |
| `experimental.provider.small_model` | **297** | `provider/provider.ts:1887-1888` | ✅ |
| `experimental.session.compacting` | **305** | `session/compaction.ts:343-344` | ✅ |
| `experimental.compaction.autocontinue` | **316** | `session/compaction.ts:454-455` | ✅ |
| `experimental.text.complete` | **327** | `session/processor.ts:517` | ✅ |
| `tool.definition` | **334** | `tool/registry.ts:313` | ✅ |

All trigger paths are relative to `packages/opencode/src/`. **20 of 21 live, 1 dead.**

## B3. `permission.ask` is DEAD — CONFIRMED

**V.** Repo-wide search for `permission.ask` (all extensions, excluding `node_modules` and `dist`)
returns exactly two non-consumer hits:

| Hit | Nature |
|---|---|
| `packages/plugin/src/index.ts:261` | the declaration itself |
| `packages/core/src/plugin/skill/customize-opencode.md:354` | a doc listing that advertises the hook |

Everything else matching is a **different symbol**:

- `permission.asked` — the SSE **event** type (`packages/schema/src/v1/permission.ts:61`), consumed
  widely (`packages/tui/src/context/sync.tsx:190`, `feature-plugins/system/notifications.ts:49`, …).
- `permission.ask(...)` — the internal `PermissionV2.Service` **method**
  (`packages/opencode/src/session/processor.ts:372`), unrelated to the plugin hook.

There is no `plugin.trigger("permission.ask", …)` anywhere. **Implementing this hook is a no-op.**
To gate permissions from a plugin, react to the `permission.asked` event and reply via
`client.permission.reply({ requestID, reply })`.

## B4. `tool.ts` — the tool contract

| Symbol | Line |
|---|---|
| `ToolContext` | 3-20 — `sessionID`, `messageID`, `agent`, `directory` 11, `worktree` 16, `abort` 17, `metadata()` 18, `ask()` 19 |
| `AskInput` | 22-27 — `{ permission, patterns, always, metadata }` |
| `ToolAttachment` | 29-34 |
| `ToolResult` | 36-43 — `string \| { title?, output, metadata?, attachments? }` |
| `tool()` | **45-53** — identity builder; `tool.schema = z` (:53) |
| `ToolDefinition` | **54** — `ReturnType<typeof tool>` |

---

## C. Grid-relevant lookups

| Need | Symbol / call |
|---|---|
| register the grid screen | `api.route.register([{ name, render }])` — `tui.ts:595` |
| open it from the palette | `api.keymap.registerLayer({ commands: [...] })` — `tui.ts:592`; working pattern at `packages/tui/src/feature-plugins/system/diff-viewer.tsx:1053` |
| focus one session | `api.route.navigate("session", { sessionID })` — `tui.ts:596`; **only `sessionID` survives** (`adapters.tsx:48-51`) |
| return path | `returnRoute: api.route.current` — `tui.ts:597` |
| enumerate sessions | ⚠️ not on `api.state` — use `api.client.session.list()` (`tui.ts:614`) or a direct `useSync` import |
| session count as a change tripwire | `api.state.session.count()` — `tui.ts:388` |
| border: busy/idle | `api.state.session.status(id)` — `tui.ts:392` |
| border: RED | `api.state.session.permission(id).length > 0` — `tui.ts:393` |
| border: YELLOW | `api.state.session.question(id).length > 0` — `tui.ts:394` |
| act on RED / YELLOW | `api.client.permission.reply({requestID, reply})` / `api.client.question.reply({requestID, answers})` |
| cross-directory routing | `api.event.on(type, (event, metadata) => …)` — **needs a cast, §A5** |
| colors | `api.theme.current.*` — `tui.ts:303-357` |
| sound / desktop notify | `api.attention.notify({...})` — `tui.ts:299`; sound names `tui.ts:235` |
| teardown | `api.lifecycle.onDispose(fn)` / `api.lifecycle.signal` — `tui.ts:525-528`; ⚠️ real only on the loader path (§A2) |

---

## D. Corrections and additions to `docs/SCAN.md` / `docs/PROBE.md`

Neither document is **in this repo** (see Provenance at the top). The left column restates each
claim in full, so this table is readable without them — but the claims cannot be re-checked
against the original wording. Verdicts were re-derived from the code and stand on their own.

| Claim | Status |
|---|---|
| `TuiEventBus` declares a single-arg handler at `plugin/src/tui.ts:519-521` | **correct, exact** |
| `route.register` is public at `plugin/src/tui.ts:595` | **correct, exact** |
| `TuiPluginApi` at `plugin/src/tui.ts:582` | off by one — the type opens at **`:581`**; `:582` is its first member (`app`) |
| `permission.ask` declared at `plugin/src/index.ts:261`, zero trigger sites | **correct — independently re-verified, §B3** |
| `api.state` bridged at `tui/src/plugin/adapters.tsx:98-163` | **correct, exact** (`stateApi`) |
| `navigate` reads only `sessionID` — `adapters.tsx:48-51` | **correct, exact** |
| `createBuiltinPlugins(options)` ignores its `options` argument | **correct** — `packages/tui/src/feature-plugins/builtins.ts:22-37` never reads `options` |
| — | **New:** `api.lifecycle` / `api.slots` / `api.plugins` are stubs in `packages/tui/src/plugin/api.ts:42-52` and `adapters.tsx:306-330`; real impls only via `packages/opencode/src/plugin/tui/runtime.ts:612-650`. Builtins do get the real ones. |
| — | **New:** none of the 21 `index.ts` hooks fire on the v2 core path — zero `plugin.trigger` sites in `packages/core/src` or `packages/server/src`. The v2 core has a separate plugin system at `packages/plugin/src/v2/`. |
