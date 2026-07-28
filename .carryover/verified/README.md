# Verified rig — the redo that counts

Supersedes `../verify*.py`, which are void (local model, forced question path). These ran on
`openai/gpt-5.6-sol` through the real harness. 90/91 assertions passed; the one failure was a
bug in the test, not the code (see below).

```sh
python3 -m venv venv && venv/bin/pip install pyte

# free — no model turns, no API credits.
# FREE TO RE-RUN, not free to run the FIRST time: all but probe_turn_predicate.py need the
# gitignored opencode/ checkout (rebuild from fork/README.md), and probe_error_state.py,
# probe_focus.py and probe_turn_growth.py need hb/*.db, which only the PAID rigs below can
# create. On a fresh clone this suite does not run — see docs/CLONE.md.
venv/bin/python probe_on_grid.py     # 4/4   does the route predicate actually discriminate?
venv/bin/python probe_fleet.py       # 10/10 does harness/fleet.sh do what it claims?
venv/bin/python probe_error_state.py # 10/10 does a hard-errored session render ERROR?
                                     #       (replays the 350K run's real overflow DB)
venv/bin/python probe_focus.py       # 24/24 does `enter` open the SELECTED session? (same DB)
venv/bin/python probe_twin.py        # 23/23 is there still exactly ONE implementation of
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
venv/bin/python probe_control_wiring.py # 14/14 are the control tools and agent registered?
venv/bin/python probe_turn_growth.py # 16/16 is ~170K the TAIL or the MIDDLE of single-turn growth?
                                     #       Re-derives the `worst_turn` that SIZES RETIRE_AT from
                                     #       every session DB on disk instead of the one turn it
                                     #       rested on. Runs the SHIPPED turnFinished() and
                                     #       occupancyOf() in node; negative control regroups the
                                     #       same corpus with the OLD per-step predicate

# these spend credits
venv/bin/python smoke.py             # 6/6   provider/model/config sanity — run this first
venv/bin/python verify_permission.py # 40/40 the exit-gate permission clause at N=4
venv/bin/python verify_question.py   # 27/27 the question clause, UNFORCED
venv/bin/python verify_surface.py    # 17/18 auto-surface, suppression, tab cycling
venv/bin/python verify_retire.py     # 17/17 the retirement observable and threshold
venv/bin/python verify_handoff.py    # 21/21 retire and hand off with continuity intact
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
(`harness/config/opencode/plugin/healbot.ts:346-349`) is now opencode's own, from `prompt.ts:1295`:
`if (info.error) return true; return Boolean(info.finish && !["tool-calls","unknown"].includes(info.finish))`.
It deliberately does not read `time.completed`. `consider()`'s parameter is `turnOver` and its
guard is a plain `if (!turnOver) return` (`:612`, `:622`). **Nothing is aborted on the gate path** —
`retire()` still calls `POST /abort` (`:473`, under the comment at `:458-472`), but on this path it
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
~170K is the **tail** (p50 is 22,152), it just is not the **maximum**, which is what the derivation
used it as. **And the threshold is MODEL-SPECIFIC**: the corpus holds a **223,258** turn on
`gpt-5.6-terra`, which at 180,000 lands at 403,258 and dies — so the number is verified only while
`opencode.jsonc:16` pins `gpt-5.6-sol`, and the probe asserts that pin. `docs/GROWTH.md` §1.

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
9 backfilled it. And **a timeout raises nothing at all**: `wait_for()` (`rig.py:259-270`) prints
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
and `worst_turn = 175,148` exists only in `hb/*.db`, which `.gitignore:13` excludes. MEASURED on a
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
`identifier.ts:22`), so ascending sort is already newest-first. The grid used to sort
`b.localeCompare(a)` under a comment claiming the opposite and rendered oldest-first; both the
grid and these rigs were corrected together, so the interesting session is now created **first**
to land in the last cell. Fixing only one side would have made three assertions pass for the
wrong reason.

## The one failure

`verify_surface.py`'s "nothing is blocked yet" precondition asserts `not t.find("blocked")`.
The grid footer is literally `a answer · tab next blocked · …` (`healbot.tsx:464`), so that
substring is always present while the grid is open. Test bug; the same run's `1 blocked` /
`2 blocked` / `3 blocked` checks are the ones that carry the meaning, and they passed.
