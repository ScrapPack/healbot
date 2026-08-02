#!/bin/sh
# Healbot claude fleet: a crew of interactive Claude Code sessions in tmux, one captain.
#
#   ~/Desktop/healbot/harness/hb-fleet.sh <command> [args]
#
#   start [--no-nvim] [--no-grid]             preflight + up + attach. THE verb; start here
#   help                                      this card (also C-b ? inside the cockpit)
#   preflight                                 can this machine run a fleet right now?
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
# ONE-TIME interactive login first (env.claude.sh header, which also records where the
# credential lands and why the harness login does not touch the owner's). A signed-out root
# used to surface as `spawn`'s ready-wait timing out after HB_SPAWN_TIMEOUT seconds, naming
# the symptom and hiding the cause; since 2026-08-02 `preflight` reports it and `spawn`
# refuses on it in milliseconds. Resume hints below only work from a shell that sourced
# env.claude.sh — a bare `claude --resume` looks in the wrong config root.

set -eu

FLEET_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"
if [ ! -f "$FLEET_ROOT/env.claude.sh" ]; then
  echo "hb-fleet: could not locate the harness (looked in '$FLEET_ROOT')." >&2
  echo "hb-fleet: run with zsh or bash, or set HARNESS_ROOT and re-run." >&2
  exit 1
fi
REPO="$(cd "$FLEET_ROOT/.." && pwd)"
# The absolute form of $0. Anything that crosses into tmux — a key binding, the bridge pane's
# startup command — is run later, by a different process, from a directory we do not choose,
# so a relative $0 would resolve to nothing at the moment it mattered and the failure would be
# a silently empty popup rather than an error.
SELF="$FLEET_ROOT/$(basename "$0")"

HB_SOCKET="${HB_SOCKET:-healbot}"
HB_RUN="${HB_RUN:-hb-main}"
HB_FLEET_DIR="${HB_FLEET_DIR:-$REPO/.fleet/$HB_RUN}"
HB_CLAUDE="${HB_CLAUDE:-$(command -v claude || echo "$HOME/.local/bin/claude")}"  # PATH first, then the native installer's path: the old bare pin was one machine's layout, and doctor.py's claude row resolves through PATH — so the pin could be wrong while preflight said PASS
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

py() { if command -v python3 >/dev/null 2>&1; then python3 "$@"; else python "$@"; fi; }

