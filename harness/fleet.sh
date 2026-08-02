#!/bin/sh
# Healbot fleet: one long-lived server, the control terminal as a client.
#
#   ~/Desktop/healbot/harness/fleet.sh [project-dir] [port]
#
# This is the architecture PLAN.md:335 assumed from the start — "one `opencode serve` hosts
# every session. The control TUI is a client. Sessions are server-side and keep running
# whether or not anything renders them." Until now the harness only ever ran `opencode`,
# which hosts its own server inside the TUI process and takes every session down with it.
#
# WHY THIS IS NOT THE SAME AS RUNNING `opencode`
#
#   1. Your sessions outlive the terminal. Quit the grid, resize, crash, reattach — the turns
#      that were running are still running, and the grid repaints them.
#   2. The cold-start reconcile becomes reachable. `healbot.tsx`'s `reconcile()` exists to
#      recover blocks that predate the client, via `GET /permission` and `GET /question`.
#      With a TUI-hosted server that path is dead code by construction: a restart kills the
#      pending requests along with the server, because they live in an in-memory Map
#      (`permission/index.ts:24,50` — the `permission` table has zero rows). Split them and
#      the reconcile does real work.
#   3. More than one client can watch the same fleet.
#
# `HARNESS.md` used to record this as **blocked**, on the reasoning that `--port` is "port to
# listen on" (`cli/network.ts:9`) so the TUI always hosts its own server. The premise is true
# and the conclusion was wrong: `opencode attach <url>` is a separate, first-class command
# (`cli/cmd/attach.ts:7-16`), registered unhidden at `index.ts:84`, and its non-`--mini`
# branch calls the SAME `run()` from `cli/tui/layer` with the SAME
# `createLegacyTuiPluginHost()` as `cli/cmd/tui.ts:271-296`. So it is the full TUI, and the
# Healbot grid loads on it like any other builtin (`feature-plugins/builtins.ts`).
#
# Both halves are started under `env.sh`. The SERVER's config is the one that decides the
# model pin and `compaction.auto`, because the server owns the sessions; the client's decides
# theme and keybinds. Sourcing once and exporting covers both.

set -eu

FLEET_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"
if [ ! -f "$FLEET_ROOT/env.sh" ]; then
  echo "fleet.sh: could not locate the harness (looked in '$FLEET_ROOT')." >&2
  echo "fleet.sh: run this with zsh or bash, or set HARNESS_ROOT and re-run." >&2
  exit 1
fi

PROJECT="${1:-$PWD}"
PORT="${2:-${HEALBOT_PORT:-4096}}"
URL="http://127.0.0.1:$PORT"
LOG="${TMPDIR:-/tmp}/healbot-serve-$PORT.log"

# WHICH opencode. This matters more than it looks: the grid is a builtin plugin inside the
# FORK (`packages/tui/src/feature-plugins/system/healbot.tsx`), so the released `opencode` on
# your PATH does not have it. Running this against the installed binary gets you the fleet
# architecture and no control terminal — `/healbot` simply will not exist.
# hb_nativepath: paths that cross into a NATIVE process (bun's --cwd, claude/opencode
# flags) must be Windows-shaped under Git Bash; POSIX /c/... resolves wrongly there.
# Identity everywhere else. Same rule and rationale as env.sh's copy.
hb_nativepath() {
  case "$(uname -s 2>/dev/null)" in
    MINGW*|MSYS*|CYGWIN*) cygpath -m "$1" 2>/dev/null || printf '%s\n' "$1";;
    *) printf '%s\n' "$1";;
  esac
}

# HEALBOT_OPENCODE overrides the resolution below with a launch command of your own (a
# second checkout, a wrapper, a pinned build). Optional and unset by default; the two
# derived branches under it are the supported paths and neither needs configuring.
FORK="$(hb_nativepath "$(cd "$FLEET_ROOT/.." 2>/dev/null && pwd)/opencode")"
if [ -n "${HEALBOT_OPENCODE:-}" ]; then
  OC="$HEALBOT_OPENCODE"
elif [ -f "$FORK/packages/opencode/src/index.ts" ]; then
  OC="bun run --cwd $FORK/packages/opencode --conditions=browser src/index.ts"
