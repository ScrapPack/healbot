#!/bin/sh
# Healbot harness environment.
#
#   . ~/Desktop/healbot/harness/env.sh    then run `opencode` as normal
#
# Every switch below is here because it was measured, not assumed. See docs/STRIP.md.

# Self-location. ${BASH_SOURCE[0]} is a bash/zsh array expansion, so this line does NOT work
# in every POSIX sh despite the shebang. TESTED sourcing from an unrelated cwd:
#   zsh 5.9 / bash 3.2 / macOS /bin/sh (bash in POSIX mode)  -> correct
#   dash   -> "Bad substitution", HARNESS_ROOT falls back to $PWD
#   ksh    -> no error at all, HARNESS_ROOT silently becomes $PWD
# A wrong HARNESS_ROOT does not leak the user's ~/.config -- XDG just points at a directory
# with no config in it, so opencode boots with an EMPTY config: no model pin, no
# compaction.auto=false, no agent/build.md prompt override, no trim plugin. The two exports
# below still apply, so it looks like a working harness while delivering none of the
# measured isolation. That is the worst possible failure shape here, so it is checked.
# `:-` and not a bare assignment: the error message below tells you to "set HARNESS_ROOT
# yourself before sourcing", and an unconditional assignment overwrote the value you set,
# so the documented escape hatch did not work. It does now. Consequence to know about: once
# HARNESS_ROOT is exported it is sticky, so sourcing a SECOND harness checkout in the same
# shell keeps pointing at the first. `unset HARNESS_ROOT` between them.
HARNESS_ROOT="${HARNESS_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)}"

if [ ! -f "$HARNESS_ROOT/config/opencode/opencode.jsonc" ]; then
  echo "env.sh: could not locate the harness (looked in '$HARNESS_ROOT')." >&2
  echo "env.sh: your shell does not support \$BASH_SOURCE. Source this from zsh or bash," >&2
  echo "env.sh: or set HARNESS_ROOT yourself before sourcing. Nothing was exported." >&2
  return 1 2>/dev/null || exit 1
fi

# Config isolation. XDG_CONFIG_HOME is the ONLY thing that actually redirects the global
# config root -- OPENCODE_CONFIG_DIR is additive and changes nothing about inheritance
# (docs/SCAN.md C1, TESTED both ways). Global.Path.config is derived from xdgConfig at
# module load, so this must be exported before opencode starts.
XDG_CONFIG_HOME="$HARNESS_ROOT/config"
export XDG_CONFIG_HOME

# Skill trees. Skills key off $HOME, not the config dir, so XDG isolation alone leaves all
# 18 in place. This is the switch that actually drops them.
#
# 18 -> 1 / 20 -> 3 IS A NEUTRAL-DIRECTORY FIGURE. skill/index.ts:205-208 runs the
# config-DIRECTORY scan unconditionally and config/paths.ts:23-41 walks `.opencode` up from
# cwd, so the floor is cwd-dependent. TESTED with this exact switch set, cwd = the fork:
# 2 skills / 12 commands / 9 agents -- it readmits 8 upstream repo commands (commit,
# changelog, translate, ...), the `effect` skill and 2 agents. Phase 4 develops in the fork.
#
# The security half is cwd-independent and is the stronger reason to keep this on: a SKILL.md
# body containing !`cmd` shell-executes on slash-invoke with no permission check
# (session/prompt.ts:1397-1408). TESTED end to end, including with
# OPENCODE_PERMISSION='{"skill":"deny"}' set -- the deny removes the `skill` TOOL but the
# /<skill-name> slash path (command/index.ts:134-149) ignores it and still runs the shell.
# Removing skills from the prompt is the only thing that actually closes this.
OPENCODE_DISABLE_EXTERNAL_SKILLS=true
export OPENCODE_DISABLE_EXTERNAL_SKILLS

