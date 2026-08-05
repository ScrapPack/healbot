# AGENT-SETUP.md — bring-up by a Claude Code agent

Live surface, not a phase record. This page holds one thing: the paste-in prompt for a
fresh Claude Code session on a newly cloned machine. The agent then works the bring-up
with the doctor as referee.

Another file owns every step the prompt orchestrates. `README.md` owns the POSIX
quickstart. `docs/WINDOWS.md` owns PC bring-up and the platform table.
`docs/OPERATIONS.md` owns the command surface. `harness/doctor.py` answers for the
machine itself.

This file owns only the orchestration prompt: when it disagrees with an owner, the
owner wins and this page is the bug.

The prompt enforces two boundaries, recorded here for the human. First, the one-time
`claude` login is yours, not the agent's. Credentials never pass through an agent: it
stops there, hands you the command, and verifies afterward. Second, prerequisite
installs on a PC may need an admin shell. The agent names what is missing and asks
rather than installing system tools itself.

Paste everything inside the fence:

```
Set up this healbot clone on this machine. You are the setup operator; the repo's own
docs carry every step, and harness/doctor.py is the referee. Do not invent steps.

READ FIRST: HARNESS.md (the root index), then the "What runs where" table in
docs/WINDOWS.md. On native Windows the tmux fleet, the pty rig, and the worktree pool
are N/A by design: a SKIP row there is not a defect. Windows work runs in Git Bash
inside Windows Terminal.

RULES, all hard:
- Never set XDG_DATA_HOME. auth.json lives there.
- Never run a verify_*.py rig, run_refusal.py, or smoke.py. They spend API credits and
  need the owner's go (the paid-run-protocol skill).
- The interactive `claude` login belongs to the human. Stop, hand over the exact
  command, wait, then verify.
- Do not push. Report instead; the owner pushes through the gate.
- Classify every claim in your report VERIFIED / TESTED / INFERRED / SUSPECTED, and
  never present a lower tier as a higher one.

THE PROCEDURE. Run the doctor between steps; it tells you what the last step changed.

1. Run `python3 harness/doctor.py` (`python` on Windows). Rows print with a tier
   summary, and exit 2 mid-bring-up means a tier is NOT YET: the checklist working.
2. Run `git config core.hooksPath gate/hooks`. Pushes now gate themselves.
3. Reconstitute the opencode checkout with the reconstitution block in README.md
   "Quickstart — macOS / Linux" (same commands on a PC). The doctor's `fork overlay`
   row turns PASS.
4. Build the rig venv per the same quickstart. On Windows the layout is
   `venv/Scripts/python.exe`, and the gate resolves both.
5. Run `python3 harness/install-skills.py`. On a DRIFT or CONFLICT row, stop with
   the output in your report. A clean run prints only installed, in-sync, linked,
   link ok, or copy dir rows.
6. Hand the login to the human: `. harness/env.claude.sh && claude`, sign in, quit.
   Afterward the doctor's auth row turns PASS.
7. Run `python3 harness/doctor.py` once more. The exit is 0, or 2 with only named
   pending tiers.
8. Run the gate command from docs/OPERATIONS.md "The gate". The verdict line prints
   `== PASS ==`.
9. On a machine with the rig, run the free-suite one-liner from docs/OPERATIONS.md
   "Rig and corpus". Every probe exits 0.

REPORT: one table, a row per doctor tier, columns state / evidence / classification,
plus the verbatim output of steps 7 through 9. Anything that failed is a finding about
this machine or about the docs. Record it either way, with the exact output. Do not
summarize a failure into a pass.
```

Once bring-up is green, the follow-on is the conversion checklist in `docs/WINDOWS.md`.
Running it on the PC converts that page's INFERRED platform claims to TESTED.
