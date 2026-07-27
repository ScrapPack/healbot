# NEXT — the prompt for a fresh session

Paste the block below into a new agent session at `~/Desktop/healbot`. Everything else in this
file is context for whoever maintains the prompt; the agent only needs the block.

The prompt is short on purpose. This project's method is that a phase reads the written
artifacts, never the prior transcript — and the project exists to cut standing context, so a
handoff that pastes ten thousand words of history is working against its own premise.

---

## The prompt

```
Continue the healbot build at ~/Desktop/healbot. Phase 6 is complete and committed.

READ FIRST, in this order. Stop when you can name the file that owns any given behaviour:
  1. HARNESS.md          — root index: load-bearing facts, Traps, Closed, Still open
  2. docs/HEADLESS.md    — Phase 6: automatic retirement moved to a SERVER plugin so it runs
                           with no client attached, focus and question.rejected closed, and
                           the control agent built
  3. .carryover/verified/README.md — the test rig and its assertion discipline

Do NOT read the whole tree first. HARNESS.md indexes everything; follow it on demand.

YOUR TASK — Phase 7. Every non-optional step of the original build order is now built, so this
phase is about closing the gap between "tested at a low threshold" and "trustworthy in use".
In this order:

  1. Exercise the shipped 256,000 gate end to end, once. Everything about automatic retirement
     is TESTED at 20,000. The comparison is a single `>=` so the risk is genuinely low, but the
     number that ships has never fired. Run verify_headless_retire.py with no
     HEALBOT_RETIRE_AT override and confirm it behaves identically at scale. This costs real
     money (see verify_retire_350k.py's note) — ASK ME FIRST with an estimate.

  2. Close the double-retire race. `x` in the grid and the server gate are two processes with
     no shared lock; retire() re-reads the archived state right before archiving, which
     narrows the window to one request but does not close it. Pressing `x` as the gate fires
     can still produce two successors for one session. Options worth weighing: have the grid's
     `x` go through the plugin instead of running its own retire() (which would also collapse
     the two copies of handoffDocument that probe_twin.py currently guards), or claim the
     session server-side before spawning.

  3. Pick up whatever in `Still open` you judge worth the cost. The cheap ones: a startup sweep
     for sessions already over the gate when a server restarts (a policy call — say why),
     re-running verify_control_agent.py after its corrected assertion, and why the session
     route does not render a dismissed question on screen.

METHOD — this project's standard, and it is not decoration:
  - Classify every claim VERIFIED (read code, cite file:line) / TESTED (ran it) / INFERRED /
    SUSPECTED. Never present a lower tier as a higher one. Cite file:line and open the file.
  - This suite's characteristic failure is PASSING. Every new assertion needs a negative
    control or a mutation check — prove it can fail before you trust it green. Phase 6 caught
    three of its own: a tautology written into a rig, an assertion that measured terminal
    width instead of behaviour, and one that counted a subagent it should have excluded.
  - Run the FREE probes before spending anything:
      cd .carryover/verified
      venv/bin/python probe_on_grid.py        # 4/4
      venv/bin/python probe_error_state.py    # 10/10
      venv/bin/python probe_focus.py          # 24/24
      venv/bin/python probe_twin.py           # 20/20
      venv/bin/python probe_headless_arm.py   # 11/11
      venv/bin/python probe_control_wiring.py # 14/14
      venv/bin/python probe_fleet.py          # 10/10
    The credit-spending rigs are listed in .carryover/verified/README.md.
  - Gates before you claim done, from ~/Desktop/healbot/opencode:
      ./node_modules/.bin/tsgo --noEmit -p packages/tui/tsconfig.json    # expect exit 0, no output
      ./node_modules/.bin/oxlint packages/tui/src/feature-plugins/system/healbot.tsx
                                                                        # expect exit 0, 3 warnings
  - Every phase revises the artifacts it contradicts. Write docs/<PHASE>.md, update HARNESS.md,
    and fix any figure you disprove. Do not leave a stale number in a file that another session
    will trust. Phase 6 found one in harness/config/opencode/opencode.jsonc that Phase 5 had
    already disproved.

TRAPS THAT COST REAL TIME — all measured, all in HARNESS.md, repeated here because each one
silently produces a wrong result rather than an error:
  - The installed `opencode` binary has NO grid. The Healbot route is a builtin of the fork.
    Run from source: rig.py's OC constant, or harness/fleet.sh which resolves it for you.
  - AUTOMATIC RETIREMENT IS A SERVER PLUGIN, not part of the grid. Thresholds are read by the
    SERVER process, so a rig that exports HEALBOT_RETIRE_AT into its own environment before
    attach() configures nothing. Use rig.serve(..., env_extra={...}) and read what it did with
    rig.serve(..., log=path).
  - A server plugin gets the v1 SDK client, the TUI gets v2, and they diverge silently: v1 has
    no permission/question sub-clients and its session.update body has no time.archived. The
    SERVER accepts it; the generated types are narrower than the routes.
  - A plugin module may export ONLY functions. One exported constant throws at load time and
    leaves a healthy server with a missing feature.
  - The rig's Api MUST send `x-opencode-directory`. Omit it and every call succeeds, the
    sessions are there, and the grid shows `0 sessions` — you are addressing a different
    instance (workspace-routing.ts:87 falls back to process.cwd()).
  - The rig's project dir needs its own git repo (rig.git_baseline()). It is gitignored by this
    repo, and session diffs are computed with git, so without it every changed file is invisible.
  - Never set XDG_DATA_HOME. auth.json lives there and OpenAI is on oauth; redirecting it
    strands the credentials and the model pin stops resolving. Isolate the DB only, via rig.db().
  - Term.find() is case-INSENSITIVE and the project path contains "healbot". Use rig.on_grid()
    for route assertions and t.exact() for cell labels.
  - The session-route sidebar is gated on width > 120 and is the only thing rendering a session
    id. The navigation rigs use exactly 120, so a focus assertion there measures geometry.
  - Session ids are DESCENDING identifiers, so ascending sort is newest-first.
  - The context ceiling is ~360K, NOT the 922,000 limit.input the model registry advertises.
    Nothing is truncated on the way up — it is a cliff, not a slope.

Ask me before spending real API credits on anything beyond a few turns.
```

