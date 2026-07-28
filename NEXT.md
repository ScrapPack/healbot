# NEXT — the prompt for a fresh session

Paste the block below into a new agent session at `~/Desktop/healbot`. Everything else in this
file is context for whoever maintains the prompt; the agent only needs the block.

The prompt is short on purpose. This project's method is that a phase reads the written
artifacts, never the prior transcript — and the project exists to cut standing context, so a
handoff that pastes ten thousand words of history is working against its own premise.

---

## The prompt

```
Continue the healbot build at ~/Desktop/healbot. Phase 8 is complete and committed; the fork
overlay is pinned at 509f4c0b1 (unchanged — Phase 8 built nothing in the fork).

READ FIRST, in this order. Stop when you can name the file that owns any given behaviour:
  1. HARNESS.md          — root index: load-bearing facts, Traps, Closed, Still open
  2. docs/GROWTH.md      — Phase 8: `worst_turn` was ONE measurement and it was not the worst.
                           Re-derived from 86 real turns, the pinned model's worst is 175,148, so
                           the bound on RETIRE_AT is 184,852 and the shipped 180,000 clears it by
                           1.3% of the ceiling. The threshold is now MODEL-SPECIFIC. Also:
                           `healbot_*: deny` is a context control and NOT a sandbox
  3. docs/RELAY.md       — Phase 7: retirement collapsed into ONE implementation (the server
                           plugin), the gate made per-TURN, RETIRE_HARD deleted, threshold
                           256,000 -> 180,000. GROWTH.md corrects one figure in it, not its shape
  4. .carryover/verified/README.md — the test rig and its assertion discipline

Do NOT read the whole tree first. HARNESS.md indexes everything; follow it on demand.

YOUR TASK — Phase 9. Everything in the build order is built and every known correctness hole is
closed. Phase 8 closed three open questions and took two decisions, so there is NO decision
pending on me this time and nothing is blocking you. Do not invent something to build.

  0. TWO THINGS ARE DECIDED. Do not re-open either as a defect, and do not "fix" them.
     - RETIRE_AT STAYS AT 180,000. Phase 8 re-derived the worst_turn that sizes it (175,148 on the
       pinned model, so the bound is 184,852, margin 1.3% of the ~360K ceiling) and offered four
       options; the answer was leave it and correct the prose, which is done. What that ACCEPTS is
       written down in docs/GROWTH.md §1 and is inherited knowingly.
     - NO STARTUP SWEEP. Retirement stays purely event-driven. A session parked over the gate when
       a server restarts stays there until its next turn ends. Decided in Phase 8, §5.
     The one LIVE constraint out of all that: RETIRE_AT is verified only while opencode.jsonc:16
     pins gpt-5.6-sol. probe_turn_growth.py asserts the pin.

  1. FREE, and start here — Phase 8's free work was worth more than anything paid.
     - Re-run the ten free probes (below). probe_turn_growth.py is new; if its corpus figures
       have moved, something changed under it and that is itself the finding.
     - The suite has never been run from a FRESH CLONE. rig.fixtures() and rig.db() were built in
       Phase 5 for exactly that, and probe_turn_growth.py newly depends on a file OUTSIDE the
       repo (~/.local/share/opencode/opencode.db) which it treats as optional and prints NOT
       EXERCISED for. Nobody has checked that claim by actually removing it.

  2. PAID and OPTIONAL — the 180,000 gate has still never been FIRED at its real value. Half is
     closed free (probe_headless_arm.py asserts the shipped default arms; probe_turn_predicate.py
     the predicate) and the remaining half is a single `>=` already exercised at 20,000. Costed at
     ~$2.60, range $1.75-5, ~6-11 min in .carryover/verified/README.md. OFFERED IN PHASE 8 AND
     DECLINED, on the grounds that a `>=` against a variable is threshold-independent by
     inspection — so do not put it at the top of the list, but it is still the cheapest paid thing
     available. NOT via verify_headless_retire.py: THRESHOLD = 20_000 (`:52`) is a bare literal it
     forces into the server via env_extra, which rig.serve() applies LAST, and its workload is one
     prompt capped at 50 KB by read.ts:16. Use verify_retire_350k.py's growth loop retargeted.
     ASK ME FIRST.

  3. ALSO PAID and OPTIONAL — an EXTERNAL plugin's route has never been RENDERED. Phase 8 settled
     *can it* at VERIFIED (same PluginEntry, same activation loop, same pluginApi; the only
     `source` discrimination in the path is a metadata display field) but not *does it, under a
     real workload*. Everything TESTED in this repo was measured on the builtin path.

  DO NOT remind me about `/code-review ultra`. It has been run. HARNESS.md and two phase docs
  still carry it as an open row; leave them, that is deliberate and it is my business, not a
  documentation defect for you to tidy.

METHOD — this project's standard, and it is not decoration:
  - Classify every claim VERIFIED (read code, cite file:line) / TESTED (ran it) / INFERRED /
    SUSPECTED. Never present a lower tier as a higher one. Cite file:line and open the file.
  - This suite's characteristic failure is PASSING, and every phase since 5 has caught more
    instances of it — Phase 8 caught three, including a rig comment that had asserted an
    impossibility since the day it was written and was disproved the first time anything ran
    against it. GREEN IS NOT EVIDENCE UNTIL YOU KNOW WHAT WOULD HAVE MADE IT RED. Every new
    assertion needs a negative control or a mutation check. An assertion about ORDERING needs a
    workload that could have violated it.
  - AND THE CONVERSE, which is Phase 8's addition: A FAILING ASSERTION NEEDS THE SAME SCRUTINY AS
    A PASSING ONE. probe_turn_growth.py's first run reported a red derivation, and before that
    could be written down it had to survive "is this an artifact of my grouping?" — an
    unterminated turn mid-session would make the next delta span two turns and inflate it. It was
    not. The check is why the number can be quoted.
  - A NUMBER IS NOT EVIDENCE, AND REPEATING IT DOES NOT MAKE IT MORE EVIDENCE. `~170K` appeared in
    five files and was one turn measured once, and the derivation that sized the shipped threshold
    treated it as a bound. Re-deriving it cost nothing.
  - Run the FREE probes before spending anything (141/141 total):
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
      venv/bin/python probe_turn_growth.py      # 15/15
  - Gates before you claim done, from ~/Desktop/healbot/opencode:
      ./node_modules/.bin/tsgo --noEmit -p packages/tui/tsconfig.json    # expect exit 0, no output
      ./node_modules/.bin/oxlint packages/tui/src/feature-plugins/system/healbot.tsx
                                                                        # expect exit 0, 3 warnings
  - Every phase revises the artifacts it contradicts. Write docs/<PHASE>.md, update HARNESS.md,
    fix any figure you disprove. Phase 8 corrected the same number in five files.

TRAPS — all measured, all in HARNESS.md, repeated because each silently produces a wrong belief
rather than an error:
  - The installed `opencode` binary has NO grid. Run from source: rig.py's OC constant, or
    harness/fleet.sh.
  - RETIRE_AT IS ONLY VALID FOR THE PINNED MODEL. `worst_turn` is a fact about a MODEL's
    tool-calling behaviour, not about opencode. The pinned gpt-5.6-sol's worst turn is 175,148;
    the same corpus has 223,258 on gpt-5.6-terra. Changing opencode.jsonc:16 silently un-verifies
    the threshold — probe_turn_growth.py asserts the pin so it goes red instead.
  - `healbot_*: deny` SCOPES CONTEXT, NOT CAPABILITY. TESTED: the build agent, with all five tool
    definitions removed from its payload, ran `opencode run --auto ...` through bash and created a
    real top-level session. The CLI is on PATH in the tool sandbox and talks to the same DB. Do
    not build anything on the assumption that a denied agent cannot reach a capability.
  - AN EXTERNAL TUI PLUGIN CAN SILENTLY REPLACE THE GRID. Internal plugins are added before
    external ones and the route map is last-wins (`plugin/api.ts:33-35`), which the activation
    loop's own comment states. A third-party plugin registering `healbot` wins, with no error and
    no log line. The name is neither pinned nor reserved.
  - EVERY field that looks like "the turn is over" on an assistant message is set per STEP:
    `finish`, `time.completed` (processor.ts:443, :445, :595-596; a new message per step at
    prompt.ts:1186-1201). turnFinished() is the only correct reader; prompt.ts:1295 is why.
  - THE GATE AND THE THRESHOLD ARE COUPLED. Per-turn with no second gate means RETIRE_AT must stay
    below 184,852 on the pinned model. Raising it without restoring a hard gate silently
    reintroduces the cliff.
  - RETIREMENT HAPPENS IN EXACTLY ONE PROCESS. The grid's `x` only writes
    metadata.healbot.retireRequested. Without the harness config loaded, `x` looks like it worked
    and nothing retires — and the coupling is untyped in both directions.
  - Automatic retirement is a SERVER plugin. Thresholds are read by the SERVER process, so
    exporting HEALBOT_RETIRE_AT into a rig's own environment configures nothing. Use
    rig.serve(..., env_extra={...}) and read rig.serve(..., log=path).
  - A server plugin gets the v1 SDK client, the TUI gets v2, and they diverge silently. The
    generated types are NARROWER than the routes (metadata, time.archived).
  - A plugin module may export ONLY functions. One exported constant throws at load time and
    leaves a healthy server with a missing feature.
  - The rig's Api MUST send `x-opencode-directory`, or you address a different instance and the
    grid shows `0 sessions` while every call succeeds.
  - The rig's project dir needs its own git repo (rig.git_baseline()) or every changed file is
    invisible to the diff machinery.
  - Never set XDG_DATA_HOME. auth.json lives there and OpenAI is on oauth. Isolate the DB only.
  - Term.find() is case-INSENSITIVE and the project path contains "healbot". Use rig.on_grid()
    and t.exact().
  - The session-route sidebar is gated on width > 120 and is the only thing rendering a session
    id. The navigation rigs use exactly 120, so a focus assertion there measures geometry.
  - Session ids are DESCENDING identifiers, so ascending sort is newest-first.
  - The context ceiling is ~360K, NOT the 922,000 limit.input the model registry advertises.

Ask me before spending real API credits on anything beyond a few turns.
```

