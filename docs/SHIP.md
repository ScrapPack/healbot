# Phase 13 — the ship: claude fleet, firstmate, and config parity

Date 2026-08-01. Owner mandate: compare healbot's workflow shape against Kun Chen's
(kunchenguid) published agentic-engineering workflow and integrate the necessary or
high-value pieces; Claude Code must become a build driver in the fleet, not only the
review/measurement engine; claude and opencode harnesses must have config parity.

Method: six parallel investigation agents (live GitHub re-verification of the kunchenguid
repos; the video's own transcript via yt-dlp; the local Claude Code 2.1.220 config
surface; the healbot baseline with citations; tmux 3.7b mechanics tested on throwaway
sessions on this machine; a value scan for neovim and lavish). Findings below carry the
tier they arrived with; everything tagged TESTED in §2-§3 was executed on this machine
during the phase.

## 1. The comparison, settled

The 2026-07-31 evaluation had already adopted the DELIVERY half of Kun's workflow: the
pre-push gate pipeline is no-mistakes-shaped, `harness/pool.py` is treehouse-shaped, and
the arm factory covers the A/B pattern. This phase adds the COCKPIT half that was left on
the table, and closes two of his pieces as deliberate non-adoptions (§4).

Kun's cockpit, from the video transcript and the firstmate sources (VERIFIED): WezTerm +
tmux + neovim as the "ship"; one agent session per tmux tab as the parallelism unit; per-
tab `treehouse` then `claude`; firstmate as an AGENT DISTRO — a cloned repo whose
AGENTS.md turns the primary session into the captain-facing orchestrator (there is no
`/firstmate` slash command anywhere in it); crewmates spawned into tmux windows through a
backend contract; a zero-token bash watcher re-waking the orchestrator on fleet events;
all crew communication flowing through the first mate; the human as captain on top.

## 2. Config parity (`harness/claude/` + `harness/env.claude.sh`)

**Where the claude root lives is load-bearing, and the first draft got it wrong.** It began
at `harness/config/claude/` and the free suite caught it: `arms._base_files()` os.walks
everything under `harness/config/` into every arm snapshot (arms.py:60, :83-92), so
`probe_arm_factory.py` went red on its banned-filename snapshot check — and the deeper
problem is that after the one-time login this directory holds CREDENTIAL state, which must
never be frozen into a run directory. Moved to `harness/claude/`, outside the frozen tree;
`probe_fleet_claude.py` now asserts the separation structurally. Second collision from the
same event: the crew memory file must be named `CLAUDE.md` for Claude Code to read it, and
gate.py:192 bans exactly that name anywhere in the tracked tree — resolved by the repo's
existing skills convention (safe name tracked: `crew-constraints.md`; real name
materialized: env.claude.sh creates the `CLAUDE.md` symlink at source time, and the
whitelist `.gitignore` keeps the symlink untracked).

The opencode harness knob map and its claude equivalents, load-bearing rows only:

