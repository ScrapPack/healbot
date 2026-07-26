/** @jsxImportSource @opentui/solid */
import type { TuiPlugin, TuiPluginApi, TuiRouteCurrent } from "@opencode-ai/plugin/tui"
import { useKeyboard } from "@opentui/solid"
import { createSignal, For, onCleanup } from "solid-js"

// F4-proof spike. Proves, in one route:
//   1. a plugin-registered route renders full-screen
//   2. it receives keyboard input
//   3. it can read all-session state via api.client   (the grid's data path)
//   4. it can subscribe to live events via api.event   (the border state path)
//   5. it can navigate back out                        (the focus/return path)
// Delete once the real grid lands.

const ROUTE = "healbot-spike"

function HealbotSpike(props: { api: TuiPluginApi }) {
  const theme = () => props.api.theme.current
  const [keyCount, setKeyCount] = createSignal(0)
  const [lastKey, setLastKey] = createSignal("(none)")
  const [sessionCount, setSessionCount] = createSignal(-1)
  const [sessionError, setSessionError] = createSignal("")
  const [eventLog, setEventLog] = createSignal<string[]>([])

  const push = (line: string) => setEventLog((prev) => [line, ...prev].slice(0, 6))

  // The route the palette command stashed, read back out of route params.
  // diff-viewer casts the whole params bag unvalidated (diff-viewer.tsx:95-103); this
  // checks the shape instead, so a malformed param yields "home" rather than a bad navigate.
  const returnRoute = (): TuiRouteCurrent | undefined => {
    const current = props.api.route.current
    if (!("params" in current)) return undefined
    const value: unknown = (current.params as Record<string, unknown> | undefined)?.returnRoute
    if (!value || typeof value !== "object" || !("name" in value)) return undefined
    return value as TuiRouteCurrent
  }

  // (3) data path — the grid will read every session from here.
  props.api.client.session
    .list()
    .then((result: any) => setSessionCount((result?.data ?? result ?? []).length))
    .catch((err: any) => setSessionError(String(err?.message ?? err).slice(0, 40)))

  // (4) live event path — these are the exact events the border states key off.
  // `api.event.on` returns an unsubscribe that the host tracks to the PLUGIN scope
  // (runtime.ts:593-597), not to this component. Without onCleanup, every route mount
  // leaves four more live handlers writing into a disposed component's signals.
  // The grid subscribes to message.part.updated (fires per token delta) — it must do this.
  onCleanup(
    props.api.event.on("session.status", (event: any) =>
      push(`session.status ${String(event?.properties?.status?.type ?? "?")}`),
    ),
  )
  onCleanup(props.api.event.on("session.idle", () => push("session.idle")))
  onCleanup(props.api.event.on("permission.asked", () => push("permission.asked  <- RED")))
  onCleanup(props.api.event.on("question.asked", () => push("question.asked     <- YELLOW")))

  // (2) keyboard path
  useKeyboard((evt) => {
    if (evt.name === "q") {
      evt.preventDefault()
      evt.stopPropagation()
      // (5) return path — honour the route the palette command stashed, as diff-viewer
      // does (diff-viewer.tsx:439-445). Falls back to home when opened cold.
      const back = returnRoute()
      props.api.ui.dialog.clear()
      props.api.route.navigate(back?.name ?? "home", back && "params" in back ? back.params : undefined)
      return
    }
    setKeyCount((n) => n + 1)
    setLastKey(evt.name ?? "?")
  })

  return (
    <box flexGrow={1} flexDirection="column" padding={1}>
      <box border borderColor={theme().primary} padding={1} flexDirection="column">
        <text fg={theme().primary}>HEALBOT SPIKE — plugin route renders full-screen</text>
      </box>

      <box border borderColor={theme().success} padding={1} flexDirection="column" marginTop={1}>
        <text fg={theme().text}>
          PROBE_KEYS={keyCount()} PROBE_LASTKEY=[{lastKey()}]
        </text>
        <text fg={sessionError() ? theme().error : theme().text}>
          {sessionError()
            ? `PROBE_SESSIONS_ERR=[${sessionError()}]`
            : sessionCount() < 0
              ? "PROBE_SESSIONS_PENDING"
              : `PROBE_SESSIONS_OK=[${sessionCount()}]`}
        </text>
      </box>

      <box border borderColor={theme().warning} padding={1} flexDirection="column" marginTop={1} flexGrow={1}>
        <text fg={theme().warning}>live events (border-state source)</text>
        <For each={eventLog()} fallback={<text fg={theme().textMuted}>waiting for events…</text>}>
          {(line) => <text fg={theme().text}>{line}</text>}
        </For>
      </box>

      <text fg={theme().textMuted}>press any key to count · q to return home</text>
    </box>
  )
}

const tui: TuiPlugin = async (api) => {
  // (1) full-screen route
  api.route.register([
    {
      name: ROUTE,
      render: () => <HealbotSpike api={api} />,
    },
  ])

  api.keymap.registerLayer({
    commands: [
      {
        name: "healbot.spike",
        title: "Healbot spike",
        slashName: "healbot",
        category: "Healbot",
        namespace: "palette",
        run() {
          api.route.navigate(ROUTE, { returnRoute: api.route.current })
          api.ui.dialog.clear()
        },
      },
    ],
  })
}

export default {
  id: "healbot-spike",
  tui,
}
