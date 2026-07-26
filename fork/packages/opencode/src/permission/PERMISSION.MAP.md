# permission/ — structural map

Owns the ask/reply state machine for tool authorization: rule evaluation, the pending-request
map, the `permission.asked`/`permission.replied` events, and the **subtractive** filter that
removes denied tools' schemas from the model's context.

Repo `~/Desktop/healbot/opencode` @ `0fdcfb6`, branch `healbot`, v1.18.5. Three files, 223 + 163
+ 1 lines. Small subsystem, wide blast radius.

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
| **`index.ts`** | 223 | Everything: rule evaluation, ask/reply, approval cache, tool subtraction. | `Event` 10 · `Interface` 12-16 · `PendingEntry` 18-21 · `State` 23-26 · **`evaluate()` 28-38** · `Service` 40 · `layer` 42-176 (scope finalizer **54-61**) · **`ask()` 67-106** · **`reply()` 109-167** · `list()` · `expand()` 178-184 · `fromConfig()` 186-198 · `merge()` 200-202 · **`disabled()` 204-214** · `visibleTools()` 216-219 · `node` 221 |
| `arity.ts` | 163 | Bash command-prefix arity table — turns a full command into a generalizable "always" pattern. | `prefix(tokens)` 1-9 · `ARITY` dict 24-161 (not exported) · `BashArity` 163 |
| `evaluate.ts` | 1 | `export { evaluate } from "."` — import shim so `@/permission/evaluate` resolves without pulling the layer. No logic. | — |

External but load-bearing:

| File | Owns |
|---|---|
| `packages/core/src/util/wildcard.ts:3-14` | The matcher. Regex, not glob. `*`→`.*` (:8), `?`→`.` (:9); **`" .*"` → `"( .*)?"` at :11** so `git commit *` also matches bare `git commit`. Anchored; case-insensitive on Windows only (:13). **No path-segment awareness — `*` crosses `/`.** |
| `packages/core/src/v1/permission.ts` | Error classes `RejectedError` :8-10, `CorrectedError` :16-18, `DeniedError` :24-26 |
| `packages/core/src/v1/config/permission.ts` | Config schema. `Action` :5 · `Object` :8 · known keys :17-36 · `Info` :43-48 (bare string → `{"*": action}` :40-41). **Comment :14-16: parsing uses `propertyOrder: "original"` because key order is semantic.** |
| `packages/schema/src/v1/permission.ts` | `Request` :27-35 · `Event.Asked` :61 · `Event.Replied` :62-65 · inventory :66 |

---

## Rule evaluation

`evaluate(permission, pattern, ...rulesets)` — `index.ts:28-38`:

```ts
rulesets.flat().findLast(r => Wildcard.match(permission, r.permission) && Wildcard.match(pattern, r.pattern))
  ?? { action: "ask", permission, pattern: "*" }
```

- **`findLast` = last-writer-wins. There is no specificity scoring.** Array order alone decides.
- Unmatched → `"ask"`. Fail-closed.
- `merge()` (`:200-202`) is literally `rulesets.flat()` — precedence is purely positional.

**Effective precedence, low → high:**

| Tier | Site |
|---|---|
| 1. agent defaults (`"*": "allow"` base) | `agent/agent.ts:119-136` |
| 2. per-builtin-agent overrides | `agent/agent.ts:145-152` (build), `160-178` (plan), `185-191` (general), `198-209` (explore) |
| 3. global user config | `agent/agent.ts:138` ← `config.permission`; env override `config/config.ts:545-551`; legacy `tools:{}` map `config/config.ts:553-564` |
| 4. per-agent config block | **`agent/agent.ts:293`** |
| 5. session ruleset | `handlers/session.ts:194-197`; merged at ask time (`session/tools.ts:87`) |
| 6. runtime `approved` cache | `index.ts:73` — spread **last**, so an "always" beats a configured deny |

---

## Ask / reply state machine

