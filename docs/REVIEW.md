# Probe review — assumption audit of phases 0–3

Date 2026-07-26. Method: 7 domain probes over `PLAN.md`, `docs/PROBE.md`, `docs/SCAN.md`,
`HARNESS.md`, `docs/STRIP.md` and the shipped `harness/`; each probe followed by an
independent skeptic that re-derived its findings from source rather than trusting them; one
completeness critic over the merged result. 15 agents, 1,047 tool calls.

96 findings, 61 adversarial reviews. Verdicts after the skeptic pass:

| | count |
|---|---:|
| CONFIRMED | 35 |
| OVERSTATED | 31 |
| REFUTED | 13 |
| STALE | 8 |
| UNVERIFIABLE | 2 |

Evidence tiers as used elsewhere in this project. Findings marked **(own check)** were
re-verified directly in the main session, not accepted from an agent.

## Status — what has been actioned

| | Item | State |
|---|---|---|
| R1 | Retirement trigger measures the wrong quantity | **Resolved by decision.** 350K is a *quality* limit on context bloat, so the metric is live **occupancy**, not cumulative spend — and `cache.read` is *included*, not excluded. Rewritten in `HARNESS.md`, `SCAN.md §2`, `opencode.jsonc` |
| R2 | v2 never writes `session.tokens` | **Settled.** v1 is now written down as a hard constraint |
| R3 | `session.next.*` is v2-only | **Documented** as a trap and in the `PLAN.md` errata |
| R4 | Fork model pin `opencode/` → broken | **FIXED.** `opencode/.opencode/opencode.jsonc` now pins `openai/gpt-5.6-sol`; TESTED, sessions run from the fork root again |
| R5 | The strip's false ✗ | **Retracted** in `STRIP.md`, with the model mix-up explained |
| §4.1 | N-way concurrency unproven | **TESTED — it holds.** See below |
| §4.2 | 350K unsourced | **Answered by the owner**, see R1 |
| — | `env.sh` breaks in dash/ksh | **FIXED.** Now validates and refuses loudly |
| — | `OPENCODE_PURE` rationale false | **FIXED** in `env.sh` and `STRIP.md` |
| — | False "SCAN/PROBE never committed" across 7 maps | **RETRACTED** in all 7 |
| — | `TOOL.MAP.md` counted `websearch` | **FIXED**, 12 → 11 tools / 19,903 B, reconciling it with STRIP |
| — | `~20 tok/skill` | **FIXED** → ~108 tok/skill in `SCAN.md` and `SKILL.MAP.md` |
| — | Root index omitted Phase 3 | **FIXED.** `HARNESS.md` now leads with the deliverable |
| — | `PLAN.md` never revised | **FIXED.** rev-3 errata table at the top |
| 9 | `/code-review ultra` on the `harness/` diff | **Still open** — user-triggered, cannot be launched from here |

### Concurrency — TESTED, the founding premise holds

Measured against the harness on one `opencode serve`, using `openai/gpt-5.4-mini` (same
`gpt.txt` + `apply_patch` + no-websearch routing as `gpt-5.6-sol`, ~7x cheaper):

| | wall clock | per-turn |
|---|---:|---|
| 4 sessions fired simultaneously | **5.72s** | 2.84 / 3.01 / 3.21 / 5.72 |
| the same 4 run serially | **10.45s** | 2.43 / 2.69 / 2.60 / 2.72 |

Parallel wall clock equals the **slowest single turn exactly** (ratio 1.00), not the sum. The
server does not serialize. Throughput gain at N=4 is ~1.8x rather than 4x because per-turn
latency degrades under load — that contention is provider-side, not opencode.

**Head-of-line blocking: none.** With `OPENCODE_PERMISSION='{"bash":"ask"}'`, one session was
parked on a `permission.asked` while three others ran plain turns. All three completed
(`finish: "stop"`); the blocked one never returned — confirming both that the premise holds and
that a pending permission hangs forever with no timeout.

### One new defect found while testing — ~~defect~~ **REFUTED, 2026-07-27**

This section originally read: *"`POST /session/{id}/prompt_async` accepts a prompt and executes
nothing. The user message is stored; no assistant turn follows, no error is logged."* It is
**wrong**, and the way it is wrong is a trap worth keeping.

