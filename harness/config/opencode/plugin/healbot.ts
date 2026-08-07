/**
 * The healbot SERVER plugin. Two halves that share one implementation of retirement:
 *
 *   A. HEADLESS AUTOMATIC RETIREMENT — the lifecycle guard, moved off the screen (Phase 6).
 *   B. THE CONTROL AGENT'S TOOLS — `PLAN.md:378`'s build-order step 5: "its own session in the
 *      same server, with tools to spawn / prompt / abort / retire the others".
 *
 * They live in ONE file because `retire()` is the same operation for both, and it builds a handoff
 * document whose exact prose is behaviour.
 *
 * THIS FILE IS NOW THE ONLY IMPLEMENTATION OF RETIREMENT ANYWHERE — Phase 7. Until then
 * `healbot.tsx` carried a second complete copy for the operator's manual `x`, because the harness
 * config directory and the fork checkout cannot import each other (one is not in the other's
 * workspace, the other is derived and gitignored). Phase 6 called that "a compromise guarded by a
 * test" and pointed at `probe_twin.py`. A review then found the guard compared only double-quoted
 * literals, so it could not see either template literal that renders the document's actual bullets
 * — it missed eight seeded divergences and caught one — and that the two copies were also a live
 * race, since `x` and the gate could both reach `POST /session` for the same session.
 *
 * So `x` no longer retires. It writes a request to session metadata and this file serves it: see
 * `REQUEST_KEY` and `considerRequest`. One writer, one document, one `busy` flag that now actually
 * means something. `probe_twin.py` was rewritten to assert the second copy is GONE rather than to
 * compare it, and `probe_request_channel.py` drives the new channel end to end for free.
 *
 * WHY A SERVER PLUGIN RATHER THAN A TUI ONE.
 *
 * Phase 5 built automatic retirement and TESTED it 13/13 (`docs/HARDEN.md` §7), but the trigger
 * was a `createEffect` INSIDE the Healbot route component. That has two consequences, and the
 * second is worse than the first:
 *
 *   1. It only runs while the grid is open. Navigating into a session with `enter` unmounts the
 *      route (`app.tsx:1079-1085` computes the plugin route in a `createMemo` that returns
 *      `undefined` the moment `route.data.type !== "plugin"`), so retirement is dead for as long
 *      as the operator is looking at a session.
 *   2. A fleet left running with NO client attached retires nothing at all. That is the whole
 *      point of `harness/fleet.sh` — the server outlives the terminal — so the guard was absent
 *      in exactly the topology the architecture exists to support.
 *
 * The obvious fix, "move it to TUI plugin scope", does not actually fix (2) and is unsound
 * besides:
 *
 *   - A TUI plugin runs in the TUI process. No TUI, no retirement. (2) survives untouched.
 *   - TUI plugin scope has NO Solid owner. `plugin/tui/runtime.ts:1082-1088`'s `load()` crosses
 *     at least one `await` before `activatePluginEntry` invokes `tui(api)` at `:529`, so the
 *     synchronous `createRoot` window is long closed. TESTED: `getOwner()` is `null` there. A
 *     `createEffect` at that scope runs and stays reactive but is never disposed, and a bare
 *     `onCleanup` is a SILENT NO-OP. Moving a retirement trigger — which spawns and archives
 *     sessions — into an undisposable effect is the wrong direction.
 *   - `TuiPluginModule` is `{ id?, tui, server?: never }` and `PluginModule` is
 *     `{ id?, server, tui?: never }` (`packages/plugin/src/tui.ts` and `.../index.ts`). The two
 *     are mutually exclusive by type, so `healbot.tsx` could not have hosted this anyway.
 *
 * So it lives here, on the SERVER plugin surface, and runs inside `opencode serve`:
 *
 *   - `Hooks.event` is a real hook with a LIVE trigger site — `plugin/index.ts:255`,
 *     `void hook["event"]?.({ event: { id, type, properties: event.data } })`. (Worth stating,
 *     because this project has already been bitten by a DECLARED-but-dead hook: `permission.ask`
 *     has zero trigger sites.)
 *   - It is directory-filtered at `plugin/index.ts:251`
 *     (`if (event.location?.directory !== ctx.directory) return`), and every event published
 *     through the bridge carries that location automatically (`event-v2-bridge.ts:19-33` attaches
 *     `Location.Info` from `InstanceRef`). One plugin instance per directory, each guarding its
 *     own sessions — which is the coverage you want, not a limitation.
 *   - It covers BOTH topologies with one implementation. Under `fleet.sh` the server is a
 *     separate long-lived process; under plain `opencode` the TUI hosts a server in-process.
 *     Both load config plugins, so both get this.
 *
 * REGISTRATION: `opencode.jsonc`'s `"plugin"` array. `getLegacyPlugins`
 * (`plugin/index.ts:95-108`) treats every export of the module as a plugin and THROWS
 * `TypeError: Plugin export is not a function` on any export that is not one — so this file
 * exports exactly one function and nothing else. Every constant below is deliberately module-
 * private for that reason, not for encapsulation. (Being listed in the array AND auto-discovered
 * by `config/plugin.ts:21`'s `{plugin,plugins}/*.{ts,js}` glob does not double-load it:
 * `config.ts:343` dedupes plugin origins by identity. TESTED — the arming line appears once.)
 *
 * NO IMPORTS, deliberately, and the same choice `trim-tools.ts` makes. The harness config
 * directory's `node_modules` is UNTRACKED (`HARNESS.md` records this: opencode seeds a
 * self-ignoring `.gitignore` into any config dir at boot), so a fresh clone has the harness
 * without its dependency manifest. A plugin that imported `zod` or `@opencode-ai/plugin` would
 * fail to load there — silently, as a line in a server log. Tool argument schemas are therefore
 * raw JSON Schema, which `tool/registry.ts:129` accepts via `legacyJsonSchema` when the entries
 * are not zod types. That path marks every property REQUIRED (`registry.ts:365`), which is why
 * no tool below has an optional argument.
 *
 * KILL SWITCH: `HEALBOT_AUTO_RETIRE=0` disables half A only — the control tools stay, because an
 * operator who wants retirement to be deliberate still wants to be able to ask for it.
 */

// ---------------------------------------------------------------------------------------------
// Thresholds. These MUST agree with `healbot.tsx`'s copies — see the drift note at the bottom.
// ---------------------------------------------------------------------------------------------

/**
 * Context occupancy at which a session should be retired, in tokens. The ONLY gate. There is no
 * second one, and the number below is not independent of that fact — read both paragraphs before
 * changing either.
 *
 * IT FIRES AT THE END OF A TURN. `turnFinished()` below uses opencode's own predicate
 * (`prompt.ts:1295`), which excludes `"tool-calls"` and `"unknown"` — so a multi-step turn is
 * allowed to run to completion and the gate acts in the gap between turns. Nothing in flight is
 * aborted. This is what `PLAN.md` specified all along, and until Phase 7 it was what every
 * artifact in this repo *claimed* while the code did something else: the old predicate read
 * `finish` directly, and `processor.ts:443-445` sets `finish` and `tokens` in one mutation at
 * every `step-finish`, so it was true mid-turn on 733/733 measured messages.
 *
 * **180,000, AND THE HEADROOM IS THE WHOLE REASON.** Waiting for the turn means accepting whatever
 * that turn adds, and MEASURED that is up to ~170K on its own (`docs/HARDEN.md` §6: occupancy
 * 5,216 -> 70,898 on a single tool result, the turn finishing at 175,090). Against a ~360K ceiling
 * the arithmetic for one gate is `RETIRE_AT + worst_turn < ceiling`, so anything at or above
 * ~190,000 can be carried past the ceiling by one ordinary read-heavy turn. 180,000 + ~170K =
 * ~350K, just inside.
 *
 * This replaced 256,000, which was correct for a DIFFERENT design — Phase 5 chose it against a
 * second gate at 330,000 that aborted mid-turn, and Phase 7 measured that second gate to have been
 * inert since it was written. When the hard gate was deleted and the predicate made per-turn, the
 * soft threshold had to come down with it. A 256,000 gate with no hard gate and per-turn semantics
 * is the one combination that can silently drive a session off the cliff.
 *
 * If you raise this, you are trading session length for that margin, and the margin is the only
 * thing standing between a long session and `ContextOverflowError`. Lower it freely; raise it only
 * with a new measurement of worst-case single-turn growth.
 *
 * **The ceiling is ~360K, NOT the 922,000 `limit.input` the model registry advertises.** MEASURED:
 * a session driven up took its last successful turn at occupancy 359,829 and then failed 25
 * consecutive turns with the provider's `ContextOverflowError`. The harness sets
 * `compaction.auto: false`, which makes `overflow.ts:28` disable opencode's own overflow check
 * entirely, so nothing upstream catches it — the provider does, and by then the turn is lost.
 * Nothing is truncated on the way up either: there is no history slicing on the v1 prompt path and
 * `compaction.prune` is unset, so opencode sends the ENTIRE history every turn until the provider
 * refuses it. It is a cliff, not a slope.
 *
 * Floor, measured: a freshly spawned and seeded session reads ~4.8K on its first turn, almost all
 * `cache.read`. A threshold at or below that fires on turn one and proves nothing.
 */