---

## Why this order

**For the first time since Phase 5 there is no decision of mine at the top.** Phase 7's was the gate
semantics, Phase 8's was the startup sweep *and* the threshold, and both of Phase 8's were taken in
the same session that raised them. So the prompt opens with a **§0 of things already decided**
instead of a question. That section is doing real work: two of the three decisions on record were
originally written up as open questions, and the failure mode now is a fresh session treating a
settled policy as a bug and "fixing" it.

**1 is free, and Phase 8 is the argument for putting it first.** Everything of value that phase
produced — the re-derived `worst_turn`, the model-specificity constraint, two open questions closed,
one disproved rig premise — cost nothing but reading. The only paid work was a rig re-run that had
been queued for two phases, and even that earned its money by *failing*.

**2 and 3 are last because they are confirmations, not discoveries.** The `>=` at 180,000 has been
exercised at 20,000; the external route has been VERIFIED at source. Both buy a tier upgrade on a
claim already believed, which is the least interesting thing money can do here — and 2 was offered
to the owner in Phase 8 and declined on exactly that reasoning.

**The `/code-review ultra` reminder is gone from the prompt, and the open rows it referred to are
not.** The review has been run. The Still-open rows in `HARNESS.md`, `docs/RELAY.md` §5 and
`docs/GROWTH.md` §6 still describe the Phase 3 exit gate as unmet and still say an agent session
cannot launch it — that is stale, knowingly, and the owner's call to leave. The prompt carries an
explicit instruction not to touch them, because the alternative is every fresh session either
nagging about a completed review or "correcting" a row it has no evidence about. Whoever next
reconciles the gate should do it from the review's own findings, not from this file.

