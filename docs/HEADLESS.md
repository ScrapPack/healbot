# Phase 6 — headless, and the control agent

Date 2026-07-27. Three items, in the order they had to happen: make automatic retirement run
without a client, close the two open questions that had been deferred since Phase 4, and build the
last non-optional step of `PLAN.md`'s build order.

> **Phase 7 erratum — read before trusting this document's account of the gate.** A review of this
> phase found that the gate fired at a **step** boundary, not at the end of a turn, and that
> `RETIRE_HARD` had been inert since it was written. So every statement below about the turn in
> flight finishing was true of the *design* and false of the *code*.
>
> It is true again. Phase 7 replaced the predicate with opencode's own (`prompt.ts:1295`, which
> excludes `"tool-calls"`), so the turn does now run to completion and nothing is aborted on the
> gate path — and it **deleted** `RETIRE_HARD` rather than resurrect it, which forced the threshold
> down from 256,000 to **180,000**: with one gate, `RETIRE_AT` must absorb a worst-case turn
> (~170K measured) under the ~360K ceiling. Wherever this document says "soft gate" and "hard
> gate", there is now one gate. `docs/RELAY.md` has the arc and the arithmetic; corrections to
> specific claims are marked inline below. This document is otherwise left as the Phase 6 record.

---

## 1. The prescribed fix does not work, and why

The task as written was: *"the trigger is a `createEffect` INSIDE the route component, so it only
fires while the grid is open. A fleet left running with no client attached retires nothing. Move it
to plugin scope, driven off `message.updated`."*

The goal is right. The mechanism is not, and the reason is worth recording because it is the kind
of thing that reads as a detail and is actually the whole decision.

**A TUI plugin runs in the TUI process.** Moving the trigger from the route component to
`healbot.tsx`'s plugin scope fixes the *first* half of the problem — the trigger surviving
navigation into a session — and does nothing at all about the second. No TUI, no plugin, no
retirement. The failing case in the task description is untouched by the prescribed fix.

Two further facts make it worse than merely insufficient:

- **TUI plugin scope has no Solid owner.** `plugin/tui/runtime.ts`'s `load()` crosses at least one
  `await` before `activatePluginEntry` invokes `tui(api)` at `:529`, so the synchronous
  `createRoot` window has closed. TESTED: `getOwner()` is `null` there. `createSignal` and
  `createMemo` are fine (they never touch the owner), but a `createEffect` runs, stays reactive,
  and is **never disposed**, and a bare `onCleanup` is a **silent no-op**. Putting a trigger that
  spawns and archives sessions into an undisposable effect is the wrong direction.
- **The two plugin surfaces are mutually exclusive by type.** `TuiPluginModule` is
  `{ id?, tui, server?: never }`; `PluginModule` is `{ id?, server, tui?: never }`. `healbot.tsx`
  could not have hosted a server hook even if it wanted to.

So the guard moved to the **server** plugin surface, in `harness/config/opencode/plugin/healbot.ts`.

| | |
|---|---|
| The hook | `Hooks.event`, live trigger site at `plugin/index.ts:255` |
| Its scope | directory-filtered at `plugin/index.ts:251`; every event carries `location.directory` because `event-v2-bridge.ts:19-33` attaches it from `InstanceRef` |
| Registration | `opencode.jsonc`'s `plugin` array |
| Topologies covered | both — `opencode serve`, and the server the TUI hosts in-process |
| Driven off | `message.updated`, exactly as specified: `properties` is `{sessionID, info}` and `info` is the whole assistant message, tokens included |

Checking that `Hooks.event` is *live* was not ceremony. This project has already been bitten by a
declared-but-dead hook: `permission.ask` is on the same interface and has zero trigger sites.

### The grid gives the gate up entirely

`healbot.tsx`'s `createEffect`, its `handled` set, `AUTO_RETIRE` and `RETIRE_HARD` are **deleted**,
not kept as a fallback. **Exactly one process may own the gate.** The two run in different
processes and neither can see the other's in-flight state, so an operator pressing `x` at the
moment the gate fires would produce two successors for one session.

What the grid keeps: `x`, and painting `RETIRE` / `N to retire` / the share-of-threshold figure off
`RETIRE_AT`.

Consequence to know: **run the fork without the harness config and nothing retires automatically.**
The border still goes purple and `x` still works. That is acceptable because the harness *is* the
deliverable — the model pin and `compaction.auto:false` live there too — but it is a real
behavioural split between the two trees and it is not written down anywhere else.

### Raw `fetch`, not the injected SDK client