const RETIRE_AT = Math.max(1, Number(process.env["HEALBOT_RETIRE_AT"]) || 180_000)

/** Kill switch. It spawns and archives without asking, so it gets one. */
const AUTO_RETIRE = process.env["HEALBOT_AUTO_RETIRE"] !== "0"

/**
 * How many user messages the handoff fans out over to collect changed files, head AND tail.
 *
 * Never just the tail. TESTED at the 350K threshold: a 103-message session produced an EMPTY
 * file list because the last 20 user messages were all pure reads and the one file the session
 * created was made on turn one. Scaffolding happens early; a handoff that only looks at recent
 * turns systematically misses exactly the files worth handing over.
 */
const DIFF_FANOUT = 60

/** Guard against a pathological history making the startup/steady-state cost unbounded. */
const MAX_DOCUMENT_TAIL = 2000

/**
 * Capture trigger (iii): the occupancy at which a session is nudged to record its decisions.
 *
 * A FRACTION OF THE RETIREMENT GATE, not a number of its own, because the thing it has to stay
 * below is the gate — and an absolute threshold set beside a gate that moves with
 * `HEALBOT_RETIRE_AT` would silently end up above it. At the default 0.5 a session is asked at
 * half its context, which leaves it a whole half to answer in.
 *
 * WHY THIS EXISTS AT ALL, and why it is not "capture at retirement". `healbot.ts:550-558`
 * archives a session whose `open.length === 0` with no successor and no record, so the sessions
 * that finished their work cleanly are exactly the ones that record nothing. Waiting for
 * retirement means the cleanest sessions are the ones the store never hears from. Firing at a
 * fraction closes that hole structurally rather than by asking the agent to remember.
 *
 * The 0.5 is a GUESS and is stated as one. Nothing has measured where useful decisions actually
 * accumulate in a session; it is tunable so the answer can replace it.
 */
const CAPTURE_AT = RETIRE_AT * Math.min(1, Math.max(0.05, Number(process.env["HEALBOT_CAPTURE_AT"]) || 0.5))

/**
 * The decision-record store's one implementation, reached by spawning it.
 *
 * WHY A SUBPROCESS AND NOT TYPESCRIPT. The plan called for building the record here. That would
 * put a second copy of the project-key rule, the id rule, the JSON-frontmatter format and the
 * whole validator into a file that CANNOT import the first copy — and two implementations of one
 * rule is the failure the plan deletes `harness/records.py` to avoid. It does not stop being
 * that failure when the second copy is in another language; it gets harder to notice, because no
 * probe can diff a TypeScript key function against a Python one by reading either.
 *
 * The no-imports rule is untouched: `Bun.spawn` and `import.meta.dir` are runtime globals, not
 * imports, so the harness config directory still needs no `node_modules`. TESTED 2026-08-06 —
 * `bun run` reports `Bun.spawn`, `Bun.file`, `Bun.write` and `import.meta.dir` all present, and
 * a record with multi-paragraph prose round-trips through this path intact.
 *
 * In a materialized A/B arm this path does not resolve, because `arms.py` snapshots
 * `harness/config` alone. The tool then refuses by name, which is the right answer: records must
 * not leak into a measurement, and an arm that silently wrote them would contaminate one.
 */
const MEMORY_PY = `${import.meta.dir}/../../../memory.py`

/**
 * The session-metadata key the grid's `x` writes to ask THIS process to retire a session.
 *
 * THE POINT IS THAT THERE IS NOW EXACTLY ONE RETIRING PROCESS. Until Phase 7 the grid ran its own
 * copy of `retire()` in the TUI process while this plugin ran another in the server, with no
 * shared lock, so `x` landing as the gate fired produced two successors for one session. Phase 6
 * documented that as "narrowed to one request" by a re-read before archiving; a review showed the
 * re-read narrows nothing, because it runs AFTER the successor is created and seeded.
 *
 * So the grid no longer retires. It relays. `PATCH /session/{id}` with
 * `metadata: { healbot: { retireRequested: <ms> } }` is accepted at
 * `httpapi/groups/session.ts:51` and `handlers/session.ts:191-192`, reaches `Session.setMetadata`
 * (`session.ts:763`), which calls the shared `patch()` — and `patch()` publishes
 * `SessionV1.Event.Updated` with the WHOLE session object at `session.ts:748`. This plugin's
 * `event` hook already receives every event for its directory, so the request arrives here with no
 * new endpoint, no new dependency and no route registration (the server plugin surface has none to
 * offer — `packages/plugin/src/index.ts` is hooks only, and `event` is receive-only).
 *
 * Self-triggering is not a hazard: archiving is itself a `patch()` and republishes `session.updated`
 * with this key still set, but by then `time.archived` is populated and `considerRequest` bails on
 * it. The key is deliberately left in place rather than cleared — it is a record of who asked.
 */
const REQUEST_KEY = "healbot"

/** The request marker, or 0. Kept as a function so the grid's shape and this reader stay together. */
function requestedAt(session: SessionInfo | undefined): number {
  const value = session?.metadata?.[REQUEST_KEY]?.["retireRequested"]
  return typeof value === "number" && value > 0 ? value : 0
}

// ---------------------------------------------------------------------------------------------
// Structural types. Declared locally rather than imported, matching `trim-tools.ts`: the harness
// config directory is not part of the fork's workspace, so an import of `@opencode-ai/plugin`
// would couple the deliverable to a node_modules tree it does not own.
// ---------------------------------------------------------------------------------------------

type Tokens = {
  total?: number
  input?: number
  output?: number
  reasoning?: number
  cache?: { read?: number; write?: number }
}

type MessageInfo = {
  id?: string
  role?: string
  sessionID?: string
  parentID?: string
  tokens?: Tokens
  finish?: string
  error?: unknown
  time?: { completed?: number }
}

type Part = { type?: string; text?: string }
type WithParts = { info?: MessageInfo; parts?: Part[] }

type SessionInfo = {
  id: string
  title?: string
  parentID?: string
  directory?: string
  time?: { archived?: number }
  metadata?: Record<string, any>
}

type Todo = { content?: string; status?: string }
type FileDiff = { file?: string }
type Pending = { sessionID?: string }

type PluginEvent = { id?: string; type?: string; properties?: Record<string, any> }

type PluginInput = {
  directory: string
  serverUrl: URL
}

