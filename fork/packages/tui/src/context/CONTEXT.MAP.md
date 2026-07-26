# CONTEXT.MAP.md — `packages/tui/src/context`

Solid context providers = all shared TUI state. `sync.tsx` is the all-session store the Healbot
grid reads. Parent map: `packages/tui/TUI.MAP.md`.

> Filename note: this file is `CONTEXT.MAP.md`, **not** `CONTEXT.md`. opencode auto-ingests
> `AGENTS.md`/`CLAUDE.md`/`CONTEXT.md` into the model's context window; `.MAP.md` is inert.

> **Path convention.** A citation prefixed `packages/…` is repo-relative. A **bare path** resolves
> against, in order: (1) this file's own directory, (2) the owning package's `src/`, (3) the repo
> root — all three are in use here. A bare **`:NNN`** is a line in the file named by the enclosing
> section heading or table row.

---

## File table

| File | Lines | Hook / provider | Owns |
|---|---|---|---|
| **`sync.tsx`** | **666** | `useSync` / `SyncProvider` | **The store.** All sessions, statuses, permissions, questions, messages, parts, todos, diffs, providers, agents, commands, config, lsp, mcp, formatter, vcs |
| `sdk.tsx` | 151 | `useSDK` / `SDKProvider` | `OpencodeClient` instance + **the global SSE feed** + 16ms event batching |
| `event.ts` | 36 | `useEvent()` (plain fn, no provider) | Typed `subscribe`/`on` over the SSE emitter; attaches `{directory, workspace}` metadata |
| `data.tsx` | 569 | `useData` / `DataProvider` | **v2 (`session.next.*`) event store.** One consumer only — see below |
| `theme.tsx` | 332 | `useTheme` / `ThemeProvider` | Active theme, dark/light mode, lock, syntax styles |
| `route.tsx` | 60 | `useRoute` / `RouteProvider` | `Route = HomeRoute \| SessionRoute \| PluginRoute`; `navigate()` |
| `local.tsx` | 542 | `useLocal` / `LocalProvider` | Per-user prefs: `model`, `agent`, `mcp`, `session` (quick-switch), `permission` (re-export of `usePermission`, `:62,:538`) |
| `editor.ts` | 408 | `useEditor` | External-editor / IDE integration, selections, mentions |
| `project.tsx` | 115 | `useProject` | `project()`, `instance.path()/directory()`, `workspace.{current,set,list,get,status,sync}` |
| `permission.tsx` | 26 | `usePermission` | `mode: "auto" \| "normal"` from `--auto` (`:12`); `set`, `toggle` |
| `kv.tsx` | 66 | `useKV` | Persisted key/value at `<state>/kv.json`, `Flock`-locked, atomic writes (`:56-63`); `signal(name, default)` helper |
| `runtime.tsx` | 62 | `useTuiPaths`, `useTuiTerminalEnvironment`, `useTuiStartup` | `{cwd,home,state,worktree}`; platform/multiplexer; `initialRoute`, `skipInitialLoading` |
| `helper.tsx` | 26 | `createSimpleContext` | **Every context in this dir is built with it.** See G1 |
| `args.tsx` | 16 | `useArgs` | CLI args: `model, agent, prompt, continue, sessionID, fork, auto` |
| `thinking.ts` | 67 | `useThinkingMode` | reasoning-effort cycling |
| `clipboard.tsx` | 18 | `useClipboard` | `read`/`write` |
| `exit.tsx` | 8 | `useExit` | `exit(reason?)` |
| `epilogue.tsx` | 6 | `useEpilogue` | stdout text printed after teardown |
| `prompt.tsx` | 18 | `usePromptRef` | ref to the focused Prompt |
| `location.tsx` | 14 | `useLocation` | current directory/workspace ref |
| `directory.ts` | 17 | `useDirectory` | resolved directory string |
| `path-format.tsx` | 24 | `usePathFormatter` | path abbreviation for display |

---

# `sync.tsx` — the store the grid reads

## Store shape (`createStore` at `:64`, closes `:138`)

