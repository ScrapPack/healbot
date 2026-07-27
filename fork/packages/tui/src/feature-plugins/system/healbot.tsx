/** @jsxImportSource @opentui/solid */
import type { TuiPlugin, TuiPluginApi, TuiRouteCurrent } from "@opencode-ai/plugin/tui"
import type { PermissionRequest, QuestionRequest } from "@opencode-ai/sdk/v2"
import { useTerminalDimensions } from "@opentui/solid"
import { createEffect, createMemo, createSignal, For, onCleanup, onMount, Show } from "solid-js"
import { useSync } from "../../context/sync"
import { OPENCODE_BASE_MODE, useBindings } from "../../keymap"
import { PermissionPrompt } from "../../routes/session/permission"
import { QuestionPrompt } from "../../routes/session/question"

// The Healbot control terminal: every session in the instance as one grid of bordered
// cells, border colour carrying live state. Architecture settled by healbot-spike.tsx
// (PROBE F7) — a builtin plugin route inside this fork's TUI, not a separate app.

const ROUTE = "healbot"
const MIN_CELL_WIDTH = 30
const CELL_HEIGHT = 6

/**
 * Context occupancy at which a session should be retired, in tokens. Env-overridable so the
 * exit gate can actually be exercised: `PLAN.md:379-381` requires a session "driven past the
 * retirement threshold", and `REVIEW.md` §4.3 records that clause as unadjudicable precisely
 * because no threshold was configurable anywhere in the deliverable.
 *
 * Default **256,000**, lowered from 350,000 on the owner's decision after the ceiling below was
 * measured. 256K leaves ~104K of headroom under that ceiling — roughly the 30% reserve the
 * threshold is meant to provide, and enough that no single tool result can cross it.
 *
 * **The ceiling is ~360K, NOT the 922,000 `limit.input` the model registry advertises.** This
 * file used to claim "350K leaves ~570K of headroom". MEASURED, and it is false: a session
 * driven up at the shipped default took its last successful turn at occupancy **359,829** and
 * then failed **25 consecutive turns** with the provider's `ContextOverflowError` — "Your input
 * exceeds the context window of this model". So the real margin between this threshold and a
 * dead session is about **10K, under 3%**, not 570K.
 *
 * That margin is not enough. A single large tool result is ~10K, so one read can carry a
 * session from "should be retired" to "cannot run another turn". The harness sets
 * `compaction.auto: false`, which makes `overflow.ts:28` disable opencode's own overflow check
 * entirely, so nothing upstream catches this first — the provider does, and by then the turn is
 * lost. **Retirement is the only guard, and at 350K it fired too late to be one.**
 *
 * NOTE what is NOT happening here: nothing is truncated or dropped. There is no history
 * slicing on the v1 prompt path, `compaction.auto:false` disables compaction, and
 * `compaction.prune` is unset so `compaction.ts:245` returns early. opencode sends the ENTIRE
 * history every turn until the provider refuses it. So context is not "lost" gradually as the
 * window fills — the session works perfectly and then hits a wall. That is precisely why the
 * threshold needs real headroom rather than a small margin.
 *
 * Floor, measured: a freshly spawned and seeded session reads ~4.8K on its very first turn,
 * almost all of it `cache.read` — the standing-context prefix. A threshold at or below that
 * fires on turn one and proves nothing. So the usable band is roughly 5K–360K.
 */
const RETIRE_AT = Math.max(1, Number(process.env["HEALBOT_RETIRE_AT"]) || 256_000)

/**
 * AUTOMATIC retirement does not live in this file any more. It lives in the server plugin at
 * `harness/config/opencode/plugin/auto-retire.ts`, and `RETIRE_AT` above is now used HERE only
 * to render the `RETIRE` border, the `N to retire` header count and the share-of-threshold
 * figure on each cell. `x` — manual retirement — is still `retire()` below.
 *
 * It moved because a `createEffect` in this component could only ever run while the grid was
 * mounted. Two consequences, and the second is the one that mattered:
 *
 *   1. Navigating into a session with `enter` unmounts this route (`app.tsx:1079-1085` computes
 *      the plugin route in a `createMemo` that returns `undefined` as soon as
 *      `route.data.type !== "plugin"`), so retirement was dead while the operator was reading a
 *      session — the exact moment a long session is most likely to cross the gate.
 *   2. A fleet left running with NO client attached retired nothing. `harness/fleet.sh` exists
 *      so the server outlives the terminal, so the guard was absent in the topology the
 *      architecture is built around.
 *
 * Moving it to TUI *plugin* scope would have fixed (1) and not (2) — a TUI plugin still needs a
 * TUI — and would have been unsound anyway: plugin scope has no Solid owner (`getOwner()` is
 * `null` there, TESTED), so the effect would never be disposed and a bare `onCleanup` is a
 * silent no-op. `TuiPluginModule` and `PluginModule` are mutually exclusive by type
 * (`tui?: never` / `server?: never`), so this file could not have hosted both halves regardless.
 *
 * **Exactly one process may own the gate.** If this effect still lived here, an operator pressing
 * `x` and the server plugin firing on the same session would each spawn a successor. That is why
 * it is deleted rather than kept as a fallback. Consequence to know: run the fork WITHOUT the
 * harness config and nothing retires automatically — the border still goes purple and `x` still
 * works. See `docs/HEADLESS.md`.
 */

/**
 * How many user messages a handoff fans out over to collect changed files.
 *
 * Applied to the SERVER's full history, not to the store's window, and not biased toward
 * recent. Both of those were wrong and for the same reason the objective was: TESTED at the
 * shipped 350K threshold, a 103-message session produced an EMPTY file list and no
 * "## Files already changed" section at all, because the last 20 user messages were all pure
 * reads and the one file the session actually created was made on turn one — outside the
 * 20-message window and outside the store's 100-message cap besides.
 *
 * Scaffolding happens early. A handoff that only looks at recent turns systematically misses
 * exactly the files worth handing over.
 */
const DIFF_FANOUT = 60

/**
 * Border state, highest precedence first. RED/YELLOW outrank everything because they are the
 * states that need a human *now*: the session is blocked until someone answers. ERROR sits
 * directly under them for the same reason — the turn is over and it did not succeed, and the
 * one thing a control terminal must never do is let that read as completion. RETIRE outranks
 * activity because a session over the threshold keeps spending toward a hard error while it
 * works, and the cell still carries its occupancy so "working" is not lost.
 */
type CellState =
  | "blocked-permission"
  | "blocked-question"
  | "errored"
  | "needs-retire"
  | "retrying"
  | "busy"
  | "done"
  | "idle"

/**
 * Pending requests recovered by the cold-start reconcile, grouped by session — see
 * `reconcile()`. These are the full request bodies, not just the ids that were enough to
 * colour a border: answering a block from the grid needs the request itself (its prompt and
 * its options), and for a block that predates this client the live store holds nothing.
 */
type Cold = { permission: Map<string, PermissionRequest[]>; question: Map<string, QuestionRequest[]> }

