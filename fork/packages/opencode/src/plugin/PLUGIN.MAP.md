# plugin/ — structural map

Owns the **server-side** plugin runtime: hook registration, hook dispatch, external plugin
discovery/loading/installation, and the bundled provider-auth plugins. Also hosts the adapter
into the TUI plugin host.

The hook contract itself lives in `packages/plugin/src/index.ts` (21 hooks) and
`packages/plugin/src/tui.ts` (the TUI API). Both are mapped below.

Repo `~/Desktop/healbot/opencode` @ `0fdcfb6`, branch `healbot`, v1.18.5.

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

## File table

| File | LOC | Owns | Key symbols (line) |
|---|---|---|---|
| **`index.ts`** | 314 | The runtime. State = a flat `Hooks[]` array; `trigger` walks it. | `State = {hooks: Hooks[]}` 35-37 · `TriggerName` 40-42 · `Interface` 44-56 · `Service` 58 · `experimentalWebSocketsEnabled()` 60-62 · **`internalPlugins(flags)` 65-82** · `getServerPlugin()` 88-93 · `getLegacyPlugins()` 95-108 · `applyPlugin()` 110-121 · `layer` 123-306 · `PluginInput` build 149-164 · internal load 166-175 · external load 177-238 · **config fanout 241-249** · **event fanout 251-258** · dispose finalizer 261-274 · **`trigger()` 280-293** · `list()` 295-298 · `init()` 300-302 · `node` 308-312 |
| `loader.ts` | 237 | Resolve → install → import external plugins. Namespace `PluginLoader` (15). | `Plan` 17-21 · `Resolved` 24-29 · `Missing` 32-37 · `Report` 45-58 · `isRetryableResolveError()` 71-74 · **`resolve()` 86-133** (install 97, entrypoint 106, compat 127) · `load()` 136-145 (bare `await import` 139) · `attempt()` 149-192 · **`loadExternal()` 208-236** |
| `install.ts` | 439 | CLI install + JSONC config patching. | `packageTargets()` 145-166 · `patchPluginList()` 181-257 · **`installPlugin()` 259-281** · `readPluginManifest()` 283-331 · `patchDir()` 333-338 · `patchName()` 340-343 · `patchOne()` 345-419 (flock 347, JSONC 372) · **`patchPluginConfig()` 421-439** |
| `shared.ts` | 323 | Spec parsing, target/entrypoint resolution, module-shape validation. | `DEPRECATED_PLUGIN_PACKAGES` 10 · `parsePluginSpecifier()` 22-34 · `pluginSource()` 56-59 · **`resolvePackageFile()` 89-97 (directory-escape guard, throws 93-95)** · `resolvePackageEntrypoint()` 103-114 · `resolvePluginEntrypoint()` 136-169 · `resolvePathPluginTarget()` 175-192 · `checkPluginCompatibility()` 194-205 · **`resolvePluginTarget()` 207-213 (npm install via `Npm.add`, 211)** · `readPackageThemes()` 238-262 · **`readV1Plugin()` 272-304** · `resolvePluginId()` 306-323 (file plugins **must** export `id`, 313-315) |
| `meta.ts` | 188 | The on-disk plugin ledger `plugin-meta.json`. **TUI-only consumer.** | `Theme` 13-18 · `Entry` 20-34 · `storePath()` 48-50 (`Global.Path.state`; override `Flag.OPENCODE_PLUGIN_META_FILE`) · `fingerprint()` 108-111 · `next()` 124-140 · `touchMany()` 142-159 · `touch()` 161-167 · `setTheme()` 169-181 · `list()` 183-186 |
| `pty-environment.ts` | 25 | **Not a plugin.** An Effect `Layer` implementing `PtyEnvironment.Service` by calling `plugin.trigger("shell.env", …)`. | layer 8-24, trigger 18 |
| `tui/internal.ts` | 10 | Adapter: re-exports `@opencode-ai/tui/builtins` to the server. | `internalTuiPlugins(flags)` 6-10 |
| `tui/runtime.ts` | 1131 | The whole TUI plugin host (scopes, keymap/attention/mode scoping, activation, install). | `DISPOSE_TIMEOUT_MS` 122 · `KV_KEY` 123 · `createScopedKeymap` 143 · `createThemeInstaller` 245 · `loadInternalPlugin` 341 · `createPluginScope` 388 · `activate/deactivatePluginEntry` 516/502 · **`pluginApi()` 572-651** · `resolveExternalPlugins` 676 (→ `PluginLoader.loadExternal` 677) · `addExternalPluginEntries` 776 · `installPluginBySpec` 891 · **`init` 988** · builtins spliced 1093 · `createLegacyTuiPluginHost` 1124 |