### `ask()` — `index.ts:67-106`

| Step | Line | Behavior |
|---|---|---|
| Evaluate every pattern | 72-82 | |
| **Any `deny` → abort the whole call** | **75-79** | throws `DeniedError` carrying the filtered ruleset |
| All `allow` → return silently | 84 | **fast path — no event published** |
| Mint id (caller may supply) | 86 | `request.id ?? PermissionV1.ID.ascending()` |
| Build `Request` info | 87-95 | `{id, sessionID, permission, patterns, metadata, always, tool}` |
| Register pending | 98-99 | `Deferred.make` + `pending.set(id, …)` |
| **Publish `permission.asked`** | **100** | |
| Block until replied | 101-106 | `Effect.ensuring(Deferred.await(…), delete pending)` |

### `reply()` — `index.ts:109-167`, keyed by `requestID` alone

| Reply | Line | Behavior |
|---|---|---|
| miss | 111-112 | `NotFoundError` |
| (all) | 114-119 | delete from `pending`, publish `permission.replied` |
| **`reject`** | **121-140** | fails the deferred with `CorrectedError({feedback})` if `message` present, else `RejectedError` (124-126). **129-138 then force-rejects every other pending request in the same `sessionID`.** |
| **`once`** | 142-143 | resolve. **Nothing cached.** |
| **`always`** | 145-166 | pushes `{permission, pattern, action:"allow"}` into `approved` for each entry in **`info.always`** (not `info.patterns`) — 145-151. Then 153-166 re-evaluates every pending request in the same session and auto-resolves the now-allowed ones. |

### Lifetime and scope of approvals

- `approved: Rule[]` lives in `State` (`:25`), created by `InstanceState.make` (`:46`).
- **Instance-wide, not per-session.** The write at `:145-151` has no `sessionID` filter — an
  "always" in session A applies to session B in the same server process. Only the *cascade*
  (`:130`, `:154`) is session-scoped.
- **Zero persistence.** `PermissionV1.Approval` (`schema/src/v1/permission.ts:46-49`) has no
  usage anywhere under `packages/*/src` — nothing writes approvals to disk.
- **No timeout, no abort.** `Deferred.await` (`:102`) waits indefinitely; grep for
  `timeout|interrupt|abort` across `permission/` returns zero matches. The only teardown is the
  scope finalizer at **`:54-61`**, which fails all pending deferreds with `RejectedError` when the
  instance scope closes.

---

## `arity.ts` — how "always" generalizes a bash command

`prefix(tokens)` (`:1-9`) walks longest→shortest token prefix against the `ARITY` dict (`:24-161`)
and returns `tokens.slice(0, arity)`. Unknown command → first token only (`:8`).

Examples: `git`→2 (`:83`) · `git config`→3 (`:84`) · `npm`→2 (`:111`) · `npm run`→3 (`:114`) ·
`docker compose`→3 (`:72`) · bare utilities `rm`/`ls`/`cat`→1 (`:42`/`:37`/`:25`).

**Sole consumer — `tool/shell.ts:409`:**
```ts
scan.always.add(BashArity.prefix(tokens).join(" ") + " *")
```
So the **ask** pattern is the full command source (`shell.ts:408`) while the **always** pattern is
the arity-truncated prefix + `" *"`. Approving "always" on `git commit -m "x"` persists the rule
`git commit *` — which, via the `wildcard.ts:11` special case, also matches bare `git commit`.

---

## Events

| Event | Schema | Published at | Subscribers |
|---|---|---|---|
| `permission.asked` | `schema/src/v1/permission.ts:61` | **`index.ts:100`** | TUI `tui/src/context/sync.tsx:190`; notifications `tui/src/feature-plugins/system/notifications.ts:49`; CLI `cli/cmd/run.ts:796`; desktop `app/src/context/global-sync/event-reducer.ts:29,396`; ACP `acp/permission.ts:16`; server-internal `session/llm.ts:169-174` |
| `permission.replied` | `schema/src/v1/permission.ts:62-65` | **`index.ts:115, 132, 160`** | same feed |

