#!/bin/sh
# Healbot claude harness environment — the Claude Code half of config parity.
#
#   . ~/Desktop/healbot/harness/env.claude.sh    then run `claude` as normal
#
# Parity means the same DISCIPLINE as env.sh, not the same model: an isolated config root,
# an explicit model pin, compaction off so retirement is the sole lifecycle policy, and a
# short list of switches deliberately NOT set. Mechanisms verified in docs/SHIP.md §2.
#
# Self-location: same ${BASH_SOURCE[0]} caveats as env.sh's header (zsh/bash correct; dash
# and ksh silently fall back to $PWD). The existence check below makes a wrong root loud.
# HARNESS_ROOT is shared with env.sh on purpose — both resolve to harness/, and sourcing
# both files in one shell is the normal fleet bring-up (opencode grid pane + claude crew).
HARNESS_ROOT="${HARNESS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)}"

if [ ! -f "$HARNESS_ROOT/claude/settings.json" ]; then
  echo "env.claude.sh: could not locate the claude harness (looked in '$HARNESS_ROOT')." >&2
  echo "env.claude.sh: source this from zsh or bash, or set HARNESS_ROOT yourself first." >&2
  return 1 2>/dev/null || exit 1
fi

# The claude config root lives at harness/claude/, NOT under harness/config/. That
# placement is load-bearing twice over (docs/SHIP.md §2): arms.py freezes every regular
# file under harness/config/ into arm snapshots (arms.py:60, _base_files' os.walk), so a
# claude root inside it would (a) trip the banned-filename snapshot check — measured, the
# first draft turned probe_arm_factory red — and (b) after login, copy CREDENTIAL STATE
# into every future arm's run directory. Do not move it back.
#
# CLAUDE.md is materialized here as a symlink because the tracked file must carry a safe
# name (gate.py's banned-filenames check refuses CLAUDE.md anywhere in the tracked tree),
# while Claude Code reads exactly that name from the config root. Same convention as
# harness/skills/<name>.md -> ~/.agents/skills/<name>/SKILL.md. A symlink is known to
# work: the owner's own ~/.claude/CLAUDE.md is one.
if [ ! -e "$HARNESS_ROOT/claude/CLAUDE.md" ]; then
  ln -s crew-constraints.md "$HARNESS_ROOT/claude/CLAUDE.md" 2>/dev/null || true
fi

# Config isolation. CLAUDE_CONFIG_DIR redirects the ENTIRE user config root — settings,
# CLAUDE.md, skills, agents, hooks, AND auth/state. TESTED (docs/SHIP.md §2): under a
# redirected empty dir, `claude doctor` reported "Not signed in" despite the real ~/.claude
# being signed in, and wrote .claude.json + backups/ inside the redirected dir. Two
# consequences, both load-bearing:
#
#   1. This is the REAL isolation knob — the naming is inverted relative to opencode, where
#      OPENCODE_CONFIG_DIR is the additive false-isolation trap and XDG_CONFIG_HOME is the
#      real one. Do not "fix" this by analogy in either direction.
#   2. AUTH DOES NOT FOLLOW. First use of this harness requires one interactive login:
#      run `claude` once after sourcing this file and sign in. Until then every crew spawn
#      lands on a signed-out session. WHERE the credential lands is macOS-subtle (review
#      finding, VERIFIED): the real install's OAuth token lives in the login KEYCHAIN
#      (`security find-generic-password -s "Claude Code-credentials"` returns it and
#      ~/.claude/.credentials.json does not exist), with a .credentials.json file only as
#      a fallback path in the binary. So the harness login may SHARE the owner's keychain
#      item rather than isolate — settle it at the first login and record the answer in
#      docs/SHIP.md §5. The whitelist .gitignore covers the file-fallback case either way:
#      nothing credential-shaped can be committed.
#
# Project-scope config (.claude/ under a session's cwd) is NOT redirected — that is the
# deliberate keep, mirroring env.sh's project-AGENTS.md decision.
CLAUDE_CONFIG_DIR="$HARNESS_ROOT/claude"
export CLAUDE_CONFIG_DIR

# Compaction off, second half. The first half is "autoCompactEnabled": false in
# settings.json; this env var is the belt-and-braces redundancy. Both names verified
# present in the 2.1.220 binary; CLAUDE_CODE_DISABLE_AUTO_COMPACT and DISABLE_MICROCOMPACT
# are NOT in the binary (0 hits) — do not use them (docs/SHIP.md §2).
#
# Same consequence as opencode.jsonc's compaction block: with compaction off, the context
# ceiling is a HARD ERROR, not a compaction. Retirement must fire first. The opencode
# numbers (RETIRE_AT 180,000 / ceiling ~360K / worst_turn 175,148) are measurements of
# gpt-5.6-sol through opencode and DO NOT TRANSFER to any Claude model — the claude-side
# gate has no verified threshold until one is measured (docs/SHIP.md §5, open items).
DISABLE_AUTO_COMPACT=1
export DISABLE_AUTO_COMPACT

# HB_FLEET_DIR is deliberately NOT exported here. The fleet-state hooks in
# claude/hooks/fleet-state.sh are inert without it, so an interactive `claude`
# under this harness (e.g. the one-time login) runs with zero hook side effects.
# harness/hb-fleet.sh exports it per fleet run.

# NOT SET, on purpose:
#   --bare / --safe-mode      -- the OPENCODE_PURE trap transferred: both skip the
#                                harness's OWN hooks and config, so the fleet-state
#                                channel dies silently. Never launch crew with them.
#   ANTHROPIC_MODEL           -- settings.json owns the pin; a second copy in the
#                                environment is a divergence surface. Per-spawn override
#                                is `hb-fleet.sh spawn --model ...`, which passes --model
#                                explicitly and records it in the fleet manifest.
#   ANTHROPIC_API_KEY         -- the harness runs on the owner's interactive login, same
#                                as the opencode harness runs on oauth. Keys in env leak
#                                into every pane's environment.
#   permissions bypass flags  -- still not set AS FLAGS, but the decision they encoded is
#                                REVERSED: owner directive 2026-08-01 makes
#                                "permissions": {"defaultMode": "bypassPermissions"} the
#                                settings.json default, so bypass is a config fact, not a
#                                launch flag (one place, recorded, no per-spawn argv drift).
#                                WAS: crew ran with Claude Code's normal permission prompts,
#                                and gnhf's --dangerously-skip-permissions posture
#                                (docs/AFK.md §1.7) was called the counterexample, not the
#                                model. The Notification-event blocked-crew channel STAYS
#                                load-bearing either way: bypass mode does not silence the
#                                residual dialogs -- the bypass-mode acceptance dialog and
#                                the per-directory trust dialog both still block a crewmate
#                                until a human answers, and the fleet must see that.