/**
 * Sessions whose last turn ended in error, mapped to a short reason for the cell.
 *
 * This has to be tracked out of band because **the store cannot express it**. Every v1 error
 * path ends by setting status idle (`session/processor.ts:611` for the context-overflow case,
 * `:623` for everything else), and `session/status.ts:41` publishes that `{type:"idle"}` before
 * `:44` deletes the key — so `sync.tsx:310` records it and a dead session becomes
 * indistinguishable from one that finished its task. `session-status-event.ts` has no `error`
 * member at all; the only carrier is the separate `session.error` event.
 *
 * Without this map the grid paints a session that died on an expired credential, a crashed tool
 * or a hard context overflow in `theme.success` and labels it `done`. On a terminal whose entire
 * premise is that border colour carries truth, that is the worst available failure: silent, and
 * biased toward "everything finished". PLAN.md:357 asked for the state; HARNESS.md's
 * load-bearing facts and `TUI.MAP.md` G5 both say the grid must track it itself.
 */
type Errors = Map<string, string>

/**
 * A grid cell's session, from either roster source. `time.archived` rides along because
 * retirement has to be filtered by the grid itself — `PATCH time.archived` hides a session
 * from **nothing** server-side (`ListInput` has no `archived` field, `listByProject` has no
 * `time_archived` predicate, the v2 list does not filter, and `grep -rn archived
 * packages/tui/src` finds no other consumer). A retired session keeps coming back from
 * `GET /session` forever unless the caller drops it.
 */
type Roster = {
  id: string
  title?: string
  parentID?: string
  directory?: string
  time?: { archived?: number }
}

/**
 * The slice of the SDK client this grid needs that `TuiPluginApi["client"]` does not surface
 * with types. Declared once and narrowly, so the file carries a single unsafe assertion
 * instead of one per call site. Each response is the generated client's usual
 * `{ data }` envelope, which some transports flatten — hence the unwrapping at the use sites.
 */
type Envelope<T> = { data?: T; error?: unknown } | undefined

type GridClient = {
  permission: { list(): Promise<unknown> }
  question: { list(): Promise<unknown> }
  session: {
    todo(input: { sessionID: string }): Promise<Envelope<{ content: string; status: string }[]>>
    diff(input: { sessionID: string; messageID: string }): Promise<Envelope<{ file?: string; path?: string }[]>>
    /**
     * Omitting `limit` is load-bearing, not laziness. `handlers/session.ts:119-121` branches on
     * it: with a limit you get `MessageV2.page`, which is `orderBy(desc(...))` — the NEWEST N.
     * Without one you get `session.messages`, which pages the whole history backwards and
     * `session.ts:852` `.reverse()`s it, so `[0]` is genuinely the session's first message.
     */
    messages(input: {
      sessionID: string
    }): Promise<
      Envelope<
        {
          info?: { role?: string; id?: string }
          role?: string
          id?: string
          parts?: { type: string; text?: string }[]
        }[]
      >
    >
    create(input: { directory?: string }): Promise<{ data?: { id?: string }; id?: string; error?: unknown } | undefined>
    promptAsync(input: { sessionID: string; parts: { type: "text"; text: string }[] }): Promise<Envelope<unknown>>
    abort(input: { sessionID: string }): Promise<Envelope<unknown>>
    update(input: { sessionID: string; time?: { archived?: number } }): Promise<Envelope<unknown>>
  }
}

/**
 * Passes an SDK response through, or throws with a usable message if it carries an error.
 *
 * The generated client does NOT reject on failure — it is built without `throwOnError`
 * (`context/sdk.tsx:25-31`), so `client.gen.ts:222-233` resolves with `{data: undefined, error}`
 * and an unchecked `await` looks exactly like success. Every mutating call in `retire()` runs
 * through this, because the alternative is a handoff that reports `handed off N open items`
 * after archiving a session it never actually replaced.
 */
function ok<R extends { error?: unknown } | undefined>(result: R, what: string): R {
  const error = result?.error
  if (!error) return result
  const detail =
    typeof error === "object" && error !== null && "message" in error && typeof error.message === "string"
      ? error.message
      : typeof error === "object" && error !== null && "name" in error && typeof error.name === "string"
        ? error.name
        : "request failed"
  throw new Error(`${what}: ${detail}`)
}

const gridClient = (api: TuiPluginApi) => api.client as unknown as GridClient

/**
 * The passover document handed to a successor session.
 *
 * DEVIATION FROM PLAN.md:371, which specifies `POST /session/{id}/summarize` as the source.
 *
 * That route is not the git-diff summariser its name suggests — there are TWO `summarize`s and
 * the plan reads as though there is one. `handlers/session.ts:273-283` routes
 * `POST /session/{id}/summarize` into `compactSvc.create(...)`: it is COMPACTION, an LLM turn,
 * and it is what `HARNESS.md`'s "summarize mutates in place and adds tokens" describes. The
 * git-diff one is `SessionSummary.summarize` (`summary.ts:102-127`, no LLM), which already runs
 * automatically on the prompt path (`prompt.ts:1253`) and writes its result onto the *user*
 * message. So the diff data the plan wanted is available without compacting anything.
 *
 * Two further reasons to skip the compaction route:
 *
 *  1. The project's stated position (`opencode.jsonc`, REVIEW) is that handing a fresh session
 *     a passover prompt beats compacting, *because compaction loses specificity*. The sources
 *     below lose none — they are the literal todos and the literal file list.
 *  2. It costs an extra model turn, a wait and a failure mode, for material already available
 *     synchronously and exactly.
 *
 * What it does NOT carry is narrative — what was tried and abandoned. The last assistant
 * message is included as a partial substitute. If that proves too thin in practice, adding a
 * `summarize` call back is a two-line change; it is deliberately not the default.
 */
function handoffDocument(input: {
  title: string
  objective?: string
  open: { content: string }[]
  files: string[]
  lastMessage?: string
}) {
  const lines = [
    "You are taking over a session that was retired because its context window was too full.",
    "Continue its work now. Do not start over, and do not simply report status — the",
    "outstanding items below are what is left to DO.",
    "",
    // Labelled as the ORIGINAL INSTRUCTION rather than "objective", and explicitly demoted
    // below the outstanding list. TESTED and it matters: handed a verbatim first message that
    // happened to contain step sequencing ("do only the first, leave the rest pending"), the
    // successor obeyed that stale instruction and replied "No further work performed". The
    // instruction is the best statement of intent available, but it is a historical record —
    // the todo list is the live one.
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
    lines.push("", "## Where it left off", input.lastMessage.trim().slice(0, 2000))
  }
  return lines.join("\n")
}