The plugin is handed `createOpencodeClient` from `@opencode-ai/sdk` — the **v1** generated client,
not the v2 one the TUI uses. They diverge on all three calls that matter, silently:

- The v1 client has **no `permission` and no `question` sub-client at all**.
  `client.permission.list()`, which `healbot.tsx` calls happily, does not exist there.
- v1 `SessionUpdateData["body"]` is `{ title?: string }` — no `time.archived`, so the one call
  retirement cannot do without would not type-check. **The server accepts it**:
  `groups/session.ts:53-57`'s `UpdatePayload` has `time: { archived }` and
  `handlers/session.ts:200-201` calls `setArchived`. The generated v1 types are narrower than the
  route.
- v1 `SessionCreateData["body"]` is `{ parentID?, title? }`; `directory` is a query param.

Writing the requests out is more honest than casting past the generated types on three calls, it
matches what `rig.py`'s `Api` already does, and it cannot rot when the SDK is regenerated.

### And no imports at all

`harness/config/opencode/node_modules` is **untracked** — `HARNESS.md` records why: opencode seeds
a self-ignoring `.gitignore` into any config dir at boot. A fresh clone gets the harness without
its dependency manifest, so a plugin importing `zod` or `@opencode-ai/plugin` would fail to load
there, silently, as a line in a server log. Tool argument schemas are therefore raw JSON Schema,
which `tool/registry.ts:129` accepts via `legacyJsonSchema`. That path marks every property
**required** (`registry.ts:365`), which is why no control tool has an optional argument.

### Results

| Rig | | |
|---|---|---|
| `probe_twin.py` | **20/20** | free — the two handoff implementations agree, with mutation checks |
| `probe_headless_arm.py` | **11/11** | free — the guard arms with nothing rendering; negative control on `HEALBOT_AUTO_RETIRE=0` |
| `verify_headless_retire.py` | **20/20** | the full lifecycle with **no TUI in the process table** |

The end-to-end run: occupancy crossed the gate at 36,647 (1.8x a 20,000 test gate), the turn
finished `tool-calls ×3 → stop` with no error, exactly **one user turn** ran, 2/2 open todos
reached the successor's own list, the created file was handed over, the successor started at 5,366
— near the ~4.8K floor — and nothing chained.

Two pieces of evidence carry the "headless" claim rather than the absence of a `boot()` call: the
process table is checked for any TUI (`ps -eo command`), and the retirement is confirmed against
**the server's own log line naming the successor**, which a TUI cannot produce.

### Two copies of the handoff document, and the test that guards them

`healbot.tsx` still needs `handoffDocument` for manual `x`. The harness config directory and the
fork checkout cannot import each other — one is not in the other's workspace, the other is derived
and gitignored — so there are two copies of prose that **is** behaviour: a successor briefed
differently depending on whether a human pressed a key or a threshold fired is exactly the class of
silent divergence this project keeps catching in itself.

`probe_twin.py` is the guard. It compares the thresholds and every string literal inside both
`handoffDocument`s, and follows each comparison with a **mutation check** — the same predicate
re-run against a deliberately corrupted copy, required to fail. It also asserts the grid no longer
contains an automatic trigger, and that the plugin exports only functions (`getLegacyPlugins`
throws `TypeError: Plugin export is not a function` on any export that is not one — a single
exported constant would disable the whole guard at load time, in a log line nobody reads).

> **Phase 7 erratum — "every string literal" is false, and the sentence was doing real work.**
> `document_strings()` (`probe_twin.py:83`) is `re.findall(r'"((?:[^"\\]|\\.)*)"', body)` —
> **double-quoted only**. The two lines that render every *variable* line of the handoff are
> template literals (`` `- [ ] ${todo.content}` `` and `` `- ${f}` ``) and are invisible to it, as
> is `MAX_DOCUMENT_TAIL`, which is declared 178 lines above `handoffDocument` and thus outside the
> brace-matched body the extractor reads. TESTED by mutating the grid and leaving the plugin
> alone: the probe **missed** eight real divergences (both bullet formats, the tail slice bound,
> two conditional thresholds, the objective fallback, and a dropped `.trim()`) and caught one —
> `lines.join("\n")`, the sole double-quoted operand. Both mutation checks at `:165-172` mutate a
> double-quoted *heading*, i.e. the one thing the extractor already sees, so they demonstrate the
> machinery without exercising the gap. The two copies **are** byte-identical today (VERIFIED), so
> this is a coverage hole, not a live divergence — but the claim above is exactly the kind of
> overstatement this project exists to catch, and it was mine.