| opencode (env.sh / opencode.jsonc) | claude harness |
|---|---|
| `XDG_CONFIG_HOME` redirect — the only real isolation | `CLAUDE_CONFIG_DIR` redirect — TESTED: under a redirected empty dir, `claude doctor` reported signed-out and wrote `.claude.json` + `backups/` into it. Full user-root redirect including auth/state; project `.claude/` stays, which is the deliberate keep |
| `"model"` pin | `settings.json "model": "opus"` — a DISCIPLINE pin, not a measured one (owner directive 2026-08-01; was `"sonnet"`). Alias VERIFIED present in the 2.1.220 binary (`grep -ac '"opus"` → 24). Per-spawn override records into the fleet manifest; `--model fable` (Fable 5, alias verified, 18 hits) is the recorded escalation for planning/long-form-synthesis briefs, never the default |
| no equivalent (opencode has no persisted effort knob) | `settings.json "effortLevel": "xhigh"` — max reasoning effort, same owner directive. VERIFIED as a user-settings enum in the 2.1.220 binary: `effortLevel:E.enum(["low","medium","high","xhigh"]).optional()...describe("Persisted effort level for supported models.")`, `"xhigh"` the top member |
| `permission: {...}` posture | `settings.json "permissions": {"defaultMode": "bypassPermissions"}` — the 2026-07-31 decision (crew run with normal prompts) REVERSED by owner directive 2026-08-01. Both names VERIFIED in the binary: `defaultMode:E.preprocess(...E.enum([...Q_e...]))` (39 hits) over the mode list `["acceptEdits","auto","bypassPermissions","default","dontAsk","plan"]` (`bypassPermissions` 136 hits). Set in settings, NOT as a launch flag, so there is one recorded place and no per-spawn argv drift. Note the binary gates this mode out of PROJECT-scope settings — the harness root is user-scope via `CLAUDE_CONFIG_DIR`, which is where it is grantable |
| `"compaction": {"auto": false}` | `"autoCompactEnabled": false` + env `DISABLE_AUTO_COMPACT=1`, both names verified present in the 2.1.220 binary. `CLAUDE_CODE_DISABLE_AUTO_COMPACT` and `DISABLE_MICROCOMPACT` are NOT in the binary (0 hits) — do not use |
| `OPENCODE_DISABLE_EXTERNAL_SKILLS` | The redirect itself: claude's user skills live UNDER the config root, so an empty harness `skills/` is the switch. The `!`cmd`` slash-invoke hole this closed on opencode does not exist on the claude side |
| `OPENCODE_DISABLE_CLAUDE_CODE` | The redirect drops the user's `~/.claude/CLAUDE.md`; the harness ships its own crew-constraints `CLAUDE.md` |
| `permission: healbot_* deny` (strips definitions) | No equivalent at the permission layer — claude's `permissions.deny` blocks execution but leaves definitions paying rent, the exact "scoped deny" trap opencode.jsonc warns about. Definition-stripping is done by not loading tools (`--tools`, per-agent frontmatter) |
| `small_model`; trim-tools' `tool.definition` hook | NO EQUIVALENT. Recorded, not worked around |

Two facts earned by the doctor probe, both traps:

- **The `*_CONFIG_DIR` naming is INVERTED between the two programs.** opencode's
  `OPENCODE_CONFIG_DIR` is the additive false-isolation knob; claude's
  `CLAUDE_CONFIG_DIR` is the real one. Do not "fix" either by analogy with the other.
- **Auth does not follow the redirect.** A fresh harness config dir is signed out; the
  owner must run `claude` once under `env.claude.sh` and log in before any crew spawn
  works. The config dir is therefore mixed code+state, which is why its `.gitignore` is a
  WHITELIST — everything ignored except the four tracked files (.gitignore,
  settings.json, crew-constraints.md, hooks/fleet-state.sh) — so no file-shaped
  credential state can be committed. `probe_fleet_claude.py` asserts the ignore both
  ways. The review corrected the stronger claim this paragraph first made: on macOS the
  real install's OAuth token lives in the login KEYCHAIN (VERIFIED:
  `security find-generic-password -s "Claude Code-credentials"` returns it and
  `~/.claude/.credentials.json` does not exist), with the file only a fallback path in
  the binary — so the harness login may SHARE the owner's keychain item rather than
  isolate it. The first login settles that (§5).

## 3. The fleet (`harness/hb-fleet.sh`, the state channel, the firstmate skill)

One tmux server on its own socket, one session per fleet run, bridge window (captain
shell, optional nvim pane, optional opencode-grid pane) + crew window (one Claude Code
session per pane, tiled). tmux natively provides what `fleet.sh` had to hand-build with
`nohup`/`disown`: pane processes are children of the daemonized server and survive
terminal close (TESTED).

Mechanics measured on this machine before being written into the script (all TESTED):
socket isolation via `-L` (separate server, safe `kill-server`); `select-layout tiled`
RENUMBERS pane indexes, so panes are addressed only by immutable `%id`; `send-keys`
without `-l` interprets words like `Enter` as keys; a TUI that flushes its tty input at
startup DISCARDS early sends while still echoing them (the worst shape: the pane looks
fed, the app never saw it), so spawn waits for a ready marker; `history-limit` binds per
pane at creation; `kill-session` is SIGHUP (a child process was reaped in under 0.5s) —
in-flight turns abort, transcripts survive, `claude --resume <sid>` recovers; the server
auto-exits with its last session and takes global options with it, so bootstrap is
idempotent and re-asserts everything; tmux expands `%`/`#{}` formats inside hook strings
before the shell sees them.