// Store first (live SSE), then the cold-start reconcile. The store's `permission` /
// `question` maps are populated ONLY by events observed in this process, so a client that
// attaches to an already-running server sees none of the blocks that predate it — those
// cells render dim, which is precisely the state a control terminal must not miss.
//
// Scope of the reconcile, measured: pending requests live in `InstanceState`
// (`permission/index.ts:24,50` — an in-memory Map; the `permission` table has 0 rows), so
// they die WITH the server. When the TUI hosts its own server, as it does today, a restart
// loses the request on both sides and nothing can recover it — VERIFIED: sessions left
// blocked on a permission and on a question both came back reading `idle`. The reconcile
// pays off under the intended architecture instead — one long-lived `opencode serve` with
// the control terminal as a client (PLAN.md:335) — where the server outlives the TUI.

function pendingPermission(sync: ReturnType<typeof useSync>, cold: Cold, sessionID: string): PermissionRequest[] {
  const live = sync.data.permission[sessionID] ?? []
  return live.length > 0 ? live : (cold.permission.get(sessionID) ?? [])
}

function pendingQuestion(sync: ReturnType<typeof useSync>, cold: Cold, sessionID: string): QuestionRequest[] {
  const live = sync.data.question[sessionID] ?? []
  return live.length > 0 ? live : (cold.question.get(sessionID) ?? [])
}

/** Copy of `map` with one request removed, dropping the session key when it empties. */
function without<T extends { id: string }>(map: Map<string, T[]>, sessionID: string, requestID: string) {
  const bucket = map.get(sessionID)
  if (!bucket) return map
  const next = bucket.filter((item) => item.id !== requestID)
  const out = new Map(map)
  if (next.length > 0) out.set(sessionID, next)
  else out.delete(sessionID)
  return out
}

/**
 * Live context OCCUPANCY for a session, in tokens — how full the window is right now.
 *
 * Deliberately not `session.tokens`: that is lifetime spend and answers a different question.
 * The reference 101-turn session shows 652K input against 8.7M `cache.read`, which says nothing
 * about how full its window is. The quantity a retirement trigger needs is the one
 * `isOverflow` itself reads (`session/overflow.ts:21-33`) — the assistant message's own
 * `tokens`, delivered on every `message.updated` — with **`cache.read` included**, because the
 * cached prompt prefix is part of the window.
 *
 * Scans backwards for the most recent populated reading rather than taking the last message.
 * An assistant row is created ~20ms before its turn actually runs and carries all-zero tokens
 * until then (the same race that produced a false `prompt_async` defect report), so reading
 * `messages.at(-1)` blindly reports 0 for every session that is mid-turn.
 */
function occupancyOf(sync: ReturnType<typeof useSync>, sessionID: string): number {
  const messages = sync.data.message[sessionID] ?? []
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i]
    if (message.role !== "assistant") continue
    const tokens = message.tokens
    if (!tokens) continue
    const total = tokens.total || tokens.input + tokens.output + tokens.cache.read + tokens.cache.write
    if (total > 0) return total
  }
  return 0
}

/**
 * Short, human reason for an error cell. Mirrors `notifications.ts:20-27`, which is not
 * exported. `MessageAbortedError` is called out separately because an abort is a deliberate act
 * — including the one `retire()` performs on a busy predecessor — and reading it as a failure
 * would train the operator to ignore the state.
 */
function errorReason(error: { name?: string; data?: unknown } | undefined): string {
  if (error?.name === "MessageAbortedError") return "aborted"
  const data = error?.data
  if (data && typeof data === "object" && "message" in data && (data as { message?: unknown }).message === "SSE read timed out") {
    return "model stopped responding"
  }
  // The one an operator of THIS terminal will actually meet, and the raw class name is both
  // the longest string here and the least useful phrasing. At 20 characters it also overflows
  // the cell's state line and collapses the separators around it — TESTED, the line rendered as
  // `ERROR· ContextOverflowError· retire`. "context full" says the same thing in 12 and names
  // the condition retirement exists to prevent.
  if (error?.name === "ContextOverflowError") return "context full"
  // Bounded for the same reason: an unknown error class must not push `· retire` off the line.
  return error?.name ? truncate(error.name, 16) : "error"
}

/**
 * The error state DERIVED FROM STORED MESSAGES, not from having witnessed `session.error`.
 *
 * The event subscription alone is not enough and the 350K run proved it the expensive way: a
 * session that had failed **25 consecutive turns** with `ContextOverflowError` rendered a
 * cheerful `RETIRE`, because every one of those failures happened before the grid route was
 * mounted and the subscription lives inside the component. That is the same cold-start hole
 * `reconcile()` exists to plug for permissions and questions — a control terminal cannot only
 * know what happened while it was looking.
 *
 * Scanning BACKWARDS for the most recent assistant message also gives the clear-on-recovery
 * behaviour for free: if the latest turn succeeded, this returns undefined and the cell leaves
 * the error state with no event required.
 */
function storedErrorOf(sync: ReturnType<typeof useSync>, sessionID: string): string | undefined {
  const messages = sync.data.message[sessionID] ?? []
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i]
    if (message.role !== "assistant") continue
    // An in-flight assistant row exists ~20ms before it fills; it is neither finished nor
    // failed, so it must not be read as either. Same race `occupancyOf` guards against.
    if (!message.time?.completed && !message.finish && !message.error) continue
    if (message.error) return errorReason(message.error as { name?: string; data?: unknown })
    if (message.finish === "error") return "error"
    return undefined
  }
  return undefined
}

/** Live event first (it arrives with a reason immediately), stored state as the durable floor. */
function errorOf(sync: ReturnType<typeof useSync>, errors: Errors, sessionID: string): string | undefined {
  return errors.get(sessionID) ?? storedErrorOf(sync, sessionID)
}

function stateOf(sync: ReturnType<typeof useSync>, cold: Cold, errors: Errors, sessionID: string): CellState {
  if (pendingPermission(sync, cold, sessionID).length > 0) return "blocked-permission"
  if (pendingQuestion(sync, cold, sessionID).length > 0) return "blocked-question"
  // Above RETIRE, because a session that died is not a session that needs retiring — retiring a
  // dead session hands its successor a document built from a turn that failed. The header's
  // `to retire` count is computed off occupancy rather than off this function (see `retirable`),
  // so nothing is lost by ranking the error first.
  if (errorOf(sync, errors, sessionID)) return "errored"
  if (occupancyOf(sync, sessionID) >= RETIRE_AT) return "needs-retire"
  const status = sync.data.session_status[sessionID]
  // Absent is meaningful: the server deletes the key on idle (session/status.ts:42-45), so
  // the HTTP seed only ever carries busy/retry. Key present + idle ⇒ it ran and finished in
  // THIS process. Absent ⇒ never started here — dim, not green. See CONTEXT.MAP.md G3.
  if (!status) return "idle"
  // Split out of `busy`, per PLAN.md:357's "red flash | session.status {type:"retry"}". A retry
  // is not progress: the provider rejected the request and opencode is backing off. It looks
  // exactly like work from the outside, which is precisely why it earns its own colour.
  if (status.type === "retry") return "retrying"
  if (status.type === "busy") return "busy"
  return "done"
}

