#!/bin/bash
# Render + install the daily opencode-DB backup LaunchAgent. macOS only — launchd; the PC
# recipe is docs/WINDOWS.md ("Corpus backup"). Idempotent: safe to re-run after editing
# either half.
#
# Why a render step exists at all: launchd expands neither ~ nor environment variables in
# ProgramArguments/StandardOutPath, so an installed plist must carry absolute home paths —
# and the tracked repo must not (they are machine-specific and name the account; the gate's
# home-paths invariant rejects them). The tracked plist therefore carries __HOME__
# placeholders and this script substitutes the real $HOME at install time.
#
# The TCC constraint (TESTED 2026-07-31, backup-opencode-db.sh header): a launchd-spawned
# bash gets "Operation not permitted" reading anything under ~/Desktop, so the agent runs a
# COPY of the script from ~/.local/libexec/healbot/, refreshed here on every install.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
LABEL=com.healbot.opencode-db-backup

mkdir -p "$HOME/.local/libexec/healbot" "$HOME/Library/LaunchAgents"
cp "$HERE/backup-opencode-db.sh" "$HOME/.local/libexec/healbot/"
sed "s|__HOME__|$HOME|g" "$HERE/$LABEL.plist" > "$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "installed: $LABEL — daily 13:00, log: ~/Library/Logs/healbot-opencode-db-backup.log"
