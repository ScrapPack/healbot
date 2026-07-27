# Verified rig — the redo that counts

Supersedes `../verify*.py`, which are void (local model, forced question path). These ran on
`openai/gpt-5.6-sol` through the real harness. 90/91 assertions passed; the one failure was a
bug in the test, not the code (see below).

```sh
python3 -m venv venv && venv/bin/pip install pyte

# free — no model turns, no API credits
venv/bin/python probe_on_grid.py     # 4/4   does the route predicate actually discriminate?
venv/bin/python probe_fleet.py       # 10/10 does harness/fleet.sh do what it claims?
venv/bin/python probe_error_state.py # 10/10 does a hard-errored session render ERROR?
                                     #       (replays the 350K run's real overflow DB)
venv/bin/python probe_focus.py       # 24/24 does `enter` open the SELECTED session? (same DB)
venv/bin/python probe_twin.py        # 23/23 is there still exactly ONE implementation of
                                     #       retirement, and does the untyped request channel
                                     #       agree at both ends? (NOT a document comparison any
                                     #       more — see below)
venv/bin/python probe_headless_arm.py# 15/15 does the retirement guard arm with NOTHING rendering
                                     #       — including at the SHIPPED 256,000 default, with no
                                     #       override anywhere?
venv/bin/python probe_request_channel.py # 9/9 does `x`'s metadata write actually reach the server
                                     #       and retire THAT session and no other? (real server,
                                     #       no model turn — an empty session has no todos, so
                                     #       retire() takes its no-successor branch)
venv/bin/python probe_control_wiring.py # 14/14 are the control tools and agent registered?

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
venv/bin/python verify_headless_retire.py # 20/20 automatic retirement with NO TUI ANYWHERE.
                                     #       Runs at a HARDCODED 20,000 and cannot be pointed at
                                     #       256,000 — there is no override to remove; see below
venv/bin/python verify_control_agent.py   # 15/16 the control agent's tools, and the scoping that
                                     #       keeps them out of every other session's prompt
venv/bin/python verify_retire_350k.py# 25/25 retirement at a full-scale threshold.
                                     #       ~5M cumulative input tokens; run it deliberately —
                                     #       and read its docstring first, the 25/25 predates
                                     #       both the 256,000 default and server-side retirement
```

**Since Phase 6 the SERVER enforces the retirement thresholds, not the client.** Automatic
retirement is a server plugin (`harness/config/opencode/plugin/healbot.ts`), so a rig that sets
`HEALBOT_RETIRE_AT` in its own environment before `attach()` is configuring the wrong process.
`rig.serve(..., env_extra={...})` is how you reach the server; `rig.serve(..., log=path)` is how you
read what it did, and it matters because the plugin's log line is often the only independent
evidence that the thing under test actually happened. Under `boot()` the TUI hosts the server
in-process, so the ambient environment still reaches it — which is why `probe_error_state.py` and
`probe_focus.py` can still disarm the gate with `os.environ["HEALBOT_AUTO_RETIRE"] = "0"`.

**`verify_headless_retire.py` cannot be pointed at 256,000, and "just remove the override" is not
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

**What is unbought at 256,000 is narrower than "the 256K gate has never been exercised".** Split it
in two and only one half costs money. (a) WHICH CONSTANT ARMS is a fact about config resolution and
it is now TESTED, free, in `probe_headless_arm.py:180-195` — a third server started with
`env_extra={}` and no `HEALBOT_RETIRE_AT` anywhere, asserted to log `soft 256,000` and
`hard 330,000`. It is deliberately paired with the pre-existing negative at `:120-124`, which
requires that same string to be ABSENT when an override IS supplied: one string asserted both ways
in one run, so neither can be passing for a trivial reason. (b) WHETHER A SESSION DRIVEN TO 256,000
RETIRES is still TESTED at 20,000 only, and threshold-independent by inspection — the gate is one
`>=` against a variable. The vehicle that would buy (b) is `verify_retire_350k.py`'s growth loop
(`MAX_TURNS = 70` at `:82`, `CHUNK_BYTES = 35_000` at `:83`, and it already
`os.environ.pop("HEALBOT_RETIRE_AT", None)` at `:90`) retargeted to 256,000. Costing, preserved:
**~$4.50, range $3-9, ~8-15 min wall** — ~27 turns at the recorded 9.46K/turn, cumulative context
scaling N(N+1)/2, so (27×28)/(37×38) = 0.538 of the 350K run's ~5M tokens ≈ 2.7M: 0.27M cache_write
at $6.25/M = $1.69, 2.43M cache_read at $0.50/M = $1.22, 54K output at $30/M = $1.62. Load-bearing
to that number: 256,000 stays UNDER the provider's 272,000 context tier, which DOUBLES every rate,
so base rates hold throughout — the 350K run crossed into the 2× tier for its last ~8 turns. NOT
BOUGHT.