This is why the control agent's tools live in the **same file** as the gate rather than their own:
`healbot_retire` calls the same `retire()`. Two copies are a compromise guarded by a test. Three
would not be.

---

## 2. The two open questions, closed

### Focus — `probe_focus.py`, 24/24, free

Build-order step 4, three lines of code, never run. The Phase 4 gate was explicitly about answering
a block **without** focusing, so nothing ever pressed the one key that leaves the grid.

The trap here is that `not on_grid()` is not evidence. The session route's fetch can fail
(`routes/session/index.tsx:284-292`), and when it does it toasts `Session not found: <id>` and
navigates **home** — so a bare "the grid header is gone" assertion scores that bounce as success.
Focus is therefore asserted positively on three independent signals, with the bounce asserted
against explicitly:

| Predicate | True on | False on |
|---|---|---|
| `Healbot\s+\d+\s+sessions?` | the grid | home, the session route |
| `Ask anything\.\.\.` | home only | the grid, the session route |
| `\d+% used` | the session route | the grid (cells render a bare `NN%`, never the word), home |

And the assertion that actually matters: **focus follows the cursor.** The sidebar renders the
session's own id verbatim, so the probe focuses cell 0 and asserts cell 0's id is present and cell
1's is not, then moves the cursor and repeats with the two swapped. The same predicate run twice
with opposite expectations cannot be a tautology.

Two findings:

- **Focusing does NOT clear ERROR cells.** Navigating away unmounts the route and fires every
  `onCleanup`, discarding the component-local `errors` map — which is a plausible reading of the
  code, and wrong. `storedErrorOf` re-derives the state from stored messages, so the cells come
  back, exactly as they survive a cold start. TESTED both before and after the round trip.
- **The sidebar is gated on `width > 120`** (`routes/session/index.tsx:264`), and it is the only
  thing that renders a session id. The navigation rigs use exactly 120 on purpose. Any focus
  assertion written at that width measures terminal geometry instead of behaviour — which is
  precisely what the first version of `verify_cold_question.py`'s trailing check did, and reported.

