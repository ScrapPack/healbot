#!/bin/sh
# Healbot claude fleet: a crew of interactive Claude Code sessions in tmux, one captain.
#
#   ~/Desktop/healbot/harness/hb-fleet.sh <command> [args]
#
#   up    [--nvim] [--grid]                   bring the fleet session up (idempotent)
#   spawn <name> --dir DIR [--model M] [--brief FILE] [--slot]
#   ls                                        census: manifest x live panes
#   state [name]                              per-crew state (hook channel + screen check)
#   send  <name> <text...> [--force]          type into a crewmate (single line)
#   brief <name> <file>                       paste a multi-line brief, then submit
#   peek  <name> [lines]                      tail of the crewmate's screen
#   occupancy <name>                          live context occupancy from the transcript
#   attach                                    attach the control terminal
#   kill  <name>                              kill one crewmate pane (manifest-resolved only)
#   down                                      kill the fleet session (transcripts survive)
#
# Selectors are ENVIRONMENT, not flags, so they hold across invocations: HB_SOCKET (tmux
# server, default healbot) and HB_RUN (session name, default hb-main). A `--run` flag
# existed for one draft and was removed after review: it mutated only the `up` process, so
# every later subcommand silently addressed the DEFAULT fleet — cross-fleet contamination
# with no warning. `HB_RUN=x hb-fleet.sh <anything>` is the supported form.
#
# ARCHITECTURE. One tmux server per machine on its own socket (-L), one session per fleet
# run, two windows: "bridge" (captain shell, optional nvim pane, optional opencode grid
# pane) and "crew" (one pane per crewmate, tiled). Every mechanism here was tested on this
# machine before it was written down — the record is docs/SHIP.md §3; the guardrails that
# are assertions, not prose, live in probe_fleet_claude.py. The shape follows firstmate's
# tmux backend contract (bounded capture, type-once-retry-Enter, five-state liveness,
# fail-closed kill), reimplemented not vendored — same posture as harness/pool.py's
# treehouse verdict: borrowed vocabulary, rejected isolation model, zero third-party code.
#
# WHY TMUX AND NOT fleet.sh's nohup DANCE: pane processes are children of the daemonized
# tmux server, so they survive terminal close natively — the guarantee fleet.sh had to
# hand-build with nohup+disown+</dev/null for opencode serve. Do not add nohup inside
# panes; it is redundant and hides exit codes from remain-on-exit.
#
# THE LOAD-BEARING GUARDRAILS (each measured, each probed):
#   1. Panes are addressed by immutable pane id (%N), never index — select-layout tiled
#      RENUMBERS indexes out of creation order.
#   2. Prompt text goes through send-keys -l -- (literal), then a separate Enter.
#   3. Never send blind after spawn: a TUI that flushes its tty input at startup discards
#      early keys WHILE ECHOING THEM. Wait for the ready marker.
#   4. synchronize-panes stays off and is pinned at bootstrap.
#   5. history-limit binds per pane AT CREATION — set before any crew pane exists.
#   6. Panes inherit the tmux SERVER's start environment, not the caller's (TESTED by the
#      phase review) — so HB_FLEET_DIR is injected per pane with split-window -e, never
#      assumed from the server. The pane-died hook is SESSION-scoped for the same reason.
#   7. spawn never respawns an existing pane. The placeholder shell the crew window is
#      born with is killed AFTER a successful split; a full window is a loud refusal.
#      The first draft respawned `head -1` on split failure — the review TESTED that
#      split failure means WINDOW FULL, not first-spawn, and that respawn-pane -k on a
#      live pane silently kills a crewmate mid-turn.
#
# STATE CHANNEL. harness/claude/hooks/fleet-state.sh writes $HB_FLEET_DIR/state/<sid>.json
# on SessionStart/Stop/Notification (push); `state` merges that with a bounded screen
# capture (poll backstop). Screen markers are version-dependent and SUSPECTED until pinned
# against a live crewmate — override via HB_READY_MARKER / HB_BUSY_MARKER / HB_TRUST_MARKER
# and record the pinned strings in docs/SHIP.md when the first crew comes up.
#
# AUTH. Crew sessions run under CLAUDE_CONFIG_DIR = harness/claude, which needs its
# ONE-TIME interactive login first (env.claude.sh header). A signed-out crewmate is the
# first thing `spawn`'s ready-wait will fail on. Resume hints below only work from a shell
# that sourced env.claude.sh — a bare `claude --resume` looks in the wrong config root.

