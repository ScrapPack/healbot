# WINDOWS.md — the second machine

Bring-up guide for a Windows PC, written 2026-08-02. The goal is workflow parity with the
Mac for the daily-driver halves (Claude Code, opencode, the gate), an honest boundary around
what stays POSIX-bound (the tmux fleet, the pty rig, the APFS pool), and a mechanical way to
verify all of it **on the PC itself**: `harness/doctor.py`. Owner decision, recorded here:
**local models are not part of the PC setup.** The Mac's local-model pin is machine state
outside this repo, the harness config never references one, and nothing below installs one.

## What runs where

| Capability | Native Windows (Git Bash) | WSL2 | macOS |
|---|---|---|---|
| Claude Code workflow (`env.claude.sh`, settings pin, hooks) | yes | yes | yes |
| opencode workflow (`env.sh`, fork TUI/grid, `fleet.sh` server+attach) | yes | yes | yes |
| Per-change gate (`gate/gate.py`, pre-push hook) | yes | yes | yes |
| Crew fleet (`hb-fleet.sh`) | no — tmux | yes | yes |
| Rig / free suite (`.carryover/verified/`) | no — `term.py` drives a real pty (`pty`/`termios`/`fcntl`) | yes | yes |
| Worktree pool (`harness/pool.py`) | no — APFS clonefile (`cp -c`) is its economic premise | no | yes |
| Corpus backup LaunchAgent | no — launchd/iCloud; see the Task Scheduler note below | n/a | yes |

"Yes" for native Windows is INFERRED from verified mechanisms until the doctor and a smoke
session have run on the PC — the mechanisms themselves are VERIFIED at source (below), the
scripts are TESTED on macOS after the portability changes, and the honest classification for
"the TUI renders and a turn completes on this exact PC" cannot be earned from a Mac. Run the
checklist at the bottom, in order, and it converts.

## Why this works at all: the two isolation knobs, verified

The whole harness stands on two environment redirections, and both survive Windows:

- **opencode** resolves its config root through the `xdg-basedir` package —
  `packages/core/src/global.ts:13` — which reads `$XDG_CONFIG_HOME` on **every** platform;
  there is no `%APPDATA%` branch in that package at the pinned version. The same file derives
  the data root (`auth.json`, `opencode.db`) from `$XDG_DATA_HOME` falling back to
  `~/.local/share`, so on Windows the live DB lands at `%USERPROFILE%\.local\share\opencode\`.
  The standing trap transfers verbatim: **never set `XDG_DATA_HOME`** (auth lives there).
- **Claude Code** honors `CLAUDE_CONFIG_DIR` on Windows (documented; default root
  `%USERPROFILE%\.claude`), and with Git for Windows installed both its Bash tool and its
  hook commands run under Git Bash — which is what makes `settings.json`'s
  `"$CLAUDE_CONFIG_DIR/hooks/fleet-state.sh"` hook commands portable as written.

What did NOT survive unmodified was the **path shape at the process boundary**: under Git
Bash, `$PWD`-derived paths are POSIX-shaped (`/c/Users/...`), and a native opencode/claude
process resolves that against the drive root — producing exactly the silent empty-config
boot `harness/env.sh`'s header warns about. Both env scripts and `fleet.sh` therefore pass
every boundary-crossing path through `hb_nativepath()` (cygpath `-m` on MSYS, identity
elsewhere). If you see a session that ignores the model pin, that conversion is the first
thing to check — `doctor.py` checks it structurally.

## Prerequisites

Install, in any order (winget names given; any equivalent works):

| Tool | winget id | Why |
|---|---|---|
| Git for Windows | `Git.Git` | **Required, not optional here**: Git Bash is the shell for the env scripts, the pre-push hook, and Claude Code's hook commands |
| Windows Terminal | `Microsoft.WindowsTerminal` | Run the TUIs from its Git Bash profile. Do not use mintty (the bare "Git Bash" console) for TUIs — ConPTY is what makes them render |
| Python 3.10+ | `Python.Python.3.12` | doctor, gate, venv. Watch for the Microsoft Store `python3` stub; the harness calls `python` when `python3` is absent |
| Bun | `Oven-sh.Bun` | runs opencode from source (`fork/README.md` pins bun 1.3.14) |
| Node LTS | `OpenJS.NodeJS.LTS` | `probe_turn_predicate` and the checkout's lint gates |
| Claude Code | per docs.anthropic.com | the Claude half |
| GitHub CLI (optional) | `GitHub.cli` | only if you push; the gate's publisher uses `gh` |

## Bring-up, in order

Everything below runs in **Git Bash inside Windows Terminal**, from the clone root. To
have a Claude Code agent drive these steps instead, paste the prompt in
`docs/AGENT-SETUP.md`.

1. **Clone to a path without spaces** (the gate's command strings word-split by design):

   ```sh
   git clone https://github.com/ScrapPack/healbot ~/healbot && cd ~/healbot
   ```

   Line endings are pinned by `.gitattributes` (`eol=lf`), so a default Windows git cannot
   CRLF-break the scripts. The doctor verifies the working tree anyway.

2. **Run the doctor, first thing and after every step:**

   ```sh
   python harness/doctor.py
   ```

   It prints PASS/FAIL/WARN/SKIP rows plus a tier summary of what this machine can carry.
   SKIP rows on native Windows (tmux, pty) are by design, not defects.

3. **Wire the push gate** (once per clone): `git config core.hooksPath gate/hooks`

4. **Reconstitute the opencode checkout** — same commands as the Mac, per `fork/README.md`:

   ```sh
   git clone https://github.com/sst/opencode opencode
   cd opencode && git checkout -b healbot 7534d23 && git apply ../fork/healbot-fork.patch
   bun install && cd ..
   cp -R fork/packages/. opencode/packages/ && cp -R fork/.opencode/. opencode/.opencode/
   ```

   `*.patch` is marked `-text` in `.gitattributes`, so the patch bytes are exact. The two
   `cp` lines are load-bearing, not tidying: the patch is pinned at the fork commit it was
   cut from and two overlay files have had citation corrections since (`fork/README.md`,
   "Correction, 2026-08-02"). Re-run the doctor after this step — its `fork overlay` row is
   what tells you the checkout matches `fork/`.

5. **Build the venv** (gate Tier 1 runs on native Windows; the pty probes do not):

   ```sh
   python -m venv .carryover/verified/venv
   .carryover/verified/venv/Scripts/python.exe -m pip install pyte
   ```

   `gate/gate.py` and the pre-push hook auto-detect the `Scripts/` layout.

6. **Install the skill twins** — `python harness/install-skills.py` copies each
   `harness/skills/<name>.md` to `~/.agents/skills/<name>/SKILL.md` and surfaces it at
   `~/.claude/skills/<name>` (a copy there, not a symlink, without Developer Mode — the
   installer says which it did). The doctor's skill-twins row verifies the installed
   `~/.agents` halves; the copy surface is the installer's own to re-check — a re-run
   refreshes an in-sync copy and HOLDS a divergent one at exit 1 (`--force` overwrites,
   the drift-direction rule in the script's header).

7. **opencode half:** `harness/fleet.sh` for the server+attach shape — first boot compiles
   under bun and is slow, and the grid is `/healbot`. `. harness/env.sh && opencode` is the
   single-session form, but note what it runs: `opencode` off your `PATH`, which on a fresh
   PC is nothing at all (the prerequisites above install **bun**, not a released opencode)
   and if you do install one is a **released binary with no grid** — the harness config
   still reaches it (pin, compaction off, retirement plugin), but `/healbot` is a builtin of
   the fork. `fleet.sh` prefers the checkout and warns when it falls back.

8. **Claude half:** `. harness/env.claude.sh && claude` — the redirected config root needs
   its **one-time interactive login** (env.claude.sh's header explains; the Mac's
   keychain-landing finding is macOS-specific and does not transfer — on Windows the
   credential lands under the redirected root or DPAPI, and the whitelist `.gitignore`
   already covers the file case). Expect the per-directory trust dialog once.
   `CLAUDE.md` materializes as a **copy** here (symlinks need Developer Mode); the script
   refreshes a drifted copy on every source, and the doctor flags stale copies.

9. **WSL2, when you want the rest:** install a distro, clone the repo *inside* WSL (not on
   `/mnt/c` — pty and file-watcher performance), and follow the macOS/Linux quickstart
   there. tmux fleet (`hb-fleet.sh`), the rig, and Claude Code's sandboxing all work under
   WSL2. The pool stays Mac-only either way.

## Mac-only pieces, and their PC stand-ins

- **Corpus backup** (`harness/backup-opencode-db.sh`, installed by
  `harness/install-db-backup.sh`, which renders `__HOME__` into
  `harness/com.healbot.opencode-db-backup.plist` at install time): the script's method
  (`VACUUM INTO`, integrity check, gzip, rename) is portable; its install (launchd, TCC,
  iCloud paths) is not. On a PC with paid corpus worth protecting, run the same VACUUM
  snapshot from Task Scheduler against `%USERPROFILE%\.local\share\opencode\opencode.db`
  into any synced folder — schedule `bash <repo>\harness\backup-opencode-db.sh` only after
  editing `SRC`/`DEST_DIR`, or write the two-line PowerShell equivalent. Deliberately not
  shipped: no PC corpus exists yet to protect, and an untested backup script is worse than a
  documented recipe.
- **`harness/pool.py`**: `cp -c` is APFS clonefile and `os.kill(pid, 0)` is not a liveness
  probe on Windows. Do not run it there; `hb-fleet.sh spawn --slot` is the only caller and
  is WSL/Mac territory anyway.
- **The keychain finding** in env.claude.sh's comments (login credential in the macOS login
  keychain) is a macOS fact, recorded as such.

## The conversion checklist (INFERRED → TESTED, on the PC)

Run these on the PC and the platform claims above stop being inferences:

1. `python harness/doctor.py` → expect FAIL 0; SKIPs only for tmux/pty. Exit 0 once the
   checklist is complete (the tmux/pty tiers are N/A on native Windows, and N/A counts as
   carried); exit 2 mid-checklist means a tier is still NOT YET, which is the checklist
   working, not a defect.
2. `.carryover/verified/venv/Scripts/python.exe gate/gate.py` → `== PASS ==` (Tier 1 + the
   citation sweep run natively).
3. `harness/fleet.sh` → in the TUI, the model line shows `gpt-5.6-sol` (the pin reached the
   process — the single most load-bearing check on this page) and `/healbot` exists. Both
   clauses need the **fork**, which is why the command is `fleet.sh` and not
   `. harness/env.sh && opencode`: the latter runs whatever released binary is on `PATH`,
   where the pin arrives and the grid does not. If `fleet.sh` prints its
   `no fork checkout … falling back` warning, step 4 did not finish.
4. `. harness/env.claude.sh && claude` → sign in once; `claude` again → still signed in,
   `/status` shows the redirected config root, model `opus`.
5. Optional, WSL2: the macOS/Linux quickstart end-to-end, then `hb-fleet.sh up` + one spawn.

Anything that fails here is a finding about the PC or about this guide — record it either
way (HARNESS.md "The second machine" section owns the index).