`prompt_async` works. TESTED on `openai/gpt-5.6-sol`, side by side with the synchronous path on
one server: it acks in **0.01 s** (against 5.1 s for `POST /message`), and the turn **completes
2.0 s after the ack** with `finish: "stop"` and the same answer the sync control gave. It runs
on the same model, accrues tokens normally, and publishes no `Session.Event.Error`. Spawn-and-
seed works too: a fresh session seeded through it replied and started at its own occupancy.

**Why it looked broken, and it will fool you the same way.** `prompt_async` creates the
assistant message row within ~**20 ms** of the ack, and that row is **empty** until the turn
actually runs. Poll for "an assistant message exists" and you get `true` almost immediately with
no content; check once, shortly after firing, and you see a stored user message and a blank
assistant row — exactly the description above. The completion signal is the assistant message's
own `time.completed` / `finish`, not the existence of the row. This session made the identical
mistake on its first attempt before catching it.

Source agrees, and did all along: `handlers/session.ts:311-328` calls the **same**
`promptSvc.prompt()` as the synchronous handler, wrapped in
`Effect.forkIn(scope, {startImmediately: true})`, and `scope` is bound at `:62` inside the
`HttpApiBuilder.group()` construction generator — the layer scope, which outlives any single
request, so the fiber is not interrupted when the response returns.

**Consequence for Phase 4:** `PLAN.md:335`/`:341` may build the spawn-and-seed path on
`prompt_async` as written. No workaround is needed.

---

## 1. Ship-blockers

### R1 — The retirement trigger measures the wrong quantity (CRITICAL, own check)

`HARNESS.md:82-83` prescribes thresholding `session.tokens` on `input + output + reasoning`,
excluding `cache.read`. opencode's own capacity check is a different metric on different
fields, and nothing in the tree reconciles them.

`packages/opencode/src/session/overflow.ts:21-33`:

```ts
export function isOverflow(input: { cfg; tokens: SessionV1.Assistant["tokens"]; model; outputTokenMax? }) {
  if (input.cfg.compaction?.auto === false) return false
  if (input.model.limit.context === 0) return false
  const count = input.tokens.total || input.tokens.input + input.tokens.output + input.tokens.cache.read + input.tokens.cache.write
  return count >= usable(input)
}
```

Three things follow, all verified:

1. `isOverflow` reads **per-assistant-message occupancy**, not the cumulative session row, and
   it **includes `cache.read`** — the field `HARNESS.md` says to exclude.
2. The harness sets `"compaction": {"auto": false}`, so line 28 makes `isOverflow` return
   `false` unconditionally. The overflow check is dead under the shipped config.
3. When the provider then rejects the request, `packages/opencode/src/session/processor.ts:607-613`
   marks the assistant message `finish = "error"`, publishes `Session.Event.Error` and sets
   status idle. **A session that fills its window hard-errors; it does not compact and it is
   not retired.**

Consequence for the grid: a session can hard-fail on context while its cumulative counter sits
far below 350K, and a cheap long-running session can cross 350K at ~5% occupancy and be retired
for nothing. `PLAN.md:329`'s "token gauge vs. the retirement ceiling" watches a counter that
cannot predict the failure it exists to prevent.

The observable that *does* predict it is already on the wire and is named in no document: the
assistant message's own `tokens` (`packages/schema/src/v1/session.ts:472-481`) against the
model's `limit.input`.

### R2 — The v2 engine never writes `session.tokens` (CRITICAL, own check)

`HARNESS.md:135` records this as the project's biggest open question, with two Phase-2 agents
contradicting each other. It is settled, and the answer is the dangerous one.

`grep -rn applyUsage packages --include="*.ts"` → 5 hits, all in
`packages/core/src/session/projector.ts` (:90 def, :286, :304, :327, :328), every call site
inside a `SessionV1.Event.*` projection. The v2 runner carries usage on a different event
(`runner/publish-llm-event.ts:396-400` → `runner/llm.ts:326-333`) which projects to the
**message** row (`message-updater.ts:209-214`), not the session row.

The skeptic settled it at TESTED tier: a v2 prompt on a 1.18.5 source server burned
`{input:3381, output:4, reasoning:14}` and left the session row at `{0,0,0,0,0}`.

Two corrections to `HARNESS.md` follow:

