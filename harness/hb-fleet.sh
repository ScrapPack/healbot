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
# capture (poll backstop). All three events are MEASURED firing with the expected stdin
# shape, and all three screen markers are MEASURED against a live crewmate — ready on
# 2026-08-01, busy and trust on 2026-08-03 (claude 2.1.220; docs/SHIP.md §5). Two dates
# because they were two sessions, and the ready pin predates the version being recorded.
# Markers stay version-dependent, so a CLI upgrade re-opens them: override via
# HB_READY_MARKER / HB_BUSY_MARKER / HB_TRUST_MARKER, and re-pin against a live crewmate
# rather than by reading release notes. Each default's own comment carries what it was
# measured against.
#
# AUTH. Crew sessions run under CLAUDE_CONFIG_DIR = harness/claude, which needs its
# ONE-TIME interactive login first (env.claude.sh header, which also records where the
# credential lands and why the harness login does not touch the owner's). A signed-out root
# used to surface as `spawn`'s ready-wait timing out after HB_SPAWN_TIMEOUT seconds, naming
# the symptom and hiding the cause; since 2026-08-02 `preflight` reports it and `spawn`
# refuses on it in milliseconds. The same detector call also contains the CLI's one-time
# settings migration in a fresh root and leaves the root STAMPED (hb_auth_state), so the
# crew panes — and the login the refusal prescribes — start clean. Resume hints below only
# work from a shell that sourced env.claude.sh — a bare `claude --resume` looks in the
# wrong config root.

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
# MEASURED 2026-08-03 on claude 2.1.220, against a live crewmate, both directions:
# present mid-turn and ABSENT at idle, which is what makes it discriminate. The busy
# footer also carries HB_READY_MARKER, so the screen case below MUST test busy before
# ready — that arm order is load-bearing, not stylistic.
HB_BUSY_MARKER="${HB_BUSY_MARKER:-esc to interrupt}"
# The trust dialog's menu item, verbatim. The old default was the bare word "trust",
# which MEASURED as a false positive the same day: an idle crewmate that merely SAID the
# word ("I trust this result.") classified as trust-dialog, i.e. as blocked on a human
# decision — and the crew constraints file itself uses the word twice, so the prose that
# trips it is prose the harness ships. The menu item cannot appear in a reply that is not
# quoting the dialog.
HB_TRUST_MARKER="${HB_TRUST_MARKER:-Yes, I trust this folder}"
HB_SPAWN_TIMEOUT="${HB_SPAWN_TIMEOUT:-90}"
MANIFEST="$HB_FLEET_DIR/manifest.jsonl"
VENVPY="$REPO/.carryover/verified/venv/bin/python"

export HB_FLEET_DIR
# shellcheck source=./env.claude.sh
HARNESS_ROOT="$FLEET_ROOT" . "$FLEET_ROOT/env.claude.sh"

t() { tmux -L "$HB_SOCKET" "$@"; }

py() { if command -v python3 >/dev/null 2>&1; then python3 "$@"; else python "$@"; fi; }

# display-popup landed in tmux 3.2. One predicate, shared by `up` (which `?` binding to
# install) and `preflight` (which behavior to promise): split in two, the promise and the
# binding drift independently (the 5db6d96 push's review caught them already split). An
# unparsable version returns 1, so both callers take the pane fallback together.
#
# The parse takes the FIRST major.minor token and drops everything after it, so a
# pre-release like "3.1-rc3" is 3.1, not the 3.13 a digits-only strip produced (the
# 8ee08a8 push's review). TV_PROBE is left set for preflight's report lines: one parse,
# one displayed truth.
tmux_has_popup() {
  TV_PROBE="$(tmux -V 2>/dev/null | sed -n 's/^tmux[^0-9]*\([0-9][0-9]*\.[0-9][0-9]*\).*$/\1/p')"
  case "$TV_PROBE" in
    [0-9]*.[0-9]*) [ "${TV_PROBE%%.*}" -gt 3 ] || { [ "${TV_PROBE%%.*}" = 3 ] && [ "${TV_PROBE#*.}" -ge 2 ]; };;
    *) return 1;;
  esac
}