Also recorded, because it is a real usability fact and not a bug: **there is no key that returns
from a session to the grid.** `healbot.open` is namespace `palette` with slashName `healbot` and
has no binding anywhere (greps in the doc's commit message). The routes back are `ctrl+p` or typing
`/healbot`. `returnRoute` cannot help — `adapters.tsx:47-52` drops every param but `sessionID` on
the way in. The selection index does survive, because it lives in the plugin closure.

### `question.rejected` — `verify_cold_question.py`, 22/22

The permission half of the cold-start reconcile was TESTED in Phase 5. The question half was
source-reading only, and the two are not interchangeable: different service, different in-memory
store, different endpoints, and questions resolve through **two** events (`question.replied` and
`question.rejected`, published from different lines) where a permission has one.

Ordering is the whole test, as in `verify_cold.py`: headless server, a question raised **unforced**
with nothing rendering, and only then a client. The SSE stream does not replay — `handlers/event.ts`
emits a synthetic `server.connected` and then only live events — and `sync.tsx` initialises
`data.question` to `{}` and never seeds it over HTTP. So a yellow cell can only have come from
`reconcile()` reading `GET /question`.

| | |
|---|---|
| question raised before any client existed | **113 s** in, no TUI process anywhere |
| grid on first paint | `QUESTION`, `1 blocked` |
| panel mounted from the reconciled request | carried the real prompt **and** both options |
| `escape` → rejected | block cleared server-side, cell left `QUESTION`, header count gone |
| the model was told | "dismissed" present in the session's parts |

An asymmetry worth knowing: the plain session route renders `QuestionPrompt` from
`sync.data.question` alone, which is event-fed only. **The session route could not have surfaced
this block at all.** The grid's own reconcile is the only reason it was ever answerable.

#### Two rig defects this cost, both mine

- **The retry loop was non-deterministic.** Attempt 1 timed out at 300 s, attempt 2 was fired
  against a new session, and then attempt 1's model asked anyway. Two sessions were blocked at
  once, `questions()[0]` belonged to the abandoned one, and the rig rejected one question while
  asserting about the other — eight failures with nothing to do with the reconcile. It now aborts
  the previous attempt and matches the pending request by `sessionID`.
- **An expectation asserted before it was established.** "The dismissal is visible in the asker's
  transcript" failed. It is provably in the session's parts over HTTP — that assertion passes — but
  it is not on the visible viewport. That is a property of the session route, not of the reconcile,
  and I had never checked it. It is now printed as an observation rather than asserted, and named in
  *Still open*. Deleting it quietly would have been worse than leaving it red.

---

## 3. The control agent — build-order step 5

`PLAN.md:378`: *"Control agent. Its own session in the same server, with tools to spawn / prompt /
abort / retire the others (`POST /session`, `/prompt_async`, `/abort`). Same registry you see."*

Two pieces: five tools on the server plugin's `tool` hook, and
`harness/config/opencode/agent/control.md`.

**Why the plugin hook and not `<configdir>/tool/*.ts`.** Both mechanisms work and both are scanned
from the harness config directory. Only one gets an HTTP client: a tool module is imported with no
arguments (`tool/registry.ts:178-192`) and its `execute` context is `ToolContext` — sessionID,
messageID, agent, directory, worktree, abort, metadata, ask — with no client, no serverUrl, no app
instance. Tools defined inside the plugin function close over the server address, which is the
entire difference between a control agent and a set of stubs.

| Tool | Does |
|---|---|
| `healbot_list` | every live session, its state, occupancy as a share of the gate, and whether it is blocked. Archived filtered out, newest first — the same order the grid renders |
| `healbot_spawn` | `POST /session` + `prompt_async` seed. Returns the id |
| `healbot_prompt` | `prompt_async` to an existing session |
| `healbot_abort` | `POST /abort`. The session stays alive |
| `healbot_retire` | the shared `retire()` — abort, todos, diff fan-out, seed a successor, archive |

Guards the model cannot talk its way past: it cannot abort or retire its own session, cannot retire
a subagent (that orphans the parent's tool call), and cannot retire an already-archived session.

### The scoping, which is the part that matters for this project's purpose

Tool definitions are the largest single block of standing context — 11 shipped tools measure
19,898 B. Five more left global would be rent **every** session pays forever for a capability one
agent uses. So:

```jsonc
// opencode.jsonc
"permission": { "healbot_*": "deny" }
```
```yaml
# agent/control.md frontmatter
permission:
  healbot_*: allow
```

The mechanism is specific and easy to get wrong. `Permission.fromConfig` turns a string value into
`{permission, pattern: "*", action}` (`permission/index.ts:190`), and `Permission.disabled`
(`:204-215`) removes a tool from the request payload exactly when the **last** matching rule is
`pattern: "*"` with `action: "deny"`. The agent's own permission block is merged last
(`agent/agent.ts:293`), so `control.md`'s allow wins the `findLast`. **A scoped deny would leave
the definitions in every prompt and only block execution** — all of the cost, none of the benefit.

`mode: primary` is also load-bearing: an agent defined only in config defaults to `mode: "all"`
(`agent/agent.ts:273-280`), and a non-primary agent's description becomes per-request `task`-tool
rent for every other session (`tool/registry.ts:260-273`).

### Results

| Rig | | |
|---|---|---|
| `probe_control_wiring.py` | **14/14** | free — tools registered, agent registered as primary and matching `control.md`, permission wiring, plugin loaded clean |
| `verify_control_agent.py` | **15/16** as executed | the same instruction under two agents |

The runtime rig sends **one instruction that names no tool** to two agents and compares the tool
calls, keying on parts of `type: "tool"` and their `tool` field — never on message text, which is
what makes the negative half falsifiable.

| | control agent | build agent |
|---|---|---|
| tools called | `healbot_list`, `healbot_spawn` | `skill`, `bash`, `bash`, `task` |
| healbot tools | **present and used** | **none** |
| outcome | a real top-level session, seeded, ran unprompted, wrote `hello.txt` = `HELLO` | delegated to a `@general` subagent instead |

The spawn is confirmed independently by the server's own `[healbot] control: spawned <id>` log
line, so it is not the model narrating a plausible story.

**On the 15/16, honestly.** The failing assertion was mine and mis-specified: it counted *every*
new session, and the extra one was the build agent's `@general` subagent — denied the healbot
tools, it reached for `task` instead, which is the correct thing for it to do and creates a session
with a `parentID`. The check was measuring "did anything create a session" when the claim is "did
the denied tools create a top-level session". It is corrected to the stronger form — *every session
the build agent created is a `task` subagent* — and that corrected predicate was **evaluated
against the run's persisted database**: extras = one session, and it has a parent, so the corrected
predicate is True where the old one was False. The corrected file has **not been re-executed
end to end**; re-running costs roughly the same again, and the owner scoped this to the core proof.

---

## 4. What this changes elsewhere

Per the process rule from `docs/REVIEW.md` — every phase revises the artifacts it contradicts:

- **`harness/config/opencode/opencode.jsonc`** — still asserted "with a 922,000-token input limit
  and a 350K retirement threshold there is ~570K of headroom". Phase 5 measured the ceiling at
  ~360K and lowered the default to 256,000; the comment had not been updated and would have been
  the next reader's figure. Corrected, with the measurement named.
- **`HARNESS.md`** — the auto-retirement row leaves *Still open*, focus and `question.rejected`
  leave it, four traps are added (TUI plugin scope has no owner; the v1/v2 SDK divergence; the
  sidebar's 120-column gate; the fork-without-harness split), and the load-bearing facts section
  records that the gate now lives in the server.
- **`fork/README.md`** — overlay re-pinned to `88f7ce8cf`, patch regenerated and re-verified
  against the base in a throwaway worktree, and the `healbot.tsx` row records that it no longer
  owns the automatic gate.
- **`.carryover/verified/README.md`** — five new rigs, and `rig.serve` gained `log=` and
  `env_extra=`. The second is load-bearing and easy to get wrong: since Phase 6 the **server**
  enforces the thresholds, so a rig that exports `HEALBOT_RETIRE_AT` into its own environment
  before `attach()` is configuring the wrong process.
- **`NEXT.md`** — rewritten for Phase 7.

---

## 5. Still open after Phase 6

Carried forward, unchanged:

- **External plugin route registration** is untested; the grid is a builtin.
- **Phase 3's exit gate** — `/code-review ultra` on the `harness/` diff. User-triggered and billed;
  an agent session cannot launch it. Still the owner's action.
- **The 256K gate has never been exercised at its real value.** The comparison is a single `>=`
  and the path is TESTED at 20,000, so the risk is low, but the full-scale run has not been paid
  for. **Phase 7: `verify_headless_retire.py` cannot be the vehicle.** It hardcodes
  `THRESHOLD = 20_000` at `:52` and forces it into the server's environment at `:96-103`, which
  `rig.py:159` applies last — there is no override to remove. Nor does editing the constant
  help: one prompt, one `read` capped at 50 KB by `read.ts:16`, measured peak 36,647, and
  `len(user_turns) == 1` asserted structurally at `:200-204`. See `NEXT.md` for what does work and
  what it costs.

Added by this phase:

- **Cold start on the gate.** The trigger is purely event-driven, so a server that restarts with a
  session already over the threshold does nothing until that session's next turn. In practice the
  next turn's first `message.updated` carries the occupancy and ~~the hard gate catches it
  mid-turn~~ — **Phase 7: the gate catches it at the END of that turn. The hard gate never could
  have: it was inert, and it has since been deleted** — but a startup sweep would close it properly.
  Deliberately not built: a server restart causing mass retirement is a policy decision, not a bug
  fix.
- **The manual/automatic double-retire window is ~~narrowed, not closed~~ neither narrowed nor
  closed.** `retire()` re-reads the session's archived state immediately before the irreversible
  step, which reduces the window to the width of one request. Two processes, no shared lock. An
  operator pressing `x` at the exact moment the gate fires can still produce two successors.

  > **Phase 7 erratum, and this one was self-flattering.** The re-read narrows *nothing* about two
  > successors: it runs **after** `POST /session` and `prompt_async`, so whichever actor loses has
  > already created and seeded one — the code's own return string says so ("successor `${id}` is
  > seeded and live"). All the re-read prevents is a redundant idempotent PATCH and a log line
  > claiming a retirement someone else performed. The window that actually produces two successors
  > runs from `consider()`'s archived check to `POST /session`, spanning `isBlocked`'s two GETs,
  > the abort, the todo GET, an unlimited full-history GET on a session at the gate, and up to
  > `DIFF_FANOUT` parallel `/diff` GETs. That is seconds, not one request. The grid's copy has no
  > re-read at all, so "narrowed" never described the manual half under any reading.
  >
  > It is also **not only cross-process**, which this entry asserted throughout. `consider()` tests
  > `busy` and `handled` at the top and sets them *after three awaits*, so the control agent's
  > `healbot_retire` can interleave with the automatic gate **inside one process** — contradicting
  > the "serialised deliberately" comment on `busy` itself. Closing the race needs a claim written
  > **before** the spawn, not a check after it.
- **`verify_control_agent.py` has not been re-executed since its one assertion was corrected** —
  see §3.
- **The session route does not surface a dismissed question on screen.** The text is in the
  session's parts over HTTP; it is not on the visible viewport. Scroll position, rendering of an
  errored tool part, or both — unexamined.
- **Two copies of `handoffDocument` exist by necessity**, guarded by `probe_twin.py` rather than by
  a type.