Deliberately **not** in the prompt:

- **Worktree isolation** (build-order step 7). `PLAN.md` marks it optional and nothing needs it.
- **The startup sweep and the threshold**, except as §0's do-not-reopen list. Both DECIDED in
  Phase 8: no sweep, and `RETIRE_AT` stays at 180,000. Re-opening either as a defect is the
  specific mistake this handoff is shaped to prevent.
- **The remaining grid traps** — RED silent under `--auto`, archived sessions never leaving the
  list. Review-tier rows in `HARNESS.md`; the index carries them.

## Current state, for the maintainer of this file

Phase 8 changed **no fork code** — the overlay stays pinned at `509f4c0b1` and
`fork/healbot-fork.patch` is untouched. What changed is one new probe, one corrected rig, one new
phase doc, and the same number in five files.

What it found, in the order it found it:

- **`worst_turn` was one turn measured once**, quoted in `HARNESS.md`, `docs/HARDEN.md`,
  `docs/RELAY.md`, `harness/env.sh` and this file until the repetition looked like corroboration.
  Re-derived from 86 completed turns: ~170K is the **tail** (p50 22,152) but not the **maximum**,
  which is what the derivation used it as. Pinned-model worst 175,148 → bound 184,852, margin 1.3%.
- **The threshold is model-specific**, which nothing had said. A 223,258-token turn exists in the
  corpus on `gpt-5.6-terra`.
- **`healbot_*: deny` is not a sandbox.** Found by finally running `verify_control_agent.py`, whose
  third-form assertion failed on first execution against a premise in its own comment.
- **Two open questions closed at source, free**: the session route has no render site for a
  dismissed question's text, and an external plugin can register a route (which produced a new trap
  about last-wins route collisions).

Two decisions were taken in the same session that raised them, and both are recorded as decisions
rather than as open rows: **no startup sweep** (event-driven only) and **`RETIRE_AT` stays at
180,000** with the prose corrected. The paid 180,000 firing run was offered and **declined**.

Free suite: 4/4, 10/10, 24/24, 10/10, 14/14, 23/23, 14/14, 9/9, 18/18, **15/15** — 141 total, all
re-run after the edits. `verify_control_agent.py` moved from a recorded 15/16 that no execution
matched to a **15/15** that one does. Gates: `tsgo` exit 0 with no output, `oxlint` exit 0 with the
expected 3 warnings.
