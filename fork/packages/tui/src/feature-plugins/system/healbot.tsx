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
 * Border state, highest precedence first. RED/YELLOW outrank activity because they are
 * the states that need a human: the session is blocked until someone answers.
 */
type CellState = "blocked-permission" | "blocked-question" | "busy" | "done" | "idle"

/**
 * Pending requests recovered by the cold-start reconcile, grouped by session — see
 * `reconcile()`. These are the full request bodies, not just the ids that were enough to
 * colour a border: answering a block from the grid needs the request itself (its prompt and
 * its options), and for a block that predates this client the live store holds nothing.
 */
type Cold = { permission: Map<string, PermissionRequest[]>; question: Map<string, QuestionRequest[]> }

/** A grid cell's session, from either roster source. */
type Roster = { id: string; title?: string; parentID?: string; directory?: string }

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

function stateOf(sync: ReturnType<typeof useSync>, cold: Cold, sessionID: string): CellState {
  if (pendingPermission(sync, cold, sessionID).length > 0) return "blocked-permission"
  if (pendingQuestion(sync, cold, sessionID).length > 0) return "blocked-question"
  const status = sync.data.session_status[sessionID]
  // Absent is meaningful: the server deletes the key on idle (session/status.ts:42-45), so
  // the HTTP seed only ever carries busy/retry. Key present + idle ⇒ it ran and finished in
  // THIS process. Absent ⇒ never started here — dim, not green. See CONTEXT.MAP.md G3.
  if (!status) return "idle"
  if (status.type === "busy" || status.type === "retry") return "busy"
  return "done"
}

function borderColor(api: TuiPluginApi, state: CellState, selected: boolean) {
  const theme = api.theme.current
  switch (state) {
    case "blocked-permission":
      return theme.error
    case "blocked-question":
      return theme.warning
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

  const state = createMemo(() => stateOf(sync, props.cold, props.sessionID))
  const todos = createMemo(() => (sync.data.todo[props.sessionID] ?? []).filter((item) => item.status !== "completed"))
  const last = createMemo(() => {
    const messages = sync.data.message[props.sessionID] ?? []
    return messages[messages.length - 1]
  })

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
        <Show when={props.parentID}>
          <text fg={theme().textMuted}> · subagent</text>
        </Show>
      </box>
      <text fg={theme().textMuted}>
        {truncate(
          [
            todos().length > 0 ? `${todos().length} todo` : undefined,
            last() ? `${(sync.data.message[props.sessionID] ?? []).length} msg` : "no history",
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
  const reload = async () => {
    const result: any = await props.api.client.session.list({ scope: "project" })
    const list = (result?.data ?? result ?? []) as Roster[]
    // Ids are monotonic-ascending, so id order is creation order — newest first.
    setRoster([...list].sort((a, b) => b.id.localeCompare(a.id)))
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
    const client = props.api.client as any
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
      out.push(item)
    }
    return out
  })

  const isBlocked = (sessionID: string) => stateOf(sync, cold(), sessionID).startsWith("blocked")
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
        <box flexGrow={1} />
        <text fg={theme().textMuted}>
          {/*
            "esc reject", not "esc dismiss": escape is DESTRUCTIVE on both prompts — the
            permission prompt passes escapeKey="reject" (permission.tsx:406) and the question
            prompt's escape calls reject() (question.tsx:281). There is no back-out key, which
            is the same bargain the session route makes; naming it honestly is the guard.
          */}
          {answering() ? "answering · esc reject" : "a answer · tab next blocked · enter focus · r refresh · q close"}
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
