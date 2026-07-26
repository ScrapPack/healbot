/** @jsxImportSource @opentui/solid */
import type { TuiPlugin, TuiPluginApi, TuiRouteCurrent } from "@opencode-ai/plugin/tui"
import { useTerminalDimensions } from "@opentui/solid"
import { createMemo, createSignal, For, onCleanup, onMount, Show } from "solid-js"
import { useSync } from "../../context/sync"
import { useBindings } from "../../keymap"

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

function stateOf(sync: ReturnType<typeof useSync>, sessionID: string): CellState {
  if ((sync.data.permission[sessionID] ?? []).length > 0) return "blocked-permission"
  if ((sync.data.question[sessionID] ?? []).length > 0) return "blocked-question"
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

  const state = createMemo(() => stateOf(sync, props.sessionID))
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
  const [roster, setRoster] = createSignal<{ id: string; title?: string; parentID?: string }[]>([])
  const reload = async () => {
    const result: any = await props.api.client.session.list({ scope: "project" })
    const list = (result?.data ?? result ?? []) as { id: string; title?: string; parentID?: string }[]
    // Ids are monotonic-ascending, so id order is creation order — newest first.
    setRoster([...list].sort((a, b) => b.id.localeCompare(a.id)))
  }
  onMount(() => void reload())

  // Union of both sources, deduped by id. The store may be ahead (live inserts via
  // `session.updated`) while the fetch is authoritative on scope; a control terminal wants
  // whatever either can see, and neither is a superset of the other.
  const sessions = createMemo(() => {
    const seen = new Set<string>()
    const out: { id: string; title?: string; parentID?: string }[] = []
    for (const item of [...roster(), ...[...sync.data.session].reverse()]) {
      if (seen.has(item.id)) continue
      seen.add(item.id)
      out.push(item)
    }
    return out
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
  ]

  useBindings(() => ({
    commands,
    bindings: [
      { key: "escape,q", cmd: "healbot.close", desc: "Close Healbot" },
      { key: "h,left", cmd: "healbot.left", desc: "Select left" },
      { key: "l,right", cmd: "healbot.right", desc: "Select right" },
      { key: "k,up", cmd: "healbot.up", desc: "Select up" },
      { key: "j,down", cmd: "healbot.down", desc: "Select down" },
      { key: "return", cmd: "healbot.focus", desc: "Focus selected session" },
      { key: "r", cmd: "healbot.refresh", desc: "Refresh session list" },
      ...props.api.tuiConfig.keybinds.gather(
        "healbot",
        commands.map((command) => command.name),
      ),
    ],
  }))

  const blocked = createMemo(
    () => sessions().filter((item) => stateOf(sync, item.id).startsWith("blocked")).length,
  )

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
        <text fg={theme().textMuted}>enter focus · r refresh · q close</text>
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
                    />
                  )}
                </For>
              </box>
            )}
          </For>
        </box>
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