- `HARNESS.md:143-153` records that `POST /api/session/{id}/prompt` "produces no assistant
  turn after 60s" and uses that to justify deferring the question. **Not reproducible** — the
  skeptic got a complete turn in ~1.2s. The earlier failures are still in the DB, each holding
  only `agent-switched` + `model-switched` rows pinning `gpt-5.6-sol`; the working run used a
  different model. The negative was model-specific, not structural.
- `docs/SCAN.md:79-81`'s "v2 is reachable only via the separate `lildax` bin" is **refuted**.
  The `opencode` binary wires the v2 handlers (`server.ts:102`, `:177-181`) with an in-process
  execution backend (`server.ts:299-302` → `core/src/session/execution/local.ts:16-28`).

So v2 is live on the shipped binary, reachable on the same port, and any client that uses it
gets a session the retirement trigger cannot see. "Drive v1" is not a hedge against an unknown —
it is a **hard requirement**, or the control terminal must sum `SessionMessageTable.data.tokens`.

### R3 — The whole `session.next.*` event family is v2-only (CRITICAL, own check)

`PLAN.md:57-59` lists `session.next.context.updated`, `session.next.compaction.started/.ended`
and `session.next.tool.called/.progress/.success/.failed` under "Verified event types".
`PLAN.md:328-329` makes `session.next.tool.called` the "last tool" field of every grid frame.

`grep -rn "session\.next\." packages/opencode/src --include="*.ts"` → 4 hits, **all consumers**
(`cli/cmd/run/stream.transport.ts:149-150`, `cli/cmd/run/session-data.ts:778,798`), zero
publishers. The only publisher factory is `packages/core/src/session/runner/publish-llm-event.ts`,
whose sole non-test importer is `packages/core/src/session/runner/llm.ts:36`.

This is mutually exclusive with R2's prescription. **The engine `HARNESS.md` tells you to use
cannot emit the events `PLAN.md` builds the frames from** — and a grid built on that vocabulary
gets silence, not an error. Same root cause as the PURPLE gap: `session.next.compaction.started`
cannot fire on the v1 path under any flag, because v1's compactor publishes only
`session.compacted` (`opencode/src/session/compaction.ts:508`).

### R4 — Every session started inside the fork dies before its first turn (CRITICAL, own check)

`opencode/.opencode/opencode.jsonc:9` pins `"model": "opencode/gpt-5.6-sol"`. That model id
does not exist — the catalog has `openai/gpt-5.6-sol`, `-fast`, `-pro`, and no
`opencode/gpt-5.6-sol` (own check: `opencode models | grep gpt-5.6-sol`). Project config beats
global config, so it overrides the harness's correct `openai/` id.

```
Error: Model not found: opencode/gpt-5.6-sol. Did you mean: gpt-5.6-sol?
```

Fails identically with and without the harness. It came in with fork commit `174e54d`
(2026-07-26 11:13), whose message asserts the pin "makes the documented default the actual
default" and reports measurements taken under it — measurements that cannot have been taken,
since the id never resolves. **This is the directory Phase 4 builds in.** One-character fix:
`opencode/` → `openai/`.

Note: `174e54d` landed on the fork *during* this review, from outside this session (no probe
agent ran `git commit` — checked against the workflow transcripts).

### R5 — The single ✗ in the strip's verification table is a misattribution (CRITICAL)

`docs/STRIP.md:189` marks the tool-using turn failed, and `:214-230` attributes it to a
pre-existing `opencode run` defect, "consistent with the Phase 2 trap: no timeout on a pending
permission".

TESTED, twice by the probe and again by the skeptic: **the tool-using turn works.** Under the
harness in a scratch dir — `% Patch 1 file`, `→ Read hello.txt`, file on disk, 8s.

The stock-side comparison compared two different **models**. Stock resolves to the user's global
default `ollama/gemma4-agentic:q6`, which mangled a path and got auto-rejected. The skeptic's
control run settles it: stock config with only `-m openai/gpt-5.6-sol` forced → identical
success. The stated cause is also wrong — `opencode run` prints `auto-rejecting` and returns; it
does not hang.

Two consequences: the "strip removed no capability" conclusion is hedged on a defect that does
not exist, and **any other stock-vs-harness A/B in that document silently compared gemma4 to
gpt-5.6-sol**.

---

## 2. High severity

### The 41% headline is a best case the harness can never deliver

Three independent scope errors, all measured:

| Scope error | Effect |
|---|---|
| Measured in an empty neutral dir. In the fork root, the project `AGENTS.md` (8,748 B) loads in **both** arms | 46,332 B baseline → cut is 33.3%, not 41% |
| The −7,569 B prompt replacement applies to the **`build` agent only**. `plan` and `general` define no `prompt` (`agent/agent.ts:141,156,182`), so every subagent session still gets the full 9,284 B `gpt.txt` | subagent sessions pay full freight |
| The −506 B tool trim ships **OFF** (`env.sh` line commented) | delivered delta is 15,427 B / 42.03% by direct measurement, vs the doc's 15,134 B / 41.22% |

The saving itself is real and cwd-invariant at ~15.4 KB. It is the *percentage* and the
*coverage* that do not hold.

Worse for the v2 path: `packages/core` has **no** `gpt.txt`, no `~/.claude` ingestion and no
external-skill discovery — its builtin `build` prompt is 190 characters
(`core/src/plugin/agent.ts:13`). 96.7% of the claimed delta is v1-only, and on v2 the harness's
own `build.md` would be a ~1,525-char *addition*.

### The "18 → 1 skills, 20 → 3 commands" floor does not hold in the fork

`skill/index.ts:205-208` runs the config-directory scan unconditionally; `config/paths.ts:23-41`
walks `.opencode` up from cwd. TESTED in the real fork with the full `env.sh` switch set:
**2 skills, 12 commands, 9 agents** — it silently readmits 8 upstream repo commands
(`commit`, `changelog`, `translate`, …), an `effect` skill and 2 extra agents. In a neutral dir:
1 / 3 / 7, as documented.

Corollary: `docs/SCAN.md:243`'s "19 skills" figure was measured inside the fork, which is why it
never matched STRIP's 18.

### `PATCH time.archived` does not remove a session from anything

The DELETE half is right (`session.ts:608-626` recurses over children). But archiving filters
**nothing** the grid would read: `ListInput` (`session.ts:302-311`) has no `archived` field;
`listByProject` (`:957-1009`, the query behind `GET /session`) has no `time_archived` predicate;
the only filter is `listGlobal` (`:564`), reachable solely via `GET /experimental/session`; the
v2 list does not filter; `grep -rn archived packages/tui/src` → zero hits.

**Retired sessions keep appearing in `GET /session`, `GET /api/session` and the TUI list.** The
control terminal must filter `time.archived` itself — a requirement written down nowhere.

### The threshold fires 13 turns earlier than documented

Recomputed against a DB copy of the reference 101-turn session:

| definition | crosses 350K |
|---|---|
| `input + output` | turn 90 |
| **`input + output + reasoning`** (the recommended rule) | **turn 77** |
| `input + output + cache.read` | turn 17 |

`SCAN.md`'s two rows are exact. But `HARNESS.md:82-83` carried the turn-90 figure forward and
attached it to the +reasoning rule, which fires at turn 77 — ~76% of the session's life, not
~89%. And turn 90 is fragile: turns 86–89 sit at 341K–347K and only clear on a 154K input spike,
so any additive term moves the crossing into the 70s.

### The documented cross-directory fallback does not widen scope

`SCAN.md §6` offers `client.session.list()` polled off `api.state.session.count()` as the
workaround for the subdirectory trap. `Session.list` is hard-scoped to `ctx.project.id`
(`session.ts:548-555`); `ListInput` has no `projectID` field, so `...input` cannot widen it.
And `api.state.session.count()` returns `sync.data.session.length` (`adapters.tsx:120-122`) —
**the same narrowed store**, so the tripwire can never detect what it was meant to detect.

The real cross-project path is `client.experimental.session.list()` → `/experimental/session`,
which is cursor-paginated (not capped at 100, as the probe first claimed).

### `PLAN.md` §4 is the only Phase 4 build order, and every premise in it is dead

Errata, `PLAN.md` line → superseding doc:

| line | claim | superseded by |
|---|---|---|
| :72, :216, :280 | `OPENCODE_CONFIG_DIR` gives config isolation | SCAN C1 — **REFUTED, own check**: all three of `OPENCODE_CONFIG_DIR` / `_CONFIG` / `_CONFIG_CONTENT` *merge on top of* the global config. Following this row leaves you inheriting the ollama provider block, 18 skills and `~/.claude/CLAUDE.md` while believing you are isolated |
| :79, :147-149, :284 | risk (b) RESOLVED by `OPENCODE_DISABLE_AUTOCOMPACT` | SCAN C2 |
| :80, :158-161, :323 | risk (d), yellow border gated | SCAN C3 |
| :81 | `OPENCODE_ENABLE_PARALLEL` = "parallelism, relevant to N-session operation" | **REFUTED** — it selects the *web-search provider* (parallel.ai vs exa), `runtime-flags.ts:36-39`, used only in `tool/registry.ts:289` and `tool/websearch.ts`. Nothing to do with session concurrency |
| :113-136 | Ink + PTY hand-off hybrid | PROBE F4/F7 |
| :119-120, :208, :237 | `packages/tui` is Go / "TS core + Go TUI" | PROBE F1 — zero `.go` files |
| :143-144 | `/api/session/{id}/context` gives per-message lifetime tokens | **worse than SCAN said**: `SessionHistory` reads `SessionMessageTable` exclusively, which v1 never writes. For a v1 session `/context` returns an **empty array**. TESTED: the 101-turn reference session has 0 `session_message` rows and 738 `part` rows |
| :298-346 | whole Phase 4 build order: Ink, `@opencode-ai/sdk`, spike S3 | PROBE F7 |
| :302, :307 | "P4 already proved the SDK works on Node" / "P1/P2/P4 already answered in Phase 0" | PROBE.md:21-23 — **all three NOT RUN** |
| :343 | `fork` "is cheaper" | SCAN §3 — fork is disqualified |

### The `/<skill>` bypass is worse than documented

Both security claims CONFIRMED, and upgraded from code-read to TESTED. The skeptic ran both in
one process with `OPENCODE_PERMISSION='{"skill":"deny"}'`:

- the deny **is** effective on the tool path (no `skill` tool in the captured request, no
  `<available_skills>` block at all), and
- the slash path executed the skill to completion anyway, with a `!\`cmd\`` body running a real
  shell (`$((3*13))` → `39` on the wire).

So `permission: {skill: "deny"}` — which `SKILL.MAP.md:112` recommends as a strip lever —
provides **zero** protection on the slash path. Citation drift worth fixing:
the block is `prompt.ts:1397-1408`, not `:1396-1406`.

### `~20 tok/skill` is wrong by 5.4x

Wire capture (both agents, independently, via mock provider endpoints): `<available_skills>` is
**7,794–7,798 B for 18 entries = 433 B/skill ≈ 108 tok/skill**. `SKILL.MAP.md:63` contradicts
itself in one sentence: "~20 tok/skill (measured ~1,930 tok for 19 skills)" — 1930/19 = 101.6.
The *block* total reproduces; only the per-skill unit price is broken — and that is exactly the
number `STRIP.md`'s keep/cut test prices decisions with.

### `AGENTS.md` stacking, and a source comment that is wrong about its own code

`SCAN.md:334`'s "instruction files stop at the FIRST match" is misleading. The `break` is over
the *filename list*, not over ancestors: `instruction.ts:126-131` calls `fs.findUp(...)` and
`fs-util.ts:154-166` collects **every** hit up to the worktree root. TESTED with a synthetic
3-level repo: all three `AGENTS.md` markers appear. The source comment at `instruction.ts:123`
claims the opposite and is wrong.

For this fork, a session at `packages/opencode/src/session/llm` ingests 22,273 B of `AGENTS.md`,
not 8,748. Separately, `tool/read.ts:300` re-attaches nearby instruction files on every read
(67,489 B reachable in this tree, excluding the root one already in the system prompt) — and it
re-attaches after each compaction, since `extract()` skips compacted parts (`instruction.ts:22`).

### Two repos that cannot resolve each other's paths, one of them unbacked

`.gitignore` excludes `/opencode/`. The 14 `*.MAP.md` files and the spike live only in the fork,
whose only remote is `https://github.com/sst/opencode` — so branch `healbot` has no valid push
destination. `HARNESS.md:26-54`'s 14 links all point into the ignored subtree.

This has **already caused a false conclusion**: fork commit `ce4a844` asserts `docs/SCAN.md` and
`docs/PROBE.md` "were never committed (no blob by either name in any reachable tree)" and
stamped UNVERIFIED on 33 citations across 7 maps. Both files are committed — in the other repo.
The claim is still live at `TOOL.MAP.md:25-27`.