| Key | Line | Type | Grid relevance |
|---|---|---|---|
| `status` | 65 | `"loading" \| "partial" \| "complete"` | gate initial paint |
| `session` | 83 | `Session[]` — **sorted by `id`**, binary-searched | **the cell list** |
| `session_status` | 84-86 | `{ [sessionID]: SessionStatus }` | **amber / green / red-flash** |
| `permission` | 76-78 | `{ [sessionID]: PermissionRequest[] }` | **RED** |
| `question` | 79-81 | `{ [sessionID]: QuestionRequest[] }` | **YELLOW** |
| `todo` | 90-92 | `{ [sessionID]: Todo[] }` | cell body |
| `message` | 93-95 | `{ [sessionID]: Message[] }` — **capped at 100/session** | cell preview |
| `part` | 96-98 | `{ [messageID]: Part[] }` — **keyed by messageID, NOT sessionID** | see G4 |
| `session_diff` | 87-89 | `{ [sessionID]: SnapshotFileDiff[] }` | cell body |
| `config` / `agent` / `command` | 82/74/75 | | |
| `provider` / `provider_default` / `provider_next` / `provider_auth` | 66/67/68/73 | | |
| `console_state` / `capabilities` | 69 / 70-72 | | |
| `lsp` / `mcp` / `mcp_resource` / `formatter` / `vcs` | 99/100-102/103-105/106/107 | | |

Ordering invariant: `session`, `message[sid]`, `part[mid]`, `permission[sid]`, `question[sid]` are
all kept **sorted by id** and mutated via the binary-search helper `search()` (`:41-52`). Ids are
monotonic-ascending, so id order == creation order.

## Event switch (`event.subscribe(...)`, `:170-440`)

| Case | Line | Writes |
|---|---|---|
| `server.instance.disposed` | 172 | re-runs `bootstrap()` |
| `permission.replied` | 175 | splices out of `permission[sid]` |
| **`permission.asked`** | **190** | **if `permission.mode === "auto"` → auto-replies `"once"` and `break`s BEFORE writing (`:192-199`)**; else insert/reconcile |
| `question.replied` / `question.rejected` | 221 / 222 | splice out of `question[sid]` |
| `question.asked` | 237 | insert/reconcile into `question[sid]` |
| `todo.updated` | 259 | `todo[sid] = todos` |
| `session.diff` | 263 | `session_diff[sid] = diff` |
| `session.deleted` | 267 | splice out of `session` |
| `session.updated` | 279 | reconcile **or insert** into `session` (`:285-290`) — the *de facto* new-session path |
| `session.next.moved` | 294 | patches `directory`, `path`, `workspaceID`, `time.updated` |
| **`session.status`** | **310** | `session_status[sid] = status` — **write-only, never deletes** |
| `message.updated` | 315 | insert/reconcile; **trims to 100 and drops the oldest message's parts (`:335-352`)** |
| `message.removed` | 355 | splice |
| **`message.part.updated`** | **370** | `part[messageID]` insert/reconcile — **the PURPLE signal path** |
| `message.part.delta` | 392 | string-append into an existing part field |
| `message.part.removed` | 411 | splice |
| `lsp.updated` | 427 | refetch `lsp.status()` |
| `vcs.branch.updated` | 433 | sets `vcs.branch` if workspace matches |

**Not handled (verified absent from the switch):** `session.created`, `session.idle`,
`session.error`, `session.compacted`, `permission.updated`, any `session.next.*` except `moved`.

## Public surface (`result`, `:552-663`)

| Member | Line | Notes |
|---|---|---|
| `data` | 553 | the raw store — reactive |
| `set` | 554 | raw `setStore` — escape hatch |
| `status` | 555-557 | store status |
| `ready` | 558-561 | `startup.skipInitialLoading \|\| status !== "loading"` — **gates the whole provider, see G1** |
| `path` | 562-564 | `project.instance.path()` |
| `session.get(id)` | 566-570 | binary search; `undefined` if absent |
| `session.query()` | 571-573 | the current list filter (`{scope:"project"}` or `{path}`) |
| `session.refresh()` | 574-577 | re-`listSessions()` + `reconcile` — **the whole-list refetch the grid needs** |
| `session.status(id)` | 578-587 | **DEAD CODE — zero call sites repo-wide.** Reads `session.time.compacting` (`:581`), which has no writer |
| **`session.sync(id)`** | **588-660** | **the only historical backfill.** Fetches session + last 100 messages + todo + diff; guarded by `fullSyncedSessions` (`:589`) and an in-flight map (`:590`) |
| `bootstrap(opts)` | 662 (def `:445`) | full re-hydrate |

### Data acquisition

