#!/bin/bash
# Daily snapshot of the LIVE opencode DB (~/.local/share/opencode/opencode.db) into iCloud
# Drive. That DB sits OUTSIDE this repo and is one-of-a-kind measurement evidence: it holds
# the 223,258 terra turn and most of the Phase 12 scoped population that sizes RETIRE_AT
# (docs/OUTCOME.md, probe_turn_growth.py's real-corpus half). The in-repo hb/ corpus is
# tracked in git; this file was the last un-backed-up leg (2026-07-31 audit).
#
# Method: `VACUUM INTO` takes a consistent read snapshot even while opencode is writing
# (WAL mode), and the output is self-contained (WAL content folded in, no sidecars). The
# snapshot is integrity-checked BEFORE it is allowed to replace anything, gzipped, then
# renamed into place so iCloud never syncs a partial file.
#
# Installed as a LaunchAgent, and the install has a TCC constraint (TESTED 2026-07-31): a
# launchd-spawned /bin/bash gets "Operation not permitted" reading anything under ~/Desktop,
# so the agent runs a COPY of this script from ~/.local/libexec/healbot/, not this file.
# iCloud Drive is NOT blocked for the agent (same test). THIS repo copy is canonical; after
# editing it, re-install:
#   cp harness/backup-opencode-db.sh ~/.local/libexec/healbot/
#   cp harness/com.healbot.opencode-db-backup.plist ~/Library/LaunchAgents/
#   launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.healbot.opencode-db-backup.plist
# Daily at 13:00; launchd runs a missed firing on next wake (skipped if powered off).
# Log: ~/Library/Logs/healbot-opencode-db-backup.log
# Run by hand any time: bash harness/backup-opencode-db.sh
set -euo pipefail

SRC="$HOME/.local/share/opencode/opencode.db"
DEST_DIR="$HOME/Library/Mobile Documents/com~apple~CloudDocs/healbot-backups/opencode-db"
KEEP=14   # newest snapshots retained; ~40 MB each at the Jul 2026 129 MB DB size

ts() { date '+%Y-%m-%d %H:%M:%S'; }

if [ ! -f "$SRC" ]; then
  echo "$(ts) ERROR: source DB missing: $SRC" >&2
  exit 1
fi

mkdir -p "$DEST_DIR"
STAMP="$(date '+%Y%m%d-%H%M%S')"
TMP="$(mktemp -d)/opencode-$STAMP.db"
trap 'rm -rf "$(dirname "$TMP")"' EXIT

sqlite3 "$SRC" "VACUUM INTO '$TMP'"

CHECK="$(sqlite3 "$TMP" 'PRAGMA quick_check;')"
if [ "$CHECK" != "ok" ]; then
  echo "$(ts) ERROR: snapshot failed quick_check: $CHECK" >&2
  exit 1
fi

gzip "$TMP"
FINAL="$DEST_DIR/opencode-$STAMP.db.gz"
mv "$TMP.gz" "$FINAL.partial"
mv "$FINAL.partial" "$FINAL"

# Prune to the newest $KEEP. Filenames are collision-free timestamps with no spaces, so
# sorting basenames newest-first is safe; the directory path itself contains spaces.
cd "$DEST_DIR"
ls -1 opencode-*.db.gz 2>/dev/null | sort -r | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f -- "$old"
  echo "$(ts) pruned $old"
done

SIZE="$(du -h "$FINAL" | cut -f1 | tr -d ' ')"
COUNT="$(ls -1 opencode-*.db.gz | wc -l | tr -d ' ')"
echo "$(ts) OK: $(basename "$FINAL") ($SIZE, quick_check ok, $COUNT retained)"
