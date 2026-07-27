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
overlay is pinned at 36f674109.

READ FIRST, in this order. Stop when you can name the file that owns any given behaviour:
  1. HARNESS.md          — root index: load-bearing facts, Traps, Closed, Still open
  2. docs/RELAY.md       — Phase 7: retirement collapsed into ONE implementation (the server
                           plugin); the grid's `x` became a REQUEST written to
                           `session.metadata.healbot.retireRequested`; the gate was found to fire
                           per STEP, was made per TURN, `RETIRE_HARD` was DELETED, and the
                           threshold came down 256,000 -> 180,000 as the direct consequence
  3. .carryover/verified/README.md — the test rig and its assertion discipline

Do NOT read the whole tree first. HARNESS.md indexes everything; follow it on demand.

YOUR TASK — Phase 8. Every step of the build order is built and no known correctness hole is
open. What is left is ONE decision that is mine to make, some verification that was never
re-run, and one optional spend. Do not invent a ninth thing to build.

  1. ASK ME THE DECISION IN YOUR FIRST MESSAGE, then do 2 while you wait. It is not a bug; it is
     policy; it is small once decided. Present the branches, do NOT pick for me.

     The startup sweep. `consider()` (`plugin/healbot.ts:612`) has one call site, there is no
     polling, so a server restarting with a session already over the gate does nothing until
     that session's next event — then the gate catches it at the end of that turn. A sweep at
     boot would close it properly and is small — list sessions, call the same `consider()`. It is
     not built because a restart triggering mass retirement is a policy choice, not a defect.
     Tell me which behaviour I want; the code is the easy part.

  2. FREE while you wait. All three are open questions, not builds.
     - IS ~170K THE TAIL OR THE MIDDLE? `RETIRE_AT` = 180,000 is derived, not chosen: with one
       gate the requirement is `RETIRE_AT + worst_turn < ceiling`, ceiling ~360K, and
       `worst_turn` is ~170K — ONE measurement, one turn, `docs/HARDEN.md` §6 (occupancy 5,216 ->
       70,898 on a single tool result, that turn finishing at 175,090). A second measurement
       moves the number in either direction. The material is already on disk and costs nothing:
       the session databases under `.carryover/verified/hb/*.db` (`retire350.db` is the largest,
       104 messages to 359,829). Sample the largest single-turn occupancy DELTAS — group
       assistant messages into turns with `turnFinished()`'s rule, not per message — and report
       the distribution. If ~170K is the p50 rather than the max, 180,000 is too high.
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

  4. PAID and OPTIONAL — the gate has still only been exercised at 20,000. Half of it is closed
     for free: probe_headless_arm.py asserts the SHIPPED 180,000 default actually arms
     (`:176-177`), paired with the opposite assertion that the override's gate value is ABSENT
     from that same line (`:187`). What remains unbought is FIRING at the real value, and the
     comparison is a single `>=`. If you want it: verify_retire_350k.py's growth-loop workload
     (70 x 35 KB chunks) retargeted to 180,000 — it already pops HEALBOT_RETIRE_AT and asserts
     its absence. The costing in .carryover/verified/README.md was derived for a 256,000 target;
     180,000 is fewer turns and less cumulative context, so it is CHEAPER — re-derive it there
     before you spend, do not quote the old figure. 180,000 is comfortably under the provider's
     272,000 context tier, which DOUBLES every rate, so base rates hold throughout. NOT via
     verify_headless_retire.py: `THRESHOLD = 20_000` (`:52`) is a bare literal it hands the
     server via `env_extra`, which `rig.serve()` applies LAST; its workload is one prompt capped
     at 50 KB by `read.ts:16` and it asserts `len(user_turns) == 1`. At 180,000 the gate never
     fires and the 900s wait times out. ASK ME FIRST.

  5. NOT YOURS — Phase 3's exit gate, `/code-review ultra` on the `harness/` diff, is still
     unmet. It is user-triggered and billed; an agent session cannot launch it. Remind me.

