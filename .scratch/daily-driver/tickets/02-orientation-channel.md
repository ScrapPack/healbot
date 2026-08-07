# Is /orient enough to replace the pasted NEXT.md block

Type: grilling
Mode: HITL
Status: open
Assignee: -
Blocked by: 01

## Question

A fresh session in this repo starts with zero project memory. Today the captain pastes `NEXT.md`'s
prompt block by hand, which is single-slot, manual, and maintained by human discipline.

A first cut shipped 2026-08-05: `.claude/commands/orient.md`, a project slash command that reads
`HARNESS.md`'s index and Agent-skills section, reads `NEXT.md`'s `DECIDED`, runs the frontier query,
reads each live map's Destination and Decisions-so-far, checks tree state, then reports and stops.

It was written to work within the constraint rather than against it: a root `CLAUDE.md` is refused
tree-wide by `gate/gate.py`'s `BANNED` set, because those filenames auto-ingest into every opencode
session, which is the cost this project exists to remove. On-demand orientation is the project's own
thesis applied to itself.

Open, and this is a decision rather than a build:

- Does `/orient` load the right things? It currently loads four surfaces. Too few, too many?
- Is a slash command the right channel at all, or does orientation want to be automatic, which on
  the Claude Code side means a `SessionStart` hook writing into the session rather than a file the
  captain invokes?
- Does `NEXT.md` shrink to a pointer once this holds, and what happens to the documents that cite
  it by section name? `/citation-hygiene` before touching it.
- Whether `/orient` should differ for a crewmate and for the captain. A crewmate's world is its
  brief by design, so orientation may be a captain-only verb.

**VERIFIED 2026-08-05:** `/orient` registers as a live skill in a session on this repo, so a
project-level `.claude/commands/` entry does load. What is still untested is whether it loads with
`CLAUDE_CONFIG_DIR` pointed at `harness/claude/`, which ticket 09 settles for skills generally.

## Comments

**Re-scoped 2026-08-05 by ticket 01's grilling. Read this before working the question above.**

Two of round 1's answers change what this ticket is asking.

**Orientation is probably not the captain's job to invoke.** The grilling decided that firstmate
drives the interaction and the captain learns only how to talk to firstmate. That makes a slash
command the captain has to remember a half-fix at best. The live options are now: firstmate orients
itself and reports, a `SessionStart` hook orients automatically, or `/orient` survives as a manual
override for the times the captain wants it. The first is most consistent with everything else
decided.

**It has to work for any project, not this one.** healbot is the primary work environment for all
projects, so `/orient` as written is anchored to a repo that has `HARNESS.md`, `NEXT.md` and a
`.scratch/` map. In a fresh project none of those exist. Either the command degrades honestly to
"this project has no map yet, want one?", or project onboarding becomes its own ticket. Decide which
here rather than letting a fresh project produce a confusing report.