set -eu

FLEET_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"
if [ ! -f "$FLEET_ROOT/env.claude.sh" ]; then
  echo "hb-fleet: could not locate the harness (looked in '$FLEET_ROOT')." >&2
  echo "hb-fleet: run with zsh or bash, or set HARNESS_ROOT and re-run." >&2
  exit 1
fi
REPO="$(cd "$FLEET_ROOT/.." && pwd)"

HB_SOCKET="${HB_SOCKET:-healbot}"
HB_RUN="${HB_RUN:-hb-main}"
HB_FLEET_DIR="${HB_FLEET_DIR:-$REPO/.fleet/$HB_RUN}"
HB_CLAUDE="${HB_CLAUDE:-$HOME/.local/bin/claude}"
HB_READY_MARKER="${HB_READY_MARKER:-bypass permissions on}"  # footer line under the bypass default (MEASURED 2026-08-01)
HB_BUSY_MARKER="${HB_BUSY_MARKER:-esc to interrupt}"   # spinner line (SUSPECTED, pin at bring-up)
HB_TRUST_MARKER="${HB_TRUST_MARKER:-trust}"            # first-launch trust dialog (SUSPECTED)
HB_SPAWN_TIMEOUT="${HB_SPAWN_TIMEOUT:-90}"
MANIFEST="$HB_FLEET_DIR/manifest.jsonl"
VENVPY="$REPO/.carryover/verified/venv/bin/python"

export HB_FLEET_DIR
# shellcheck source=./env.claude.sh
HARNESS_ROOT="$FLEET_ROOT" . "$FLEET_ROOT/env.claude.sh"

t() { tmux -L "$HB_SOCKET" "$@"; }

py() { python3 "$@"; }

# Manifest: one JSON line per spawn — {name, pane, dir, sid, transcript, model, at}.
# The durable join between tmux, the worktree, and the claude session; it survives
# everything tmux does not. Lives outside the worktrees, mirroring pool.py's rule that
# leases never live inside a slot. All values cross into python as ARGV, never spliced
# into source — a path with a quote must not be able to break or inject (review finding).
manifest_get() {  # manifest_get <name> <field>
  py - "$MANIFEST" "$1" "$2" <<'PY'
import json, sys
path, name, field = sys.argv[1:4]
row = None
try:
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d.get("name") == name:
                row = d  # last write wins: a respawned name supersedes its ancestor
except FileNotFoundError:
    pass
if row is None or row.get(field) is None:
    sys.exit(3)
print(row[field])
PY
}

manifest_names() {
  [ -f "$MANIFEST" ] || return 0
  py - "$MANIFEST" <<'PY'
import json, sys
seen = {}
for line in open(sys.argv[1]):
    line = line.strip()
    if line:
        seen[json.loads(line)["name"]] = 1
print(" ".join(seen))
PY
}

manifest_has_pane() {  # exit 0 if any row claims this pane id
  [ -f "$MANIFEST" ] || return 1
  py - "$MANIFEST" "$1" <<'PY'
import json, sys
for line in open(sys.argv[1]):
    line = line.strip()
    if line and json.loads(line).get("pane") == sys.argv[2]:
        sys.exit(0)
sys.exit(1)
PY
}

resolve_pane() {  # fail-closed: manifest only, never a tmux name search. A "successful"
  # send to a guessed pane is worse than a loud failure (firstmate's fm-send rule,
  # docs/SHIP.md §3), so an unknown name refuses here.
  manifest_get "$1" pane || { echo "hb-fleet: unknown crewmate '$1' (not in $MANIFEST)" >&2; exit 2; }
}

pane_dead() {  # 0 = dead or missing, 1 = alive pane
  state="$(t list-panes -t "$HB_RUN:crew" -F '#{pane_id} #{pane_dead}' 2>/dev/null | awk -v p="$1" '$1==p{print $2}')"
  [ "$state" = "1" ] || { [ -n "$state" ] && return 1; }
  return 0
}

usage() { sed -n '4,22p' "$0"; exit 1; }

cmd="${1:-}"; [ -n "$cmd" ] && shift || usage

case "$cmd" in

