# OPERATIONS.md — the command surface

The operator's cheat sheet: every standing command across both machines, with a one-line
*what* and a pointer to the file or doc that owns the full story. This file deliberately
owns **no facts of its own** — numbers, thresholds, and rationale live with their owners
(the prose-copy rule in the citation-hygiene skill); if a row here disagrees with its
pointer, the pointer wins and this row is the bug.

Conventions: commands run from the repo root in **zsh/bash** (macOS/Linux/WSL2) or **Git
Bash in Windows Terminal** (native Windows — `docs/WINDOWS.md`). `VENVPY` means
`.carryover/verified/venv/bin/python` on POSIX, `.carryover/verified/venv/Scripts/python.exe`
on native Windows; `gate/gate.py` and the pre-push hook resolve this themselves.

## Preflight

| Command | What |
|---|---|
| `python3 harness/doctor.py` (`python` on Windows) | What can this machine run? PASS/FAIL/WARN/SKIP rows + a tier summary. Run it first on any new machine, and after changing the toolchain |
| `git config core.hooksPath gate/hooks` | Wire the push gate, once per clone (`gate/GATE.MAP.md`) |

## opencode half

| Command | What |
|---|---|
| `. harness/env.sh && opencode` | One TUI session under the harness: model pin, compaction off, skill/claude-code switches. env.sh's own comments are the rationale record |
| `harness/fleet.sh [project-dir] [port]` | The fleet shape: one detached `opencode serve` + the control terminal as a client; sessions survive the terminal. Default port 4096; reattach with the same command. Resolves the fork checkout itself and warns when it falls back to a released binary — which has no `/healbot` |
| `HEALBOT_OPENCODE='<launch cmd>'` / `HEALBOT_PORT` | Override what `fleet.sh` launches / its default port. Both optional; the derived branches are the supported paths (`harness/fleet.sh`, "WHICH opencode") |
| `pkill -f "serve --port 4096"` | Stop that server (fleet.sh prints this and the log path on exit) |
| `/healbot` (inside the TUI) | The control grid — fork-only; the installed opencode binary does not have it, and fleet.sh warns when it falls back |
| `HEALBOT_RETIRE_AT=20000 harness/fleet.sh …` | Exercise retirement cheaply. The default 180,000 and its derivation live in `harness/env.sh`; the threshold is read by the **server** process |
| `HARNESS_TRIM_TOOLS=1` | Opt into tool-description trimming (`harness/config/opencode/plugin/trim-tools.ts`) |

## Claude Code half

| Command | What |
|---|---|
| `. harness/env.claude.sh && claude` | Isolated config root (`harness/claude/`), model pin `opus`, compaction off. First use on a machine: sign in once interactively (env.claude.sh header) |
| `claude --resume <sid>` | Resume a crewmate — only from a shell that sourced env.claude.sh, or it looks in the wrong config root |

## Crew fleet (macOS / WSL2 — tmux)

`harness/hb-fleet.sh <cmd>`; selectors are environment (`HB_RUN`, `HB_SOCKET`), never flags.
The captain/crewmate contract is the firstmate skill; mechanics and guardrails are the
script's own header and `docs/SHIP.md`.

| Command | What |
|---|---|
| `hb-fleet.sh start [--no-nvim] [--no-grid]` | **The verb.** Preflight, then `up` with the optional panes detected rather than flagged, then attach. Idempotent: re-running on a live fleet reattaches |
| `hb-fleet.sh help` | The command card + cockpit key map. Same text as `C-b ?` in the cockpit and the bridge pane's banner — the script header is the single owner |
| `hb-fleet.sh preflight` | Can this machine run a fleet right now? Auth, tmux (and whether it has `display-popup`), nvim, checkout+bun, rig venv. Blockers exit 2; advisories only cost an optional pane |
| `hb-fleet.sh up [--nvim] [--grid]` | Bring the fleet session up (idempotent); `--grid` adds a fleet.sh viewport pane |
| `hb-fleet.sh spawn <name> --dir DIR [--model M] [--brief FILE] [--slot]` | One crewmate; `--slot` leases a pool worktree (`harness/pool.py`, Mac-only) |
| `hb-fleet.sh ls` / `state [name]` | Census (manifest × live panes) / per-crew liveness + hook channel + screen read |
| `hb-fleet.sh send <name> <text> [--force]` / `brief <name> <file>` | One line into a crewmate / a multi-line brief via bracketed paste |
| `hb-fleet.sh peek <name> [lines]` / `occupancy <name>` | Screen tail / live context occupancy from the transcript |
| `hb-fleet.sh attach` / `kill <name>` / `down` | Attach the control terminal / kill one pane / kill the session (transcripts survive) |

## The gate

Exit codes are the interface: **0 pass · 2 blocked · 3 error** (`gate/GATE.MAP.md`).

