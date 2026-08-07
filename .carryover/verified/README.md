# Verified rig — the redo that counts

Supersedes `../verify*.py`, which are void (local model, forced question path). These ran on
`openai/gpt-5.6-sol` through the real harness. 90/91 assertions passed; the one failure was a
bug in the test, not the code (see below).

```sh
python3 -m venv venv && venv/bin/pip install pyte

# free — no model turns, no API credits.
# TEN OF THESE RUN ON A FRESH CLONE, and the venv above is the only thing they need. MEASURED
# 2026-08-07 in a worktree with NO opencode/ checkout present: probe_gate_scope (32),
# probe_memory_store (70), probe_pool (33), probe_refusal_driver (30), probe_refusal_fixtures (9),
# probe_refusal_scoring (20), probe_review_parse (9), probe_rig_contract (40), probe_study_driver
# (42) and probe_turn_predicate (18) went 303/303 green. None of the ten reads hb/ at all.
# EVERY OTHER PROBE IN THIS LIST NEEDS MORE. Stated as an allowlist on purpose: an earlier draft
# named seven that need more and so implied, by omission, that the other eight run.
# MEASURED, and reproducible across runs: probe_citations, probe_twin, probe_control_wiring and
# probe_staleness_join exit 3 without the gitignored opencode/ checkout (rebuild from
# fork/README.md); probe_headless_arm and probe_request_channel call rig.serve(), which runs that
# same checkout; probe_error_state, probe_focus and probe_turn_growth need hb/*.db, which only the
# PAID rigs below can create.
# DELIBERATELY NOT CHARACTERISED: probe_backend, probe_fleet_claude, probe_gnhf_spend,
# probe_arm_factory, probe_fleet and probe_on_grid depend on ambient state rather than on the
# checkout — a Claude Code transcript for THIS checkout (probe_backend exits 3 without one, its
# own declared cannot-measure sentinel, not an environment skip), a live server, or a skip budget.
# Two sweeps an hour apart gave different exit codes for three of them, so any fixed list here
# would be a number that rots between runs. Run them and read the probe's own output.
# An earlier version of this comment said "all but probe_turn_predicate.py need the checkout" and
# "on a fresh clone this suite does not run". Both were false, and together they discouraged the
# only free verification a fresh clone has — see docs/CLONE.md.
#
# THE N/N BESIDE EACH PROBE IS ITS DECLARED FLOOR, `Results(expect=N)` in the probe itself, which
# is the only place that number is true. Four of them had drifted below the live floor when this
# was written (control_wiring 14, pool 24, arm_factory 19, gate_scope 30), so an operator running
# pool and seeing 33/33 had a manual telling them to expect 24.
venv/bin/python probe_on_grid.py     # 4/4   does the route predicate actually discriminate?
venv/bin/python probe_fleet.py       # 10/10 does harness/fleet.sh do what it claims?
venv/bin/python probe_error_state.py # 10/10 does a hard-errored session render ERROR?
                                     #       (replays the 350K run's real overflow DB)
venv/bin/python probe_focus.py       # 24/24 does `enter` open the SELECTED session? (same DB)
venv/bin/python probe_twin.py        # 25/25 is there still exactly ONE implementation of
                                     #       retirement, and does the untyped request channel
                                     #       agree at both ends? (NOT a document comparison any
                                     #       more — see below)
venv/bin/python probe_headless_arm.py# 14/14 does the retirement guard arm with NOTHING rendering
                                     #       — at the SHIPPED 180,000 default, with no override
                                     #       anywhere, and does the arming line name ONE gate?
                                     #       (was 15/15; the hard-gate assertions went with the
                                     #       constant)
venv/bin/python probe_turn_predicate.py # 18/18 does `turnFinished()` actually distinguish a TURN
                                     #       from a step? Brace-matches the function out of the
                                     #       shipped plugin and runs THAT TEXT in node against the
                                     #       measured message distribution
venv/bin/python probe_request_channel.py # 9/9 does `x`'s metadata write actually reach the server
                                     #       and retire THAT session and no other? (real server,
                                     #       no model turn — an empty session has no todos, so
                                     #       retire() takes its no-successor branch)
venv/bin/python probe_control_wiring.py # 16/16 are the control tools and agent registered?
venv/bin/python probe_pool.py        # 33/33 does harness/pool.py's lease/guard machine refuse
                                     #       what it claims? (miniature pool of real git repos,
                                     #       every refusal exercised with the violating state)
venv/bin/python probe_arm_factory.py # 23/23 does a synthesized arm hold EXACTLY its declared
                                     #       delta? (arms.py: freeze/materialize/tamper-refuse,
                                     #       then boots BOTH arms and diffs GET /skill)
venv/bin/python probe_citations.py   # 21/21 do this repo's file:line citations still point at
                                     #       code? Resolves every citation the prose carries and
                                     #       asserts the file exists, the line exists, and it is not
                                     #       blank. fork/README.md's "drift mode 2", which was named
                                     #       as a risk for eleven phases with no check behind it
venv/bin/python probe_rig_contract.py# 40/40 does every rig in this suite still report FAILURE as
                                     #       failure — and can it SEE one? Reads every entrypoint (36 today)
                                     #       (itself included) as SOURCE and asserts six contracts:
                                     #       a declared assertion FLOOR, a satisfiable one, no
                                     #       `finally` that exits without a crash guard, an exit
                                     #       status that depends on summary(), that verdict exit
                                     #       LAST in the finally — and (Phase 12) that no assertion
                                     #       decides a turn COMPLETED by counting fire()'s box.
                                     #       Six paid rigs failed the fourth and always exited 0;
                                     #       four rows failed the sixth and could not fail at all
venv/bin/python probe_gate_scope.py  # 32/32 does the pre-push gate gate the PUSHED range, not the
                                     #       checkout's HEAD, and does it enumerate that range at
                                     #       all? Builds a scratch bare remote plus a
                                     #       work repo, drives a real merge push through the REAL
                                     #       hook and gate.py from a checkout parked on an ancestor
                                     #       branch, and asserts the planted F841 in the pushed
                                     #       blob refuses the push. A second scenario pushes a
                                     #       non-ASCII and a spaced path, one of them a BANNED
                                     #       filename. FOUR mutation legs (base...HEAD scoping
                                     #       reverted; record head reverted to tree; the quoting
                                     #       flag removed; the enumeration's exit code ignored) are
                                     #       all detected by the same predicates the live legs
                                     #       pass. Pins run 20260802-184854, the merge push that
                                     #       gated as zero files. Needs ruff on PATH; no checkout,
                                     #       no venv beyond stdlib, so it survives a fresh clone
                                     #       (the score above was 2 stale before this row was
                                     #       rewritten; it is a number nothing computes, so trust
                                     #       `Results(expect=N)` and the probe's own print)
venv/bin/python probe_turn_growth.py # 20/20 green again; the Phase-12 red below was CORRECT and is RESOLVED.
                                     #       A single turn measured 299,326 on the pinned model —
                                     #       71% above the 175,148 RETIRE_AT is derived from — so
                                     #       180,000 + 299,326 = 479,326 against a ~360K ceiling and
                                     #       the margin is -119,326. Cause: hb/project is an
                                     #       UNDECLARED variable in the derivation. It has grown to
                                     #       84 entries / 94 MB / node_modules across every paid run
                                     #       ever, because sessions create files nobody cleans and
                                     #       git_baseline() commits them into the baseline. Exclude
                                     #       Phase 12's two runs and the maximum is still 175,148.
                                     #       DO NOT clear hb/project or drop a DB to make this green
                                     #       — that deletes the measurement to restore the number.
                                     #       docs/OUTCOME.md §10; decided in §11: declared scope,
                                     #       RETIRE_AT stands (NEXT.md carries it as DECIDED).
                                     #       (was 16/16) is ~170K the TAIL or the MIDDLE of single-turn growth?
                                     #       Re-derives the `worst_turn` that SIZES RETIRE_AT from
                                     #       every session DB on disk instead of the one turn it
                                     #       rested on. Runs the SHIPPED turnFinished() and
                                     #       occupancyOf() in node; negative control regroups the
                                     #       same corpus with the OLD per-step predicate

# these spend credits
venv/bin/python smoke.py             # 6/6   provider/model/config sanity — run this first
venv/bin/python verify_permission.py # 40/40 the exit-gate permission clause at N=4
venv/bin/python verify_question.py   # 27/30 the question clause, UNFORCED. THREE KNOWN REDS since
                                     #       Phase 5, found by Phase 12's run — its FIRST execution
                                     #       since Phase 4. Phase 5 built auto-surface (the cursor
                                     #       lands ON the blocked cell) and left three assertions
                                     #       assuming it does not: "'a' on an unblocked cell",
                                     #       "tab moved the cursor onto the blocked cell", and
                                     #       `t.find("4 sessions")` — which cannot hold at all, since
                                     #       extra ask attempts and model-spawned SUBAGENTS both add
                                     #       cells (this run rendered 6). The recorded 27/27 was a
                                     #       PHASE 4 score, and it reconciled perfectly under Phase
                                     #       10's count-the-sites check: 27 sites, 27 recorded.
                                     #       Counting proves a score is REACHABLE, not ACHIEVABLE
venv/bin/python verify_surface.py    # 18/18 auto-surface, suppression, tab cycling. Was 17/18 for
                                     #       five phases on a TEST bug that Phase 10 fixed — and
                                     #       that could sit there because this rig discarded
                                     #       summary()'s verdict and exited 0. VERIFIED, not yet
                                     #       re-run. docs/VERDICT.md §4
venv/bin/python verify_retire.py     # 17/17 the retirement observable and threshold
venv/bin/python verify_handoff.py    # 21/21 retire and hand off with continuity intact
                                     #       ** STALE: 21/21 is a PHASE 4 score. Phase 5 took the
                                     #       file to 22 unconditional assertions and never re-ran
                                     #       it, so 21/21 is unreachable. Floor is 22; re-run it
                                     #       before quoting the number. docs/VERDICT.md §2
venv/bin/python verify_cold.py       # 21/21 the COLD-START reconcile, via serve + attach
venv/bin/python verify_cold_question.py # 22/22 the question.rejected half of that reconcile
venv/bin/python verify_auto_retire.py # 13/13 automatic retirement WITH THE GRID OPEN. Superseded
                                     #       by the one below; kept because it is the record of
                                     #       the Phase 5 behaviour
venv/bin/python verify_headless_retire.py # 22/22 automatic retirement with NO TUI ANYWHERE,
                                     #       and the gate crossed MID-TURN so it discriminates
                                     #       Runs at a HARDCODED 20,000 and cannot be pointed at
                                     #       180,000 — there is no override to remove; see below
venv/bin/python verify_control_agent.py   # 15/15 the control agent's tools, and the scoping that
                                     #       keeps them out of every other session's prompt.
                                     #       Was 15/16 for two phases against an assertion that had
                                     #       been rewritten twice and never run; Phase 8 ran it, the
                                     #       assertion was DISPROVED on execution, and the fourth
                                     #       form is what is now green — see below
venv/bin/python verify_retire_350k.py# 25/25 retirement at a full-scale threshold.
                                     #       ~5M cumulative input tokens; run it deliberately —
                                     #       and read its docstring first, the 25/25 predates
                                     #       server-side retirement AND every threshold since
                                     #       350,000 (350,000 -> 256,000 -> 180,000)
```