### Bundled provider plugins (all registered in `index.ts:65-82`)

| File | Hooks it implements | Registered |
|---|---|---|
| `openai/codex.ts:263-565` (+ `openai/ws.ts`, `ws-pool.ts`) | `provider` 278 · `auth` 320 · `chat.headers` 549 · `chat.params` 559 | `index.ts:68-71` (wrapped to inject `experimentalWebSockets`) |
| `github-copilot/copilot.ts:56-414` (+ `models.ts:213`) | `provider.models` 60 · `auth` 94 · `chat.params` 340 · `experimental.provider.small_model` 355 · `chat.headers` 360 | `index.ts:72` |
| `cloudflare.ts:3-27` | `auth` (provider `cloudflare-workers-ai`, 15-16) | `index.ts:75` |
| `cloudflare.ts:29-76` | `auth` 53-63 · `chat.params` 64 (strips `max_tokens` for OpenAI reasoning models) | `index.ts:76` |
| `azure.ts:3-26` | `auth` only; prompts for `AZURE_RESOURCE_NAME` 5-12 | `index.ts:77` |
| `digitalocean.ts:224-325` | `provider.models` 226-268 · `auth` (OAuth) 271 | `index.ts:78` |
| `snowflake-cortex.ts:266-507` | `auth` w/ OAuth loader + single-flight refresh 283-285 | `index.ts:79` |
| `xai.ts:458-626` | `auth` w/ device-code/PKCE + fetch-override token injection 460-461 | `index.ts:80` |

`GitlabAuthPlugin` and `PoeAuthPlugin` come from npm, not this directory (`index.ts:73-74`).

---

## Hook dispatch

**`trigger()` — `index.ts:280-293`.** The whole mechanism:

```
286  const s = yield* InstanceState.get(state)
287  for (const hook of s.hooks) {
288    const fn = hook[name] as any
289    if (!fn) continue
290    yield* Effect.promise(async () => fn(input, output))
291  }
292  return output          ← callers read the MUTATED output object
```

- **Sequential, no concurrency.** Registration order is load order.
- **No per-hook error catching.** A hook that throws rejects the `Effect.promise` and fails the
  caller's effect. (Contrast the `config` fanout at `:241-249` and internal-plugin load at
  `:166-175`, which *do* swallow errors.)
- **Mutation, not return value, is the contract.** Hooks mutate `output` in place.

**Load order — `index.ts:130-278`:**
1. internal plugins (`:166-175`), gated by `flags.disableDefaultPlugins` (`:166`); each wrapped in
   `Effect.tryPromise` + `Effect.option`, failures logged (`:171`) and dropped.
2. external plugins from `cfg.plugin_origins` (`:177`); `flags.pure` empties the list.
3. The external loop is **deliberately sequential** — comment at `:218-219` says hook order must
   stay deterministic. (`PluginLoader.loadExternal` itself imports in parallel via `Promise.all`
   at `loader.ts:214`; the *registration* is what is serialized.)

**Two non-`trigger` dispatch paths:**
- `config` — direct fanout loop, `index.ts:241-249`.
- `event` — `events.listen` at `index.ts:251-258`, **filtered to `event.location?.directory === ctx.directory`** (`:252`) and fire-and-forget (`void`, `:255`).

---

## THE HOOK CATALOG

Contract: `packages/plugin/src/index.ts:222-335` — 21 hooks. Every trigger site verified.

### Data-field hooks (not dispatched through `trigger`)

| Hook | Declared | Consumed at | Status |
|---|---|---|---|
| `dispose` | :223 | `plugin/index.ts:266` (scope finalizer 261-274) | LIVE |
| `event` | :224 | `plugin/index.ts:255` | LIVE |
| `config` | :225 | `plugin/index.ts:243` | LIVE |
| **`tool`** | :226-228 | **`tool/registry.ts:196-198`** | LIVE — the tool-contribution path |
| `auth` | :229 | `provider/auth.ts:116-127`; `provider/provider.ts:1544-1562`; `cli/cmd/providers.ts:431-433,445-447` | LIVE |
| `provider` | :230 | `provider/provider.ts:1379`, `1392-1400` | LIVE |

