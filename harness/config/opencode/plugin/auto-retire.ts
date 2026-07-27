/**
 * HEADLESS automatic retirement. The lifecycle guard, moved off the screen.
 *
 * WHY THIS FILE EXISTS, and why it is a SERVER plugin rather than a TUI one.
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
 * private for that reason, not for encapsulation.
 *
 * KILL SWITCH: `HEALBOT_AUTO_RETIRE=0` restores operator-initiated retirement (`x` in the grid).
 */

// ---------------------------------------------------------------------------------------------
// Thresholds. These MUST agree with `healbot.tsx`'s copies — see the drift note at the bottom.
// ---------------------------------------------------------------------------------------------

/**
 * Context occupancy at which a session should be retired, in tokens. The SOFT gate: cross it and
 * the turn in flight is allowed to finish, then the handoff runs.
 *
 * **The ceiling is ~360K, NOT the 922,000 `limit.input` the model registry advertises.** MEASURED
 * at the shipped default: a session driven up took its last successful turn at occupancy 359,829
 * and then failed 25 consecutive turns with the provider's `ContextOverflowError`. The harness
 * sets `compaction.auto: false`, which makes `overflow.ts:28` disable opencode's own overflow
 * check entirely, so nothing upstream catches it — the provider does, and by then the turn is
 * lost. Nothing is truncated on the way up either: there is no history slicing on the v1 prompt
 * path and `compaction.prune` is unset, so opencode sends the ENTIRE history every turn until
 * the provider refuses it. It is a cliff, not a slope.
 *
 * Floor, measured: a freshly spawned and seeded session reads ~4.8K on its first turn, almost all
 * `cache.read`. A threshold at or below that fires on turn one and proves nothing.
 */
const RETIRE_AT = Math.max(1, Number(process.env["HEALBOT_RETIRE_AT"]) || 256_000)

/**
 * The HARD gate. Cross it *during* a turn and the session is retired immediately, aborting it.
 *
 * Two gates are needed because "let the agent finish what it is doing" has an overshoot cost, and
 * the cost is much larger than it looks. MEASURED on one ordinary turn: occupancy went
 * 5,216 -> 70,898 on a single tool result, and that turn finished at 175,090. One turn added
 * ~170K by itself. A session sitting just under the 256,000 soft gate that starts one more
 * read-heavy turn finishes near 426,000 — past the ceiling, dead, having obeyed the finish-first
 * rule the whole way.
 *
 * The abort is not weighed against finishing. It is weighed against `ContextOverflowError`, which
 * discards the same work, spends the tokens first, and produces no handoff.
 */
const RETIRE_HARD = Math.max(RETIRE_AT, Number(process.env["HEALBOT_RETIRE_HARD"]) || 330_000)

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
 * Has the turn ended?
 *
 * An assistant message row exists ~20 ms after a prompt is accepted and is EMPTY until the turn
 * runs — the same race that produced a false `prompt_async` defect report in the Phase 4 audit.
 * So "an assistant message exists" means nothing; the completion signal is the message's own
 * `time.completed` / `finish`.
 *
 * NOTE there is more than one projection site for that. `processor.ts:595-596` sets
 * `time.completed` and republishes in `SessionProcessor.cleanup`, which `Effect.ensuring` at
 * `:676` guarantees runs — but `prompt.ts:364-365`, `:396-397`, `:534-536` and `:1209-1210` each
 * do the same on the tool-driven and interrupted paths. Reading the FIELD rather than watching
 * one site is what makes this correct across all five.
 */
function finished(info: MessageInfo): boolean {
  return Boolean(info.time?.completed || info.finish || info.error)
}

// ---------------------------------------------------------------------------------------------
// The handoff document
// ---------------------------------------------------------------------------------------------

