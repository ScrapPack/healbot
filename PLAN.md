# Healbot Harness — Plan (rev 2)

A stripped opencode fork used as a clean harness layer, plus a control terminal that
nests N agent sessions as Healbot-style status frames in one terminal.

Inspiration: **Healbot (WoW)** — a grid of unit frames, color-coded by state, click-to-act.
Not terminal mirroring. Status first, interaction on focus.

> **rev 2 changed the phase structure.** An optimization pass found that `/code-review ultra`
> cannot do what Phase 1 asked of it, and that most of Phase 3's work is reachable through
> documented env switches. See §6 for the full diff against rev 1.

---

## ⚠ ERRATA — read before anything below

**This document was written before Phases 0–3 ran and has never been revised.** Phases 0–3 and
the audit in [docs/REVIEW.md](docs/REVIEW.md) refuted a number of statements below that are
still written as settled fact. The body is left intact as a record; this table is the
correction. **Where they disagree, this table wins.**

> **Citations below are pinned to THIS revision of this file.** Every `:NNN` in the *Where*
> column was silently wrong by exactly **+31** until Phase 5 — inserting this errata block
> shifted the body it cites, and nothing re-derived them, so all fourteen rows pointed 31
> lines above their target. Re-verified row by row after the shift. **If you insert or delete
> lines above §0, re-run the same check**; a table that is authoritative over the body is
> worse than useless when it points at the wrong body. The general lesson, measured in the
> Phase 5 audit: citations into upstream opencode held at 59/64, citations into this
> project's own moving files at 0/17. Only the former has a stable target.

