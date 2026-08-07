# Where the daily-driver workflow actually hurts

Type: grilling
Mode: HITL
Status: closed
Assignee: captain
Blocked by: -

## Question

The captain reports the human end-to-end path is weak and is still using stock Claude Code instead
of the harness. Where, specifically?

This is charting step 2, the breadth-first grilling that should have preceded the map and did not.
Fan out across the whole path rather than deep on any thread. The map's fog was seeded by
inspection in one session, so it is thinner than the real fog; this ticket is expected to graduate
several patches of **Not yet specified** into tickets, and may rule others out of scope.

Ground the exchange in the path as it exists, not as documented:

- Cold start. What does the captain do first on a new day, and what does that cost in keystrokes,
  waiting, and remembering?
- Where does the harness ask for something stock Claude Code does not, and is each one paying for
  itself?
- Which documented verbs has the captain never used, and why? `docs/E2E.md` walked the path once as
  an operator and closed its findings, but a walk is not a habit.
- What does the captain currently do in stock Claude Code that the harness cannot do at all?
- What breaks or annoys often enough that the captain has built a workaround?

Do not propose fixes during the grilling. Surface the decisions, then wire them as tickets.

The one candidate already found, by inspection rather than by being told: a fresh session in this
repo starts with no project memory and gets it only from a hand-pasted `NEXT.md` block. That is
ticket 02, which is blocked by this one, because a first cut at a fix already exists and the
question is whether it addresses the real pain or a guessed one.

## Comments

**2026-08-05, found while gathering facts for the grilling: the harness config root has no skills
and no plugins, so a harness session may load none of the method the repo mandates.**

VERIFIED:

- `harness/env.claude.sh` sets `CLAUDE_CONFIG_DIR` to `harness/claude`, and its own comment states
  that this "redirects the ENTIRE user config root — settings, CLAUDE.md, skills, agents, hooks,
  AND auth/state."
- `harness/claude/` contains no `skills/`, no `agents/`, and no `commands/` directory. Its
  `plugins/` holds only `known_marketplaces.json` and an empty `marketplaces`, against the default
  root's `installed_plugins.json`, `cache`, `data` and `blocklist.json`.
- `harness/install-skills.py` hard-codes its Claude surface to `~/.claude/skills`, the DEFAULT
  root, with no `CLAUDE_CONFIG_DIR` awareness.
- `harness/doctor.py`'s skill-twins row names that same default root as the claude surface. So the
  doctor verifies skills are installed at a root the harness deliberately redirects away from.
- Nothing in `env.claude.sh`, `hb-fleet.sh`, `doctor.py` or `install-skills.py` wires skills into
  the redirected root.

## Resolution

Grilled 2026-08-05, two rounds. The pain is **not** where the map guessed.

**It is not a missing feature. It is operator knowledge.** Asked directly what made the captain
open stock Claude Code that morning, the answer was "I don't know how to operate within the
harness." `docs/E2E.md` already exists as a written operator walk and did not close this, so
another document is not the fix.

**The benefit the captain wants is not the one the harness advertises.** Not retirement, and not
compaction-off. It is work parallelization across many Claude Code sessions, collapsed into one
navigable terminal, with neovim showing only the diffs a human must judge while everything below
that bar clears through automatic review.

**Scope is all projects, not healbot.** healbot is the primary work environment for every project.

**The normal interaction shape is crew, not solo.** The captain drives `/firstmate` with
`/wayfinder` and the planning skills to set parallel building sessions. This inverts the map's
original assumption and puts ticket 03 on the critical path.

Four decisions taken, each now a line on the map:

1. **Destination redrawn** to the four testable conditions above.
2. **The review bar is severity, fail-closed, plus a path escalation** for `harness/`, `gate/` and
   `fork/`. `gate/review.py`'s `blocking` mode already implements the severity half and is switched
   off. The missing half is the handoff: nothing carries a blocked diff to the captain's eyes.
3. **Firstmate drives the cockpit.** New fleet verbs for pane selection and opening a diff, so the
   only thing the captain learns is how to talk to firstmate.
4. **Plain `git worktree` per project** for non-healbot crew workspaces. The pool is healbot-only by
   construction and Mac-only by mechanism, and the PC is wanted. Generalizing it stays a measured
   decision, not an assumed one.

Plus the finding in Comments above, which is the likely mechanical half of "I don't know how to
operate it": the harness config root carries no skills and no plugins.

Graduated into tickets 09 through 14. Ticket 02 unblocked and re-scoped.
