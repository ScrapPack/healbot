# Domain docs

How the engineering skills should consume this repo's domain documentation.

Layout: **single-context**. There is no `CONTEXT-MAP.md` and there will not be one.

## TRAP: three of the filenames these skills expect are BANNED in this tree

`gate/gate.py`'s `BANNED` set refuses `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md` and `SKILL.md`
anywhere in the tree, as a BLOCKED gate row on any change that adds one. The first three
auto-ingest into every opencode session's context window
(`packages/opencode/src/session/instruction.ts`), which is the exact cost this project exists to
remove; `SKILL.md` collides with opencode's skill glob, where a body containing a bang-backtick
substitution shell-executes on slash-invoke with no permission check. HARNESS.md's "Naming"
section is the invariant; the gate is its enforcement.

This bites two skills directly:

- **`/domain-modeling`** says "if no `CONTEXT.md` exists, create one when the first term is
  resolved." **Do not.** It would block the next push.
- **`/grill-with-docs`** creates `CONTEXT.md` and ADRs lazily for the same reason. Same answer.

**What to do instead.** This repo's glossary and its "which file owns this behavior" index are
both `HARNESS.md`, and its architectural decisions are recorded in two places that already exist:
the `DECIDED` section of `NEXT.md` for standing decisions, and the dated phase records under
`docs/` for the evidence behind each one. When a term needs pinning or a decision needs recording,
put it there. If a glossary file is genuinely wanted later, it needs a name outside the banned
set and an owner's decision, not a lazy creation mid-session.

## Before exploring, read these

- **`HARNESS.md`** at the repo root. It is the index. Its own exit test is that from it alone you
  can name the file that owns any given behavior.
- **`NEXT.md`**, specifically its `DECIDED` section, before proposing anything that looks like a
  fix. Those entries are closed on purpose and several read as defects to a fresh reader.
- The **dated phase record** under `docs/` for the area you are touching. `HARNESS.md` indexes
  them newest first and says what each one settles.
- **`docs/adr/` does not exist.** Proceed silently; do not flag its absence and do not create it.

## Use the repo's vocabulary

When your output names a domain concept, use the term as `HARNESS.md` and the phase records use
it. The load-bearing ones: **retirement** (a session crosses a threshold, finishes its turn,
writes a handoff, and a fresh session continues), **the gate** (the per-change check wired into
`git push`), **a probe** (a free assertion rig with a declared floor), **a rig** (a paid
measurement), **the fleet** (tmux crew sessions), **captain** and **crewmate**, **the pool**
(leased worktree slots), and **a twin** (two copies of one file that a checker keeps in sync).

## Flag contradictions rather than overriding them

If your output contradicts a `DECIDED` entry or a phase record's finding, surface it explicitly
with the evidence, in the repo's own classification: VERIFIED (read the code, cite the file),
TESTED (ran it, captured the exit code), INFERRED, or SUSPECTED. Never present a lower tier as a
higher one. Silently overriding a recorded decision is the failure this whole record exists to
prevent.
