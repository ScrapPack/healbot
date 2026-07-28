# NEXT — the prompt for a fresh session

Paste the block below into a new agent session at `~/Desktop/healbot`. Everything else in this
file is context for whoever maintains the prompt; the agent only needs the block.

The prompt is short on purpose. This project's method is that a phase reads the written
artifacts, never the prior transcript — and the project exists to cut standing context, so a
handoff that pastes ten thousand words of history is working against its own premise.

---

## The prompt

```
Continue the healbot build at ~/Desktop/healbot. Phase 11 is complete and committed; the fork
overlay is pinned at 509f4c0b1 (unchanged — Phase 11 changed no fork CODE and spent nothing; it did
correct stale citations inside two of the overlay's .MAP.md files, resynced to the checkout).

READ FIRST, in this order. Stop when you can name the file that owns any given behaviour:
  1. HARNESS.md          — root index: load-bearing facts, Traps, Closed, Still open
  2. docs/CITE.md        — Phase 11: the maps had rotted and nothing checked them. 930 citations
                           swept, eight stale — and THREE were created by Phases 9 and 10 editing
                           documents that other documents cite into. Also: probe_twin guarded 1 of
                           17 overlay files; the fork is verified to REPRODUCE from its patch
  3. docs/VERDICT.md     — Phase 10: six PAID rigs printed summary()'s verdict and threw it away,
                           so a failing run exited 0 — including smoke.py, and verify_surface.py
                           which held a permanently-red assertion for five phases. Also
                           verify_handoff.py's recorded 21/21 is UNREACHABLE (22 assertions since
                           Phase 5) and is cited in four docs as the Phase 4 exit gate
  4. docs/CLONE.md       — Phase 9: the suite could not tell "everything passed" from "almost
                           nothing ran". From a FRESH CLONE three probes exited 0 having proven
                           nothing, and probe_turn_growth.py's two load-bearing assertions get
                           EASIER as their evidence disappears — 48.2% margin instead of 1.3%
  5. docs/GROWTH.md      — Phase 8: `worst_turn` was ONE measurement and it was not the worst.
                           The pinned model's worst is 175,148, the bound on RETIRE_AT is 184,852,
                           and the shipped 180,000 clears it by 1.3%. The threshold is
                           MODEL-SPECIFIC. Also: `healbot_*: deny` is a context control, NOT a
                           sandbox. (CLONE.md §4 annotates its corpus counts; its findings stand)
  6. .carryover/verified/README.md — the test rig and its assertion discipline

Do NOT read the whole tree first. HARNESS.md indexes everything; follow it on demand.

YOUR TASK — Phase 12. Everything in the build order is built and every known correctness hole is
closed. There is NO decision pending on me and nothing is blocking you. Do not invent something to
build.

  THE ONE NEW ITEM, and it is cheap: verify_handoff.py must be RE-RUN before its 21/21 can be
  quoted again. Phase 5 took it from 21 to 22 unconditional assertions and never executed it, so
  the recorded score is unreachable, and HARNESS.md / docs/VERIFY.md §10 / the rig README all cite
  it as the Phase 4 exit gate's second clause. Its floor is now 22. This is one paid rig, not a
  campaign. ASK ME FIRST — and note that every Phase 10 fix to a paid rig is VERIFIED, not TESTED,
  so whichever paid rig runs next is also the first execution of its floor.

  0. TWO THINGS ARE DECIDED. Do not re-open either as a defect, and do not "fix" them.
     - RETIRE_AT STAYS AT 180,000. Phase 8 re-derived the worst_turn that sizes it (175,148 on the
       pinned model, bound 184,852, margin 1.3% of the ~360K ceiling) and offered four options; the
       answer was leave it and correct the prose. What that ACCEPTS is in docs/GROWTH.md §1 and is
       inherited knowingly. Phase 9 STRENGTHENED it: the corpus grew 14% (86 -> 94 turns) and every
       maximum, bound and conditional was unchanged (docs/CLONE.md §4). It is the first evidence the
       derivation is stable under corpus growth, not a reason to revisit it.
     - NO STARTUP SWEEP. Retirement stays purely event-driven. A session parked over the gate when
       a server restarts stays there until its next turn ends. Decided in Phase 8 §5.
     The one LIVE constraint out of all that: RETIRE_AT is verified only while
     harness/config/opencode/opencode.jsonc:16 pins gpt-5.6-sol (there are TWO files named
     opencode.jsonc; the checkout's has a blank line 16). probe_turn_growth.py asserts the pin.

  1. FREE, and start here — it has been the best value in each of the last two phases.
     - Re-run the TWELVE free probes (below). Expect 180/180. If probe_turn_growth.py's corpus counts
       have moved, that is EXPECTED and not a finding by itself: the suite writes to the corpus it
       measures (docs/CLONE.md §4). What would be a finding is a moved MAXIMUM, BOUND or
       CONDITIONAL — those held across +14% of corpus and are the load-bearing figures.
     - probe_rig_contract.py is new and is the guard for all of this: it reads all 23 rigs (itself included — a guard that exempts itself is the defect it hunts) as
       SOURCE and asserts each declares a satisfiable assertion floor, has no `finally` that exits
       without a crash guard, and exits on summary()'s verdict. If you add a rig, it must satisfy
       that contract or the probe goes red. Floors are MINIMUMS — adding assertions is safe,
       removing them is not.
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
  - THE DOCUMENTS ARE ARTIFACTS TOO (Phase 11's addition). A `file:line` citation is an untyped
    coupling between two files: edit either end and it rots silently. probe_citations.py checks
    POSITIONAL rot only — semantic rot is not mechanically checkable and is not claimed. Two
    editorial rules came with it: a citation quoted as BROKEN must not be written in live
    `file:line` form, and line numbers are for CODE while section NAMES are for living documents
    like HARNESS.md, which gains rows every phase and will rot any line citation into it.
  - A RECORDED SCORE IS A CLAIM ABOUT A FILE AT A MOMENT (Phase 10's addition). Re-run a rig
    before quoting its number, or say which execution the number came from. Phase 8 found one rig
    whose score did not match its file and called it "the one rig in the suite"; that uniqueness
    was never checked and was false. `grep -c 'r\.check('` against the recorded scores is the
    whole test.
  - A GREEN RUN IS NOT EVIDENCE THAT THE RUN HAPPENED (Phase 9's addition, and it cost three
    probes). The vacuous pass and the missing assertion are the same defect: an assertion that
    never ran is True on exactly the runs that did not evaluate it. Check the COUNT, not just the
    colour. And when a predicate's inputs come from a corpus, THE CORPUS NEEDS A FIXTURE CHECK as
    much as the predicate needs a mutation check — losing the evidence and passing the test can be
    the same event.
  - A NUMBER IS NOT EVIDENCE, AND REPEATING IT DOES NOT MAKE IT MORE EVIDENCE (Phase 8's).
  - Run the FREE probes before spending anything (180/180 total):
      cd .carryover/verified
      venv/bin/python probe_on_grid.py          # 4/4
      venv/bin/python probe_error_state.py      # 10/10
      venv/bin/python probe_focus.py            # 24/24
      venv/bin/python probe_fleet.py            # 10/10
      venv/bin/python probe_control_wiring.py   # 14/14
      venv/bin/python probe_twin.py             # 25/25
      venv/bin/python probe_headless_arm.py     # 14/14
      venv/bin/python probe_request_channel.py  # 9/9
      venv/bin/python probe_turn_predicate.py   # 18/18
      venv/bin/python probe_turn_growth.py      # 16/16
      venv/bin/python probe_rig_contract.py     # 22/22
      venv/bin/python probe_citations.py        # 14/14
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
    the same corpus has 223,258 on gpt-5.6-terra. Changing the pin at
    harness/config/opencode/opencode.jsonc:16 silently un-verifies the threshold —
    probe_turn_growth.py asserts the pin so it goes red instead.
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

**Phase 11 emptied the free list and then found two more things in it**, which is now the third
phase running where that happened. The pattern is stable enough to state: the free findings come
from looking at a surface nobody has looked at *as an artifact* — the derivation under a number
(8), the suite from a fresh clone (9), the paid rigs as source (10), the prose as pointers (11).

**§0 stays.** Both decisions have survived three phases of adversarial work.

**The one paid item is unchanged and still unbought.** `verify_handoff.py`'s 21/21 is still a Phase 4
score against a file Phase 5 edited. Its floor is 22.

Deliberately **not** in the prompt:

- **Worktree isolation** (build-order step 7). `PLAN.md` marks it optional and nothing needs it.
- **The startup sweep and the threshold**, except as §0's do-not-reopen list.
- **Semantic citation checking.** `probe_citations.py` proves a citation points somewhere real,
  never that it points at the right thing. That is a reading task, not a probe, and pretending
  otherwise would produce exactly the kind of guard this project keeps finding.
- **Making the suite portable** — a fresh clone cannot rebuild `hb/*.db` without paying.

## Current state, for the maintainer of this file

Phase 11 changed **no fork code**. It corrected stale citations inside two `.MAP.md` files in the
overlay and resynced both to the checkout; `healbot.tsx`, `builtins.ts` and the patch are untouched,
so the overlay stays pinned at `509f4c0b1`. Nothing was paid for.

What it found:

- **Citation rot had no guard**, though `fork/README.md` named it as "drift mode 2". A sweep of 930
  citations across 25 documents found **eight stale**: three pointing ~140 lines past the end of
  `healbot.tsx` (pre-existing), five landing on blank lines.
- **Three of the five were created by Phases 9 and 10** — editing `HARNESS.md` moved two section
  headings other documents cite, and editing `probe_twin.py` moved a line `docs/HEADLESS.md` cites.
  The phases about silent failure introduced silent doc rot while nothing was looking.
- **The model-pin citation was ambiguous and resolved to a blank line.** Two files are named
  `opencode.jsonc` and the checkout's has a blank line 16; it is the citation
  `probe_turn_growth.py`'s `RETIRE_AT` argument depends on. All occurrences now carry the full path.
- **`probe_twin` was guarding 1 of the 17 overlay files.** Now all 17, with a mutation check — and
  the risk fired during the phase itself.
- **The fork reproduces**, verified harder than recorded: base tree 6,330, patch applies, and
  applying it yields all 17 overlay files byte-identically.

New guard: **`probe_citations.py`**, free, 14/14. Its own first draft manufactured **155 false
findings** by resolving `prompt.ts:1295` to the 57-line schema file instead of the 1,631-line session
one — seven files share that basename — and the resolver bug is pinned as an assertion so it cannot
return.

Free suite: 4/4, 10/10, 24/24, 10/10, 14/14, **25/25**, 14/14, 9/9, 18/18, 16/16, 22/22, **14/14** —
**180 total**, every probe exit 0. Gates: `tsgo` exit 0 with no output, `oxlint` exit 0 with the
expected 3 warnings.