| Where | Says | Actually |
|---|---|---|
| §0.1 line 115, and :259, :323 | `OPENCODE_CONFIG_DIR` gives config isolation | **False, and harmful.** All three of `OPENCODE_CONFIG_DIR` / `_CONFIG` / `_CONFIG_CONTENT` **merge** the harness config on top of the inherited global one. Following this row leaves you with the ollama provider block, 18 skills and `~/.claude/CLAUDE.md` while believing you are isolated. Only `XDG_CONFIG_HOME` replaces (SCAN C1, TESTED) |
| §0.1 line 122; §2 risk (b); :327 | risk (b) RESOLVED by `OPENCODE_DISABLE_AUTOCOMPACT` | Reaches the legacy compactor only. Use `"compaction": {"auto": false}` in the config file (SCAN C2) |
| §0.1 line 123; §2 risk (d); :366 | the yellow border may be gated | False alarm. The gate is `["app","cli","desktop"].includes(flags.client)` and `OPENCODE_CLIENT` defaults to `cli` (SCAN C3). Still worth confirming for a non-CLI client |
| §0.1 line 124 | `OPENCODE_ENABLE_PARALLEL` = "parallelism, relevant to N-session operation" | **Unrelated.** It selects the web-search provider (parallel.ai vs exa), `runtime-flags.ts:36-39`. Nothing to do with session concurrency |
| §1 (:152-179) | Ink grid + PTY hand-off hybrid; focus suspends Ink and hands off to `opencode attach` | **Superseded by PROBE F7 (TESTED).** The grid is a plugin-registered route inside the fork's TUI; focus is `route.navigate("session", {sessionID})`. No PTY, no Ink, no suspend/resume. (`opencode attach --session`/`--mini` *do* exist, so the fallback is real if F7's external-plugin case fails) |
| :162-163, :251, :280 | `packages/tui` is Go; "TS core + Go TUI" | 33 packages, **zero** `.go` files. The TUI is TypeScript + SolidJS on OpenTUI (PROBE F1/F2) |
| §2 risk (a) (:185-188) | 350K "must mean cumulative tokens" because the model caps at 256K | **The premise died with F6.** `openai/gpt-5.6-sol` is context 1,050,000 / `limit.input` 922,000 — a session absolutely can hold 350K. The threshold is a **context-occupancy** limit, motivated by quality degradation under context bloat. See HARNESS.md "Token accounting" |
| §2 risk (a), and :81 | `GET /api/session/{id}/context` gives per-message lifetime tokens | It returns the post-compaction tail — and for a **v1** session it returns an **empty array**, because it reads `SessionMessageTable` which v1 never writes (TESTED) |
| §0 (:100-102) | `session.next.*` listed under "Verified event types" | The entire family is **v2-only** — zero publishers in `packages/opencode/src`. On the v1 path you must use, they never fire. That includes `session.next.tool.called`, which :371 makes a frame field |
| §4 (:341-389) | Phase 4 build order: Ink in `control/`, `@opencode-ai/sdk`, spike S3 | Superseded by F7. The grid is a TUI plugin route |
| :345, :350 | "P4 already proved the SDK works on Node"; "P1/P2/P4 already answered in Phase 0" | **All three were never run** (PROBE.md:21-23). P1 was answered in Phase 1 instead; P2 in Phase 1 (C3) |
| :374 | click-to-act via `POST /permission/{id}/reply` | `client.permission.reply({requestID, ...})` — keyed by `requestID` alone |
| :386 | "Compare against `POST /session/{id}/fork`, which is cheaper" | `fork` is disqualified — it inherits the parent's whole token count within ~3s. `summarize` also wrong. Use `POST /session` + seed prompt |
| §5 (:399-402) | phases run fresh, handoff is the written artifact | The method has **no repair step**, which is why this errata table is necessary. Every phase should now also revise the artifacts it contradicts |
| §3 layout (:223, :230-235) | the `.md` substructure: `harness/AGENTS.md`, and "one .md named after the directory it sits in" | **Do not follow this.** `AGENTS.md` / `CLAUDE.md` / `CONTEXT.md` are auto-ingested into the model's context window (`session/instruction.ts:64-68`) and `SKILL.md` collides with opencode's skill-manifest glob — the exact cost this project exists to remove. The convention actually used is `<DIR>.MAP.md`; see HARNESS.md's Naming note, which forbids all four filenames |
| §4 step 4 / step 5 (:377-382) | focus hands off to a child process; a control agent drives the others | Focus is `route.navigate("session", {sessionID})`. **Both are now built and TESTED** (Phase 6, `docs/HEADLESS.md`): focus 24/24 free, the control agent 14/14 wiring + 15/16 runtime. Step 5's tools live on the *server plugin's* `tool` hook, not in `<configdir>/tool/*.ts` — only the plugin hook gets an HTTP client. There is still no key to get **back** from a session to the grid |
| §4 step 5, and §0's premise that the terminal drives everything | the control terminal is where the lifecycle happens | **Automatic retirement is not in the terminal at all.** Phase 6 moved it to a server plugin so a fleet with no client attached still retires — a TUI plugin would not have helped, since it needs a TUI, and TUI plugin scope has no Solid owner besides. The grid keeps manual `x` and the `RETIRE` border. `docs/HEADLESS.md` §1 |
| §4 build order, and the "blocked" premise | — | **Phase 5 built `serve` + `attach`** (`harness/fleet.sh`). `opencode attach <url>` is a registered command (`cli/cmd/attach.ts:7`, `index.ts:84`) running the full TUI, so the long-lived-server architecture this document assumes at :378 is real and TESTED, and the cold-start reconcile with it (21/21, `docs/HARDEN.md`) |

**Settled since, and not reflected below:** N-way session concurrency works (4 sessions
finished in the time of the slowest, not the sum) and a blocked permission does not stall the
others — so the founding premise of §4 holds. `compaction.auto:false` is right, but it turns
context overflow into a hard error rather than a compaction.

---

## 0. Ground truth (verified 2026-07-26 on this machine)

**Installed**

