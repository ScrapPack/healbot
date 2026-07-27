# Phase 7 — one writer, and the sentence that was never true

Date 2026-07-27. This phase began as a review of Phase 6 and turned into a correction. The headline
is not a feature: it is that the retirement gate had never behaved the way five artifacts in this
repo said it did, and nobody had checked because everything passed.

Two things came out of it. The prose was brought to the code, on the owner's decision to keep the
shipped behaviour. And the double-retire race was closed by deleting the second implementation
rather than by narrowing the window between two.

---

## 1. `finished()` was reading a per-STEP field

The plugin's completion predicate was:

```ts
function finished(info: MessageInfo): boolean {
  return Boolean(info.time?.completed || info.finish || info.error)
}
```

under a docblock headed *"Has the turn ended?"*. It does not answer that question, and the gap is
the whole phase.

**VERIFIED at source.** `processor.ts:443` sets `ctx.assistantMessage.finish = value.reason` and
`:445` sets `.tokens = usage.tokens` — two lines apart, in the same mutation, inside the block that
emits a `type: "step-finish"` part at `:452`. `:595-596` sets `time.completed` in `cleanup()`,
which `Effect.ensuring` at `:676` runs per `process()` call. And `processor.ts:445` is the **only**
site in the session tree that ever writes a non-zero `tokens` — grepped exhaustively; the four
other assignments (`prompt.ts:278`, `:499`, `:1195`, `compaction.ts:370`) all initialise to zero.

opencode's own predicate for "the turn ended" is `prompt.ts:1295`, and it is strictly narrower:

```ts
const finished = handle.message.finish && !["tool-calls", "unknown"].includes(handle.message.finish)
```

The plugin's omitted exactly that exclusion. Two consequences follow, and the second is the one
that makes the first tolerable.

**(a) The gate fires mid-turn and aborts the turn in flight.** `consider()`'s
`if (!turnOver && !hard) return` sees `turnOver === true` at every step boundary, so the gate fires
at the first step above the threshold and `retire()`'s unconditional `POST /abort` cancels the
live turn. MEASURED on a real session: one user message produced 30 assistant messages, 29 of them
carrying `finish: "tool-calls"` **and** `time.completed`, occupancy climbing 9,106 → 135,573.

**(b) `RETIRE_HARD` is inert, and provably so.** Because occupancy and `finish` are written in the
same mutation, any event carrying non-zero tokens also carries a set `finish`. So `turnOver` is
true on every event that can reach `consider()`, the guard never returns, and `hard` never decides
anything. MEASURED across 733 real assistant messages with occupancy > 0: **zero** had a null
`finish` — 677 `tool-calls`, 56 `stop`. `HEALBOT_RETIRE_HARD` is a knob with no effect, and no rig
had ever executed the branch: `probe_headless_arm.py` only asserted the constant appeared in the
arming log line, and `probe_twin.py` only that the string appeared in a source file.

### The behaviour is better than the design

This is the uncomfortable part. The documented design — let the turn finish, catch the overshoot
with a second gate — was written to solve a real measured problem: `docs/HARDEN.md` §6 records one
turn going 5,216 → 70,898 on a single tool result and finishing at 175,090, which is ~170K of
growth in one turn, enough to carry a session from just under 256,000 to past the ~360K ceiling.

The shipped behaviour bounds that exposure to **one step** (~65K from the same table) rather than
one turn (~170K). A session crossing at 256,000 is retired by ~321,000 worst case, comfortably
inside the ceiling. The margin `HARNESS.md` credited to `RETIRE_HARD` is real; it just comes from
somewhere else.

So the design goal was met by an implementation that did not implement the design, and the second
gate that was supposed to deliver the safety has never once fired. That is not a happy accident to
be quietly banked. It is exactly the shape of thing this project exists to catch, and it survived
Phase 5 and Phase 6 because every test passed.

### Why the existing test could not have caught it

`verify_headless_retire.py:180-183` asserts `finishes[-1] == "stop"`, which is falsifiable in
principle. But its prompt (`:127-134`) puts the only large token jump on the input of the final
model call, so the crossing lands at the last step **by construction**. The assertion has never
discriminated "waits for the turn" from "fires at any step boundary". The rig's own comment at
`:185-186` — "assistant messages are STEPS within a turn" — shows the distinction was understood
in the test and not in the code.

