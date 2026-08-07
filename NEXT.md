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
Continue the healbot build at ~/Desktop/healbot. Phase 14 (windows parity for the
daily-driver halves, doctor preflight, public-repo hardening: LICENSE, the path scrub, the
gate's home-paths invariant — docs/WINDOWS.md, README.md) is complete; the fork overlay is
pinned at 509f4c0b1 (the pin is recorded in fork/README.md — the patch itself carries no
hash; probe_twin.py verifies fork/ and the checkout agree byte-for-byte, floor 17 files).

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
  - lavish-axi is REJECTED for now (vendor bill vs. need, docs/SHIP.md §4); nvim gets NO
    repo machinery (coexistence is the pool's job); Claude Code's native --tmux/--worktree
    spawning stays unused (the fleet owns its topology and manifest). Do not re-open any
    of the three without a demonstrated need.
  - The claude harness settings pin ("opus" / effortLevel "xhigh" / permissions.defaultMode
    "bypassPermissions", owner directive 2026-08-01; the model was "sonnet") is a
    DISCIPLINE pin, not a measured one. Fable 5 (`--model fable`) is the recorded per-spawn
    escalation for planning and long-form-synthesis briefs, never the default. NO retirement
    threshold is verified for any Claude model. Hand off early; do not copy the opencode
    numbers across.
  - The decision-record store lives OUTSIDE every repository, at ~/.healbot/records/, keyed
    on the main worktree root. Not gitignored-in-repo (that needs a .gitignore written into
    a project you do not own) and not XDG (env.sh and arms.py both rewrite XDG_CONFIG_HOME,
    so it would split per harness root and per A/B arm). It does not travel with a clone;
    that cost was accepted. docs/RECORDS.md §3.
  - Every BACKFILLED record is INFERRED, and INFERRED never reaches the orientation block.
    That pairing is what makes a free lossy import safe. Do not "upgrade" backfilled records
    in bulk to make them retrievable — they already are, through recall. docs/RECORDS.md §6.
  - The store WARNS and never blocks. The doctor's three `record store` rows gate a tier on
    FAIL only, an empty store is a WARN, and no push is ever refused over a record. False
    positives train the operator toward --no-verify, which also silently disables the
    evidence publisher. docs/RECORDS.md §8.
  - NEXT.md's DECIDED section does NOT retire into the store. It is operator-facing and
    frozen at a constant shape; the store is agent-facing and out of tree. Whether it ever
    moves is an open decision with an existing owner. Do not open it as part of other work.

YOUR TASK — Phase 15. Everything in the build order is built and every known correctness
hole is closed. Nothing is blocking you. Do not invent something to build.
  0. FLEET BRING-UP RESIDUE — DONE 2026-08-03, do not re-spend on it. All three screen
     markers and all three hook events are MEASURED against a live crewmate on 2.1.220,
     and the pinning session found two things it was not looking for: every healthy
     crewmate read `ambiguous` (pane_current_command is the CLI VERSION), and `kill`
     leaves the pool lease held. Both recorded in docs/SHIP.md §5; both are fixed and
     guarded (the kill lease closed 2026-08-03 with E2E.md's other open items, §7). What is still UNMEASURED on the claude side
     is the retirement marker (~300K, INFERRED) — that needs occupancy near the marker,
     not another bring-up run.
  1. FREE, start here: run the suite. In each of the last five phases the finding came from
     reading a surface nobody had read AS AN ARTIFACT (a derivation, the suite from a fresh
     clone, the paid rigs as source, the prose as pointers, the shared library). If you find
     one, that IS the phase.
     Then read the decision records: `python3 harness/memory.py recall ""`. They are new as
     of 2026-08-06 and they are the surface nobody has read yet.
  1b. THE CITATION-STALENESS STAGE IS IN SHADOW MODE AND NEEDS PUSHES, not work. It writes
     gate/runs/*-staleness.json on every push from a branch carrying it and prints nothing.
     13 records exist, several of them replays of one range, against an acceptance of 15-20
     REAL pushes. Phase 3 (operator-visible output + the reviewer scope carve-out) stays
     gated until a human reads the distribution: two independent replays disagreed by more
     than 4x on the mean and both were lower bounds. Note the stage as built has NO blocking
     mode, deliberately (gate/staleness.py's header argues it); Phase 3's design assumed one.
  1c. THE DECISION-RECORD STORE IS BUILT AND UNMEASURED. Mechanism is proven 68/68
     (probe_memory_store.py); whether it improves an agent's work is not, and docs/RECORDS.md
     §9 names the three blockers that put that measurement out of reach — the arm factory
     cannot express a memory-on/memory-off contrast, it sets no Claude config root, and
     neither driver supports the multi-turn shape the value actually has. Do not quote a
     benefit. The Claude-side SessionStart output contract is INFERRED, not TESTED.
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
  7. FREE, on the PC: clone, run `python harness/doctor.py`, and work docs/WINDOWS.md's
     conversion checklist — every native-Windows claim is INFERRED until that run happens
     on that machine.

Ask me before spending real API credits on anything beyond a few turns.
Never set XDG_DATA_HOME: auth.json lives there and OpenAI is on oauth.
```

---

## Open on the Mac, from the Windows bring-up (2026-08-05)

Smaller, also open: the repo pins no ruff config anywhere, so the gate's lint verdict is
whatever the installed ruff version defaults to and differs by machine. Under that
config-less invocation ruff calls the `# noqa: E402` in `probe_citations.py` unused and
offers to delete it — but under the ruleset `docs/PLAINCODE.md` documents, E402 fires on
that exact line. Running `ruff --fix` there would strip a directive the documented standard
needs.