// ---------------------------------------------------------------------------------------------
// HTTP. Deliberately raw `fetch` rather than the injected SDK client.
//
// The plugin is handed `createOpencodeClient` from `@opencode-ai/sdk` — the **v1** generated
// client (`sdk/js/src/client.ts:33` -> `gen/sdk.gen.ts`), NOT the v2 client the TUI uses. They
// diverge on all three calls that matter here, and the divergence is silent:
//
//   - The v1 client has **no `permission` and no `question` sub-client at all**. Its
//     `OpencodeClient` exposes global/project/pty/config/tool/instance/path/vcs/session/command/
//     provider/find/file/app/mcp/lsp/formatter/tui/auth/event and one loose
//     `postSessionIdPermissionsPermissionId`. `client.permission.list()` — which `healbot.tsx`
//     calls happily on the v2 client — does not exist here.
//   - v1 `SessionUpdateData["body"]` is `{ title?: string }`. There is no `time.archived`, so the
//     one call retirement cannot do without would not type-check. The SERVER accepts it —
//     `groups/session.ts:53-57`'s `UpdatePayload` has `time: { archived }` and
//     `handlers/session.ts:200-201` calls `session.setArchived` — the generated v1 types are
//     simply narrower than the route.
//   - v1 `SessionCreateData["body"]` is `{ parentID?, title? }`; `directory` is a query param.
//
// So the choice is between casting past the generated types on three calls and writing the
// requests out. Written out is more honest, matches the endpoints this project has verified and
// documented, matches what `.carryover/verified/rig.py`'s `Api` already does, and cannot rot when
// the SDK is regenerated.
// ---------------------------------------------------------------------------------------------

/**
 * `x-opencode-directory` is NOT optional. `workspace-routing.ts:87` resolves the instance as
 * `?directory || x-opencode-directory || process.cwd()`, and under `serve` the cwd is wherever
 * the launcher put it. Get this wrong and every call succeeds against the WRONG instance — the
 * exact failure that cost a whole run in Phase 5. The real SDK url-encodes it
 * (`sdk/js/src/client.ts:46-49`); so do we.
 */
function headers(directory: string): Record<string, string> {
  const out: Record<string, string> = {
    "content-type": "application/json",
    "x-opencode-directory": encodeURIComponent(directory),
  }
  // Mirrors `ServerAuth.header` (`server/auth.ts:36-42`). Unset under the harness — `fleet.sh`
  // binds loopback only — but a plugin that silently 401s the moment someone sets a password is
  // a guard that stops guarding without saying so.
  const password = process.env["OPENCODE_SERVER_PASSWORD"]
  if (password) {
    const username = process.env["OPENCODE_SERVER_USERNAME"] || "opencode"
    out["authorization"] = `Basic ${Buffer.from(`${username}:${password}`).toString("base64")}`
  }
  return out
}

