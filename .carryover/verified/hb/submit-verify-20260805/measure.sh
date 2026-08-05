#!/bin/sh
# Submit-verify measurement (single-use rig, paid-run-protocol applies).
#
# Question under measurement (hb-fleet.sh send, the raw-tail exception): at the
# instants the shipped verify loop samples (+1s, +2s after the submit Enter),
# does the pane's last-3 window — raw, and blank-stripped per screen_tail —
# contain the submitted text? Two geometries: a tall solo pane (raw tail-3 is
# padding, the known blindness) and a pane the render fills.
#
#   measure.sh dry            free rehearsal on a scratch tmux server
#   measure.sh live ARCHIVE   the paid run: 2 submits on one crewmate
#
# live runs the MAIN checkout's hb-fleet.sh (credentialed harness root) after
# proving it byte-identical to this worktree's copy. Instrumentation is a PATH
# shim on tmux (timestamps every call send makes — the verify sample instants
# — then execs the real binary) plus a 10Hz sampler on the real binary.
set -eu

SELFDIR="$(cd "$(dirname "$0")" && pwd)"
WT="$(cd "$SELFDIR/../../../.." && pwd)"
MAIN="${HB_MEASURE_MAIN:-$HOME/Desktop/healbot}"
RUN="hb-measure"
REAL_TMUX="$(command -v tmux)"
PY="$(command -v python3)"
CREW="probe-echo"

fleet() { HB_RUN="$RUN" "$MAIN/harness/hb-fleet.sh" "$@"; }
t() { "$REAL_TMUX" -L healbot "$@"; }

make_shim() {  # $1 = shim dir
  mkdir -p "$1"
  cat > "$1/tmux" <<'ZSH'
#!/bin/zsh -f
zmodload zsh/datetime
print -r -- "$EPOCHREALTIME $*" >> "$HB_SHIM_LOG"
exec "$HB_REAL_TMUX" "$@"
ZSH
  chmod +x "$1/tmux"
}

# One leg: sampler up, then the REAL send through the shim, exit code assigned
# never piped (paid-run-protocol). $1 legdir  $2 pane  $3 nonce  $4 socket
run_leg() {
  legdir="$1" pane="$2" nonce="$3" sock="$4"
  mkdir -p "$legdir/frames"
  printf '%s\n' "$nonce" > "$legdir/nonce.txt"
  : > "$legdir/tmux-calls.log"
  "$PY" "$SELFDIR/sampler.py" "$REAL_TMUX" "$sock" "$pane" \
    "$legdir/frames" 10 12 & SAMPLER=$!
  sleep 0.4
  rc=0
  out="$(PATH="$SHIMDIR:$PATH" HB_SHIM_LOG="$legdir/tmux-calls.log" \
         HB_REAL_TMUX="$REAL_TMUX" HB_RUN="$RUN" \
         "$MAIN/harness/hb-fleet.sh" send "$CREW" "$nonce" \
         2>"$legdir/send.err")" || rc=$?
  printf '%s\n' "$out" > "$legdir/send.out"
  printf '%s\n' "$rc" > "$legdir/send.exit"
  wait $SAMPLER
}

wait_idle() {  # $1 = seconds cap
  waited=0
  while [ "$waited" -lt "$1" ]; do
    line="$(fleet state "$CREW" 2>/dev/null | head -1 || true)"
    case "$line" in *"screen: idle"*) return 0;; esac
    sleep 3; waited=$((waited + 3))
  done
  echo "measure: $CREW not idle after $1 s — last state: $line" >&2
  return 1
}

case "${1:-}" in
dry)
  ARCHIVE="${2:-/tmp/hb-submit-verify-dry}$$"
  SHIMDIR="$ARCHIVE/shim"; make_shim "$SHIMDIR"
  SOCK="hb-subverify-dry-$$"
  NONCE="hbverify-dry-nonce"
  # Painter: phase 1 is a composer holding the nonce; phase 2 simulates the
  # post-submit render — echo among the last painted lines, padding below —
  # the exact shape whose classification the analyzer must get right.
  "$REAL_TMUX" -L "$SOCK" -f /dev/null new-session -d -s fix -x 100 -y 48 sh -c '
    clear; i=1; while [ $i -le 8 ]; do echo "filler $i"; i=$((i+1)); done
    echo "> '"$NONCE"'"; echo "(composer)"
    sleep 3
    clear; i=1; while [ $i -le 8 ]; do echo "filler $i"; i=$((i+1)); done
    echo "> '"$NONCE"'"; echo "spinner..."; echo "(empty composer)"
    sleep 120'
  PANE="$("$REAL_TMUX" -L "$SOCK" list-panes -t fix -F '#{pane_id}')"
  legdir="$ARCHIVE/tall"; mkdir -p "$legdir/frames"
  printf '%s\n' "$NONCE" > "$legdir/nonce.txt"
  : > "$legdir/tmux-calls.log"
  # A stand-in for send's verify block (same call shapes, same schedule), so
  # the shim log and the analyzer are rehearsed against real traffic.
  cat > "$ARCHIVE/standin.sh" <<EOF
tmux -L "$SOCK" send-keys -t "$PANE" -l -- "$NONCE"
tmux -L "$SOCK" send-keys -t "$PANE" Enter
tries=0
while [ \$tries -lt 2 ]; do
  sleep 1
  case "\$(tmux -L "$SOCK" capture-pane -p -t "$PANE" | tail -3)" in
    *"$NONCE"*) tmux -L "$SOCK" send-keys -t "$PANE" Enter; tries=\$((tries+1));;
    *) break;;
  esac