| Thing | State |
|---|---|
| `opencode` | **1.17.10**, `/opt/homebrew/bin/opencode` |
| `node` | v26.4.0 |
| `git` / `gh` | 2.50.1 / 2.87.3 |
| `bun` | **NOT INSTALLED** — needed only to *build* the fork (deferred, see Phase 0) |
| `tmux` / `zellij` / `wezterm` / `kitty` | none installed |
| `~/.config/opencode/opencode.jsonc` | exists — local Ollama providers, default `ollama/gemma4-agentic:q6` @ 256K ctx |
| opencode clone | none anywhere on disk — greenfield |

**The server API is the whole ballgame.** Ran `opencode serve`, dumped its OpenAPI: **153 paths**.

```
GET  /event                                   SSE stream, all events
GET  /session                                 list; per-session tokens{input,output,reasoning,cache}
GET  /session/status                          map sessionID -> {type:"idle"|"busy"|"retry"}
POST /session/{id}/prompt_async               fire prompt, non-blocking
POST /session/{id}/abort | /fork | /summarize
POST /api/session/{id}/compact
GET  /api/session/{id}/context                full context entries, each w/ tokens{}
GET  /session/{id}/todo
GET  /permission  + POST /permission/{id}/reply
GET  /question    + POST /question/{id}/reply
GET/POST /pty , GET /pty/{id}/connect         server-hosted PTYs
POST /tui/append-prompt | submit-prompt | execute-command | select-session | show-toast
GET  /agent | /command | /skill               the harness surface itself
GET/POST /experimental/worktree               worktree isolation
```

**Verified event types** (exact schemas from the spec):

```
session.status                  {sessionID, status:{type:"idle"|"busy"|"retry",...}}
session.idle                    {sessionID}
session.error
permission.asked                {id, sessionID, permission, patterns[], tool{...}}
question.asked                  {id, sessionID, questions[{question,header,options,multiple,custom}]}
todo.updated                    {sessionID, todos[{content,status,priority}]}
session.next.context.updated    {sessionID, messageID, text, timestamp}
session.next.compaction.started/.ended   {sessionID, reason:"auto"|"manual", text, recent}
session.next.tool.called/.progress/.success/.failed
pty.created/.updated/.exited/.deleted
```

Complete Healbot data model, natively. **No screen-scraping, no polling for state.**

### 0.1 The control switches (verified in the 1.17.10 binary)

This is the finding that reshaped the plan. opencode ships documented env switches for
nearly everything Phase 3 wanted to achieve by hand:

| Switch | Effect |
|---|---|
| `OPENCODE_CONFIG_DIR` / `OPENCODE_CONFIG` / `OPENCODE_CONFIG_CONTENT` | **config isolation** — point the fork at its own config, stop inheriting |
| `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS` | **stops the `~/.claude/skills` ingestion** |
| `OPENCODE_DISABLE_EXTERNAL_SKILLS` | stops external skill sources |
| `OPENCODE_DISABLE_CLAUDE_CODE` / `_PROMPT` | drops Claude Code compat layer / its prompt |
| `OPENCODE_DISABLE_DEFAULT_PLUGINS` | no default plugins |
| `OPENCODE_DISABLE_PROJECT_CONFIG` | ignore per-project config |
| `OPENCODE_PURE` (= `--pure`) | run without external plugins |
| **`OPENCODE_DISABLE_AUTOCOMPACT`** | **settles the retirement-vs-compaction conflict** |
| `OPENCODE_ENABLE_QUESTION_TOOL` | gates the `question.asked` event — **the yellow border depends on this** |
| `OPENCODE_ENABLE_PARALLEL` / `OPENCODE_EXPERIMENTAL_PARALLEL` | parallelism, relevant to N-session operation |
| `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS` | background subagents |
| `OPENCODE_EXPERIMENTAL_WORKSPACES` | workspace isolation |
| `OPENCODE_PERMISSION` | permission configuration |

Consequence: **the clean harness layer is mostly reachable by configuration, not by patching
source.** That is a large scope reduction for Phase 3.

### 0.2 The bloat, fully traced