# AUTH DETECTION. `claude auth status` is the detector, and it is the detector because four
# properties were MEASURED on 2.1.220 (2026-08-02), not assumed:
#   1. It EXITS 1 with no credential and 0 with one, so sh needs no JSON parsing. The JSON it
#      prints on stdout is a convenience for doctor.py, not the interface here.
#   2. It honours CLAUDE_CONFIG_DIR, which the env.claude.sh source above has already pointed
#      at the HARNESS root — so the answer is about the root crew actually spawn under, never
#      the owner's default. (No line citation on purpose: it would rot on the next insert.)
#   3. It does NOT read .claude.json. A config dir holding a copied profile with a complete
#      oauthAccount block still exits 1. That killed the cheaper "grep the profile" check,
#      which would have gone GREEN on exactly the state this guard exists to catch.
#   4. In an UNSTAMPED root it FIRES the CLI's one-time settings migration (HARNESS.md
#      Traps): the ladder, gated on `migrationVersion` in the untracked .claude.json,
#      rewrites the TRACKED settings.json — 2.1.220's step 13 flips exactly the pin "opus"
#      to "opus[1m]" inside a key-reordering round-trip, then stamps 13. Fresh worktrees,
#      pool slots, and clones carry only the tracked half, so the fleet's first CLI call
#      there dirtied a tracked file. MEASURED in this worktree on this exact no---json
#      call, while signed out: the rewrite fires regardless of the exit code.
# It is LOCAL — unchanged behind a black-hole proxy, same ~0.2s — so it proves a credential is
# PRESENT, not that the token is live. An expired token passes here and dies at the crewmate's
# first turn; the refusal text says so rather than promising more than the check measured.
#
# Property 4 is why the call is wrapped: snapshot the settings bytes, byte-restore when the
# file no longer matches the snapshot after the call, KEEP the stamp (doctor's
# check_claude_auth posture). That comparison is against this invocation's snapshot, not an
# authorship proof: two of these overlapping in the same UNSTAMPED root can interleave so
# the later one snapshots migrated bytes and faithfully restores the flip after the earlier
# one cleaned it. Accepted residual, not a guarantee gap to paper over with a lock: spawns
# are issued serially, the window is the ~0.2s detector call, and the settings probe's
# VALUE row catches the end state on any machine. The kept
# stamp is the actual crew protection — this guard runs before every spawn, and in
# preflight before anything is built, so by the time a crew pane (or the first login the
# refusal prescribes) starts a session in this root, the ladder finds the stamp and fires
# nothing. Letting the CLI stamp itself was chosen over pre-stamping .claude.json by hand:
# the stamp VALUE belongs to the binary, not to this script, so a future ladder step is
# contained here with no edit. Pre-existing dirt is deliberately left alone — that finding
# belongs to the settings probe, not to a detector that would otherwise mutate state it did
# not disturb.
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
  stf="$CLAUDE_CONFIG_DIR/settings.json"
  snap="$(mktemp "${TMPDIR:-/tmp}/hb-settings.XXXXXX" 2>/dev/null)" || snap=""
  if [ -n "$snap" ] && ! cp "$stf" "$snap" 2>/dev/null; then
    rm -f "$snap"; snap=""
  fi
  [ -n "$snap" ] || echo "hb-fleet: could not snapshot settings.json — running the detector unguarded" >&2
  if "$HB_CLAUDE" auth status >/dev/null 2>&1; then arc=0; else arc=1; fi
  if [ -n "$snap" ]; then
    if ! cmp -s "$snap" "$stf"; then
      if cp "$snap" "$stf" 2>/dev/null && cmp -s "$snap" "$stf"; then
        echo "hb-fleet: contained the CLI settings migration — unstamped root; settings.json restored, stamp kept (HARNESS.md Traps)" >&2
      else
        echo "hb-fleet: the CLI settings migration fired and the byte-restore FAILED — a tracked file is modified." >&2
        echo "hb-fleet: repair: git checkout -- '$stf'   (keep the untracked stamp file: it stops the re-fire)" >&2
      fi
    fi
    rm -f "$snap"
  fi
  return $arc
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

