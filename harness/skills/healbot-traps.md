---
name: healbot-traps
description: Lookup of healbot's measured traps, each a silent wrong-belief producer rather than an error. Invoke when touching fork/, .carryover/verified/, or harness/ code, and whenever observed behavior contradicts expectation. Every entry is measured; most are also guarded by a probe, named per entry.
---

# Healbot traps

Every trap below produces a wrong belief silently rather than an error. All are measured;
where a probe guards the trap mechanically it is named, and those entries exist here only so
you recognize the red when it fires. HARNESS.md's "Traps" section is the canonical registry.

## Rig traps

- **`fire()` records a thrown turn and a finished turn identically.** `len(box)` counts
  turns that ENDED. Gate on ended, assert on ran via `rig.completed()`. Guard: contract 6 in
  probe_rig_contract.py. Full rule: the rig-assertion-discipline skill.
- **`wait_for`'s timeout does not bound.** The deadline is checked only between calls to
  `fn`, and `Api.__call__` defaults to timeout=900, so a 300 s budget can be held for 900 s.
  Unrepaired; sizing any watchdog, stay above ~20 minutes.
- **`Term.find()` is case-insensitive and the project path contains "healbot".** Use
  `rig.on_grid()` and `t.exact()`.
- **The rig's Api must send `x-opencode-directory`** or you address a different instance:
  every call succeeds and the grid shows 0 sessions.
- **The rig project dir needs its own git repo** (`rig.git_baseline()`) or every changed
  file is invisible to the diff machinery.
- **verify_question.py depends on the model CHOOSING to ask.** Three framings, 300 s polls
  each; ~10 minutes before it reaches the grid is the rig working, not hanging.
- **The suite is not portable.** A fresh clone lacks the gitignored `opencode/` checkout
  (rebuild per fork/README.md) and the venv; only probe_turn_predicate.py survives a fresh
  clone. Guard: `Results(expect=N)` floors make the collapse loud.
- **probe_turn_growth.py's real-corpus counts grow** with the live opencode.db. Since
  2026-07-31 the fixture is a FLOOR (677/56/733, the Phase 7 snapshot), so growth stays
  green and falling BELOW the floor means a different corpus (fresh clone, truncation) —
  not drift. A moved IN-SCOPE maximum, bound, or conditional is a finding either way. The
  probe prints both populations side by side.

## Fork and plugin traps

- **`fork/healbot-fork.patch` is a THIRD copy of the overlay and nothing compares it to
  `fork/`.** probe_twin.py guards `fork/` ↔ `opencode/`, and the checkout is kept in sync by
  hand — so the guarded pair stayed green while the unguarded one came apart. TESTED
  2026-08-02 from a fresh clone: `git apply` reproduces 15 of 17 overlay files and leaves two
  `.MAP.md` behind (Phase 11 corrected citations in them after the patch was cut), taking
  doctor.py to 1 FAIL, probe_twin.py to 24/25, and the gate to exit 2. `fork/` is the
  authority; the reconstitution ends by copying `fork/` over the checkout. Guard: the doctor's
  `fork overlay` row and probe_twin.py — both read the END STATE, which is why the patch
  itself can still drift.
- **The installed `opencode` binary has NO grid.** Run from source: rig.py's OC constant, or
  harness/fleet.sh. TESTED 2026-08-02 on the 1.18.5 release: it carries the `diff-viewer` and
  `which-key` builtins and zero `healbot` strings — while the harness config still reaches it,
  so the pin, compaction-off and the retirement plugin all arm on it. The failure is
  narrow and therefore easy to misread: everything works except the headline screen.
- **Every field that looks like "the turn is over" is set per STEP** (`finish`,
  `time.completed`), usually mid-turn. `turnFinished()` in the harness server plugin is the
  only correct reader. Guard: probe_turn_predicate.py, including the mutation leg.
- **Retirement happens in exactly ONE process.** The grid's `x` only writes
  `metadata.healbot.retireRequested`; without the harness config loaded, `x` looks like it
  worked and nothing retires. The coupling is untyped in both directions.