/**
 * The passover document handed to a successor session.
 *
 * This is a VERBATIM twin of `handoffDocument` in `healbot.tsx`. The two must stay identical or a
 * successor gets a different briefing depending on whether a human pressed `x` or the gate fired
 * — and "the same feature behaves differently depending on who triggered it" is precisely the
 * class of silent divergence this project keeps catching in itself.
 *
 * `.carryover/verified/probe_twin.py` asserts the two copies match, for free and with a mutation
 * check. If you edit this function, edit the other one; the probe will tell you if you did not.
 *
 * DEVIATION FROM PLAN.md:371, inherited from the grid: the plan names
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

export const AutoRetire = async (input: PluginInput) => {
  if (!AUTO_RETIRE) return {}

  const directory = input.directory
  const base = input.serverUrl.toString().replace(/\/$/, "")
  const api = makeApi(base, directory)
  const log = (message: string) => console.log(`[healbot/auto-retire] ${message}`)

  /**
   * Sessions this process has already acted on, so a retire that FAILS is not retried on every
   * subsequent event. Without it a session that is over the gate and erroring emits
   * `message.updated` repeatedly and would spawn a successor per event.
   */
  const handled = new Set<string>()

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
    // Unconditional and idempotent: aborting an idle session is a no-op. On the soft-gate path it
    // IS a no-op, since we only get here once the turn finished; its purpose is the race, where a
    // turn starts between that check and this call. A turn beginning after the gate was met is
    // exactly what "no turn consumption after the gate" forbids.
    await api("POST", `/session/${sessionID}/abort`)

    const todos = (await api<Todo[]>("GET", `/session/${sessionID}/todo`).catch(() => [])) ?? []
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

    // Newest-first, first assistant message with non-empty text. Skips the in-flight empty row a
    // hard-gate abort leaves behind.
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
      log(`retired ${label} — nothing outstanding`)
      return
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

    // Re-read immediately before the irreversible step. The grid's manual `x` runs the same flow
    // in a different process and neither can see the other's in-flight state; this narrows the
    // double-retire window to the width of one request. It does NOT close it — see
    // `docs/HEADLESS.md`.
    const current = await api<SessionInfo>("GET", `/session/${sessionID}`).catch(() => undefined)
    if (current?.time?.archived) {
      log(`${label} was archived by another actor mid-handoff; successor ${successorID} is seeded and live`)
      return
    }

    await api("PATCH", `/session/${sessionID}`, { time: { archived: Date.now() } })
    log(
      `retired ${label} at the gate — handed off ${open.length} open item${open.length === 1 ? "" : "s"}` +
        `, ${files.length} file${files.length === 1 ? "" : "s"} -> ${successorID}`,
    )
  }

  async function consider(sessionID: string, occupancy: number, turnOver: boolean) {
    if (busy) return
    if (handled.has(sessionID)) return

    const hard = occupancy >= RETIRE_HARD
    // Let it finish — UNLESS it has also crossed the hard gate. Cutting a turn off throws away
    // work the successor has to rediscover, which is the looping-discovery failure this handoff
    // design exists to avoid, so the soft gate always waits.
    if (!turnOver && !hard) return

    const session = await api<SessionInfo>("GET", `/session/${sessionID}`).catch(() => undefined)
    if (!session) return
    // Already retired. Archiving hides a session from NOTHING server-side (`ListInput` has no
    // `archived` field and `listByProject` has no `time_archived` predicate), so this has to be
    // checked rather than assumed.
    if (session.time?.archived) return
    // Never a subagent. A subagent is a tool call inside its parent's turn; archiving one mid-turn
    // orphans the parent's `task` call, and its window is the parent's problem to bound.
    if (session.parentID) return
    if (await isBlocked(sessionID)) return

    handled.add(sessionID)
    busy = true
    try {
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

  log(
    `headless retirement armed — soft ${RETIRE_AT.toLocaleString()}, hard ${RETIRE_HARD.toLocaleString()}, ` +
      `directory ${directory}`,
  )

  return {
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
        if (event.type !== "message.updated") return
        const info = event.properties?.["info"] as MessageInfo | undefined
        if (!info || info.role !== "assistant") return
        const sessionID = info.sessionID ?? (event.properties?.["sessionID"] as string | undefined)
        if (!sessionID) return
        const occupancy = occupancyOf(info.tokens)
        if (occupancy < RETIRE_AT) return
        await consider(sessionID, occupancy, finished(info))
      } catch (error) {
        log(`event handler error: ${error instanceof Error ? error.message : String(error)}`)
      }
    },
  }
}