### What was decided, and what changed

The owner chose to keep the shipped per-step behaviour. So the code changed only in name and the
prose changed everywhere:

- `finished()` → **`stepFinished()`**, with a docblock that states what it tests and names
  `prompt.ts:1295` as the single-function hinge back to per-turn semantics.
- `consider()`'s parameter `turnOver` → `stepOver`; its dead guard is labelled dead and kept,
  because it is the exact line that starts working if the hinge is ever flipped.
- `RETIRE_HARD` is marked **INERT** and kept, with its reason for being kept: it becomes
  load-bearing again the day `stepFinished()` is made per-turn, and re-deriving it from scratch
  would be worse than carrying a documented dead constant.
- Corrected in place: `HARNESS.md` (a new load-bearing-facts block and three rows),
  `docs/HEADLESS.md` (erratum banner and inline notes; left otherwise as the Phase 6 record),
  `docs/HARDEN.md` (inline notes; its measured table is correct and was always per-step data,
  reasoned about as per-turn), `opencode.jsonc`, `harness/env.sh`, `PLAN.md`'s errata table, and
  `agent/control.md` — that last one matters operationally, because the control agent was being
  told the gate was gentler than it is and it decides when to retire things.

---

## 2. The double-retire race, closed by subtraction

Phase 6 recorded the race as *"narrowed to one request"* by a re-read of the archived state
immediately before archiving. **That was wrong, and self-flattering.** The re-read runs at
`healbot.ts` *after* `POST /session` and after `prompt_async` — so whichever actor loses has
already created and seeded a successor. The code's own return string says so: *"successor `${id}`
is seeded and live"*. All the re-read prevents is a redundant idempotent PATCH and a log line
claiming a retirement someone else performed.

The window that actually produces two successors runs from `consider()`'s archived check to
`POST /session`, spanning `isBlocked`'s two GETs, the abort, the todo GET, an unlimited
full-history GET on a session at the gate, and up to `DIFF_FANOUT` parallel `/diff` GETs. Seconds,
not one request.

And it was never only cross-process. `consider()` tested `busy` and `handled` at the top and set
them **four awaits later**, so the control agent's `healbot_retire` could interleave with the
automatic gate *inside one process* — contradicting the "Serialised deliberately" comment on `busy`
itself.

### The fix is that there is now one writer

`x` no longer retires. It writes a request; the server plugin performs it.

| | |
|---|---|
| The write | `session.update({sessionID, metadata: {healbot: {retireRequested: Date.now()}}})` |
| Accepted at | `httpapi/groups/session.ts:51` declares `metadata` on the update payload; `handlers/session.ts:191-192` calls `setMetadata` |
| Which reaches | `Session.setMetadata` (`session.ts:763`) → the shared `patch()` |
| Which publishes | `SessionV1.Event.Updated`, with the **whole session object**, at `session.ts:748` |
| Which arrives at | the plugin's `event` hook — it already receives every event for its directory |

**No endpoint was registered, because none can be.** The server plugin surface
(`packages/plugin/src/index.ts`) is hooks only, and `event` is receive-only; a server plugin cannot
register a route for the TUI to call. It does not need one. A metadata write is a durable, ordered
request that survives the writing process dying.

Self-triggering is not a hazard: archiving is itself a `patch()` and republishes `session.updated`
with the key still set, but by then `time.archived` is populated and `considerRequest` bails.
`probe_request_channel.py` asserts the count is exactly one.

The marker is deliberately **not** cleared. It is a record of who asked.

### What that deleted

- ~180 lines from `healbot.tsx` — a second complete implementation of abort → todos → diff fan-out
  → document → spawn → seed → archive.
- The **`handoffDocument` twin**. Phase 6 called two copies "a compromise guarded by a test". The
  guard did not work (§3). A successor is now briefed identically whether a human pressed a key or
  the gate fired, because only one thing can brief it.
- `GridClient`, from ten members to three: two cold-start reconcile reads and one write.
- `DIFF_FANOUT` from the grid.