Registered globally at `packages/schema/src/event-manifest.ts:49`. Re-exported as
`Permission.Event` (`index.ts:10`).

**HTTP:**

| Route | Handler | Note |
|---|---|---|
| `GET /permission` | `handlers/permission.ts:12` | cold-start reconciliation of pending requests |
| `POST /permission/reply` | `handlers/permission.ts:16-37` | `requestID` + `reply`; `NotFoundError`→HTTP mapping 27-34 |
| `POST /session/:id/permissions/:permissionID` | `handlers/session.ts:362-367` | session-scoped alias |

---

## The subtractive path (the reason this subsystem matters for token cost)

```
permission/index.ts:204-214  disabled(tools, ruleset) → Set<string>
permission/index.ts:216-219  visibleTools(tools, ruleset)
session/llm/request.ts:208-214  resolveTools()  ← called at :148
session/llm/request.ts:184      tools: Object.fromEntries(...)  → provider request body
```

**A denied tool's description and JSON Schema never reach the model.** Genuinely subtractive.

**But the gate is narrow — `index.ts:210-211`:**
```ts
const rule = ruleset.findLast(r => Wildcard.match(permission, r.permission))
return rule?.pattern === "*" && rule.action === "deny"
```
Only a **blanket** deny hides a tool. `bash: {"rm -rf *": "deny"}` leaves the full bash schema in
context and is enforced at call time by `ask()` throwing `DeniedError`. And because `findLast` is
used, a later narrower rule *un-hides* the tool: `{"*":"deny"}` followed by
`{"bash":{"ls *":"allow"}}` keeps `bash` visible.

**Alias table — `index.ts:205-206`:**
- `edit`, `write`, `apply_patch` → all resolve against the **`edit`** permission
- `list_mcp_resources`, `list_mcp_resource_templates`, `read_mcp_resource` → against **`read`**

**Other places a deny removes context (not just blocks a call):**

| Site | Removes |
|---|---|
| `tool/registry.ts:262-264` | denied subagents from the **`task` tool's description text** |
| `tool/registry.ts:281-282` + `:300-303` | MCP tools from the code-mode catalog; empty catalog drops the whole `execute` tool |
| `tool/code-mode.ts:209-210` | the code-mode TS API surface |
| `skill/index.ts:314` | denied skills from the available list |
| `session/system.ts:99` | the **entire `<available_skills>` block** if `skill` is blanket-denied |
| `session/system.ts:112-117` | an MCP server's `<mcp_instructions>` when all its tools are disabled |

---

## Ask call sites (every permission gate in the codebase)

Central gateway: `Tool.Context.ask`, wired at **`session/tools.ts:81-89`** (`.pipe(Effect.orDie)`
at `:89` — permission failures become defects). Custom/plugin tools go through
`tool/registry.ts:145`. Subagents: `session/prompt.ts:341-347`; a no-op stub `ask: () =>
Effect.void` at `session/prompt.ts:825`.

| Subsystem | file:line | Permission key |
|---|---|---|
| bash | `tool/shell.ts:270` / `:283` | `external_directory` / `bash` |
| read | `tool/read.ts:255` | `read` |
| write | `tool/write.ts:54` | `edit` |
| edit | `tool/edit.ts:102`, `:145` | `edit` |
| apply_patch | `tool/apply_patch.ts:206` | `edit` |
| glob | `tool/glob.ts:28` | `glob` |
| grep | `tool/grep.ts:39` | `grep` |
| webfetch | `tool/webfetch.ts:39` | `webfetch` |
| websearch | `tool/websearch.ts:119` | `websearch` |
| todowrite | `tool/todo.ts:24` | `todowrite` |
| lsp | `tool/lsp.ts:56` | `lsp` |
| task | `tool/task.ts:120` | `task` |
| skill | `tool/skill.ts:27` | `skill` |
| external dir | `tool/external-directory.ts:35` | `external_directory` |
| code-mode | `tool/code-mode.ts:147` | dynamic `entry.key` |
| MCP resources | `session/tools.ts:180`, `:263`, `:343` | `read` |
| MCP tool exec | `session/tools.ts:408` | dynamic key, `patterns:["*"]` |
| doom-loop detector | `session/processor.ts:372-379` | `doom_loop` |
| workflow approval | `session/llm.ts:186-196` | `workflow_tool_approval` |

