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
 * exit gate can actually be exercised: `PLAN.md:392-394` requires a session "driven past the
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
 * RETIREMENT DOES NOT LIVE IN THIS FILE AT ALL. Automatic retirement moved to the server plugin
 * at `harness/config/opencode/plugin/healbot.ts` in Phase 6 — this pointer read `auto-retire.ts`
 * until 7b7ce9f renamed the file, and `find . -name "auto-retire*"` now returns nothing — and in
 * Phase 7 MANUAL retirement followed it. `x` no longer runs a handoff; it writes a request to
 * session metadata and the plugin, the only implementation left, performs it. See `retire()`
 * below for the channel and why it is a metadata write.
 *
 * `RETIRE_AT` above is therefore used HERE only to render the `RETIRE` border, the `N to retire`
 * header count and the share-of-threshold figure on each cell.
 *
 * The border painted off `RETIRE_AT` and the moment the server acts on it are NOT the same event.
 * That gate fires at a STEP boundary, not at the end of a turn — `processor.ts:443-445` writes
 * `finish` and `tokens` in one mutation at every `step-finish`, so the plugin's `stepFinished()`
 * holds on every message that carries occupancy at all (MEASURED across 733 real assistant
 * messages with occupancy > 0: zero had a null `finish`; 677 were `"tool-calls"`, i.e. mid-turn).
 * So a cell reading `RETIRE · working` can be aborted and handed off mid-turn, one step after it
 * turns purple, and overshoot past the line is bounded by a step rather than a whole turn — the
 * full account is `HARNESS.md`.
 *
 * Automatic retirement moved because a `createEffect` in this component could only ever run while
 * the grid was mounted. Two consequences, and the second is the one that mattered:
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
 * **Exactly one process may own retirement**, and as of Phase 7 exactly one does. Deleting this
 * effect was the first half; Phase 6 stopped there and left `x` running a second complete copy of
 * the handoff in this process, which is why an operator pressing `x` as the gate fired could still
 * produce two successors for one session. Phase 6 recorded that window as "narrowed to one
 * request" by a re-read before archiving — a review showed the re-read narrows nothing, since it
 * runs after the successor is created and seeded. The second writer is now gone rather than
 * better-timed.
 *
 * Consequence to know, and it is bigger than it was: run the fork WITHOUT the harness config and
 * **neither** automatic nor manual retirement works. The border still goes purple, `x` still
 * writes its request, and nothing is listening. That is an acceptable trade because the harness
 * IS the deliverable — the model pin and `compaction.auto:false` live there too — but it is a real
 * behavioural split between the two trees. See `docs/HEADLESS.md`.
 */

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
 * biased toward "everything finished". PLAN.md:370 asked for the state; HARNESS.md's
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
    /**
     * `metadata` IS accepted by the route and is NOT in the generated type — the same divergence
     * `docs/HEADLESS.md` records for the v1 client's `time.archived`, one tree over. VERIFIED:
     * `httpapi/groups/session.ts:51` declares `metadata: Schema.optional(Session.Metadata)` on the
     * update payload and `handlers/session.ts:191-192` calls `session.setMetadata` with it. The
     * generated `session.update` input is `{ sessionID, time? }` and typechecking the real call
     * against it fails with TS2353. Widening the structural type here is the honest fix: this
     * declaration exists precisely to name the slice of the client the grid uses, and the file
     * already carries exactly one unsafe assertion to reach it.
     *
     * This shrank from ten members to three in Phase 7. `todo`, `diff`, `messages`, `create`,
     * `promptAsync` and `abort` were the grid's own duplicate of `retire()`; the server plugin
     * owns that now and they are gone. What is left is the two cold-start reconcile reads and one
     * write to ask for a retirement.
     */
    update(input: {
      sessionID: string
      time?: { archived?: number }
      metadata?: Record<string, unknown>
    }): Promise<Envelope<unknown>>
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
 * `handoffDocument` USED TO LIVE HERE, and its deletion is the point of the Phase 7 change.
 *
 * It was a verbatim twin of the same function in `harness/config/opencode/plugin/healbot.ts`,
 * because the grid ran its own `retire()` for manual `x` and the two trees cannot import each
 * other. Phase 6 called two copies "a compromise guarded by a test" and pointed at
 * `probe_twin.py`. A review then showed the guard compared only DOUBLE-QUOTED literals, so it
 * could not see either of the two template literals that render the document's actual bullets —
 * it missed eight seeded divergences and caught one.
 *
 * The compromise is gone rather than better-guarded. `x` now relays a request to the server plugin
 * (see `retire` below), which owns the only implementation. A successor is briefed identically
 * whether a human pressed a key or the gate fired, because there is only one thing that can brief
 * it. `probe_twin.py` no longer compares documents; it asserts this file has no second copy.
 *
 * The thresholds are still duplicated — `RETIRE_AT` above — and still deliberately so: the grid
 * needs the number to paint with and cannot import it. That one is a NUMBER, comparable exactly,
 * and it is what `probe_twin.py` still guards.
 */

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
// the control terminal as a client (PLAN.md:348) — where the server outlives the TUI.

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
  // Split out of `busy`, per PLAN.md:370's "red flash | session.status {type:"retry"}". A retry
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
    // Red, like a permission, and deliberately so: PLAN.md:366 and :370 assign red to both. The label
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

  // Retirement, MANUAL only: `x` on the selected cell, and nothing else in this file retires
  // anything. This comment read "AUTOMATIC on threshold (PLAN.md:381), with `x` kept as the manual
  // override" for two phases; that described a `createEffect` which no longer exists here. The
  // automatic gate is the server plugin's (`harness/config/opencode/plugin/healbot.ts`) and it
  // fires per STEP — see the header block at the top of this file. `RETIRE_AT` survives in this
  // file only to paint the `RETIRE` border (`stateOf`), count `N to retire` in the header
  // (`retirable`) and print the share-of-threshold figure on each cell (`share`).
  //
  // What has not changed is why the threshold cannot be advisory, which is the argument that moved
  // to the plugin along with the effect: the ceiling is ~360K and there is no graceful degradation
  // below it — a session that crosses the gate and keeps working eventually reaches a point where
  // EVERY turn dies, which a 350K run demonstrated 25 times in a row. PLAN.md:381's "on threshold"
  // is still the requirement; it is met in the server, not here.
  const [retiring, setRetiring] = createSignal<string | null>(null)
  const [retireNote, setRetireNote] = createSignal<string | null>(null)

  const retire = async (session: Roster) => {
    const client = gridClient(props.api)
    const sessionID = session.id
    setRetiring(sessionID)
    setRetireNote(null)
    try {
      // THE GRID NO LONGER RETIRES. It asks the server to, and this is the whole fix for the
      // double-retire race — the one thing `NEXT.md` carried into Phase 7 as an open defect.
      //
      // What used to be here: ~180 lines that aborted the session, read its todos, fanned out over
      // its diffs, built a handoff document, spawned a successor, seeded it and archived the
      // predecessor — a second, complete implementation of `retire()`, running in the TUI process
      // while the server plugin ran its own copy with no shared lock between them. Phase 6
      // documented the resulting window as "narrowed to one request" by a re-read before
      // archiving; a review showed the re-read narrows nothing, because it runs AFTER the
      // successor is created and seeded. Both actors could reach `POST /session`, and one session
      // would get two live successors editing the same directory.
      //
      // It also meant `handoffDocument` — prose that IS behaviour — existed twice, guarded only by
      // a probe that (also per the review) compared double-quoted literals and could not see
      // either of the two template literals that render the document's actual bullets.
      //
      // Both problems have the same cause: two writers. So there is now one. The server plugin
      // owns retirement outright, for `x` and for the gate, and this call is the entire client
      // side of it.
      //
      // THE CHANNEL, and why a metadata write rather than an endpoint: the server plugin surface
      // is hooks only (`packages/plugin/src/index.ts`) and its `event` hook is receive-only, so a
      // plugin cannot register a route for the TUI to call. It does not need one. `PATCH
      // /session/{id}` accepts `metadata` (`httpapi/groups/session.ts:51`,
      // `handlers/session.ts:191-192`), which reaches `Session.setMetadata` (`session.ts:763`),
      // which calls the shared `patch()` — and `patch()` publishes `SessionV1.Event.Updated` with
      // the whole session object at `session.ts:748`. The plugin already receives every event for
      // its directory. So a one-line write is a durable, ordered request that survives this
      // process dying, and needs no new dependency on either side.
      //
      // The key and its shape are `REQUEST_KEY` / `requestedAt` in
      // `harness/config/opencode/plugin/healbot.ts`. If you change one, change the other — and
      // note that unlike the two `handoffDocument`s this replaces, the failure mode here is loud:
      // nothing retires, rather than something retiring differently.
      ok(
        await client.session.update({ sessionID, metadata: { healbot: { retireRequested: Date.now() } } }),
        "request retirement",
      )

      // Deliberately NOT awaited to completion, and not reported as done. Retirement now happens
      // in another process and takes several round trips; the grid learns it happened the same way
      // it learns everything else, through `session.updated` and its own `reload()`. Claiming
      // success here would be claiming knowledge this process does not have — the exact failure
      // this project keeps catching in itself.
      setRetireNote(`asked the server to retire ${truncate(session.title ?? sessionID, 40)}`)
      await reload()
    } catch (error) {
      setRetireNote(`retire request failed: ${error instanceof Error ? error.message : String(error)}`)
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