### `(input, output)` hooks dispatched via `Plugin.trigger`

| Hook | Declared | Triggered at | Ctx? |
|---|---|---|---|
| `chat.message` | :234 | `session/prompt.ts:999` | **yes** |
| `chat.params` | :247 | `session/llm/request.ts:114` | no |
| `chat.headers` | :257 | `session/llm/request.ts:134` | no |
| **`permission.ask`** | **:261** | **DEAD — zero trigger sites** | — |
| `command.execute.before` | :262 | `session/prompt.ts:1460` | **yes** |
| `tool.execute.before` | :266 | `session/tools.ts:106,175,258,338,402`; `session/prompt.ts:307`; `tool/code-mode.ts:141` | no |
| `shell.env` | :270 | `plugin/pty-environment.ts:18`; `server/…/handlers/pty.ts:71`; `tool/shell.ts:417`; `session/prompt.ts:554` | no |
| `tool.execute.after` | :274 | `session/tools.ts:121,208,291,373,420`; `session/prompt.ts:389`; `tool/code-mode.ts:180` | **yes** |
| `experimental.chat.messages.transform` | :282 | `session/prompt.ts:1255`; `session/compaction.ts:350` | **yes** |
| `experimental.chat.system.transform` | :291 | `session/llm/request.ts:69`; `agent/agent.ts:381` | **yes** |
| `experimental.provider.small_model` | :297 | `provider/provider.ts:1887` | no |
| `experimental.session.compacting` | :305 | `session/compaction.ts:343` | **yes** |
| `experimental.compaction.autocontinue` | :316 | `session/compaction.ts:454` | no |
| `experimental.text.complete` | :327 | `session/processor.ts:516` | **yes** |
| **`tool.definition`** | :334 | **`tool/registry.ts:313`** | **yes** |

"Ctx?" = whether the hook can put text into the model's context window. See below.

---

## Token cost — **SCAN.md is wrong here**

> SCAN.md §4: *"Plugins | Zero unless they contribute a `tool`."*

**Refuted.** There are nine verified paths by which a plugin injects text into the model's
context, only one of which is the `tool` field.

| Path | Site | What it injects |
|---|---|---|
| `experimental.chat.system.transform` | **`session/llm/request.ts:69-72`** (`{ system }` array mutated; re-joined 74-78); also `agent/agent.ts:381` | arbitrary text into the **system prompt** |
| **`tool.definition`** | **`tool/registry.ts:313`** | rewrites `description` / `parameters` / `jsonSchema` of **any** tool, builtins included |
| `tool` field | `tool/registry.ts:194-199` → `fromPlugin()` `registry.ts:120-176` (description at `:138`, Zod→JSON Schema at `:126-131`) | a whole new tool description + schema |
| `experimental.chat.messages.transform` | `session/prompt.ts:1255`; `session/compaction.ts:350` | mutates the **entire message array** pre-send |
| `experimental.session.compacting` | `session/compaction.ts:343-348` | `output.context[]` appended to, or `output.prompt` fully **replaces**, the compaction prompt |
| `chat.message` | `session/prompt.ts:999-1009` | `output.parts` mutable before parts are finalized |
| `command.execute.before` | `session/prompt.ts:1460-1464` | `output.parts` mutable before `prompt()` |
| `tool.execute.after` | `session/tools.ts:121` (+6 more) | `output.output` **is** the tool-result text the model reads |
| `experimental.text.complete` | `session/processor.ts:516-517` | return value assigned back to `ctx.currentText.text` |

**What is genuinely zero:** the runtime itself. `index.ts` adds no standing text; a plugin that
implements only `auth`, `provider`, `event`, `config`, `dispose`, or `shell.env` costs nothing.

**Corollary — `tool.definition` (`registry.ts:313`) is the cheapest strip lever in the whole
fork:** it lets a plugin rewrite every builtin tool's description with **no source change to the
fork**. See `../tool/TOOL.MAP.md` for the per-tool byte targets.