pane_exists() {  # 0 = the pane id is still listed in the crew window, ALIVE OR A CORPSE
  # Deliberately NOT pane_dead, for the same reason kill avoids it: that helper answers
  # "dead OR missing" and would drop exactly the corpses that still hold pool slots
  # (remain-on-exit is on). `down` asks a different question, was this crewmate ever
  # killed, and a pane tmux still lists was not.
  t list-panes -t "$HB_RUN:crew" -F '#{pane_id}' 2>/dev/null | awk -v p="$1" '$1==p{f=1} END{exit !f}'
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
  ?    this card (esc closes)    z    zoom the pane under the cursor
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
  # anything fleet-specific must not be bound this way. Without -E the popup stays up until it
  # is dismissed, which is what makes it readable rather than a flash. The dismissal key is
  # ESCAPE, and only Escape: this line used to read "q or Escape", and TESTED twice on tmux 3.7
  # (2026-08-03) `q` leaves the popup open — it reaches the finished command's pane, not tmux.
  # An operator who believes the old comment is stuck on a card with no way out, so the card's
  # own `?` row names the key.
  # `?` shadows tmux's default list-keys binding, so the card names `:` to keep the full
  # binding list one prompt away.
  # GEOMETRY IS PART OF THE CARD. A popup does not scroll: tmux renders the command's output
  # into the box and drops whatever does not fit off the TOP, silently. MEASURED 2026-08-03
  # driving `start` end to end for the first time: at -w 84 -h 28 the card wrapped to 45 rendered
  # rows in a 26-row box, so the visible overlay began at `kill` — `start`, `spawn`, `ls`,
  # `state` and `send` were all off-screen, and the card's own headline verb with them. The box
  # is sized to the card here (94x34 of content against 32 lines, longest 91), and
  # probe_fleet_claude.py asserts the fit from source, so a command line added to the header
  # goes red instead of pushing the top out of view again. PRECONDITION, because the guarantee
  # is only as good as its scope: tmux CLAMPS a popup to the client's terminal, so the fit
  # holds on a terminal at least 96x36 and a smaller one truncates the same way again. The
  # cockpit builds its own session at 220x50 and a detached client re-clamps to whatever
  # attaches. Nothing here can widen someone's terminal; naming the bound is what it can do.
  t unbind -T prefix '?' 2>/dev/null || true
  if tmux_has_popup; then
    t bind -T prefix '?' display-popup -w 96 -h 36 "'$SELF' help"
  else
    # No display-popup below 3.2: `run-shell` renders the card in the pane's view mode
    # (q dismisses), which is the fallback preflight promises.
    t bind -T prefix '?' run-shell "'$SELF' help"
  fi

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
    # FULL WINDOW WIDTH (-f), and the flag is load-bearing rather than layout taste: the
    # session route's sidebar is the only thing that renders a session id, and it is gated
    # on width > 120 (upstream routes/session/index.tsx; the traps registry has the row).
    # A half split gave the grid 110 of the session's 220 columns, so the default cockpit
    # could not show an id at all. Attach also re-clamps every pane to the client terminal,
    # so the halved pane needed a ~242-column client; full width tracks the client itself,
    # and any terminal of 121+ columns clears the gate, the same bound as running fleet.sh
    # bare. MEASURED 2026-08-03 in both directions (docs/E2E.md finding 11: no id at 110
    # columns, id plus cost line at 160). The cost is the nvim pane's height when both
    # optional panes are up. NOTE: hb_add_pane's @hb_role marker makes panes idempotent,
    # so a fleet built before this flag keeps its half-width grid until `down` + `start`.
    hb_add_pane grid -vf "$FLEET_ROOT/fleet.sh"
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
  # kill-pane on the LAST crewmate takes the crew window with it (tmux destroys an empty
  # window), and the split refusal below then misreads the missing window as a full one.
  # MEASURED 2026-08-03 while testing the kill close: the first spawn after such a kill
  # dead-ended with "crew window is full". Re-ensure it, the same line `up` uses.
  t list-windows -t "$HB_RUN" -F '#{window_name}' | grep -qx crew || \
    t new-window -d -t "$HB_RUN" -n crew -c "$REPO"
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
    # Capture first, tail second: a pipeline's status is tail's, so the old one-liner
    # swallowed acquire's exit 2 (pool exhausted) and fell through to a --dir refusal
    # naming a flag the operator never passed (push-review finding, 2026-08-03).
    ACQ_OUT="$("$VENVPY" "$FLEET_ROOT/pool.py" acquire --owner "$HB_RUN" --purpose "crew $NAME")" \
      || { echo "hb-fleet: no slot leased (the pool's reason is above)." >&2; exit 2; }
    DIR="$(printf '%s\n' "$ACQ_OUT" | tail -1)"
  fi
  release_slot_on_failure() {
    # A spawn that dies after the lease must not keep it. MEASURED 2026-08-03 while
    # testing the kill close: a refused split left slot-1 leased to a crewmate that never
    # existed. Plain release only, so a slot that somehow holds work is refused, kept,
    # and named by the pool itself. Called on the dir refusal, the transcript failure,
    # the two split refusals, and the boot death; deliberately NOT on the ready-wait
    # timeout, where the crewmate is alive in its pane and may still boot — releasing
    # would reset the tree under a live process. Defined before the first exit that can
    # follow the lease, which is why it sits above the dir check.
    [ "$USE_SLOT" = 1 ] || return 0
    if "$VENVPY" "$FLEET_ROOT/pool.py" release "$DIR" --if-owner "$HB_RUN"; then
      echo "hb-fleet: released the just-leased slot back to the pool." >&2
    else
      echo "hb-fleet: could not release the just-leased slot (the pool's reason is above)." >&2
    fi
  }
  [ -d "${DIR:-}" ] || { echo "hb-fleet: --dir does not exist: '$DIR'" >&2; release_slot_on_failure; exit 2; }
  DIR="$(cd "$DIR" && pwd)"

  SID="$(uuidgen | tr 'A-Z' 'a-z')"

  # Transcript path is knowable BEFORE the pane exists because we chose the uuid, and
  # computing it here — rather than after the split, where it lived until the push
  # review read the gap — means its failure path holds no crewmate: the lease releases
  # cleanly and no pane outlives an aborted spawn. backend.transcript_path owns the slug
  # rule AND honors CLAUDE_CONFIG_DIR — crew transcripts land under the REDIRECTED root,
  # not ~/.claude (review finding; SHIP.md §3).
  if ! TRANSCRIPT="$("$VENVPY" - "$SID" "$DIR" "$REPO" <<'PY'
import sys
sys.path.insert(0, sys.argv[3] + "/.carryover/verified")
import backend
print(backend.transcript_path(sys.argv[1], sys.argv[2]))
PY
)"; then
    echo "hb-fleet: could not compute ${NAME}'s transcript path (backend.transcript_path failed — traceback above)" >&2
    release_slot_on_failure
    exit 1
  fi

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
  spawn_split() {  # guardrail 6: the pane gets THIS run's HB_FLEET_DIR — and its config
    # root — explicitly. Panes inherit the tmux SERVER's start environment, so a server
    # brought up from another checkout would hand every pane THAT checkout's root: one this
    # run's auth guard never measured or STAMPED (migration containment, hb_auth_state),
    # and a different root from the one the manifest's transcript path below is computed
    # against. Injecting it pins the pane to the root the guard just cleared.
    t split-window -t "$HB_RUN:crew" -c "$DIR" -e "HB_FLEET_DIR=$HB_FLEET_DIR" \
      -e "CLAUDE_CONFIG_DIR=$CLAUDE_CONFIG_DIR" \
      -P -F '#{pane_id}' -- "$HB_CLAUDE" "$@"
  }
  if ! PANE="$(spawn_split "$@" 2>/dev/null)"; then
    if [ -n "$PLACEHOLDER" ]; then
      t kill-pane -t "$PLACEHOLDER"; PLACEHOLDER=""
      PANE="$(spawn_split "$@")" || { echo "hb-fleet: crew window cannot fit another pane even after reclaiming the placeholder — kill a crewmate or start a second fleet (HB_RUN=...)" >&2; release_slot_on_failure; exit 2; }
    else
      echo "hb-fleet: crew window is full (split-window refused) — kill a crewmate or start a second fleet (HB_RUN=...)" >&2
      release_slot_on_failure
      exit 2
    fi
  fi
  if [ -n "$PLACEHOLDER" ]; then
    # Best-effort from here down to the title: a placeholder that vanished between the
    # scan and this kill, or a layout/title call failing, must not end spawn under
    # set -eu with the lease held and a live untracked crewmate (push-review finding).
    t kill-pane -t "$PLACEHOLDER" 2>/dev/null || true
  fi
  t select-layout -t "$HB_RUN:crew" tiled 2>/dev/null || true
  t select-pane -t "$PANE" -T "$NAME" 2>/dev/null || true

  if [ "$USE_SLOT" = 1 ]; then
    # The lease records no holder pid at acquire: the acquiring process is this spawn's
    # command substitution, gone in seconds, which is why pool.py status read every live
    # crewmate's slot as holder-DEAD (docs/E2E.md finding 8). The pane's root process is
    # the real holder and it exists now, so record it; the status liveness note becomes
    # true exactly when the crewmate dies. A failed adopt costs the note, not the spawn.
    PANE_PID="$(t display -p -t "$PANE" '#{pane_pid}' 2>/dev/null || true)"
    if ! { [ -n "$PANE_PID" ] && "$VENVPY" "$FLEET_ROOT/pool.py" adopt "$DIR" --pid "$PANE_PID" --if-owner "$HB_RUN" >/dev/null 2>&1; }; then
      echo "hb-fleet: could not record ${NAME}'s pane pid on the slot lease — pool.py status will make no liveness claim" >&2
    fi
  fi

  # The slot field is kill's discriminator: a --slot spawn's dir IS a pool worktree, but
  # nothing in the row said so before this field, so kill could not know a lease was at
  # stake (docs/E2E.md finding 9). Rows written before the field have none; manifest_get
  # exits 3 on a missing field, which kill reads as not-a-slot. Safe degradation.
  py - "$MANIFEST" "$NAME" "$PANE" "$DIR" "$SID" "$TRANSCRIPT" "${MODEL:-settings-pin}" "$USE_SLOT" <<'PY'