up)
  WANT_NVIM=0; WANT_GRID=0
  while [ $# -gt 0 ]; do case "$1" in
    --nvim) WANT_NVIM=1; shift;;
    --grid) WANT_GRID=1; shift;;
    *) usage;;
  esac; done
  mkdir -p "$HB_FLEET_DIR/state" "$HB_FLEET_DIR/briefs" "$HB_FLEET_DIR/raw"

  if t has-session -t "$HB_RUN" 2>/dev/null; then
    echo "hb-fleet: reusing session $HB_RUN on socket $HB_SOCKET"
  else
    # -f /dev/null: the user's ~/.tmux.conf must not leak keybinds/hooks into fleet
    # behaviour. -x/-y: a detached session's panes otherwise default small.
    t -f /dev/null new-session -d -s "$HB_RUN" -n bridge -x 220 -y 50 -c "$REPO"
  fi

  # Options are re-asserted on every `up`, not only first creation: the server auto-exits
  # with its last session and takes every global option with it (TESTED), so bootstrap
  # must be idempotent. Order matters for history-limit (guardrail 5).
  t set -g history-limit 100000
  t set -g remain-on-exit on
  t set -g synchronize-panes off
  t set -g mouse on
  t set -g focus-events on
  t set -g pane-border-status top
  t set -g pane-border-format ' #{pane_index}:#{pane_title}#{?pane_dead, [DEAD #{pane_dead_status}],} '
  t set -g set-titles on
  t set -g set-titles-string '#S #{pane_title}'
  # SESSION-scoped (guardrail 6): a global hook is rewritten by every run's `up`, so with
  # two fleets on one socket the last `up` would claim every death. No % or #{} beyond
  # tmux's own in the shell string — tmux expands formats first (TESTED). The path is
  # single-quoted inside the run-shell string; pane titles are kebab-validated names.
  t set-hook -t "$HB_RUN" pane-died "run-shell \"echo died #{hook_pane} #{pane_title} >> '$HB_FLEET_DIR/deaths.log'\""

  t list-windows -t "$HB_RUN" -F '#{window_name}' | grep -qx crew || \
    t new-window -d -t "$HB_RUN" -n crew -c "$REPO"

  if [ "$WANT_NVIM" = 1 ] && command -v nvim >/dev/null 2>&1; then
    t split-window -d -h -t "$HB_RUN:bridge" -c "$REPO" -- nvim
  fi
  if [ "$WANT_GRID" = 1 ]; then
    # The opencode fleet grid as a viewport pane. fleet.sh's server is nohup'd/disowned by
    # its own design, so this pane is disposable — killing it never kills that fleet.
    t split-window -d -v -t "$HB_RUN:bridge" -c "$REPO" -- "$FLEET_ROOT/fleet.sh"
  fi
  if [ "$HB_RUN" = "hb-main" ]; then
    echo "hb-fleet: up. attach with: $0 attach   (state dir: $HB_FLEET_DIR)"
  else
    echo "hb-fleet: up. This is fleet '$HB_RUN' — every later command needs the selector:"
    echo "hb-fleet:   HB_RUN=$HB_RUN $0 attach     (state dir: $HB_FLEET_DIR)"
  fi
  ;;

