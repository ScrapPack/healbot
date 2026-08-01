# NEXT — the prompt for a fresh session

Paste the block below into a new agent session at `~/Desktop/healbot`.

**This file is FROZEN at a constant shape** (2026-07-31): the task list, the decided list,
and pointers. Nothing else. It grew 4.3x across phases 5-12 by accreting method prose, in a
project whose premise is cutting standing context; that stops here. The working method now
lives in five skills (canonical copies in `harness/skills/`, installed at
`~/.agents/skills/<name>/SKILL.md`, surfaced to Claude Code via `~/.claude/skills/`
symlinks). The traps registry stays in HARNESS.md's "Traps" section, mirrored by the
healbot-traps skill. Per-probe expected scores live in each probe's own `Results(expect=N)`
floor and nowhere else; five prose copies of those counts went stale, the floors never did.

**The maintenance rule:** a phase updates the TASK and DECIDED sections only. A method
lesson lands in a skill or a probe; a trap lands in HARNESS.md and the healbot-traps skill;
history lands in the phase doc. If editing this file changes its line count, check for
citations into it first (the citation-hygiene skill; docs cite this file by section name,
never by line).

---

## The prompt

```
Continue the healbot build at ~/Desktop/healbot. Phase 12 is complete and committed; the
fork overlay is pinned at 509f4c0b1 (probe_twin.py verifies the pin and all 17 overlay
files).

READ FIRST: HARNESS.md, the root index. Stop when you can name the file that owns any given
behaviour; follow its pointers into the phase docs on demand instead of reading the tree.
The test rig's manual is .carryover/verified/README.md.

METHOD, in one line: classify every claim VERIFIED (read the code, cite file:line) /
TESTED (ran it, real exit code captured) / INFERRED / SUSPECTED, and never present a lower
tier as a higher one. Four skills carry the rest of the method; invoke each BEFORE the
matching work:
  /rig-assertion-discipline   before creating or editing any probe_* or verify_* rig
  /citation-hygiene           before editing any .md containing file:line citations
  /paid-run-protocol          before anything that spends API credits
  /healbot-traps              when touching fork/, rig, or harness code, or when behaviour
                              contradicts expectation

VERIFY: run the free suite before and after your work, from .carryover/verified:
  for p in probe_*.py; do venv/bin/python "$p"; echo "$p exit=$?"; done
Every probe must exit 0; each declares and prints its own floor. probe_turn_growth.py's
real-corpus fixture counts drift as the live opencode.db grows: count drift alone is not a
finding, a moved IN-SCOPE maximum or bound is (the probe prints both populations).
Gate before claiming done:
  .carryover/verified/venv/bin/python gate/gate.py
Every phase revises the artifacts it contradicts: write docs/<PHASE>.md, update HARNESS.md,
and fix any figure you disprove, in the same change.

DECIDED — do not reopen any of these as a defect, and do not "fix" them:
  - RETIRE_AT stays 180,000. The sizing corpus has a DECLARED SCOPE (completed turns,
    started at or above GATE_FLOOR 100,000, compaction off): in-scope max 70,704, bound
    289,296, margin 109,296 = 30.4%. docs/OUTCOME.md §11. Valid only while the harness
    config pins gpt-5.6-sol; probe_turn_growth.py asserts the pin. The named residual: a
    single turn from an EMPTY session larger than the ~360K ceiling dies at ANY RETIRE_AT.
  - NO startup sweep. Retirement stays purely event-driven; a session parked over the gate
    at server restart stays there until its next turn ends. docs/GROWTH.md (Phase 8 §5).
  - The five wait_for SEQUENCING gates that read the raw box stay as they are. Converting
    them trades a fast red for a seven-minute timeout. docs/OUTCOME.md §2.
  - /code-review ultra has been run. HARNESS.md and three phase docs deliberately carry it
    as an open row; leave them.

YOUR TASK — Phase 13. Everything in the build order is built and every known correctness
hole is closed. Nothing is blocking you. Do not invent something to build.
  1. FREE, start here: run the suite. In each of the last five phases the finding came from
     reading a surface nobody had read AS AN ARTIFACT (a derivation, the suite from a fresh
     clone, the paid rigs as source, the prose as pointers, the shared library). If you find
     one, that IS the phase.
  2. FREE TO WRITE, paid to test; pair each with the next paid run (per the
     paid-run-protocol skill). Detail for all four: docs/OUTCOME.md §7-9.
     - verify_question.py: three assertions red since Phase 5 assume auto-surface does not
       exist; rewrite them to the surfacing behaviour and derive the session count.
     - The three single-use rigs compare the grid header to a DB literal; derive the count
       from what the rig created.
     - rig.fixtures() should write hb/project's .gitignore as part of the declared fixture.
     - Bound wait_for's timeout (Api takes its timeout from the wrapping budget).
  3. PAID, ASK FIRST, most valuable: no real near-gate turn has ever been measured on the
     pinned model. Drive a gpt-5.6-sol session to ~150,000 occupancy, then ONE read-heavy
     final turn (the 130 KB ledgers, NOT a synthetic fixed chunk: eleven of the twelve
     in-scope pinned-model turns already ARE the synthetic loop, which is the gap), and
     record the delta. A variant of verify_retire_350k.py's growth loop with a different
     final turn. Clean workspace per the paid-run-protocol skill.
  4. PAID, ASK FIRST: re-run verify_handoff.py before its recorded score is ever quoted
     again; its floor is 22 and the recorded 21/21 is unreachable. Workload: three ~130 KB
     ledgers read in full plus file creation, so not free, but nowhere near the 350K rig.
  5. PAID, ASK FIRST, cheapest: the 180,000 gate has never been FIRED at its real value
     (exercised at 20,000; the remaining half is a single >= already argued
     threshold-independent). Use verify_retire_350k.py's growth loop retargeted.
  6. PAID, optional: an EXTERNAL plugin's route has never been RENDERED under real
     workload; everything TESTED so far was on the builtin path.

Ask me before spending real API credits on anything beyond a few turns.
Never set XDG_DATA_HOME: auth.json lives there and OpenAI is on oauth.
```

---

## For the maintainer of this file

History and current-state narrative live in the phase docs (`docs/`), the commit log, and
HARNESS.md; this file no longer duplicates them. The freeze and the skill conversion are
recorded in this file's own git history and the freeze commit's message. If a future phase
needs to grow this file, the burden of proof is on the growth: the prompt above fit
Phase 13 in about 70 lines.
