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

# these spend credits
venv/bin/python smoke.py             # 6/6   provider/model/config sanity — run this first
venv/bin/python verify_permission.py # 40/40 the exit-gate permission clause at N=4
venv/bin/python verify_question.py   # 27/27 the question clause, UNFORCED
venv/bin/python verify_surface.py    # 17/18 auto-surface, suppression, tab cycling
venv/bin/python verify_retire.py     # 17/17 the retirement observable and threshold
venv/bin/python verify_handoff.py    # 21/21 retire and hand off with continuity intact
venv/bin/python verify_cold.py       # 21/21 the COLD-START reconcile, via serve + attach
venv/bin/python verify_auto_retire.py # 13/13 AUTOMATIC retirement: the gate fires by itself,
                                     #       the turn finishes, no turn runs after it
venv/bin/python verify_retire_350k.py# 25/25 retirement at a full-scale threshold.
                                     #       ~5M cumulative input tokens; run it deliberately
```

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