The generated `session.update` type does not include `metadata` — the same "generated types are
narrower than the routes" divergence `docs/HEADLESS.md` records for the v1 client's `time.archived`,
one tree over. The grid's local structural type was widened, which is what that declaration exists
for.

**Consequence to know, and it is bigger than Phase 6's:** run the fork without the harness config
and **neither** automatic nor manual retirement works. The border still goes purple, `x` still
writes its request, and nothing is listening. Previously `x` worked regardless.

### Two more defects fixed while in there

- **`busy` is now claimed synchronously**, before the first await, instead of four awaits later.
  JavaScript's single thread is what makes that sufficient: nothing interleaves between the
  synchronous check and the set. `healbot_retire` already had its check and set adjacent, so both
  entry points now hold the same discipline. `handled.add` stays after the blocked check, so
  answering a block does not cost a session its retirement.
- **A failed todo read no longer reads as "no open todos".** `retire()` used
  `.catch(() => [])`, and 60 lines below, an empty list means *archive with no successor* — so one
  transient loopback failure would silently retire a session with outstanding work and log that
  there was none. It now throws; `consider()` logs `retire FAILED`, the predecessor stays
  unarchived and retryable. The grid's twin had always thrown here, via its `ok()` wrapper, so this
  was also a real divergence between the manual and automatic paths that `probe_twin.py` did not
  cover.

---

## 3. The guard that could not fail, and its replacement

`probe_twin.py` existed to stop the two `handoffDocument`s diverging. Its extractor was:

```py
re.findall(r'"((?:[^"\\]|\\.)*)"', body)
```

**Double-quoted literals only.** Every line of the document that renders a variable is a template
literal — `` `- [ ] ${todo.content}` ``, `` `- ${f}` `` — and was invisible to it. So was
`MAX_DOCUMENT_TAIL`, declared 178 lines above the function and therefore outside the brace-matched
body.

TESTED, by mutating the grid against an untouched plugin. **MISSED:** `- [ ] ` → `- [x] `,
`- [ ] ` → `* `, a changed file-bullet prefix, `slice(0, 2000)` → `slice(0, 200)`,
`files.length > 0` → `> 3`, a dropped `input.objective?.trim() ||`, `open.length > 0` → `>= 0`, a
dropped `.trim()`. **CAUGHT:** `lines.join("\n")`, the sole double-quoted operand. Eight real
divergences would have shipped silently.

Both of its mutation checks mutated a double-quoted *heading* — the one class of thing the
extractor already saw. They demonstrated the machinery without exercising the gap. `docs/HEADLESS.md`
described the probe as comparing "every string literal", and a template literal is a string literal.

The duplication is gone rather than better-guarded, so the probe changed job. It now asserts the
grid has **no** `handoffDocument` and no spawn/seed/archive of its own, and it guards the coupling
that replaced the twin: the metadata key, which has no shared type, no import and no compiler
between writer and reader. **23/23.**

New discipline, recorded in `.carryover/verified/README.md` because it generalises:

- **An absence assertion needs an inverted mutation check.** "The grid has no `handoffDocument`"
  passes trivially if the extractor is reading the wrong text. The probe re-runs the same predicate
  against a copy that *does* contain the symbol and requires it to trip.
- **An untyped cross-process coupling is asserted from both ends** — the probe mutates the writer
  and the reader in turn.
- **The predicate a mutation check corrupts must be the predicate that runs.** The channel check is
  factored into a function whose inputs are mutated, not re-implemented inline.

### `probe_request_channel.py` — new, free, and it fails when it should

Structure is not behaviour. A new probe drives the channel end to end with **no model turn**:
headless server, automatic gate **disabled**, two sessions created, the marker written to one.

It is free because a session with no turns has no todos, so `retire()` takes its
archive-with-no-successor branch — the whole channel runs without a provider call.

Four independent signals, because "the session ended up archived" would also be true if the script
had archived it: the plugin's own log line (which only it writes, and the script never PATCHes
`time.archived`), the archive itself, a **negative control** (a second, unmarked session must still
be live), and a no-loop count. **9/9.**

And it was TESTED to fail: renaming `REQUEST_KEY` in the plugin drops it to **5/9**, with exactly
the four channel assertions failing and the negative control correctly unaffected.