**Since Phase 6 the SERVER enforces the retirement thresholds, not the client.** Automatic
retirement is a server plugin (`harness/config/opencode/plugin/healbot.ts`), so a rig that sets
`HEALBOT_RETIRE_AT` in its own environment before `attach()` is configuring the wrong process.
`rig.serve(..., env_extra={...})` is how you reach the server; `rig.serve(..., log=path)` is how you
read what it did, and it matters because the plugin's log line is often the only independent
evidence that the thing under test actually happened. Under `boot()` the TUI hosts the server
in-process, so the ambient environment still reaches it — which is why `probe_error_state.py` and
`probe_focus.py` can still disarm the gate with `os.environ["HEALBOT_AUTO_RETIRE"] = "0"`.

**`verify_headless_retire.py` cannot be pointed at 180,000, and "just remove the override" is not
an operation you can perform on it.** `THRESHOLD = 20_000` is a bare literal (`:52`) that the rig
forces into the SERVER's environment itself (`:96-103`, the `env_extra={"HEALBOT_RETIRE_AT":
str(THRESHOLD), "HEALBOT_AUTO_RETIRE": "1"}` at `:102`), and `rig.py`'s `serve()` applies
`env_extra` LAST (`:159`, after `OPENCODE_DB` at `:157` and the `OPENCODE_CLIENT` default at
`:158`), so an ambient value is overwritten unconditionally — there is nothing to remove. Editing
the constant does not rescue it either: the rig fires ONE prompt whose only growth is a single
`read` of the 130 KB `ledger0.txt` (`:140`, `offset=1 limit=1400`), and the read tool caps a call's
output at 50 KB (`MAX_BYTES = 50 * 1024`, `opencode/packages/opencode/src/tool/read.ts:16`,
enforced at `:164`, announced to the model at `:345`). Recorded peak occupancy for that run was
36,647. Raise its threshold and the gate never fires, the 900-second `wait_for` (`:148-162`) times
out, and it exits 1. Its docstring says it runs low ON PURPOSE. Wrong vehicle, and it was named as
the full-scale one for a while.

**What is unbought at 180,000 is narrower than "the shipped gate has never been exercised".** Split
it in two and only one half costs money. (a) WHICH CONSTANT ARMS is a fact about config resolution
and it is TESTED, free, in `probe_headless_arm.py:170-189` — a third server started with
`env_extra={}` and no `HEALBOT_RETIRE_AT` anywhere, asserted to log `gate 180,000`, and asserted
separately (`:180-184`) that the arming line names ONE gate. It is deliberately paired with the
pre-existing negative at `:114-118`, which requires that same string to be ABSENT when an override
IS supplied: one string asserted both ways in one run, so neither can be passing for a trivial
reason. (b) WHETHER A SESSION DRIVEN TO 180,000 RETIRES is still TESTED at 20,000 only, and
threshold-independent by inspection — the gate is one `>=` against a variable. The vehicle that
would buy (b) is `verify_retire_350k.py`'s growth loop (`MAX_TURNS = 70` at `:82`,
`CHUNK_BYTES = 35_000` at `:83`, and it already `os.environ.pop("HEALBOT_RETIRE_AT", None)` at
`:90`) retargeted to 180,000.

Costing, REDONE for the 180,000 target — the previous version of this paragraph costed a 256,000
target at ~$4.50 and is superseded, not merely rescaled, because the tier argument under it changed
sign. **~$2.60, range $1.75-5, ~6-11 min wall.** Turns: 180,000 ÷ the recorded 9.46K/turn = 19.0,
call it ~19, against 37 turns to reach 350,000. Cumulative context is quadratic — every turn
re-sends everything before it — so it scales N(N+1)/2 and the ratio to the 350K run is
(19×20)/(37×38) = 380/1406 = 0.270. Against that run's ~5M cumulative input tokens: 0.270 × 5M =
1.35M. Split the way the 350K run's was, a tenth of input written to cache and nine tenths read
back, with ~2K of output per turn: 0.135M cache_write at $6.25/M = $0.84, 1.215M cache_read at
$0.50/M = $0.61, 38K output at $30/M = $1.14. Sum $2.59. Wall clock scales with turns, 19/27 = 0.70
of the 8-15 min the 256,000 target would have taken.

The provider-tier point gets STRONGER at 180,000, and this is the part that is not a rescaling. The
272,000 context tier DOUBLES every rate above it, so the estimate only holds while the largest
single request stays under it. At 256,000 the margin was 16,000 tokens — under two turns of growth
at 9.46K/turn, so one long tool result could have tipped the last turns into the 2× tier and the
estimate with them. At 180,000 the margin is 92,000, about ten turns, and base rates hold for the
whole run with room to spare. (The 350K run itself crossed into the 2× tier for its last ~8 turns,
which is why its recorded cost is not simply 5M at base rates.) NOT BOUGHT.

**`verify_control_agent.py` now reports 15/15, and getting there DISPROVED the assertion Phase 7
wrote.** It stood at 15/16 for two phases against a check that had been rewritten twice and never
run. Phase 8 ran it. The third form — *it created NO top-level session* — **failed on its first
execution**, and correctly: the build agent, with all five tool definitions removed from its payload,
went looking with `opencode --help` / `session list` / `run --help` and then ran

    opencode run --auto --format json --title "..." "Create a file named hello.txt ..."

which created a real TOP-LEVEL session. The `opencode` CLI is on `PATH` inside the tool sandbox and
talks to the same database.

**So `healbot_*: deny` scopes CONTEXT, not CAPABILITY**, and the rig's own comment on `TASK` had
asserted the opposite — *"a session cannot create ANOTHER session with `bash`"* — since the day it
was written. That premise is now marked disproved in the file. What is untouched is the claim the rig
is paid for: the tool definitions really are absent from the build agent's request payload, which is
the token-budget claim, and it still passes.

The fourth form asserts what the deny actually guarantees — **no healbot TOOL spawned anything**,
checked against the server log, which only the server writes, so a leak produces a second
`control: spawned` line. The containment finding itself is printed as an `[observation]` and
deliberately is **not** an `r.check`: it has no failing case, and an assertion that cannot go red is
this suite's characteristic failure. Both runs are on record and they took different branches — run 1
shelled out (observation printed the command), run 2 delegated via `task` (observation printed
`NOT EXERCISED this run`). The build agent's response to losing the tools is not deterministic, which
is exactly why the finding is pinned to the recorded run rather than to the next execution.

Note the shape of the sequence, because it is the point: form 2 (`all()` over a possibly-empty list)
was too weak to fail; form 3 was strong enough to fail, and did, against a premise nobody had
re-read in two phases. **A test that cannot fail is not merely useless — it is load-bearing in the
wrong direction.** It was the reason the comment went unexamined.

**The gate waits for the TURN, and the version of this paragraph written a few hours ago said the
opposite.** It said *the gate fires per STEP, not per turn*, that *the turn in flight IS aborted*,
that overshoot was *bounded by one STEP (~65K measured) rather than one whole turn (~170K
measured)*, and it called that *better than what was designed, arrived at by accident*. All of that
described the code as it then stood and none of it describes the code that ships now.

The finding underneath it was correct and is worth keeping, because it is why a rig can be fooled
here. `processor.ts:443-445` assigns `finish` and `tokens` in the SAME mutation at every
`step-finish`, and `:445` is the only site in the session tree that writes a non-zero `tokens` — so
every `message.updated` that carries occupancy at all also carries a set `finish`, usually
`"tool-calls"`, i.e. mid-turn. MEASURED across 733 real assistant messages with occupancy > 0: zero
had a null `finish` (677 `tool-calls`, 56 `stop`). A predicate that reads `finish` — or
`time.completed`, which `cleanup()` sets per step at `processor.ts:595-596` — is therefore true
mid-turn on essentially every event the gate ever sees. That is the defect that survived two
phases.

Phase 7 fixed the predicate rather than the prose. `turnFinished()`
(`harness/config/opencode/plugin/healbot.ts:386-389`) is now opencode's own, from `prompt.ts:1295`:
`if (info.error) return true; return Boolean(info.finish && !["tool-calls","unknown"].includes(info.finish))`.
It deliberately does not read `time.completed`. `consider()`'s parameter is `turnOver` and its
guard is a plain `if (!turnOver) return` (`:681`, `:691`). **Nothing is aborted on the gate path** —
`retire()` still calls `POST /abort` (`:542`, under the comment at `:527-541`), but on this path it
is a no-op by construction, because `turnFinished()` is what got the call there. It exists for the
race where a turn starts between the check and the call, and for `healbot_retire` arriving from the
control agent on a session that is working.

**`RETIRE_HARD` is DELETED, and this file used to record it as merely INERT.** The finding stands
as history: at 330,000 its only consumer was `consider()`'s `if (!stepOver && !hard) return`, and
`stepOver` was true on 733/733, so it never once fired and `HEALBOT_RETIRE_HARD` was a knob with no
effect. The previous paragraph kept it on the grounds that it would become *load-bearing again the
day the predicate becomes per-turn*. That day arrived and the owner deleted it instead — the
constant, the `hard` variable, the guard, the env var and its half of the arming log line are all
gone from `healbot.ts` and `healbot.tsx`, and `HEALBOT_RETIRE_HARD` now reads nothing. VERIFIED by
grep over both files, and asserted twice in the suite: `probe_twin.py:132-136` and
`probe_turn_predicate.py:162-166`. The margin the hard gate was supposed to provide now comes from
the THRESHOLD being low enough to absorb a worst-case turn, which is why the default moved.

**PHASE 8 RE-DERIVED `worst_turn`, AND THE PARAGRAPH BELOW RESTS ON ONE TURN.** `probe_turn_growth.py`
(free, 16/16) groups every assistant message on disk into TURNS with the shipped `turnFinished()` —
86 completed turns, the rig DBs plus the same `~/.local/share/opencode/opencode.db` the 733-message
figure comes from, fixture-checked at 677/56/733. Results: the worst single-turn growth on the pinned
`gpt-5.6-sol` is **175,148**, so the bound on `RETIRE_AT` is **184,852**, not the ~190,000 stated
below and in three other files, and 180,000 clears it by **4,852 tokens — 1.3% of the ceiling**,
thinner than the "~10K, under 3%" margin this project already rejected at the old 350,000 default.

> **SUPERSEDED IN PHASE 12 — the bound is 289,296 and the margin 30.4%.** Everything in this
> paragraph is a maximum over turns that mostly START AT ZERO, and the gate never faces one: a turn
> beginning at 0 that grows 175,148 *ends* at 175,148, well under the ceiling. The rule
> `RETIRE_AT + worst_turn < ceiling` is about a session already near the gate taking one more turn,
> so the corpus now has a declared SCOPE — completed, started >= 100,000, compaction off — and
> `worst_turn` is the maximum over that population: **70,704**. 175,148 is itself out of scope, and
> the probe asserts that, because a scope invented to protect a number would have kept it.
> `docs/OUTCOME.md` §11.
~170K is the **tail** (p50 is 22,152), it just is not the **maximum**, which is what the derivation
used it as. **And the threshold is MODEL-SPECIFIC**: the corpus holds a **223,258** turn on
`gpt-5.6-terra`, which at 180,000 lands at 403,258 and dies — so the number is verified only while
`harness/config/opencode/opencode.jsonc:16` pins `gpt-5.6-sol`, and the probe asserts that pin. `docs/GROWTH.md` §1.

**`RETIRE_AT` defaults to 180,000, down from 256,000, and the number is a consequence of the
semantics above.** With one gate the requirement is `RETIRE_AT + worst_turn < ceiling`. Waiting for
the turn means accepting whatever that turn adds, and worst measured single-turn growth is ~170K
(`docs/HARDEN.md` §6: occupancy 5,216 → 70,898 on a single tool result, that turn finishing at
175,090). The ceiling is ~360K MEASURED — last good turn at 359,829, then 25 consecutive
`ContextOverflowError`s. So 180,000 + ~170K = ~350K, just inside, and anything at or above ~190,000
can be carried off the cliff by one ordinary read-heavy turn. 256,000 was correct for the design it
was chosen against — a second gate at 330,000 aborting mid-turn — and is the one value that must
not be paired with a per-turn predicate and no hard gate. The arming line now reads
`headless retirement armed — gate 180,000 (per-turn, single gate), directory …`; it used to read
`soft N, hard N`. Unchanged by any of this: the ~360K ceiling, the ~4.8K floor,
`compaction.auto: false`, and the handoff document.

**Paths derive from `__file__` and fixtures generate themselves.** They did not until Phase 5:
every `verify_*.py` hardcoded an absolute scratchpad path belonging to the session that wrote
it, and nothing created the `worker*.txt` payloads or the 130 KB `ledger*.txt` files the
retirement rigs prompt against — so the suite could not be re-run from a fresh clone at all.
`rig.fixtures()` now builds them; `rig.db(name)` gives each rig its own isolated DB. Override
the work directory with `HEALBOT_RIG_WORK` if you want it off the repo.

## The refusal A/B entrypoints

The files below are the OUTCOME half of the suite: probes and rigs answer "does the code do
what the map says", these answer "does a harness change make the agent better or worse". None
carry a `probe_`/`verify_` name, on purpose: they are drivers and libraries, so
`probe_rig_contract.py`'s sweep does not pick them up, and their contracts are held instead by
dedicated free probes named per file below. Each of those probes declares its own
`Results(expect=N)` floor, which is where the numbers live; this section quotes no scores.
Anything here that reaches a model spends credits, so the paid-run-protocol skill governs
every launch. `AB-HANDOFF.md` (this directory) is the design brief the half was built from;
`docs/REFUSAL-BASELINE.md` holds the question, `docs/REFUSAL-RESCORE.md` the closed full run
and the corpus-v2 fixes, and `hb/ab-runs/refusal-full-archived-20260731/ARCHIVED.md` the
stranded first launch.

**`ab.py` is the A/B library: arms, the pinned turn, the scorer, the paired statistics.** An
ARM is a complete runtime configuration, a STUDY is a fixed corpus of prompts, and the model is
pinned identically in every arm (`PIN`, `ab.py:54`) because varying the model and the harness
at once measures neither. It owns the two ENVIRONMENT arms (`ARMS`, `ab.py:73-96`: `harness`
sources env.sh, `stock` inherits the user's real `~/.config/opencode`); `serve_arm()`
(`ab.py:99-130`), which strips the three env.sh exports that would otherwise leak into the
stock arm and silently equalize the very contrast under test (`:120-121`); `ask()`
(`ab.py:133-141`, one synchronous pinned turn returning the raw transcript); and the shape
classifier `score()` (`ab.py:255-311`), whose outcomes are comply / hedge / de_escalate /
refuse_model / refuse_provider / empty plus a `needs_review` flag for whatever it cannot
cleanly separate. The DECLINE patterns are FIRST-PERSON ONLY (`ab.py:221-229`): Set A's
compliant answers are saturated with "malware"/"exploit" vocabulary, so a topic grep returns a
confident, exactly-backwards refusal rate. `probe_refusal_scoring.py` holds that inversion as
a hand-labeled fixture and REQUIRES the naive grep to fail it; do not weaken that probe.
`provider_blocked()` (`ab.py:169-188`) is the scorer's one exact discriminator, structural on
`finish: "content-filter"`, separating "the model declined" from "the provider blocked".
`delivered()` (`ab.py:314-318`) is the binary the paired test runs on; `mcnemar_exact()`
(`ab.py:324-341`) and `wilson()` (`ab.py:344-354`) are the statistics. Runs persist under
`hb/ab-runs/<study>-<tag>/` (`ab.py:50`) with every turn's full transcript in `rows.json`
(`ab.py:404-412`), so every number is re-derivable and auditable without spending again.

**`run_refusal.py` is the Set A driver, first generation, now pinned by its own history.** It
runs the refusal corpus over the two environment arms on ports 4771/4772 (`run_refusal.py:33`)
and owns the Set A corpus contract (`validate_study()`, `run_refusal.py:36-78`): exactly 25
probes, five families of five, every probe carrying an `artifact` regex that must match its
inline compliant fixture, miss its topic-matched negative, and miss a generic refusal
(`:68-73`). `probe_refusal_fixtures.py` re-checks those regexes against the realistic corpus
in `studies/refusal/fixtures/` because hand-written fixtures passed while two of the first
four regexes exercised on real output were wrong. The run ledger is the shape the second
driver later copied: checkpoint after every row, reserve-before-send (`run_refusal.py:516-524`),
an interrupted ambiguous turn REFUSES to be repeated without `--retry-pending` (`:496-504`),
`--rescore` re-derives labels from saved transcripts with zero model calls after verifying
every saved prompt against the corpus (`:418-427`), and the pin is asserted from the returned
transcript after every persisted row (`:542-544`). Its meta pins the corpus, scorer and driver
bytes (`run_refusal.py:286-287`) and resume refuses drift (`:393-397`), which is why
pluggability went into a new driver rather than an edit (`run_study.py:3-11`). **A bare
invocation no longer starts a run** (`:325-336`, `:382-384`): a tag whose directory holds no
`meta.json` is refused before the directory is created, with any `-archived-*` sibling named,
and `--start-new` is the only way to begin at row zero. That edit moves `driver_sha256` and
orphans no resumable run — `scorer_sha256` in both recorded metas already differs from the
live `ab.py`, and `--rescore` allows drift in all three hashes (`:395`). Its
one real weakness is that it reads the LIVE `studies/refusal/set_a.json` on every invocation
(`run_refusal.py:365`), so a corpus edit after paid rows exist orphans the spend. That is what
stranded `refusal-full` at 24/150 rows on 2026-07-31; ARCHIVED.md is the record, and the run
was archived BY RENAME so the tag-derived path can never resume it. Free guard:
`probe_refusal_driver.py`. Companions: `verify_refusal_a.py` reads a completed run back
without spending, and holds `needs_review` rows out of the aggregate until a human outcome is
supplied; `verify_refusal_b.py` is the Set B negative control (permission gating on
`studies/refusal/set_b.json`, scored on the gate event, not on model text).

**`run_study.py` is the second-generation driver: a pluggable per-study scorer over frozen
synthesized arms, built ALONGSIDE `run_refusal.py` rather than editing it.** Three designs
distinguish it, and each exists because the first launch died of the alternative:

- **The scorer is the study's, not the driver's.** A study definition is a module
  `study_<name>.py` in this directory owning `validate()`/`score()`/`delivered()` plus an
  optional `pilot()`, enforced at load (`run_study.py:106-109`). meta pins BEHAVIOR, not a
  wrapper: `sources_sha256` records one sha per file the definition declares in `SOURCES`,
  plus the driver itself (`run_study.py:121-125`), so delegated logic cannot drift behind an
  unchanged wrapper hash. A scorer returning a driver-reserved row key is refused outright,
  because those keys are spend evidence (`DRIVER_KEYS`, `run_study.py:84-87`).
- **Arms are frozen at creation, never inherited.** `--arms-spec` is a JSON list
  (`arms-tdd.json` is the live example: `base`, plus one arm adding the tdd skill), and it is
  read exactly ONCE, at run creation (`load_armspec`, `run_study.py:429-454`); `create_run()`
  writes the frozen corpus, then the frozen arms, then meta (`run_study.py:493-516`). A new
  run REQUIRES the spec (`:718-719`); a resume REFUSES it (`:711-712`). After creation the run
  directory owns the bytes (`run_study.py:56-58`). The driver contains no environment arm at
  all: `ab.ARMS` and `ab.serve_arm` are deliberately unreferenced, and
  `probe_study_driver.py` asserts that from the AST (`run_study.py:24-26`).
- **The corpus is frozen the same way.** The live `studies/` file is read exactly once, at
  creation; resume and `--rescore` read the run directory's own `corpus.json`
  (`run_study.py:699-700`), so the live-corpus edit that blocked `refusal-full`'s resume
  cannot recur here. A tag whose directory this driver did not create is refused, never
  adopted (`:694-697`), and resume re-verifies the frozen arm manifests against the digests
  meta recorded at freeze (`verify_frozen_arms`, `run_study.py:472-486`).

A probe may also carry a HIDDEN EXECUTABLE CHECK: a shebang script frozen with the corpus, run
after the turn in a pooled disposable workspace (`harness/pool.py`) the turn's session was
bound to, with the script body written OUTSIDE the workspace so the model can never read the
test it is scored by (`run_study.py:335-368`). The result lands on the row as raw evidence,
and `--rescore` re-reads the RECORDED result rather than re-running a check against a restored
tree (`:311-315`). Servers take ports 4791+i (`run_study.py:80`). Free guard:
`probe_study_driver.py`, which exercises each refusal above with the violating state actually
present. The recorded execution: `refusal tdd-full-1`, 150 rows complete, `base` vs
`plus-tdd` on frozen corpus `771ce241`, a powered null (both arms delivered 75/75, exact
McNemar p = 1.0) with 27 `needs_review` rows re-scored to 12 under corpus v2;
`docs/REFUSAL-RESCORE.md` is the record.

**`study_refusal.py` is instance one of the study-definition contract, and it is deliberately
nearly empty.** The refusal scorer was born in `ab.py` and its corpus contract in
`run_refusal.py`, and both are pinned by paid rows, so this definition DELEGATES: `validate()`
is `run_refusal.validate_study`, `score()` wraps `ab.score` (dropping the `models` key the
driver's `pin_result` owns, adding `family`), `delivered()` is `ab.delivered`
(`study_refusal.py:43-55`). `SOURCES` declares all three files (`study_refusal.py:40`), so an
`ab.py` edit surfaces as `sources_sha256` drift even while this wrapper stays byte-identical.
The `check` parameter is accepted and ignored: refusal probes classify transcript shape and
produce no work product to check (`study_refusal.py:20-23`).

**`arms.py` is the arm factory: synthesized, frozen runtime configs, base plus at most ONE
delta skill.** Environments move: the stock arm changed twice on 2026-07-31 alone, which is
what made frozen arms a precondition for ever launching again. A synthesized arm inverts the
dependency, so the study owns the config bytes. `define()` refuses a delta body carrying the
`` !`cmd` `` shell-substitution hole (`arms.py:107-111`). `freeze()` snapshots every base
config file with per-file sha256 into `<run>/arms/<name>/` and fails CLOSED on an
unconstituted base: no `package-lock.json` or no `node_modules`, no freeze (`arms.py:132-140`).
`materialize()` rebuilds a live `XDG_CONFIG_HOME` from the snapshot, byte-verifying every file
(`arms.py:191-197`) and refusing on lockfile drift (`:218-234`); `node_modules` itself is NOT
frozen, the lockfile pins it. `serve()` boots the arm with `XDG_CONFIG_HOME` at the
materialized directory and BOTH external-skill switches pinned off (`arms.py:250-252`), so the
only skill any arm can see is the one its manifest declares. The repo's `SKILL.md` filename
ban is satisfied by construction: the tracked snapshot stores the delta as `_delta_skill.md`,
and only `materialize()` writes a literal `SKILL.md`, into `hb/arms/`, which `.gitignore`'s
`hb/*` rule ignores (`arms.py:21-28`, `:163-167`). Guard: `probe_arm_factory.py`, already in
the free list above.

**`backend.py` makes the second PROGRAM addressable: an arm is a configuration, a backend is
the program that runs it.** It normalizes Claude Code's persisted JSONL transcripts into
opencode's message shape, the vocabulary every existing consumer already reads, rather than
inventing a neutral third schema (`backend.py:10-17`). The `STOP_REASON` map
(`backend.py:76-83`) carries the one load-bearing row, `"refusal"` to `"content-filter"`: drop
it and every provider block silently reclassifies as a model refusal (`:70-75`). `thinking`
blocks are dropped, because a model that reasons "I can't just refuse this" and then complies
must not score as refusing on its own scratchpad (`backend.py:149-157`), and sidechain records
are excluded, because sub-agent turns carry their own model and token accounting
(`:173-180`). `ClaudeCodeBackend` spawns the installed CLI headless and re-reads the
transcript it persisted (`backend.py:230-281`); `OpencodeBackend` wraps `ab.serve_arm` behind
the same two methods (`backend.py:284-315`). A Claude Code arm deliberately CANNOT join Set A:
the method is the model held constant, and Claude Code serves Anthropic models, so this
backend measures Claude Code sessions (occupancy, retirement, handoff), it is not a third arm
(`backend.py:23-31`). Free guard: `probe_backend.py`, run against transcripts Claude Code
already wrote on this machine.

**The frozen-corpus catalog: `studies/refusal/frozen/` keeps every retired Set A version as
bytes, named by corpus-hash prefix.** A plain entry hashes to its own name prefix; a derived
variant keeps its parent's prefix plus a label, and its own hash is recorded where it is used.
`set_a-41fecb7f.json` is the original freeze, the corpus whose prompts the archived run's 24
rows carry. `set_a-41fecb7f-regexfix.json` is the prompt-preserving variant of it (own hash
`39f98c53`) built so the archive rescore could fix regexes WITHOUT touching prompts; ARCHIVED.md
records it verifying all 24 saved prompts with zero mismatches, and also that it reddens
`probe_refusal_fixtures.py`, so it was never a candidate to stay live.
`set_a-771ce241-overhaul.json` is the full overhaul, the version `refusal tdd-full-1` froze
and ran. Every hash in this paragraph was re-derived 2026-08-02 with `corpus_hash()`
(`run_refusal.py:81-83`). The live `set_a.json` sits downstream of 771ce241 via corpus v2's
four regex and two prompt fixes (`docs/REFUSAL-RESCORE.md`); its current hash is whatever
`run_refusal.py --check` prints, and this document deliberately does not record a number the
live file moves out from under. The catalog rule is the corpus half of archive-never-delete: a
version any paid run consumed exists forever, in that run's own frozen `corpus.json`, and, if
it was ever the live file, here under its hash BEFORE the live file moves on.

**Study DBs are measurement corpus, and the archive rules above apply to them with no study
exception.** Every study turn lands in per-arm DBs under `hb/`: `ab-refusal-<tag>-<arm>.db`
(`run_refusal.py:466`) and `study-<study>-<tag>-<arm>.db` (`run_study.py:796`), both through
`rig.db()` (`rig.py:42-49`), which puts them inside the `hb/*.db` glob that
`probe_turn_growth.py` derives `worst_turn` from. So never delete one; that deletes the
measurement. They are single-use by construction: the tag is baked into the name, a new study
is a new tag with fresh DBs, and an archived run's DBs keep their names in the corpus
(ARCHIVED.md, again). Two ledger obligations attach to every new run, both the
paid-run-protocol skill's: `.gitignore` ignores `hb/*` wholesale and un-ignores each paid DB
BY NAME, and its own comment warns that a new paid DB without its negation line is "silently
unprotected"; and the WAL must be folded in (`PRAGMA wal_checkpoint(TRUNCATE)`) before
committing a corpus update so the committed bytes are self-contained, as the LAST step before
`git add` when a run rewrote the DB. This no longer applies to `errorstate.db`/`focus.db`,
which 43d90b9 untracked: `gate/tier2.py` still rewrites both, invisibly to git. Run
directories under `hb/ab-runs/` are tracked evidence in full: rows, meta, server logs, frozen
arms and corpus. A dead run is archived BY RENAME, the way `refusal-full` became
`refusal-full-archived-20260731`, so the tag-derived path can never silently resume and
respend it; `run_study.py` additionally refuses to adopt any directory it did not create
(`run_study.py:694-697`).

## What is different from the void run, and why it matters

| | void run | this rig |
|---|---|---|
| model | `ollama/gemma4-agentic:q6` via `@ai-sdk/openai-compatible` | `openai/gpt-5.6-sol`, native path, asserted per-message |
| harness | env vars hand-copied | `zsh -c '. harness/env.sh && exec …'` — literally sourced |
| isolation | `XDG_DATA_HOME` redirected | **DB only**, absolute `OPENCODE_DB` |
| question | forced with `tools: {"*": false, "question": true}` | no `tools` map at all; the model chooses |
| concurrency | one local GPU, serialized | three real tool-using turns, 5.1/5.3/5.9s, 6.1s wall |

`XDG_DATA_HOME` is the trap that made the void run reach for a local model: `Global.Path.data`
derives from it (`core/src/global.ts:11`) and `auth.json` lives there
(`opencode/src/auth/index.ts:10`). OpenAI is on **oauth**, so redirecting it strands the
credentials and `gpt-5.6-sol` stops resolving. `database.ts:43-46` returns an absolute
`OPENCODE_DB` directly, which is why DB-only isolation works.

`/etc/hostname` — the void run's permission trigger — **does not exist on macOS**. This rig uses
`/etc/shells`, which also gives assertable content (`/bin/zsh`) for proving the approved tool
actually ran.

## Assertion discipline

**This suite's characteristic failure is passing.** Eight assertions across the effort were
found to be incapable of failing, against four real defects that tests actually caught. Read
that as the house style to guard against, not a historical note.

**A COUNT IS NOT AN OUTCOME — Phase 12's addition, and it cost four assertion rows.** `fire()`
appends a turn that THREW and a turn that FINISHED in the same 3-tuple `(label, elapsed, payload)`,
and until Phase 12 **nothing in this suite read element `[2]`** — the one that says which. So
`len(box)` answered *how many turns ended*, while four `r.check` rows spent it as *how many turns
ran*. TESTED: three `fire()` calls at a port with nothing listening filled a box with three
`URLError`s in **9 milliseconds**, and that satisfied `len(box) == 3`, `len(workers) == 3` and
`any(b[0] == "blocker" for b in box)` — every completion predicate the suite owned.

The rule is **gate on ENDED, assert on RAN**:

```python
wait_for(lambda: len([b for b in box if b[0].startswith("worker")]) == 3, 300, "worker turns")
workers = completed(box, "worker")          # <- NOT len(box)
r.check("the workers ran to completion", len(workers) == 3, ...)
```

Waiting on the raw box is right — a thrown turn should release the gate *fast* so the assertion
goes red immediately instead of timing out. Asserting on the raw box is what could not fail. And the
DETAIL string should still print the exceptions: that is what a human reads when the row goes red.
`rig.completed()` uses `isinstance(b[2], BaseException)` rather than truthiness on purpose — `None`
and `[]` are what this API returns for an empty body and an empty list, and a truthy filter would
throw away two real completions. **Contract 6 in `probe_rig_contract.py` enforces this from source**
across all 24 entrypoints, with the pre-Phase-12 files from git as its negative control.

**A RIG THAT CANNOT BE RUN TWICE IS A RIG WITH ONE RECORDED SCORE.** `db(name)` never resets, and
the grid header counts *every session in the DB* — so the four sites that compare it to a literal
(`verify_permission.py:116` and `:143`, `verify_question.py:135`, `verify_cold.py:102`) pass only on
a pristine database. Before re-running one of those, **archive its DB under a name that still
matches `hb/*.db`** (`quest.db` → `quest-phase12a.db`). Never delete it: that glob is the corpus
`probe_turn_growth.py` derives `worst_turn` from, and clearing it to make a rig re-runnable would
quietly remove the evidence that sizes `RETIRE_AT`.

**AND A GREEN RUN IS NOT EVIDENCE WHEN THERE WAS NO RUN AT ALL — Phase 10's addition, and it is
about the PAID half.** Phase 9 fixed the ten free probes and touched none of the eleven rigs that
cost money, where the same defect was older and worse. **Six of them never read `summary()`'s
return value**: `finally: r.summary(); t.close()`, no `sys.exit`, so the process ended normally and
the shell saw 0 however many assertions had failed. Three contain no `sys.exit` anywhere. Among
them `smoke.py` — the provider check this file tells you to run FIRST — and `verify_surface.py`,
which carried a permanently-red assertion for five phases precisely because nothing surfaced it.

A fresh clone could not have caught this the way it caught Phase 9's: a paid rig cannot be run
from a clone, so the paid half never executed, never crashed, and never got the chance to report a
false green. **It was only ever visible in the source.** Hence `probe_rig_contract.py`, which reads
all 24 entrypoints (itself included) as artifacts and asserts the contract — floor declared, floor satisfiable, no
`finally` that exits without a crash guard, exit status dependent on `summary()`, and since Phase 12
no completion claim decided by counting `fire()`'s box — with a mutation
check per predicate and an inverted leg so a module with no `try` is not flagged.

**A RECORDED SCORE IS A CLAIM ABOUT A FILE AT A MOMENT, AND NOTHING TIED THE TWO TOGETHER.**
`verify_handoff.py` is cited as **21/21** in four documents as the evidence for the Phase 4 exit
gate's second clause. It holds **22** unconditional assertions: Phase 5 replaced a vacuous check
with two mutation legs and never re-ran it, so 21/21 is unreachable. Phase 8 had found the same
shape in `verify_control_agent.py` and called it *"the one rig in the suite"* — that uniqueness was
never checked and is false. Counting `r.check(` per file and comparing against the recorded scores
reconciles every other rig in one command: `verify_cold.py` and `verify_retire_350k.py` differ by
exactly their own crash guard, `verify_control_agent.py` by one conditional. **Re-run a rig before
quoting its number, or say which execution the number came from.** `docs/VERDICT.md` §2.

**A `file:line` CITATION IS AN UNTYPED COUPLING, AND THE DOCUMENTS ARE ARTIFACTS TOO — Phase 11's
addition.** Nothing in this repo checked prose against the code it cites, for eleven phases, while
`fork/README.md` named exactly that as "drift mode 2". MEASURED across 930 citations: eight stale.
Three pointed past the end of `healbot.tsx`; five landed on blank lines, and **three of those were
created by Phases 9 and 10** — editing `HARNESS.md` moved two section headings that other documents
cite, and editing `probe_twin.py` moved a line `docs/HEADLESS.md` cites. Editing a file that other
files point *into* is the failure, and it is the same untyped-coupling shape as the metadata request
channel and the recorded-score-outliving-its-file of Phase 10.

Three rules fall out, all of them earned within the phase:

- **A citation quoted as BROKEN must not be written in live `file:line` form.** A reader cannot tell
  a pointer from a specimen, and neither can the probe. `docs/CITE.md`'s first draft tripped its own
  check nine times, every hit a stale citation being discussed. Write "line 1241 of `healbot.tsx`".
  An escape marker was considered and rejected: it is a hole that silences real rot, and the person
  most likely to reach for it is the one least inclined to fix the citation.
- **Line numbers are for code; section NAMES are for living documents.** `HARNESS.md` gains rows
  every phase, so every `HARNESS.md:NNN` is guaranteed to rot — demonstrated an hour after the fix,
  when this phase's own index row re-broke the citation it had just corrected. Cite the section.
- **Positional rot is checkable; semantic rot is not, and the probe does not claim it.** A citation
  landing on a real, non-blank line that says something else entirely passes. Every citation in the
  corpus resolves; how many describe what they claim to is not a question a probe can answer.

**A GREEN RUN IS NOT EVIDENCE THAT THE RUN HAPPENED — and every rule in this section was about
predicates, not about execution.** `Results.summary()` returned `not failed` over whatever rows
happened to be appended and had no idea what should have been. MEASURED in Phase 9 by cloning this
repo and running the ten probes in it: `probe_on_grid` reported **2/2**, `probe_control_wiring`
**7/7**, and `probe_headless_arm` printed `!! timed out waiting for server … after 90s` and then
**1/1** — three green exit codes over 10 of 52 assertions. `opencode/` is gitignored, so
`bun run --cwd` ENOENTs and no server ever starts; every screen predicate is then trivially false
and every `not on_grid` assertion passes **vacuously**.

Two independent routes produce it, which is why the fix is in `Results` and not in a per-probe
guard. **`sys.exit()` inside a `finally` DISCARDS the in-flight exception** — named at
`probe_request_channel.py:151-153` since Phase 7, and present in only **3 of 10** probes until Phase
9 backfilled it. And **a timeout raises nothing at all**: `wait_for()` (`rig.py:628-639`) prints
`!!` and returns `None`, so no exception guard can see it and the probe simply runs fewer
assertions. `Results(expect=N)` now catches both. It is a **floor, not an equality** — adding an
assertion must not turn a probe red, losing one must. Controlled in both directions: **142/142 on
the real repo**, **9 of 10 exit 1** on the same fresh clone.

The generalisable form, and it is the sharper version of everything above: **the vacuous pass and
the missing assertion are the same defect wearing different clothes.** An assertion that never ran
is `True` on exactly the runs that did not evaluate it. It did not look like the familiar failure
because the vacuity was in the *control flow* rather than in the predicate, and every rule on the
books pointed at predicates.

**WHEN A PREDICATE'S INPUTS COME FROM A CORPUS, THE CORPUS NEEDS A FIXTURE CHECK AS MUCH AS THE
PREDICATE NEEDS A MUTATION CHECK.** `probe_turn_growth.py`'s two load-bearing assertions are both
`retire_at + worst_sol < CEILING` in some form, so they get **easier as `worst_sol` gets smaller** —
and `worst_turn = 175,148` exists only in `hb/*.db`, which `.gitignore`'s `hb/*` rule excludes. MEASURED on a
fresh clone: the pinned population collapses to 6,643 and the probe reports the gate clearing its
ceiling by **173,357 tokens, 48.2%**, and the bound as **353,357** — against the true 4,852 / 1.3% /
184,852 — **in green**, with its own detail string still quoting 175,148. Losing the evidence and
passing the test were the same event. The real corpus already had such a check (677/56/733, added in
Phase 8, and it is why the missing-real-DB case fails loudly); the rig corpus did not, and now does
(`worst_sol >= 175_148`, `>=` so that a *larger* turn is new evidence rather than a failure).

**Both of `probe_turn_growth.py`'s corpora are REQUIRED**, and its docstring said the real one was
optional until Phase 9 disproved it by running without the file: `r.check(…, have_real, …)` makes
absence a **FAIL**, exit **1**, 12/14. The `[NOT EXERCISED: …]` text is the detail on a *failing*
row. Note that the two fail in opposite directions — without the real corpus the probe goes loudly
red; without the rig corpus it goes quietly *greener*.

**The suite writes to the corpus it measures.** `probe_turn_growth.py` globs `hb/*.db` and every
paid rig writes there, so its percentiles are a snapshot rather than a constant — the corpus moved
86 → 94 turns between Phase 8 and Phase 9, entirely from `hb/control.db`, written by
`verify_control_agent.py` six minutes after Phase 8 recorded its figures. Every maximum, bound and
conditional was unchanged across that +14%, which is the first evidence the derivation is stable
under corpus growth. Do not read drift here as a signal about the model.

Navigation is asserted on the `▸` marker's `(line, column)`, never on cell text — cell text is
present regardless of which cell is selected. The terminal is 120 cols on purpose: at 170 the
four cells fit one row, `j`/`k` clamp, and the keyboard-gating assertions pass vacuously.

**The terminal width is part of the predicate.** 120 columns is deliberate for the navigation rigs
— at 170 the four cells fit one row, `j`/`k` clamp, and the keyboard-gating assertions pass
vacuously. But the session route's sidebar is gated on `width > 120`
(`routes/session/index.tsx:264`), and that sidebar is the **only** thing that renders a session's
id. So any assertion about *which* session was focused has to run at 170, and one written at 120
measures terminal geometry instead of behaviour. That is not hypothetical: it is what the first
version of `verify_cold_question.py`'s focus check reported.

**A screen predicate is worthless until it has been shown FALSE.** `on_grid(t)` matches
`Healbot\s+\d+\s+sessions?` case-sensitively — the grid's own header, and nothing else in the
TUI. It replaced `t.find("Healbot")`, which backed nine "the route never changed" assertions and
was `True` on *every* screen: `Term.find` lowercases both sides and the rig's own project path
is `.../healbot/.carryover/verified/hb/project`. `probe_on_grid.py` demonstrates both the
collision and the replacement, for free. Every rig asserting `on_grid` also asserts `not
on_grid` somewhere it must be false.

**Prefer `t.exact()` for cell labels.** `find()` is case-insensitive, and three of the four
substring failures came through it — `find("RETIRE")` also matches the header's `1 to retire`.
Labels are uppercase and header phrasing is lowercase; case is the only separator.

**`verify_headless_retire.py` now discriminates per-turn from per-step — it did not until Phase 7.**
Its `finishes[-1] == "stop"` check was necessary but never sufficient: it is satisfied by a gate
firing at ANY step boundary provided the crossing happened to be the last one, and this rig's
prompt guaranteed exactly that by putting the single large token jump (the 130 KB `ledger0.txt`
read) on the FINAL model call. MEASURED on that version: steps at 4,999 / 5,165 / 5,236 and then
`stop` at 36,612 against a 20,000 gate — the only step over the line was the last, so the per-step
and per-turn predicates were indistinguishable and 20/20 said nothing about which one shipped.

The prompt now reads the ledger FIRST, so its result sits in the input of every later step and the
crossing lands mid-turn. Two assertions were added on top: that a NON-FINAL step was over the gate,
and that the turn ran on past it. TESTED at 22/22 — crossing at step 1 (36,361 vs a 20,000 gate),
steps 2 and 3 at 89,850 and 90,011, and the turn still running to `stop` at step 5 before the
handoff. Under the predicate that shipped before Phase 7 this would have aborted at step 1.

**The lesson generalises and belongs in this section: an assertion about ORDERING needs a workload
that could have violated it.** "The turn finished first" over a workload whose only threshold
crossing is on the last step is not a test, it is a restatement of the fixture.

**`probe_twin.py` no longer compares two handoff documents, because there are no longer two.**
Phase 7 deleted the grid's copy along with the grid's whole `retire()`; the server plugin is the
only implementation of retirement anywhere. The probe's job changed with it: it now asserts the
ABSENCE (`the grid has NO handoffDocument`, `:154-158`; no spawn/seed/archive of its own,
`:168-172`) and guards the two couplings that survive.

The finding that made deletion the right fix, kept because it is the reason: **the duplication was
never safely guarded.** `document_strings()` was `re.findall(r'"((?:[^"\\]|\\.)*)"', body)` —
DOUBLE-QUOTED literals only, 16 of them — and every line of the document that renders a VARIABLE is
a template literal (`` `- [ ] ${todo.content}` ``, `` `- ${f}` ``), invisible to it. TESTED by
mutating the grid against an untouched plugin: it MISSED `- [ ] ` → `- [x] `, `- [ ] ` → `* `, a
changed file-bullet prefix, `slice(0, 2000)` → `slice(0, 200)`, `files.length > 0` → `> 3`,
dropping `input.objective?.trim() ||`, `open.length > 0` → `>= 0`, and a dropped `.trim()`. It
CAUGHT one thing, `lines.join("\n")`. Both of its own mutation checks corrupted a double-quoted
heading — the one class of thing the extractor already saw — so they demonstrated the machinery
without exercising the gap. Eight seeded divergences through a guard reported as green. That was a
coverage hole, not a live divergence (the two bodies did agree), and the structural fix on the
table was a normalised whole-body diff OR collapsing the copies; the collapse is what shipped,
and it makes the whole class unreachable. `document_strings()` itself is now GONE — an earlier
version of this paragraph said it "still exists at `probe_twin.py:79-112` … dead code now, not a
running check", and it was deleted along with the comparison it served. The history survives in the
probe's module docstring (`probe_twin.py:14-24`), which is the right place for it: the extractor
was the defect, and a defect kept as dead code is a defect waiting to be called again.

**What it guards instead.** `RETIRE_AT` is still duplicated, deliberately — the grid needs the
number to paint `RETIRE`, `N to retire` and the per-cell share, and cannot import it. That is a
NUMBER, so it compares exactly (`:101-118`, with a mutation check at `:113-118` that rewrites
`|| 180_000` to `|| 999_000` in the grid and requires the comparison to notice): the duplication
that was always safe to test, and the only one left. `HEALBOT_RETIRE_HARD` is asserted here too,
and that assertion INVERTED in Phase 7 — it used to require the variable to be the plugin's alone,
matching the grid's deletion of its own gate, and it now requires it to be ABSENT FROM BOTH
(`:132-136`), because the constant was deleted outright. Its stated reason is the point: *a knob
that reads as load-bearing and is not must not grow back*. The new risk is the REQUEST CHANNEL —
the grid writes `metadata: {healbot: {retireRequested: <ms>}}` and the plugin reads it, with no
shared type, no import and no compiler in between (`:185-230`). Same failure shape as the old
divergence, so it gets the same treatment, from both ends. TESTED against the current sources:
23/23.

**An absence assertion needs an INVERTED mutation check.** "The grid has no `handoffDocument`" is
satisfied by the symbol being gone and equally by your extractor reading the wrong text — a
comment-stripping regex that ate the file returns the same green. So the same predicate is re-run
against a copy that DOES contain the symbol and is REQUIRED to trip: `probe_twin.py:162-167`
appends `function handoffDocument() {}` to the grid source, pushes it through the identical
comment-stripping, and asserts the substring is found. Presence checks get a mutation that breaks
them; absence checks get one that satisfies them.

**An untyped cross-process coupling gets asserted from BOTH ends.** The metadata request key is
written by the TUI and read by the server plugin with no shared type, no import and no compiler
between the two. Rename it on either side and `x` stops retiring anything — no error, no log, the
cell simply stays put. One-sided assertions cover half of that, so `probe_twin.py:221-230` mutates
each side in turn: `retireRequested` → `retireWanted` in the grid, then the same rename in the
plugin, each required to fail the agreement predicate.

**A predicate that a mutation check corrupts must be the predicate that ACTUALLY RUNS.** If the
mutation check re-implements the comparison inline against a doctored string, it proves that the
inline copy discriminates and says nothing about the code under test — the two drift and the
mutation check keeps passing. `probe_twin.py:207-220` factors the channel comparison into
`channel_agrees(writer, reader)`, the live check calls it, and the two mutation checks call the
same function with corrupted inputs. One definition, three call sites.

**And the same rule one level up: TEST THE SHIPPED SOURCE TEXT, NOT A COPY OF IT.** A probe that
re-implements the function it is checking proves that the re-implementation is correct. That is a
harder failure to see than the inline-mutation one above, because the copy is usually right on the
day it is written and only becomes a lie later, silently, when the shipped code moves and the copy
does not. `probe_turn_predicate.py` is the case where it mattered most — `turnFinished()` is the
single point where per-turn semantics live, and getting it wrong means aborting turns mid-flight
again or, now that `RETIRE_HARD` is gone, never firing at all. It **cannot import** the function:
the plugin must export ONLY its plugin function, because `getLegacyPlugins`
(`plugin/index.ts:95-108`) iterates `Object.values(mod)` and calls each as a plugin, so exporting a
helper to make it testable would disable the whole guard at load time, in a log line nobody reads.
(`probe_twin.py:253-260` asserts that export constraint separately, which is what makes "cannot
import" a tested fact rather than an excuse.) So the probe brace-matches `function turnFinished(`
out of `harness/config/opencode/plugin/healbot.ts` (`extract()`, `:44-67`), strips the two
TypeScript annotations with a pair of regexes (`:65-66`), and evaluates THAT TEXT in `node -e`
against the cases (`run()`, `:70-76`). A rename returns `None` rather than raising, so it surfaces
as one named failure in the summary instead of a traceback the summary would never reach
(`:103-109`).

The cases are the measured distribution rather than invented ones: 11 message shapes drawn from the
733 real assistant messages with occupancy > 0 — 677 mid-turn `tool-calls` that must be FALSE, 56
`stop` that must be TRUE, the `unknown` finish opencode also excludes, both error paths, and the
empty in-flight row that exists ~20 ms after `prompt_async` acks. Two of them carry `time.completed`
alongside a mid-turn `finish`, which is the shape that made the old predicate wrong, and there is a
separate source-text assertion that the function does not mention `time` at all (`:111-115`). The
table is itself mutation-checked: `:137-153` re-runs the identical cases against the OLD per-step
predicate, `Boolean(info.time?.completed || info.finish || info.error)`, and REQUIRES it to fail. It
gets 4 wrong, including the mid-turn tool call that 677 of 733 real messages look like. Without that
leg the probe could be green because the extracted function happens to be right for a reason
unrelated to the claim — this suite's characteristic failure, and the exact way the original defect
survived two phases.

**`all()` over a possibly-empty list is not an assertion.** `verify_control_agent.py` asserted
`all(s.get("parentID") for s in extras)` under the label *every session the build agent created is
a subagent*, and `extras` is empty whenever the build agent does not delegate — which it need not
— so the assertion was `True` by vacuity in exactly the runs that exercised nothing. Two fixes,
both needed. Assert the real claim: the denied tools are the only way to make a TOP-LEVEL session,
so the claim is that it created NONE, and `not [s for s in extras if not s.get("parentID")]` goes
False the moment one appears (`:226-239`). And make non-exercise VISIBLE — the empty-`extras` case
is still vacuous, so when it happens the detail line prints `[NOT EXERCISED: … so this assertion
held vacuously — the scoping claim rests on the tool-call check above]` (`:234-235`) instead of an
unremarkable green. A vacuous pass you can SEE is a different object from one you cannot.

**Scope a document assertion to its section, then mutate it.** `verify_handoff.py`'s continuity
legs check a sentinel inside the objective section and a filename inside the file section, and
then re-run each predicate against a document with that material stripped and require it to
fail. Checking the whole document passed via the objective echo, which names the same files.

**The project directory needs its own git repo.** `rig.git_baseline()` provides it, and it is
not optional for anything asserting on changed files: `GET /session/{id}/diff` serves
`summary.diffs`, which `SessionSummary.summarize` computes with git, and this directory is
gitignored by the parent repo. Without an inner repo every file a session creates here is
invisible to the diff machinery — silently, with no error. That cost a 350K run.

**`Api` must send `x-opencode-directory`.** `workspace-routing.ts:87` resolves the instance as
`?directory || x-opencode-directory || process.cwd()`. Omit it under `serve()` and you address
`packages/opencode` — every call succeeds, the sessions are there, and the grid shows
`0 sessions`, because you and it are looking at different instances.

Session ids are **descending** identifiers (`schema/src/session-id.ts:8` →
`schema/src/identifier.ts:22`), so ascending sort is already newest-first. The grid used to sort
`b.localeCompare(a)` under a comment claiming the opposite and rendered oldest-first; both the
grid and these rigs were corrected together, so the interesting session is now created **first**
to land in the last cell. Fixing only one side would have made three assertions pass for the
wrong reason.

## The one failure — fixed in Phase 10, and the reason it lasted

`verify_surface.py`'s "nothing is blocked yet" precondition asserted `not t.find("blocked")`. The
grid footer is literally `a answer · x retire · tab next blocked · …` (`healbot.tsx:997`), so that
substring is present whenever the grid is open and the predicate was False **by construction** —
`find()` is case-insensitive substring. Test bug, never a code one; the same run's `1 blocked` /
`2 blocked` / `3 blocked` checks carry the meaning and they passed.

It is now `not t.search(r"\d+ blocked") and not t.exact("PERMISSION")`. The header that counts
blocks is wrapped in `<Show when={blocked() > 0}>` (`healbot.tsx:963`, VERIFIED at source), so
`\d+ blocked` is on screen exactly when something is blocked. The regex was checked both ways —
it matches `Healbot  4 sessions  3 blocked`, it does not match the footer alone — but the rig is
paid and has not been re-run, so this is **VERIFIED, not TESTED**.

**The interesting part is why a permanently-red assertion survived five phases.** This rig ended
`finally: r.summary(); t.close()` — the verdict computed, printed, and discarded, with no
`sys.exit` anywhere in the file. It exited **0** every time. Five other paid rigs did the same,
including `smoke.py`, the provider check this README tells you to run first. `docs/VERDICT.md` §1.