### Phase 3's exit gate is unmet

`PLAN.md:296` requires "code-review ultra findings triaged". `STRIP.md:236-238` says it was
never run; no later commit closed it. The two fork commits that sound like reviews (`ce4a844`,
`bd54bab`) are docs-only diffs inside `packages/**` and touch nothing under `harness/`.

The unreviewed diff is the risky one: 48 lines of environment switches, a prompt that *replaces*
`gpt.txt`, and 91 lines that mutate live tool descriptions. That diff class demonstrably
contains live defects — `OPENCODE_DISABLE_DEFAULT_PLUGINS` broke every model turn and was found
by accident, and this review found a second error in the same file (below).

---

## 3. What held up

Load-bearing claims that reproduced under adversarial re-derivation. Recorded because "this one
holds" is decision-relevant.

- **`XDG_CONFIG_HOME` isolation.** Reproduced: config dir redirects, `debug config` returns only
  harness keys, the ollama provider block is gone. Full replacement, not merge. The
  export-before-start requirement is real (`global.ts:13` is a module-scope const).
- **`"compaction": {"auto": false}` reaches the legacy engine.** TESTED via `GET /config` and
  `overflow.ts:28`. The probe called the both-engines claim OVERSTATED; the skeptic overturned
  that and confirmed it at low severity. (Moot in practice — see R1, where `auto:false` is what
  converts overflow into a hard error.)
- **The prompt-replacement ternary** (`llm/request.ts:60`) and that `agent/build.md` overrides
  the builtin `build` rather than duplicating it, preserving its other properties.
- **The `trim-tools.ts` plugin loads and works**: relative path resolves, the named-export shape
  is accepted, `todowrite` 2,548 → 2,042 B with `HARNESS_TRIM_TOOLS=1`.
- **Token accounting on v1**: the accumulator chain, the exact DB-sum match, and monotonicity
  through compaction. The skeptic extended it — **40/40 sessions** in the real DB match
  `SUM(step-finish)` exactly.
- **`fork` inherits the parent's count**; `summarize` mutates in place. Both stand.
- **The skill-dedup race**, the `18 = 16 ∪ 16 + 1` arithmetic (15 of 16 `~/.claude/skills`
  entries are symlinks into `~/.agents/skills`), and C3's yellow-border correction.
- **The grid-state trap block**: RED never fires under `--auto`, `session.created` unhandled,
  the 30-day + subdirectory filter, the 100-message cap, no `api.state.session.list()`,
  `route.navigate` dropping params, the PURPLE gap, and the finished-vs-never-started
  discriminator.
- **The `.MAP.md` naming rule.** The manifest globs are literal `SKILL.md`
  (`skill/index.ts:23-25`) and the ingest list is exactly the three named filenames — the rule
  is sound and all 14 map files are safe. (Minor: `HARNESS.md:12` cites `instruction.ts:64-68`;
  the array spans `:65-70`.)
- **`opencode attach --session <id>` and `--mini` are real** (`cli/cmd/attach.ts:7-50`). The
  abandoned PTY fallback exists; do not delete it from the plan merely because it is labelled
  stale.

---

## 4. Not proven, by anyone, in four phases

1. **N concurrent sessions on one server.** The founding premise and the Phase 4 definition of
   done. P5 asked for a two-session measurement; `PROBE.md` F6 answered a different question
   (picked a hosted model) and declared risk (c) retired. **No concurrent-session observation
   exists in any document.** Encouraging but insufficient: no semaphore in the v1 session path,
   fan-out sites use `concurrency: "unbounded"`. Untested interaction: `HARNESS.md`'s **Behavior → file** section says an
   approval is instance-wide with no `sessionID` filter — nobody has checked whether one blocked
   permission stalls the other three. ~15 minutes to settle.
2. **Where 350K came from.** Nine mentions across the tree, not one sourcing it. Introduced at
   `PLAN.md:142-144` as already-known and reinterpreted in the same breath as cumulative spend.
   That inference is now baked into the shipped config as the justification for `auto: false`.
   Given R1, if it was originally meant as *occupancy*, the reinterpretation and the
   compaction-off decision that rests on it are both wrong. One question to the owner settles it.