spawn)
  NAME="${1:-}"; [ -n "$NAME" ] || usage; shift
  # Kebab-only names (arms.define's rule): they become pane titles, hook-string text, and
  # python argv, so the validation here is what makes those layers quote-safe.
  case "$NAME" in *[!a-z0-9-]*|-*) echo "hb-fleet: crew name must be lowercase kebab-case: '$NAME'" >&2; exit 2;; esac
  DIR=""; MODEL=""; BRIEF=""; USE_SLOT=0
  while [ $# -gt 0 ]; do case "$1" in
    --dir) DIR="$2"; shift 2;;
    --model) MODEL="$2"; shift 2;;
    --brief) BRIEF="$2"; shift 2;;
    --slot) USE_SLOT=1; shift;;
    *) usage;;
  esac; done
  t has-session -t "$HB_RUN" 2>/dev/null || { echo "hb-fleet: no session — run '$0 up' first" >&2; exit 2; }
  if manifest_get "$NAME" pane >/dev/null 2>&1; then
    P="$(manifest_get "$NAME" pane)"
    if ! pane_dead "$P"; then
      echo "hb-fleet: crewmate '$NAME' already live at $P — kill it first or pick a new name" >&2
      exit 2
    fi
  fi
  if [ "$USE_SLOT" = 1 ]; then
    DIR="$("$VENVPY" "$FLEET_ROOT/pool.py" acquire --owner "$HB_RUN" --purpose "crew $NAME" | tail -1)"
  fi
  [ -d "${DIR:-}" ] || { echo "hb-fleet: --dir does not exist: '$DIR'" >&2; exit 2; }
  DIR="$(cd "$DIR" && pwd)"

  SID="$(uuidgen | tr 'A-Z' 'a-z')"

  # Guardrail 7: never respawn an existing pane. Identify the placeholder (a bare shell
  # no manifest row claims) so it can be killed AFTER a successful split; if the split
  # fails with a placeholder present, reclaim that space and retry ONCE; otherwise the
  # window is genuinely full and the refusal is loud.
  PLACEHOLDER=""
  for row in $(t list-panes -t "$HB_RUN:crew" -F '#{pane_id}:#{pane_current_command}' 2>/dev/null); do
    case "${row##*:}" in
      sh|bash|zsh|dash)
        if ! manifest_has_pane "${row%%:*}"; then PLACEHOLDER="${row%%:*}"; break; fi;;
    esac
  done
  set -- --session-id "$SID" -n "$NAME"
  [ -n "$MODEL" ] && set -- "$@" --model "$MODEL"
  spawn_split() {  # guardrail 6: the pane gets THIS run's HB_FLEET_DIR explicitly
    t split-window -t "$HB_RUN:crew" -c "$DIR" -e "HB_FLEET_DIR=$HB_FLEET_DIR" \
      -P -F '#{pane_id}' -- "$HB_CLAUDE" "$@"
  }
  if ! PANE="$(spawn_split "$@" 2>/dev/null)"; then
    if [ -n "$PLACEHOLDER" ]; then
      t kill-pane -t "$PLACEHOLDER"; PLACEHOLDER=""
      PANE="$(spawn_split "$@")" || { echo "hb-fleet: crew window cannot fit another pane even after reclaiming the placeholder — kill a crewmate or start a second fleet (HB_RUN=...)" >&2; exit 2; }
    else
      echo "hb-fleet: crew window is full (split-window refused) — kill a crewmate or start a second fleet (HB_RUN=...)" >&2
      exit 2
    fi
  fi
  if [ -n "$PLACEHOLDER" ]; then
    t kill-pane -t "$PLACEHOLDER"
  fi
  t select-layout -t "$HB_RUN:crew" tiled
  t select-pane -t "$PANE" -T "$NAME"

  # Transcript path is knowable BEFORE the session exists because we chose the uuid, and
  # backend.transcript_path owns the slug rule AND honors CLAUDE_CONFIG_DIR — crew
  # transcripts land under the REDIRECTED root, not ~/.claude (review finding; SHIP.md §3).
  TRANSCRIPT="$("$VENVPY" - "$SID" "$DIR" "$REPO" <<'PY'
import sys
sys.path.insert(0, sys.argv[3] + "/.carryover/verified")
import backend
print(backend.transcript_path(sys.argv[1], sys.argv[2]))
PY
)"

  py - "$MANIFEST" "$NAME" "$PANE" "$DIR" "$SID" "$TRANSCRIPT" "${MODEL:-settings-pin}" <<'PY'
import json, sys, time
path, name, pane, d, sid, transcript, model = sys.argv[1:8]
row = {"name": name, "pane": pane, "dir": d, "sid": sid,
       "transcript": transcript, "model": model, "at": int(time.time())}
with open(path, "a") as f:
    f.write(json.dumps(row) + "\n")
PY

  # Guardrail 3: wait for the ready marker (or surface the trust dialog) before declaring
  # the crewmate spawnable-into. Timeout is loud, never silent.
  waited=0
  while :; do
    SCREEN="$(t capture-pane -p -t "$PANE" 2>/dev/null || true)"
    case "$SCREEN" in
      *"$HB_TRUST_MARKER"*) echo "hb-fleet: $NAME is at the first-launch trust dialog — attach and answer it once for this directory"; break;;
      *"$HB_READY_MARKER"*) echo "hb-fleet: $NAME ready at $PANE (sid $SID)"; break;;
    esac
    if pane_dead "$PANE"; then
      echo "hb-fleet: $NAME's pane died during boot — the corpse:" >&2
      t capture-pane -p -t "$PANE" | tail -15 >&2
      exit 1
    fi
    waited=$((waited + 1))
    if [ "$waited" -ge $((HB_SPAWN_TIMEOUT * 2)) ]; then
      echo "hb-fleet: $NAME showed neither ready ('$HB_READY_MARKER') nor trust ('$HB_TRUST_MARKER') in ${HB_SPAWN_TIMEOUT}s." >&2
      echo "hb-fleet: markers are version-dependent — attach, read the pane, and pin HB_READY_MARKER (docs/SHIP.md §3)." >&2
      exit 1
    fi
    sleep 0.5
  done

  if [ -n "$BRIEF" ]; then
    exec "$0" brief "$NAME" "$BRIEF"
  fi
  exit 0
  ;;