function borderColor(api: TuiPluginApi, state: CellState, selected: boolean) {
  const theme = api.theme.current
  switch (state) {
    case "blocked-permission":
      return theme.error
    case "blocked-question":
      return theme.warning
    // Red, like a permission, and deliberately so: PLAN.md:357 assigns red to both. The label
    // is what separates them, which is the same contract every other state in this grid keeps.
    case "errored":
    case "retrying":
      return theme.error
    case "needs-retire":
      // PLAN.md reserved purple for `session.next.compaction.started`, which REVIEW R3 proved
      // cannot fire on the v1 path under any flag — so the colour is free, and retirement is
      // what compaction was going to signal anyway.
      return theme.secondary
    case "busy":
      return theme.accent
    case "done":
      return theme.success
    default:
      return selected ? theme.borderActive : theme.border
  }
}

function label(state: CellState) {
  switch (state) {
    case "blocked-permission":
      return "PERMISSION"
    case "blocked-question":
      return "QUESTION"
    case "errored":
      return "ERROR"
    case "retrying":
      return "RETRY"
    case "needs-retire":
      return "RETIRE"
    case "busy":
      return "working"
    case "done":
      return "done"
    default:
      return "idle"
  }
}

function truncate(value: string, width: number) {
  if (width <= 1) return ""
  return value.length <= width ? value : value.slice(0, Math.max(0, width - 1)) + "…"
}

function Cell(props: {
  api: TuiPluginApi
  sessionID: string
  title: string
  parentID?: string
  selected: boolean
  width: number
  cold: Cold
  errors: Errors
}) {
  const sync = useSync()
  const theme = () => props.api.theme.current

  // Cold-cell hydration. store.message[id] is empty for any session this process has not
  // opened (CONTEXT.MAP.md GAP-2); sync() is idempotent and self-deduping, and the
  // emptiness guard skips the call entirely for cells already carrying messages.
  // Lifted from routes/session/index.tsx:2213-2222.
  onMount(() => {
    if (!sync.data.message[props.sessionID]?.length) void sync.session.sync(props.sessionID)
  })

  const state = createMemo(() => stateOf(sync, props.cold, props.errors, props.sessionID))
  const todos = createMemo(() => (sync.data.todo[props.sessionID] ?? []).filter((item) => item.status !== "completed"))
  const last = createMemo(() => {
    const messages = sync.data.message[props.sessionID] ?? []
    return messages[messages.length - 1]
  })
  // Occupancy as a share of the retirement threshold, because "how close am I to being
  // retired" is the question the operator is actually asking. Kept on the meta line rather
  // than the state line so that a cell whose border has gone RETIRE still shows what it is
  // doing — RETIRE outranks `working`, and without this the activity would just vanish.
  const occupancy = createMemo(() => occupancyOf(sync, props.sessionID))
  const share = createMemo(() => (occupancy() > 0 ? `${Math.round((occupancy() / RETIRE_AT) * 100)}%` : undefined))

  return (
    <box
      border
      borderColor={borderColor(props.api, state(), props.selected)}
      flexDirection="column"
      width={props.width}
      height={CELL_HEIGHT}
      paddingLeft={1}
      paddingRight={1}
    >
      <box flexDirection="row">
        <text fg={props.selected ? theme().text : theme().textMuted}>{props.selected ? "▸ " : "  "}</text>
        <text fg={theme().text}>{truncate(props.title, props.width - 6)}</text>
      </box>
      <box flexDirection="row">
        <text fg={borderColor(props.api, state(), props.selected)}>{label(state())}</text>
        <Show when={state() === "errored"}>
          <text fg={theme().textMuted}>{" · "}{errorOf(sync, props.errors, props.sessionID)}</text>
        </Show>
        {/*
          An errored session that is ALSO over the threshold still needs retiring once looked at,
          and ERROR outranks RETIRE — so say both rather than let the precedence swallow one.
          Same bargain the `· working` suffix below makes for RETIRE over `busy`.
        */}
        <Show when={state() === "errored" && occupancy() >= RETIRE_AT}>
          <text fg={theme().secondary}>{" · retire"}</text>
        </Show>
        <Show when={state() === "needs-retire" && sync.data.session_status[props.sessionID]?.type === "busy"}>
          <text fg={theme().accent}>{" · working"}</text>
        </Show>
        <Show when={props.parentID}>
          <text fg={theme().textMuted}> · subagent</text>
        </Show>
      </box>
      <text fg={theme().textMuted}>
        {truncate(
          [
            todos().length > 0 ? `${todos().length} todo` : undefined,
            last() ? `${(sync.data.message[props.sessionID] ?? []).length} msg` : "no history",
            share(),
          ]
            .filter(Boolean)
            .join(" · "),
          props.width - 4,
        )}
      </text>
    </box>
  )
}