METHOD — this project's standard, and it is not decoration:
  - Classify every claim VERIFIED (read code, cite file:line) / TESTED (ran it) / INFERRED /
    SUSPECTED. Never present a lower tier as a higher one. Cite file:line and open the file.
  - This suite's characteristic failure is PASSING. Every new assertion needs a negative
    control or a mutation check — prove it can fail before you trust it green. Phase 7's
    probe_turn_predicate.py re-runs its whole table against the OLD per-step predicate and
    requires it to FAIL, which it does on 4 cases; probe_request_channel.py was TESTED to fail by
    renaming REQUEST_KEY in the plugin (9/9 -> 5/9, exactly the four channel assertions). Phase 7
    also found an assertion that passed on an empty list, and Phase 6 caught three of its own.
  - Run the FREE probes before spending anything:
      cd .carryover/verified
      venv/bin/python probe_on_grid.py          # 4/4
      venv/bin/python probe_error_state.py      # 10/10
      venv/bin/python probe_focus.py            # 24/24
      venv/bin/python probe_fleet.py            # 10/10
      venv/bin/python probe_control_wiring.py   # 14/14
      venv/bin/python probe_twin.py             # 23/23
      venv/bin/python probe_headless_arm.py     # 14/14
      venv/bin/python probe_request_channel.py  # 9/9
      venv/bin/python probe_turn_predicate.py   # 18/18
    The credit-spending rigs are listed in .carryover/verified/README.md.
  - Gates before you claim done, from ~/Desktop/healbot/opencode:
      ./node_modules/.bin/tsgo --noEmit -p packages/tui/tsconfig.json    # expect exit 0, no output
      ./node_modules/.bin/oxlint packages/tui/src/feature-plugins/system/healbot.tsx
                                                                        # expect exit 0, 3 warnings
  - Every phase revises the artifacts it contradicts. Write docs/<PHASE>.md, update HARNESS.md,
    and fix any figure you disprove. Do not leave a stale number in a file that another session
    will trust. Phase 7 rewrote three documents and one rig because one claim about the gate
    turned out to be backwards — and then rewrote them AGAIN when the decision reversed.

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
  - EVERY COMPLETION-LOOKING FIELD ON AN ASSISTANT MESSAGE IS SET PER **STEP**. `finish` is
    assigned at every `step-finish` in the same mutation as `tokens` (`processor.ts:443-445`,
    and `:445` is the only site writing a non-zero `tokens`), and `time.completed` is set per
    step in `cleanup()` (`processor.ts:595-596`). MEASURED on 733 real assistant messages with
    occupancy > 0: 677 carried `finish: "tool-calls"` — mid-turn — and zero carried a null
    `finish`. So any new code that reads either field directly to mean "the turn is over" is
    wrong, and that exact defect survived two phases while five artifacts asserted the opposite.
    `turnFinished()` (`plugin/healbot.ts:346-349`) is the only correct reader: it is opencode's
    own predicate, `prompt.ts:1295`, and it deliberately ignores `time.completed`.
    probe_turn_predicate.py evaluates the real source text against the measured distribution.
  - THE GATE AND THE THRESHOLD ARE COUPLED — you cannot move one without the other. Per-turn
    semantics with a single gate means the session accepts whatever the in-flight turn adds
    (~170K measured worst case) before anything happens, against a ~360K ceiling. That is why
    `RETIRE_AT` is 180,000 (`plugin/healbot.ts:135`, `healbot.tsx:57`) and why anything at or
    above ~190,000 can be carried off the cliff by one ordinary read-heavy turn. Raising it
    without restoring a second, mid-turn gate silently reintroduces the exact failure
    `RETIRE_HARD` was drawn to catch — and `RETIRE_HARD` is gone: the constant, the guard, the
    env var and its half of the arming log line were all deleted, not disabled.
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

**The one decision goes first because it is mine, not the agent's, and because everything else in
the phase is independent of it.** Asking it in the first message costs one round trip and unblocks
the rest; asking halfway through stalls a session that has already spent context.

This section used to carry a second decision, `RETIRE_HARD` — delete it or resurrect it — and it
warned that the failure mode was an agent making the harness per-turn and trading a ~65K overshoot
for a ~170K one. **Both halves are now settled and the warning is obsolete.** The predicate was
made per-turn (`turnFinished()`, opencode's own), `RETIRE_HARD` was deleted outright, and because
that combination reintroduces exactly the overshoot the hard gate existed to bound, the soft
threshold came down with it: 256,000 -> 180,000. What the decision left open is narrower and now
sits in the free block — `worst_turn` ~170K is a single data point, and the whole derivation rests
on it.

**2 is free and 3 is nearly free, so they precede anything billed.** `verify_control_agent.py` is
the only rig in the suite whose recorded score does not correspond to an execution of the file as
it stands; its assertion has now been rewritten twice without a run, which is exactly the state
this suite punishes.

**4 is last because half of what it used to buy is now free.** `probe_headless_arm.py` asserts the
shipped default arms, and asserts the negative in the same run. What money buys is the firing half
at the real value, over a `>=` already exercised at 20,000. The prompt does not quote a price: the
one in the rig README was derived against a 256,000 target and 180,000 is cheaper, so it needs
re-deriving rather than copying.

Deliberately **not** in the prompt:

- **Worktree isolation** (build-order step 7). `PLAN.md` marks it optional and nothing needs it.
- **The remaining grid traps** — RED silent under `--auto`, archived sessions never leaving the
  list. They are review-tier rows in `HARNESS.md`; the index carries them and the prompt does not
  need to.

## Current state, for the maintainer of this file

Phase 7 landed with the overlay re-pinned at fork **`36f674109`** (was `88f7ce8cf`, then briefly
`6794bd581` — this file named that intermediate commit and it was wrong) and
`fork/healbot-fork.patch` regenerated as `git diff 7534d23 36f674109`, verified to apply cleanly
to base `7534d23`.

What changed: the double-retire race was closed by removing the second writer, not by narrowing a
window — the grid's `x` writes `metadata.healbot.retireRequested` and the server plugin performs
every retirement, which deleted ~180 lines and the `handoffDocument` twin from `healbot.tsx` and
shrank `GridClient` from ten members to three. `consider()` now claims `busy` synchronously before
its first await. `retire()`'s todo read throws instead of `.catch(() => [])`, which used to make a
failed read look identical to "no open todos" and archive a session with no successor. And the
review found the gate fired per STEP, not per turn: the first decision kept the shipped behaviour
and rewrote the prose to match (committed as `5bcdeab`), then reversed — the predicate is per-turn,
`RETIRE_HARD` is deleted, and `RETIRE_AT` defaults to 180,000 in both the plugin and the grid.

Free suite: 4/4, 10/10, 24/24, 10/10, 14/14, 23/23, 14/14, 9/9, 18/18. `probe_twin.py` was
rewritten (it no longer compares two handoff documents, because there is only one) and now asserts
`HEALBOT_RETIRE_HARD` is absent from BOTH files; `probe_headless_arm.py` lost its hard-gate
assertions and gained the 180,000 pair; `probe_request_channel.py` and `probe_turn_predicate.py`
are new, free, and TESTED to fail. Paid results are unchanged from Phase 6 and listed in the rig
README.