function makeApi(base: string, directory: string) {
  return async function api<T>(method: string, path: string, body?: unknown): Promise<T> {
    const response = await fetch(`${base}${path}`, {
      method,
      headers: headers(directory),
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
    if (!response.ok) {
      const detail = await response.text().catch(() => "")
      throw new Error(`${method} ${path} -> ${response.status} ${detail.slice(0, 200)}`)
    }
    if (response.status === 204) return undefined as T
    return (await response.json().catch(() => undefined)) as T
  }
}

// ---------------------------------------------------------------------------------------------
// Occupancy
// ---------------------------------------------------------------------------------------------

/**
 * Context OCCUPANCY, in tokens — how full the window is right now.
 *
 * Deliberately not `session.tokens`, which is lifetime spend and answers a different question:
 * the reference 101-turn session shows 652K input against 8.7M `cache.read`, which says nothing
 * about how full its window is. This is the quantity `isOverflow` itself reads
 * (`session/overflow.ts:21-33`) — the assistant message's own `tokens`, delivered on every
 * `message.updated` — with **`cache.read` included**, because the cached prompt prefix is part of
 * the window.
 *
 * Same expression as `healbot.tsx`'s `occupancyOf`, so the grid's `RETIRE` border and this
 * trigger can never disagree about which sessions are over the line.
 */
function occupancyOf(tokens: Tokens | undefined): number {
  if (!tokens) return 0
  if (tokens.total && tokens.total > 0) return tokens.total
  return (
    (tokens.input ?? 0) + (tokens.output ?? 0) + (tokens.cache?.read ?? 0) + (tokens.cache?.write ?? 0)
  )
}

/**
 * Has the TURN ended? This is opencode's own predicate, and using anything else is what Phase 7
 * had to correct.
 *
 * THE TRAP, stated plainly because it cost two phases. Every completion-looking field on an
 * assistant message is set per STEP, not per turn. `processor.ts:443` sets `finish = value.reason`
 * and `:445` sets `tokens`, both inside the `step-finish` case that emits the `step-finish` part at
 * `:452`; `:595-596` sets `time.completed` in `cleanup()`, which `Effect.ensuring` at `:676` runs
 * per `process()` call — and `prompt.ts:1186-1201` creates a NEW assistant message per step. So
 * `Boolean(info.time?.completed || info.finish)` — the old implementation — is true several times
 * inside one turn, with `finish: "tool-calls"` each time, which is precisely the value
 * `prompt.ts:1111-1114` loops on.
 *
 * The exclusion list is the entire difference, and it is copied from `prompt.ts:1295`:
 *
 *     const finished = handle.message.finish && !["tool-calls", "unknown"].includes(...)
 *
 * `time.completed` is deliberately NOT read here. It looks like the most authoritative signal and
 * is the least: it is per-step like the rest, and including it re-introduces the whole defect.
 *
 * `error` IS read. A turn that died — the `ContextOverflowError` case above, a crashed tool, an
 * expired credential — is over, and a session sitting at the gate with a dead turn is exactly one
 * that should be handed off rather than left to fail again. `processor.ts:607-613` sets
 * `finish: "error"` on that path, so the finish clause would usually catch it anyway; reading the
 * field directly makes it independent of that spelling.
 */
function turnFinished(info: MessageInfo): boolean {
  if (info.error) return true
  return Boolean(info.finish && !["tool-calls", "unknown"].includes(info.finish))
}

// ---------------------------------------------------------------------------------------------
// The handoff document
// ---------------------------------------------------------------------------------------------

/**
 * The passover document handed to a successor session.
 *
 * THE ONLY COPY. Until Phase 7 this was a verbatim twin of a `handoffDocument` in `healbot.tsx`,
 * kept in step by hand because the operator's `x` ran its own retirement in the TUI process. The
 * requirement was real — a successor briefed differently depending on whether a human pressed a
 * key or the gate fired is precisely the class of silent divergence this project keeps catching in
 * itself — but the guard was not. `probe_twin.py` compared only double-quoted literals, and both
 * lines that render the document's actual bullets are template literals, so eight seeded
 * divergences passed it.
 *
 * `x` now relays a request to this process instead (see `REQUEST_KEY`), so there is one
 * implementation and nothing to keep in step. `probe_twin.py` was rewritten to assert the grid has
 * NO copy of this function, with an inverted mutation check so the absence assertion cannot pass
 * by reading the wrong text.
 *
 * DEVIATION FROM PLAN.md:383, inherited from the grid: the plan names
 * `POST /session/{id}/summarize` as the source, but that route is `compactSvc.create`
 * (`handlers/session.ts:273-283`) — COMPACTION, an LLM turn. The git-diff summariser is a
 * different function of the same name (`summary.ts:102-127`) which already runs on the prompt
 * path. The material below is the literal todos and the literal file list; it loses no
 * specificity and costs no model turn.
 */
function handoffDocument(input: {
  title: string
  objective?: string
  open: { content?: string }[]
  files: string[]
  lastMessage?: string
}) {
  const lines = [
    "You are taking over a session that was retired because its context window was too full.",
    "Continue its work now. Do not start over, and do not simply report status — the",
    "outstanding items below are what is left to DO.",
    "",
    // Labelled as the ORIGINAL INSTRUCTION rather than "objective", and explicitly demoted below
    // the outstanding list. TESTED and it matters: handed a verbatim first message that happened
    // to contain step sequencing ("do only the first, leave the rest pending"), the successor
    // obeyed that stale instruction and replied "No further work performed".
    "## Original instruction, for context only",
    "It may contain sequencing that has already been carried out. Where the two disagree, the",
    "outstanding list below wins.",
    "",
    input.objective?.trim() || input.title,
    "",
    "## Outstanding work — do this",
    ...(input.open.length > 0
      ? input.open.map((todo) => `- [ ] ${todo.content}`)
      : ["- (no open todo items were recorded)"]),
  ]
  if (input.files.length > 0) {
    lines.push("", "## Files already changed — read these before editing them", ...input.files.map((f) => `- ${f}`))
  }
  if (input.lastMessage?.trim()) {
    lines.push("", "## Where it left off", input.lastMessage.trim().slice(0, MAX_DOCUMENT_TAIL))
  }
  return lines.join("\n")
}

// ---------------------------------------------------------------------------------------------
// The plugin
// ---------------------------------------------------------------------------------------------

export const Healbot = async (input: PluginInput) => {
  const directory = input.directory
  const base = input.serverUrl.toString().replace(/\/$/, "")
  const api = makeApi(base, directory)
  const log = (message: string) => console.log(`[healbot] ${message}`)

  /**
   * Sessions this process has already acted on, so a retire that FAILS is not retried on every
   * subsequent event. Without it a session that is over the gate and erroring emits
   * `message.updated` repeatedly and would spawn a successor per event.
   */
  const handled = new Set<string>()

  /**
   * The decision-record maps. Same scope, lifetime and restart semantics as `handled` above: a
   * server restart forgets all three, which for these two means a session gets nudged once more
   * than it strictly needed. That is the right way round — the alternative is persisting nudge
   * state, and a nudge that survives a restart can go permanently silent on a session that never
   * actually captured anything.
   */
  const nudged = new Set<string>()

  /** Sessions that have called `healbot_decide`. This is the "uncaptured material" gate: a
   * session that already recorded a decision is not asked again. */
  const captured = new Set<string>()

  /** Sessions with a nudge waiting to be delivered on their next system prompt. Delivery costs
   * ZERO extra turns — it rides the prompt the session was going to send anyway. */
  const nudgePending = new Set<string>()

  /**
   * The orientation block, SNAPSHOTTED PER SESSION at its first system prompt.
   *
   * Not re-read every turn, and the reason is cost rather than tidiness. `request.ts:74-78`
   * keeps element 0 of the system array as the cacheable header and joins the rest; a block
   * whose text changed mid-session because another worktree captured a record would move bytes
   * inside that joined tail on a turn where nothing else moved, and the session would pay a
   * cache miss for a decision it had no interest in. A session orients ONCE, from what was
   * settled when it started, which is also the honest reading of what "orientation" means.
   */
  const orientOf = new Map<string, string>()

  /**
   * Serialised deliberately. Each retire spawns one session and archives another; two interleaved
   * would double-spend the gate. Anything skipped while one is in flight is picked up on the next
   * event, because a session over the threshold keeps producing them.
   */
  let busy = false

  /** Blocked on a human? Answering is the operator's call, and retiring underneath a pending
   * permission or question would discard the decision they were in the middle of making.
   *
   * Asked over HTTP rather than tracked from events on purpose: `GET /permission` and
   * `GET /question` read the live in-memory pending maps (`permission/index.ts:169`,
   * `question/index.ts:150-153`), so this has no cold-start hole — a block raised before this
   * plugin loaded is still visible. An event-fed cache would not be. */
  async function isBlocked(sessionID: string): Promise<boolean> {
    const [permissions, questions] = await Promise.all([
      api<Pending[]>("GET", "/permission").catch(() => [] as Pending[]),
      api<Pending[]>("GET", "/question").catch(() => [] as Pending[]),
    ])
    const hit = (list: Pending[]) => Array.isArray(list) && list.some((item) => item?.sessionID === sessionID)
    return hit(permissions) || hit(questions)
  }

  async function retire(session: SessionInfo) {
    const sessionID = session.id
    const label = (session.title ?? sessionID).slice(0, 60)

    // Stop the predecessor BEFORE anything else. Archiving does not abort — `session.setArchived`
    // is a bare DB patch (`session.ts:759-761`) — so without this the predecessor keeps editing
    // the SAME directory as its successor, with no cell anywhere once archived, possibly parked
    // forever on a permission (`permission/index.ts:96-105` has no timeout).
    //
    // Unconditional and idempotent: aborting an idle session is a no-op, and on the gate path it
    // IS one — `turnFinished()` is what got us here, so the turn is over.
    //
    // Its purpose is the two paths where that is not true. (1) The RACE: a new turn can start
    // between `consider()`'s check and this call, and a turn beginning after the gate was met is
    // exactly what "no turn consumption after the gate" forbids. (2) `healbot_retire`, which the
    // control agent may call on a session that is working right now.
    //
    // Be careful reading this comment against Phase 7's: for one commit the gate fired per STEP and
    // this abort was usually live, cancelling a turn in flight. It is not any more.
    await api("POST", `/session/${sessionID}/abort`)

    // NOT `.catch(() => [])`. A failed read and a genuinely empty list are the same value, and 60
    // lines below, an empty list means ARCHIVE WITH NO SUCCESSOR — so one transient loopback
    // failure would silently retire a session with outstanding work and log that there was none.
    // That is the exact ordering hazard this function warns about further down ("archiving first
    // and failing to seed loses the work with no cell to find it"), reached by a different route.
    //
    // Throwing is recoverable: `consider()` logs `retire FAILED`, the predecessor stays unarchived
    // and still has a cell, and the next event retries. The grid's twin already behaves this way —
    // its `ok()` wrapper throws on the same call — so this also removes a real divergence between
    // the manual and automatic paths that `probe_twin.py` does not cover.
    const todos = await api<Todo[]>("GET", `/session/${sessionID}/todo`).catch((error) => {
      throw new Error(
        `todo read failed, refusing to archive ${sessionID}: ${error instanceof Error ? error.message : String(error)}`,
      )
    })
    const open = (Array.isArray(todos) ? todos : []).filter((todo) => todo && todo.status !== "completed")

    // ONE unlimited fetch, serving the objective, the file fan-out AND the closing narrative.
    // Omitting `limit` is load-bearing, not laziness: `handlers/session.ts:118-121` branches on
    // it. WITH a limit you get `MessageV2.page`, which is `orderBy(desc(...))` — the NEWEST N.
    // WITHOUT one you get `session.messages`, which pages the whole history backwards and
    // `session.ts:852` reverses it, so `[0]` is genuinely the session's first message.
    const history = (await api<WithParts[]>("GET", `/session/${sessionID}/message`).catch(() => [])) ?? []
    const messages = Array.isArray(history) ? history : []

    const textOf = (entry: WithParts) =>
      (entry.parts ?? [])
        .filter((part) => part?.type === "text")
        .map((part) => part.text ?? "")
        .join("\n")
        .trim()

    const users = messages.filter((entry) => entry?.info?.role === "user")

    // The objective comes from the SERVER, and that is the difference between a correct handoff
    // and a confidently wrong one. The TUI store holds at most the newest 100 messages, so on any
    // longer session its first entry is an arbitrary mid-conversation turn — which
    // `handoffDocument` would then label "## Original instruction" and tell the successor to
    // treat as the statement of intent. Retirement targets sessions past 100 messages, so the bug
    // lived exactly where the feature fires. Oldest-first here, so the first one with text really
    // is message one.
    const objective = users.map(textOf).find(Boolean)

    // Newest-first, first assistant message with non-empty text. Skips any in-flight empty row an
    // abort leaves behind — `healbot_retire` on a working session, or the start-of-turn race above.
    const lastMessage = [...messages]
      .reverse()
      .filter((entry) => entry?.info?.role === "assistant")
      .map(textOf)
      .find(Boolean)

    // `GET /session/{id}/diff` is a PER-USER-MESSAGE endpoint, not a session-wide one:
    // `summary.ts:129-133` returns [] outright with no messageID, and [] again unless that
    // message is a USER message. PLAN.md:383 says "its /diff" as though one call covered the
    // session. Fan out and union.
    const ids = users.map((entry) => entry.info?.id).filter((id): id is string => Boolean(id))
    const candidates =
      ids.length <= DIFF_FANOUT ? ids : [...ids.slice(0, DIFF_FANOUT / 2), ...ids.slice(-DIFF_FANOUT / 2)]
    const files = [
      ...new Set(
        (
          await Promise.all(
            candidates.map((messageID) =>
              api<FileDiff[]>("GET", `/session/${sessionID}/diff?messageID=${encodeURIComponent(messageID)}`).catch(
                () => [] as FileDiff[],
              ),
            ),
          )
        )
          .flat()
          .map((entry) => entry?.file)
          .filter((value): value is string => Boolean(value)),
      ),
    ]

    // PLAN.md:369-370 splits the two cases and they really are different: a session with nothing
    // outstanding has nothing to hand over, so spawning a successor would burn a fresh window to
    // say "there is no work".
    if (open.length === 0) {
      await api("PATCH", `/session/${sessionID}`, { time: { archived: Date.now() } })
      const outcome = `retired ${label} — nothing outstanding, no successor spawned`
      log(outcome)
      return outcome
    }

    const document = handoffDocument({
      title: session.title ?? sessionID,
      objective,
      open,
      files,
      lastMessage,
    })

    // `POST /session` + seed is the ONLY path that yields a zero-token successor: `fork` reports 0
    // at creation then climbs to exactly the parent's total within ~3s, and `summarize` mutates in
    // place and adds tokens. Same directory, or the successor cannot see the work — passed as a
    // query param because v1's create body carries only `{parentID, title}`.
    const target = session.directory ?? directory
    const created = await api<SessionInfo>("POST", `/session?directory=${encodeURIComponent(target)}`, {})
    const successorID = created?.id
    if (!successorID) throw new Error("POST /session returned no id")

    // ORDERING IS THE POINT, and Phase 5 fixed it the expensive way. The handoff is only real once
    // the seed is ACCEPTED, so the seed is confirmed BEFORE the source is retired. Failing that
    // way round is recoverable — an unarchived predecessor still has a cell and can be retired
    // again — whereas archiving first and failing to seed loses the work with no cell to find it.
    await api("POST", `/session/${successorID}/prompt_async`, { parts: [{ type: "text", text: document }] })

    // Re-read immediately before the irreversible step, because the grid's manual `x` runs the
    // same flow in a different process and neither can see the other's in-flight state.
    //
    // BE PRECISE ABOUT WHAT THIS BUYS, because the surrounding docs overstated it: it does NOT
    // narrow the two-successor window at all. By the time control reaches here the successor has
    // already been created and seeded, two calls above — the return string below says so itself.
    // All this check prevents is a redundant idempotent PATCH and a log line claiming a retirement
    // that another actor already performed.
    //
    // The window that actually produces two successors runs from `consider()`'s archived check to
    // the `POST /session` above, and it spans `isBlocked`'s two GETs, the abort, the todo GET, an
    // unlimited full-history GET on a session at the gate, and up to DIFF_FANOUT parallel `/diff`
    // GETs. That is seconds, not one request. Closing it needs a claim BEFORE the spawn — see
    // `docs/HEADLESS.md`.
    const current = await api<SessionInfo>("GET", `/session/${sessionID}`).catch(() => undefined)
    if (current?.time?.archived) {
      const outcome = `${label} was archived by another actor mid-handoff; successor ${successorID} is seeded and live`
      log(outcome)
      return outcome
    }

    await api("PATCH", `/session/${sessionID}`, { time: { archived: Date.now() } })
    const outcome =
      `retired ${label} at the gate — handed off ${open.length} open item${open.length === 1 ? "" : "s"}` +
      `, ${files.length} file${files.length === 1 ? "" : "s"} -> ${successorID}`
    log(outcome)
    return outcome
  }

  async function consider(sessionID: string, occupancy: number, turnOver: boolean) {
    if (busy) return
    if (handled.has(sessionID)) return

    // Let the turn finish. There is no second gate to override this any more — `RETIRE_HARD`
    // existed to abort mid-turn when the soft gate's overshoot ran long, and Phase 7 deleted it
    // after measuring that it had never once fired. The margin it was supposed to provide now
    // comes from `RETIRE_AT` being low enough to absorb a worst-case turn instead; see that
    // constant. Cutting a turn off throws away work the successor has to rediscover, which is the
    // looping-discovery failure this handoff design exists to avoid, so the gate always waits.
    if (!turnOver) return

    // CLAIM THE FLAG HERE, before the first await — not after the eligibility checks, which is
    // where it used to be set and where it did not work.
    //
    // `busy` was read at the top of this function and written four awaits later, so it guarded
    // nothing across them: the hook is fire-and-forget (`plugin/index.ts:255` calls it with
    // `void`), a turn emits several qualifying events (occupancy and `finish` land together on
    // every step), and `healbot_retire` can arrive from the control agent at any point. Two
    // invocations could both pass `if (busy)` while the first was parked on the session GET or on
    // `isBlocked`'s two GETs, and both would reach `POST /session` — two live successors seeded
    // with the same handoff, editing the same directory. That contradicted the "serialised
    // deliberately" note on `busy` itself.
    //
    // JavaScript's single thread is what makes the fix sufficient: nothing can interleave between
    // the synchronous `if (busy) return` above and this assignment, so the check-and-set is
    // atomic. `healbot_retire` already had its check and set adjacent, so the two entry points now
    // hold the same discipline and exclude each other. The cost is that eligibility checks for
    // OTHER sessions also wait — acceptable, because a session over the gate keeps emitting
    // events and is reconsidered on the next one.
    busy = true
    try {
      const session = await api<SessionInfo>("GET", `/session/${sessionID}`).catch(() => undefined)
      if (!session) return
      // Already retired. Archiving hides a session from NOTHING server-side (`ListInput` has no
      // `archived` field and `listByProject` has no `time_archived` predicate), so this has to be
      // checked rather than assumed.
      if (session.time?.archived) return
      // Never a subagent. A subagent is a tool call inside its parent's turn; archiving one
      // mid-turn orphans the parent's `task` call, and its window is the parent's problem to bound.
      if (session.parentID) return
      // Blocked on a human — bail WITHOUT marking handled, so answering the block does not cost
      // the session its retirement. This is why `handled.add` is here and not above with `busy`.
      if (await isBlocked(sessionID)) return

      handled.add(sessionID)
      await retire(session)
    } catch (error) {
      // Surfaced, not swallowed, and NOT retried — `handled` already holds the id. A retirement
      // that fails silently in a headless process is the same class of defect as a grid that
      // paints a dead session green.
      log(`retire FAILED for ${sessionID}: ${error instanceof Error ? error.message : String(error)}`)
    } finally {
      busy = false
    }
  }

  /**
   * The operator pressed `x`. Same serialisation as the gate — this is the whole reason the race
   * is closed: both paths now run in ONE process, so `busy` and `handled` actually mean something.
   *
   * Differences from `consider()`, both deliberate:
   *   - No occupancy test. A manual retirement is a decision, not a threshold; retiring a small
   *     session on purpose is a supported thing to do and the grid offers it at any size.
   *   - No `isBlocked` test. The automatic gate skips blocked sessions because retiring underneath
   *     a pending permission discards a decision the human is in the middle of making — but here
   *     the human IS the caller, looking at the same grid that renders the block. Refusing would
   *     be second-guessing the operator; the gate's caution does not transfer.
   * The archived and subagent guards DO transfer: both are structural, not policy.
   */
  async function considerRequest(sessionID: string) {
    if (busy) return
    if (handled.has(sessionID)) return
    busy = true
    try {
      const session = await api<SessionInfo>("GET", `/session/${sessionID}`).catch(() => undefined)
      if (!session) return
      // The archive itself republishes `session.updated` with the request key still set. This is
      // what stops that from looping.
      if (session.time?.archived) return
      if (session.parentID) return
      // Re-read the marker from the server rather than trusting the event payload: the event may
      // be stale by the time this runs, and a request that has already been served leaves an
      // archived session that the check above catches anyway.
      if (!requestedAt(session)) return
      handled.add(sessionID)
      log(`request: retiring ${sessionID} on the operator's mark`)
      await retire(session)
    } catch (error) {
      log(`requested retire FAILED for ${sessionID}: ${error instanceof Error ? error.message : String(error)}`)
    } finally {
      busy = false
    }
  }

  // -------------------------------------------------------------------------------------------
  // B. THE CONTROL AGENT'S TOOLS
  //
  // `PLAN.md:378`: "Control agent. Its own session in the same server, with tools to spawn /
  // prompt / abort / retire the others (POST /session, /prompt_async, /abort). Same registry you
  // see." The endpoints were already exercised inside `retire()`; what was missing was the agent
  // shell and these definitions.
  //
  // WHY THE PLUGIN `tool` HOOK AND NOT `<configdir>/tool/*.ts`. Both mechanisms work and both are
  // scanned from the harness config directory. Only this one gets an HTTP client: a tool module
  // is imported with no arguments (`tool/registry.ts:178-192`) and its `execute` context is
  // `ToolContext` — sessionID, messageID, agent, directory, worktree, abort, metadata, ask, and
  // no client, no serverUrl, no app instance. Tools defined HERE are created inside the plugin
  // function and close over the server address, which is the whole difference between a control
  // agent and a set of stubs.
  //
  // TOKEN COST, and why these are scoped rather than global. Tool definitions are the largest
  // single block of standing context in this harness — 11 shipped tools measure 19,898 B. Five
  // more, however terse, are rent every session pays forever. So `opencode.jsonc` denies
  // `healbot_*` globally and `agent/control.md` allows it back: `Permission.fromConfig` turns a
  // string value into `{permission, pattern: "*", action}` (`permission/index.ts:190`), and
  // `Permission.disabled` (`:204-215`) removes a tool from the request payload exactly when the
  // LAST matching rule is `pattern: "*"` with `action: "deny"`. The agent's own permission is
  // merged last (`agent/agent.ts:293`), so its `allow` wins the `findLast` and the tools exist for
  // the control agent alone. This is the one shape of deny that actually removes a schema — a
  // scoped deny would leave the definitions in the prompt and only block execution.
  // -------------------------------------------------------------------------------------------

  const str = (description: string) => ({ type: "string", description })
  const strs = (description: string) => ({ type: "array", items: { type: "string" }, description })

  /**
   * Run `harness/memory.py` and return `{ code, out, err }`. The record travels on STDIN as one
   * JSON object, never on argv: a rationale is prose with newlines and quotes in it, and on argv
   * every shell in the path gets a vote on what it says.
   *
   * Never throws. A missing `python3`, an unwritable store and a refused record are all ordinary
   * here and each becomes a sentence the model reads — a capture tool that throws would fail a
   * turn over a lost note, which inverts the whole point of the store being advisory.
   */
  async function memory(args: string[], stdin?: unknown) {
    try {
      const proc = Bun.spawn(["python3", MEMORY_PY, ...args, "--dir", directory], {
        stdin: stdin === undefined ? "ignore" : new TextEncoder().encode(JSON.stringify(stdin)),
        stdout: "pipe",
        stderr: "pipe",
      })
      const [out, err] = await Promise.all([
        new Response(proc.stdout).text(),
        new Response(proc.stderr).text(),
      ])
      return { code: await proc.exited, out: out.trim(), err: err.trim() }
    } catch (error) {
      return { code: -1, out: "", err: error instanceof Error ? error.message : String(error) }
    }
  }

  /** Compact one-line state for a session, from data the control agent would otherwise have to
   * ask for in four separate calls. Occupancy is expressed against the gate because "how close is
   * this to being retired" is the question the agent is actually asking. */
  async function describe(session: SessionInfo, blocked: Set<string>) {
    const history = (await api<WithParts[]>("GET", `/session/${session.id}/message?limit=8`).catch(() => [])) ?? []
    let occupancy = 0
    let state = "idle"
    for (let i = history.length - 1; i >= 0; i--) {
      const info = history[i]?.info
      if (!info || info.role !== "assistant") continue
      const value = occupancyOf(info.tokens)
      if (value > 0 && occupancy === 0) occupancy = value
      if (occupancy > 0) {
        // "done" means the TURN ended, not a step — so a multi-step turn correctly reads
        // "working" all the way through. This was wrong for one commit, when the predicate was
        // per-step and every gap between tool calls reported "done" to the control agent.
        state = info.error ? "errored" : turnFinished(info) ? "done" : "working"
        break
      }
    }
    if (blocked.has(session.id)) state = "blocked"
    const share = occupancy > 0 ? ` ${Math.round((occupancy / RETIRE_AT) * 100)}% of gate` : ""
    const kind = session.parentID ? " subagent" : ""
    return `${session.id}  ${state}${share}${kind}  ${(session.title ?? "untitled").slice(0, 60)}`
  }

  /** Shared by abort and retire: refuse to act on the caller. An agent that aborts its own session
   * mid-tool-call kills the turn that issued the command, and one that retires itself spawns a
   * successor seeded with its own control instructions. Both are recoverable and neither is
   * something the model should be able to do by accident. */
  function selfCheck(sessionID: string, context: { sessionID?: string }, verb: string) {
    if (sessionID === context.sessionID) {
      return `Refused: ${sessionID} is your own session. You cannot ${verb} yourself.`
    }
    return undefined
  }

  const tools = {
    healbot_list: {
      description:
        "List every live session in this project with its state, context occupancy as a share of " +
        "the retirement gate, and whether it is blocked waiting on a human. Archived (retired) " +
        "sessions are omitted. Use this before acting on any session.",
      args: {},
      async execute() {
        const [sessions, permissions, questions] = await Promise.all([
          api<SessionInfo[]>("GET", "/session?scope=project").catch(() => []),
          api<Pending[]>("GET", "/permission").catch(() => [] as Pending[]),
          api<Pending[]>("GET", "/question").catch(() => [] as Pending[]),
        ])
        const blocked = new Set(
          [...(permissions ?? []), ...(questions ?? [])].map((item) => item?.sessionID).filter(Boolean) as string[],
        )
        // Ids are DESCENDING identifiers, so ascending sort is newest-first — the same order the
        // grid renders, so the agent and the operator are looking at the same list in the same
        // order. Archived filtered here because archiving hides a session from nothing
        // server-side.
        const live = (Array.isArray(sessions) ? sessions : [])
          .filter((session) => !session?.time?.archived)
          .sort((a, b) => a.id.localeCompare(b.id))
        if (live.length === 0) return "No live sessions."
        const lines = await Promise.all(live.map((session) => describe(session, blocked)))
        return `${live.length} live session(s), newest first:\n${lines.join("\n")}`
      },
    },

    healbot_spawn: {
      description:
        "Create a new session in this project and immediately give it work. Returns the new " +
        "session id. The prompt is its founding instruction, so state the objective fully — the " +
        "new session sees none of your context.",
      args: {
        prompt: str("The full instruction for the new session. Self-contained; it sees no context of yours."),
      },
      async execute(args: { prompt?: string }) {
        const text = (args?.prompt ?? "").trim()
        if (!text) return "Refused: prompt is empty. A session spawned with no work is a wasted context window."
        const created = await api<SessionInfo>("POST", `/session?directory=${encodeURIComponent(directory)}`, {})
        const id = created?.id
        if (!id) return "Failed: POST /session returned no id."
        // prompt_async, not the blocking prompt: it acks in ~10ms and the turn runs on. The
        // synchronous POST /session/{id}/message blocks until the whole turn completes, which
        // would stall the control agent's own turn behind the one it just started.
        await api("POST", `/session/${id}/prompt_async`, { parts: [{ type: "text", text }] })
        log(`control: spawned ${id}`)
        return `Spawned ${id} and seeded it. It is running now; use healbot_list to watch it.`
      },
    },

    healbot_prompt: {
      description:
        "Send a follow-up instruction to an EXISTING session and return immediately without " +
        "waiting for it to finish. Use healbot_list first to get the session id.",
      args: {
        sessionID: str("The target session id, as reported by healbot_list."),
        prompt: str("The instruction to send."),
      },
      async execute(args: { sessionID?: string; prompt?: string }, context: { sessionID?: string }) {
        const sessionID = (args?.sessionID ?? "").trim()
        const text = (args?.prompt ?? "").trim()
        if (!sessionID || !text) return "Refused: both sessionID and prompt are required."
        if (sessionID === context.sessionID) return "Refused: that is your own session. Just do the work."
        const session = await api<SessionInfo>("GET", `/session/${sessionID}`).catch(() => undefined)
        if (!session) return `Failed: no session ${sessionID}.`
        if (session.time?.archived) return `Refused: ${sessionID} is retired. Spawn a new one instead.`
        await api("POST", `/session/${sessionID}/prompt_async`, { parts: [{ type: "text", text }] })
        log(`control: prompted ${sessionID}`)
        return `Sent. ${sessionID} is working on it.`
      },
    },

    healbot_abort: {
      description:
        "Stop a session's current turn. The session stays alive and keeps its history — this " +
        "cancels the work in flight, it does not retire anything. Idempotent: aborting an idle " +
        "session does nothing.",
      args: { sessionID: str("The target session id, as reported by healbot_list.") },
      async execute(args: { sessionID?: string }, context: { sessionID?: string }) {
        const sessionID = (args?.sessionID ?? "").trim()
        if (!sessionID) return "Refused: sessionID is required."
        const refusal = selfCheck(sessionID, context, "abort")
        if (refusal) return refusal
        await api("POST", `/session/${sessionID}/abort`)
        log(`control: aborted ${sessionID}`)
        return `Aborted ${sessionID}.`
      },
    },

    healbot_retire: {
      description:
        "Retire a session and hand its work to a fresh one. Aborts it, collects its open todos " +
        "and changed files, seeds a successor with a passover document, then archives it. This " +
        "is what happens automatically at the context gate; use it to retire a session early. " +
        "If the session has no open todos it is archived with no successor.",
      args: { sessionID: str("The target session id, as reported by healbot_list.") },
      async execute(args: { sessionID?: string }, context: { sessionID?: string }) {
        const sessionID = (args?.sessionID ?? "").trim()
        if (!sessionID) return "Refused: sessionID is required."
        const refusal = selfCheck(sessionID, context, "retire")
        if (refusal) return refusal
        const session = await api<SessionInfo>("GET", `/session/${sessionID}`).catch(() => undefined)
        if (!session) return `Failed: no session ${sessionID}.`
        if (session.time?.archived) return `Nothing to do: ${sessionID} is already retired.`
        if (session.parentID) {
          return `Refused: ${sessionID} is a subagent. Retiring one orphans its parent's tool call; ` +
            `retire the parent instead.`
        }
        if (busy) return "Another retirement is in flight. Try again in a moment."
        // Mark it handled so the automatic gate does not retire it a second time if it is also
        // over the threshold.
        handled.add(sessionID)
        busy = true
        try {
          const outcome = await retire(session)
          return outcome
        } catch (error) {
          return `Retire failed for ${sessionID}: ${error instanceof Error ? error.message : String(error)}`
        } finally {
          busy = false
        }
      },
    },

    /**
     * Capture trigger (ii): the only cheap source of `alternatives[]` there will ever be.
     *
     * A commit message states the choice and usually the reasoning. It almost never states what
     * was rejected and why, because by the time it is written the rejected options are gone from
     * the author's head. Backfill can therefore recover choices and never alternatives, which is
     * exactly why every backfilled record is INFERRED and this one is not. This tool is the
     * moment the alternatives still exist.
     *
     * EVERY ARGUMENT IS REQUIRED, and that is not a style choice. The raw-JSON-Schema path marks
     * every property required (`tool/registry.ts:365`), so an "optional" field here would be a
     * lie the schema does not tell. The model must pass `[]` explicitly for the arrays.
     *
     * `execute` validates `classification` itself and does not rely on the schema to do it: the
     * legacy path performs NO server-side validation, so an enum in the schema is a hint to the
     * model and nothing more. The real refusal is `memory.py`'s, and this one only exists to give
     * the model a sentence it can act on without paying for a subprocess round trip first.
     */
    healbot_decide: {
      description:
        "Record WHY a decision went the way it did, so a later session does not re-litigate it. " +
        "Use it when you chose between real alternatives — an approach, a schema, a threshold — " +
        "not for facts, not for progress notes, and not for a choice with one obvious answer. " +
        "State what was REJECTED and why: that is the half nothing else in this system captures. " +
        "classification must be VERIFIED (read the code, have file:line), TESTED (ran it), " +
        "INFERRED (evidence with an unverified link) or SUSPECTED (a hypothesis). Pass [] for " +
        "an empty list — every argument is required.",
      args: {
        question: str("The question that was open, as a question. Not a summary of the answer."),
        choice: str("What was decided, in one or two sentences."),
        alternatives: strs(
          "Each rejected option as `option -- why it was rejected`. The reason is the point; an " +
            "option with no reason is what a commit message already carries. [] if there were none.",
        ),
        rationale: str("The reasoning behind the choice. Prose, as long as it needs to be."),
        evidence: strs("`file:line` pointers that support this. [] if none."),
        classification: str("VERIFIED | TESTED | INFERRED | SUSPECTED — see the description."),
      },
      async execute(
        args: {
          question?: string
          choice?: string
          alternatives?: string[]
          rationale?: string
          evidence?: string[]
          classification?: string
        },
        context: { sessionID?: string },
      ) {
        const classification = (args?.classification ?? "").trim().toUpperCase()
        if (!["VERIFIED", "TESTED", "INFERRED", "SUSPECTED"].includes(classification)) {
          return (
            `Refused: classification ${JSON.stringify(args?.classification ?? "")} is not one of ` +
            `VERIFIED, TESTED, INFERRED, SUSPECTED. An unclassified claim is how INFERRED gets ` +
            `read as VERIFIED later, which is the failure the whole field exists to stop.`
          )
        }
        const question = (args?.question ?? "").trim()
        const choice = (args?.choice ?? "").trim()
        if (!question || !choice) return "Refused: both question and choice are required."

        // `option -- why` split here rather than asking the model for nested objects: the legacy
        // schema path flattens anyway, and a one-line-per-alternative shape is what a model
        // actually produces reliably. An entry with no separator keeps its whole text as the
        // option and says so, which is visible in the record rather than silently dropped.
        const alternatives = (args?.alternatives ?? []).map((raw) => {
          const text = String(raw)
          const cut = text.indexOf("--")
          return cut < 0
            ? { option: text.trim(), why_rejected: "(no reason given)" }
            : { option: text.slice(0, cut).trim(), why_rejected: text.slice(cut + 2).trim() }
        })

        const result = await memory(["capture"], {
          question,
          choice,
          alternatives,
          rationale: (args?.rationale ?? "").trim(),
          evidence: (args?.evidence ?? []).map((e) => String(e).trim()).filter(Boolean),
          classification,
          captured_by: `opencode:${context?.sessionID ?? "unknown"}`,
        })
        if (result.code !== 0) {
          return `Could not record it: ${result.err || `memory.py exited ${result.code}`}. The ` +
            `decision still stands; only the record was lost.`
        }
        if (context?.sessionID) captured.add(context.sessionID)
        log(`recorded a decision for ${context?.sessionID ?? "unknown"}`)
        return `Recorded. ${result.out}`
      },
    },

    /**
     * Retrieval is PULL, and this is the whole retrieval surface.
     *
     * WHY PULL AND NOT PUSH. Tool definitions are the largest standing token cost in this
     * harness — 11 shipped tools measure 19,898 B — so a store that pushed its contents into
     * every prompt would spend the budget this harness exists to protect on records the session
     * never asked for. The one exception is the orientation block below, which is capped at
     * `MAX_DOCUMENT_TAIL` bytes and holds only settled heads.
     *
     * THERE IS NO PATH ARGUMENT, deliberately and permanently. The project is resolved from the
     * plugin's OWN directory, so neither the model nor any instruction reaching it through a
     * file, a web page or another session's output can name a different project's store. A
     * `project` argument would make cross-project reads one prompt injection away, and the whole
     * per-project isolation rule would then hold only as long as nobody asked it not to.
     */
    healbot_recall: {
      description:
        "Search this project's decision records for why something was decided the way it was, " +
        "and what was rejected. Use it before re-opening a settled question, before changing a " +
        "threshold or a schema someone chose deliberately, and when a comment or document says " +
        "a choice was made but not why. Searches questions, choices, reasoning and evidence. " +
        "Records are scoped to this project and cannot be read from another one.",
      args: {
        query: str("Words to search for. Pass an empty string to list every settled decision."),
        include_superseded: str(
          "\"yes\" to include decisions that were later reversed, with what reversed them — use " +
            "this when you want the history of a choice rather than its current state. " +
            "\"no\" for only what still stands.",
        ),
      },
      async execute(args: { query?: string; include_superseded?: string }) {
        const every = (args?.include_superseded ?? "").trim().toLowerCase().startsWith("y")
        const result = await memory(["recall", args?.query ?? "", ...(every ? ["--all"] : [])])
        if (result.code !== 0) {
          return `Could not read the decision records: ${result.err || `exited ${result.code}`}`
        }
        return result.out || "No decision records match that."
      },
    },
  }

  if (AUTO_RETIRE) {
    log(
      `headless retirement armed — gate ${RETIRE_AT.toLocaleString()} (per-turn, single gate), ` +
        `directory ${directory}`,
    )
  } else {
    log(`retirement gate DISABLED (HEALBOT_AUTO_RETIRE=0); control tools still available`)
  }

  // OUTSIDE the branch above, deliberately. Capture is armed whether or not the retirement gate
  // is, so the line that says so has to print in both states — otherwise the one operator most
  // likely to wonder whether capture is running (the one who just disabled the gate) is the one
  // who gets no answer.
  log(`decision capture armed — nudge at ${CAPTURE_AT.toLocaleString()} of ${RETIRE_AT.toLocaleString()}`)

  return {
    tool: tools,

    /**
     * The nudge's delivery, and it costs ZERO extra turns: it rides the system prompt the
     * session was going to send anyway.
     *
     * `!input.sessionID` IS THE LOAD-BEARING GUARD. There are two dispatch sites and only one of
     * them is a session. `session/llm/request.ts:68-72` passes `{ sessionID, model }` — that is
     * the real one. `agent/agent.ts:381` passes `{ model }` alone, with `system` holding
     * `PROMPT_GENERATE`, because it is generating an agent's description. Appending here without
     * the guard would push a nudge about decision records into a prompt whose entire job is
     * writing one sentence about an agent.
     *
     * `output.system` is an ARRAY and this appends to it. `request.ts:74-78` keeps element 0 as
     * the header and joins everything after it, so element 0 — the cacheable part — is untouched
     * by anything added here.
     */
    "experimental.chat.system.transform": async (
      input: { sessionID?: string; model: unknown },
      output: { system: string[] },
    ) => {
      const sessionID = input?.sessionID
      if (!sessionID) return

      // Orientation, once per session. `memory.py orient` renders it — not this file — so the
      // four selection rules (heads only, VERIFIED|TESTED only, deterministic sort, truncation
      // at a record boundary) have ONE implementation that a probe can assert, rather than one
      // here and another in the Claude-side hook that would quietly disagree.
      if (!orientOf.has(sessionID)) {
        const result = await memory(["orient"])
        orientOf.set(sessionID, result.code === 0 ? result.out : "")
      }
      const block = orientOf.get(sessionID)
      if (block) output.system.push(block)

      if (nudgePending.delete(sessionID)) {
        output.system.push(
          "You are about halfway through this session's context. If you have settled a question " +
            "in it where real alternatives were considered and rejected, record it now with " +
            "healbot_decide — the reasoning and the rejected options are lost when this session " +
            "retires, and they are what a later session needs. If nothing qualifies, say nothing " +
            "and carry on; do not invent a decision to have one to record.",
        )
      }
    },
    /**
     * Driven off `message.updated`, which is the only event that carries the assistant message's
     * own `tokens` — `properties` is `{ sessionID, info: Message }` and `info` is the WHOLE
     * message object, not just ids.
     *
     * The hook is fire-and-forget at the trigger site (`plugin/index.ts:255` calls it with
     * `void`), so nothing awaits this and a rejection here would be an unhandled rejection in the
     * server process. Every path inside is guarded.
     */
    event: async ({ event }: { event: PluginEvent }) => {
      try {
        // `session.updated` — the OPERATOR'S `x`, relayed. See `claimedRequest`. This is checked
        // before the AUTO_RETIRE gate on purpose: the kill switch disables the automatic gate, not
        // the operator's ability to retire a session by hand.
        if (event.type === "session.updated") {
          const info = event.properties?.["info"] as SessionInfo | undefined
          if (!info?.id) return
          if (!requestedAt(info)) return
          await considerRequest(info.id)
          return
        }

        // Capture trigger (iii), ABOVE the kill switch on purpose — the same reason the request
        // relay above it is. `HEALBOT_AUTO_RETIRE=0` disables the automatic RETIREMENT GATE and
        // nothing else; its documented contract is "the control tools stay". Below this line,
        // setting it would silently disable decision capture too, with no log line saying so,
        // and the operator would be measuring a memory system that had been switched off by a
        // flag about something else. Occupancy is recomputed here rather than reused because
        // there is nothing above to reuse.
        if (event.type === "message.updated") {
          const m = event.properties?.["info"] as MessageInfo | undefined
          const sid = m?.sessionID ?? (event.properties?.["sessionID"] as string | undefined)
          if (
            m?.role === "assistant" &&
            sid &&
            // `turnFinished` alone is not enough: it returns TRUE on an errored turn, and a
            // session whose turn just blew up has no decision to record and no attention to
            // spare for being asked. Both conjuncts.
            turnFinished(m) &&
            !m.error &&
            occupancyOf(m.tokens) >= CAPTURE_AT &&
            !nudged.has(sid) &&
            !captured.has(sid)
          ) {
            nudged.add(sid)
            nudgePending.add(sid)
            log(`capture nudge armed for ${sid} at ${occupancyOf(m.tokens).toLocaleString()}`)
          }
        }

        if (!AUTO_RETIRE) return
        if (event.type !== "message.updated") return
        const info = event.properties?.["info"] as MessageInfo | undefined
        if (!info || info.role !== "assistant") return
        const sessionID = info.sessionID ?? (event.properties?.["sessionID"] as string | undefined)
        if (!sessionID) return
        const occupancy = occupancyOf(info.tokens)
        if (occupancy < RETIRE_AT) return
        await consider(sessionID, occupancy, turnFinished(info))
      } catch (error) {
        log(`event handler error: ${error instanceof Error ? error.message : String(error)}`)
      }
    },
  }
}