**`verify_control_agent.py` reports 15/16 and that is the recorded result.** The one failure was a
mis-specified assertion — it counted the build agent's `@general` subagent, which `task`
legitimately creates. The first correction, *every session the build agent created is a subagent*,
was itself unsound: `all()` over a possibly-empty list, and that list is empty whenever the build
agent does not delegate. Phase 7 restated it as the claim actually at stake — *it created NO
top-level session* — and made non-exercise print itself (`:226-236`; see the bullet in **Assertion
discipline**). The predicate was evaluated against the run's persisted database and is True where
the original was False, but the file has NOT been re-executed end to end since either correction.

**The gate fires per STEP, not per turn, and that changes what a retirement rig is observing.**
`processor.ts:443-445` assigns `finish` and `tokens` in the SAME mutation at every `step-finish`,
and `:445` is the only site in the session tree that writes a non-zero `tokens` — so every
`message.updated` that carries occupancy at all also carries a set `finish`, usually
`"tool-calls"`, i.e. mid-turn. MEASURED across 733 real assistant messages with occupancy > 0:
zero had a null `finish` (677 `tool-calls`, 56 `stop`). The consequence for these rigs is that
"the turn finished, then it retired" is not what happens — the turn in flight IS aborted, and
overshoot past the gate is bounded by one STEP (~65K measured) rather than one whole turn (~170K
measured). Better than what was designed, arrived at by accident. An assertion written on the
turn-boundary belief is measuring the wrong thing. Two knock-ons worth knowing before writing
another retirement rig: `RETIRE_HARD` (330,000) is INERT, because its only consumer is
`consider()`'s `if (!stepOver && !hard) return` and `stepOver` was true on 733/733, so
`HEALBOT_RETIRE_HARD` is a knob with no effect — kept in the code, and load-bearing again the day
the predicate becomes per-turn. And the hinge is one function: the plugin's `stepFinished()`
versus opencode's own per-turn predicate at `prompt.ts:1295`
(`finish && !["tool-calls","unknown"].includes(finish)`). Unchanged by any of this: the ~360K
ceiling, the 256,000 default, and the handoff document.

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

**`verify_headless_retire.py:201-205` is an assertion that has never discriminated.** It asserts
`finishes[-1] == "stop"` under the label *the turn was allowed to FINISH before the handoff*. It
passes, but not for that reason: the rig's prompt puts the single large token jump — the 130 KB
`ledger0.txt` read — on the final model call, so the gate crossing lands on the last step **by
construction**. Move the jump earlier and the last finish is `"tool-calls"` and it fails, with
nothing about the gate having changed. It has never been able to tell per-turn firing from
per-step firing, which is the only thing its label claims. Left in place with the reasoning
recorded above it; the count is unchanged and the printed label is stale.

**`probe_twin.py` no longer compares two handoff documents, because there are no longer two.**
Phase 7 deleted the grid's copy along with the grid's whole `retire()`; the server plugin is the
only implementation of retirement anywhere. The probe's job changed with it: it now asserts the
ABSENCE (`the grid has NO handoffDocument`, `:189-193`; no spawn/seed/archive of its own,
`:203-207`) and guards the two couplings that survive.

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
and it makes the whole class unreachable. `document_strings()` itself still exists at
`probe_twin.py:79-112` with that history in its docstring, but nothing calls it — it is dead code
now, not a running check, and a green from this probe no longer means anything about prose.

**What it guards instead.** `RETIRE_AT` is still duplicated, deliberately — the grid needs the
number to paint `RETIRE`, `N to retire` and the per-cell share, and cannot import it. That is a
NUMBER, so it compares exactly (`:136-153`): the duplication that was always safe to test, and the
only one left. The new risk is the REQUEST CHANNEL — the grid writes
`metadata: {healbot: {retireRequested: <ms>}}` and the plugin reads it, with no shared type, no
import and no compiler in between (`:220-265`). Same failure shape as the old divergence, so it
gets the same treatment, from both ends. TESTED against the current sources: 23/23.

**An absence assertion needs an INVERTED mutation check.** "The grid has no `handoffDocument`" is
satisfied by the symbol being gone and equally by your extractor reading the wrong text — a
comment-stripping regex that ate the file returns the same green. So the same predicate is re-run
against a copy that DOES contain the symbol and is REQUIRED to trip: `probe_twin.py:197-202`
appends `function handoffDocument() {}` to the grid source, pushes it through the identical
comment-stripping, and asserts the substring is found. Presence checks get a mutation that breaks
them; absence checks get one that satisfies them.

**An untyped cross-process coupling gets asserted from BOTH ends.** The metadata request key is
written by the TUI and read by the server plugin with no shared type, no import and no compiler
between the two. Rename it on either side and `x` stops retiring anything — no error, no log, the
cell simply stays put. One-sided assertions cover half of that, so `probe_twin.py:256-265` mutates
each side in turn: `retireRequested` → `retireWanted` in the grid, then the same rename in the
plugin, each required to fail the agreement predicate.

**A predicate that a mutation check corrupts must be the predicate that ACTUALLY RUNS.** If the
mutation check re-implements the comparison inline against a doctored string, it proves that the
inline copy discriminates and says nothing about the code under test — the two drift and the
mutation check keeps passing. `probe_twin.py:242-248` factors the channel comparison into
`channel_agrees(writer, reader)`, the live check calls it, and the two mutation checks call the
same function with corrupted inputs. One definition, three call sites.

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