3. **The Phase 4 exit gate is not adjudicable.** "Driven past the retirement threshold" means
   350K real tokens on a frontier model, and no threshold is configurable anywhere in the
   deliverable. "Handed off with continuity intact" has no definition and no check.
4. **External plugin route registration.** F7 proved a *builtin* registers a route. That
   `route.register` is on the public API is verified; that an external plugin can actually use
   it is not.
5. **The spike on HEAD.** F7's five-row evidence table describes `healbot-spike.tsx` at commit
   `0fdcfb6`. The file has changed since and the current version has never been run.

---

## 5. The structural finding

The plan's method — fresh session per phase, artifact-only handoff — **has no repair step**.
Corrections are always appended to a *new* document while the old one stays wrong at the path
everything links to. `SCAN.md`'s C1/C2/C3 never edited `PROBE.md`; `STRIP.md`'s "Correction to
Phase 1" never edited `SCAN.md`. Four phases in, the result is:

- `PLAN.md` is linked **first** from the root index and has never been revised.
- `HARNESS.md`, the designated root index, contains **zero** references to `STRIP.md`,
  `harness/`, `env.sh` or Phase 3. `grep -n "STRIP\|harness/\|env.sh\|[Pp]hase 3" HARNESS.md`
  returns nothing. The deliverable is orphaned from its own index.
- `HARNESS.md:136-137` still lists two questions Phase 3 answered 24 minutes later.
- `HARNESS.md:91-93`'s cost model is the superseded `anthropic.txt` measurement.
- `PLAN.md:300` omits `SCAN.md` from Phase 4's inputs — yet the border mapping, the reply
  shapes, the retirement field selection and the handoff mechanism exist **only** there.

Staleness here is structural, not incidental, and it compounds at every phase.

---

## 6. What is left

Items 1–8 of the original order are done (see Status above). What remains:

1. **Run `/code-review ultra` from `~/Desktop/healbot`.** Phase 3's exit gate still requires it,
   it is the one artifact that ships, and this audit found two live defects in `env.sh` alone
   without ever reviewing the diff as a diff. User-triggered and billed; cannot be launched
   from here.
2. **Push the fork somewhere.** Branch `healbot` holds all 14 maps and the spike, its only
   remote is `sst/opencode`, and it therefore has no valid push destination. The work exists on
   one disk.
3. ~~**Confirm `flags.client` for the grid.**~~ **DONE**, TESTED — `OPENCODE_CLIENT` defaults to
   `"cli"` (`core/src/flag/flag.ts:75-76`), which `tool/registry.ts:202` admits, and a real
   `question` fired unforced on `gpt-5.6-sol` and was answered from the grid. YELLOW fires.
   `docs/VERIFY.md` §4.
4. **Confirm an *external* plugin can register a route.** F7 proved a builtin can. That decides
   whether the grid must live inside the fork or can ship separately. ~20 min.
5. ~~**Run `healbot.tsx`.**~~ **DONE**, TESTED on `openai/gpt-5.6-sol` — rendering, live session
   state, keyboard ownership, and clearing both a permission and a question block from the grid
   without focusing the session. 90/91 assertions across four runs; the exit gate's
   blocked-permission clause is met. `docs/VERIFY.md`.
6. ~~**Diagnose `prompt_async`**~~ **DONE** — it was never broken. REFUTED at TESTED tier; see
   the retraction above. The spawn-and-seed path can be built on it as `PLAN.md` specifies.
7. **Make the retirement threshold configurable** so the Phase 4 exit gate can be exercised at
   5K instead of 350K, and write down what "continuity intact" actually means.

### Process change, adopted

The plan's method had no repair step: every phase appended corrections to a new document and
left the old one wrong at the path everything linked to. That is the root cause of most of §5.
**Every phase now also revises the artifacts it contradicts** — this pass rewrote `PLAN.md`
(errata header), `HARNESS.md` (index, facts, traps, opens), `SCAN.md` (six inline corrections),
`STRIP.md` (measurements, retraction), `env.sh`, `opencode.jsonc`, and 8 map files in the fork,
rather than recording the corrections only here.

---

*Raw findings, per-agent evidence and the skeptic reviews are in the workflow journal:*
`~/.claude/projects/-Users-brittonwerdell-Desktop-healbot/9e0e754c-1daa-45ea-adec-073b3b86496b/subagents/workflows/wf_b44d22b6-e8d/journal.jsonl`