`tool/question.ts:24` and `tool/plan.ts:30` call `question.ask` — a **separate** service
(`src/question/index.ts`), structurally parallel but unrelated to this subsystem.

---

## Auto-approve (`--auto`) — not implemented here

The service has no auto-approve concept. It is **client-side**, by auto-replying to the published
event:

| Client | Site |
|---|---|
| CLI `run` | `cli/cmd/run.ts:242-246` (flag), `:274` (`auto = args.auto \|\| args.yolo \|\| args["dangerously-skip-permissions"]`), **`:796-815`** — auto → `reply:"once"` (801-804); **otherwise auto-*rejects*** (811-814) |
| TUI | `cli/cmd/tui.ts:108,118,294` → `tui/src/context/permission.tsx:5,12,22` → **`tui/src/context/sync.tsx:190-200`** |
| Desktop | `app/src/context/permission.tsx:158,291,299,428` |

**Two consequences for the control terminal:**
1. Under `--auto`, `sync.tsx:190-200` replies *before* writing to the store — a RED border driven
   off store state will never fire (SCAN.md §6).
2. `--auto` still round-trips through the event bus. **A headless client that ignores
   `permission.asked` hangs forever** — there is no server-side timeout.

---

## Token cost

**Zero on the ask path.** Nothing in `permission/` writes system-prompt or message text (imports
at `index.ts:1-8` are `LayerNode`, `ConfigPermissionV1`, `InstanceState`, `Wildcard`, `effect`,
`os`, `PermissionV1`, `EventV2Bridge` — no session, no prompt, no plugin service).

**Non-zero on the rejection path.** The three error classes carry model-facing messages:

| Error | `message` | Reaches the model via |
|---|---|---|
| `RejectedError` (`core/src/v1/permission.ts:8-10`) | "The user rejected permission to use this specific tool call." | ↓ |
| `CorrectedError` (`:16-18`) | interpolates the user's `feedback` **verbatim** | ↓ |
| `DeniedError` (`:24-26`) | **`JSON.stringify(this.ruleset)`** — matching permission rules serialized into context | ↓ |

Path: `ask()` throws (`index.ts:76` or `122-127`) → `Effect.orDie` (`session/tools.ts:89`) →
`SessionProcessor.failToolCall` (`session/processor.ts:186`, writes `error` at `:194`) →
`session/message-v2.ts:337-347` emits `{state:"output-error", errorText}` into the assistant
parts sent to the provider. `processor.ts:200-202` also sets `ctx.blocked`, halting the loop.

**Net effect on standing context is strongly negative** (i.e. it removes text) — see the
subtractive table above.

---

## Extension points

| Point | Mechanism | Site |
|---|---|---|
| Static rules | config `permission: {}` | `fromConfig()` `index.ts:186-198`; env override `config/config.ts:545-551` |
| Per-agent rules | `agent.permission` in agent frontmatter/config | `agent/agent.ts:293` |
| Per-session rules | `PATCH /session/:id` `{permission}` | `handlers/session.ts:194-197` |
| Runtime approval | `POST /permission/reply` `{reply:"always"}` | `index.ts:145-166` |
| Auto-approve | client-side reply to `permission.asked` | `sync.tsx:190-200`, `run.ts:796-815` |
| **plugin `permission.ask` hook** | **DEAD — see gotchas** | declared `packages/plugin/src/index.ts:261` |

