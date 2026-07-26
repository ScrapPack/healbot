#!/bin/sh
# Healbot harness environment.
#
#   . ~/Desktop/healbot/harness/env.sh    then run `opencode` as normal
#
# Every switch below is here because it was measured, not assumed. See docs/STRIP.md.

HARNESS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# Config isolation. XDG_CONFIG_HOME is the ONLY thing that actually redirects the global
# config root -- OPENCODE_CONFIG_DIR is additive and changes nothing about inheritance
# (docs/SCAN.md C1, TESTED both ways). Global.Path.config is derived from xdgConfig at
# module load, so this must be exported before opencode starts.
XDG_CONFIG_HOME="$HARNESS_ROOT/config"
export XDG_CONFIG_HOME

# Skill trees. Skills key off $HOME, not the config dir, so XDG isolation alone leaves all
# 18 in place. This is the switch that actually drops them (18 -> 1, 20 -> 3 commands).
# Also a security lever: a SKILL.md body containing !`cmd` shell-executes on slash-invoke
# with no permission check (docs/SCAN.md §7).
OPENCODE_DISABLE_EXTERNAL_SKILLS=true
export OPENCODE_DISABLE_EXTERNAL_SKILLS

# Drops ~/.claude/CLAUDE.md from the instruction chain (and redundantly the .claude skills
# half). Project-level AGENTS.md still loads -- deliberately, that is where real
# project-specific facts belong.
OPENCODE_DISABLE_CLAUDE_CODE=true
export OPENCODE_DISABLE_CLAUDE_CODE

# Tool-description trimming: OFF by default, opt-in and reversible. See
# config/opencode/plugin/trim-tools.ts for why it is not a default.
# HARNESS_TRIM_TOOLS=1; export HARNESS_TRIM_TOOLS

# NOT SET, on purpose:
#   OPENCODE_DISABLE_DEFAULT_PLUGINS -- BREAKS THE HARNESS. The "default plugins" are the 10
#                                 built-in provider AUTH plugins. With OpenAI on oauth, this
#                                 switch makes model resolution fail outright:
#                                 "ProviderModelNotFoundError: Model not found:
#                                 openai/gpt-5.6-sol". Caught by the functional smoke test;
#                                 every measurement before that was taken on a config that
#                                 could not run a turn. It also saves zero tokens (no prompt
#                                 impact). Do not re-add.
#   OPENCODE_CONFIG_DIR        -- additive, does not isolate (C1)
#   OPENCODE_DISABLE_AUTOCOMPACT -- only reaches the legacy compactor; the config file's
#                                 "compaction": {"auto": false} covers both engines (C2)
#   OPENCODE_DISABLE_PROJECT_CONFIG -- would also kill project AGENTS.md, which we want
#   OPENCODE_PURE              -- despite the name it only disables external plugins,
#                                 which OPENCODE_DISABLE_DEFAULT_PLUGINS already covers