| Concern | Line | Detail |
|---|---|---|
| `sessionListQuery()` | 154-162 | if KV `session_directory_filter_enabled` (default `true`) → filters to the **current subdirectory**, else `{scope:"project"}` |
| `listSessions()` | 164-168 | **`start: Date.now() - 30 days`** — hard 30-day window; sorts by `id` |
| `bootstrap()` blocking phase | 452-472 | providers, provider list, capabilities, console state, agents, config, project. Session list is blocking **only under `--continue`** (`:471`) |
| commit batch | 499-508 | single `batch()` — one render |
| non-blocking phase | 511-533 | session list, commands, lsp, mcp, resources, formatter, **`session.status()` seed (`:524-526`)**, provider auth, vcs, workspaces → then `status = "complete"` |
| `onMount` | 548-550 | fires `bootstrap()` once |
| hydration trackers | 144-146 | `fullSyncedSessions` Set, `syncingSessions` Map, `hydratingSessions` Map — reconcile live deltas against the fetched snapshot (`:607-649`) |

## The two known gaps

### GAP-1 — `session.created` is not handled

Server publishes it (`packages/opencode/src/session/session.ts:537`,
`SessionV1.Event.Created`). `sync.tsx`'s switch has no case for it (verified absent).
A newly spawned session therefore enters `store.session` only via:

1. a later `session.updated` (`:279-292` — the insert branch at `:285-290`), or
2. an explicit `sync.session.refresh()` (`:574-577`).

**Grid must handle this itself.** Cheapest fix: `api.event.on("session.created", () => void sync.session.refresh())`.

### GAP-2 — historical backfill only happens on the session route

`sync.session.sync(id)` (`:588-660`) has **two** production call sites, both in
`packages/tui/src/routes/session/index.tsx`:

| Site | Line | Shape |
|---|---|---|
| Route open | `:306` | `await sync.session.sync(sessionID)` — eager, for the session being opened |
| **`Task` tool part** | **`:2221`** | **lazy + guarded, for the _subagent child_ session — the grid-cell pattern** |

(Six further call sites live in `test/cli/cmd/tui/sync-live-hydration.test.tsx` (5) and
`sync-undefined-messages.test.tsx` (1) — tests, not precedent.)

Neither covers an arbitrary session. `:306` fires only for the session being opened. `:2221`
fires only for a **subagent child** — `<Task/>` renders when `display() === "task"` (`:1758-1759`)
and hydrates `props.metadata.sessionId`, which the server sets to the child session
(`packages/opencode/src/tool/task.ts:185-187`: `sessionId: nextSession.id`, `parentSessionId:
ctx.sessionID`). So for any session the grid lists but the user has not opened **in this TUI
process**, `store.message[id]`, `store.todo[id]`, `store.session_diff[id]` are all empty even
though `store.session` has the row — the cell must hydrate it itself.

**`:2213-2222` is the precedent — copy the _shape_, not the code.** A sub-component hydrating
another session's messages on mount, guarded against a redundant fetch:

```tsx
function Task(props: ToolProps) {                 // :2213
  const sync = useSync()                          // :2216
  onMount(() => {                                 // :2219
    const sessionID = stringValue(props.metadata.sessionId)
    if (sessionID && !sync.data.message[sessionID]?.length) void sync.session.sync(sessionID)
  })                                              // :2221-2222
```

`sync.session.sync` is already idempotent and self-deduping — `fullSyncedSessions` (`:589`)
short-circuits a completed hydrate, `syncingSessions` (`:590-591`) returns the in-flight
promise. So the `!...?.length` guard is an **optimisation, not a correctness requirement**:
it skips the call for cells already carrying messages instead of paying a function call and a
Set lookup per cell per render. A grid with N cells wants it.

---

# `sdk.tsx` — the feed everything rides on

| Item | Line | Detail |
|---|---|---|
| `createOpencodeClient` | 24-31 | `{ baseUrl, signal, directory, fetch, headers }` |
| handler set + emitter | 35-46 | plain Set fan-out, not Solid |
| **queue + 16ms coalescing** | 48-80 | if last flush <16ms ago, batch; else flush immediately (`:75-79`) |
| `flush()` wraps emission in `batch()` | 61-65 | **all store writes from one flush = one render** |
| **`startSSE()` — the global feed** | 82-117 | `await sdk.global.event({ signal, sseMaxRetryAttempts: 0 })` at **`:91`**; `for await (const event of events.stream)` `:102` |
| reconnect backoff | 113-114 | exponential, cap 30s (`:52`) |
| injected `props.events` path | 119-132 | tests/embedders can supply an `EventSource` instead of SSE |
| returned surface | 141-149 | `client`, `directory`, `event` (emitter), `fetch`, `url` |

**`global.event` is not session-scoped.** Events for *every* session in the instance arrive
regardless of which session is open. That is what makes an all-session grid possible without polling.

# `event.ts` — the typed wrapper