---

## Gotchas

1. **The `permission.ask` plugin hook is dead.** Declared at `packages/plugin/src/index.ts:261`;
   **zero trigger sites repo-wide.** Verified: grep for the exact quoted literal `"permission.ask"`
   across `packages/**/*.{ts,tsx,js,json,md}` returns exactly two hits — the declaration and a
   docs mention at `packages/core/src/plugin/skill/customize-opencode.md:354`. Every other
   `permission.ask` hit is either the `permission.ask**ed**` event or the Effect service method
   `perm.ask(...)`. `permission/index.ts` imports no plugin service at all. Implementing the hook
   is a no-op; to gate permissions from a plugin you must intercept `tool.execute.before` instead.
2. **`findLast`, not specificity.** A `{"*": "allow"}` written *after* a narrow deny wins. Config
   key order is load-bearing, which is why `core/src/v1/config/permission.ts:14-16` pins
   `propertyOrder: "original"`.
3. **Runtime approvals outrank configured denies.** `index.ts:73` spreads `approved` last, so a
   user who answers "always" permanently overrides a config `deny` for matching patterns — for the
   life of the process, across all sessions in the instance.
4. **"always" is instance-wide, not session-wide.** `index.ts:145-151` has no `sessionID` filter.
5. **One `reject` clears the session's whole pending queue.** `index.ts:129-138`.
6. **One denied pattern aborts the entire ask.** `index.ts:75-79` — patterns are AND, not OR.
7. **No timeout on `Deferred.await`.** A permission request blocks its tool call forever until
   replied or the instance scope closes (`index.ts:54-61`).
8. **Blanket vs scoped deny is the whole ballgame for token cost.** Only `pattern: "*"` removes a
   schema (`index.ts:211`). SCAN.md §4's "Permissions are subtractive — a deny removes the tool
   schema entirely" is **true only for blanket denies**; correct that before relying on it.
9. **`edit`/`write`/`apply_patch` share one permission key** (`index.ts:205`). To hide file
   mutation you must deny `edit`, not `write`.
10. **There is a second, parallel implementation.** `packages/core/src/permission.ts` (310 lines)
    is an independent v2 service — tag `"@opencode/v2/Permission"` (`:101`), its own `evaluate`
    (`:76`), `merge` (`:88`), errors `DeclinedError`/`BlockedError` (`:60-72`), and its own
    `Event.Asked`/`Replied` publishes at `:184, :225, :239, :276`. It uses `action`/`resource`
    instead of `permission`/`pattern`. Its only importer under `packages/*/src` is
    `packages/server/src/handlers/permission.ts:2`. **The v1 service documented here is what
    `packages/opencode` runs** — do not conflate the two `permission.asked` publishers.

---

## Strip levers

| Lever | Site | Effect |
|---|---|---|
| **Blanket-deny unused tools** — the single largest token cut in the fork | config `permission`; enforced `index.ts:204-214` → `session/llm/request.ts:208-214` | removes description + schema from context. Target list and per-tool bytes in `../tool/TOOL.MAP.md` |
| Deny `skill` | `system.ts:99` early-returns | removes the whole `<available_skills>` block (~1,930 tok) *and* the `skill` tool |
| Deny specific subagents via `task` | `tool/registry.ts:262-264` | shrinks the `task` description (714 B for 2) |
| Widen the subtraction rule | **`index.ts:210-211`** | changing `rule?.pattern === "*"` to also hide on any deny would make scoped denies subtractive too — a real source-level lever, but it changes semantics |
| Trim `DeniedError`'s payload | `core/src/v1/permission.ts:24-26` | stops serializing the ruleset into model context on every deny |
| Drop the dead hook | `packages/plugin/src/index.ts:261` | contract cleanup, zero runtime effect |
| Simplify `ARITY` | `arity.ts:24-161` | no token effect — code size only |
