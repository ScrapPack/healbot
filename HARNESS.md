# HARNESS.md — root index

Navigation layer for the healbot fork. One `.MAP.md` per core subsystem, living **inside**
the directory it describes. This file indexes them.

**Exit test:** from this file alone you should be able to name the file that owns any given
behavior. If you can't, the map is wrong — fix the map, not your memory.

**Naming:** map files are `<DIR>.MAP.md`. The `.MAP` infix is not cosmetic — `SKILL.md`
collides with opencode's skill-manifest glob (`**/SKILL.md`), and `AGENTS.md` / `CLAUDE.md` /
`CONTEXT.md` are auto-ingested into the model's context window
(`packages/opencode/src/session/instruction.ts:64-68`), which is the exact cost this project
exists to remove. **Never create those four filenames anywhere in this tree.**

Phase docs, newest first. The `0R` rows are a parallel track, and the two `—` rows are not
phase records:

| Doc | Phase | Read it for |
|---|---|---|
| [docs/REFUSAL-BASELINE.md](docs/REFUSAL-BASELINE.md) | 0R | **A parallel track, not part of the 0–9 build.** Measures the MODEL's own refusal by removing harness content-policy prose — except there is **none to remove**: `gpt.txt`, `build.md`, all 11 tool descriptions, `<env>`, skills and reminders are content-policy-clean on the pinned model (line-by-line + mutation-controlled grep). The strip diff is **empty**, so the refusal source is already model + provider and the number already attributes correctly. The user-safety backbone (`permission/index.ts` fail-closed `?? "ask"`, the ask-gates, the destructive-command guards) is code and untouched. The provider's server-side moderation is the **unreachable floor** on `gpt-5.6-sol`; only a self-hosted arm C (GLM/Kimi) removes it — and it is the only arm with a non-empty strip (`default.txt:15`). Set A/B design is written; running is paid and unstarted |
| [docs/REFUSAL-RESCORE.md](docs/REFUSAL-RESCORE.md) | 0R | **The null was a DETECTION gap, not a delivery gap.** The `refusal tdd-full-1` run (150 rows, banked at `bb798ff`) was a powered null — 75/75 per arm, exact McNemar p = 1.0 — with **27 rows flagged `needs_review`**. All 27 were `outcome=comply`: `ab.score()` flags exactly the branch with no declination *and* no artifact-regex match, so the flag was the scorer refusing to guess, by design. Corpus v2's regex fixes re-score those 27 → **12** over the frozen transcripts, with **zero outcome changes and zero delivery changes** — the regex only sets `has_artifact`, moving `comply+needs_review` to `comply+has_artifact`, so delivery stays 75/75 and the McNemar null is untouched. The completed run keeps its original scores: `--rescore` reads the immutable frozen corpus in the run dir, not the live file, so v2 applies to the **next** run |
| [docs/E2E.md](docs/E2E.md) | — | **Not a phase record — the documented operator path, walked start to finish for the first time (2026-08-03).** README Quickstart from a fresh clone, `hb-fleet.sh start` to an attached cockpit, two crewmates driven only through the documented verbs, the grid up to the last free keystroke, and the troubleshooting table row by row. Fourteen findings, six repaired in the same change: the `C-b ?` overlay rendered 45 rows into a 26-row box and opened on `kill`, with `start` and every verb above it off-screen; the card claimed `q` dismisses the popup and only Escape does; `term.py` could not host tmux at all (pyte rejects the private device queries tmux sends at startup) so the instrument for this walk had to be repaired before the walk could happen; and the gate's documented 2-vs-3 split does not survive a missing checkout. What it does NOT cover is named where it stops: `x` retirement is a paid model turn and the keystroke was not pressed |
| [NEXT.md](NEXT.md) | 13 | **Start here if you are a fresh session.** The prompt to continue the build, and the traps that silently produce wrong results instead of errors |
| [docs/SHIP.md](docs/SHIP.md) | 13 | **The record for the phase `NEXT.md` above continues.** Claude Code became a build driver rather than only the review/measurement engine, and the two harnesses reached config parity. It owns three traps: the `*_CONFIG_DIR` naming is **INVERTED** between the tools — opencode's `OPENCODE_CONFIG_DIR` is the additive false-isolation trap and `XDG_CONFIG_HOME` is the real switch, while Claude Code's `CLAUDE_CONFIG_DIR` IS the real switch, so reasoning by analogy in either direction configures the wrong thing silently; a fresh claude config dir is **SIGNED OUT**, because auth does not follow the redirect; and `python3 - <<heredoc` consumes stdin as the PROGRAM, so a hook reading its payload from stdin reads nothing — syntactically clean, exit 0, writes nothing. §5 carries the open items |
| [docs/OUTCOME.md](docs/OUTCOME.md) | 12 | **The box that could not fail.** `rig.py`'s `fire()` appends a turn that THREW and a turn that FINISHED in the same 3-tuple, and **no rig in the suite had ever read the element that tells them apart** — the hazard was named in `fire()`'s own docstring as `result_or_exception` and handled by nobody. TESTED: three `fire()` calls at a dead port satisfied **every** completion predicate in the suite in **9 milliseconds**. Four `r.check` rows counted threads that had stopped while claiming turns had run; **one of them had no independent evidence anywhere else in its file**. Fixed with `rig.completed()`, a transcript backstop for the file that lacked one, and **contract 6** in `probe_rig_contract.py` (22/22 → **29/29**) — whose negative control is the real pre-phase source from git, which it rediscovers all four rows in. The surface nobody had read: **the library the whole suite stands on**, which the contract probe deliberately excludes. Then paying to run one rig found three more: **`verify_question.py` has been three assertions RED since Phase 5** (27/30 — Phase 5 built auto-surface and left the assertions that assume it does not, and **Phase 10's count-the-sites reconciliation cannot see that**, because the behaviour changed and the count did not); **three paid rigs are single-use**; and **`wait_for`'s timeout does not bound** what it claims to. Finally, a 299,326-token turn took `probe_turn_growth.py` red and forced the corpus to get a **declared scope** — which showed the derivation had been answering a question the gate never asks: **all four largest turns start at ZERO**, and a turn starting at 0 cannot carry a session over the ceiling. Re-derived on turns that start near the gate, **the bound is 289,296 and the margin 30.4%, not 184,852 and 1.3%** |
| [docs/CITE.md](docs/CITE.md) | 11 | **The maps had rotted, and three of the rot was Phase 9's and 10's.** `fork/README.md` names citation rot as "drift mode 2" and had **no check for it**, so every instance was found by hand. A sweep of **930 citations** found eight stale: three past the end of `healbot.tsx` (pre-existing, off by ~140 lines) and five landing on blank lines — **three of those created by Phases 9 and 10 themselves**, which moved `## Traps`, `## Behavior → file` and a cited line in `probe_twin.py` while nothing was looking. Also: the model-pin citation was **ambiguous** and resolved to a blank line in the wrong `opencode.jsonc`; `probe_twin` was guarding **1 of the 17** overlay files; and the fork is now verified to *reproduce* from its patch, not merely to apply. New guard `probe_citations.py` (14/14) |
| [docs/VERDICT.md](docs/VERDICT.md) | 10 | **Six paid rigs printed the verdict and threw it away.** `finally: r.summary(); t.close()` — no `sys.exit`, so a failing run exited **0**. Among them `smoke.py`, the provider check the README says to run first, and `verify_surface.py`, which carried a **permanently-red assertion for five phases** because nothing ever surfaced it. Phase 9 had fixed the free probes only. Also: **`verify_handoff.py`'s recorded 21/21 is unreachable** — it holds 22 unconditional assertions since Phase 5 edited it, and four documents cite that score as the Phase 4 exit gate's evidence; and Phase 8's *"the one rig in the suite"* claim was **two** rigs. New free guard `probe_rig_contract.py` (22/22 at the time; 29/29 across 24 entrypoints since Phase 12) asserts the contract from source (itself included) so none of it grows back |
| [docs/CLONE.md](docs/CLONE.md) | 9 | **The suite could not tell "everything passed" from "almost nothing ran."** Run from a FRESH CLONE for the first time, three probes reported success — `2/2`, `7/7`, and `1/1` *after a 90-second timeout* — all exit 0, all having proven nothing. Two escape routes: `sys.exit()` in a `finally` discards the exception, and `wait_for()` times out without raising. Worse: `probe_turn_growth.py`'s two load-bearing assertions get **easier** as their evidence disappears, reporting the gate clearing its ceiling by **48.2%** instead of 1.3% — in green — because `worst_turn = 175,148` lives only in the gitignored `hb/*.db`. Fixed with an assertion floor and a corpus fixture check, both controlled in both directions. Plus: the real corpus is REQUIRED, not "optional" as its own docstring said; and the corpus moved 86 → 94 turns because **the suite writes to the corpus it measures** — with every load-bearing figure unchanged |
| [docs/GROWTH.md](docs/GROWTH.md) | 8 | **`worst_turn` was one measurement and it was not the worst.** Re-derived from every session DB on disk: the pinned model's true worst turn is **175,148**, so the gate's own ceiling is **184,852**, not ~190,000 — and the shipped 180,000 clears it by 1.3% of the context ceiling. Off the pinned model the corpus holds a **223,258** turn, which makes `RETIRE_AT` **model-specific** for the first time. Plus: `healbot_*: deny` is a context control and NOT a sandbox (the build agent shelled out to `opencode run`), and two open questions closed for free at source |
| [docs/RELAY.md](docs/RELAY.md) | 7 | **The gate was never per-turn — so it was made per-turn.** `finished()` read a per-step field, so the gate fired mid-turn and the second gate `RETIRE_HARD` was inert. The predicate is now opencode's own (`prompt.ts:1295`), the hard gate is **deleted**, and `RETIRE_AT` came down to **180,000** to carry the margin the deleted gate used to. Plus the double-retire race closed by deleting the grid's copy of `retire()`: `x` now relays a request and the server plugin is the only implementation |
| [docs/HEADLESS.md](docs/HEADLESS.md) | 6 | Automatic retirement moved to a **server** plugin so it runs with no client attached — and why "move it to plugin scope" was the wrong mechanism for the right goal. Plus focus and `question.rejected` closed, and the control agent built |
| [docs/HARDEN.md](docs/HARDEN.md) | 5 | The Phase 4 audit and what it forced: six defects fixed, the rig's vacuous assertions replaced, and `serve` + `attach` built — which closed the cold-start reconcile that was recorded here as *blocked* |
| [docs/VERIFY.md](docs/VERIFY.md) | 4 | The control terminal, verified on `gpt-5.6-sol`: answering a blocked session from the grid. What is TESTED, what is unreachable, and why the first attempt was void |
| [docs/REVIEW.md](docs/REVIEW.md) | audit | **Read this before trusting any figure below.** Adversarial audit of every phase-0–3 assumption; what held, what did not |
| [docs/STRIP.md](docs/STRIP.md) | 3 | The strip: what was cut, what it measures, how to run the harness |
| [HARNESS.md](HARNESS.md) | 2 | This file |
| [docs/SCAN.md](docs/SCAN.md) | 1 | Architecture scan. **§4's cost table is superseded** — see REVIEW |
| [docs/PROBE.md](docs/PROBE.md) | 0 | Empirical probes F1–F7; the architecture proof |
| [docs/AFK.md](docs/AFK.md) | — | **Not a phase record — a specification for running this repo AFK under `gnhf` 0.1.43**, written 2026-07-31 against `76b23cc`. No loop was run and nothing in this repo was modified, so every claim carries its tier and the appendix names what is INFERRED and what is NOT MEASURED rather than letting the reader assume. One constraint from it is live and belongs where it will be seen: **use `--agent claude`, and do not run gnhf's opencode backend while the refusal study can start** — both bind local ports and both write session DBs. SUSPECTED collision, not measured, and judged high-stakes enough to avoid rather than test |
| [PLAN.md](PLAN.md) | — | **Superseded in parts and never revised.** §1 and §4 describe an Ink/PTY architecture that F7 replaced, and §0.1's switch table has false rows. It carries a rev-4 errata header; read that first |

## The deliverable

`harness/` is the thing this project actually ships. It is not in the map table below because
it is not part of the fork.

```sh
. ~/Desktop/healbot/harness/env.sh   # zsh or bash only — it guards and refuses elsewhere
opencode
```

For a **fleet** — one long-lived server, the control terminal as a client, sessions that outlive
the terminal — use `fleet.sh` instead. It is the architecture `PLAN.md` assumed all along:

```sh
~/Desktop/healbot/harness/fleet.sh [project-dir] [port]   # default port 4096
```

| File | Owns |
|---|---|
| `harness/env.sh` | The switch set. `XDG_CONFIG_HOME` isolation + the skill switch + the claude-code switch, each with its measured justification and a NOT-SET list of the switches that break things. Also the retirement knob: `HEALBOT_RETIRE_AT`, **default 180,000 and the only gate**, with the derivation written out. `HEALBOT_RETIRE_HARD` was deleted in Phase 7 and the file says so — if it is still in a shell profile it reads nothing |
| `harness/fleet.sh` | `opencode serve` + `opencode attach`: sessions survive the terminal, and the cold-start reconcile becomes reachable. TESTED 10/10 end to end, plus 21/21 on the reconcile itself (`docs/HARDEN.md`). Resolves the fork checkout automatically — the released binary has no grid |
| `harness/config/opencode/opencode.jsonc` | Model pin, `compaction.auto=false` and why, plugin registration, and the global `healbot_*: deny` that keeps the control tools out of every other session's prompt |
| `harness/config/opencode/agent/build.md` | The 1,715 B prompt that *replaces* `gpt.txt` |
| `harness/config/opencode/agent/control.md` | **The control agent** — build-order step 5. `mode: primary`, and the `healbot_*: allow` that wins back the globally denied tools. TESTED 14/14 + 15/16 (`docs/HEADLESS.md` §3) |
| `harness/config/opencode/plugin/healbot.ts` | **ALL retirement, and the control tools.** Since Phase 7 this is the only implementation of retirement anywhere: the automatic gate, the operator's `x` (relayed as a metadata request), and `healbot_retire` all run the same `retire()` in this one process. It runs headless, so a fleet with no client attached still retires. TESTED 20/20 end to end with no TUI in the process table (`docs/HEADLESS.md`), plus 9/9 on the relay (`docs/RELAY.md`) |
| `harness/config/opencode/plugin/trim-tools.ts` | Tool-description trimming. Ships OFF (`HARNESS_TRIM_TOOLS=1`) |
| `harness/pool.py` | **Pooled worktree slots** — provision once, lease many times. A bare worktree is measured-broken here (tracked files only; the 2.8G checkout, node_modules and venv are all untracked), so a slot = detached worktree + APFS-clonefile'd payload (~35s, ~zero marginal disk — a 1G `cp -c` cost no free space, TESTED 2026-07-31). Durable lease files with owner/purpose/lease_id, conditional release, and a release refusal that protects BOTH uncommitted changes and commits made on the detached HEAD (clean by `git status`, orphaned by reset — the push review caught it); per-slot acceptance (the slot's own gate + a server booted from the slot's checkout) before it may lease, re-verified and repaired on every `provision`. Treehouse's lease design with its hygiene model inverted — the untracked payload is the value, not dirt. Booting probes must not run in two slots concurrently (fixed ports; the file's docstring records it) |

Three more files exist on disk (`.gitignore`, `package.json`, `package-lock.json`) and are
**untracked** — opencode seeds a self-ignoring `.gitignore` into any config dir at boot
(`config/config.ts:297-303`), which is the "config loading mutates your disk" trap firing on
our own deliverable. A fresh clone gets the harness without its dependency manifest.

---

## The maps

The maps live at [`fork/`](fork/README.md) — the overlay of everything this project contributes
to its opencode checkout (17 files, plus the exact patch against base `7534d23`, v1.18.5). The
checkout itself is at `opencode/` and is gitignored: it is derived, and
[`fork/README.md`](fork/README.md) says how to rebuild it. Links below point at the overlay, so
they resolve here and on GitHub; the same files sit at the matching paths inside the checkout.

### Harness surface — what enters a session

| Map | Owns |
|---|---|
| [config/CONFIG.MAP.md](fork/packages/opencode/src/config/CONFIG.MAP.md) | Config ingress and merge order; `ConfigPaths.directories()`; the env switches; why `OPENCODE_CONFIG_DIR` does **not** isolate |
| [skill/SKILL.MAP.md](fork/packages/opencode/src/skill/SKILL.MAP.md) | Skill discovery across the two external trees; the dedup race; the `/<skill>` permission bypass |
| [command/COMMAND.MAP.md](fork/packages/opencode/src/command/COMMAND.MAP.md) | Command registry. Mostly a *projection of skills* — "20 commands" is 2 builtins + 18 skills |
| [agent/AGENT.MAP.md](fork/packages/opencode/src/agent/AGENT.MAP.md) | The seven built-in agents; which are structural (`build`, `compaction`) vs cuttable |

### Model-facing cost — where the tokens go

| Map | Owns |
|---|---|
| [session/SESSION.MAP.md](fork/packages/opencode/src/session/SESSION.MAP.md) | System-prompt assembly, session lifecycle, compaction, status events. The v1 engine |
| [tool/TOOL.MAP.md](fork/packages/opencode/src/tool/TOOL.MAP.md) | Tool registry and per-tool description costs — **the largest single token line item** |
| [permission/PERMISSION.MAP.md](fork/packages/opencode/src/permission/PERMISSION.MAP.md) | Permission model; which denies actually remove a tool schema |
| [plugin/PLUGIN.MAP.md](fork/packages/opencode/src/plugin/PLUGIN.MAP.md) | Server plugin host; the 21 hooks and which have live trigger sites |

### Control terminal — where healbot is built

| Map | Owns |
|---|---|
| [tui/TUI.MAP.md](fork/packages/tui/TUI.MAP.md) | The TUI package: SolidJS + OpenTUI, `app.tsx` structure, routes, slot render sites |
| [tui/context/CONTEXT.MAP.md](fork/packages/tui/src/context/CONTEXT.MAP.md) | `sync.tsx` all-session store, sdk, theme, route, event. **The grid's data source** |
| [tui/plugin/PLUGIN.MAP.md](fork/packages/tui/src/plugin/PLUGIN.MAP.md) | TUI plugin runtime: `route.register`, the `api.state` bridge, slots |
| [tui/feature-plugins/FEATURE-PLUGINS.MAP.md](fork/packages/tui/src/feature-plugins/FEATURE-PLUGINS.MAP.md) | Builtin plugins. `diff-viewer` = route pattern, `notifications` = state discriminator |

### v2 tree and public contract

| Map | Owns |
|---|---|
| [core/session/SESSION.MAP.md](fork/packages/core/src/session/SESSION.MAP.md) | The v2 engine; `projector.ts` token accumulation; v2 compaction |
| [plugin/src/PLUGIN-API.MAP.md](fork/packages/plugin/src/PLUGIN-API.MAP.md) | The **public** plugin contract — `TuiPluginApi`, server hooks. What healbot is built against |

---

## Behavior → file

| To find… | Go to |
|---|---|
| why a skill/command appears at all | `skill/SKILL.MAP.md` → `command/COMMAND.MAP.md` |
| what text the model receives before you type | `session/SESSION.MAP.md` (assembly chain) + `tool/TOOL.MAP.md` |
| how to cut standing token cost | `tool/TOOL.MAP.md` (biggest), then `agent/AGENT.MAP.md` (prompt replacement) |
| how config is loaded / how to isolate it | `config/CONFIG.MAP.md` |
| session token accounting / the retirement trigger | `core/session/SESSION.MAP.md` + `session/SESSION.MAP.md` |
| what drives a grid border color | `tui/context/CONTEXT.MAP.md` (store) + `session/SESSION.MAP.md` (event origins) |
| how to register the grid route | `tui/plugin/PLUGIN.MAP.md` + `plugin/src/PLUGIN-API.MAP.md` |
| what to copy when building the grid | `tui/feature-plugins/FEATURE-PLUGINS.MAP.md` |

---

## Load-bearing facts

Established across phases 0–2. Each is cited in the map named.

**Architecture.** The grid is a plugin-registered **route**, not an `app`-slot overlay and not
a separate app (`tui/plugin`). Focus is `api.route.navigate("session", {sessionID})` — no PTY,
no Ink, no suspend/resume. Proven by a running spike (PROBE F7), and now **built**:
`feature-plugins/system/healbot.tsx` landed at fork `26c9316` and retired the spike. **Byte and
line counts are deliberately not quoted here** — they were stated three times across this repo
and all three were stale within a day. `wc` the file.

**Answering from the grid works — TESTED, and it is the feature the project exists for.** Four
sessions on one server, three finishing real tool-using turns in 6.1 s wall while the fourth sat
blocked; `a` docks the session route's own `PermissionPrompt` / `QuestionPrompt` **below** the
grid, which keeps rendering; the reply clears the block server-side *and* the answer reaches the
model, which resumes and acts on it. The route never changes. Same result for a `question` the
model chose to ask unforced. See `docs/VERIFY.md`.

**Grid keybindings must be `OPENCODE_BASE_MODE` + `enabled: !answering()` — both, not either.**
`mode` is a *require*-condition (`keymap.tsx:56-60`), so a mode-less binding set is live in
**every** mode. `QuestionPrompt` pushes its own mode and binds `tab/h/l/j/k/return/escape` plus
digits (`question.tsx:129-134, :227-264`); `PermissionPrompt` pushes no mode and binds
`h/l/return/escape` in base mode (`permission.tsx:568-608`). Base mode handles the first,
`enabled` handles the second. TESTED under both prompts: `j/k/l/h` leave the grid cursor still.

**Concurrency — TESTED, the founding premise holds.** Four sessions fired simultaneously at one
`opencode serve` finished in 5.72s wall, exactly the slowest single turn, vs 10.45s serially.
The server does not serialize. Per-turn latency degrades under load (2.4–2.7s solo → 2.8–5.7s
at 4-way), so budget ~1.8x throughput at N=4, not 4x. And a session parked on
`permission.asked` does **not** stall the others — three concurrent sessions completed while
the blocked one hung indefinitely.

**Token accounting — the retirement trigger measures OCCUPANCY, not cumulative spend.**
Corrected; the earlier rule here was wrong for its own stated purpose.

- *Why the limit exists*: model quality degrades as the context window bloats. So the quantity
  to threshold is **how full the window is right now**, not what the session has spent over its
  life. `session.tokens` is lifetime spend and answers a different question — the reference
  101-turn session shows 652K input against 8.7M `cache.read`, which says nothing about
  occupancy.
- *What to read*: the assistant message's own `tokens` (`schema/src/v1/session.ts:472-481`),
  delivered on every `message.updated`. Occupancy is `total`, or
  `input + output + cache.read + cache.write` — the same expression `isOverflow` uses
  (`session/overflow.ts:21-33`). **`cache.read` is included**: it is the cached prompt prefix,
  and it is part of the window.
- *Headroom* — **this row was wrong and the correction is the most important number in this
  file.** It used to read: "`gpt-5.6-sol` is context 1,050,000 / `limit.input` 922,000. A 350K
  threshold leaves ~570K before the hard ceiling." **MEASURED at the shipped default: the real
  ceiling is ~360K.** A session driven up took its last successful turn at occupancy **359,829**
  and then failed **25 consecutive turns** with the provider's `ContextOverflowError` ("Your
  input exceeds the context window of this model"). The registry's 922,000 does not describe
  this provider path. Actual margin at a 350K threshold: **~10K, under 3%** — roughly one large
  tool result. Since `compaction.auto:false` disables opencode's own overflow check
  (`overflow.ts:28`), nothing catches it before the provider does, and by then the turn is lost.
  **The 350K default fired too late to be a guard.** Phase 5 lowered it to 256,000 and added a
  second HARD gate at 330,000; Phase 7 deleted that second gate and brought the one remaining gate
  down to **180,000**, which is the shipped default. The arithmetic is in the block below.
  (`docs/HARDEN.md` §6, §8; `docs/RELAY.md` §1). **Phase 8 re-derived the `worst_turn` input to that
  arithmetic from 86 real turns instead of one — see the next row.**
- *`worst_turn` was ONE measurement, and it was not the worst.* MEASURED across every session DB on
  disk (`probe_turn_growth.py`, free; the probe owns its own floor): on the pinned `gpt-5.6-sol` the worst single-turn
  growth is **175,148**, not ~170,000, so the gate's own ceiling is **184,852 — not the ~190,000
  this file, `docs/RELAY.md` and `harness/env.sh` all state.** The shipped 180,000 still satisfies
  its rule, by **4,852 tokens, 1.3% of the ceiling** — thinner than the "~10K, under 3%" margin this
  same file rejects two rows down as "too late to be a guard". ~170K is genuinely the **tail** of the
  distribution (p50 is 22,152), it just is not the **maximum**, which is what the derivation used it
  as. **And the threshold is now MODEL-SPECIFIC:** the corpus holds a **223,258**-token turn on
  `gpt-5.6-terra`, which at a 180,000 gate lands at 403,258 and dies. `RETIRE_AT` is only verified
  while `harness/config/opencode/opencode.jsonc:16` pins `gpt-5.6-sol`; the probe asserts the pin so changing it goes red.
  (`docs/GROWTH.md` §1)
- ***THE BOUND IS 289,296, NOT 184,852, AND THE MARGIN IS 30.4% — the derivation was answering a
  question the gate never asks (Phase 12).*** Every figure in the two rows above is the maximum over
  EVERY turn on disk. **All four of the largest turns in the corpus start at ZERO** — 299,326,
  223,258, 182,918, 177,110 — and so does 175,148. A turn that starts at 0 and grows 299,326 **ends
  at 299,326**, under the ~360K ceiling, and is retired at its end: it was never a cliff. The rule
  `RETIRE_AT + worst_turn < ceiling` exists for exactly one scenario — a session that has
  accumulated to just under the gate takes one more turn — so `worst_turn` must be the worst turn
  that STARTS near the gate. `probe_turn_growth.py` had argued this in a comment headed *THE
  DECISIVE CUT* since Phase 8 and conditioned only its printout. **Re-derived on the declared scope
  (completed, started >= 100,000, compaction off): the in-scope maximum is 70,704, the bound on
  `RETIRE_AT` is 289,296, and the shipped 180,000 clears it by 109,296 — 30.4% of the ceiling**, not
  1.3%. The scope is asserted to be honest, not argued to be: the probe checks that it throws out
  175,148 as well, since a scope invented to protect a number would have kept it. **What the old
  rule was really conflating** is a failure mode NO value of `RETIRE_AT` can prevent: a single turn
  from an EMPTY session larger than the ceiling dies whatever the gate is set to. Unaddressed, and
  now named. **The open gap is not the threshold — it is that NO REAL NEAR-GATE TURN HAS EVER BEEN
  MEASURED ON THE PINNED MODEL**: of 12 in-scope `gpt-5.6-sol` turns, eleven are one rig's fixed
  22,152 synthetic loop and the twelfth is 109 tokens, so 70,704 is a cross-model figure used
  because it is the conservative one. (`docs/OUTCOME.md` §11; 19/19)
- *`session.tokens` is still useful* — for cost, and it is genuinely cumulative and monotonic
  through compaction (VERIFIED + TESTED, 40/40 sessions match `SUM(step-finish)` exactly). Just
  not for retirement.
- *If you do threshold cumulative spend anyway*: `input + output` crosses 350K at turn 90 of
  101; `input + output + reasoning` — the rule this file used to recommend — crosses at
  **turn 77**, not turn 90. The old text attached SCAN's turn-90 measurement to a different
  formula.

**ALL retirement is a SERVER plugin, not part of the grid — automatic since Phase 6, manual since Phase 7.**
`harness/config/opencode/plugin/healbot.ts` runs inside `opencode serve`, driven off
`message.updated` (whose `properties.info` is the whole assistant message, tokens included). The
grid keeps painting `RETIRE` off `RETIRE_AT` and keeps the `x` binding, but owns no retirement
logic: its `createEffect` was deleted in Phase 6 and its copy of `retire()` in Phase 7. `x` now
writes `metadata.healbot.retireRequested` via `session.update`, which reaches the plugin as an
ordinary `session.updated` event (`session.ts:748` publishes the whole session from the shared
`patch()`), and the plugin performs it. No endpoint was registered because none can be — the server
plugin surface is hooks only and `event` is receive-only. Consequence, and it is bigger than Phase
6's: **run the fork without the harness config and NEITHER automatic nor manual retirement works** —
the border still goes purple, `x` still writes its request, and nothing is listening.
`docs/RELAY.md`.

**The gate fires at the end of a TURN, at 180,000, and it is the ONLY gate. It took three states to
get here and the middle one was committed.** Every artifact in this repo asserted per-turn while
the code did something else; a Phase 7 review found it; the first decision was to keep the shipped
per-STEP behaviour and correct the prose, which is what commit `5bcdeab` and its message say; the
owner then reversed it. If you are reading anything written before that reversal — including
`5bcdeab` itself — it describes a per-step gate and a kept-but-inert hard gate, and both are wrong
now.

*What was actually wrong.* `processor.ts:443-445` writes `finish` and `tokens` in the same mutation
at every `step-finish`, and `:445` is the ONLY site in the session tree that writes a non-zero
`tokens`. So every `message.updated` that carries occupancy also carries a set `finish` — usually
`"tool-calls"`, i.e. mid-turn. `:595-596` sets `time.completed` per step too, in `cleanup()`.
MEASURED on 733 real assistant messages with occupancy > 0: **zero** had a null `finish` (677
`tool-calls`, 56 `stop`). The old predicate read `time.completed || finish` and was therefore true
on 733/733. That measurement is what proved it wrong and it is the case table
`probe_turn_predicate.py` now runs against the shipped source text (18/18, free).

- *The predicate now.* `turnFinished()` in `harness/config/opencode/plugin/healbot.ts:346-349` is
  opencode's own, copied from `prompt.ts:1295`: `if (info.error) return true; return
  Boolean(info.finish && !["tool-calls","unknown"].includes(info.finish))`. It deliberately does
  **not** read `time.completed`. `consider()`'s guard is a plain `if (!turnOver) return`
  (`healbot.ts:622`).
- *Nothing is aborted on the gate path.* The turn is allowed to run to completion and the gate acts
  in the gap between turns — what `PLAN.md` specified all along. `retire()` still opens with
  `POST /abort` (`healbot.ts:473`), but there it is a no-op: `turnFinished()` is what got us there.
  It exists for the race (a new turn starting between the check and the call) and for
  `healbot_retire`, which the control agent may call on a session that is working right now.
- *`RETIRE_HARD` is DELETED, and that is why 180,000.* Not disabled — the constant, the `hard`
  variable, the `if (!stepOver && !hard) return` guard, the env var and its half of the arming log
  line are all gone from both files. `HEALBOT_RETIRE_HARD` reads nothing. It was a second gate at
  330,000 that aborted mid-turn to bound the first gate's overshoot, and Phase 7 measured it to
  have been inert since it was written (its consumer was dominated on 733/733). Deleting it while
  making the predicate per-turn reintroduced the exact failure it was built for: per-turn means
  accepting whatever the turn adds, MEASURED at up to ~170K (`docs/HARDEN.md` §6 — occupancy 5,216
  → 70,898 on one tool result, that turn finishing at 175,090), and against a ~360K ceiling a gate
  at 256,000 lets a session finish near 426,000 and die. So the threshold came down with the gate.
  With one gate the requirement is `RETIRE_AT + worst_turn < ceiling`: **180,000 + ~170K = ~350K,
  just inside.** Anything at or above ~190,000 can be carried off the cliff by one ordinary
  read-heavy turn. **Phase 8 tightened that bound: the pinned model's worst measured turn is 175,148,
  not ~170,000, so the real figure is 184,852 (`docs/GROWTH.md` §1).**
- *The arming line names one gate.* `headless retirement armed — gate 180,000 (per-turn, single
  gate), directory …` (`healbot.ts:903-904`). It used to read `soft N, hard N`;
  `probe_headless_arm.py` asserts the current spelling and the 180,000 default, 14/14.
- *What this does NOT change*: the ~360K ceiling, the ~4.8K floor, or the handoff. Nothing is cut
  off, so everything handed over — todos, diffs, last completed text — comes from a turn that
  finished.

**Compaction is off, so overflow is a HARD ERROR — and the grid now renders it. Built in Phase
5; before that it painted GREEN.** `overflow.ts:28` returns `false` outright when
`compaction.auto === false`, and `processor.ts:607-613` then sets `finish: "error"` and status
idle. That idle is the trap: `status.ts:41` publishes `{type:"idle"}` *before* `:44` deletes the
key, `sync.tsx:310` stores it, and the grid's `stateOf` had no error branch — so a session that
died on an expired credential, a crashed tool or a filled window was pixel-identical to one that
finished its task, in `theme.success`, labelled `done`. On a terminal whose whole premise is that
border colour carries truth, that is the worst available failure: silent, and biased toward
"everything finished". The state is tracked out of band from `session.error` (the only event that
carries the fact — `session-status-event.ts` has no `error` member) and cleared when the session
next goes busy. `retry` is split out of `busy` at the same time, per `PLAN.md:384`'s border table.

**Handoff.** `fork` is disqualified — TESTED, a fork reports 0 tokens at creation then climbs
to exactly the parent's total within ~3s. `summarize` mutates in place and adds tokens. Only
`POST /session` + a seed prompt yields a zero-token session. Retire with
`PATCH time.archived`, never `DELETE` (hard recursive delete) — **but see the trap below:
archiving hides a session from nothing.**

**`prompt_async` works — the audit's "defect" is REFUTED, TESTED.** It acks in 0.01s against
5.1s for the synchronous `POST /session/{id}/message`, and the turn completes ~2s after the ack
with `finish: "stop"` and the same answer, same model, tokens accrued, no error published. The
spawn-and-seed path of `PLAN.md:356` can be built on it as written. See the row in Traps for the
race that made it look broken. A freshly spawned + seeded session starts at its **own**
occupancy — measured floor ~4.8K total on turn one, almost all `cache.read`, which is the
standing-context prefix. Any retirement threshold set for testing must clear that floor.

**Engine choice is load-bearing, not a preference.** v1 (`POST /session/{id}/message`) and v2
(`POST /api/session/{id}/prompt`) have incompatible token accounting *and* incompatible event
vocabularies. Both are mounted on the same port by the shipped binary. **Use v1.** See the two
traps below.

**Where the tokens actually are.** Under `openai/gpt-5.6-sol` in a neutral directory: tool
definitions ~19,900 B dominate, then base prompt 9,284 B (`gpt.txt`), skills ~7,900 B,
instructions, `<env>` ~957 B, `<mcp_instructions>` 0 B. The stripped harness serves ~21.3 KB
against a ~36.7 KB baseline. **Both figures are neutral-directory measurements** — in the fork
the project AGENTS.md adds ~9 KB to *both* arms, so the percentage drops from ~41% to ~33%
while the absolute saving stays ~15.4 KB. Earlier `anthropic.txt` figures (~5,740 / ~2,360 /
~2,050 / ~1,930 tok) described a model this harness does not run; they are superseded.

**Cheapest strip levers**, in order of measured value:
1. An agent's own `prompt` **replaces** the base prompt (ternary, not append) — one
   `agent/*.md` drops 7,569 B (`agent/AGENT.MAP.md`). **Per-agent**: `build`, `plan` and
   `general` each define no `prompt` (`agent/agent.ts:141,156,182`), so overriding `build`
   leaves every `plan` session and every `general` subagent on the full `gpt.txt`.
2. `OPENCODE_DISABLE_EXTERNAL_SKILLS` — measured Δ **7,112 B** (two independent wire captures
   agreed exactly). 18 skills → 1 and 20 commands → 3 *in a neutral directory*; in the fork the
   floor is 2 skills / 12 commands, because the config-directory scan is unconditional.
3. `tool.definition` plugin hook rewrites any builtin tool's description — zero source change,
   aimed at the biggest block, but it recovered only 506 B and ships OFF
   (`plugin/PLUGIN.MAP.md`). Most of that block turned out to be load-bearing.

---

## Traps

Things that will silently cost correctness. All cited in the maps.

| Trap | Where |
|---|---|
| **THE RIG'S PROJECT DIRECTORY IS AN UNDECLARED VARIABLE, AND IT ONLY GROWS.** `rig.fixtures()` is idempotent for its own files, but sessions create files nobody cleans and `git_baseline()` commits them into the baseline, so they stop showing as changes. It now holds **84 entries and 94 MB including `node_modules`** — a model in some earlier run shelled out to `npm install`. A turn measured in that directory grew **299,326** tokens on the pinned model, 71% above the 175,148 on record, and took `probe_turn_growth.py` RED at 13/16. **The threshold turned out to be fine** — that turn started at zero and is out of scope under the re-derivation (row above, `docs/OUTCOME.md` §11) — but the mechanism is not: **every paid run silently changes the workload the corpus measures**, nothing pins the directory the way the probe pins the model, and the same accident would move any figure derived from an unconditioned maximum. **RESTORED at the end of Phase 12: 94 MB → 1.8 MB, back to the seven declared entries**, and TESTED to have deleted no measurement — `probe_turn_growth.py` re-ran afterwards with every figure identical (107 turns, in-scope 70,704, out-of-scope 299,326). The evidence was always in `hb/*.db`; the project directory only ever held the workload. **One live consequence:** the removed residue included a model-created `.gitignore` holding `node_modules/`, so a future run that shells out to `npm install` will have `git_baseline()`'s `git add -A` commit `node_modules` into `hb/project/.git`. The repair is to make it declared — `rig.fixtures()` should write it | `docs/OUTCOME.md` §7, §10 |
| **COUNTING `r.check(` SITES PROVES A SCORE IS REACHABLE, NOT ACHIEVABLE — AND `verify_question.py` HAD BEEN THREE ASSERTIONS RED SINCE PHASE 5.** TESTED: 27/30, exit 1, on a clean DB — its first execution since Phase 4. Phase 5 **built auto-surface**, which lands the cursor ON the blocked cell, and added a comment to that very file saying the rig *"asserts the cursor SURFACES onto the block, not that `tab` reached it"* — then left three assertions assuming the opposite, and never re-ran it. It would not have mattered: at Phase 5 the file ended `finally: r.summary()` with no `sys.exit`. Phase 10 added the verdict exit but did not run it. **The reconciliation Phase 10 used cannot detect this**: 27 static sites against a recorded 27/27 reconciles perfectly, because Phase 5 changed the BEHAVIOUR UNDER TEST, not the assertion count. Only running the rig finds it. The product is fine — auto-surface is the intended feature and `verify_surface.py` tests it; the assertions are stale | `docs/OUTCOME.md` §9 |
| **THREE PAID RIGS ARE SINGLE-USE AND NOTHING SAID SO.** `rig.db(name)` returns a persistent path and never resets it, while the grid header counts *every session in the DB* — and four sites compare that header against a **literal**: `verify_permission.py:116` and `:143`, `verify_question.py:135` (all `t.find("4 sessions")`) and `verify_cold.py:102` (`t.find("1 session")`). Run any of them a second time and the header reads `8 sessions` and the row goes red for a reason that has nothing to do with the code under test. TESTED by accident: a killed run left four sessions in `hb/quest.db`, the next run rendered `Healbot  8 sessions  1 blocked`, and line 135 went red. **Their recorded scores were reachable only on a first-ever execution.** Clearing one: ARCHIVE, never delete — `hb/*.db` is the corpus `probe_turn_growth.py` derives `worst_turn` from, so rename to something that still matches the glob (`quest.db` → `quest-phase12a.db`) | `docs/OUTCOME.md` §7 |
| **`wait_for`'s TIMEOUT DOES NOT BOUND WHAT IT SAYS IT BOUNDS.** VERIFIED by reading, never fired: `wait_for` checks its deadline only *between* calls to `fn` (`rig.py:595`), and `Api.__call__` defaults to `timeout=900` (`rig.py:348`). So `wait_for(lambda: api(...), 300, ...)` advertises 300 seconds and a single hung request can hold it for 900 — worst case ~1,200s against a stated 300. Every `wait_for` wrapping an `Api` call has this shape. A number that reads as a guarantee and is not one | `docs/OUTCOME.md` §8 |
| **`fire()` RECORDS A THROWN TURN AND A FINISHED TURN IDENTICALLY, SO `len(box)` COUNTS TURNS THAT *ENDED*, NEVER TURNS THAT *RAN*.** Both branches append `(label, elapsed, payload)` to the same list, and element `[2]` — the one that says which — was read by **nothing** in the suite; VERIFIED by exhaustive grep across all 28 files. TESTED: three `fire()` calls at a port with nothing listening filled a box with three `URLError`s in **9 ms**, and that satisfied `len(box) == 3`, `len(workers) == 3` and `any(b[0] == "blocker" for b in box)` — every completion predicate the suite owns. Four `r.check` rows were affected; three sit beside a transcript check that carries the real weight, and **one (`verify_question.py`'s concurrency row) had no independent evidence anywhere else in its file**. The rule now is **gate on ENDED, assert on RAN**: `wait_for` still counts the raw box so a thrown turn releases it fast, and the assertion counts `rig.completed()` so the row goes red instead of green. Contract 6 in `probe_rig_contract.py` enforces it from source | `docs/OUTCOME.md` §1, §4 |
| **A `file:line` CITATION IS AN UNTYPED COUPLING BETWEEN TWO FILES, and editing either end rots it silently.** `fork/README.md` names this "drift mode 2" and had no check, so every instance was found by hand — the audit found "one or two lines", Phase 7 found an off-by-one asserted as VERIFIED whose line was blank. TESTED across **930 citations in 25 documents**: eight were stale. Three cited `healbot.tsx` past its 1,100-line end (pre-existing, off by ~140); five landed on blank lines, and **three of those were created by Phases 9 and 10**, which moved `## Traps` and `## Behavior → file` in this very file and a cited line in `probe_twin.py`. Editing a document that other documents point *into* is the failure mode, and no tool in the repo modelled it. `probe_citations.py` now does — positional rot only; **semantic rot, a citation landing on a real line that says something else, is not mechanically checkable and is not claimed**. Editorial rule that falls out of it: a citation quoted as BROKEN must not be written in live `file:line` form, or the probe cannot tell a pointer from a specimen | `docs/CITE.md` §1, §2 |
| **Two files are named `opencode.jsonc`, and the checkout's has a BLANK line 16.** The harness's `harness/config/opencode/opencode.jsonc:16` is the model pin — the citation `probe_turn_growth.py` asserts `RETIRE_AT` against, and the reason the threshold is verified at all. It was written bare — just `opencode.jsonc` and the line number — in three documents, so a reader with the checkout open (the likelier one, since that is where the code is) followed it to nothing. All occurrences now carry the full path, and `probe_citations.py` pins both halves: that a path-prefixed citation beats a bare basename, and that the pin really is on line 16 | `docs/CITE.md` §3 |
| **SIX PAID RIGS DISCARDED `summary()`'s VERDICT AND ALWAYS EXITED 0.** `finally: r.summary(); t.close()` — the boolean computed, printed and dropped; `verify_retire.py`, `verify_surface.py` and `smoke.py` contain no `sys.exit` anywhere in the file. VERIFIED by reading all twelve paid entrypoints. Two consequences worth naming: **`smoke.py`** is what the README tells you to run FIRST to confirm the model pin resolves, and it returned success when it could not; **`verify_surface.py`** carried a known-red assertion (recorded 17/18) for **five phases**, because the exit code is the channel that would have surfaced it and it was disconnected. A fresh clone could not have caught this the way it caught Phase 9's — a paid rig cannot be run from a clone, so the paid half never executed and never got the chance to report a false green. Only visible in source, which is why the guard reads source: `probe_rig_contract.py`, free, **29/29** across **24** entrypoints since Phase 12 added contract 6 (it was 22/22 across 23 when Phase 10 wrote it; `probe_citations.py` made the 24th) | `docs/VERDICT.md` §1, `docs/OUTCOME.md` §4 |
| **A RECORDED SCORE IS A CLAIM ABOUT A FILE AT A MOMENT, AND NOTHING TIED THE TWO TOGETHER.** `verify_handoff.py` is cited as **21/21** here, in `docs/VERIFY.md` §10 and in the rig README as the evidence for the Phase 4 exit gate's second clause. TESTED by AST walk: it holds **22** assertions, all unconditional — Phase 5 (`823d7a2`) removed a vacuous check and added two mutation legs, taking it from 21 to 22, and nothing re-ran it. 21/21 is a Phase 4 score against a Phase 4 file. Phase 8 found the identical shape in `verify_control_agent.py` and called it *"the one rig in the suite"* (`docs/GROWTH.md:176`) — **that uniqueness was never checked and is false.** Counting `r.check(` per file against the recorded scores reconciles every other rig in one command: `verify_cold.py` (22 sites/21) and `verify_retire_350k.py` (26/25) differ by exactly their own crash guard, `verify_control_agent.py` (16/15) by one conditional. **Re-run a rig before quoting its number** | `docs/VERDICT.md` §2 |
| **A GREEN PROBE RUN IS NOT EVIDENCE THAT THE PROBE RAN.** `Results.summary()` returned `not failed` over whatever rows happened to be appended, so a probe that crashed or timed out early reported `N/N passed` and exit 0. TESTED from a fresh clone: `probe_on_grid` **2/2**, `probe_control_wiring` **7/7**, `probe_headless_arm` **1/1** after printing `!! timed out … after 90s` — three green exit codes over 10 of 52 assertions. Two independent routes: `sys.exit()` inside a `finally` **discards the in-flight exception** (named at `probe_request_channel.py:151-153` since Phase 7 and present in only 3 of 10 probes), and `wait_for()` (`rig.py:593-604`) prints `!!` and returns `None` without raising, which no exception guard can catch. Both now caught by `Results(expect=N)` — a **floor**, not an equality. Positive control 142/142 on the real repo, negative control 9-of-10 exit 1 on the clone | `docs/CLONE.md` §1 |
| **`probe_turn_growth.py`'s headline assertions PASS MORE COMFORTABLY as their evidence disappears.** Both are `retire_at + worst_sol < CEILING` in some form, so a **smaller** `worst_sol` makes them easier — and `worst_turn = 175,148` exists only in `hb/*.db`, which `.gitignore:13` excludes. TESTED on a fresh clone: the pinned population collapses to 6,643 and the probe reports the gate clearing its ceiling by **173,357 tokens, 48.2%**, and the bound as **353,357** — against the true 4,852 / 1.3% / 184,852 — **in green**, while its own detail string still quotes 175,148. Guarded now by a fixture check `worst_sol >= 175_148`; `>=` is deliberate, so new evidence of a *larger* turn correctly tightens the derivation instead of failing here. **When a predicate's inputs come from a corpus, the corpus needs a fixture check as much as the predicate needs a mutation check** | `docs/CLONE.md` §2 |
| **Both of `probe_turn_growth.py`'s corpora are REQUIRED, and its docstring said the real one was optional.** TESTED with the file absent: `r.check(…, have_real, …)` makes absence a **FAIL**, exit **1**, 12/14 — the `[NOT EXERCISED: …]` string is the detail on a *failing* row, not a pass. The model-specificity assertion goes red with it, since the 223,258-token off-pin turn lives there. Note the two corpora fail in **opposite directions**: without the real one the probe goes loudly red; without the rig one it goes quietly *greener* | `docs/CLONE.md` §3 |
| **The suite writes to the corpus it measures.** `probe_turn_growth.py` globs `hb/*.db` and every paid rig writes there, so its percentiles are a function of how many rigs have run since — a snapshot, not a constant. TESTED: the corpus moved 86 → 94 turns between Phase 8 and Phase 9, and the entire delta is `hb/control.db` (mtime 19:50) written by `verify_control_agent.py` **six minutes after** Phase 8 recorded its figures (probe mtime 19:44). Hiding that one file reproduces Phase 8's percentiles exactly. Do not read drift here as a signal about the model. **Every maximum, bound and conditional was unchanged across +14% of corpus** — the first evidence the derivation is stable under corpus growth | `docs/CLONE.md` §4 |
| **The suite is NOT portable, and `rig.py:27-30`'s comment implies it is.** That comment records the Phase 5 fix for hardcoded scratchpad paths and says the suite "could not be re-run from a fresh clone"; deriving paths from `__file__` fixed the **paths**, not the runnability, and nobody executed it until Phase 9. A fresh clone lacks the gitignored `opencode/` checkout (so `bun run --cwd` ENOENTs and no server starts) and the gitignored `hb/*.db` (which only paid rigs can rebuild). `probe_error_state` and `probe_focus` are listed as "free" but need `verify_retire_350k.py`'s database first — free to **re-run**, not free to run the first time. **`probe_turn_predicate.py` is the only one of the ten that survives a fresh clone**, because it depends solely on tracked files plus `node` | `docs/CLONE.md` §1, §5 |
| **TUI plugin scope has NO Solid owner.** `plugin/tui/runtime.ts`'s `load()` crosses an `await` before `activatePluginEntry` invokes `tui(api)` at `:529`, so the synchronous `createRoot` window has closed. TESTED: `getOwner()` is `null` there. `createSignal`/`createMemo` work (they never touch the owner), but a `createEffect` is **never disposed** and a bare `onCleanup` is a **silent no-op**. This is why "move the retirement trigger to plugin scope" was rejected — and it would not have made it headless anyway, since a TUI plugin needs a TUI | `docs/HEADLESS.md` |
| **Every field that looks like "the turn is over" on an assistant message is set per STEP.** `finish` (`processor.ts:443`), `tokens` (`:445`) and `time.completed` (`:595-596`, in `cleanup()`, which runs per `process()` call) all fire at each `step-finish`, and `prompt.ts:1186-1201` creates a new assistant message per step. MEASURED: 733 real messages carrying occupancy, **zero** with a null `finish` — 677 `"tool-calls"`, 56 `"stop"`. So any NEW code that reads those fields to detect a turn boundary re-creates the defect Phase 7 spent a phase on, and it fails silently, in the direction of acting too early. `turnFinished()` (`healbot.ts:346-349`) — opencode's own predicate from `prompt.ts:1295`, excluding `["tool-calls","unknown"]` and deliberately ignoring `time.completed` — is the only correct reader in this tree; `probe_turn_predicate.py` evaluates its shipped source text against that measured distribution, and re-runs the same table against the old predicate to require it to fail | `docs/RELAY.md` §1 |
| **`RETIRE_AT` is only valid for the PINNED MODEL, and nothing said so before Phase 8.** `worst_turn` is a fact about how far one agent turn grows, which is a fact about a model's tool-calling behaviour — not about opencode. MEASURED: the pinned `gpt-5.6-sol`'s worst turn is 175,148, but the same corpus holds a **223,258** turn on `gpt-5.6-terra` and 3 turns off-pin exceed the pinned worst case. At a 180,000 gate that turn lands at 403,258, past the ~360K ceiling. So switching the model in `harness/config/opencode/opencode.jsonc:16` silently un-verifies the threshold, with no error and no log — `probe_turn_growth.py` asserts the pin so it goes red instead | `docs/GROWTH.md` §1 |
| **`healbot_*: deny` scopes CONTEXT, not CAPABILITY — it is not a sandbox.** TESTED: the build agent, with all five tool definitions removed from its payload, ran `opencode --help` → `session list` → `run --help` and then `opencode run --auto --format json --title … "Create a file named hello.txt …"`, creating a real TOP-LEVEL session. The CLI is on `PATH` inside the tool sandbox and talks to the same DB. The deny still does the job it is paid for — keeping ~5 tool definitions out of every session's standing context — and `verify_control_agent.py`'s own comment had asserted the opposite ("a session cannot create ANOTHER session with `bash`") since the day it was written. Do not build anything on the assumption that a denied agent cannot reach a capability | `docs/GROWTH.md` §2 |
| **An EXTERNAL TUI plugin can silently replace the grid.** Internal plugins are added before external ones (`plugin/tui/runtime.ts:1093-1105`), activation is sequential, and the route map is last-wins — `get(name)` returns `routes.get(name)?.at(-1)?.render` (`tui/src/plugin/api.ts:33-35`), which the loop's own comment at `:1108-1110` states outright. So a third-party plugin registering a route named `healbot` wins over the builtin: no error, no warning, no log line, and `ctrl+p → healbot` opens somebody else's screen. The name is neither pinned nor reserved | `docs/GROWTH.md` §4 |
| **Retirement happens in exactly ONE process, and the grid's `x` is only a request.** It writes `metadata.healbot.retireRequested` and returns; if the harness config is not loaded, `x` looks like it worked and nothing retires. Before Phase 7 `x` worked without the harness. The coupling is untyped in both directions — a rename on either side silently stops manual retirement, with no error and no log — which is why `probe_twin.py` mutates both ends | `docs/RELAY.md` §2 |
| **`verify_headless_retire.py` cannot be pointed at the shipped threshold.** It hardcodes `THRESHOLD = 20_000` at `:52` and forces it into the SERVER's env at `:96-103`, and `rig.py:282` applies `env_extra` last — there is no override to remove. Its one prompt reads ≤50 KB (`read.ts:16`) and it asserts `len(user_turns) == 1`, so editing the constant just times out after 15 minutes. The two halves that can be checked without paying for it are covered free instead: `probe_headless_arm.py` on the arming (that the shipped 180,000 default arms, and that the log line names ONE gate), `probe_turn_predicate.py` on the predicate. What it DOES buy, at 20,000, is the wiring and the per-turn ordering — TESTED 22/22 with the gate crossed mid-turn at step 1 and the turn running on to `stop` at step 5 | `docs/RELAY.md` §4 |
| **A server plugin gets the v1 SDK client; the TUI gets the v2 one, and they diverge silently.** The v1 client has **no `permission` and no `question` sub-client at all**; its `SessionUpdateData["body"]` is `{title?}` with no `time.archived`; its `SessionCreateData["body"]` has no `directory`. The SERVER accepts all three (`groups/session.ts:53-57`, `handlers/session.ts:200-201`) — the generated v1 types are narrower than the routes. `healbot.ts` writes the requests out with `fetch` rather than casting past the types three times | `docs/HEADLESS.md` |
| **The session-route sidebar is gated on `width > 120`** (`routes/session/index.tsx:264`), and it is the only thing that renders a session's id. The navigation rigs use exactly 120 so cells cannot fit one row — so a focus assertion written at that width measures terminal geometry, not behaviour. TESTED, it reported a failure that way | `docs/HEADLESS.md` §2 |
| **There is no key that returns from a session to the grid.** `healbot.open` is namespace `palette` / slashName `healbot` with no binding anywhere; the routes back are `ctrl+p` or typing `/healbot`. `returnRoute` cannot help — `adapters.tsx:47-52` drops every param but `sessionID`. The selection index does survive, in the plugin closure | `docs/HEADLESS.md` §2 |
| **A plugin module may export ONLY functions.** `getLegacyPlugins` (`plugin/index.ts:95-108`) iterates `Object.values(mod)` and throws `TypeError: Plugin export is not a function` on the first that is not — so one exported constant disables the whole plugin, at load time, in a log line nobody reads. `applyPlugin` catches and publishes rather than crashing, so the symptom is a healthy server with a missing feature | `docs/HEADLESS.md` |
| **The whole `session.next.*` event family is v2-only.** Zero publishers in `packages/opencode/src` (4 hits, all consumers); the sole publisher factory is `core/src/session/runner/publish-llm-event.ts`, imported once by the v2 runner. So on the v1 path — the one you must use — `session.next.tool.called`, `.context.updated` and `.compaction.started/.ended` never fire. `PLAN.md:115-117` lists them as "verified event types" and builds frame contents on them | REVIEW |
| **The v2 engine never writes `session.tokens`.** `applyUsage` has 5 call sites, all in v1 projections; v2 usage lands on the message row instead. TESTED — a v2 turn burned 3,399 tokens and left the session row at `{0,0,0,0,0}`. A v2-driven session is invisible to any retirement trigger | `core/session/SESSION.MAP.md` |
| **`GET /api/session/{id}/context` returns an EMPTY array for v1 sessions.** It reads `SessionMessageTable`, which v1 never writes. TESTED: the 101-turn reference session has 0 `session_message` rows and 738 `part` rows. `PLAN.md:96` names this endpoint as the token source | REVIEW |
| **`PATCH time.archived` hides a session from nothing.** `ListInput` has no `archived` field; `listByProject` (behind `GET /session`) has no `time_archived` predicate; the v2 list does not filter; `grep -rn archived packages/tui/src` → zero hits. Only `listGlobal` filters, reachable solely via `GET /experimental/session`. **The grid must filter retired sessions itself** | REVIEW |
| **`client.session.list()` cannot enumerate across PROJECTS** — hard-scoped to `ctx.project.id` (`session.ts:548-555`), and `ListInput` has no `projectID` to widen it. Worse, the documented tripwire `api.state.session.count()` reads `sync.data.session.length` — the *same narrowed store*, so it can never detect the misses. Use `client.experimental.session.list()` (cursor-paginated). **Note the axis**: this is about projects, not directories. `scope: "project"` IS a real query param (`groups/session.ts:32` declares it, `handlers/session.ts:67-68` drops the directory filter for it) and is what the grid uses to escape the current-subdirectory filter | `tui/context/CONTEXT.MAP.md` |
| **An "always" permission applies to every session in the process** — approvals are instance-wide, never persisted, no sessionID filter. Directly hostile to a multi-session terminal | `permission/PERMISSION.MAP.md` |
| **No timeout on a pending permission** — a client that ignores `permission.asked` hangs that tool call forever. TESTED: it hangs indefinitely, but it does **not** stall other sessions | `permission/PERMISSION.MAP.md` |
| **`permission: {skill: "deny"}` does not stop a skill.** TESTED in one process: the deny removes the `skill` tool *and* the whole `<available_skills>` block, yet `/<skill-name>` still executes the skill to completion, shell substitutions included. Only removing skills from the prompt closes it | `skill/SKILL.MAP.md` |
| **Instruction files do NOT stop at the first ancestor.** The `break` is over the *filename* list; `fs-util.ts:154-166` collects every `AGENTS.md` up to the worktree root. The source comment at `instruction.ts:123` claims the opposite and is wrong. In the fork, a session under `src/session/llm` ingests 22,273 B of AGENTS.md | `session/SESSION.MAP.md` |
| **The 18→1 skill floor is cwd-dependent** — the config-directory scan is unconditional. In the fork the harness delivers 2 skills / 12 commands / 9 agents, readmitting upstream repo tooling | `skill/SKILL.MAP.md` |
| **`OPENCODE_CONFIG_DIR` merges rather than isolates** — it is worse than a no-op. Same for `OPENCODE_CONFIG` and `OPENCODE_CONFIG_CONTENT`. Only `XDG_CONFIG_HOME` replaces | `config/CONFIG.MAP.md` |
| **RED never fires under `--auto`** — `sync.tsx` auto-replies before writing to the store | `tui/context/CONTEXT.MAP.md` |
| **`session.created` is not handled** by the sync store — freshly spawned sessions don't appear until a later `session.updated` | `tui/context/CONTEXT.MAP.md` |
| **`listSessions()` has a 30-day window + current-subdirectory filter** — a cross-directory grid silently misses sessions | `tui/context/CONTEXT.MAP.md` |
| **`store.message[sid]` caps at 100 and drops evicted parts**, grid-wide | `tui/context/CONTEXT.MAP.md` |
| **There is no `api.state.session.list()`** — the grid must direct-import `useSync`; it cannot be patched at the host layer | `tui/plugin/PLUGIN.MAP.md` |
| **`route.navigate("session", …)` discards every param but `sessionID`** | `tui/plugin/PLUGIN.MAP.md` |
| **The grid's roster renders OLDEST first, and its comment claims the opposite.** `healbot.tsx:203-204` says "ids are monotonic-ascending … newest first" and sorts `b.id.localeCompare(a.id)`. Session ids are **descending** identifiers (`schema/src/session-id.ts:8` → `schema/src/identifier.ts:22`, `descending ? ~current : current`), so they already sort newest-first ascending and that comparator reverses them. TESTED both ways. Cosmetic, but cell order is what an operator builds muscle memory on | `docs/VERIFY.md` §7 |
| **`escape` is destructive on both prompts and there is no back-out key** — `escapeKey="reject"` (`permission.tsx:406`) and question's escape calls `reject()` (`question.tsx:280`). TESTED: escape rejected, the tool never ran. Worse, the labels disagree on screen — the grid footer says `esc reject`, the question panel it docks says `esc dismiss` (`question.tsx:508`, upstream) | `docs/VERIFY.md` §5, §7 |
| ~~**The TUI cannot attach to an external server**~~ — **REFUTED, TESTED.** `--port` really is "port to listen on" (`cli/network.ts:9`), but that was never the whole CLI: `opencode attach <url>` is a registered command (`cli/cmd/attach.ts:7-16`, `index.ts:84`) whose non-`--mini` branch calls the same `run()` with the same `createLegacyTuiPluginHost()` as `cli/cmd/tui.ts:271-296`, so the grid loads on it. `harness/fleet.sh` ships the pairing and the cold-start reconcile is now TESTED 21/21. **A true premise carried a false conclusion for three phases because nothing checked the rest of the command surface** | `docs/HARDEN.md` |
| **A client and the rig must agree on `x-opencode-directory`** — `workspace-routing.ts:87` resolves the instance as `?directory \|\| x-opencode-directory \|\| process.cwd()`, and under `serve` the cwd is wherever the launcher put it, not your project. Get this wrong and every API call succeeds, `GET /session` returns your sessions, and the grid renders `0 sessions` — two different instances. TESTED, it cost a whole run | `docs/HARDEN.md` |
| **A backgrounded server dies with the shell that launched it** — plain `&` is not enough; the shell HUPs its jobs on exit and the job shares the terminal's stdin. `nohup … </dev/null & disown` is the working form. TESTED: without it, closing the control terminal took the whole fleet down, which is the exact failure the fleet exists to prevent | `harness/fleet.sh` |
| **`GET /session/{id}/diff` returns `[]` without a `messageID`** — `summary.ts:130` returns `[]` outright when none is given, and `:133` returns `[]` again unless that message is a **user** message. It is a per-user-message endpoint; the diffs live on the user message's `summary.diffs`. `PLAN.md:398` says "its `/diff`" as though one call covered the session. Fan out over user messages and union | `docs/VERIFY.md` §10 |
| **There are TWO `summarize`s.** `POST /session/{id}/summarize` → `compactSvc.create` (`handlers/session.ts:273-283`) is **compaction**, an LLM turn — that is the one that "mutates in place and adds tokens". `SessionSummary.summarize` (`summary.ts:102-127`) computes git diffs, calls no LLM, and already runs on the prompt path (`prompt.ts:1253`). Do not reach for the route to get diff data | `docs/VERIFY.md` §10 |
| **An assistant message row exists ~20 ms after `prompt_async` acks, and is EMPTY until the turn runs.** Polling "does an assistant message exist" returns true immediately with no content. The completion signal is the message's own `time.completed` / `finish`. This produced a false "prompt_async executes nothing" defect report in the audit, and fooled the verification session again before it was caught | `docs/REVIEW.md` |
| **Scoped denies do NOT remove a tool schema** — only blanket `*` denies do, and a later narrow allow un-hides a blanket-denied tool | `permission/PERMISSION.MAP.md` |
| **`tool/read.ts` attaches nearby `AGENTS.md` on every file read** — unbounded cost, invisible to standing-context measurement | `session/SESSION.MAP.md` |
| **`bash`'s description is generated at runtime**, not stored — editing `shell.txt` looks like the fix and does almost nothing | `tool/TOOL.MAP.md` |
| **Skill dedup is a race** — winner varies by I/O completion order across boots | `skill/SKILL.MAP.md` |
| **`` !`cmd` `` in a SKILL.md body shell-executes on slash-invoke**, no permission check | `skill/SKILL.MAP.md` |
| **The built-in agent table exists twice** (v1 and v2) — editing one does not change the other | `agent/AGENT.MAP.md` |
| **Config loading mutates your disk every boot** — `$schema` injection, file seeding, `.gitignore` writes | `config/CONFIG.MAP.md` |
| **`api.event` metadata arg works but is untyped** — needs a cast; the grid needs it for cross-directory routing | `plugin/src/PLUGIN-API.MAP.md` |
| `permission.ask` plugin hook is **dead** — declared, zero trigger sites | `plugin/PLUGIN.MAP.md` |
| ~~`healbot-spike` occupies `/healbot` in the palette~~ — resolved at fork `26c9316`: the spike was deleted in the same commit that added the real grid, so `/healbot` now belongs to `healbot.tsx` | `tui/feature-plugins/FEATURE-PLUGINS.MAP.md` |
| **The `*_CONFIG_DIR` naming is INVERTED between opencode and Claude Code.** opencode's `OPENCODE_CONFIG_DIR` is the additive false-isolation trap and `XDG_CONFIG_HOME` is the real switch; Claude Code's `CLAUDE_CONFIG_DIR` IS the real switch (TESTED: a doctor run under a redirected empty dir was signed out and wrote state into it). Reasoning by analogy in either direction configures the wrong thing silently | `docs/SHIP.md` §2 |
| **tmux `capture-pane -p` PADS TO THE PANE HEIGHT AND THE CLI PAINTS TOP-DOWN, so a fixed `tail -N` of the capture reads pure padding on a tall, mostly empty pane.** MEASURED 2026-08-05 on a solo crewmate holding the crew window alone: at 49 rows the ready marker sat on line 17 and `state` classified it unreadable off twenty blank lines; the same pane at 23 rows read idle, same marker line. A solo crewmate always misread, spawning a second one "fixed" it by halving the panes, and the E2E walk ran two, which is why it never met this. The help-card geometry finding in a new coat: a variable-size render read through a fixed-size window. `peek` carried the correct read (strip blanks, THEN tail) six verbs up while `state` omitted the strip, so the repair is ONE shared reader, `screen_tail`, now behind every classification read; `send`'s submit verify — kept raw at first because a stripped window might have read the transcript's ECHO of the sent text as "still unsubmitted" — joined it 2026-08-05 after a live two-submit measurement (rig, frames, REPORT.md: `.carryover/verified/hb/submit-verify-20260805/`) kept the echo never nearer than six painted lines above the pane bottom — two-plus clear of the stripped 3-line window at every frame — on a 49-row and a 17-row pane, while the raw tail it replaced read pure padding at its +1s verify instant on the tall pane and chrome on the 17-row pane (that leg's filled-pane design went UNMET; run notes in the archive REPORT.md), printing "sent" having never seen the composer. Guard: `probe_fleet_claude.py`'s screen-reader conjuncts (raw-tail census ZERO), seven mutation legs, and a live tall-pane counterfactual on a scratch tmux server | `harness/hb-fleet.sh` |
| **A fresh claude config dir is SIGNED OUT — auth does not follow the redirect.** A crew spawn under an un-logged-in `harness/claude` used to fail its ready-wait, naming the timeout rather than the cause; since 2026-08-02 `hb-fleet.sh preflight`, doctor.py's `harness claude auth` row and `spawn`'s own guard all name it, and `spawn` refuses in milliseconds. The config dir is mixed code+state after a login, which is why its `.gitignore` is a whitelist — and why it lives OUTSIDE `harness/config/`, which `arms.py` freezes wholesale into arm snapshots (measured: the first draft turned `probe_arm_factory.py` red). On macOS the credential itself is a login-KEYCHAIN item, not a config-dir file, and the harness login ISOLATES rather than sharing the owner's: the keychain service name is derived from the config root, so each root has its own item (MEASURED 2026-08-02) | `docs/SHIP.md` §2, §5; `harness/env.claude.sh` |
| **`python3 - <<heredoc` consumes stdin as the PROGRAM, so a hook reading its payload from stdin reads nothing** — syntactically clean, exits 0, writes nothing. In a fail-open script that shape is invisible except to a live happy-path check, which `probe_fleet_claude.py` now is | `docs/SHIP.md` §3 |
| **`fork/healbot-fork.patch` IS A THIRD COPY OF THE OVERLAY, AND NOTHING EVER COMPARED IT TO `fork/`.** `probe_twin.py` asserts `fork/` ↔ `opencode/`, and the owner's checkout is kept in sync BY HAND — so the pair that is guarded stayed green while the pair that is not silently came apart. TESTED from a fresh clone reconstituted exactly as `README.md` prescribes: `git apply` reproduces **15 of 17** overlay files byte-for-byte and leaves two behind (`packages/core/src/session/SESSION.MAP.md`, `packages/tui/src/feature-plugins/FEATURE-PLUGINS.MAP.md`), which takes `harness/doctor.py` to **1 FAIL**, `probe_twin.py` to **24/25 exit 1**, and `gate/gate.py` to **exit 2 BLOCKED** — a stranger cannot pass the gate on a clean clone, for a reason that is not their change. The patch was last cut at `045e416` (Phase 7); Phase 11 (`16ec8e7`) corrected citations inside those two maps and hand-copied each into the checkout. Only the `.MAP.md` prose diverged — every code path in the overlay is identical — and `fork/README.md`'s "byte-identical to `fork/` afterwards" claim, TRUE when Phase 11 measured it, is the casualty. **`fork/` is the authority and the patch is the base-relative bootstrap**, so both reconstitution blocks now end by copying `fork/` over the checkout; regenerating the patch was rejected because it would trade the artifact's only provenance for two lines of prose | `docs/CLONE.md` §8, `fork/README.md` |
| **THE SKILL TWINS SYNC BY HAND, AND ONLY ONE OF THEM WAS GUARDED.** `harness/skills/<name>.md` is the tracked half; `~/.agents/skills/<name>/SKILL.md` is the half every live session loads — BOTH harnesses: Claude Code through the `~/.claude/skills` symlinks, opencode through its manifest glob over `~/.agents`, where the `.agents` copy also wins name collisions (`skill/SKILL.MAP.md`, sources 1-2). No installer script exists; `env.claude.sh` only cites the naming convention. MEASURED 2026-08-02: `healbot-traps.md` gained two trap entries in the repo while the installed copy served the stale body for two days, in green — the guarded specimen (firstmate) held while the unguarded population drifted, the fork-patch shape one row up wearing skill clothing. Guards now sweep the population: doctor's `skill twins` row (stdlib, any machine, three states — a FAIL gates BOTH workflow tiers) and `probe_fleet_claude.py`'s mutation-controlled census/frontmatter/shell-hole/identity rows (main checkout, tier 2). A red's direction is a diff's call, never the tooling's: repo-newer happened this time; installed-newer happens the day someone edits an installed copy | `harness/doctor.py`, `.carryover/verified/probe_fleet_claude.py` |
| **THE CLAUDE CLI MIGRATES EACH CONFIG ROOT ONCE, AND THE MIGRATION REWRITES THE TRACKED MODEL PIN.** The config root is mixed halves: `harness/claude/settings.json` is tracked, and the marker that says "already migrated" lives in the untracked half (`.claude.json`, key `migrationVersion`). claude 2.1.220's ladder step 13 rewrites exactly the alias `opus` → `opus[1m]` — the 1M-context variant, premium-priced above 200K input — in any root whose `.claude.json` is missing or holds `migrationVersion < 13`, then stamps 13 so it never fires there again. TESTED 2026-08-02 in scratch roots: `claude auth status --json` (the precise call `check_claude_auth` makes) and `claude config list` both rewrite and stamp on first run; `claude --version` touches nothing; deleting `migrationVersion` re-fires the rewrite while deleting the decoy keys `opusProMigrationComplete` / `sonnet1m45MigrationComplete` does not; pins `sonnet`, `haiku`, `opus[1m]`, `claude-opus-5` pass byte-identical, so the mapping is the alias `opus` alone — exactly what the 2026-08-01 model policy pins. The bite: `git worktree add` and fresh clones copy only the tracked half, so EVERY new worktree, pool slot, and clone is an unstamped root whose first doctor run or crew spawn dirties a tracked file mid-session — first seen when a worktree doctor run flipped the pin and the flip passed `settings_ok`'s `bool(d.get("model"))`. The MAIN checkout's root already carries `migrationVersion: 13` (VERIFIED 2026-08-02), so it will not rewrite; both pool slots have no `.claude.json` and will, on their first claude invocation. The repair is revert-and-keep-the-stamp: `git checkout` the settings file and leave `.claude.json` alone. Guard: `probe_fleet_claude.py`'s settings row now asserts the pin VALUE with a mutation leg for this exact flip — a deliberate pin change updates probe and file in one commit. Contained at both known triggers since 2026-08-02: the doctor restores its own trigger (`check_claude_auth` snapshots and byte-restores the settings file, stamp kept), and the fleet contains it at `hb_auth_state`, which stamps the root before every spawn and preflight, so crew panes and the first login start stamped. Residual: a hand-run interactive `claude` in an unstamped root still fires once; repair unchanged | `.carryover/verified/probe_fleet_claude.py`, `harness/doctor.py`, `harness/hb-fleet.sh` |

---

## Closed

| Was open | Answer |
|---|---|
| Does the v2 engine write `session.tokens`? | **No.** Settled at TESTED tier — see below. Drive v1 |
| Does `$XDG_CONFIG_HOME` fully redirect global config? | **Yes**, TESTED. It is the harness's isolation mechanism (`docs/STRIP.md`) |
| Re-measure standing context under `gpt-5.6-sol` | **Done** (`docs/STRIP.md`), corrected in `docs/REVIEW.md` |
| Do N sessions actually run concurrently on one server? | **Yes**, TESTED. And a blocked permission does not stall the others |
| Is the yellow border gated behind `OPENCODE_ENABLE_QUESTION_TOOL`? | **No** (SCAN C3) |
| Does `flags.client` land in the `["app","cli","desktop"]` allowlist? | **Yes**, TESTED. `OPENCODE_CLIENT` defaults to `"cli"` (`core/src/flag/flag.ts:75-76`) and `tool/registry.ts:202` admits it. A real `question` fired unforced on `gpt-5.6-sol` and was answered from the grid. YELLOW fires (`docs/VERIFY.md` §4) |
| Has `healbot.tsx` actually been **run**? | **Yes**, TESTED on `gpt-5.6-sol` — rendering, live session state, keyboard ownership, and clearing both a permission and a question block from the grid without focusing. 90/91 assertions (`docs/VERIFY.md`) |
| Does a session need `permission: {question: "allow"}` to ask? | **No.** `question` is `"deny"` in the shared default block (`agent/agent.ts:127`), but `build` and `plan` each merge `question: "allow"` on top (`agent/agent.ts:141-152`). Only `general` and `explore` subagents inherit the deny |
| Is `prompt_async` broken? | **No** — REFUTED, TESTED. Acks in 0.01s, turn completes ~2s later, same answer/model/tokens as the sync path. The audit polled a row that exists ~20ms before it fills. Build the spawn-and-seed path on it (`docs/VERIFY.md` §9) |
| Make the retirement threshold configurable | **Done.** `HEALBOT_RETIRE_AT`, default **180,000** — 350,000 in Phase 4, 256,000 in Phase 5, 180,000 in Phase 7 when the second gate was deleted. `HEALBOT_RETIRE_HARD` is gone and reads nothing. The grid renders `RETIRE` + `N to retire` + a share-of-gate figure off the same variable. TESTED at 20,000 against a session grown to 37,179 while quiet ones sat at 4,969. **Not 5K** — a fresh session's floor is ~4.8K, so 5K fires on turn one |
| What counts as "continuity intact" for a handoff? | **Defined and TESTED.** The successor must be handed the objective, carry the predecessor's **open** todos in its own list, and be handed a file the predecessor changed — all asserted on artefacts, never on the successor's prose. Retirement is **automatic on the gate**, with `x` as the manual override (`docs/HARDEN.md` §8). 21/21, occupancy 90,310 → 5,649 (`docs/VERIFY.md` §10). **CAVEAT, Phase 10: that 21/21 is a Phase 4 score against a Phase 4 file.** Phase 5 replaced a vacuous check with two mutation legs, so `verify_handoff.py` now holds **22** unconditional assertions and 21/21 is unreachable — nothing has re-run it. The clause is not disproved, but it is cited from a superseded file. `docs/VERDICT.md` §2 |
| Is the Phase 4 exit gate met? | **Yes**, both clauses, TESTED on `gpt-5.6-sol`. Four concurrent with one answered from the grid without focusing (§2–§5); one driven past the threshold and handed off with continuity intact (§10) |
| Does auto-retirement work headless? | **Yes**, TESTED 20/20 with no TUI in the process table. It is a **server** plugin, not a TUI one — "move it to plugin scope" would not have achieved it, because a TUI plugin needs a TUI. `docs/HEADLESS.md` |
| Does `enter` focus the selected session? | **Yes**, TESTED 24/24 and free. Asserted on the session id the sidebar renders, cell 0 then cell 1, so the predicate runs twice with opposite expectations. Also: focusing does **not** clear ERROR cells — `storedErrorOf` re-derives them |
| Is the `question.rejected` half of the cold reconcile exercised? | **Yes**, TESTED 22/22. Question raised unforced with no client, cell renders `QUESTION` on first paint, panel mounts from the reconciled request with real options, `escape` rejects, block clears. The plain session route could not have shown it at all — `sync.data.question` is event-fed only |
| **Is the control agent built?** | **Yes** — build-order step 5, the last non-optional unbuilt step. Five tools on the server plugin's `tool` hook plus `agent/control.md`. 14/14 wiring (free) and 15/16 runtime: the same instruction under `control` calls `healbot_list`/`healbot_spawn` and produces a real seeded session; under `build` it calls none of them. See the honest note on the 15/16 in `docs/HEADLESS.md` §3 |

### The v2 token question — settled

Earlier this file recorded an inconclusive result: `POST /api/session/{id}/prompt` "produces no
assistant turn after 60s". **That is not reproducible.** A retry got a complete turn in ~1.2s;
the earlier failures are still in the DB, each holding only `agent-switched` + `model-switched`
rows pinning `gpt-5.6-sol`. The negative was model-specific, not structural — v2 is live.

The answer, from source and confirmed by execution: **v2 does not write `session.tokens`.**
`applyUsage` is called only from `SessionV1` projections (`core/src/session/projector.ts:90,
286, 304, 327, 328`). The v2 runner publishes `SessionEvent.Step.Ended`
(`runner/publish-llm-event.ts:396-400` → `runner/llm.ts:326-333`), which projects to the
message row via `message-updater.ts:209-214`. TESTED: a v2 prompt burned
`{input: 3381, output: 4, reasoning: 14}` and left the session row at `{0,0,0,0,0}`.

**So `v1 only` is a hard constraint, not a workaround.** Also note `docs/SCAN.md:79-81`'s
"v2 is reachable only via the separate `lildax` bin" is refuted — the `opencode` binary wires
the v2 handlers with an in-process execution backend (`server.ts:102, :177-181, :299-302`).
The v2 endpoint is one typo away on the same port.

If you ever must use v2, sum `SessionMessageTable.data.tokens`; `message-updater.ts:185-206`
appends a new assistant message per step, so the `draft.tokens =` assignment cannot lose
multi-step turns.

---

## Still open

| Question | Why it matters | Cost |
|---|---|---|
| ~~Can an **external** plugin register a route, or only a builtin?~~ | **YES — VERIFIED at source in Phase 8, free.** Internal and external plugins converge on the same `PluginEntry` (`plugin/tui/runtime.ts:1093-1104` and `:776-808`), the same single activation loop (`:1106-1113`), and the same `pluginApi()` (`:525` → `:577-579`) which builds `route.register` regardless of source. The ONLY place `source` is discriminated in that whole path is `:328`, a metadata display field. So the grid does not have to live inside the fork on this axis. `docs/GROWTH.md` §4 | closed |
| Can an external plugin's route survive a real workload? | The grid is a builtin. Everything TESTED here was measured on the builtin path — §4 settles *can it* at VERIFIED, not *does it under load* at TESTED | ~20 min |
| ~~**Cold start on the retirement gate.**~~ | **DECIDED in Phase 8, not built — this is now policy, not an open question.** The trigger is purely event-driven: `consider()` has one call site, no polling, and `handled` is per-process and empty on restart, so a server restarting with a session already over the gate does nothing until that session's next event, then catches it at the END of that turn. Four branches were put to the owner (don't build / sweep and retire / sweep and flag only / sweep bounded and capped) and the answer was **don't build it**. Accepted consequence: a session parked over the gate stays there if never prompted again, and one restarted mid-work is not swept until it next finishes something. Note the gap is bounded by the same arithmetic the threshold already carries — a session caught one turn late is caught at `occupancy + worst_turn` — so the sweep would have bought promptness, not margin. (This row was wrong twice about which gate catches the restart case: it credited `RETIRE_HARD`, which was inert and is deleted, then the first step boundary, which stopped applying when the predicate went per-turn.) `docs/GROWTH.md` §5 | closed |
| ~~The double-retire window~~ | **CLOSED in Phase 7, by subtraction.** Both halves are gone: the grid no longer runs `retire()` at all (`x` writes `metadata.healbot.retireRequested` and the server plugin serves it), and `consider()` now claims `busy` synchronously before its first await instead of four awaits later. One writer, one document, one flag that means something. TESTED 9/9 free (`probe_request_channel.py`), and TESTED to fail — renaming the key drops it to 5/9. See `docs/RELAY.md` §2 | closed |
| ~~`verify_control_agent.py` has not been re-executed~~ | **RUN in Phase 8, and the third form of its assertion was DISPROVED on execution.** The build agent, denied the five tools, ran `opencode run --auto …` through `bash` and created a real top-level session — so "the denied tools are the only way to make one" is false, and so is the premise the rig had carried in a comment since it was written (*"a session cannot create ANOTHER session with `bash`"*). **`healbot_*: deny` scopes CONTEXT, not CAPABILITY.** The token-budget claim it is paid for is untouched and still passes. Fourth form asserts what the deny actually makes — no healbot TOOL spawned anything, checked against the server log — and the file now runs **15/15 end to end**. `docs/GROWTH.md` §2 | closed |
| ~~The session route does not surface a **dismissed question** on screen~~ | **ANSWERED at source in Phase 8, free — and both standing hypotheses were wrong.** Not scroll position, not errored-tool-part rendering. `Question` (`routes/session/index.tsx:2543-2577`) has two branches and the only one printing `q.question` (`:2562`) is gated on `answers()`, which `parseQuestionAnswers` returns `undefined` for when there are none (`:2690`) — exactly the rejected case. It falls to `InlineTool` and renders only `Asked N questions`, struck through via `denied()` matching `QuestionRejectedError` (`:1857-1864`). **The question text has no render site on that path at all.** By construction, upstream, and not a property of the reconcile. `docs/GROWTH.md` §3 | closed |
| Does the grid handle the **remaining** traps? | Sessions created while the grid is open **do** appear (TESTED, VERIFY §5) — but that does not isolate the grid's `session.created → reload()` from the store's `session.updated` path, so the trap is mitigated in behaviour, not proven closed. Still unexercised: RED silent under `--auto`, and archived sessions never leaving the list. *(The project-scoped `session.list()` is now exercised on both the hosted and attached paths.)* | review |
| ~~Is 256,000 the right gate for *heavy-read* workloads?~~ | **Not a tuning question any more. 180,000 is DERIVED, and the derivation is the constraint.** With one gate the requirement is `RETIRE_AT + worst_turn < ceiling`. Worst measured turn growth is **~170K** (`docs/HARDEN.md` §6: occupancy 5,216 → 70,898 on a single tool result, that turn finishing at 175,090). The ceiling is **~360K** MEASURED (last good turn at 359,829, then 25 consecutive `ContextOverflowError`s). So `180,000 + ~170K = ~350K`, just inside; anything at or above ~190,000 can be carried off the cliff by one ordinary read-heavy turn. **Both figures in that sentence were superseded in Phase 8: `worst_turn` on the pinned model is 175,148, so the sum is 355,148 and the bound is 184,852.** This row twice claimed a margin it did not have — first crediting `RETIRE_HARD` (330,000, inert, now deleted), then crediting per-STEP firing (~65K exposure, true only for the one commit that shipped it). **Rule for changing it: lower freely; raise only with a new measurement of worst-case single-turn growth.** **Phase 8 made that new measurement and it points DOWN — see the row below.** **PHASE 12 MADE ANOTHER AND IT POINTS UP: the bound is 289,296 and the margin 30.4%.** Every figure in this row is a maximum over turns that mostly START AT ZERO, and the gate never faces one of those — see the `worst_turn` scope row under Load-bearing facts, and `docs/OUTCOME.md` §11 | constraint |
| ~~**`RETIRE_AT` has a live recommendation against it**~~ — but **the number is now MODEL-SPECIFIC, and that part is live** | `probe_turn_growth.py` (free, 16/16) re-derived `worst_turn` from 86 real turns instead of one — **94 as of Phase 9, with every maximum, bound and conditional unchanged (`docs/CLONE.md` §4)**. Pinned-model worst is **175,148**, so the gate's ceiling is **184,852** and 180,000 clears it by **1.3% of the context ceiling** — thinner than the margin this file condemns elsewhere. Four options went to the owner (leave and fix the prose / ~150,000 / ~136,000 / restore a second mid-turn gate) and **the decision was to LEAVE 180,000 and correct the prose**, which is done. That is a decision on the record, not inaction — do not re-open it as a defect. What it accepts: a 4,852-token margin against the largest turn ever *measured*, with nothing bounding turn growth from above. **PHASE 12 RETIRED THAT ACCEPTANCE — the 4,852 was an artifact of an unconditioned population.** Re-derived on the declared scope (completed, started >= 100,000, compaction off) the margin is **109,296, 30.4% of the ceiling**, and the bound is **289,296**. The decision to leave 180,000 was right; the arithmetic under it was answering a question the gate never asks. **The live constraint is still the model pin**: a **223,258** turn exists on `gpt-5.6-terra`, so `RETIRE_AT` is verified only while `harness/config/opencode/opencode.jsonc:16` pins `gpt-5.6-sol`, and the probe asserts it — **and the pin now matters MORE, because the in-scope maximum carrying the derivation is itself a cross-model figure**: of 12 in-scope `gpt-5.6-sol` turns, eleven are one rig's synthetic loop. `docs/GROWTH.md` §1, `docs/OUTCOME.md` §11 | constraint |
| **`verify_handoff.py` must be re-run before 21/21 can be quoted** | Phase 5 took it from 21 to 22 unconditional assertions and never executed it, so the recorded score is unreachable and four documents cite it as the Phase 4 exit gate's second clause. The clause is not disproved — a real Phase 4 run passed a real Phase 4 file — but it is cited from a superseded one. Its floor is now 22, so the next run either confirms 22/22 or says what changed. **Every paid-rig fix in Phase 10 is VERIFIED, not TESTED**, for the same reason: the next paid run of any rig is also the first execution of its floor. Floors are set to each rig's *unconditional* assertion count so a conditional leg that does not fire cannot false-fail one | one paid rig |
| The **180K gate** has never been exercised at its real value | Automatic retirement is TESTED at 20,000 and the comparison is a single `>=`, so the risk is low — but the full-scale run at 180,000 has not been paid for. What *is* covered free is the arming (`probe_headless_arm.py`, 14/14), the turn predicate the gate depends on (`probe_turn_predicate.py`, 18/18), and now the growth distribution the threshold is sized against (`probe_turn_growth.py`, 16/16) | ~$2.60 |
| **Phase 3's exit gate is still unmet** — `/code-review ultra` on the `harness/` diff | `PLAN.md:354` makes "code-review ultra findings triaged" an explicit clause. It is user-triggered and billed; it cannot be launched from an agent session. Run it from `~/Desktop/healbot` | user action |

~~Can the **cold-start reconcile** ever be tested?~~ **Closed, TESTED 21/21** — see the refuted
trap above and [docs/HARDEN.md](docs/HARDEN.md). It was never blocked; the CLI already had
`attach`.

---

## The claude fleet and config parity (Phase 13)

Claude Code as a build driver in a tmux fleet, with the same measured config discipline as
the opencode harness. The record is `docs/SHIP.md`; the working files:

| | |
|---|---|
| `harness/env.claude.sh` | env.sh's counterpart: `CLAUDE_CONFIG_DIR` redirect (the real isolation knob — see the trap above), `DISABLE_AUTO_COMPACT`, and the deliberately-NOT-set list (whose permissions entry now records the 2026-08-01 reversal: bypass is a settings default, not a launch flag) |
| `harness/claude/` | the parity config root — deliberately OUTSIDE `harness/config/`, which arms.py freezes into snapshots: `settings.json` holds the model pin (`opus`), `effortLevel: xhigh`, `permissions.defaultMode: bypassPermissions` (all three owner-directed 2026-08-01, each key verified present in the 2.1.220 binary — docs/SHIP.md §2) and `autoCompactEnabled:false`; crew constraints in `crew-constraints.md` (materialized as the `CLAUDE.md` symlink by env.claude.sh — gate.py bans the real name in-tree), the fleet-state hook, and a whitelist `.gitignore` because claude writes state (and after login, credentials) into its config root |
| `harness/hb-fleet.sh` | the fleet: socket-isolated tmux, bridge + crew windows, spawn/state/send/brief/peek/occupancy/kill, a manifest joining pane id ↔ worktree ↔ session uuid ↔ transcript path. Five measured guardrails in its header, probed |
| `harness/skills/firstmate.md` | the controller skill (captain/crewmate contract, adapted from kunchenguid/firstmate, reimplemented not vendored), installed at `~/.agents/skills/firstmate/` |
| `.carryover/verified/probe_fleet_claude.py` | free guard: live fail-open hook executions, a mutation control per source predicate, the canonical/installed skill twins (the whole `harness/skills/` population since 2026-08-02), the arms-tree separation. The count lives in the probe's own `Results(expect=)` floor and its printout, nowhere else |
| `.carryover/verified/backend.py` | the measurement seam the fleet reads through: occupancy and transcripts, unchanged from its Phase 12 build |

Open items live in `docs/SHIP.md` §5. All three screen markers and all three hook
events are now MEASURED (2026-08-03, a live crewmate on 2.1.220 — the busy marker in
both directions, the trust marker repinned off the dialog's own menu item after the
bare word `trust` false-positived on ordinary crewmate prose), so what remains open
there is the claude-side retirement marker: **provisional ~300K (30% of the 1M window), INFERRED not measured** — the
planning-stage degradation rule validated as transferring to claude-opus-5's 1M
architecture on 2026-08-01; a claude-side growth measurement is what would verify it
(the opencode numbers remain non-transferable). Deliberately not adopted, with reasons on record:
lavish-axi (vendor bill vs. need), any nvim machinery (coexistence is the pool's job), and
Claude Code's native `--tmux`/`--worktree` spawning (it owns naming and worktrees the
fleet must own).

---

## The second machine, and the public repo (Phase 14, 2026-08-02)

Windows parity for the daily-driver halves, an honest boundary around what stays
POSIX-bound, and the public face of the repo (`github.com/ScrapPack/healbot` was already
live and public; this phase made it navigable). Owner decision on record: **local models are
not part of the PC setup** — the Mac's local-model pin is machine state outside this repo.

| File | Owns |
|---|---|
| `README.md` | The public face: what this is, the repo map, both quickstarts, scope of the numbers |
| `docs/WINDOWS.md` | PC bring-up: prerequisites, the native/WSL2 capability table, Mac-only stand-ins, and the INFERRED→TESTED conversion checklist. **Owns every platform claim** |
| `docs/OPERATIONS.md` | The operator cheat sheet — commands only, no facts of its own, pointers win |
| `harness/doctor.py` | Machine preflight: PASS/FAIL/WARN/SKIP rows + a tier summary of what THIS machine can carry. The feedback loop that replaces "should work on the PC" |
| `harness/install-skills.py` | The skill-twin installer (2026-08-05): `harness/skills/` → `~/.agents/skills/` + the `~/.claude/skills` surface. Holds divergent copies rather than deciding direction; the doctor's skill-twins row verifies the installed `~/.agents` halves |
| `docs/AGENT-SETUP.md` | Live surface (2026-08-05): the paste-in prompt that lets a Claude Code session drive a fresh clone's bring-up, doctor as referee, login and pushes reserved to the human |
| `.gitattributes` | `eol=lf` pinned repo-wide (bash-everywhere survives any clone's autocrlf), `*.patch -text` (byte-exact overlay), `*.db binary` |

What actually had to change, each measured or source-verified rather than assumed:

- **The path shape at the process boundary.** Git Bash hands native processes POSIX-shaped
  `/c/...` paths, which they resolve against the drive root — reproducing env.sh's
  "worst possible failure shape" (a silently empty config). `hb_nativepath()` (cygpath `-m`
  on MSYS, identity elsewhere) now wraps every boundary-crossing export in `env.sh`,
  `env.claude.sh`, and `fleet.sh`. The mechanism it protects is VERIFIED, not hoped:
  opencode's config root comes from the `xdg-basedir` package
  (`packages/core/src/global.ts:13`), which reads `$XDG_CONFIG_HOME` on every platform —
  the Phase-14 sweep's contrary %APPDATA% claim was checked against the package source and
  was wrong.
- **The venv layout.** `gate/gate.py` and `gate/hooks/pre-push` resolve
  `venv/Scripts/python.exe` when `venv/bin/python` is absent; in gate.py a missing venv
  still reports the same ERROR it always has, and since 2026-08-02 the hook refuses a
  wholly absent venv up front by name (fresh clone/worktree — the measured symptom was a
  Windows path and "exit 127, unknown" on macOS; remedy in
  `.carryover/verified/README.md`). `tier2.py` inherits via its `PY` import.
- **`probe_citations.py`'s resolver** compared normpath'd (os.sep) paths against a
  `"/"`-joined needle — on Windows that never matches and the fallback silently widens to
  every basename collision, in a Tier-1 gate check. The needle is os.sep-normalized now;
  byte-identical behavior on POSIX.
- **The crew-constraints materialization.** `ln -s` on Windows fails without Developer Mode
  or silently degrades to a copy; env.claude.sh now falls back to a copy and refreshes it
  whenever it drifts from `crew-constraints.md` (the drift was the silent wrong-belief
  producer). The symlink path, and probe_fleet_claude's anchored assertion on it, are
  untouched on POSIX.
- **`python3` vs `python`.** fleet-state.sh resolves either (still fail-open); hb-fleet.sh's
  `py()` likewise.
- The line-number shifts these edits caused were re-derived, not offset: the `gate.py:220`
  ban and the `harness/env.sh:63-68` shell-hole block are the two everything cites, and
  `docs/RELAY.md`'s pointer to the RETIRE_HARD statement was found already 12 lines stale
  and re-derived to `harness/env.sh:139`. Gate 14/14 after.

The boundary, stated once (docs/WINDOWS.md carries the full table): **native Windows** runs
the Claude Code workflow, the opencode workflow, and the gate under Git Bash; the **tmux
fleet and the pty rig are WSL2 territory** (`term.py` imports `pty`/`termios`/`fcntl` at
module load); the **pool is Mac-only** (APFS clonefile, and its `os.kill(pid, 0)` liveness
probe would TERMINATE a lease holder on Windows). Still open, and honestly held: every
native-Windows "yes" is INFERRED until `harness/doctor.py` and docs/WINDOWS.md's conversion
checklist run on a real PC — this machine can verify mechanisms, not that machine's
behavior.