| Symbol | Line | Detail |
|---|---|---|
| `subscribe(handler)` | 12-20 | drops `payload.type === "sync"` envelopes (`:14-16`); calls `handler(payload, { directory, workspace })` |
| `on(type, handler)` | 22-30 | filters by `event.type`, same 2-arg handler |
| `EventMetadata` | 4-7 | `{ directory: string; workspace: string \| undefined }` |

⚠️ The **metadata second arg exists at runtime** and is used (`sync.tsx:170`, `app.tsx:985`),
but the plugin-facing `TuiEventBus` type declares a **single-arg** handler
(`packages/plugin/src/tui.ts:519-521`). A plugin needing `{directory, workspace}` must cast.

# `data.tsx` — the v2 store

| Item | Line | Detail |
|---|---|---|
| `Data` shape | 36-48 | `session.{info,message,permission,question}`, `project.permission`, `location` (keyed by `JSON.stringify([directory, workspaceID])`, `:50-52`) |
| `handleEvent(event: V2Event)` | 124-403 | switch over `session.next.*` + `catalog.updated` / `reference.updated` / `integration.updated` |
| subscription | 405-414 | reshapes v1 envelopes into `V2Event` (`data: event.properties`, `location: {...metadata}`) then dispatches |
| public surface | 416-~560 | `session.{get,refresh,message,permission,question}`, `project.permission`, `location.{agent,command,model,provider,skill,reference,integration}` — every branch has `list()` + `refresh()` |
| **`session.next.compaction.started` / `.delta` are explicit no-ops** | **376-379** | fall through to `break` — nothing recorded |
| `session.next.compaction.ended` | 380-391 | prepends a `type:"compaction"` message |

**Dormancy status (corrected):** `data.tsx` is mounted in the tree
(`app.tsx:38,308,331`) but has exactly **one production consumer** —
`component/prompt/autocomplete.tsx:12,90`, and only for `data.location.reference.list()`
(`autocomplete.tsx:280`). Everything else in it is exercised only by
`test/cli/tui/data.test.tsx`. Treat as effectively dormant, **not** as unmounted dead code.

# `theme.tsx`

| Item | Line |
|---|---|
| `ThemeSource` type / `themeSource` | 32 / 37 |
| `discoverThemes(directories)` | 52 |
| re-exports from `../theme` (`Theme`, `ThemeJson`, …) | 63-80 |
| `THEME_REFRESH_DELAYS = [250, 1000]` | 82 |
| module-level `store` (themes, mode, active, lock, ready) | 92 |
| provider `init` | 102 |
| `renderer.setBackgroundColor` effect | 269 |
| syntax memos | 271-272 |
| **returned surface** | 274-301 — `theme` (Proxy `:275-280`), `selected` `:281`, `all`, `has`, `syntax`, `subtleSyntax`, `mode()`, `locked()`, `lock`, `unlock`, `setMode`, `set(name)`, `ready` |

# `route.tsx`

| Item | Line |
|---|---|
| `HomeRoute` / `SessionRoute` / `PluginRoute` / `Route` | 6 / 11 / 17 / 23 |
| `PluginRoute = { type:"plugin"; id: string; data?: Record<string, unknown> }` | 17-21 |
| provider + `initialRoute` fallback chain | 25-42 |
| `data` getter / `navigate(route)` (uses `reconcile`) | 34-36 / 37-39 |
| `initialRoute(value)` — rehydrates `OPENCODE_ROUTE`; **plugin branch drops `data`** | 44-53 (`:50-52`) |
| `useRouteData<T>(type)` — **unchecked cast** | 57-60 |

---

## Gotchas

