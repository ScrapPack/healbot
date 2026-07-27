# NEXT — the prompt for a fresh session

Paste the block below into a new agent session at `~/Desktop/healbot`. Everything else in this
file is context for whoever maintains the prompt; the agent only needs the block.

The prompt is short on purpose. This project's method is that a phase reads the written
artifacts, never the prior transcript — and the project exists to cut standing context, so a
handoff that pastes ten thousand words of history is working against its own premise.

---

## The prompt

```
Continue the healbot build at ~/Desktop/healbot. Phase 5 is complete and committed.

READ FIRST, in this order. Stop when you can name the file that owns any given behaviour:
  1. HARNESS.md          — root index: load-bearing facts, Traps, Closed, Still open
  2. docs/HARDEN.md      — Phase 5: what the Phase 4 audit forced, the fleet, the two
                           retirement gates, and the measured ~360K ceiling
  3. .carryover/verified/README.md — the test rig and its assertion discipline

Do NOT read the whole tree first. HARNESS.md indexes everything; follow it on demand.

YOUR TASK — Phase 6, in this order:

  1. Make auto-retirement headless. It works (13/13, docs/HARDEN.md §7) but the trigger is a
     createEffect INSIDE the route component, so it only fires while the grid is open. A fleet
     left running with no client attached retires nothing. Move it to plugin scope, driven off
     `message.updated`, which carries the assistant tokens the occupancy check needs. This
     completes the lifecycle the owner specified: gate met -> finish the turn -> hand off ->
     retire -> successor starts immediately, with no turn consumption after the gate.

  2. Close the two cheap open questions (~20 min each):
       - Focus (`enter` -> the session route) is build-order step 4, three lines of code, and
         has NEVER been tested. The gate was about *not* focusing, so nothing exercised it.
       - The `question.rejected` half of the cold-start reconcile is source-reading only. The
         permission half is TESTED (verify_cold.py). No rig rejects a question that predates
         the client.

  3. Build the control agent — build-order step 5 (PLAN.md:378), the last non-optional
     unbuilt step: its own session with tools to spawn / prompt / abort / retire the others.
     Two of the three endpoints are already exercised inside retire(); /abort landed in
     Phase 5. What is missing is the agent shell and its tool definitions.

METHOD — this project's standard, and it is not decoration:
  - Classify every claim VERIFIED (read code, cite file:line) / TESTED (ran it) / INFERRED /
    SUSPECTED. Never present a lower tier as a higher one. Cite file:line and open the file.
  - This suite's characteristic failure is PASSING. Eight assertions across the effort were
    found incapable of failing, against four real defects tests actually caught. Every new
    assertion needs a negative control or a mutation check — prove it can fail before you
    trust it green.
  - Run the FREE probes before spending anything:
      cd .carryover/verified
      venv/bin/python probe_on_grid.py      # 4/4   route predicate discriminates
      venv/bin/python probe_error_state.py  # 10/10 hard-errored session renders ERROR
      venv/bin/python probe_fleet.py        # 10/10 harness/fleet.sh does what it claims
    The credit-spending rigs are listed in .carryover/verified/README.md. verify_retire_350k.py
    is ~5M cumulative input tokens — do not run it casually.
  - Gates before you claim done, from ~/Desktop/healbot/opencode:
      ./node_modules/.bin/tsgo --noEmit -p packages/tui/tsconfig.json    # expect exit 0, no output
      ./node_modules/.bin/oxlint packages/tui/src/feature-plugins/system/healbot.tsx
                                                                        # expect exit 0, 3 warnings
  - Every phase revises the artifacts it contradicts. Write docs/<PHASE>.md, update HARNESS.md,
    and fix any figure you disprove. Do not leave a stale number in a file that another session
    will trust.

TRAPS THAT COST REAL TIME — all measured, all in HARNESS.md, repeated here because each one
silently produces a wrong result rather than an error:
  - The installed `opencode` binary has NO grid. The Healbot route is a builtin of the fork.
    Run from source: rig.py's OC constant, or harness/fleet.sh which resolves it for you.
  - The rig's Api MUST send `x-opencode-directory`. Omit it and every call succeeds, the
    sessions are there, and the grid shows `0 sessions` — you are addressing a different
    instance (workspace-routing.ts:87 falls back to process.cwd()).
  - The rig's project dir needs its own git repo (rig.git_baseline()). It is gitignored by this
    repo, and session diffs are computed with git, so without it every changed file is invisible.
  - Never set XDG_DATA_HOME. auth.json lives there and OpenAI is on oauth; redirecting it
    strands the credentials and the model pin stops resolving. Isolate the DB only, via rig.db().
  - Term.find() is case-INSENSITIVE and the project path contains "healbot". Use rig.on_grid()
    for route assertions and t.exact() for cell labels.
  - Session ids are DESCENDING identifiers, so ascending sort is newest-first.
  - The context ceiling is ~360K, NOT the 922,000 limit.input the model registry advertises.
    Nothing is truncated on the way up — it is a cliff, not a slope.

Ask me before spending real API credits on anything beyond a few turns.
```

---

## Why these three, in this order

**1 finishes what Phase 5 started.** The owner's specified lifecycle is implemented and tested,
but only under a condition the owner did not specify — that someone is looking at the grid. That
is the gap most likely to bite in real use, and it is the smallest of the three.

**2 is two cheap closures** that have been open since Phase 4 and keep getting deferred because
neither is in any exit gate. They are ~20 minutes each and they retire two rows from *Still
open*, which is worth more than their size suggests: an open question nobody closes eventually
gets treated as closed.

**3 is the last non-optional unbuilt step** of the original build order, and it is genuinely
medium-sized. Doing it before 1 would mean building an agent that spawns and retires sessions on
top of a retirement trigger that only runs when a human is watching.

Deliberately **not** in the prompt:

- **Worktree isolation** (build-order step 7). `PLAN.md` marks it optional and nothing needs it
  yet.
- **The 256K gate end to end.** The threshold comparison is a single `>=` and the path is TESTED
  at 20,000; a full-scale run is real money for low information.
- **`/code-review ultra` on the `harness/` diff.** Still Phase 3's unmet gate, still user-
  triggered — an agent session cannot launch it. It stays the owner's action.

## Current state, for the maintainer of this file

Phase 5 landed across four commits (`823d7a2`, `d61cc5e`, `d2e2e27`, `650ae72`), overlay at fork
`467ba9b`. Six defects fixed, the rig made able to fail, `serve` + `attach` built, retirement
automatic at two gates. Test results: 25/25 at full scale, 21/21 cold reconcile, 13/13 auto
retirement, plus 4/4, 10/10 and 10/10 free.