# AUTH DETECTION. `claude auth status` is the detector, and it is the detector because three
# properties were MEASURED on 2.1.220 (2026-08-02), not assumed:
#   1. It EXITS 1 with no credential and 0 with one, so sh needs no JSON parsing. The JSON it
#      prints on stdout is a convenience for doctor.py, not the interface here.
#   2. It honours CLAUDE_CONFIG_DIR, which the env.claude.sh source above has already pointed
#      at the HARNESS root — so the answer is about the root crew actually spawn under, never
#      the owner's default. (No line citation on purpose: it would rot on the next insert.)
#   3. It does NOT read .claude.json. A config dir holding a copied profile with a complete
#      oauthAccount block still exits 1. That killed the cheaper "grep the profile" check,
#      which would have gone GREEN on exactly the state this guard exists to catch.
# It is LOCAL — unchanged behind a black-hole proxy, same ~0.2s — so it proves a credential is
# PRESENT, not that the token is live. An expired token passes here and dies at the crewmate's
# first turn; the refusal text says so rather than promising more than the check measured.
#
# Exit codes are the interface, same posture as the gate: 0 authed, 1 signed out, 2 no binary.
# A missing binary is a DIFFERENT fact from a signed-out root and must not be reported as one:
# `$HB_CLAUDE auth status` on a nonexistent path also exits non-zero, and collapsing the two
# would send the operator to a login screen that is not the problem.
hb_auth_state() {
  case "$HB_CLAUDE" in
    */*) [ -x "$HB_CLAUDE" ] || return 2 ;;
    *) command -v "$HB_CLAUDE" >/dev/null 2>&1 || return 2 ;;
  esac
  "$HB_CLAUDE" auth status >/dev/null 2>&1 || return 1
  return 0
}

hb_auth_guard() {  # loud, actionable refusal; called before anything that launches claude
  if hb_auth_state; then return 0; else rc=$?; fi
  if [ "$rc" = 2 ]; then
    echo "hb-fleet: no claude binary at '$HB_CLAUDE' — install it, or point HB_CLAUDE at it." >&2
  else
    echo "hb-fleet: the harness config root is SIGNED OUT, so every crewmate would spawn into" >&2
    echo "hb-fleet: a login screen and time out after ${HB_SPAWN_TIMEOUT}s. Fix it once, interactively:" >&2
    echo "hb-fleet:   . $FLEET_ROOT/env.claude.sh && claude      (sign in, then exit)" >&2
    echo "hb-fleet: config root: $CLAUDE_CONFIG_DIR" >&2
    echo "hb-fleet: (this checks that a credential EXISTS, not that it is unexpired — an" >&2
    echo "hb-fleet:  expired token passes here and fails at the crewmate's first turn.)" >&2
  fi
  return 1
}

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

# The range is the header's command list PLUS the selector paragraph, and it is a LINE range
# into this file: inserting a command line above shifts the paragraph and silently truncates
# the last line of it. Bumped 22 -> 23 for `preflight`, 23 -> 25 for `start`/`help`.
# probe_fleet_claude.py asserts both halves are still inside the range, so the next person
# gets a red rather than a quietly shortened header.
hb_header() { sed -n '4,25p' "$0"; }

usage() { hb_header; exit 1; }

# ONE owner for the command list: the header above. The popup, the captain's card, and
# `usage` all render THAT, so a command added to the header appears in every surface and
# cannot go stale in two of them (the prose-copy rule, citation-hygiene skill). Only the key
# map is extra here, because tmux keys are not commands and live nowhere else.
hb_help() {
  hb_header | sed 's/^#\{1,\} \{0,1\}//; s/^#$//'
  cat <<'EOF'

COCKPIT KEYS  (press the tmux prefix C-b first, then the key)
  ?    this card                 z    zoom the pane under the cursor
  0    bridge window             1    crew window
  d    detach — the fleet keeps running, reattach with `start` or `attach`
  [    scrollback (q leaves)     :    tmux command prompt

THE CAPTAIN'S SEAT is the bridge shell. To delegate rather than drive:
  claude          then  /firstmate      — the controller skill runs the crew for you
Census is `ls`, never the status bar: the bar names the fleet, `ls` counts it.
EOF
}

cmd="${1:-}"; [ -n "$cmd" ] && shift || usage

case "$cmd" in

start)
  # THE one verb: preflight, then up, then attach. The optional panes are DETECTED, not
  # flagged. `--nvim`/`--grid` were opt-in switches you had to already know existed, which is
  # how a fleet that can show you an editor and a live grid ended up presenting as a bare
  # shell. Absence is never a refusal here — a missing tool costs exactly its own pane, and
  # preflight has already named which one and why.
  NO_NVIM=0; NO_GRID=0
  while [ $# -gt 0 ]; do case "$1" in
    --no-nvim) NO_NVIM=1; shift;;
    --no-grid) NO_GRID=1; shift;;
    *) usage;;
  esac; done
  "$SELF" preflight || exit $?
  set --
  if [ "$NO_NVIM" = 0 ] && command -v nvim >/dev/null 2>&1; then
    set -- "$@" --nvim
  fi
  if [ "$NO_GRID" = 0 ] && [ -f "$REPO/opencode/packages/opencode/src/index.ts" ] \
     && command -v bun >/dev/null 2>&1; then
    set -- "$@" --grid
  fi
  "$SELF" up "$@"
  # Attaching from inside tmux is the one thing `start` will not do: tmux refuses to nest and
  # the error it prints describes tmux's rule rather than the operator's situation. The fleet
  # is already up by this point, so this is a report, not a failure.
  if [ -n "${TMUX:-}" ]; then
    echo "hb-fleet: fleet '$HB_RUN' is up, but this shell is already inside tmux."
    echo "hb-fleet: detach first (C-b d) and re-run, or from another terminal: $SELF attach"
    exit 0
  fi
  exec "$SELF" attach
  ;;

help)
  hb_help
  ;;

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
    # The bridge pane prints the captain's card once and then EXECS an ordinary shell, so the
    # card is a login banner rather than a process sitting in the captain's way. It is here,
    # in the creation branch only, because a re-run of `up` or `start` must not redraw it over
    # work in progress — the same reason `up` reuses a live session instead of rebuilding it.
    t -f /dev/null new-session -d -s "$HB_RUN" -n bridge -x 220 -y 50 -c "$REPO" \
      -- sh -c "'$SELF' help; exec \"\${SHELL:-/bin/sh}\""
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

  # THE COCKPIT'S ONLY ALWAYS-VISIBLE AFFORDANCE. Stock tmux says nothing about what this
  # session is or how to drive it, which is most of why a running fleet read as a bare shell:
  # the help lived in a README nobody had open. SESSION-scoped, same reasoning as the
  # pane-died hook (guardrail 6) — a second fleet on this socket must not wear this one's name.
  #
  # Deliberately NO crew count. A number in a permanently visible surface has to be right
  # every second or it manufactures exactly the wrong belief this repo spends its effort
  # removing, and every cheap version is wrong for part of a fleet's life: live panes count
  # the placeholder shell before the first spawn, manifest rows count crewmates that have
  # since died. `ls` owns the census, is exact, and is one keystroke away.
  t set -t "$HB_RUN" status on
  t set -t "$HB_RUN" status-interval 5
  t set -t "$HB_RUN" status-style "bg=colour236,fg=colour252"
  t set -t "$HB_RUN" status-left " #[bold]#S#[nobold] @ $HB_SOCKET "
  t set -t "$HB_RUN" status-left-length 48
  t set -t "$HB_RUN" status-right " C-b  ?:help  z:zoom  0:bridge  1:crew  d:detach "
  t set -t "$HB_RUN" status-right-length 64

  # Key bindings are SERVER-global in tmux — there is no session-scoped key table — so this
  # one is shared by every fleet on this socket. That is acceptable here and ONLY here,
  # because the popup renders static text out of this script and carries no per-fleet state;
  # anything fleet-specific must not be bound this way. Without -E the popup stays up until
  # it is dismissed (q or Escape), which is what makes it readable rather than a flash.
  # `?` shadows tmux's default list-keys binding, so the card names `:` to keep the full
  # binding list one prompt away.
  t unbind -T prefix '?' 2>/dev/null || true
  t bind -T prefix '?' display-popup -w 84 -h 28 "'$SELF' help"

  t list-windows -t "$HB_RUN" -F '#{window_name}' | grep -qx crew || \
    t new-window -d -t "$HB_RUN" -n crew -c "$REPO"

  # Optional panes carry a PANE-SCOPED marker (`@hb_role`) rather than being recognised by
  # title or current command: nvim rewrites its own pane title through the terminal, and the
  # grid pane's command is whatever fleet.sh ends up exec'ing. Without a marker, every re-run
  # of `up` — and so every `start` — splits another copy of both panes.
  hb_has_role() { t list-panes -t "$HB_RUN:bridge" -F '#{@hb_role}' 2>/dev/null | grep -qx "$1"; }
  hb_add_pane() {  # hb_add_pane <role> <split-flag> <command...>
    role="$1"; flag="$2"; shift 2
    hb_has_role "$role" && return 0
    pane="$(t split-window "$flag" -d -t "$HB_RUN:bridge" -c "$REPO" -P -F '#{pane_id}' -- "$@")"
    t set -p -t "$pane" @hb_role "$role"
  }

  if [ "$WANT_NVIM" = 1 ] && command -v nvim >/dev/null 2>&1; then
    hb_add_pane nvim -h nvim
  fi
  if [ "$WANT_GRID" = 1 ]; then
    # The opencode fleet grid as a viewport pane. fleet.sh's server is nohup'd/disowned by
    # its own design, so this pane is disposable — killing it never kills that fleet.
    hb_add_pane grid -v "$FLEET_ROOT/fleet.sh"
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
  # Before the pool lease, not after: a --slot spawn that cannot possibly come up must not
  # first take a worktree off the pool. This is also the whole reason the detector exists —
  # without it a signed-out root costs HB_SPAWN_TIMEOUT seconds of ready-wait per crewmate
  # and reports "timed out", which names the symptom and hides the cause (script header, AUTH).
  hb_auth_guard || exit 2
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

preflight)
  # What this machine can carry for a fleet run, before anything is built. Deliberately NOT a
  # second doctor.py: doctor answers "is this a working healbot checkout", this answers "can
  # `up` + `spawn` succeed right now", and auth is the row only this one can ask (doctor is
  # stdlib-only and must not source env.claude.sh — this script already did, at line 89).
  # Blockers exit 2, matching the gate's "a check ran and said no"; advisories never fail the
  # command, because every one of them costs only an optional pane.
  BLOCKED=0
  say() { printf '  [%-5s] %s\n' "$1" "$2"; }
  echo "hb-fleet preflight — fleet '$HB_RUN' on socket '$HB_SOCKET'"

  if hb_auth_state; then
    say OK "claude authed at $CLAUDE_CONFIG_DIR (credential present; liveness unproven)"
  else
    case $? in
      2) say BLOCK "no claude binary at '$HB_CLAUDE' — install it, or set HB_CLAUDE";;
      *) say BLOCK "claude is SIGNED OUT at $CLAUDE_CONFIG_DIR — . $FLEET_ROOT/env.claude.sh && claude";;
    esac
    BLOCKED=1
  fi

  if command -v tmux >/dev/null 2>&1; then
    TV="$(tmux -V 2>/dev/null | tr -dc '0-9.' | cut -d. -f1,2)"
    case "$TV" in
      [0-9]*.[0-9]*)
        # display-popup landed in tmux 3.2; below that the help overlay is the only casualty.
        if [ "${TV%%.*}" -gt 3 ] || { [ "${TV%%.*}" = 3 ] && [ "${TV#*.}" -ge 2 ]; }; then
          say OK "tmux $TV (display-popup available, so the help overlay works)"
        else
          say WARN "tmux $TV is below 3.2 — no display-popup, so '?' prints to the pane instead"
        fi;;
      *) say WARN "tmux present but its version did not parse ('$(tmux -V 2>&1)') — assuming no popup";;
    esac
  else
    say BLOCK "tmux missing — the fleet IS tmux (on a PC that means WSL2, docs/WINDOWS.md)"
    BLOCKED=1
  fi

  if command -v nvim >/dev/null 2>&1; then
    say OK "nvim present — the editor pane can be built"
  else
    say WARN "nvim missing — skipping the editor pane (nothing else is affected)"
  fi

  if [ -f "$REPO/opencode/packages/opencode/src/index.ts" ] && command -v bun >/dev/null 2>&1; then
    say OK "opencode checkout + bun — the grid pane can be built"
  else
    say WARN "no opencode checkout or no bun — skipping the grid pane (fork/README.md rebuilds it)"
  fi

  if [ -x "$VENVPY" ]; then
    say OK "rig venv present — 'spawn --slot' can lease a pool worktree"
  else
    say WARN "rig venv absent — 'spawn --slot' will fail; pass --dir explicitly (.carryover/verified/README.md)"
  fi

  [ "$BLOCKED" = 0 ] || { echo "hb-fleet: preflight BLOCKED — fix the rows above, then re-run." >&2; exit 2; }
  echo "hb-fleet: preflight clear."
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