ls)
  echo "== manifest ($MANIFEST) =="
  if [ -f "$MANIFEST" ]; then cat "$MANIFEST"; else echo "(empty)"; fi
  echo "== live panes =="
  t list-panes -t "$HB_RUN:crew" -F '#{pane_id} #{pane_title} #{pane_dead} #{pane_current_command} #{pane_current_path}' 2>/dev/null \
    || echo "(no crew window — run '$0 up')"
  ;;

state)
  # Five-state liveness vocabulary (alive/dead/missing/unreadable/ambiguous) borrowed from
  # firstmate's backend contract; only dead/missing would justify automated recovery,
  # because a false dead reading launches a duplicate agent (docs/SHIP.md §3).
  if [ $# -gt 0 ]; then NAMES="$1"; else NAMES="$(manifest_names)"; fi
  if [ -z "$NAMES" ]; then
    echo "hb-fleet: no crewmates yet (nothing in $MANIFEST)"
    exit 0
  fi
  for NAME in $NAMES; do
    P="$(manifest_get "$NAME" pane 2>/dev/null || true)"
    SID="$(manifest_get "$NAME" sid 2>/dev/null || true)"
    if [ -z "$P" ]; then echo "$NAME: missing (no manifest row)"; continue; fi
    ROW="$(t list-panes -t "$HB_RUN:crew" -F '#{pane_id} #{pane_dead} #{pane_current_command}' 2>/dev/null | awk -v p="$P" '$1==p')"
    if [ -z "$ROW" ]; then LIVE="missing"
    elif [ "$(echo "$ROW" | awk '{print $2}')" = "1" ]; then LIVE="dead"
    else case "$(echo "$ROW" | awk '{print $3}')" in
           *claude*|node|bun) LIVE="alive";;
           sh|bash|zsh|dash|"") LIVE="dead";;
           *) LIVE="ambiguous";;
         esac
    fi
    HOOKSTATE="no hook events"
    if [ -n "$SID" ] && [ -f "$HB_FLEET_DIR/state/$SID.json" ]; then
      HOOKSTATE="$(py - "$HB_FLEET_DIR/state/$SID.json" <<'PY' 2>/dev/null || echo "unreadable state file"
import json, sys, time
d = json.load(open(sys.argv[1]))
print(d["event"], str(int(time.time()) - d["at"]) + "s ago")
PY
)"
    fi
    SCREEN="$(t capture-pane -p -t "$P" 2>/dev/null | tail -20 || true)"
    case "$SCREEN" in
      *"$HB_BUSY_MARKER"*)  SCR="busy";;
      *"$HB_TRUST_MARKER"*) SCR="trust-dialog";;
      *"$HB_READY_MARKER"*) SCR="idle";;
      *)                    SCR="unreadable";;
    esac
    echo "$NAME: $LIVE | screen: $SCR | hooks: $HOOKSTATE | pane $P sid ${SID:-?}"
  done
  ;;