done
[ \$tries -ge 2 ] && { echo "did not provably clear"; exit 1; }
echo sent
EOF
  "$PY" "$SELFDIR/sampler.py" "$REAL_TMUX" "$SOCK" "$PANE" \
    "$legdir/frames" 10 8 & SAMPLER=$!
  sleep 0.5
  rc=0
  out="$(PATH="$SHIMDIR:$PATH" HB_SHIM_LOG="$legdir/tmux-calls.log" \
         HB_REAL_TMUX="$REAL_TMUX" sh "$ARCHIVE/standin.sh")" || rc=$?
  printf '%s\n' "$out" > "$legdir/send.out"
  printf '%s\n' "$rc" > "$legdir/send.exit"
  wait $SAMPLER
  "$REAL_TMUX" -L "$SOCK" kill-server 2>/dev/null || true
  "$PY" "$SELFDIR/analyze.py" "$ARCHIVE"
  echo "dry archive: $ARCHIVE"
  ;;

live)
  ARCHIVE="${2:?live needs an archive dir}"
  mkdir -p "$ARCHIVE"
  SHIMDIR="$ARCHIVE/shim"; make_shim "$SHIMDIR"
  cmp "$WT/harness/hb-fleet.sh" "$MAIN/harness/hb-fleet.sh" \
    || { echo "measure: worktree and main hb-fleet.sh differ — refusing" >&2; exit 2; }
  { date; "$REAL_TMUX" -V; claude --version 2>&1 || true
    (cd "$MAIN" && git log --oneline -1); } > "$ARCHIVE/meta.txt" 2>&1
  fleet preflight > "$ARCHIVE/preflight.txt" 2>&1 \
    || { echo "measure: preflight failed — see $ARCHIVE/preflight.txt" >&2; exit 2; }
  cleanup() {
    fleet kill "$CREW" >> "$ARCHIVE/teardown.txt" 2>&1 || true
    fleet down >> "$ARCHIVE/teardown.txt" 2>&1 || true
  }
  trap cleanup EXIT
  fleet up > "$ARCHIVE/up.txt" 2>&1
  spawn_out="$(fleet spawn "$CREW" --slot 2>&1)" || {
    printf '%s\n' "$spawn_out" > "$ARCHIVE/spawn.txt"
    echo "measure: spawn failed — see $ARCHIVE/spawn.txt" >&2; exit 2; }
  printf '%s\n' "$spawn_out" > "$ARCHIVE/spawn.txt"
  PANE="$("$PY" - "$MAIN/.fleet/$RUN/manifest.jsonl" <<'EOF'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
print([r for r in rows if r["name"] == "probe-echo"][-1]["pane"])
EOF
)"
  case "$spawn_out" in *"trust dialog"*)
    t send-keys -t "$PANE" Enter
    sleep 2
    waited=0
    until t capture-pane -p -t "$PANE" | grep -q "bypass permissions on"; do
      sleep 1; waited=$((waited + 1))
      [ "$waited" -ge 90 ] && { echo "measure: never ready after trust" >&2; exit 2; }
    done
    echo "trust dialog answered by rig (one Enter)" >> "$ARCHIVE/spawn.txt";;
  esac
  t resize-window -t "$RUN:crew" -x 220 -y 50 2>/dev/null || true
  sleep 2
  run_leg "$ARCHIVE/tall" "$PANE" "Reply with only: pong (hbverify-tall-$$)" healbot
  wait_idle 240
  # Shrink until the render fills the pane so raw tail-3 lands on paint. One
  # shot undershoots: the pre-resize painted count carries reflow the CLI
  # drops when it repaints smaller (run1: 17 painted on 49 rows became 9-11
  # painted on the 17-row pane it asked for — run notes in run1/REPORT.md), so
  # re-measure after every resize and stop only when paint reaches the pane
  # height or the 12-row floor. The floor can halt the chase short of paint
  # for good: run1's 17-row pane painted 9-11 lines, already below the floor,
  # and whether the render grows to fill 12 rows is unmeasured. Every step is
  # recorded either way, and analyze.py flags the leg UNMET from the frames
  # if the samples still miss paint.
  : > "$ARCHIVE/resize.txt"
  step=0
  while [ "$step" -lt 5 ]; do
    P="$(t capture-pane -p -t "$PANE" | grep -cv '^[[:space:]]*$' || true)"
    H="$(t display-message -p -t "$PANE" '#{pane_height}' 2>/dev/null || true)"
    printf 'step %s: painted %s of pane height %s\n' "$step" "$P" "$H" \
      >> "$ARCHIVE/resize.txt"
    case "$H" in ''|*[!0-9]*|0)
      # A dead height query must not degrade into "break at step 0 and run the
      # leg on the tall pane" (the geometry this loop exists to leave): refuse.
      echo "measure: pane height query failed mid-shrink — see $ARCHIVE/resize.txt" >&2
      exit 2;;
    esac
    [ "$P" -ge "$H" ] && break
    target=$P; [ "$target" -lt 12 ] && target=12
    [ "$target" -ge "$H" ] && break
    t resize-window -t "$RUN:crew" -y "$target" 2>/dev/null || true
    sleep 2
    step=$((step + 1))
  done
  run_leg "$ARCHIVE/full" "$PANE" "Reply with only: pong (hbverify-full-$$)" healbot
  wait_idle 240 || true
  trap - EXIT
  cleanup
  "$PY" "$SELFDIR/analyze.py" "$ARCHIVE"
  ;;

*) echo "usage: measure.sh dry | live ARCHIVE" >&2; exit 2;;
esac
