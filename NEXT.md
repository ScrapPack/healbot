# NEXT — the prompt for a fresh session

Paste the block below into a new agent session at `~/Desktop/healbot`. Everything else in this
file is context for whoever maintains the prompt; the agent only needs the block.

The prompt is short on purpose. This project's method is that a phase reads the written
artifacts, never the prior transcript — and the project exists to cut standing context, so a
handoff that pastes ten thousand words of history is working against its own premise.

---

## The prompt

```
Continue the healbot build at ~/Desktop/healbot. Phase 7 is complete and committed; the fork
overlay is pinned at 6794bd581.

READ FIRST, in this order. Stop when you can name the file that owns any given behaviour:
  1. HARNESS.md          — root index: load-bearing facts, Traps, Closed, Still open
  2. docs/RELAY.md       — Phase 7: retirement collapsed into ONE implementation (the server
                           plugin); the grid's `x` became a REQUEST written to
                           `session.metadata.healbot.retireRequested`; the gate was found to
                           fire per STEP rather than per turn, which makes `RETIRE_HARD` inert
  3. .carryover/verified/README.md — the test rig and its assertion discipline

Do NOT read the whole tree first. HARNESS.md indexes everything; follow it on demand.

YOUR TASK — Phase 8. Every step of the build order is built and no known correctness hole is
open. What is left is two decisions that are mine to make, some verification that was never
re-run, and one optional spend. Do not invent a ninth thing to build.

  1. ASK ME BOTH DECISIONS IN YOUR FIRST MESSAGE, then do 2 while you wait. Neither is a bug;
     both are policy; both are small once decided. Present the branches, do NOT pick for me.

     a. `RETIRE_HARD` — delete it, or resurrect it. Today `HEALBOT_RETIRE_HARD` (330,000,
        `plugin/healbot.ts:140`) decides nothing: its only consumer is `consider()`'s
        `if (!stepOver && !hard) return` (`:616`), and `stepOver` is true on 733/733 measured
        messages, so `hard` is dominated. The cost of leaving it is a knob that reads as a
        safety net and is not one.
        DELETE — free, and it costs nothing that runs: the constant and its docblock, the
        commented default at `harness/env.sh:114`, `probe_twin.py:168-169` (which asserts the
        name is the plugin's alone) and `probe_headless_arm.py:88` (which passes it), plus the
        prose in HARNESS.md, docs/RELAY.md, docs/HARDEN.md and the rig README.
        RESURRECT — swap `stepFinished()` (`:345`) for opencode's own per-turn predicate
        (`prompt.ts:1295`, `finish && !["tool-calls","unknown"].includes(finish)`). One
        expression, and the hard gate goes live. But it makes the SOFT gate per-turn too, and
        that is a real regression on the number that matters: overshoot goes from one STEP
        (~65K measured) back to one TURN (~170K measured), so a session crossing at 256,000
        could finish near 426,000 — past the ~360K ceiling. That is the case `RETIRE_HARD` was
        drawn to catch, and per-step already catches it for free.

     b. The startup sweep. `consider()` has one call site, there is no polling, so a server
        restarting with a session already over the gate does nothing until that session's next
        event — then the SOFT gate catches it at the next step boundary. (`RETIRE_HARD` does
        NOT catch it and never could; HARNESS.md and docs/HEADLESS.md used to say it did.) A
        sweep at boot would close it properly and is small — list sessions, call the same
        `consider()`. It is not built because a restart triggering mass retirement is a policy
        choice, not a defect. Tell me which behaviour I want; the code is the easy part.

  2. FREE while you wait. Both are open questions, not builds.
     - Can an EXTERNAL plugin register a route, or only a builtin? The grid is a builtin and
       every measurement in this repo was taken on that path. It decides whether the grid must
       live inside the fork.
     - Why the session route does not render a DISMISSED question on screen. The text is in
       the session's parts over HTTP (asserted, passing); it is not on the visible viewport.
       Read the route first — scroll position and errored-tool-part rendering are the two
       candidates and source may settle it without a run.

  3. CHEAP — re-run verify_control_agent.py (~4 turns). It recorded 15/16; the failure was a
     mis-specified assertion, corrected TWICE and never re-executed. The current form asserts
     the build agent "created NO top-level session" (`:229`) because the previous correction,
     `all(s.get("parentID") for s in extras)`, passed VACUOUSLY whenever the build agent
     answered directly instead of delegating. Verify the detail line says so out loud when the
     case is not exercised, then run it.

  4. PAID and OPTIONAL — the 256,000 gate has still only been exercised at 20,000. Half of it
     is now closed for free: probe_headless_arm.py asserts the SHIPPED 256,000 default actually
     arms, paired with the opposite assertion that "soft 256,000" is ABSENT when an override is
     supplied. What remains unbought is FIRING at the real value, and the comparison is a
     single `>=`. If you want it: verify_retire_350k.py's growth-loop workload (70 x 35 KB
     chunks) retargeted to 256,000 — it already pops HEALBOT_RETIRE_AT and asserts its absence.
     ~$4.50, range $3-9, ~8-15 min. 256,000 stays under the provider's 272,000 tier, which
     DOUBLES every rate, so base rates hold throughout. NOT via verify_headless_retire.py:
     `THRESHOLD = 20_000` (`:52`) is a bare literal it hands the server via `env_extra`, which
     `rig.serve()` applies LAST; its workload is one prompt capped at 50 KB by `read.ts:16` and
     it asserts `len(user_turns) == 1`. At 256,000 the gate never fires and the 900s wait times
     out. ASK ME FIRST.

  5. NOT YOURS — Phase 3's exit gate, `/code-review ultra` on the `harness/` diff, is still
     unmet. It is user-triggered and billed; an agent session cannot launch it. Remind me.

METHOD — this project's standard, and it is not decoration:
  - Classify every claim VERIFIED (read code, cite file:line) / TESTED (ran it) / INFERRED /
    SUSPECTED. Never present a lower tier as a higher one. Cite file:line and open the file.
  - This suite's characteristic failure is PASSING. Every new assertion needs a negative
    control or a mutation check — prove it can fail before you trust it green. Phase 7's
    probe_request_channel.py was TESTED to fail: renaming REQUEST_KEY in the plugin drops it to
    5/9 with exactly the four channel assertions failing. Phase 7 also found an assertion that
    passed on an empty list, and Phase 6 caught three of its own.
  - Run the FREE probes before spending anything:
      cd .carryover/verified
      venv/bin/python probe_on_grid.py          # 4/4
      venv/bin/python probe_error_state.py      # 10/10
      venv/bin/python probe_focus.py            # 24/24
      venv/bin/python probe_fleet.py            # 10/10
      venv/bin/python probe_control_wiring.py   # 14/14
      venv/bin/python probe_twin.py             # 23/23
      venv/bin/python probe_headless_arm.py     # 15/15
      venv/bin/python probe_request_channel.py  # 9/9
    The credit-spending rigs are listed in .carryover/verified/README.md.
  - Gates before you claim done, from ~/Desktop/healbot/opencode:
      ./node_modules/.bin/tsgo --noEmit -p packages/tui/tsconfig.json    # expect exit 0, no output
      ./node_modules/.bin/oxlint packages/tui/src/feature-plugins/system/healbot.tsx
                                                                        # expect exit 0, 3 warnings
  - Every phase revises the artifacts it contradicts. Write docs/<PHASE>.md, update HARNESS.md,
    and fix any figure you disprove. Do not leave a stale number in a file that another session
    will trust. Phase 7 rewrote three documents and one rig because one claim about the gate
    turned out to be backwards.

TRAPS THAT COST REAL TIME — all measured, all in HARNESS.md, repeated here because each one
silently produces a wrong belief rather than an error:
  - The installed `opencode` binary has NO grid. The Healbot route is a builtin of the fork.
    Run from source: rig.py's OC constant, or harness/fleet.sh which resolves it for you.
  - RETIREMENT NOW HAPPENS IN EXACTLY ONE PROCESS — the server plugin. The grid's `x` no longer
    retires anything; it writes `metadata.healbot.retireRequested` and the plugin acts on the
    resulting `session.updated`. So running the fork WITHOUT the harness config means `x`
    appears to work — the keypress lands, the PATCH succeeds — and nothing is ever retired.
    Until Phase 7, `x` worked with no plugin loaded. Any note that says the grid retires is
    describing deleted code.
  - THRESHOLDS ARE READ BY THE SERVER PROCESS. A rig that exports HEALBOT_RETIRE_AT into its
    own environment before attach() configures nothing. Use rig.serve(..., env_extra={...}) and
    read what it did with rig.serve(..., log=path).
  - THE GATE FIRES AT A STEP BOUNDARY AND ABORTS THE TURN IN FLIGHT. `processor.ts:443-445`
    assigns `finish` and `tokens` in the SAME mutation at every `step-finish`, and `:445` is the
    only site writing a non-zero `tokens` — so every `message.updated` carrying occupancy also
    carries a set `finish`, usually `"tool-calls"`, i.e. mid-turn. MEASURED on 733 real
    assistant messages with occupancy > 0: zero had a null `finish`. Overshoot is therefore
    bounded by one STEP (~65K), not one whole turn (~170K) — better than what was designed, and
    arrived at by accident. Anything reasoning about "the turn is allowed to finish" is
    reasoning about a design that was never built, and `RETIRE_HARD` is inert for the same
    reason. Every artifact written before Phase 7 asserted the opposite.
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

## Why this order

**The two decisions go first because they are mine, not the agent's, and because everything else
in the phase is independent of them.** Asking both in the first message costs one round trip and
unblocks the rest; asking them halfway through stalls a session that has already spent context.
Neither is a defect and the prompt says so — the failure mode here is an agent that "fixes"
`RETIRE_HARD` by making the harness per-turn, silently trading a measured ~65K overshoot for a
measured ~170K one because the knob looked broken.

**2 is free and 3 is nearly free, so they precede anything billed.** `verify_control_agent.py` is
the only rig in the suite whose recorded score does not correspond to an execution of the file as
it stands; its assertion has now been rewritten twice without a run, which is exactly the state
this suite punishes.

**4 is last because half of what it used to buy is now free.** `probe_headless_arm.py` asserts
the shipped 256,000 default arms, and asserts the negative in the same run. What the money buys
is the firing half at the real value, over a `>=` already exercised at 20,000. Priced honestly at
~$4.50, and pinned to the right vehicle — the previous prompt named a rig that cannot reach the
threshold at all.

Deliberately **not** in the prompt:

- **Worktree isolation** (build-order step 7). `PLAN.md` marks it optional and nothing needs it.
- **The remaining grid traps** — RED silent under `--auto`, archived sessions never leaving the
  list. They are review-tier rows in `HARNESS.md`; the index carries them and the prompt does not
  need to.

## Current state, for the maintainer of this file

Phase 7 landed with the overlay re-pinned at fork **`6794bd581`** (was `88f7ce8cf`) and
`fork/healbot-fork.patch` regenerated as `git diff 7534d23 6794bd581`, verified to apply cleanly
to base `7534d23`.

What changed: the double-retire race was closed by removing the second writer, not by narrowing a
window — the grid's `x` writes `metadata.healbot.retireRequested` and the server plugin performs
every retirement, which deleted ~180 lines and the `handoffDocument` twin from `healbot.tsx` and
shrank `GridClient` from ten members to three. `consider()` now claims `busy` synchronously before
its first await. `retire()`'s todo read throws instead of `.catch(() => [])`, which used to make a
failed read look identical to "no open todos" and archive a session with no successor. And the
review found the gate fires per STEP, not per turn: the shipped behaviour was kept (it is the
better one) and the prose was brought to it, leaving `RETIRE_HARD` documented as dead rather than
deleted — which is decision 1a above.

Free suite: 4/4, 10/10, 24/24, 10/10, 14/14, 23/23, 15/15, 9/9. `probe_twin.py` was rewritten (it
no longer compares two handoff documents, because there is only one) and `probe_request_channel.py`
is new, free, and TESTED to fail. Paid results are unchanged from Phase 6 and listed in the rig
README.
