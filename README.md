# healbot

A context-lifecycle harness for coding agents. Long agent sessions do not degrade gracefully —
on the measured provider path they run to a cliff (~360K tokens of live occupancy) and then
fail every subsequent turn. healbot's answer is **retirement**: a session that crosses a
measured threshold finishes its turn, writes a handoff, and a fresh session picks the work up.
This repository is the harness that implements that policy, the fleet tooling around it, and —
just as deliberately — the evidence discipline that keeps every number in it honest.

Two agent stacks are harnessed, with the same config discipline on each:

- **opencode** (an [sst/opencode](https://github.com/sst/opencode) fork overlay): a pinned
  model, compaction off so retirement is the sole lifecycle policy, a server plugin that owns
  all retirement, and a control-terminal grid (`/healbot`) for driving a fleet of sessions.
- **Claude Code**: an isolated config root with the same pins, a tmux crew fleet with a
  captain/crewmate contract, and lifecycle hooks feeding a fleet state channel.

## The method, because it is the actual deliverable

Every claim in this repo is classified — VERIFIED (read the code, cite `file:line`), TESTED
(ran it, exit code captured), INFERRED, or SUSPECTED — and the project's recurring finding is
that the dangerous failure mode is **passing**: assertions that cannot fail, suites that
report green for runs that died, numbers that survive the disappearance of their own
evidence. The phase docs in `docs/` are a chronological record of hunting exactly that, and
the guards it produced are executable:

- a free probe suite with declared assertion floors and mutation controls
  (`.carryover/verified/`),
- a per-change gate wired into `git push` (`gate/` — Tier 1 static checks, an advisory model
  review, and an evidence publisher that comments the run records onto the pushed commit),
- every `file:line` citation in the docs, mechanically resolved on every gate run —
  `probe_citations.py` prints the size of the corpus it swept.

## Repository map

| Path | What it is |
|---|---|
| `HARNESS.md` | **The root index.** Start here; it names the file that owns any behavior |
| `NEXT.md` | The prompt a fresh working session starts from |
| `harness/` | The deliverable: env scripts, opencode + Claude Code config roots, the fleet scripts, the worktree pool, `doctor.py` |
| `fork/` | The opencode fork overlay — 17 files plus the exact patch against base `7534d23` (v1.18.5), and the subsystem maps |
| `opencode/` | *Not in git.* The derived working checkout; `fork/README.md` rebuilds it |
| `gate/` | The per-change gate, tier-2 runner, model review, evidence publisher |
| `.carryover/verified/` | The measurement rig: free probes, paid rigs, and the tracked corpus of paid session DBs the thresholds are derived from |
| `docs/` | Phase docs (the evidence record), plus `OPERATIONS.md` (command cheat sheet), `RECORDS.md` (the decision-record store), `WINDOWS.md` (PC bring-up), and `AGENT-SETUP.md` (paste-in prompt for agent-driven bring-up) |
| `~/.healbot/records/` | *Not in git, and not in any repo.* The decision-record store, keyed per project. Out of the tree on purpose: a record carries verbatim session text, so a `git add -A` in a client repo would commit the operator's prompts. It does not travel with a clone — [docs/RECORDS.md](docs/RECORDS.md) §3 |

**Live surface vs. record**, because `docs/` holds both and the filenames do not say which:
this README, `docs/OPERATIONS.md`, `docs/WINDOWS.md` and `docs/AGENT-SETUP.md` are what you
read to *use* the repo, together with `harness/doctor.py` — the only one that answers for
**your** machine rather than for this one. Everything else under `docs/` is a **dated phase record**: the evidence
behind a number or a decision, written at the time and corrected in place by appending,
never rewritten. `docs/CLONE.md` is both — a Phase 9 record, and the page to read before
trusting any suite run from a fresh environment. You do not need the records to run the
harness; you need them before you argue with a figure. `HARNESS.md` indexes **all eighteen**
of them newest-first and says what each settles — MEASURED 2026-08-03, and the `docs/`
files it does not list are `OPERATIONS.md`, `WINDOWS.md`, and (since 2026-08-05)
`AGENT-SETUP.md`, which are live surface, not record. Its own exit test — *"from this file alone you should be able to name the file that
owns any given behavior"* — held for fifteen of the seventeen indexed on 2026-08-02;
`docs/AFK.md` and `docs/REFUSAL-RESCORE.md` appeared in it **zero** times. `docs/E2E.md` is
the eighteenth, added the next day.

## Quickstart — macOS / Linux

```sh
git clone https://github.com/ScrapPack/healbot && cd healbot
python3 harness/doctor.py            # fix what it names — exit 0 only when every tier is READY or N/A (1 FAIL / 2 partial)
git config core.hooksPath gate/hooks # wire the push gate, once per clone
```

Reconstitute the opencode checkout (derived, gitignored — see `fork/README.md`):

```sh
git clone https://github.com/sst/opencode opencode
cd opencode && git checkout -b healbot 7534d23 && git apply ../fork/healbot-fork.patch
bun install && cd ..
cp -R fork/packages/. opencode/packages/ && cp -R fork/.opencode/. opencode/.opencode/
```

That last line is not belt-and-braces. The patch is pinned at the fork commit it was cut
from, and two of the seventeen overlay files have had citation corrections since, so
`git apply` alone leaves the checkout two files behind `fork/` — which `fork/` being
authoritative makes a real difference, and which blocks the gate. Re-run
`python3 harness/doctor.py` afterwards: it compares all seventeen and fails if any differ.

Build the rig venv, then run the harness:

```sh
python3 -m venv .carryover/verified/venv && .carryover/verified/venv/bin/pip install pyte
python3 harness/install-skills.py     # the skill twins (doctor's skill-twins row verifies)
. harness/env.sh && opencode          # one session, harness switches applied
harness/fleet.sh                      # or: server + control terminal, sessions survive the client
. harness/env.claude.sh && claude     # the Claude Code half (one-time login on first use)
harness/hb-fleet.sh start             # the crew cockpit: preflight, build, attach
```

`opencode` on that second line is whatever is on your `PATH`. The harness config reaches a
released binary — TESTED: the model pin, compaction off, and the retirement plugin all arm
on one — but the `/healbot` grid is a builtin of the **fork**, so it exists only when
opencode runs from the reconstituted checkout. `harness/fleet.sh` resolves that itself and
says so when it has to fall back.

`hb-fleet.sh start` is the whole bring-up: it preflights the machine, builds the tmux
session, adds the editor and grid panes **if** this machine has what they need (each absence
is a named skip, never a refusal), and attaches. Re-running it on a live fleet just
reattaches. Inside the cockpit, `C-b ?` is the command card; the one-time login the preflight
asks for is the Claude Code half above.

That login is **per config root, not per machine**: the credential is keyed to
`harness/claude/`, so every clone, worktree and pool slot starts signed out and
`harness/doctor.py` says which state yours is in.

`docs/OPERATIONS.md` is the full command surface, including the crew fleet
(`harness/hb-fleet.sh`) and the gate. `docs/E2E.md` is the same surface walked end to end by
an operator, with every place the two disagreed.

## Quickstart — Windows

The daily-driver workflow (Claude Code, opencode, the gate) runs on native Windows under Git
Bash; the tmux fleet and the pty-driven rig run under WSL2 by design. `docs/WINDOWS.md` is
the bring-up guide; the short form:

```sh
python harness/doctor.py     # from Git Bash in Windows Terminal; it names what is missing
```

To have a Claude Code agent drive the whole bring-up, paste the prompt in
`docs/AGENT-SETUP.md` into a fresh session on the clone.

Local models are deliberately not part of the PC setup — that pin is Mac-side machine state,
and the harness config in this repo never references one.

## What a fresh clone can and cannot do

This is measured, not guessed (`docs/CLONE.md`): the tracked tree carries the harness, the
gate, the docs, the fork overlay, and the paid measurement corpus — but the `opencode/`
checkout and the rig venv are derived and must be rebuilt as above. Until they are, most of
the probe suite reports honestly that it cannot run (`harness/doctor.py` tells you where you
stand). The paid rigs under `.carryover/verified/` cost real API credits to re-run; their
recorded corpus is tracked precisely so the derivations remain checkable without re-paying.

## The load-bearing numbers, and their scope

Retirement fires at **180,000 tokens of live occupancy** — the default inside the server
plugin, overridable by setting `HEALBOT_RETIRE_AT` for the **server** process, which is why
sourcing `harness/env.sh` exports no such variable and the plugin's arming line is where you
read the live figure. It is derived from
a measured context ceiling of **~360K** and a measured worst single-turn growth — the full
derivation, with every correction it survived, lives in `harness/env.sh` and
`docs/OUTCOME.md`. The number is **model-specific by measurement**: it is verified only while
the harness pins `openai/gpt-5.6-sol`, and the Claude-side harness deliberately ships **no**
verified retirement threshold. Do not carry either number anywhere else.

## Status

Research harness, built and measured on one macOS machine; Windows parity work (path
boundaries, venv layouts, LF pinning, the doctor) landed 2026-08-02 with the honest caveat
that Windows end-to-end runs are verified by running `harness/doctor.py` *on that machine*,
not by this repo's history. Nothing here is packaged for reuse; it is a working lab whose
value is the record.

## License

MIT — see `LICENSE`, including its third-party notice: the `fork/` overlay and its patch
derive from [sst/opencode](https://github.com/sst/opencode) (MIT, Copyright (c) 2025
opencode), and the reconstituted `opencode/` checkout carries upstream's own license file.