- **Thresholds are read by the SERVER process.** Exporting HEALBOT_RETIRE_AT into a rig's
  own environment configures nothing; use `rig.serve(env_extra={...})` and read the serve
  log.
- **A plugin module may export ONLY functions.** One exported constant throws at load time
  and leaves a healthy server with a missing feature and no error.
- **A server plugin gets the v1 SDK client, the TUI gets v2**, and they diverge silently;
  the generated types are narrower than the routes.
- **An external TUI plugin can silently replace the grid.** The route map is last-wins and
  external plugins load after internal ones; a third-party plugin registering "healbot"
  wins with no error and no log line.
- **The session-route sidebar is gated on width > 120** and is the only thing rendering a
  session id; at exactly 120 a focus assertion measures geometry, not navigation.
- **Session ids are DESCENDING identifiers**, so ascending sort is newest-first.

## Model and threshold traps

- **RETIRE_AT is only valid for the pinned model.** `worst_turn` is a fact about a model's
  tool-calling behaviour. Changing the pin in harness/config/opencode/opencode.jsonc
  silently un-verifies the threshold. Guard: probe_turn_growth.py asserts the pin. Note
  there are TWO files named opencode.jsonc; the harness config's is the pin.
- **The gate and the threshold are coupled.** Per-turn gating with no second gate means
  raising RETIRE_AT without restoring a hard gate silently reintroduces the cliff.
- **The context ceiling is ~360K**, not the 922,000 `limit.input` the model registry
  advertises.
- **`healbot_*: deny` scopes CONTEXT, not CAPABILITY.** A denied agent reached session
  creation through `opencode run` in bash. Build nothing on the assumption that a denied
  agent cannot reach a capability.

## Environment traps

- **Never set XDG_DATA_HOME.** auth.json lives there and OpenAI is on oauth; isolate the DB
  only.
- **Environment mutation during a live study voids arms.** Check on-disk study state, not
  process liveness, before any script that touches global config (the apply-symlinks.sh
  incident). Full protocol: the paid-run-protocol skill.
- **Skill twins sync by hand; sessions load the INSTALLED half.** `harness/skills/<name>.md`
  (tracked) vs `~/.agents/skills/<name>/SKILL.md` (loaded by BOTH harnesses; the `.agents`
  copy wins name collisions). No installer exists, so a repo edit that skips the copy serves
  every live session a stale skill in green — MEASURED 2026-08-02, two days, on this very
  skill while only firstmate was guarded. A red's direction is a diff's call, never assumed.
  Guard: doctor's `skill twins` row (any machine) and probe_fleet_claude.py's population
  sweep (main checkout).
- **The Claude CLI migrates each config root ONCE, and the migration rewrites the tracked
  model pin.** claude 2.1.220's ladder step 13 rewrites exactly the alias `opus` →
  `opus[1m]` (the 1M-context variant, premium-priced above 200K input) in
  `harness/claude/settings.json` on the FIRST config-loading invocation (`auth status`,
  `config list`; `--version` is safe) in any root whose untracked `.claude.json` lacks
  `migrationVersion >= 13`, then stamps 13. Fresh worktrees, pool slots, and clones carry
  only the tracked half, so each one rewrites once — a doctor run or crew spawn dirties a
  tracked file mid-session. Other pin values pass byte-identical. Repair: revert the file,
  keep the stamp. The main checkout is stamped; the pool slots are not. Guard:
  probe_fleet_claude.py's settings row asserts the pin VALUE (opus) with a mutation leg.
  Contained at both known triggers since 2026-08-02: the doctor restores its own trigger
  (check_claude_auth snapshots and byte-restores the settings file, stamp kept), and the
  fleet contains it at hb_auth_state, which stamps the root before every spawn and
  preflight. Residual: a hand-run interactive `claude` in an unstamped root still fires
  once; repair unchanged.
