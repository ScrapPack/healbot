# Verified rig — the redo that counts

Supersedes `../verify*.py`, which are void (local model, forced question path). These ran on
`openai/gpt-5.6-sol` through the real harness. 90/91 assertions passed; the one failure was a
bug in the test, not the code (see below).

```sh
python3 -m venv venv && venv/bin/pip install pyte
venv/bin/python smoke.py             # 6/6   provider/model/config sanity — run this first
venv/bin/python verify_permission.py # 40/40 the exit-gate permission clause at N=4
venv/bin/python verify_question.py   # 27/27 the question clause, UNFORCED
venv/bin/python verify_surface.py    # 17/18 auto-surface, suppression, tab cycling
```

`rig.py` needs `hb/project/` beside it with `worker0.txt`..`worker2.txt` containing
`payload-0`..`payload-2`, and a writable `hb/` for the isolated DBs.

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

Navigation is asserted on the `▸` marker's `(line, column)`, never on cell text — cell text is
present regardless of which cell is selected. The terminal is 120 cols on purpose: at 170 the
four cells fit one row, `j`/`k` clamp, and the keyboard-gating assertions pass vacuously.

Session ids are **descending** identifiers (`schema/src/session-id.ts:8` →
`identifier.ts:22`), so the grid's `sort((a,b) => b.id.localeCompare(a.id))` renders
**oldest first**. The blocker is therefore created **last** so it lands away from the initial
cursor; create it first and `tab`/`a` assertions pass for the wrong reason.

## The one failure

`verify_surface.py`'s "nothing is blocked yet" precondition asserts `not t.find("blocked")`.
The grid footer is literally `a answer · tab next blocked · …` (`healbot.tsx:464`), so that
substring is always present while the grid is open. Test bug; the same run's `1 blocked` /
`2 blocked` / `3 blocked` checks are the ones that carry the meaning, and they passed.