Borrowed from firstmate's backend contract (reimplemented, zero third-party code run —
the pool.py/treehouse posture): type once then retry Enter only; five-state liveness
vocabulary (alive/dead/missing/unreadable/ambiguous) with only dead/missing authorizing
recovery, because a false dead reading launches a duplicate agent; sends resolve through
the manifest and refuse unresolved names rather than falling back to a tmux search.

The state channel is push-preferred, poll-backstop: `harness/claude/hooks/fleet-state.sh`
(SessionStart/Stop/Notification) writes `$HB_FLEET_DIR/state/<sid>.json`, and `state`
merges that with a bounded `capture-pane` classification. The hook is fail-open by
contract — every failure path exits 0, no `HB_FLEET_DIR` means no-op — and its one
development defect is worth recording: the first draft fed python its program via
`python3 - <<heredoc`, which consumes stdin, so the hook parsed nothing, exited 0, and
wrote nothing. Syntactically clean, behaviourally empty. TESTED into `probe_fleet_claude`
as a live happy-path check, which is the only shape that catches that class.

The `--session-id` flag is the load-bearing join: the supervisor generates the uuid, so
the transcript path `<config-root>/projects/<cwd-slug>/<sid>.jsonl` is known before the
session exists (slug rule owned by `backend.py`'s `project_slug`, verified against real
directories on disk). The config root part is the correction the review forced: crew run
under the redirected `CLAUDE_CONFIG_DIR`, so their transcripts land under
`harness/claude/projects/`, NOT `~/.claude/projects/` — this document's first draft said
the latter while its own §2 stated the full-redirect fact, and `backend.py` hardcoded the
default root. `backend.py` now honors `CLAUDE_CONFIG_DIR` (unset, nothing changes for
pre-fleet callers), so the manifest join and `occupancy` read the root the crew actually
write. That transcripts follow the root is INFERRED (strongly — session state was
observed landing in the redirected dir) until the first live crewmate confirms it (§5).
Occupancy and results are read from the transcript through `backend.py` — the screen is
never the record.

`harness/skills/firstmate.md` is the controller: the captain/crewmate contract adapted
into a skill (delegate-never-edit, all crew traffic through the controller, faithful
reporting, no blind turn-ends, fail-closed kills), installed by copy to
`~/.agents/skills/firstmate/SKILL.md` per the repo's skill convention.
`probe_fleet_claude.py` holds the canonical and installed copies byte-identical — the
probe_twin pattern — and asserts the body carries no `!`cmd`` shell-substitution pattern.

## 4. Deliberate non-adoptions

- **lavish-axi: rejected for now.** The skill is inseparable from its ~600KB
  partly-bundled Node CLI (express server, chokidar watcher, a telemetry module unread,
  and a `share` command publishing to third-party ht-ml.app), so an honest vendor-and-
  review is the largest in the whole Kun inventory, for a capability healbot's plans do
  not currently need: plans here are citation-disciplined prose swept by
  `probe_citations.py`, and an HTML plan of record would be uncheckable by exactly that
  probe. Re-evaluate only on a demonstrated need for interactive plan annotation, and
  then from source, not the published bundles — or build the minimal static renderer
  in-house. If used ephemerally ever: untracked `.lavish/`, never in `docs/`.
- **neovim: nothing to build.** Kun's own nvim config is a diff-review station (diffview/
  neogit/gitsigns; no coexistence machinery) — he solves human/agent coexistence with
  worktrees, which healbot already has as pool slots. On this machine nvim 0.12's
  `autoread` default plus the already-set tmux `focus-events on` covers reload-on-focus.
  The fleet gives nvim a bridge pane (`hb-fleet.sh up --nvim`) and that is the whole
  integration; anything more is a personal-dotfiles decision, out of repo scope.

## 5. Open after this phase

1. **One-time auth**: `. harness/env.claude.sh && claude`, log in, exit. Until then every
   crew spawn fails its ready-wait signed-out. Owner action.
2. **Pin the screen markers.** `HB_READY_MARKER`/`HB_BUSY_MARKER`/`HB_TRUST_MARKER`
   defaults are SUSPECTED, version-dependent strings. First live crewmate: capture each
   state once, pin the strings here and in the environment. Costs one short paid session.