# Drops ~/.claude/CLAUDE.md from the instruction chain (and redundantly the .claude skills
# half). Project-level AGENTS.md still loads -- deliberately, that is where real
# project-specific facts belong.
#
# Know what that costs before treating it as free. instruction.ts:126-131 -> fs-util.ts:154-166
# collect EVERY AGENTS.md from cwd up to the worktree root, not the first one (the source
# comment at instruction.ts:123 claims otherwise and is wrong about its own code; TESTED with
# a 3-level repo, all three loaded). In the fork, a session at packages/opencode/src/session/llm
# ingests 22,273 B of AGENTS.md; at the fork root, 8,748 B -- larger than the entire
# 7,569 B base-prompt saving below. There is no AGENTS.md at ~/Desktop/healbot itself, so at
# the harness's own root this switch is a pure win and the "deliberate keep" is untested there.
OPENCODE_DISABLE_CLAUDE_CODE=true
export OPENCODE_DISABLE_CLAUDE_CODE

# Tool-description trimming: OFF by default, opt-in and reversible. See
# config/opencode/plugin/trim-tools.ts for why it is not a default.
# HARNESS_TRIM_TOOLS=1; export HARNESS_TRIM_TOOLS

# Healbot retirement threshold, in tokens of live context OCCUPANCY (not lifetime spend).
# Defaults to 180000, and it is the ONLY gate -- there is no second one any more.
#
# The ENFORCING default lives in the SERVER plugin, config/opencode/plugin/healbot.ts, which since
# Phase 7 is the only thing that retires anything at all: the automatic gate, the operator's `x`
# (relayed as a metadata request) and healbot_retire all run the same code in that one process.
# The grid reads the same variable purely to paint -- the RETIRE border, the `N to retire` count,
# the share-of-gate figure. Both default to the same number, so they agree until you set this for
# one process and not the other, and the process that matters is the server's.
#
# Set this only to exercise retirement cheaply, since reaching the real gate on a frontier model
# on purpose is expensive. TESTED at 20000.
#
# WHY 180000. Two corrections stacked, and the second is the reason for this number.
#
#   1. The ceiling is ~360K, NOT the 922,000 limit.input the model registry advertises: a session
#      driven up took its last good turn at occupancy 359,829 and then failed 25 turns in a row
#      with the provider's ContextOverflowError. Nothing is truncated on the way -- opencode sends
#      the whole history every turn until the provider refuses it -- so the failure is a cliff, not
#      a slope. That took the default from 350000 to 256000 in Phase 5. See docs/HARDEN.md §6.
#   2. The gate WAITS FOR THE TURN TO END, and Phase 7 deleted the second gate that used to bound
#      how far a turn could carry a session past the line. Waiting means accepting whatever that
#      turn adds, MEASURED at up to ~170K on one turn. With one gate the arithmetic is
#      RETIRE_AT + worst_turn < ceiling, so anything at or above ~190000 can be carried off the
#      cliff by one ordinary read-heavy turn. 180000 + ~170K = ~350K, just inside. See
#      docs/RELAY.md.
#   3. PHASE 8 RE-MEASURED worst_turn AND TIGHTENED (2). The ~170K above was ONE turn measured
#      once. Across 86 completed turns from every session DB on disk (probe_turn_growth.py, free),
#      the worst single-turn growth on the pinned model is 175,148 -- so the bound on this
#      variable is 184,852, not ~190000, and 180000 clears it by 4,852 tokens: 1.3% of the
#      ceiling. That is THINNER than the "~10K, under 3%" margin HARNESS.md rejects elsewhere as
#      too late to be a guard. ~170K is the tail of the distribution, not the middle (the p50 is
#      22,152) -- it just is not the maximum, which is what the derivation used it as.
#   4. AND THIS NUMBER IS MODEL-SPECIFIC, which nothing said before Phase 8. worst_turn is a fact
#      about a MODEL's tool-calling behaviour. The same corpus holds a 223,258-token turn on
#      gpt-5.6-terra; at this gate that lands at 403,258 and the session dies. 180000 is verified
#      only while opencode.jsonc pins openai/gpt-5.6-sol. Change the pin and re-measure.
#      See docs/GROWTH.md §1.
#
# So: lower it freely, raise it only with a new measurement of worst-case single-turn growth.
# Raising it to 256000 without restoring a second gate is the one change that silently
# reintroduces the failure this whole threshold exists to prevent.
#
# Do NOT set it below ~5000: a freshly spawned and seeded session measures ~4,800 on its very
# first turn, almost all of it cache.read (the standing-context prefix), so anything at or
# under that fires immediately and proves nothing. The 5K figure HARNESS.md once suggested is
# below the floor.
# HEALBOT_RETIRE_AT=20000; export HEALBOT_RETIRE_AT

