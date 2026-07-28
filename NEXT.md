# NEXT — the prompt for a fresh session

Paste the block below into a new agent session at `~/Desktop/healbot`. Everything else in this
file is context for whoever maintains the prompt; the agent only needs the block.

The prompt is short on purpose. This project's method is that a phase reads the written
artifacts, never the prior transcript — and the project exists to cut standing context, so a
handoff that pastes ten thousand words of history is working against its own premise.

---

## The prompt

```
Continue the healbot build at ~/Desktop/healbot. Phase 9 is complete and committed; the fork
overlay is pinned at 509f4c0b1 (unchanged — Phase 9 built nothing in the fork and spent nothing).

READ FIRST, in this order. Stop when you can name the file that owns any given behaviour:
  1. HARNESS.md          — root index: load-bearing facts, Traps, Closed, Still open
  2. docs/CLONE.md       — Phase 9: the suite could not tell "everything passed" from "almost
                           nothing ran". From a FRESH CLONE three probes exited 0 having proven
                           nothing, and probe_turn_growth.py's two load-bearing assertions get
                           EASIER as their evidence disappears — 48.2% margin instead of 1.3%, in
                           green. Both fixed and controlled in both directions
  3. docs/GROWTH.md      — Phase 8: `worst_turn` was ONE measurement and it was not the worst.
                           The pinned model's worst is 175,148, the bound on RETIRE_AT is 184,852,
                           and the shipped 180,000 clears it by 1.3%. The threshold is
                           MODEL-SPECIFIC. Also: `healbot_*: deny` is a context control, NOT a
                           sandbox. (CLONE.md §4 annotates its corpus counts; its findings stand)
  4. .carryover/verified/README.md — the test rig and its assertion discipline

Do NOT read the whole tree first. HARNESS.md indexes everything; follow it on demand.

YOUR TASK — Phase 10. Everything in the build order is built, every known correctness hole is
closed, and Phase 9 closed the last free one. There is NO decision pending on me and nothing is
blocking you. Do not invent something to build.

  0. TWO THINGS ARE DECIDED. Do not re-open either as a defect, and do not "fix" them.
     - RETIRE_AT STAYS AT 180,000. Phase 8 re-derived the worst_turn that sizes it (175,148 on the
       pinned model, bound 184,852, margin 1.3% of the ~360K ceiling) and offered four options; the
       answer was leave it and correct the prose. What that ACCEPTS is in docs/GROWTH.md §1 and is
       inherited knowingly. Phase 9 STRENGTHENED it: the corpus grew 14% (86 -> 94 turns) and every
       maximum, bound and conditional was unchanged (docs/CLONE.md §4). It is the first evidence the
       derivation is stable under corpus growth, not a reason to revisit it.
     - NO STARTUP SWEEP. Retirement stays purely event-driven. A session parked over the gate when
       a server restarts stays there until its next turn ends. Decided in Phase 8 §5.
     The one LIVE constraint out of all that: RETIRE_AT is verified only while opencode.jsonc:16
     pins gpt-5.6-sol. probe_turn_growth.py asserts the pin.

  1. FREE, and start here — it has been the best value in each of the last two phases.
     - Re-run the ten free probes (below). Expect 142/142. If probe_turn_growth.py's corpus counts
       have moved, that is EXPECTED and not a finding by itself: the suite writes to the corpus it
       measures (docs/CLONE.md §4). What would be a finding is a moved MAXIMUM, BOUND or
       CONDITIONAL — those held across +14% of corpus and are the load-bearing figures.
     - The fresh-clone work is DONE and the suite is fixed, but only `Results(expect=N)` and the
       exception guard were controlled end to end. If you touch a probe, the floor must be bumped
       with it — it is a MINIMUM, so adding assertions is safe and removing them is not.
     - Nothing else free is outstanding. If you find something, that IS the phase.

  2. PAID and OPTIONAL — the 180,000 gate has still never been FIRED at its real value. Half is
     closed free (probe_headless_arm.py asserts the shipped default arms; probe_turn_predicate.py
     the predicate) and the remaining half is a single `>=` already exercised at 20,000. Costed at
     ~$2.60, range $1.75-5, ~6-11 min in .carryover/verified/README.md. OFFERED IN PHASE 8 AND
     DECLINED, on the grounds that a `>=` against a variable is threshold-independent by
     inspection — so do not put it at the top of the list, but it is still the cheapest paid thing
     available. NOT via verify_headless_retire.py: THRESHOLD = 20_000 (`:52`) is a bare literal it
     forces into the server via env_extra, which rig.serve() applies LAST, and its workload is one
     prompt capped at 50 KB by read.ts:16. Use verify_retire_350k.py's growth loop retargeted.
     ASK ME FIRST.

  3. ALSO PAID and OPTIONAL — an EXTERNAL plugin's route has never been RENDERED. Phase 8 settled
     *can it* at VERIFIED (same PluginEntry, same activation loop, same pluginApi; the only
     `source` discrimination in the path is a metadata display field) but not *does it, under a
     real workload*. Everything TESTED in this repo was measured on the builtin path.

  DO NOT remind me about `/code-review ultra`. It has been run. HARNESS.md and three phase docs
  still carry it as an open row; leave them, that is deliberate and it is my business, not a
  documentation defect for you to tidy.

METHOD — this project's standard, and it is not decoration:
  - Classify every claim VERIFIED (read code, cite file:line) / TESTED (ran it) / INFERRED /
    SUSPECTED. Never present a lower tier as a higher one. Cite file:line and open the file.
  - This suite's characteristic failure is PASSING, and every phase since 5 has caught more
    instances of it. GREEN IS NOT EVIDENCE UNTIL YOU KNOW WHAT WOULD HAVE MADE IT RED. Every new
    assertion needs a negative control or a mutation check. An assertion about ORDERING needs a
    workload that could have violated it.
  - A FAILING ASSERTION NEEDS THE SAME SCRUTINY AS A PASSING ONE (Phase 8's addition). Before
    writing down a red, ask whether it is an artifact of your own grouping or fixture.
  - A GREEN RUN IS NOT EVIDENCE THAT THE RUN HAPPENED (Phase 9's addition, and it cost three
    probes). The vacuous pass and the missing assertion are the same defect: an assertion that
    never ran is True on exactly the runs that did not evaluate it. Check the COUNT, not just the
    colour. And when a predicate's inputs come from a corpus, THE CORPUS NEEDS A FIXTURE CHECK as
    much as the predicate needs a mutation check — losing the evidence and passing the test can be
    the same event.
  - A NUMBER IS NOT EVIDENCE, AND REPEATING IT DOES NOT MAKE IT MORE EVIDENCE (Phase 8's).
  - Run the FREE probes before spending anything (142/142 total):
      cd .carryover/verified
      venv/bin/python probe_on_grid.py          # 4/4
      venv/bin/python probe_error_state.py      # 10/10
      venv/bin/python probe_focus.py            # 24/24
      venv/bin/python probe_fleet.py            # 10/10
      venv/bin/python probe_control_wiring.py   # 14/14
      venv/bin/python probe_twin.py             # 23/23
      venv/bin/python probe_headless_arm.py     # 14/14
      venv/bin/python probe_request_channel.py  # 9/9
      venv/bin/python probe_turn_predicate.py   # 18/18
      venv/bin/python probe_turn_growth.py      # 16/16
  - Gates before you claim done, from ~/Desktop/healbot/opencode:
      ./node_modules/.bin/tsgo --noEmit -p packages/tui/tsconfig.json    # expect exit 0, no output
      ./node_modules/.bin/oxlint packages/tui/src/feature-plugins/system/healbot.tsx
                                                                        # expect exit 0, 3 warnings
  - Every phase revises the artifacts it contradicts. Write docs/<PHASE>.md, update HARNESS.md,
    fix any figure you disprove.

TRAPS — all measured, all in HARNESS.md, repeated because each silently produces a wrong belief
rather than an error:
  - THE SUITE IS NOT PORTABLE. A fresh clone lacks the gitignored `opencode/` checkout (rebuild
    from fork/README.md) and the gitignored `hb/*.db` (only the PAID rigs can create it).
    probe_turn_predicate.py is the ONLY one of the ten that survives a fresh clone. Before Phase 9
    three of them reported success there anyway; `Results(expect=N)` is what stops that now.
  - The installed `opencode` binary has NO grid. Run from source: rig.py's OC constant, or
    harness/fleet.sh.
  - RETIRE_AT IS ONLY VALID FOR THE PINNED MODEL. `worst_turn` is a fact about a MODEL's
    tool-calling behaviour, not about opencode. The pinned gpt-5.6-sol's worst turn is 175,148;
    the same corpus has 223,258 on gpt-5.6-terra. Changing opencode.jsonc:16 silently un-verifies
    the threshold — probe_turn_growth.py asserts the pin so it goes red instead.
  - `healbot_*: deny` SCOPES CONTEXT, NOT CAPABILITY. TESTED: the build agent, with all five tool
    definitions removed from its payload, ran `opencode run --auto ...` through bash and created a
    real top-level session. Do not build anything on the assumption that a denied agent cannot
    reach a capability.
  - AN EXTERNAL TUI PLUGIN CAN SILENTLY REPLACE THE GRID. Internal plugins are added before
    external ones and the route map is last-wins (`plugin/api.ts:33-35`). A third-party plugin
    registering `healbot` wins, with no error and no log line. The name is neither pinned nor
    reserved.
  - EVERY field that looks like "the turn is over" on an assistant message is set per STEP:
    `finish`, `time.completed` (processor.ts:443, :445, :595-596; a new message per step at
    prompt.ts:1186-1201). turnFinished() is the only correct reader; prompt.ts:1295 is why.
  - THE GATE AND THE THRESHOLD ARE COUPLED. Per-turn with no second gate means RETIRE_AT must stay
    below 184,852 on the pinned model. Raising it without restoring a hard gate silently
    reintroduces the cliff.
  - RETIREMENT HAPPENS IN EXACTLY ONE PROCESS. The grid's `x` only writes
    metadata.healbot.retireRequested. Without the harness config loaded, `x` looks like it worked
    and nothing retires — and the coupling is untyped in both directions.
  - Automatic retirement is a SERVER plugin. Thresholds are read by the SERVER process, so
    exporting HEALBOT_RETIRE_AT into a rig's own environment configures nothing. Use
    rig.serve(..., env_extra={...}) and read rig.serve(..., log=path).
  - A server plugin gets the v1 SDK client, the TUI gets v2, and they diverge silently. The
    generated types are NARROWER than the routes (metadata, time.archived).
  - A plugin module may export ONLY functions. One exported constant throws at load time and
    leaves a healthy server with a missing feature.
  - The rig's Api MUST send `x-opencode-directory`, or you address a different instance and the
    grid shows `0 sessions` while every call succeeds.
  - The rig's project dir needs its own git repo (rig.git_baseline()) or every changed file is
    invisible to the diff machinery.
  - Never set XDG_DATA_HOME. auth.json lives there and OpenAI is on oauth. Isolate the DB only.
  - Term.find() is case-INSENSITIVE and the project path contains "healbot". Use rig.on_grid()
    and t.exact().
  - The session-route sidebar is gated on width > 120 and is the only thing rendering a session
    id. The navigation rigs use exactly 120, so a focus assertion there measures geometry.
  - Session ids are DESCENDING identifiers, so ascending sort is newest-first.
  - The context ceiling is ~360K, NOT the 922,000 limit.input the model registry advertises.

Ask me before spending real API credits on anything beyond a few turns.
```

---

## Why this order

**§0 stays, and Phase 9 added weight to one of its two entries rather than reopening it.** The
`RETIRE_AT` decision has now survived a 14% larger corpus with every maximum unchanged — that is a
reason to leave it alone with more confidence, and the prompt says so explicitly, because the
failure mode this section exists to prevent is a fresh session treating a settled policy as a bug.

**1 is free and still first, on the same evidence as last time.** Phases 8 and 9 both produced their
entire value from free work: Phase 8 re-derived `worst_turn` by reading a database that had been on
disk the whole time; Phase 9 found three probes reporting success over nothing by doing the one thing
nobody had done — `git clone` and run. Neither cost a cent. The difference this time is that **the
free list is now empty**: the fresh-clone item was the last one written down. That is stated in the
prompt as *"if you find something, that IS the phase"* rather than left as an invitation to invent
work.

**2 and 3 are last because they are confirmations, not discoveries.** The `>=` at 180,000 has been
exercised at 20,000; the external route has been VERIFIED at source. Both buy a tier upgrade on a
claim already believed, and 2 was offered to the owner in Phase 8 and declined on exactly that
reasoning.

**The `/code-review ultra` reminder stays out of the prompt, and the open rows it refers to stay in
the docs.** The review has been run. The Still-open rows in `HARNESS.md`, `docs/RELAY.md` §5,
`docs/GROWTH.md` §6 and now `docs/CLONE.md` §6 still describe the Phase 3 exit gate as unmet — that
is stale, knowingly, and the owner's call to leave. Whoever next reconciles the gate should do it
from the review's own findings, not from this file.

Deliberately **not** in the prompt:

- **Worktree isolation** (build-order step 7). `PLAN.md` marks it optional and nothing needs it.
- **The startup sweep and the threshold**, except as §0's do-not-reopen list.
- **The remaining grid traps** — RED silent under `--auto`, archived sessions never leaving the
  list. Review-tier rows in `HARNESS.md`; the index carries them.
- **Making the suite portable.** A fresh clone cannot rebuild `hb/*.db` without paying for the rigs
  that wrote it, so "make the probes run anywhere" is a spending decision dressed as a chore. It is
  recorded as a fact about the evidence in `docs/CLONE.md` §6, not as a task.

## Current state, for the maintainer of this file

Phase 9 changed **no fork code** — the overlay stays pinned at `509f4c0b1` and
`fork/healbot-fork.patch` is untouched. Nothing was paid for. What changed is `rig.py`, all ten
probes, one new phase doc, and the corrected figures in three files.

What it found, in the order it found it:

- **The corpus moved 86 → 94 turns**, and the cause is `hb/control.db` — written by
  `verify_control_agent.py` six minutes *after* Phase 8 recorded its figures. Hiding that one file
  reproduces Phase 8's percentiles exactly. **The suite writes to the corpus it measures.** Every
  maximum, bound and conditional held, which Phase 8 could not have known.
- **`probe_turn_growth.py`'s "optional" real corpus is REQUIRED** — running without it is exit 1,
  12/14. The `[NOT EXERCISED]` string is the detail on a *failing* row. Both the probe's own
  docstring and the Phase 9 prompt had inherited the claim.
- **Three probes reported success on a fresh clone having proven nothing** — `2/2`, `7/7`, and
  `1/1` after a 90-second timeout, all exit 0. Two routes: `sys.exit()` in a `finally` discards the
  exception (known since Phase 5, named in `probe_request_channel.py:151`, present in 3 of 10
  probes), and `wait_for()` times out without raising. Fixed with `Results(expect=N)`.
- **`probe_turn_growth.py`'s two load-bearing assertions get easier as their evidence
  disappears** — 48.2% margin and a 353,357 bound on a fresh clone, in green, against a true 1.3%
  and 184,852. Fixed with a fixture check on the pinned-model population.

Free suite: 4/4, 10/10, 24/24, 10/10, 14/14, 23/23, 14/14, 9/9, 18/18, **16/16** — **142 total**,
all re-run after the edits, every probe exit 0. Negative control: the same fresh clone now fails
**9 of 10** with `SHORT RUN` where a probe stops early. Gates: `tsgo` exit 0 with no output,
`oxlint` exit 0 with the expected 3 warnings.