`GET /skill` → **18**. Source, now fully accounted for:

| Source | Count |
|---|---|
| `~/.claude/skills/` | 16 |
| `~/.agents/skills/` | 16 (near-duplicate tree — 15 overlap, adds `setup-matt-pocock-skills`) |
| opencode built-in | 1 (`customize-opencode`) |
| **union after dedup** | **18** ✓ exactly matches |

So there are **two near-duplicate skill trees** feeding opencode, one of which
(`~/.agents/skills/`) you may not know exists. Neither was configured for this project.
This is Phase 3's primary target and it is now a known quantity, not a hunt.

Built-in agents: `build`, `plan` (primary) · `explore`, `general` (subagent) ·
`compaction`, `summary`, `title` (internal).

---

## 1. The PTY question — answered

**Yes, value is lost — but only on interaction, never on status.**

**Nothing is lost for the grid.** Session state, context growth, permissions, questions,
todos, tool activity, errors, compaction all arrive as typed events on `/event`. A PTY gives
you *worse* data here (regexing a screen buffer for what the API hands you as structs).
**The grid must be pure API.**

**Real value is lost on focus.** Driving a session natively gives you things that live
entirely in `packages/tui` (Go) and are unreachable from the API: the `/` command palette,
`@`-file completion and file picker, model/agent/theme switchers, the diff viewer, markdown
and tool-output renderers, prompt-box editing incl. vim mode, image paste, `/pty` panes.
Reimplementing that in Ink is a project unto itself and would rot against upstream.

**Recommendation — hand-off hybrid, not embed hybrid:**

> The grid is Ink, driven by `/event`. **Focus does not embed a PTY inside an Ink box.**
> Focus *suspends Ink and hands the whole terminal to a real child process*
> (`opencode attach <url> --session <id>`), resuming Ink on exit — the way git hands off to
> `$EDITOR`.

100% native fidelity, zero reimplementation, and the grid keeps receiving events throughout
because the server is shared. In-pane PTY embedding (xterm-headless buffer rendered into an
Ink box) stays an **optional later spike** — hardest piece in the project, and it only buys
"watch two sessions scroll at once," which the activity ticker approximates.

`--mini` is the fallback if full-screen handoff feels heavy; test both in Phase 4.

---

## 2. Open risks

**a) 350K is not a context-window number.** Your default model caps at 256K, Claude at 200K
— a session can never *hold* 350K. It must mean **cumulative tokens across the session's
life**. Available from `GET /session` → `tokens{}` and `GET /api/session/{id}/context` →
per-message `tokens{}`. **Measured empirically in Phase 0** (moved earlier in rev 2).

**b) Retirement vs. auto-compaction — RESOLVED.** `OPENCODE_DISABLE_AUTOCOMPACT` exists.
Managed sessions run with autocompact off so retirement is the sole lifecycle policy. This
is now a config decision, not a research question.

**c) NEW — parallel sessions conflict with the local-model default.** Your config defaults
to `ollama/gemma4-agentic:q6`. N concurrent sessions against one local Ollama on an M4 Pro
will serialize and crawl; your own measured figures (~250 tok/s prefill) make 4-way
concurrency impractical. **The entire premise of the control terminal is many sessions
working at once.** Mitigation: managed sessions default to a hosted API model; local stays
an explicit per-session opt-in for cheap/private work. Decide in Phase 0 — it affects the
harness config you write in Phase 3.

**d) The yellow border may not light by default.** `question.asked` appears gated behind
`OPENCODE_ENABLE_QUESTION_TOOL`. If off, the "waiting on a question" state never fires and
only `permission.asked` (red) works. Confirm in Phase 0.

---

## 3. Layout