function Healbot(props: { api: TuiPluginApi; selected: () => number; setSelected: (n: number) => void }) {
  const sync = useSync()
  const dimensions = useTerminalDimensions()
  const theme = () => props.api.theme.current

  // The roster is fetched project-scoped rather than read off `sync.data.session`.
  // That store is populated by `listSessions()` (sync.tsx:164-168), which applies
  // `sessionListQuery()`'s *current-subdirectory* filter — correct for the session
  // switcher, wrong for a control terminal that is supposed to show every session in
  // the project. CONTEXT.MAP.md G6 calls this out and names `client.session.list()` as
  // the bypass.
  //
  // Per-cell state still comes from the store: `session_status`, `permission`,
  // `question`, `todo` and `message` are keyed by sessionID and fed by the *global* SSE
  // feed, which is not directory-scoped (sdk.tsx:82-117), so cells stay live and
  // reactive regardless of where the session lives.
  // `directory` rides along because the reply endpoints are directory-scoped: the session
  // route sources it from `sync.session.get(id)?.directory` (routes/session/index.tsx:1286),
  // and the grid deliberately shows sessions that store cannot see.
  const [roster, setRoster] = createSignal<Roster[]>([])
  const [rosterError, setRosterError] = createSignal<string | null>(null)
  const reload = async () => {
    // The SDK RESOLVES on failure rather than rejecting — the client is built without
    // `throwOnError` (`context/sdk.tsx:25-31`), so `client.gen.ts:222-233` hands back
    // `{data: undefined, error, request, response}`. The previous `(result?.data ?? result ?? [])`
    // therefore fell through to the envelope on exactly the path it was meant to protect, and
    // `[...envelope]` threw `TypeError: list is not iterable`. All four call sites are `void
    // reload()`, and the TUI render process installs no `unhandledRejection` handler, so under
    // Bun that TERMINATED the terminal — a control terminal that dies when the server it is
    // watching hiccups is worse than one that shows a stale roster.
    //
    // `Array.isArray` rather than dropping the `?? result` fallback outright: both shapes are
    // real (some transports flatten the envelope), and neither can throw through this guard.
    try {
      const result: any = await props.api.client.session.list({ scope: "project" })
      const payload = result?.data ?? result
      if (!Array.isArray(payload)) {
        setRosterError(result?.error ? "session list failed" : "session list returned no array")
        return
      }
      setRosterError(null)
      // Ids are DESCENDING identifiers (`schema/src/session-id.ts:8` → `identifier.ts:22`:
      // `descending ? ~current : current`), so a later creation time yields a lexicographically
      // SMALLER id and plain ascending order is already newest-first. The comment that used to
      // sit here claimed the opposite and the comparator it justified reversed the roster into
      // oldest-first — cosmetic, but cell order is what an operator builds muscle memory on.
      setRoster([...payload].sort((a: Roster, b: Roster) => a.id.localeCompare(b.id)))
    } catch (error) {
      // Keep the previous roster. A grid that empties itself on a transient failure loses the
      // operator every cell they were watching.
      setRosterError(error instanceof Error ? error.message : String(error))
    }
    // The selection index lives in the PLUGIN closure so it survives navigating into a session
    // and back (`:846-848`), which means it also survives sessions disappearing underneath it.
    // Unclamped, a stale index renders no `▸` anywhere and leaves `a`/`x`/`enter` inert on a
    // cell that is not there.
    props.setSelected(clamp(props.selected()))
  }
  // Cold-start reconcile of RED/YELLOW. `permission.list` / `question.list` return every
  // pending request across all sessions, which is the only way to see blocks that predate
  // this process. CONTEXT.MAP.md names both as the reconcile path.
  const [cold, setCold] = createSignal({
    permission: new Map<string, PermissionRequest[]>(),
    question: new Map<string, QuestionRequest[]>(),
  })
  const reconcile = async () => {
    const group = async <T extends { sessionID?: string }>(fetcher: () => Promise<any>) => {
      const out = new Map<string, T[]>()
      try {
        const result = await fetcher()
        for (const item of (result?.data ?? result ?? []) as T[]) {
          if (!item?.sessionID) continue
          const bucket = out.get(item.sessionID)
          if (bucket) bucket.push(item)
          else out.set(item.sessionID, [item])
        }
      } catch {
        // Best-effort: without the list endpoints the grid still sees every block that
        // arrives over live SSE, just none that predate it.
      }
      return out
    }
    const client = gridClient(props.api)
    setCold({
      permission: await group<PermissionRequest>(() => client.permission.list()),
      question: await group<QuestionRequest>(() => client.question.list()),
    })
  }

  onMount(() => {
    void reload()
    void reconcile()
  })
  // A resolved request clears the block, in two steps that both matter.
  //
  // Synchronously: drop it from `cold`. `reconcile()` is async, and the store's live list is
  // spliced empty the INSTANT a reply is seen (sync.tsx:175-187, 221-235) — so for the whole
  // window until the refetch lands, `pendingPermission`'s fallback would read the stale cold
  // copy and re-render a request that is already answered. Then re-reconcile, which is what
  // catches drift this client never saw: requests resolved for other sessions, or by another
  // client entirely.
  //
  // `question.rejected` is a distinct event from `question.replied` and also clears the
  // block — miss it and a rejected pre-attach question pins its cell yellow forever.
  onCleanup(
    props.api.event.on("permission.replied", (event) => {
      const { sessionID, requestID } = event.properties
      setCold((prev) => ({ ...prev, permission: without(prev.permission, sessionID, requestID) }))
      void reconcile()
    }),
  )
  const questionResolved = (event: { properties: { sessionID: string; requestID: string } }) => {
    const { sessionID, requestID } = event.properties
    setCold((prev) => ({ ...prev, question: without(prev.question, sessionID, requestID) }))
    void reconcile()
  }
  onCleanup(props.api.event.on("question.replied", questionResolved))
  onCleanup(props.api.event.on("question.rejected", questionResolved))

  // Union of both sources, deduped by id. The store may be ahead (live inserts via
  // `session.updated`) while the fetch is authoritative on scope; a control terminal wants
  // whatever either can see, and neither is a superset of the other.
  const sessions = createMemo(() => {
    const seen = new Set<string>()
    const out: Roster[] = []
    for (const item of [...roster(), ...[...sync.data.session].reverse()]) {
      if (seen.has(item.id)) continue
      seen.add(item.id)
      // Retired sessions leave the grid HERE and nowhere else — archiving filters nothing
      // server-side. Without this line a retired session keeps its cell forever, which
      // defeats the entire point of freeing the slot.
      if (item.time?.archived) continue
      out.push(item)
    }
    return out
  })

  // Error tracking. `session.error` is the ONLY event that carries the fact — see the `Errors`
  // type. Cleared when the session next goes busy or retry, so a session that errors and is then
  // re-prompted stops reading ERROR the moment it is working again; the idiom is lifted from
  // `notifications.ts:59-65`, which solves the same problem for its toast.
  //
  // Unlike notifications.ts this does NOT gate on having seen the session go busy first. That
  // gate is right for a toast (don't notify about work you never watched) and wrong for a grid,
  // whose whole job is to show state for sessions it did not start.
  const [errors, setErrors] = createSignal(new Map<string, string>())
  onCleanup(
    props.api.event.on("session.error", (event) => {
      const sessionID = event.properties.sessionID
      if (!sessionID) return
      setErrors((prev) => new Map(prev).set(sessionID, errorReason(event.properties.error)))
    }),
  )
  onCleanup(
    props.api.event.on("session.status", (event) => {
      const { sessionID, status } = event.properties
      if (status.type !== "busy" && status.type !== "retry") return
      setErrors((prev) => {
        if (!prev.has(sessionID)) return prev
        const next = new Map(prev)
        next.delete(sessionID)
        return next
      })
    }),
  )

  const isBlocked = (sessionID: string) => stateOf(sync, cold(), errors(), sessionID).startsWith("blocked")
  const directoryOf = (sessionID: string) => sessions().find((item) => item.id === sessionID)?.directory

  // The answer panel. It holds a sessionID rather than a request so that it stays correct
  // across the reply: `answerTarget` re-reads pending state, so a block that clears — by this
  // panel, by the session's own view, or by another client — collapses the panel on its own.
  const [answering, setAnswering] = createSignal<string | null>(null)
  const answerTarget = createMemo(() => {
    const sessionID = answering()
    if (!sessionID) return undefined
    // Permission outranks question, matching both `stateOf`'s precedence and the session
    // route's (routes/session/index.tsx:1283-1292): a permission blocks the tool call itself.
    const permission = pendingPermission(sync, cold(), sessionID)[0]
    if (permission) return { sessionID, permission, question: undefined }
    const question = pendingQuestion(sync, cold(), sessionID)[0]
    if (question) return { sessionID, permission: undefined, question }
    return undefined
  })
  // Answering re-enables the grid's own keys; without this the panel's disappearance would
  // leave the grid inert, since `enabled` below reads `answering()` and not the target.
  createEffect(() => {
    if (answering() && !answerTarget()) setAnswering(null)
  })

  const columns = createMemo(() => Math.max(1, Math.floor((dimensions().width - 2) / MIN_CELL_WIDTH)))
  const cellWidth = createMemo(() => Math.floor((dimensions().width - 2) / columns()))
  const rows = createMemo(() => {
    const list = sessions()
    const perRow = columns()
    const out: (typeof list)[] = []
    for (let i = 0; i < list.length; i += perRow) out.push(list.slice(i, i + perRow))
    return out
  })

  const clamp = (n: number) => Math.max(0, Math.min(n, sessions().length - 1))
  const move = (delta: number) => props.setSelected(clamp(props.selected() + delta))

  // Retirement. AUTOMATIC on threshold (PLAN.md:381), with `x` kept as the manual override.
  //
  // This reverses an earlier decision here that retirement should be operator-initiated so the
  // grid never acts on its own. The reasoning was sound in isolation and wrong in context: it
  // makes the threshold advisory, and an advisory threshold cannot do the one job it has. The
  // ceiling is ~360K and there is no graceful degradation below it — a session that crosses the
  // gate and keeps working eventually reaches a point where EVERY turn dies, which a 350K run
  // demonstrated 25 times in a row.
  const [retiring, setRetiring] = createSignal<string | null>(null)
  const [retireNote, setRetireNote] = createSignal<string | null>(null)

  const retire = async (session: Roster) => {
    const client = gridClient(props.api)
    const sessionID = session.id
    setRetiring(sessionID)
    setRetireNote(null)
    try {
      // Stop the predecessor BEFORE anything else. Archiving does not abort — `session.update`
      // reaches `session.setArchived`, a bare DB patch (`session.ts:759-761`) — and the grid
      // deliberately renders `RETIRE · working` (see the Cell), so `x` on a mid-turn session is
      // an invited action. Without this the predecessor keeps editing the SAME directory as its
      // successor (`:724` passes `session.directory`), and the instant it is archived it leaves
      // `sessions()` and therefore has no cell, no `a`, and no place in the blocked count — a
      // session burning a slot, holding half an edit, possibly parked forever on a permission
      // nothing can answer (`permission/index.ts:96-105` has no timeout).
      //
      // Unconditional and idempotent: aborting an idle session is a no-op, and checking
      // `session_status` first would race the turn that starts between the check and the call.
      // Unconditional, and it is not in tension with "let the agent finish what it is doing".
      // The AUTO path only fires on an idle session, so this is a no-op there — its purpose is
      // the race: a turn that starts between the idle check and this call is a turn beginning
      // AFTER the gate was met, and the rule is that no turn runs after the gate. On the manual
      // path it is what stops `x` on a `RETIRE · working` cell from orphaning a live session
      // that keeps editing the same directory as its own successor.
      ok(await client.session.abort({ sessionID }), "abort predecessor")

      const todoResult = ok(
        await client.session.todo({ sessionID }),
        "read todos",
      )
      const todos = (todoResult?.data ?? []).filter(Boolean)
      const open = todos.filter((todo) => todo.status !== "completed")

      // ONE unlimited fetch, serving both the objective and the changed-file list. Omitting
      // `limit` is what makes it the whole history, oldest-first — see the type on `messages`.
      // Everything downstream that used to read `sync.data.message` was reading a window of
      // the newest 100, which is wrong in both directions on exactly the sessions retirement
      // targets. Best-effort: on failure we fall back to the store, which is worse but not
      // nothing.
      const history = await client.session
        .messages({ sessionID })
        .then((result) => result?.data ?? [])
        .catch(() => [])
      const historyUsers = history
        .filter((entry) => (entry?.info?.role ?? entry?.role) === "user")
        .map((entry) => ({ id: entry?.info?.id ?? entry?.id, parts: entry?.parts ?? [] }))
        .filter((entry): entry is { id: string; parts: { type: string; text?: string }[] } => Boolean(entry.id))

      // `GET /session/{id}/diff` is a PER-USER-MESSAGE endpoint, not a session-wide one:
      // `summary.ts:130` returns [] outright when no messageID is given, and `:133` returns []
      // again unless that message is a USER message — the git diffs are written onto the user
      // message's `summary.diffs` by `SessionSummary.summarize` (`prompt.ts:1253`, forked).
      // PLAN.md:383 says "its /diff" as though one call covered the session; it does not.
      // So: fan out over the session's user messages and union the file list.
      const fallbackUsers = (sync.data.message[sessionID] ?? [])
        .filter((message) => message.role === "user")
        .map((message) => ({ id: message.id }))
      const allUsers: { id: string }[] = historyUsers.length > 0 ? historyUsers : fallbackUsers
      // Head AND tail when the history is long, never just the tail. The files a successor
      // needs are disproportionately the ones created while the session was setting up.
      const candidates =
        allUsers.length <= DIFF_FANOUT
          ? allUsers
          : [...allUsers.slice(0, DIFF_FANOUT / 2), ...allUsers.slice(-DIFF_FANOUT / 2)]
      const files = [
        ...new Set(
          (
            await Promise.all(
              candidates.map((message) =>
                client.session
                  .diff({ sessionID, messageID: message.id })
                  .then((result) => result?.data ?? [])
                  .catch(() => []),
              ),
            )
          )
            .flat()
            .map((entry) => entry?.file ?? entry?.path)
            .filter((value): value is string => Boolean(value)),
        ),
      ]

      // PLAN.md:369-370 splits the two cases and they really are different: a session with
      // nothing outstanding has nothing to hand over, so spawning a successor for it would
      // burn a fresh window to say "there is no work".
      if (open.length === 0) {
        ok(await client.session.update({ sessionID, time: { archived: Date.now() } }), "archive session")
        setRetireNote(`retired ${truncate(session.title ?? sessionID, 40)} — nothing outstanding`)
        await reload()
        return
      }

      // Parts are keyed by messageID in their own map, not nested under the message
      // (sync.tsx:96-98), so text has to be joined per message id.
      const messages = sync.data.message[sessionID] ?? []
      const textOf = (messageID: string) =>
        (sync.data.part[messageID] ?? [])
          .filter((part) => part.type === "text")
          .map((part) => ("text" in part ? part.text : ""))
          .join("\n")
          .trim()
      // The objective is fetched from the SERVER, not read out of the store, and this is the
      // difference between a correct handoff and a confidently wrong one.
      //
      // `sync.data.message[id]` holds at most the NEWEST 100 messages — `sync.tsx:597` hydrates
      // with `limit: 100`, `:618-619` keeps `infos.slice(-100)`, and the live path evicts
      // `updated[0]` past 100. So on any session longer than that, its first entry is an
      // arbitrary mid-conversation turn. `handoffDocument` then labels whatever it got
      // "## Original instruction" and tells the successor it is the statement of intent.
      //
      // Retirement exists to fire on long sessions — 256,000 tokens by default — which are
      // exactly the sessions past 100 messages. The bug was invisible to the §10 verification
      // because that ran at `HEALBOT_RETIRE_AT=20000` against an 8-message session, i.e. the one
      // regime where the store still holds message one.
      //
      // Reuses `historyUsers` from the single unlimited fetch above — oldest-first, so the
      // first one with text is genuinely message one. Best-effort: if that fetch failed,
      // `historyUsers` is empty and this falls through to the store, which costs accuracy on
      // the objective line but does not cost the handoff.
      const firstUserText = historyUsers
        .map((entry) =>
          entry.parts
            .filter((part) => part.type === "text")
            .map((part) => part.text ?? "")
            .join("\n")
            .trim(),
        )
        .find(Boolean)
      const objective =
        firstUserText ?? messages.filter((message) => message.role === "user").map((m) => textOf(m.id)).find(Boolean)
      const lastMessage = [...messages]
        .reverse()
        .filter((message) => message.role === "assistant")
        .map((m) => textOf(m.id))
        .find(Boolean)

      const document = handoffDocument({
        title: session.title ?? sessionID,
        objective,
        open,
        files,
        lastMessage,
      })

      // POST /session + seed is the ONLY path that yields a zero-token successor: `fork`
      // reports 0 at creation then climbs to exactly the parent's total within ~3s, and
      // `summarize` mutates in place. Same directory, or the successor cannot see the work.
      const created = ok(
        await client.session.create({ directory: session.directory }),
        "spawn successor",
      )
      const successorID = created?.data?.id ?? created?.id
      if (!successorID) throw new Error("session.create returned no id")

      // prompt_async, per PLAN.md:341. It was reported broken by the audit and is not —
      // it acks in ~10ms and the turn completes normally; the report polled an assistant row
      // that exists ~20ms before it fills.
      //
      // ORDERING IS THE POINT. Archiving used to happen unconditionally on the next line with
      // none of these three calls having their `.error` read — the SDK resolves rather than
      // rejects, so a 4xx anywhere left the predecessor archived, the successor unseeded, and
      // the footer reporting `handed off N open items`. The handoff is only real once the seed
      // is accepted, so the seed is confirmed BEFORE the source is retired. Failing the other
      // way round is recoverable: an unarchived predecessor still has a cell and can be retired
      // again, whereas an archived one has no cell at all.
      ok(
        await client.session.promptAsync({ sessionID: successorID, parts: [{ type: "text", text: document }] }),
        "seed successor",
      )
      ok(await client.session.update({ sessionID, time: { archived: Date.now() } }), "archive predecessor")
      await reload()

      // Hand the grid slot to the replacement, so the operator's cursor follows the work
      // rather than the cell that just vanished.
      const index = sessions().findIndex((item) => item.id === successorID)
      props.setSelected(index === -1 ? clamp(props.selected()) : index)
      setRetireNote(`handed off ${open.length} open item${open.length === 1 ? "" : "s"}, ${files.length} file${files.length === 1 ? "" : "s"}`)
    } catch (error) {
      setRetireNote(`retire failed: ${error instanceof Error ? error.message : String(error)}`)
    } finally {
      setRetiring(null)
    }
  }

  const returnRoute = (): TuiRouteCurrent | undefined => {
    const current = props.api.route.current
    if (!("params" in current)) return undefined
    const value: unknown = (current.params as Record<string, unknown> | undefined)?.returnRoute
    if (!value || typeof value !== "object" || !("name" in value)) return undefined
    return value as TuiRouteCurrent
  }

  const leave = () => {
    const back = returnRoute()
    props.api.ui.dialog.clear()
    props.api.route.navigate(back?.name ?? "home", back && "params" in back ? back.params : undefined)
  }

  // GAP-1: sync.tsx has no `session.created` case, so a new session never lands in the store
  // on its own. The grid refetches its own roster instead. The unsubscribe is tracked to the
  // PLUGIN scope, not this component, so it must be released on unmount or handlers
  // accumulate on every route mount.
  onCleanup(props.api.event.on("session.created", () => void reload()))
  onCleanup(props.api.event.on("session.deleted", () => void reload()))

  // Surfacing. A block that arrives while the grid is open moves the selection onto it, so the
  // session that wants a human is the one already under the cursor and `a` answers it — that
  // is the whole point of a control terminal. Two cases where it must NOT steal the cursor:
  // while an answer panel is open, and when the current cell is itself blocked (you are
  // probably mid-decision on that one). Both leave the header count as the signal instead.
  const surface = (sessionID?: string) => {
    if (!sessionID || answering()) return
    const list = sessions()
    const current = list[props.selected()]
    if (current && isBlocked(current.id)) return
    const index = list.findIndex((item) => item.id === sessionID)
    if (index !== -1) props.setSelected(index)
  }
  onCleanup(props.api.event.on("permission.asked", (event) => surface(event.properties.sessionID)))
  onCleanup(props.api.event.on("question.asked", (event) => surface(event.properties.sessionID)))

  const commands = [
    { name: "healbot.close", title: "Close Healbot", category: "Healbot", run: leave },
    { name: "healbot.left", title: "Select left", category: "Healbot", run: () => move(-1) },
    { name: "healbot.right", title: "Select right", category: "Healbot", run: () => move(1) },
    { name: "healbot.up", title: "Select up", category: "Healbot", run: () => move(-columns()) },
    { name: "healbot.down", title: "Select down", category: "Healbot", run: () => move(columns()) },
    { name: "healbot.refresh", title: "Refresh session list", category: "Healbot", run: () => void reload() },
    {
      name: "healbot.focus",
      title: "Focus selected session",
      category: "Healbot",
      run() {
        const session = sessions()[props.selected()]
        if (!session) return
        props.api.ui.dialog.clear()
        // adapters.tsx:47-52 reads ONLY sessionID out of these params; everything else is
        // dropped, so the return route cannot be threaded through the session route.
        props.api.route.navigate("session", { sessionID: session.id })
      },
    },
    {
      name: "healbot.answer",
      title: "Answer selected session",
      category: "Healbot",
      run() {
        const session = sessions()[props.selected()]
        // Answering an unblocked session would open an empty panel and swallow the keyboard.
        if (!session || !isBlocked(session.id)) return
        setAnswering(session.id)
      },
    },
    {
      name: "healbot.retire",
      title: "Retire selected session and hand off",
      category: "Healbot",
      run() {
        const session = sessions()[props.selected()]
        // One at a time: the flow spawns a session and archives another, and two of them
        // interleaved would race `reload()` and leave the cursor on the wrong cell.
        if (!session || retiring()) return
        void retire(session)
      },
    },
    {
      name: "healbot.next-blocked",
      title: "Select next blocked session",
      category: "Healbot",
      run() {
        const list = sessions()
        // From the cell AFTER the current one, wrapping, so repeated presses cycle the queue
        // rather than sticking on a cell that is already blocked.
        for (let step = 1; step <= list.length; step++) {
          const index = (props.selected() + step) % list.length
          if (isBlocked(list[index].id)) {
            props.setSelected(index)
            return
          }
        }
      },
    },
  ]

  useBindings(() => ({
    // Base mode + `enabled`, together, are what let the answer panel own the keyboard. The
    // prompts collide with this grid on almost every key (j/k/h/l, 1-9, return, escape):
    // `QuestionPrompt` pushes its own mode, which a mode-less binding set would ignore
    // entirely (`mode()` is a require-condition — keymap.tsx:57-59 — so declaring no mode
    // means "every mode"), while `PermissionPrompt` binds in base mode and pushes nothing.
    // Base mode handles the first, `enabled` handles the second.
    mode: OPENCODE_BASE_MODE,
    enabled: !answering(),
    commands,
    bindings: [
      { key: "escape,q", cmd: "healbot.close", desc: "Close Healbot" },
      { key: "h,left", cmd: "healbot.left", desc: "Select left" },
      { key: "l,right", cmd: "healbot.right", desc: "Select right" },
      { key: "k,up", cmd: "healbot.up", desc: "Select up" },
      { key: "j,down", cmd: "healbot.down", desc: "Select down" },
      { key: "a", cmd: "healbot.answer", desc: "Answer blocked session" },
      // `x`, not `R`: no letter binding anywhere in this package uses a shift modifier, and
      // `r` is already refresh.
      { key: "x", cmd: "healbot.retire", desc: "Retire session and hand off" },
      { key: "tab", cmd: "healbot.next-blocked", desc: "Select next blocked session" },
      { key: "return", cmd: "healbot.focus", desc: "Focus selected session" },
      { key: "r", cmd: "healbot.refresh", desc: "Refresh session list" },
      ...props.api.tuiConfig.keybinds.gather(
        "healbot",
        commands.map((command) => command.name),
      ),
    ],
  }))

  const blocked = createMemo(() => sessions().filter((item) => isBlocked(item.id)).length)
  // Counted independently of `blocked`, and off occupancy rather than off `stateOf`: a session
  // that is over the threshold AND blocked renders as PERMISSION — blocked outranks retire —
  // but it still needs retiring once answered, and the header is the only place that survives
  // the precedence collapse.
  const retirable = createMemo(() => sessions().filter((item) => occupancyOf(sync, item.id) >= RETIRE_AT).length)
  // Same reasoning as `retirable`: counted off the raw fact rather than off `stateOf`, so a
  // session that is blocked AND errored is still counted here after the block collapses it to
  // PERMISSION. A count that disappears because another state outranked it is not a count.
  const failed = createMemo(() => sessions().filter((item) => errorOf(sync, errors(), item.id)).length)

  return (
    <box
      position="absolute"
      zIndex={2500}
      left={0}
      top={0}
      width={dimensions().width}
      height={dimensions().height}
      flexDirection="column"
    >
      <box flexDirection="row" paddingLeft={1} paddingRight={1}>
        <text fg={theme().primary}>Healbot</text>
        <text fg={theme().textMuted}>
          {"  "}
          {sessions().length} {sessions().length === 1 ? "session" : "sessions"}
        </text>
        <Show when={blocked() > 0}>
          <text fg={theme().error}>
            {"  "}
            {blocked()} blocked
          </text>
        </Show>
        <Show when={failed() > 0}>
          <text fg={theme().error}>
            {"  "}
            {failed()} failed
          </text>
        </Show>
        <Show when={retirable() > 0}>
          <text fg={theme().secondary}>
            {"  "}
            {retirable()} to retire
          </text>
        </Show>
        <box flexGrow={1} />
        <text fg={theme().textMuted}>
          {/*
            "esc reject", not "esc dismiss": escape is DESTRUCTIVE on both prompts — the
            permission prompt passes escapeKey="reject" (permission.tsx:406) and the question
            prompt's escape calls reject() (question.tsx:281). There is no back-out key, which
            is the same bargain the session route makes; naming it honestly is the guard.
          */}
          {answering()
            ? "answering · esc reject"
            : retiring()
              ? "retiring · handing off"
              : // A failed roster fetch outranks the key legend: the cells on screen are stale
                // and the operator has no other way to learn that. `r` retries.
                (rosterError()
                  ? `${rosterError()} · r retry`
                  : (retireNote() ?? "a answer · x retire · tab next blocked · enter focus · r refresh · q close"))}
        </text>
      </box>

      <Show
        when={sessions().length > 0}
        fallback={
          <box flexGrow={1} paddingLeft={1}>
            <text fg={theme().textMuted}>No sessions yet. Start one from the home screen.</text>
          </box>
        }
      >
        <box flexDirection="column" flexGrow={1}>
          <For each={rows()}>
            {(row, rowIndex) => (
              <box flexDirection="row">
                <For each={row}>
                  {(session, columnIndex) => (
                    <Cell
                      api={props.api}
                      sessionID={session.id}
                      title={session.title ?? session.id}
                      parentID={session.parentID}
                      selected={rowIndex() * columns() + columnIndex() === props.selected()}
                      width={cellWidth()}
                      cold={cold()}
                      errors={errors()}
                    />
                  )}
                </For>
              </box>
            )}
          </For>
        </box>
      </Show>

      {/*
        Answer-in-place. The grid keeps rendering above this panel — the point of a control
        terminal is that clearing one block never costs you sight of the other sessions, which
        is exactly what `route.navigate("session")` does cost. Both prompts are the session
        route's own components (routes/session/{permission,question}.tsx), not reimplementations:
        they carry multi-question walking, custom answers, always/reject and the reply calls
        themselves, and every context they consume — theme, sdk, sync, project, config, keymap —
        is app-level, so they mount anywhere inside the app tree.
      */}
      <Show when={answerTarget()}>
        {(target) => (
          <box flexShrink={0} flexDirection="column">
            <box flexDirection="row" paddingLeft={1} paddingRight={1}>
              <text fg={theme().textMuted}>answering </text>
              <text fg={theme().text}>
                {truncate(
                  sessions().find((item) => item.id === target().sessionID)?.title ?? target().sessionID,
                  Math.max(1, dimensions().width - 12),
                )}
              </text>
            </box>
            <Show when={target().permission}>
              {(request) => <PermissionPrompt request={request()} directory={directoryOf(target().sessionID)} />}
            </Show>
            <Show when={target().question}>
              {(request) => <QuestionPrompt request={request()} directory={directoryOf(target().sessionID)} />}
            </Show>
          </box>
        )}
      </Show>
    </box>
  )
}

const tui: TuiPlugin = async (api) => {
  // Selection lives in the plugin closure, not the component, so it survives navigating
  // into a session and back. Pattern from which-key.tsx:533-535.
  const [selected, setSelected] = createSignal(0)

  api.route.register([
    {
      name: ROUTE,
      render: () => <Healbot api={api} selected={selected} setSelected={setSelected} />,
    },
  ])

  api.keymap.registerLayer({
    commands: [
      {
        name: "healbot.open",
        title: "Open Healbot control terminal",
        slashName: "healbot",
        category: "Healbot",
        namespace: "palette",
        run() {
          api.route.navigate(ROUTE, { returnRoute: api.route.current })
          // Required, or the palette dialog stays layered over the route (F4).
          api.ui.dialog.clear()
        },
      },
    ],
  })
}

export default {
  id: "healbot",
  tui,
}
