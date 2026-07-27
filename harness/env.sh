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
# Defaults to 256000. This line used to say "inside the grid"; the number is right and the place
# was wrong. Since Phase 6 the ENFORCING default lives in the SERVER plugin --
# config/opencode/plugin/healbot.ts:110 -- which is the only thing that retires anything. The grid
# reads the same variable at fork/.../healbot.tsx:53 purely to paint: the RETIRE border, the
# `N to retire` count, the share-of-gate figure. Both default to 256000, so they agree until you
# set this for one process and not the other, and the process that matters is the server's.
#
# Set this only to exercise retirement cheaply, since reaching the real gate on a frontier model
# on purpose is expensive. TESTED at 20000.
#
# WHY 256000 AND NOT 350000. The ceiling is ~360K, NOT the 922,000 limit.input the model
# registry advertises: a session driven up took its last good turn at occupancy 359,829 and
# then failed 25 turns in a row with the provider's ContextOverflowError. Nothing is truncated
# on the way -- opencode sends the whole history every turn until the provider refuses it -- so
# the failure is a cliff, not a slope, and the threshold needs real headroom rather than the
# ~10K that 350K left. See docs/HARDEN.md §6.
#
# Do NOT set it below ~5000: a freshly spawned and seeded session measures ~4,800 on its very
# first turn, almost all of it cache.read (the standing-context prefix), so anything at or
# under that fires immediately and proves nothing. The 5K figure HARNESS.md once suggested is
# below the floor.
# HEALBOT_RETIRE_AT=20000; export HEALBOT_RETIRE_AT

# NO EFFECT UNDER THE SHIPPED PREDICATE. Setting this changes nothing. The variable and its
# 330000 default are kept in the code rather than deleted, and are logged at arm time, but they
# cannot decide an outcome.
#
# This block used to read: "the HARD gate, default 330000. Crossing HEALBOT_RETIRE_AT lets the
# turn in flight finish; crossing this one retires mid-turn, aborting it" -- justified by a
# measured turn that took occupancy 5,216 -> 175,090 on its own. The measurement is real; the
# semantics were not. HEALBOT_RETIRE_AT already fires at a STEP boundary and already aborts the
# turn in flight, so this gate's only consumer -- healbot.ts's `if (!stepOver && !hard) return`
# -- is dominated and never runs. VERIFIED in the code, MEASURED on 733 real assistant messages
# (733/733 arrive at a step boundary). It becomes live again the day the predicate is made
# per-turn, which is the reason it is kept.
#
# See HARNESS.md, "The gate fires at a STEP boundary, not at the end of a turn" -- the
# load-bearing-facts block, which names the one function that would resurrect this knob.
# HEALBOT_RETIRE_HARD=330000; export HEALBOT_RETIRE_HARD

# Automatic retirement is ON by default: cross the gate, and at that step boundary the turn in
# flight is ABORTED, a handoff goes to a fresh session, the old one is archived, and the successor
# picks the work up immediately. This line used to say "finish the turn" -- see the corrected
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