# HEALBOT_RETIRE_HARD IS GONE. Deleted in Phase 7, not merely disabled -- if you have it in a
# shell profile or a script, remove it; nothing reads it.
#
# It was a second gate at 330000 that would retire mid-turn, aborting it, to bound the overshoot
# the first gate's finish-the-turn rule allows. The justification was a real measurement (one turn
# taking occupancy 5,216 -> 175,090 on its own). But it never once fired: the predicate that was
# supposed to hold the soft gate back read `finish` directly, and that field is set at every step,
# so the soft gate was already firing mid-turn and the hard gate's only consumer was dominated on
# 733/733 measured messages.
#
# Phase 7 made the predicate per-turn (opencode's own, prompt.ts:1295) and deleted this knob rather
# than resurrect it. The margin it was meant to provide now comes from HEALBOT_RETIRE_AT being low
# enough to absorb a worst-case turn -- see above. One gate, one number, no knob that reads as
# load-bearing and is not.

# Automatic retirement is ON by default: cross the gate, the turn in flight is allowed to FINISH,
# then a handoff goes to a fresh session, the old one is archived, and the successor picks the work
# up immediately. Nothing is aborted on this path. (For one commit in Phase 7 that was not true and
# this line said so; the predicate is per-turn now.) See the corrected
# description above the hard gate. Set to 0 for the old operator-initiated behaviour where the
# cell goes RETIRE and `x` performs the handoff.
# HEALBOT_AUTO_RETIRE=0; export HEALBOT_AUTO_RETIRE

# NOT SET, on purpose:
#   OPENCODE_DISABLE_DEFAULT_PLUGINS -- BREAKS THE HARNESS. The "default plugins" are the 10
#                                 built-in provider AUTH plugins. With OpenAI on oauth, this
#                                 switch makes model resolution fail outright:
#                                 "ProviderModelNotFoundError: Model not found:
#                                 openai/gpt-5.6-sol". Caught by the functional smoke test;
#                                 every measurement before that was taken on a config that
#                                 could not run a turn. It also saves zero tokens (no prompt
#                                 impact). Do not re-add.
#   OPENCODE_CONFIG_DIR        -- additive, does not isolate. Worse than a no-op: it MERGES
#                                 the harness config on top of the inherited global one.
#                                 TESTED -- with it set you still get the user's ollama
#                                 provider block, 18 skills and ~/.claude/CLAUDE.md while
#                                 believing you are isolated. Same for OPENCODE_CONFIG and
#                                 OPENCODE_CONFIG_CONTENT. (C1)
#   OPENCODE_DISABLE_AUTOCOMPACT -- only reaches the legacy compactor; the config file's
#                                 "compaction": {"auto": false} covers both engines (C2)
#   OPENCODE_DISABLE_PROJECT_CONFIG -- would also kill project AGENTS.md, which we want
#   OPENCODE_PURE              -- DO NOT SET. The earlier justification here ("already covered
#                                 by OPENCODE_DISABLE_DEFAULT_PLUGINS") was wrong twice over:
#                                 that switch is itself forbidden above, and the two gate
#                                 DISJOINT sets -- plugin/index.ts:166 gates INTERNAL (auth)
#                                 plugins, :177 gates EXTERNAL ones from config `plugin`.
#                                 Nothing has ever covered external plugins here, and this
#                                 harness's OWN trim-tools.ts is an external plugin, so
#                                 setting PURE would silently disable it. TESTED: PURE alone
#                                 changes model resolution not at all (19 openai models before
#                                 and after), so it buys nothing and costs the plugin layer.