| # | Gotcha | Evidence |
|---|---|---|
| G1 | `createSimpleContext`'s provider gates children behind `<Show when={init.ready === undefined \|\| init.ready === true}>`. So `SyncProvider` **does not render its subtree** until `sync.ready` is true, and `sync.ready` is `status !== "loading"` unless `OPENCODE_FAST_BOOT`. Same for `KVProvider`, `ThemeProvider`. Anything below never observes the loading state. | `helper.tsx:14-18`; `sync.tsx:558-561` |
| G2 | **`--auto` kills RED.** `permission.asked` auto-replies `"once"` and `break`s *before* the store write. `store.permission` stays empty forever. | `sync.tsx:192-199`; `permission.tsx:12` |
| G3 | **`session_status` is write-only.** The server deletes idle entries from its own map (`packages/opencode/src/session/status.ts:42-45`), so the HTTP seed (`sync.tsx:524-526`) only ever contains busy/retry. The TUI handler (`:310-313`) writes and never removes. ⇒ **key present && `type === "idle"` ⟹ it ran and finished in this process.** Process-local: after restart, yesterday's finished session reads *absent*, i.e. dim, not green. | `sync.tsx:310-313,524-526`; `status.ts:39-45` |
| G4 | **`store.part` is keyed by `messageID`, not `sessionID`.** There is no sessionID→parts index. To find a session's parts you must go `message[sid] → id → part[id]`. But the event payload carries `part.sessionID` directly (`:371`), so an event subscriber can skip the store entirely. | `sync.tsx:96-98,371` |
| G5 | `store.message[sid]` is **capped at 100** and dropping a message deletes its parts. A long-running session silently loses history from the store. | `sync.tsx:335-352` |
| G6 | `listSessions()` has a hard **30-day** window and (by default) a **current-subdirectory** filter. A cross-directory grid must call `sync.session.refresh()` after flipping `session_directory_filter_enabled`, or bypass with `client.session.list()`. | `sync.tsx:154-168`; toggle at `app.tsx:934-945` |
| G7 | `session.time.compacting` is **read at `sync.tsx:581` and written nowhere in the repo**; its only consumer `sync.session.status()` has zero call sites. Do not build PURPLE on it. | `sync.tsx:578-587` |
| G8 | `session.idle` is deprecated and redundant with `session.status`; it double-fires on error paths with no dedup. Drive off `session.status`. | `packages/schema/src/session-status-event.ts:43-49`; `status.ts:39-45` |
| G9 | `bootstrap()` is re-entrant — `server.instance.disposed` re-runs it (`:172-174`) and `routes/session/index.tsx:302` calls it with `{fatal:false}` on workspace switch. Grid state must survive a full `reconcile` of `session`/`session_status`. | `sync.tsx:172,445,507,515,525` |
| G10 | `sync.set` is exposed raw (`:554`). Tempting and dangerous — writing custom keys into this store will be clobbered by the next `reconcile` in `bootstrap`. Keep Healbot-only state in the plugin's own signals. | `sync.tsx:554` |

---

## Build levers

| Need | Lever | file:line |
|---|---|---|
| Reactive all-session list | `useSync().data.session` (direct import — `api.state` has no `list()`) | `sync.tsx:83`, `:553` |
| Border: amber / green / dim | `sync.data.session_status[id]` — absent = dim, `busy` = amber, `idle` = green, `retry` = red-flash | `sync.tsx:84-86,310-313` |
| Border: RED | `sync.data.permission[id]?.length > 0` | `sync.tsx:76-78,190-219` |
| Border: YELLOW | `sync.data.question[id]?.length > 0` | `sync.tsx:79-81,237-257` |
| Border: PURPLE | subscribe `message.part.updated`, test `properties.part.type === "compaction"`, key off `properties.part.sessionID`. **Emitted at START** — `SessionCompaction.create()` (`compaction.ts:513-536`) writes the part via `updatePart` (`:528-535`), then `continue`s; the loop dispatches `compaction.process` on the *next* iteration | `sync.tsx:370-390`; emit `packages/opencode/src/session/compaction.ts:528-535`; ordering `packages/opencode/src/session/prompt.ts:1166` then `:1148-1158`; part schema `packages/schema/src/v1/session.ts:195-202`; end signal `compaction.ts:508` (`session.compacted`) |
| New sessions appear | `api.event.on("session.created", …)` → `sync.session.refresh()` (GAP-1) | `sync.tsx:574-577` |
| Cold-cell content | `sync.session.sync(id)` — idempotent, deduped (GAP-2). **Copy the lazy-guarded `onMount` shape** | `sync.tsx:588-660`; precedent `routes/session/index.tsx:2213-2222` |
| Cold-start reconcile of RED/YELLOW | `client.permission.list()` / `client.question.list()` via `useSDK().client` | `sdk.tsx:141-144` |
| Reply to a blocked session | `sdk.client.permission.reply({ requestID, reply })` / `question.reply({ requestID, answers })` — `requestID` only, no sessionID | `routes/session/permission.tsx:168-172`; `question.tsx:50-54` |
| Cross-directory reply args | capture `{directory, workspace}` from the **event metadata** 2nd arg; the auto-approve path does exactly this | `sync.tsx:170,193-197` |
| Focus a session | `useRoute().navigate({ type:"session", sessionID })` | `route.tsx:37-39` |
| Persist grid layout/prefs | `useKV().get/set` (atomic, flock'd) or `kv.signal(name, default)` | `kv.tsx:39-63` |
| Colors | `useTheme().theme.{error,warning,success,primary,accent,textMuted,border,borderActive}` (Proxy — read inside a reactive scope) | `theme.tsx:275-280` |
