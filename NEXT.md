# NEXT — the prompt for a fresh session

Paste the block below into a new agent session at `~/Desktop/healbot`. Everything else in this
file is context for whoever maintains the prompt; the agent only needs the block.

The prompt is short on purpose. This project's method is that a phase reads the written
artifacts, never the prior transcript — and the project exists to cut standing context, so a
handoff that pastes ten thousand words of history is working against its own premise.

---

## The prompt

```
Continue the healbot build at ~/Desktop/healbot. Phase 12 is complete and committed; the fork
overlay is pinned at 509f4c0b1 (unchanged — Phase 12 changed no fork CODE. It changed the test rig:
rig.py, probe_rig_contract.py, verify_question.py, verify_permission.py).

READ FIRST, in this order. Stop when you can name the file that owns any given behaviour:
  1. HARNESS.md          — root index: load-bearing facts, Traps, Closed, Still open
  2. docs/OUTCOME.md     — Phase 12, and it has FIVE findings, not one. §1-4: the box that could not
                           fail — rig.py's fire() appends a turn that THREW and one that FINISHED in
                           the same 3-tuple and NO rig ever read the element that tells them apart
                           (three fire() calls at a dead port satisfied every completion predicate in
                           the suite in 9ms). §7: three paid rigs are SINGLE-USE. §8: wait_for's
                           timeout does not bound. §9: verify_question.py has been three assertions
                           RED since Phase 5 and Phase 10's count-the-sites check cannot see it.
                           §10: worst_turn is a fact about the WORKLOAD too — READ THIS ONE FIRST,
                           it is why the suite is red and it is the open decision
  3. docs/CITE.md        — Phase 11: the maps had rotted and nothing checked them. 930 citations
                           swept, eight stale — and THREE were created by Phases 9 and 10 editing
                           documents that other documents cite into. Also: probe_twin guarded 1 of
                           17 overlay files; the fork is verified to REPRODUCE from its patch
  4. docs/VERDICT.md     — Phase 10: six PAID rigs printed summary()'s verdict and threw it away,
                           so a failing run exited 0 — including smoke.py, and verify_surface.py
                           which held a permanently-red assertion for five phases. Also
                           verify_handoff.py's recorded 21/21 is UNREACHABLE (22 assertions since
                           Phase 5) and is cited in four docs as the Phase 4 exit gate
  5. docs/CLONE.md       — Phase 9: the suite could not tell "everything passed" from "almost
                           nothing ran". From a FRESH CLONE three probes exited 0 having proven
                           nothing, and probe_turn_growth.py's two load-bearing assertions get
                           EASIER as their evidence disappears — 48.2% margin instead of 1.3%
  6. docs/GROWTH.md      — Phase 8: `worst_turn` was ONE measurement and it was not the worst.
                           The pinned model's worst is 175,148, the bound on RETIRE_AT is 184,852,
                           and the shipped 180,000 clears it by 1.3%. The threshold is
                           MODEL-SPECIFIC. Also: `healbot_*: deny` is a context control, NOT a
                           sandbox. (CLONE.md §4 annotates its corpus counts; its findings stand)
  7. .carryover/verified/README.md — the test rig and its assertion discipline

Do NOT read the whole tree first. HARNESS.md indexes everything; follow it on demand.

YOUR TASK — Phase 13. Everything in the build order is built. Do not invent something to build.

  READ THIS FIRST: unlike every prior handoff, THE SUITE IS NOT GREEN and there IS one decision
  pending on me. probe_turn_growth.py is RED at 13/16 because Phase 12 measured a single turn at
  299,326 on the pinned model — 71% above the number RETIRE_AT is derived from — and the cause is an
  undeclared fixture, not a code defect. §0 has it. Nothing else is blocking you, and the red is not
  yours to clear: making it green requires either my decision on the threshold or deleting the
  evidence, and the second is not an option.

  0. THREE THINGS ARE DECIDED. Do not re-open any as a defect, and do not "fix" them.
     - RETIRE_AT STAYS AT 180,000 — the DECISION stands, but its EVIDENCE has been contradicted and
       that is now an open question WITH THE OWNER, not with you. Phase 8 re-derived worst_turn
       (175,148 pinned, bound 184,852, margin 1.3%) and the answer was leave it and correct the
       prose; docs/GROWTH.md §1 has what that accepts. Phase 9 strengthened it — corpus +14%, every
       maximum unchanged. **PHASE 12 BROKE IT.** A single turn measured 299,326 on the pinned model,
       71% above 175,148, so 180,000 + 299,326 = 479,326 against a ~360K ceiling: margin -119,326,
       and probe_turn_growth.py is RED. The cause is that the rig's project directory is an
       UNDECLARED variable in the derivation — 84 entries, 94 MB, node_modules, grown across every
       paid run ever — and excluding Phase 12's two runs the maximum is still exactly 175,148.
       DO NOT change RETIRE_AT and DO NOT clear the fixture to make the probe green. Both are the
       owner's call and the second one is evidence destruction. docs/OUTCOME.md §10 states the two
       readings and costs them.
     - NO STARTUP SWEEP. Retirement stays purely event-driven. A session parked over the gate when
       a server restarts stays there until its next turn ends. Decided in Phase 8 §5.
     - THE FIVE `wait_for` GATES THAT READ THE RAW BOX STAY AS THEY ARE. Phase 12 fixed the four
       ASSERTION rows and deliberately left the SEQUENCING gates (docs/OUTCOME.md §2, "What is NOT
       claimed"): a thrown turn releases those early and what follows goes RED downstream, which is
       already the correct outcome. Do not "finish the job" by converting them; you would be
       trading a fast red for a seven-minute timeout.
     The one LIVE constraint out of all that: RETIRE_AT is verified only while
     harness/config/opencode/opencode.jsonc:16 pins gpt-5.6-sol (there are TWO files named
     opencode.jsonc; the checkout's has a blank line 16). probe_turn_growth.py asserts the pin.

  1. FREE, and start here — it has been the best value in each of the last FIVE phases.
     - Re-run the TWELVE free probes (below). Expect 184/187 — ELEVEN GREEN AND ONE RED, and the red
       is REAL. probe_turn_growth.py is 13/16, exit 1. DO NOT "fix" it by clearing hb/project or
       dropping a rig DB: that buys a green by deleting the measurement, which is the exact failure
       docs/CLONE.md §1 exists to name. Read §0 and docs/OUTCOME.md §10 before touching anything.
     - The MAXIMUM moved, which docs/CLONE.md §4 says is the thing that counts as a finding (a moved
       corpus COUNT is expected — the suite writes to the corpus it measures — but a moved maximum,
       bound or conditional is not). A single turn on the pinned model measured 299,326, 71% above
       the 175,148 the threshold is derived from, so the margin is now -119,326.
     - probe_rig_contract.py is the guard for all of this: it reads all 24 rigs (itself included — a
       guard that exempts itself is the defect it hunts) as SOURCE and asserts SIX contracts — a
       satisfiable assertion floor, no `finally` that exits without a crash guard, an exit on
       summary()'s verdict, that verdict exit LAST in the finally, and (Phase 12) that no assertion
       decides a turn COMPLETED by counting fire()'s box. If you add a rig, it must satisfy that
       contract or the probe goes red. Floors are MINIMUMS — adding assertions is safe, removing
       them is not.
     - Nothing else free is outstanding. If you find something, that IS the phase. Five phases
       running, the free finding has come from reading some surface AS AN ARTIFACT that nobody had:
       the derivation under a number (8), the suite from a fresh clone (9), the paid rigs as source
       (10), the prose as pointers (11), the shared library the whole suite stands on (12).

  2. FREE TO WRITE, and Phase 12 handed these over deliberately rather than doing them, because
     making a repair after paying for a run edits the file the new score describes — the exact
     Phase 10 defect. THREE repairs, and the first is the important one:
     - verify_question.py IS THREE ASSERTIONS RED, and has been since Phase 5. TESTED at 27/30 on a
       clean DB — its first execution since Phase 4. Phase 5 BUILT auto-surface (the cursor lands ON
       the blocked cell) and added a comment to that file saying so, then left three assertions
       assuming the opposite: "'a' on an unblocked cell opens no panel", "tab moved the cursor onto
       the blocked cell", and `t.find("4 sessions")`. THE PRODUCT IS FINE — auto-surface is the
       intended feature and verify_surface.py tests it. Rewrite the three to assert the surfacing
       behaviour the file's own comment describes, and derive the session count instead of
       hardcoding it (extra ask attempts AND model-spawned subagents both add cells — the run that
       found this rendered SIX). Then re-run to score it. Note what this says about method:
       27 static `r.check(` sites against a recorded 27/27 reconciles PERFECTLY under Phase 10's
       check, and the rig was three assertions red the whole time. COUNTING PROVES A SCORE IS
       REACHABLE, NOT ACHIEVABLE.
     - THREE PAID RIGS ARE SINGLE-USE. `rig.db()` never resets, the grid header counts every session
       in the DB, and four sites compare it to a LITERAL: verify_permission.py:116 and :143,
       verify_question.py:135 (`t.find("4 sessions")`), verify_cold.py:102 (`t.find("1 session")`).
       Re-run any of them and the row goes red for a reason that is not a defect. Derive the count
       from what the rig created. TESTED — this is how Phase 12 found it. When clearing a rig DB,
       ARCHIVE it under a name that still matches `hb/*.db` (quest.db -> quest-phase12a.db); that
       glob is probe_turn_growth.py's corpus and deleting it removes the evidence sizing RETIRE_AT.
     - `wait_for`'s TIMEOUT DOES NOT BOUND. It checks its deadline only between calls to `fn`
       (rig.py:296) and Api.__call__ defaults to timeout=900 (rig.py:225), so a 300s budget can be
       held for 900. VERIFIED by reading, never fired. Likely repair: Api takes its timeout from the
       budget wrapping it, or defaults well below the smallest budget in use.
     Both are free to WRITE and paid to TEST, so pair them with whichever paid rig runs next.

  3. PAID and OPTIONAL, and it is the cheapest thing left: verify_handoff.py must be RE-RUN before
     its 21/21 can be quoted again. Phase 5 took it from 21 to 22 unconditional assertions and never
     executed it, so the recorded score is unreachable, and HARNESS.md / docs/VERIFY.md §10 / the rig
     README all cite it as the Phase 4 exit gate's second clause. Its floor is now 22. Offered in
     Phase 12 and not taken. Its workload is three ~130 KB ledgers read in full plus file creation,
     so it is not free but it is not the 350K rig either. ASK ME FIRST.

  4. ALSO PAID and OPTIONAL — the 180,000 gate has still never been FIRED at its real value. Half is
     closed free (probe_headless_arm.py asserts the shipped default arms; probe_turn_predicate.py
     the predicate) and the remaining half is a single `>=` already exercised at 20,000. Costed at
     ~$2.60, range $1.75-5, ~6-11 min in .carryover/verified/README.md. OFFERED IN PHASE 8 AND
     DECLINED, on the grounds that a `>=` against a variable is threshold-independent by
     inspection — so do not put it at the top of the list, but it is still cheap. NOT via
     verify_headless_retire.py: THRESHOLD = 20_000 (`:52`) is a bare literal it forces into the
     server via env_extra, which rig.serve() applies LAST, and its workload is one prompt capped at
     50 KB by read.ts:16. Use verify_retire_350k.py's growth loop retargeted. ASK ME FIRST.

  5. ALSO PAID and OPTIONAL — an EXTERNAL plugin's route has never been RENDERED. Phase 8 settled
     *can it* at VERIFIED (same PluginEntry, same activation loop, same pluginApi; the only
     `source` discrimination in the path is a metadata display field) but not *does it, under a
     real workload*. Everything TESTED in this repo was measured on the builtin path.

  A NOTE ON WHAT IS TESTED vs VERIFIED IN THE PAID HALF, and Phase 12 sharpened it into a warning.
  Phase 12 ran verify_question.py twice, so its fixes are TESTED — and that single run also found
  THREE separate defects nobody could see from source (three stale assertions, the hardcoded session
  count, and the subagent-inflated grid). The two rows changed in verify_permission.py are VERIFIED,
  not TESTED, as is every Phase 10 fix to a paid rig. Do not read that as an accounting detail:
  verify_question.py sat three assertions red for SEVEN PHASES while every static check passed on it.
  The paid rigs are the least-observed surface in this project, and each one that gets run has so far
  produced findings. Whichever runs next is also the first execution of its floor.

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
  - A COUNT IS NOT AN OUTCOME (Phase 12's addition, and it cost four assertion rows). Ask of every
    predicate: what value reaching it would turn this red? If the honest answer is "nothing the
    workload can produce", the row is decoration no matter how load-bearing its NAME is. The four
    rows Phase 12 fixed were all named for the thing they could not see. And the corollary that
    made it findable: WHEN A PREDICATE READS A SHARED HELPER, READ THE HELPER — `fire()` documented
    its own hazard as `result_or_exception` and twenty-four rigs walked into it.
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
    was never checked and was false. **AND `grep -c 'r\.check('` IS NOT "the whole test", which is
    what Phase 10 called it — Phase 12 disproved that.** Counting sites proves a score is
    ARITHMETICALLY REACHABLE, never that it is ACHIEVABLE. verify_question.py reconciled perfectly
    at 27 sites / 27 recorded and had been three assertions red for seven phases, because Phase 5
    changed the BEHAVIOUR UNDER TEST and not the count. No static method sees that. Only running it
    does — which is exactly what the paid half resists, and why these survive so long.
  - A GREEN RUN IS NOT EVIDENCE THAT THE RUN HAPPENED (Phase 9's addition, and it cost three
    probes). The vacuous pass and the missing assertion are the same defect: an assertion that
    never ran is True on exactly the runs that did not evaluate it. Check the COUNT, not just the
    colour. And when a predicate's inputs come from a corpus, THE CORPUS NEEDS A FIXTURE CHECK as
    much as the predicate needs a mutation check — losing the evidence and passing the test can be
    the same event.
  - A NUMBER IS NOT EVIDENCE, AND REPEATING IT DOES NOT MAKE IT MORE EVIDENCE (Phase 8's).
  - CAPTURE THE REAL EXIT CODE. `python probe.py | tail -4; echo $?` reports TAIL's status, not
    the probe's. Use `$pipestatus`/`PIPESTATUS`, or assign the output first.
  - Run the FREE probes before spending anything (184/187 — one REAL red, see §0 and §1):
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
      venv/bin/python probe_turn_growth.py      # 13/16 RED, exit 1 — REAL. docs/OUTCOME.md §10
      venv/bin/python probe_rig_contract.py     # 29/29
      venv/bin/python probe_citations.py        # 14/14
  - Gates before you claim done, from ~/Desktop/healbot/opencode:
      ./node_modules/.bin/tsgo --noEmit -p packages/tui/tsconfig.json    # expect exit 0, no output
      ./node_modules/.bin/oxlint packages/tui/src/feature-plugins/system/healbot.tsx
                                                                        # expect exit 0, 3 warnings
  - Every phase revises the artifacts it contradicts. Write docs/<PHASE>.md, update HARNESS.md,
    fix any figure you disprove.

TRAPS — all measured, all in HARNESS.md, repeated because each silently produces a wrong belief
rather than an error:
  - `fire()` RECORDS A THROWN TURN AND A FINISHED TURN IDENTICALLY. `len(box)` counts turns that
    ENDED, never turns that RAN. Gate on ENDED (so a failure surfaces fast), assert on RAN via
    `rig.completed()`. Contract 6 in probe_rig_contract.py enforces it from source.
  - THE SUITE IS NOT PORTABLE. A fresh clone lacks the gitignored `opencode/` checkout (rebuild
    from fork/README.md) and the gitignored `hb/*.db` (only the PAID rigs can create it).
    probe_turn_predicate.py is the ONLY one of the twelve that survives a fresh clone. Before Phase
    9 three of them reported success there anyway; `Results(expect=N)` is what stops that now.
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
  - verify_question.py depends on the model CHOOSING to ask a question unforced. It carries three
    framings and polls 300s each, so a run where the first two framings do not land takes ~10
    minutes before it reaches the grid. That is the rig working, not hanging.

Ask me before spending real API credits on anything beyond a few turns.
```

---

## Why this order

**Phase 12 emptied the free list and then found something in it**, which is now the fifth phase
running where that happened. The pattern is stable enough to state as a method rule, and it now is
one: the free findings come from looking at a surface nobody has looked at *as an artifact* — the
derivation under a number (8), the suite from a fresh clone (9), the paid rigs as source (10), the
prose as pointers (11), and the shared library every rig imports (12).

Phase 12's surface was the one `probe_rig_contract.py` **deliberately excludes**. Its comment is
correct as far as it goes — `rig.py` and `term.py` own no assertions of their own, and sweeping them
would make every contract predicate fail for a reason that is not a defect. What that reasoning
missed is that `rig.py` *defines what an assertion means* for all 24 rigs, and nothing read it.

**§0 grew a third entry.** The two `wait_for` sequencing gates left unconverted are a deliberate
Phase 12 decision with a stated rationale, and they look exactly like unfinished work to the next
reader — so they are now on the do-not-reopen list with the reason attached.

**The one paid item is unchanged and still unbought.** `verify_handoff.py`'s 21/21 is still a Phase
4 score against a file Phase 5 edited. Its floor is 22.

Deliberately **not** in the prompt:

- **Worktree isolation** (build-order step 7). `PLAN.md` marks it optional and nothing needs it.
- **Semantic citation checking.** `probe_citations.py` proves a citation points somewhere real,
  never that it points at the right thing. That is a reading task, not a probe.
- **Making the suite portable** — a fresh clone cannot rebuild `hb/*.db` without paying.
- **Turning contract 6 on the `wait_for` gates.** See §0.

## Current state, for the maintainer of this file

Phase 12 changed **no fork code**. `healbot.tsx`, `builtins.ts`, the plugin and the patch are
untouched, so the overlay stays pinned at `509f4c0b1`. What changed is the test rig: `rig.py`
(new `completed()`, corrected `fire()` docstring), `probe_rig_contract.py` (contract 6, +7
assertions), `verify_question.py` (two rows fixed, three transcript rows added, floor 27 → 30) and
`verify_permission.py` (two rows fixed, floor unchanged).

What it found:

- **`fire()` could not fail.** A thrown turn and a finished turn are appended in the same 3-tuple
  and element `[2]` was read by nothing in the suite. TESTED at a dead port: three `URLError`s in
  **9 ms** satisfied every completion predicate the suite owns.
- **Four `r.check` rows** were named for a thing they could not see. **One** — `verify_question.py`'s
  concurrency row — had no independent evidence anywhere else in its file; the other three sit
  beside transcript checks that carry the real weight. The founding concurrency premise is *not* in
  doubt: `verify_permission.py` proves it with fixture payloads pulled from the server.
- **The guard rediscovers the finding.** Contract 6's negative control is the *actual* pre-Phase-12
  source recovered from git `HEAD`, and it reports exactly four violations at exactly the four lines
  named in `docs/OUTCOME.md` §2, plus zero against the fixed source.
- **Then it paid for one rig, and that found three more.** `verify_question.py` ran for the first
  time since Phase 4: **27/30, exit 1**, on a clean DB.
  - **Three assertions have been red since Phase 5**, which built auto-surface and left the
    assertions that assume it does not exist — with a comment in the same file describing the new
    behaviour correctly. **Phase 10's `grep -c 'r.check('` reconciliation cannot detect this**: 27
    sites against a recorded 27/27 reconciles perfectly. The behaviour changed; the count did not.
  - **Three paid rigs are single-use** — they compare the grid header to a literal (`4 sessions`)
    against a DB that never resets. The literal cannot hold anyway: extra ask attempts *and*
    model-spawned **subagents** both add cells, and the run rendered six.
  - **`wait_for`'s timeout does not bound** — 300s budgets wrapping a 900s `Api` default.
  All three are documented and deliberately NOT repaired, so the 27/30 describes the file that
  produced it. They are §2 of the task list above.
- **Checked and healthy:** floors are tight — 19 of the 20 statically boundable rigs have
  `floor == unconditional count`, and the exception (`probe_turn_growth.py`) is deliberate;
  `term.py` is clean; every load-bearing figure in `probe_turn_growth.py` is unmoved.
- **Corrections:** the rig sweep is **24** entrypoints, not the 23 three documents said;
  `probe_rig_contract.py`'s own detail string said *"all twenty end on it"*, hardcoded; and Phase
  10's *"reconciles every other rig in one command"* is now bounded by §2's first item.

Free suite: 4/4, 10/10, 24/24, 10/10, 14/14, 25/25, 14/14, 9/9, 18/18, **13/16 RED**, **29/29**,
14/14 — **184 of 187**, eleven probes exit 0 and one exits 1 (real exit codes, not `tail`'s). The red
is `probe_turn_growth.py` and it is CORRECT: see the fifth finding below. It was 16/16 at the start
of this phase and went red because paying for two rig runs moved the maximum it guards. Gates: `tsgo` exit 0 with no
output, `oxlint` exit 0 with the expected 3 warnings.

**One loose end that is not a defect:** `docs/REFUSAL-BASELINE.md` is **untracked** while
`HARNESS.md` links to it as Phase 0R. A fresh clone gets a broken link from the root index. It is
the owner's file and the owner's call whether it gets committed.