```
~/Desktop/healbot/
├── HARNESS.md              ← root index. Phase 2 output. Points at every *.md below.
├── PLAN.md                 ← this file, moved in at Phase 0
├── docs/
│   ├── PROBE.md            ← Phase 0 output (empirical measurements)
│   ├── SCAN.md             ← Phase 1 output (architecture scan)
│   ├── STRIP.md            ← Phase 3 output (what was cut + why)
│   └── CONTROL.md          ← Phase 4 design + spike results
├── opencode/               ← the fork (git clone sst/opencode)
│   └── packages/<pkg>/<PKG>.md      ← per-subsystem map files
├── harness/                ← the stripped config layer (the actual deliverable)
│   ├── opencode.jsonc
│   ├── AGENTS.md
│   ├── agent/
│   └── command/
└── control/                ← the Ink control terminal
    └── src/
```

**Naming convention for the .md substructure** (your "easy identification" requirement):
every core directory gets **one .md named after the directory it sits in**, placed *inside*
it — `packages/opencode/src/session/SESSION.md`, `packages/tui/TUI.md`,
`harness/agent/AGENT.md`. Root `HARNESS.md` is the index: one line per map file, path +
one-sentence hook — same shape as your MEMORY.md index. Finding the map for any directory
becomes mechanical.

---

## 4. Phases

Each phase runs in **its own fresh agent session**. The handoff is the written .md artifact
— a phase reads the prior phase's output, never the prior transcript.

### Phase 0 — Bootstrap + empirical probe

Bigger than in rev 1, deliberately: the cheap measurements moved here, because measuring the
running binary in minutes beats reading source for hours.

1. `mkdir ~/Desktop/healbot`, move `PLAN.md` in, `git init`.
2. `git clone https://github.com/sst/opencode` into `opencode/` — **for reading**. No build.
3. Confirm the package layout on disk (my TS-core + Go-TUI + SDK expectation is **INFERRED
   from the CLI surface, not verified**) and correct this plan if wrong.
4. **Probes** — each against the running 1.17.10 binary, all results into `docs/PROBE.md`:
   - **P1 (risk a):** create a session, run turns, watch `GET /session` → `tokens{}` and
     `GET /api/session/{id}/context`. Is `tokens{}` lifetime or last-message? This sets the
     retirement trigger.
   - **P2 (risk d):** does `question.asked` fire without `OPENCODE_ENABLE_QUESTION_TOOL`?
   - **P3:** verify each §0.1 switch does what its name implies — especially
     `OPENCODE_CONFIG_DIR` isolation and `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS`. Confirm by
     re-running `GET /skill` and watching the count drop from 18.
   - **P4:** `npm i @opencode-ai/sdk` under Node 26 (no bun) — does it install and connect?
     Phase 4 is built on this; find out now, not then.
   - **P5 (risk c):** two concurrent sessions against local Ollama — measure the slowdown.
     Decide the default model for managed sessions.
5. **Deferred, conditional:** installing bun and building the fork. Nothing in Phases 1–4
   needs a built fork — Phase 1 reads source, Phase 3 configures the binary, Phase 4 talks
   to the server. Build only if Phase 1 concludes you must patch internals.

**Exit gate:** `docs/PROBE.md` written; P1 and P3 answered; the retirement trigger and the
managed-session default model are decided.

### Phase 1 — Architecture scan (fresh session)

**Changed in rev 2 — this is no longer `/code-review ultra`.** See §6 for why.

A **question-scoped architecture scan**, run as parallel exploration agents over the clone.
Scope by the questions below, not by the directory tree — "review `packages/**`" is
unbounded and the questions are the actual deliverable.

Scan set: `opencode/packages/**` (TS core + Go TUI), `~/.config/opencode/opencode.jsonc`,
`~/.claude/skills/*`, `~/.agents/skills/*`, `~/.claude/settings.json`, `hooks/`, `plugins/`.

**The five questions:**
1. Every path by which config enters a session, in load order — and precisely where the two
   skill trees are read.