---

## Inputs / outputs

**Feeds in:** `Config.Service` (`cfg.plugin_origins`, derived at `config/config.ts:112-114` from
the `plugin` config key; directory discovery at `config/plugin.ts:18-29` —
`Glob.scan("{plugin,plugins}/*.{ts,js}")` per config dir; dedupe `config/plugin.ts:64-77`) ·
`RuntimeFlags.Service` (`disableDefaultPlugins`, `pure`, `experimentalWebSockets`) ·
`EventV2Bridge.Service`. Deps declared `index.ts:308-312`.

**Produces:** a `Hooks[]` array read by `Plugin.trigger` / `Plugin.list`, plus `PluginInput`
(`index.ts:149-164`: `client` 142-147, `experimental_workspace.register` 154-158, `serverUrl`
getter 159-161, `$: Bun.$` 163).

**Depends on it:** `tool/registry.ts:194-199` (tools) · `session/llm/request.ts:69,114,134` ·
`session/prompt.ts:307,389,554,999,1255,1460` · `session/tools.ts` (7 sites) ·
`session/compaction.ts:343,350,454` · `session/processor.ts:516` · `tool/registry.ts:313` ·
`provider/provider.ts:1379,1544,1887` · `provider/auth.ts:116` · `tool/shell.ts:417` ·
`plugin/pty-environment.ts:18`.

---

## Extension points this subsystem exposes

| Point | How | Site |
|---|---|---|
| Server plugin | default export function, or `{ server }` export | `index.ts:88-93`, `applyPlugin()` 110-121 |
| **TUI plugin (routes, keymaps, slots)** | `{ tui }` export → `TuiPlugin` | contract `packages/plugin/src/tui.ts:628`; host `tui/runtime.ts:988` |
| Install source | npm spec, or `file:`/path | `shared.ts:22-34` `parsePluginSpecifier`; npm install `shared.ts:207-213` → `Npm.add` (`core/src/npm.ts:263`, impl `:115` — arborist reify, not a `bun add` shell-out) |
| Config registration | `plugin: []` in `opencode.json*` | patched by `install.ts:421-439`; `patchDir()` 333-338 chooses global vs `.opencode/`; `patchName()` 340-343 chooses `opencode.json` vs `tui.json` |
| Themes | `oc-themes` package field | `shared.ts:238-262`; installed `tui/runtime.ts:245` |
| Compat gate | `engines.opencode` semver | `shared.ts:194-205` — **skipped while opencode major is 0** (`:195`) |

### `TuiPluginApi` — `packages/plugin/src/tui.ts:581-626`

`app` 582 · `attention` 583 · `command?` 590 *(deprecated, 584-589)* · `keys` 591 · `keymap` 592 ·
`mode` 593 · **`route` 594-598 (`register` 595, `navigate` 596, `current` 597)** · `ui` 599-609 ·
`tuiConfig` 610 · `kv` 611 · `state` 612 · `theme` 613 · `client` 614 · `event` 615 ·
`renderer` 616 · `slots` 617 · `plugins` 618-624 · `lifecycle` 625.

Adjacent: `TuiSlots` 512-517 · **`TuiEventBus` 519-521** · `TuiDispose` 523 · `TuiLifecycle`
525-528 · `TuiPluginEntry` 532-545 · `TuiPlugin` 628 · `TuiPluginModule` 630-634.

---

## Gotchas

1. **The `permission.ask` hook is DEAD.** Declared `packages/plugin/src/index.ts:261`, zero
   trigger sites. Verified exhaustively: grep for the exact quoted literal `"permission.ask"`
   across `packages/**` returns the declaration plus one docs mention
   (`core/src/plugin/skill/customize-opencode.md:354`); everything else is the
   `permission.ask**ed**` event or the Effect service method `perm.ask(...)`. The
   `permission/` subsystem imports no plugin service at all. **Implementing it is a no-op** — use
   `tool.execute.before` to gate from a plugin instead.
2. **SCAN.md's "plugins cost zero context" is wrong.** Nine injection paths — see the table above.
   `experimental.chat.system.transform` writes straight into the system prompt.