| Command | What |
|---|---|
| `$VENVPY gate/gate.py` | Tier 1 + scoped lint + banned filenames, on the working tree (~1s) |
| `$VENVPY gate/gate.py --base main` / `--quiet` | Gate a range / verdict lines only |
| `git push` | Runs the gate via the pre-push hook, then the advisory model review, then spawns the evidence publisher. `--no-verify` ships unverified commits — say so wherever that push is discussed |
| `HEALBOT_REVIEW=off\|advisory\|blocking` | Review stage modes; `HEALBOT_PUBLISH=off` skips evidence publishing |
| `$VENVPY gate/tier2.py` (`--list` to enumerate) | The rest of the free suite — **phase boundaries only**, triggered by the phase-close skill. Trap on record: tier2 boots probes that REWRITE `errorstate.db`/`focus.db`, so WAL-checkpoint those **after** a tier2 run, never before |

## Rig and corpus (macOS / WSL2)

| Command | What |
|---|---|
| `cd .carryover/verified && for p in probe_*.py; do venv/bin/python "$p"; echo "$p exit=$?"; done` | The free suite; every probe declares and prints its own floor. Fresh-clone expectations: `docs/CLONE.md` |
| `venv/bin/python probe_citations.py` (from `.carryover/verified`) | The citation sweep alone — run before editing any doc with `file:line` citations (citation-hygiene skill) |
| `sqlite3 <db> 'PRAGMA wal_checkpoint(TRUNCATE);'` | Before committing a corpus DB update, fold its WAL in so the tracked bytes are self-contained (`.gitignore`'s corpus block) — and remember the tier2 ordering trap above |
| — | A NEW paid DB needs its own negation line in `.gitignore` or it is silently unprotected (the file says so at the corpus block) |
| `bash harness/backup-opencode-db.sh` | Snapshot the LIVE opencode DB by hand; the scheduled install is `bash harness/install-db-backup.sh` (macOS launchd, renders the plist's `__HOME__`). PC recipe: `docs/WINDOWS.md` |
| Paid rigs (`verify_*.py`), studies, smoke | **Ask first, every time** — the paid-run-protocol skill owns costing, corpus freeze, and accounting. Never set `XDG_DATA_HOME` |

## Skills

Installed at `~/.agents/skills/<name>/` (canonical copies in `harness/skills/`); invoke as
`/<name>` in a session.

| Skill | Invoke when |
|---|---|
| `healbot-traps` | Touching fork/, rig, or harness code — or any time behavior contradicts expectation |
| `citation-hygiene` | Before editing any `.md` containing `file:line` citations |
| `rig-assertion-discipline` | Before creating or editing any probe_*/verify_* rig |
| `paid-run-protocol` | Before anything that spends API credits |
| `phase-close` | Before closing a phase, a session handoff, or a paid run — owns the tier2 trigger |
| `firstmate` | Running the crew fleet as controller |
| `tdd` | Red-green-refactor build work |
| `plainspec` | Writing docs, PR text, or error messages to the controlled prose standard ("STE mode" means strict) |

## Troubleshooting, distilled from the traps

The full registry is HARNESS.md's "Traps" section (mirrored by the healbot-traps skill);
these are the ones operators actually hit.

| Symptom | Cause → fix |
|---|---|
| `/healbot` does not exist | Installed binary, not the fork — fleet.sh already warns; reconstitute per `fork/README.md` |
| Grid's `x` retires nothing | The server plugin is not loaded (harness config not applied) — retirement lives ONLY there since Phase 7 |
| API/grid shows 0 sessions | Missing `x-opencode-directory` header / wrong project dir — you are addressing a different instance |
| Session boots with no model pin | Wrong `HARNESS_ROOT` (env.sh refuses loudly) — or on Windows, a POSIX-shaped path crossed the process boundary; run the doctor |
| Crewmate spawns signed out | The redirected config root needs its one-time login (env.claude.sh header). `spawn` refuses on this now rather than timing out — if you are seeing a login screen instead of a refusal, the token EXPIRED rather than being absent, which the detector cannot see |
| Crew constraints stale on a PC | `CLAUDE.md` is a copy there, not a symlink — re-source `harness/env.claude.sh` (it refreshes drift); the doctor flags it |
| Fleet `state` says "no hook events" forever | `HB_FLEET_DIR` unset (interactive shells are hook-silent by design), or no `python`/`python3` on PATH — the hook is fail-open and will not error |
| A probe prints green on a fresh clone | Green is not evidence that anything ran — floors catch it now, but read `docs/CLONE.md` before trusting any suite run from a new environment |
| tier2 from a worktree slot shows reds | Expected: declared environment skips (`gate/GATE.MAP.md`, "Tier 2 from a pool slot") — a skip in the MAIN checkout is the defect |
| Gate exit 3 vs 2 | 3 = a check left its claim unmeasured — it could not be launched, or its own preconditions failed (a broken truth table, a failed file enumeration, a fork twin that does not match). 2 = a check exited nonzero. The narrow surprise: a tier-1 probe that **started** is 2 on every nonzero exit, even when it ran only far enough to report its own inputs missing — so a clone without `opencode/` blocks at 2, while a clone without the venv (the probe never starts) is 3 (`docs/E2E.md` finding 13). Do not read either as "retry" |