send)
  NAME="${1:-}"; [ -n "$NAME" ] || usage; shift
  FORCE=0; TEXT=""
  for a in "$@"; do
    if [ "$a" = "--force" ]; then FORCE=1; else TEXT="${TEXT:+$TEXT }$a"; fi
  done
  [ -n "$TEXT" ] || usage
  P="$(resolve_pane "$NAME")"
  pane_dead "$P" && { echo "hb-fleet: $NAME's pane is dead — respawn with 'spawn' or read the corpse with 'peek'" >&2; exit 2; }
  if [ "$FORCE" != 1 ]; then
    SCREEN="$(t capture-pane -p -t "$P" | tail -20)"
    case "$SCREEN" in *"$HB_BUSY_MARKER"*)
      echo "hb-fleet: $NAME looks busy ('$HB_BUSY_MARKER' on screen). --force to interrupt-and-queue anyway." >&2
      exit 2;;
    esac
  fi
  # Guardrail 2, and firstmate's submit rule: type ONCE (-l literal, -- so a leading dash
  # is text not a flag), then retry Enter only — retyping double-feeds a slow composer.
  t send-keys -t "$P" -l -- "$TEXT"
  t send-keys -t "$P" Enter
  # Submit verification is honest about its limit: capture-pane returns RENDERED lines, so
  # text longer than the pane width wraps and can never match a substring check (review
  # finding). Short sends are verified; long ones say so instead of claiming success.
  if [ "${#TEXT}" -le 60 ]; then
    tries=0
    while [ $tries -lt 2 ]; do
      sleep 1
      case "$(t capture-pane -p -t "$P" | tail -3)" in
        *"$TEXT"*) t send-keys -t "$P" Enter; tries=$((tries + 1));;
        *) break;;
      esac
    done
    if [ $tries -ge 2 ]; then
      echo "hb-fleet: typed into $NAME but the composer did not provably clear — peek it" >&2
      exit 1
    fi
    echo "hb-fleet: sent to $NAME"
  else
    echo "hb-fleet: typed into $NAME (submit unverified for long text — 'peek $NAME' to confirm)"
  fi
  ;;

brief)
  NAME="${1:-}"; FILE="${2:-}"; [ -n "$NAME" ] && [ -f "${FILE:-}" ] || usage
  P="$(resolve_pane "$NAME")"
  pane_dead "$P" && { echo "hb-fleet: $NAME's pane is dead" >&2; exit 2; }
  # Multi-line channel: bracketed paste keeps embedded newlines from submitting early;
  # the single Enter afterwards submits the whole brief.
  t load-buffer -b hbbrief - < "$FILE"
  t paste-buffer -p -b hbbrief -t "$P"
  sleep 0.5
  t send-keys -t "$P" Enter
  cp "$FILE" "$HB_FLEET_DIR/briefs/$NAME-$(date +%Y%m%d-%H%M%S).md" 2>/dev/null || true
  echo "hb-fleet: briefed $NAME from $FILE"
  ;;

peek)
  NAME="${1:-}"; [ -n "$NAME" ] || usage
  P="$(resolve_pane "$NAME")"
  t capture-pane -p -t "$P" | grep -v '^[[:space:]]*$' | tail -"${2:-25}"
  ;;

occupancy)
  NAME="${1:-}"; [ -n "$NAME" ] || usage
  SID="$(manifest_get "$NAME" sid)" || { echo "hb-fleet: unknown crewmate '$NAME' (not in $MANIFEST)" >&2; exit 2; }
  DIR="$(manifest_get "$NAME" dir)" || { echo "hb-fleet: manifest row for '$NAME' has no dir" >&2; exit 2; }
  # backend.py owns occupancy (mirrors the opencode gate's occupancyOf, probe-asserted)
  # and honors CLAUDE_CONFIG_DIR, so this reads the redirected root the crew writes to.
  # The transcript is the authoritative read channel, never the screen.
  "$VENVPY" - "$SID" "$DIR" "$REPO" <<'PY'
import os
import sys

sys.path.insert(0, sys.argv[3] + "/.carryover/verified")
import backend

path = backend.transcript_path(sys.argv[1], sys.argv[2])
if not os.path.exists(path):
    print("no transcript yet at " + path)
    sys.exit(0)
msgs = backend.normalize(backend.read_transcript(sys.argv[1], sys.argv[2]), sys.argv[1])
last = next((m for m in reversed(msgs) if m["info"]["role"] == "assistant"), None)
print(backend.occupancy(last["info"]["tokens"]) if last else 0)
PY
  ;;

attach)
  exec tmux -L "$HB_SOCKET" attach -t "$HB_RUN"
  ;;

kill)
  NAME="${1:-}"; [ -n "$NAME" ] || usage
  P="$(resolve_pane "$NAME")"
  SID="$(manifest_get "$NAME" sid 2>/dev/null || echo '?')"
  t kill-pane -t "$P"
  echo "hb-fleet: killed $NAME ($P). Its transcript survives; resume from an env.claude.sh shell: claude --resume $SID"
  ;;

down)
  t kill-session -t "$HB_RUN" 2>/dev/null || true
  echo "hb-fleet: session $HB_RUN down. kill-session is SIGHUP — in-flight turns aborted, transcripts intact."
  echo "hb-fleet: resume any crewmate from an env.claude.sh shell: claude --resume <sid> (see $MANIFEST)"
  ;;

*) usage;;
esac