3. **`createBuiltinPlugins(options)` ignores its argument.** Correct path is
   **`packages/tui/src/feature-plugins/builtins.ts:22-38`** (SCAN.md gave the line range but not
   the path; there is no `builtins.ts` in this directory). Lines 23-37 are a static array literal;
   `options` is never referenced. The caller that feeds it is
   `plugin/tui/internal.ts:6-10`, which passes `experimentalEventSystem: flags.experimentalEventSystem`
   — discarded. The 13 builtins: `HomeFooter, HomeTips, SidebarContext, SidebarMcp, SidebarLsp,
   SidebarTodo, SidebarFiles, SidebarFooter, Notifications, PluginManager, WhichKey, DiffViewer,
   HealbotSpike`. **Any experimental-event gating of a TUI builtin must be added here first.**
4. **`trigger` does not catch hook errors** (`index.ts:290`). One throwing plugin fails the
   request. `config` (`:241-249`) and internal-plugin load (`:166-175`) *do* swallow errors —
   inconsistent.
5. **External plugin load failures publish no event.** `index.ts:229-234` is a commented-out
   `Session.Event.Error` publish with a `// TODO: make proper events for this`. Install /
   compatibility / entry failures *do* publish, via `publishPluginError` (`index.ts:135-137`).
   A control terminal watching the event stream will not see a plugin that failed to import.
6. **Dead code:** empty `if` block at `index.ts:178-179`
   (`if (flags.pure && cfg.plugin_origins?.length) { }`).
7. **`event` hooks are directory-filtered** (`index.ts:252`). A plugin will not see events from
   other directories/worktrees on the same server.
8. **File plugins must export `id`** (`shared.ts:313-315`) or resolution throws. npm plugins
   fall back to the package name.
9. **A module may not export both `server` and `tui`** — `shared.ts:293-295` rejects it. Ship two
   entrypoints (`exports["./server"]`, `exports["./tui"]`; read at `install.ts:145-166`).
10. **Deprecated plugins are skipped silently** (`loader.ts:161`, list at `shared.ts:10`).
11. **Compat checking is effectively off** — `shared.ts:195` skips the `engines.opencode` check
    while the opencode major version is 0.
12. **`shell.env` is v1-only.** `packages/core/src/tool/bash.ts:70` carries
    `// TODO: Add plugin shell.env environment augmentation once V2 plugin hooks exist.` — the
    hook fires for `tool/shell.ts:417` but not for the core v2 bash tool.
13. **`meta.ts` is TUI-only.** Its only consumers are `plugin/tui/runtime.ts:274` and `:779`; the
    server runtime never reads or writes `plugin-meta.json`.
14. **`loadExternal` imports in parallel** (`loader.ts:214` `Promise.all`) but the retry pass
    (`:215-230`) is sequential and only retries **file** plugins with a retryable pre-import setup
    error (`isRetryableResolveError` `:71-74`). Comment at `:222-223`: Bun caches failed dynamic
    imports.

---

## Strip levers

| Lever | Site | Effect |
|---|---|---|
| **Rewrite builtin tool descriptions from a plugin** | implement `tool.definition`; dispatched at **`tool/registry.ts:313`** | the entire tool-description cut (~5,740 tok ceiling) **with zero source change to the fork**. Highest-leverage entry point in this subsystem |
| Replace the system prompt from a plugin | implement `experimental.chat.system.transform`; dispatched at `session/llm/request.ts:69` | alternative to defining `agent.prompt`; strictly more powerful (sees the assembled array) |
| Drop the bundled provider plugins | `index.ts:65-82` — or set `flags.disableDefaultPlugins` (checked `index.ts:166`) | zero token effect; cuts boot cost and 8 auth surfaces. Keep the one matching your provider |
| Run with no external plugins | `flags.pure` (`index.ts:177`) | reproducible baseline for measurement |
| Add the healbot grid | register a `{ tui }` plugin with `route.register` (`packages/plugin/src/tui.ts:595`); builtin path = **`packages/tui/src/feature-plugins/builtins.ts:23-37`** | PROBE F7 proved this route; `HealbotSpike` is already in the builtin array |
| Wire plugin-load failures into the event stream | uncomment/replace `index.ts:229-234` | makes the control terminal able to see broken plugins |
| Delete the dead hook | `packages/plugin/src/index.ts:261` | contract cleanup, zero runtime effect |
