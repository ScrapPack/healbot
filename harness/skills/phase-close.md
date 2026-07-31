---
name: phase-close
description: The healbot phase-boundary close. Invoke BEFORE closing a phase, BEFORE writing a session handoff, and BEFORE any paid run — it runs the free suite's Tier 2 (gate/tier2.py) plus the per-change gate, and makes the records part of the close. A boundary without a tier-2 record shipped unverified.
---

# Phase close

The per-change gate (gate.py, enforced by the pre-push hook) runs only Tier 1 + scoped
lint. Everything else free — the probes that boot a TUI or a server, and the ones that
read living state — runs at PHASE BOUNDARIES, and this skill is that trigger. GATE.MAP.md
is the pipeline map; this is the checklist.

## When a boundary happens

- Closing a phase (fork/rig track) or a work track session (adoption track).
- Writing a handoff document — run this FIRST so the records land in the doc.
- Before anything paid: Tier 3 needs a clean free floor under it, or the paid run
  measures a broken tree (see the paid-run-protocol skill).

## The close, in order

1. `cd` to the repo root, then:

   ```
   .carryover/verified/venv/bin/python gate/gate.py          # tier 1 + lint, ~1s
   .carryover/verified/venv/bin/python gate/tier2.py         # the rest of the free suite, ~4-5 min
   ```

2. Read the verdicts. Both write records into `gate/runs/` (`<ts>.json`,
   `<ts>-tier2.json`); the handoff or phase-close note cites BOTH paths.

3. A BLOCKED probe ran and said no. Before writing it down, classify it against the
   known-red register below — a red that is not on that register is a FINDING and stops
   the close until a human sees it. Never extend "probably drift" to a new red.

4. A probe in ERROR could not run. That claim is unmeasured; say so in the close. An
   unmeasured claim is not a pass (docs/CLONE.md is the record of what believing
   otherwise cost).

5. Tier 3 (`verify_*` rigs) stays un-run unless the owner said go — it is PAID. The
   close names it NOT RUN, which is honest and free.

## Known-red register

Maintained here, one entry per accepted red, each with its acceptance decision:

- **probe_turn_growth.py 18/19** — the live opencode.db fixture-count row (677/56/733
  cited vs a live DB that keeps growing). Count drift only; the IN-SCOPE bound must be
  UNMOVED (70,704 / 289,296 / 30.4% — the probe prints them side by side). Accepted
  2026-07-31 pending the owner's decision on refreshing the fixture across HARNESS.md
  and five docs. A moved in-scope figure is NOT this entry — that is a finding.

## Why this is a skill and not a hook

The pre-push hook fires per change, and Tier 2 must not (minutes per run; GATE.MAP.md).
No structural event marks "phase boundary" in this environment, so the trigger is
procedural — but it is backstopped: gate.py prints the tier-2 pointer on every push, and
a close without a `-tier2.json` record is visible by absence, the same signal the
publish flow uses for unverified pushes.