3. **Verify the hook events live.** The wiring layer moved up a tier in the review's
   red-capable doctor test: the harness settings.json VALIDATES on the real 2.1.220
   binary (a control file with bad types produced typed errors naming the full valid
   event list, which includes SessionStart, Stop, and Notification), the pinned model is a
   documented alias, and hook commands run through `/bin/sh -c` with inherited
   environment, so `$CLAUDE_CONFIG_DIR` expands. Still open: the events actually FIRING
   with the expected stdin shape — the first-crewmate session settles it. The 2026-08-01
   repin (`opus` / `xhigh` / `bypassPermissions`, §2) re-opens one strand of this: every
   new key was verified present in the binary by grep, but the file has NOT been
   re-validated by the binary since, and whether bypass mode suppresses the Notification
   event for the dialogs it does NOT remove (bypass acceptance, per-directory trust) is
   UNVERIFIED. Same first-crewmate session settles both.
3b. **Settle where the harness login lands.** VERIFIED on this machine: the real
   install's token is a login-keychain item (`Claude Code-credentials`), not a config-dir
   file. Whether a login under the redirected root creates a second keychain item, reuses
   the owner's, or writes the `.credentials.json` fallback into `harness/claude/` is
   unknown until the one-time login runs. If it shares the owner's item, say so in this
   document and treat harness logout as touching the main install's auth.
4. **No verified retirement threshold exists for any Claude model.** The opencode numbers
   (180,000 gate, ~360K ceiling, 175,148 worst turn) are measurements of gpt-5.6-sol
   through opencode and DO NOT TRANSFER. With auto-compact off, the ceiling is a hard
   error, so until a claude-side growth measurement exists, the firstmate skill's rule is
   hand-off-early. The measurement program is the same one NEXT.md already carries for
   the opencode side, run through `backend.py`.
5. **Claude Code's native `--tmux`/`--worktree` spawning exists** (VERIFIED in --help)
   and is deliberately unused: it owns its own session naming and worktrees, and the
   fleet must own its topology and its pool. Recorded so nobody "simplifies" into it
   without noticing the manifest join breaks.
6. **A live-looking bearer token sits in `~/.claude/settings.local.json`** (inside a
   permissions rule for api.pixellab.ai), found during the parity inventory. Outside the
   repo, owner's to rotate or move.

## Results

| Check | | |
|---|---|---|
| `probe_fleet_claude.py` | **26/26** (floor 20) | free — live hook executions, every mutation control, the arms-tree separation, the CLAUDE.md symlink convention |
| `probe_rig_contract.py` | exit 0 | the new probe satisfies the six rig contracts |
| free suite before the build | 20/20 probes exit 0 | run at phase start, this session |
| free suite after the build | 21/21 probes exit 0 | includes the arm-factory red found and fixed mid-phase (§2) |
| phase close | gate PASS + tier2 PASS | on the final post-review tree: `gate/runs/20260801-110953.json`, `gate/runs/20260801-111010-tier2.json` (an earlier pre-review close, 105648/105706, is superseded — the score describes the file at the moment) |
| adversarial review | 28 findings, 4 lenses | four parallel reviewers (shell/config/docs/probe), several findings TESTED on this machine. Every blocking finding fixed in-phase: the spawn fallback that could respawn-pane -k a LIVE crewmate (its premise — split fails on a fresh window — was refuted by test; it fires on a FULL window), the `--run` flag that stranded every later subcommand on the default fleet (flag removed; HB_RUN env is the selector), and the transcript join pointing at `~/.claude/projects` while crew write under the redirect (backend.py now honors CLAUDE_CONFIG_DIR). Warnings fixed: per-pane `-e HB_FLEET_DIR` injection (panes inherit the SERVER's start env — TESTED), session-scoped death hook, brief-less spawn exiting 1, silent `state` on a missing manifest, argv-passed python (quote-safe paths), honest long-send reporting, kebab-validated crew names, keychain-aware credential claims, tightened whitelist. The probe gained four checks from its own lens (function-body resolution check, earliest-pane history anchor, the -e injection guardrail) |