import json, sys, time
path, name, pane, d, sid, transcript, model, use_slot = sys.argv[1:9]
row = {"name": name, "pane": pane, "dir": d, "sid": sid,
       "transcript": transcript, "model": model, "at": int(time.time()),
       "slot": int(use_slot)}
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
      release_slot_on_failure
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
           # The version-string arm is not a guess: MEASURED 2026-08-03, a healthy
           # crewmate's pane_current_command is `2.1.220` — the CLI renames its process
           # to its own version — so EVERY live crewmate fell to the `*` arm and read
           # `ambiguous`, the one state firstmate is told to escalate rather than trust.
           # A false ambiguous is the expensive direction: it sends the captain to a
           # crewmate that is fine. Matched by shape, so the next version still hits it.
           *claude*|node|bun) LIVE="alive";;
           [0-9]*.[0-9]*.[0-9]*) LIVE="alive";;
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
  # stdlib-only and must not source env.claude.sh — this script already did, in its header).
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
    # display-popup landed in tmux 3.2; below that the help overlay is the only casualty.
    # tmux_has_popup owns the parse; TV_PROBE is its major.minor readback.
    if tmux_has_popup; then
      say OK "tmux $TV_PROBE (display-popup available, so the help overlay works)"
    elif [ -n "$TV_PROBE" ]; then
      say WARN "tmux $TV_PROBE is below 3.2 — no display-popup, so '?' prints to the pane instead"
    else
      say WARN "tmux present but its version did not parse ('$(tmux -V 2>&1)') — assuming no popup, so '?' prints to the pane instead"
    fi
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
  SLOT="$(manifest_get "$NAME" slot 2>/dev/null || echo 0)"
  CREWDIR="$(manifest_get "$NAME" dir 2>/dev/null || true)"
  # Deliberately NOT pane_dead, which send and brief both use: that helper answers "dead OR
  # missing", and a DEAD pane is exactly the thing kill exists to reclaim (remain-on-exit is on,
  # so a crewmate whose process ended leaves a corpse holding a slot). Only the MISSING case
  # needs framing — `down` takes the crew window with it, and tmux's own "can't find pane: %N"
  # then ends the script under set -eu, naming a pane id instead of the crewmate, which is the
  # one refusal in this file that spoke tmux rather than fleet. MEASURED 2026-08-03, docs/E2E.md.
  if ! t kill-pane -t "$P" 2>/dev/null; then
    echo "hb-fleet: $NAME's pane $P is already gone — nothing to kill (the fleet went down, or it was killed already)." >&2
    echo "hb-fleet: its transcript survives: claude --resume $SID (from a shell that sourced env.claude.sh)" >&2
    if [ "$SLOT" = "1" ]; then
      # No auto-release on this branch: a stale row cannot prove the lease is still this
      # crewmate's (the slot may have been released and re-leased since). Name it instead.
      echo "hb-fleet: $NAME held a pool slot. Check it: $VENVPY $FLEET_ROOT/pool.py status" >&2
    fi
    exit 2
  fi
  echo "hb-fleet: killed $NAME ($P). Its transcript survives; resume from an env.claude.sh shell: claude --resume $SID"
  # Settle the lease (docs/E2E.md finding 9: kill used to leave the slot leased forever).
  # A PLAIN release is safe by construction: the pool refuses while the slot holds work,
  # keeps the lease on refusal, and prints the held files itself. Those lines reach the
  # operator uncaptured; the fleet frames the outcome and never re-says the pool's reason.
  # --if-owner scopes the release to this run's own lease. The call is if-guarded because
  # a refusal exits 2 and set -eu would otherwise end kill here (the finding-15 shape).
  if [ "$SLOT" = "1" ] && [ -d "${CREWDIR:-}" ] && [ -x "$VENVPY" ]; then
    if "$VENVPY" "$FLEET_ROOT/pool.py" release "$CREWDIR" --if-owner "$HB_RUN"; then
      echo "hb-fleet: released $NAME's pool slot; it is leasable again."
    else
      echo "hb-fleet: the pool did not release $NAME's slot (its reason is above). If it holds work:"
      echo "hb-fleet:   copy the work out, then: $VENVPY $FLEET_ROOT/pool.py release '$CREWDIR' [--discard-work]"
    fi
  elif [ "$SLOT" = "1" ]; then
    # The guard above needs the slot worktree and the venv python; when either is gone
    # (a venv rebuild between spawn and kill, an out-of-band worktree removal), the
    # release cannot run — and a silent skip would break this verb's own contract, so
    # the skip is spoken (push-review finding: the already-gone branch warned, this
    # branch did not).
    echo "hb-fleet: $NAME held a pool slot but the release cannot run (slot worktree or rig venv missing) — the lease may still be held. Check: $VENVPY $FLEET_ROOT/pool.py status" >&2
  fi
  ;;