---

## 4. What Phase 7 did NOT buy

`NEXT.md` step 1 asked for the shipped 256,000 gate to be exercised end to end by running
`verify_headless_retire.py` "with no `HEALBOT_RETIRE_AT` override". **That was not executable.**
The rig hardcodes `THRESHOLD = 20_000` at `:52` and forces it into the server's environment at
`:86-93`, and `rig.py:159` applies `env_extra` last — there is no override to remove. Editing
the constant does not help either: one prompt, one `read` capped at 50 KB by `read.ts:16`, measured
peak 36,647, and `len(user_turns) == 1` asserted structurally at `:200-204`. At 256,000 it would
have timed out and hard-failed after 15 minutes. The rig's own docstring says it runs at a low
threshold *on purpose*.

The question splits, and only one half costs money:

- **Does the shipped constant arm at 256,000?** A fact about config resolution. Now **TESTED and
  free** — `probe_headless_arm.py` starts a third server with no override and asserts
  `soft 256,000`, paired against the pre-existing assertion that the same string is *absent* when
  an override is supplied. The same string, asserted both ways in one run. **15/15.**
- **Does a session driven to 256,000 retire?** A fact about a single `>=`, already TESTED at 20,000
  and threshold-independent by inspection. Still unbought. Costing, if wanted: **~$4.50, range
  $3–9, ~8–15 min**, via `verify_retire_350k.py`'s growth-loop workload retargeted — ~27 turns at
  the recorded 9.46K/turn, cumulative context scaling N(N+1)/2 so (27·28)/(37·38) = 0.538 of the
  350K run's ~5M tokens ≈ 2.7M. The load-bearing detail: 256,000 stays **under** the provider's
  272,000 tier that doubles every rate, so base rates hold throughout.

The recommendation on record: the money is better spent on the per-step question than on
re-confirming a `>=`.

---

## 5. Still open after Phase 7

- **`RETIRE_HARD` is inert.** Kept and documented rather than deleted. The decision — delete it, or
  make `stepFinished()` per-turn and resurrect it — is deferred to the owner, because it is a
  behaviour choice and not a cleanup.
- **The 256,000 firing run** is unbought; see §4. The arming half is closed.
- **Startup sweep** for sessions already over the gate when a server restarts. Premise TRUE
  (`consider()` has one call site, no polling, `handled` is per-process and empty on restart) and
  it is ~15 lines reusing `healbot_list`'s query and `describe()`'s scan. Still deliberately not
  built: a restart causing mass retirement is a policy decision. **Rationale correction:**
  `docs/HEADLESS.md` and `HARNESS.md` credited `RETIRE_HARD` with catching the restart case
  mid-turn. It cannot. The *soft* gate catches it, at the next step boundary.
- **`verify_control_agent.py` has not been re-executed.** Its Phase 6 correction was still weak —
  `all(s.get("parentID") for s in extras)` is True on an empty list, and `extras` is empty whenever
  the build agent answers directly instead of delegating, so a re-run could have reported 16/16
  having validated nothing. Restated as "it created NO top-level session", with non-exercise now
  printed out loud instead of passing silently. Fixed but unrun.
- **External plugin route registration** untested; the grid is a builtin.
- **The session route does not render a dismissed question on screen.**
- **Phase 3's exit gate** — `/code-review ultra` on the `harness/` diff. User-triggered and billed;
  an agent session cannot launch it.

---

## 6. The method note

Phase 6 caught three of its own bad assertions and said so. Phase 7 found five more things wrong
with Phase 6, and the pattern in them is worth stating: **every one was a claim that sounded
verified and had only been reasoned.** The per-turn gate, the one-request window, the "every string
literal" guard, the "needs a real turn" scoping cost, the `all()` over a list that is usually
empty. None was a coding error. Each was a sentence written with more confidence than its evidence
carried, in a repo whose stated rule is to tier every claim.

Two of the corrections came from agents reviewing the lead's own work in this phase, including an
off-by-one in a `prompt.ts` citation that had been asserted as VERIFIED. The citation was checked
by opening the file; the line was blank.

The suite's characteristic failure is still passing.