elif command -v opencode >/dev/null 2>&1; then
  OC="opencode"
  echo "fleet: WARNING — no fork checkout at $FORK, falling back to the installed opencode." >&2
  echo "fleet: the Healbot grid is a builtin of the fork, so /healbot will NOT exist." >&2
  echo "fleet: see fork/README.md to reconstitute the checkout." >&2
else
  echo "fleet: no fork checkout at $FORK and no 'opencode' on PATH." >&2
  exit 1
fi

if [ ! -d "$PROJECT" ]; then
  echo "fleet.sh: project directory does not exist: $PROJECT" >&2
  exit 1
fi
PROJECT="$(hb_nativepath "$(cd "$PROJECT" && pwd)")"

# shellcheck source=./env.sh
HARNESS_ROOT="$FLEET_ROOT" . "$FLEET_ROOT/env.sh"

# Reuse a server that is already up. This is the point of the whole script — reattaching must
# NOT restart the fleet, or every guarantee above evaporates.
#
# Probes an API route rather than `/app`: `/app` serves the web UI's static HTML and answers
# 200 before the API layer is necessarily useful, so it can report ready too early. The
# session list is the same call the grid makes on mount.
alive() {
  curl -sf -o /dev/null --max-time 3 "$URL/session?scope=project" 2>/dev/null
}

if alive; then
  echo "fleet: reusing the server already listening on $URL"
else
  # 127.0.0.1 is `cli/network.ts:15`'s default and is restated here so that a config file
  # setting `server.hostname` cannot silently widen it — `resolveNetworkOptionsNoConfig:70-74`
  # prefers the explicit flag. OPENCODE_SERVER_PASSWORD is unset, so `serve` prints an
  # "unsecured" warning; that is correct for a loopback-only socket and wrong the moment the
  # hostname changes, which is exactly why the flag is pinned.
  echo "fleet: starting server on $URL (log: $LOG)"
  # `nohup` + `disown` + `</dev/null` are all load-bearing, and the script was WRONG without
  # them — TESTED: a plain `&` server died the moment the control terminal closed, which is
  # the precise failure this whole architecture exists to prevent.
  #
  # Three separate things want to kill it:
  #   - the shell HUPs its background jobs when it exits    -> nohup
  #   - the job table keeps it attached to this shell       -> disown
  #   - it shares the terminal's stdin and dies on its close -> </dev/null
  #
  # `disown` is a bash/zsh builtin, not POSIX, hence the `|| true`; `nohup` alone already
  # covers the SIGHUP on shells without it.
  #
  # OC is a command WORD LIST (it may be `bun run --cwd ... src/index.ts`), so it must
  # stay unquoted here. Quoting it would look for a binary with spaces in its name.
  # shellcheck disable=SC2086
  nohup $OC serve --port "$PORT" --hostname 127.0.0.1 </dev/null >"$LOG" 2>&1 &
  SERVER_PID=$!
  disown "$SERVER_PID" 2>/dev/null || true

  waited=0
  until alive; do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      echo "fleet: server exited before it became ready. Log:" >&2
      cat "$LOG" >&2
      exit 1
    fi
    # 20s: a cold boot compiles and loads the provider plugins. Bounded rather than infinite
    # so a server that comes up wedged is a failure with a log, not a hang.
    if [ "$waited" -ge 40 ]; then
      echo "fleet: server did not answer $URL/session within 20s. Log:" >&2
      cat "$LOG" >&2
      kill "$SERVER_PID" 2>/dev/null || true
      exit 1
    fi
    waited=$((waited + 1))
    sleep 0.5
  done
  echo "fleet: server ready (pid $SERVER_PID)"
fi

echo "fleet: attaching control terminal to $URL in $PROJECT"
# Deliberately NOT trapped to kill the server on exit. Leaving the grid is not the same as
# ending the work, and a control terminal that takes the fleet down when you close it is the
# behaviour this script exists to remove.
# shellcheck disable=SC2086
$OC attach "$URL" --dir "$PROJECT" || true

cat <<EOF

fleet: control terminal closed. The server is still running and your sessions are still live.
  reattach   $0 "$PROJECT" $PORT
  inspect    curl -s -H "x-opencode-directory: $PROJECT" "$URL/session?scope=project"
  stop       pkill -f "serve --port $PORT"
  log        $LOG
EOF