down)
  # Settle the slot leases this fleet still holds, finding 9's other half (docs/E2E.md
  # section 7E): kill learned to settle its own crewmate's lease, and `down` went on taking
  # the whole session and leaving every one of them leased.
  #
  # THE ORDER IS THE WHOLE FIX, and it is crew, then leases, then session. kill-session is
  # SIGHUP and the captain's seat is the bridge shell INSIDE this session (see the card
  # above; `start` ends in attach), so a release loop placed after kill-session is killed
  # with the pane that is running it. MEASURED 2026-08-04, from the bridge pane: session
  # gone, slot-1 still leased, the strand rebuilt inside its own fix and green on every
  # static leg. Killing the crew WINDOW first leaves the bridge, and therefore this script,
  # alive to finish; kill-session goes last and takes both.
  # The crew window dies before any release for the reason spawn's ready-wait branch keeps
  # its lease: release restores the worktree, and a reset under a live process is the one
  # thing the pool cannot undo. Same SIGHUP-then-reset race kill has carried since its own
  # close, deliberately not widened here.
  # The census runs first, before anything is killed, because afterwards there is no pane
  # left to ask. The discriminator is a pane that still EXISTS, corpse included: a crewmate
  # whose pane is GONE was killed, and kill settled that lease already (or said why it
  # could not).
  # Residual: `down` run from a CREW pane still kills its own caller before the releases.
  # The captain's seat is the bridge, and a crewmate tearing down its own fleet is not a
  # supported flow.
  # Residual, named rather than guarded: tmux restarts pane ids at %0 with a new server, so a
  # row left by a fleet on an older server can collide with a live pane id. The worst it buys
  # is a release aimed at a slot this same HB_RUN holds, which `down` is tearing down anyway,
  # or a "did not release" line over a lease that is already gone. Neither can reach work: the
  # pool refuses any slot holding it, and --if-owner refuses another run's lease.
  HELD=""
  for N in $(manifest_names); do
    [ "$(manifest_get "$N" slot 2>/dev/null || echo 0)" = "1" ] || continue
    P="$(manifest_get "$N" pane 2>/dev/null || true)"
    { [ -n "$P" ] && pane_exists "$P"; } || continue
    HELD="$HELD $N"
  done

  t kill-window -t "$HB_RUN:crew" 2>/dev/null || true

  for N in $HELD; do
    D="$(manifest_get "$N" dir 2>/dev/null || true)"
    # The same spoken skip kill carries: a release that could not run must never read like
    # one that did.
    if [ ! -d "${D:-}" ] || [ ! -x "$VENVPY" ]; then
      echo "hb-fleet: $N held a pool slot but the release cannot run (slot worktree or rig venv missing) — the lease may still be held. Check: $VENVPY $FLEET_ROOT/pool.py status" >&2
      continue
    fi
    # if-guarded for kill's reason and one more: a refusal exits 2, and under set -eu that
    # would end `down` here, stranding every lease after this one. That is the bug this
    # closes, rebuilt inside its own fix.
    if "$VENVPY" "$FLEET_ROOT/pool.py" release "$D" --if-owner "$HB_RUN"; then
      echo "hb-fleet: released $N's pool slot; it is leasable again."
    else
      echo "hb-fleet: the pool did not release $N's slot (its reason is above). If it holds work:"
      echo "hb-fleet:   copy the work out, then: $VENVPY $FLEET_ROOT/pool.py release '$D' [--discard-work]"
    fi
  done

  t kill-session -t "$HB_RUN" 2>/dev/null || true
  echo "hb-fleet: session $HB_RUN down. kill-session is SIGHUP — in-flight turns aborted, transcripts intact."
  echo "hb-fleet: resume any crewmate from an env.claude.sh shell: claude --resume <sid> (see $MANIFEST)"
  ;;

*) usage;;
esac