---

## Why these three, in this order

**1 is the only thing standing between "it works" and "the shipped configuration works."** Every
retirement result in this repo except the 350K run was measured at a lowered threshold. The path is
threshold-independent by construction and the code reads a single `>=`, so this is confirmation
rather than discovery — but it is the last place a shipped default is asserted rather than
observed, and this project has already been wrong about a shipped default once (the ~570K headroom
figure).

**2 is the only known correctness hole left in the lifecycle.** It is narrow and unlikely, and it
is real. It also has an attractive fix that pays a second debt: routing the grid's `x` through the
plugin would leave exactly one implementation of `handoffDocument` instead of two, and retire
`probe_twin.py` along with it.

**3 is discretionary** and the list is in `HARNESS.md`. The startup sweep in particular is a
judgement call rather than a bug — say why, either way.

Deliberately **not** in the prompt:

- **Worktree isolation** (build-order step 7). `PLAN.md` marks it optional and nothing needs it.
- **External plugin route registration.** Still untested, still only matters if the grid ever has
  to leave the fork.
- **`/code-review ultra` on the `harness/` diff.** Still Phase 3's unmet gate, still user-
  triggered — an agent session cannot launch it. It stays the owner's action, and the `harness/`
  diff is now considerably larger than when that gate was written.

## Current state, for the maintainer of this file

Phase 6 landed across three commits, overlay at fork `88f7ce8cf`. Automatic retirement is a server
plugin (`harness/config/opencode/plugin/healbot.ts`) and runs headless; the grid no longer owns the
gate. Focus and `question.rejected` are closed. The control agent is built with five tools scoped
to it by a global deny plus an agent-level allow.

Test results — free: 4/4, 10/10, 24/24, 20/20, 11/11, 14/14, 10/10. Paid: 20/20 headless
retirement, 22/22 cold question reject, 15/16 control agent (one mis-specified assertion, corrected
and validated against the run's DB but not re-executed).