2. Which extension points are *load-bearing for code functionality* vs. *prompt overhead*.
3. Where session lifecycle, token accounting, and compaction live in the source
   (cross-check against P1's measurement).
4. What each §0.1 switch actually gates (cross-check against P3).
5. Where the TUI reads state — the reusable surface if in-pane PTY is ever revisited.

**Exit gate:** `docs/SCAN.md`, findings tagged VERIFIED / INFERRED per your evidence rule,
every source claim citing `file:line`.

### Phase 2 — Outline (fresh session)

Input: `docs/SCAN.md` + `docs/PROBE.md`. No prior transcript.

1. Write `HARNESS.md` — the root index.
2. Write one `<DIR>.md` per core subsystem from Phase 1, placed in its directory.
3. Index all of them from `HARNESS.md`.

**Constraint:** map files describe *structure*, not narrative. If a line does not help you
find or change something, cut it.

**Exit gate:** from `HARNESS.md` alone, you can name the file that owns any given behavior.

### Phase 3 — Strip (fresh session)

Input: `HARNESS.md`, `docs/SCAN.md`, `docs/PROBE.md`.

Governing rule, in your words: **models are capable in base form.** Agentic method
structures and command structures can earn their place; anything the model architecture
already covers is overhead.

Per-item test:
- **Keep** if it grants a capability the model lacks — a tool, an integration, a real
  workflow gate, a project-specific fact it cannot infer.
- **Cut** if it instructs the model to do what it already does — generic "be thorough",
  restated reasoning procedure, persona framing, redundant checklists.

**Switches first, edits second.** Per §0.1 most of this is configuration:
- `OPENCODE_CONFIG_DIR` → the fork gets its own config namespace, inheritance stops.
- `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS` + `OPENCODE_DISABLE_EXTERNAL_SKILLS` → both skill
  trees off. Default-deny; re-add only what survives the test, into `harness/command/`.
- `OPENCODE_DISABLE_DEFAULT_PLUGINS`, `OPENCODE_DISABLE_PROJECT_CONFIG` as warranted.
- `OPENCODE_DISABLE_AUTOCOMPACT` for managed sessions (risk b).
- Agents: keep `build` / `plan` / `explore` / `general`; leave `compaction` / `summary` /
  `title` alone — load-bearing.

**Then `/code-review ultra` — this is where it belongs.** By now you have a real diff (the
stripped `harness/` config, and any source patches). Reviewing *that* diff is exactly what
the tool is built for, and Phase 3 is where a review actually protects you, since you are
deleting things that may be load-bearing. Note: it is user-triggered and billed; I cannot
launch it. Run it from `~/Desktop/healbot`.

**Exit gate:** `docs/STRIP.md` lists every cut with a one-line justification; `harness/`
holds the clean config; `GET /skill` and `GET /command` return only what you deliberately
kept, and you can say what each survivor buys you; code-review ultra findings triaged.

### Phase 4 — Control terminal (fresh session, largest phase)

Input: `HARNESS.md`, `docs/STRIP.md`, `docs/PROBE.md`. Build in `control/`, TypeScript +
Ink, against `@opencode-ai/sdk` (generated from the same OpenAPI dumped above → typed
sessions and events). P4 already proved the SDK works on Node.

**Architecture:** one `opencode serve` hosts every session. The control TUI is a client.
Sessions are server-side and keep running whether or not anything renders them.

**Remaining spike** (P1/P2/P4 already answered the rest in Phase 0):
- **S3:** does suspend-Ink → `opencode attach` child → resume-Ink round-trip cleanly?
  Settles the focus model. Test `--mini` as the fallback.

**Build order:**

1. **Event spine.** Subscribe `/event`, maintain an in-memory session registry. Everything
   reads from this.
2. **The grid.** Ink flexbox, N frames splitting available space, reflowing on resize.
   Border color from real state:

   | Border | Source |
   |---|---|
   | dim gray | `session.idle`, nothing pending |
   | amber, pulsing | `session.status` `{type:"busy"}` |
   | **red glow** | `permission.asked` — blocked on you |
   | **yellow glow** | `question.asked` — blocked on you *(needs P2 confirmed)* |
   | green | idle *after* work — task complete |
   | purple | `session.next.compaction.started` |
   | red flash | `session.error`, or `session.status` `{type:"retry"}` |

   Frame contents: title, agent, model, todo progress bar (`todo.updated`), last tool
   (`session.next.tool.called`), token gauge vs. the retirement ceiling.
3. **Click-to-act (the Healbot part).** Answer a blocked session *from the grid* without
   focusing it: `POST /permission/{id}/reply`, `POST /question/{id}/reply`. This is the
   feature that makes the project worth building — one keypress clears a red frame.
4. **Focus / expand.** Per S3: suspend Ink, hand terminal to `opencode attach --session <id>`,
   resume on exit.
5. **Control agent.** Its own session in the same server, with tools to spawn / prompt /
   abort / retire the others (`POST /session`, `/prompt_async`, `/abort`). Same registry you see.
6. **Retirement + handoff protocol.** On threshold (per P1):
   - finished → retire, free the slot;
   - unfinished → generate handoff (`POST /session/{id}/summarize` + its `/todo` and
     `/diff`), spawn fresh, seed via `prompt_async`, retire the old one, hand the grid slot
     to the replacement.

   Compare against `POST /session/{id}/fork`, which is cheaper. Reuse your existing
   `context-handoff` skill's document format rather than inventing one.
7. **Worktree isolation** (optional). `/experimental/worktree` per session — worth it the
   moment two sessions touch one repo.

**Exit gate:** four sessions concurrent, one deliberately blocked on a permission prompt and
answered from the grid without focusing, one driven past the retirement threshold and handed
off with continuity intact.

---

## 5. Sequencing

Phases 0–3 are strictly ordered; each consumes the prior artifact. Phase 0's probes now
de-risk Phase 4 up front, so S3 is the only unknown left when Phase 4 starts.

Run each phase in a fresh session: read the input .md, do the work, write the output .md, stop.

---

## 6. What rev 2 changed, and why

1. **`/code-review ultra` moved from Phase 1 to Phase 3 — blocking fix.** VERIFIED: the
   code-review command is a **PR/branch diff reviewer**. It fetches a diff, reviews "the file
   changes in the pull request", explicitly discards "real issues, but on lines the user did
   not modify", and comments back on the PR. A pristine `git clone sst/opencode` has **no
   diff** — Phase 1 as originally written would have reviewed nothing. Phase 1 becomes a
   question-scoped architecture scan; code-review ultra moves to Phase 3 where a real diff
   exists and where a review actually protects you.
2. **Phase 3 is mostly switches, not surgery.** §0.1 found documented env switches for
   config isolation, skill ingestion, plugins, project config, and autocompact. Large scope
   reduction.
3. **Risk (b) resolved before starting.** `OPENCODE_DISABLE_AUTOCOMPACT` exists; the S2
   spike is deleted.
4. **bun + building the fork demoted from blocking gate to conditional.** Nothing in
   Phases 1–4 needs a built fork. Front-loading a monorepo build bought nothing.
5. **Cheap measurements moved into Phase 0 (P1–P5).** Measuring the running binary beats
   reading source; results feed Phase 1's questions instead of depending on them.
6. **New risk (c) surfaced:** N-way concurrency vs. the local-model default — this conflicts
   with the core premise of the project and needed to be decided before writing harness config.
7. **New risk (d) surfaced:** the yellow border may be gated behind
   `OPENCODE_ENABLE_QUESTION_TOOL`.
8. **The 18 skills fully traced** to two near-duplicate trees (`~/.claude/skills`,
   `~/.agents/skills`) plus one built-in — arithmetic confirmed. Phase 3's target is now known.
9. **Phase 1 scope changed from tree-scoped to question-scoped** — "review `packages/**`" is
   unbounded; the five questions are the deliverable.
