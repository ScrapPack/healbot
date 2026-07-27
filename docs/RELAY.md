# Phase 7 — one writer, and the sentence that was never true

Date 2026-07-27. This phase began as a review of Phase 6 and turned into a correction. The headline
is not a feature: it is that the retirement gate had never behaved the way five artifacts in this
repo said it did, and nobody had checked because everything passed.

Two things came out of it. The gate is now per-turn, as every artifact had always claimed — but
only after a first decision to keep the shipped per-step behaviour was taken, written up, committed,
and then reversed; and the reversal forced the threshold down from 256,000 to 180,000 and deleted
the second gate outright. And the double-retire race was closed by deleting the second
implementation rather than by narrowing the window between two.

---

## 1. `finished()` was reading a per-STEP field — and fixing it moved the threshold

The plugin's completion predicate was:

```ts
function finished(info: MessageInfo): boolean {
  return Boolean(info.time?.completed || info.finish || info.error)
}
```

under a docblock headed *"Has the turn ended?"*. It did not answer that question, and the gap is
the whole phase. What follows is the discovery, in the state it was found; the resolution is at the
end of this section and is not the one this section was originally written to reach.

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

The plugin's predicate omitted exactly that exclusion. Two consequences followed, and the second is
the one that made the first tolerable.

**(a) The gate fired mid-turn and aborted the turn in flight.** `consider()`'s
`if (!turnOver && !hard) return` saw `turnOver === true` at every step boundary, so the gate fired
at the first step above the threshold and `retire()`'s unconditional `POST /abort` cancelled the
live turn. MEASURED on a real session: one user message produced 30 assistant messages, 29 of them
carrying `finish: "tool-calls"` **and** `time.completed`, occupancy climbing 9,106 → 135,573.

**(b) `RETIRE_HARD` was inert, and provably so.** Because occupancy and `finish` are written in the
same mutation, any event carrying non-zero tokens also carries a set `finish`. So `turnOver` was
true on every event that could reach `consider()`, the guard never returned, and `hard` never
decided anything. MEASURED across 733 real assistant messages with occupancy > 0: **zero** had a
null `finish` — 677 `tool-calls`, 56 `stop`. `HEALBOT_RETIRE_HARD` was a knob with no effect, and no
rig had ever executed the branch: `probe_headless_arm.py` only asserted the constant appeared in the
arming log line, and `probe_twin.py` only that the string appeared in a source file. It has since
been deleted rather than repaired — see below.

### The behaviour was better than the design — the argument for the FIRST decision

**This section is a record of an argument that was made and then set aside. It is not the
resolution.** The owner's first decision, on this reasoning, was to keep the shipped per-step
behaviour and fix the prose; that was done and committed as `5bcdeab`. The second decision reversed
it. The reasoning is kept because it was sound at the time and because the reversal is only legible
against it.

The uncomfortable part was this. The documented design — let the turn finish, catch the overshoot
with a second gate — was written to solve a real measured problem: `docs/HARDEN.md` §6 records one
turn going 5,216 → 70,898 on a single tool result and finishing at 175,090, which is ~170K of
growth in one turn, enough to carry a session from just under 256,000 to past the ~360K ceiling.

The shipped behaviour bounded that exposure to **one step** (~65K from the same table) rather than
one turn (~170K). A session crossing at 256,000 was retired by ~321,000 worst case, comfortably
inside the ceiling. The margin `HARNESS.md` credited to `RETIRE_HARD` was real; it just came from
somewhere else.

So the design goal was met by an implementation that did not implement the design, and the second
gate that was supposed to deliver the safety had never once fired. That is not a happy accident to
be quietly banked. It is exactly the shape of thing this project exists to catch, and it survived
Phase 5 and Phase 6 because every test passed.

### The reversal, and the number it dragged with it

The owner then reversed the decision: **make the predicate per-turn and delete `RETIRE_HARD`.** The
grounds are the ones the section above concedes — per-step semantics were undocumented, unintended,
and correct only by accident, and an accidental correctness that five artifacts describe wrongly is
a defect whether or not it currently hurts.

The interesting part is what that combination does on its own. Per-turn means accepting whatever
the turn adds, and MEASURED that is up to ~170K (the same `docs/HARDEN.md` §6 row: 5,216 → 70,898
on one tool result, the turn finishing at 175,090). Deleting the second gate removes the thing that
was supposed to catch exactly that overshoot. Left at 256,000 the arithmetic is the one `HARDEN.md`
already spells out:

```
  256,000  gate
+ ~170,000 worst measured single-turn growth
= ~426,000  — past the ~360K ceiling. Dead session.
```

The ceiling is MEASURED, not advertised: a session driven up took its last successful turn at
occupancy **359,829** (`docs/HARDEN.md:227`) and then failed 25 consecutive turns with the
provider's `ContextOverflowError`. `compaction.auto: false` means nothing upstream intervenes.

So the threshold came down with the predicate. With one gate the requirement is
`RETIRE_AT + worst_turn < ceiling`, which puts the ceiling on the gate itself at roughly **190,000**
— anything at or above that can be carried off the cliff by one ordinary read-heavy turn.
**180,000 + ~170K = ~350K, just inside.** That derivation is now carried in the code
(`healbot.ts:106-117`, `healbot.tsx:25-31`, which points back here), in `harness/env.sh:98`, and
here, and it must travel
with the number wherever the number is explained; 180,000 read as a preference rather than as a
consequence is an invitation to raise it.

State it plainly, because it is the whole lesson of the reversal: **per-turn semantics, no hard
gate, and a 256,000 threshold is the one combination of the three that must not ship.** Each change
is defensible alone. Together they reintroduce, in full, the failure the hard gate was built for.
Nothing in the review that found the defect, and nothing in the first decision, mentioned the
threshold at all — the second-order consequence was not on anybody's list, and it was caught by
working the arithmetic after the decision rather than by anything in the suite. It was caught
**before it shipped**, which is the only good thing to say about it.

### Why the existing test could not have caught it — and what it took to fix that

`verify_headless_retire.py` asserted `finishes[-1] == "stop"`, which is falsifiable in principle.
But its prompt put the only large token jump — the 130 KB `ledger0.txt` read — on the input of the
**final** model call, so the crossing landed at the last step *by construction*. The assertion
could never discriminate "waits for the turn" from "fires at any step boundary". The rig's own
comment that "assistant messages are STEPS within a turn" shows the distinction was understood in
the test and not in the code.

This was proved rather than argued. The rig was re-run against the new per-turn predicate and
passed **20/20** — and the run's own database showed why that meant nothing: steps at 4,999 /
5,165 / 5,236, then `stop` at 36,612, against a 20,000 gate. **The only step over the line was the
last one.** Both predicates behave identically on that workload, so a green run was compatible with
either.

The fix was to reorder the workload, not to add an assertion to it: the ledger is now read
**first**, so its result sits in the input of every later step and the crossing lands mid-turn. Two
assertions were added on top — that a NON-FINAL step was over the gate, and that the turn ran on
past it. **TESTED, 22/22**: crossing at step 1 (36,361 against a 20,000 gate), steps 2 and 3 at
89,850 and 90,011, and the turn still running to `stop` at step 5 before the handoff. Under the
predicate that shipped before this phase, that turn would have been aborted at step 1.

The generalisable form, which is now in `.carryover/verified/README.md`'s assertion discipline:
**an assertion about ORDERING needs a workload that could have violated it.** "The turn finished
first", measured over a fixture whose only crossing is on the last step, is not a test — it is a
restatement of the fixture.

### What was decided, and what changed

The shipped state, VERIFIED by opening each file:

- `finished()` → **`turnFinished()`** (`healbot.ts:346`). It is opencode's own predicate:
  `if (info.error) return true; return Boolean(info.finish && !["tool-calls","unknown"].includes(info.finish))`.
  The reference implementation is `prompt.ts:1295`, named in the docblock.
- **`time.completed` is deliberately not read**, and the docblock at `healbot.ts:337` says so in
  those words. It is the field that looks most authoritative and is the least — `cleanup()` sets it
  per step (`processor.ts:595-596`) — and reading it is what created the original defect.
- `consider()`'s parameter is **`turnOver`** again and its guard is a plain `if (!turnOver) return`
  (`healbot.ts:612`, `:622`). No `&& !hard`. The guard is live, not dead: it is the line that makes
  the gate wait.
- **`RETIRE_HARD` is deleted, not disabled.** The constant, the `hard` variable, the guard, the env
  var and its half of the arming log line are gone from `healbot.ts` and `healbot.tsx`;
  `HEALBOT_RETIRE_HARD` now reads nothing anywhere, which `harness/env.sh:112` states out loud for
  anyone carrying it in an old shell profile. The intermediate position — keep it, marked INERT,
  because it becomes load-bearing again if the predicate is ever flipped — was the first decision's,
  and the predicate was flipped in the other direction instead.
- **`RETIRE_AT` defaults to 180,000**, down from 256,000, in *both* `healbot.ts:135` and the grid's
  copy at `healbot.tsx:57`. The derivation above travels with it in both.
- The arming line is now
  `headless retirement armed — gate 180,000 (per-turn, single gate), directory ...`
  (`healbot.ts:903`). It used to read `soft N, hard N`; there is one gate, and the line says so.
- `retire()`'s `POST /abort` (`healbot.ts:473`) is a **no-op on the gate path** again, as it was
  designed to be. It survives for the two paths where it is not: the race, where a turn starts
  between `consider()`'s check and the call, and `healbot_retire`, which the control agent may fire
  at a session that is working right now. For the length of one commit — `5bcdeab` — that abort was
  usually live and was cancelling turns in flight; the comment at `:471-472` says as much, so the
  next reader does not have to reconstruct it against this document.
- Prose corrected in place, **twice**: `HARNESS.md`, `docs/HEADLESS.md`, `docs/HARDEN.md`,
  `opencode.jsonc`, `harness/env.sh`, `PLAN.md`'s errata table and `agent/control.md` were first
  rewritten to describe per-step behaviour, then rewritten again when that behaviour was reversed.
  `agent/control.md` matters operationally either way, because the control agent decides when to
  retire things and was being told the wrong thing about the gate in both directions.

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

### `probe_turn_predicate.py` — new, free, and it is the guard that was missing

This is the probe that would have caught the §1 defect, and its absence is why the defect survived
two phases. It asserts what `turnFinished()` *does*, against the measured distribution of message
shapes, without a server and without a model turn.

It tests **the real source text**, not a copy. The predicate is extracted from
`harness/config/opencode/plugin/healbot.ts` by brace-matching `function turnFinished(`, stripped of
its TypeScript annotations with two regexes, and evaluated in `node` — so a re-implementation of the
predicate inside the probe, which would prove nothing about what ships, is never written. It cannot
simply import the function instead: `getLegacyPlugins` (`plugin/index.ts:95-108`) walks
`Object.values(mod)` and pushes **every** export through `getServerPlugin` (`:88-93`) — a bare
function is accepted as a plugin and later invoked as one — so exporting a helper to make it
testable turns the predicate into a second plugin. Extraction is the price of that, and the probe's
first assertion is that the extraction found something, so a rename fails loudly instead of
silently skipping the table.

Eleven cases, drawn from the real distribution rather than invented: the 677 mid-turn
`finish: "tool-calls"` messages must be **false** (both with and without `time.completed` set —
it is set on both), `"unknown"` likewise, the 56 `"stop"` messages and `"length"`/`"abort"` must be
**true**, both error paths true, and the empty in-flight row false. Three structural assertions
sit alongside them: that the extracted text does not contain `time`, that it excludes both values
`prompt.ts:1295` excludes, and that `RETIRE_HARD` is absent from the plugin's *code* — with comments
stripped, since the constant is still discussed in prose deliberately, and with an inverted
mutation check proving the stripping did not eat everything.

The mutation check is the one assertion that proves the table discriminates at all: it re-runs the
same eleven cases against the **old** per-step predicate,
`Boolean(info.time?.completed || info.finish || info.error)`, and requires it to fail. It gets four
wrong, including the mid-turn tool call that 677 of 733 real messages look like. **18/18.**

---

## 4. What Phase 7 did NOT buy

`NEXT.md` step 1 asked for the shipped gate — 256,000 when it was written, 180,000 now — to be
exercised end to end by running `verify_headless_retire.py` "with no `HEALBOT_RETIRE_AT` override".
**That was not executable.** The rig hardcodes `THRESHOLD = 20_000` at `:52` and forces it into the
server's environment at `:86-93`, and `rig.py:159` applies `env_extra` last — there is no override
to remove. Editing the constant does not help either: one prompt, one `read` capped at 50 KB by
`read.ts:16`, measured peak 36,647, and `len(user_turns) == 1` asserted structurally at `:200-204`.
At either threshold it would have timed out and hard-failed after 15 minutes. The rig's own
docstring says it runs at a low threshold *on purpose*.

The question splits, and only one half costs money:

- **Does the shipped constant arm at 180,000?** A fact about config resolution. Now **TESTED and
  free** — `probe_headless_arm.py` starts a third server with no override and asserts
  `gate 180,000`, paired against the pre-existing assertion that the same string is *absent* when an
  override is supplied. The same string, asserted both ways in one run. It also asserts the arming
  line names **one** gate — `per-turn, single gate` present, no `hard` before `directory` — which
  is the log-line half of `RETIRE_HARD`'s deletion. **14/14**, down from 15 because the hard-gate
  assertion was removed rather than because anything regressed.
- **Does a session driven to 180,000 retire?** A fact about a single `>=`, already TESTED at 20,000
  and threshold-independent by inspection. Still unbought, and now cheaper than when this section
  was first written. Costing, **INFERRED** from the 350K run's recorded rates and not measured:
  ~19 turns at 9.46K/turn, cumulative context scaling N(N+1)/2, so (19·20)/(37·38) = 0.270 of that
  run's ~5M tokens ≈ **1.35M**, call it **~$2.25, range $1.50–4.50, ~5–10 min**. The 256,000
  version of this estimate was ~27 turns, 0.538, ≈2.7M, ~$4.50. The load-bearing detail survives
  and is now slack rather than tight: 180,000 stays well **under** the provider's 272,000 tier that
  doubles every rate, so base rates hold throughout.

The recommendation previously on record was that the money was better spent on the per-step question
than on re-confirming a `>=`. **That question is now settled, and it cost nothing** —
`probe_turn_predicate.py` (§3) evaluates the shipped predicate directly against the measured
distribution, which is a stronger answer than one end-to-end run would have given and repeats on
every invocation. The `>=` remains the least interesting thing left to buy.

---

## 5. Still open after Phase 7

- **`RETIRE_HARD` is closed, not open.** The Phase 7 draft of this list deferred the choice — delete
  it, or make the predicate per-turn and resurrect it — to the owner. The owner took the second
  branch on the predicate and the first on the constant: per-turn *and* deleted. Nothing about it
  is outstanding.
- **The 180,000 threshold has a change-rule, not a tuning question.** It replaces the old "is
  256,000 right?" item, which was a preference. It is not one now: with a single gate the
  constraint is `RETIRE_AT + worst_turn < ceiling`, worst measured turn growth is ~170K and the
  ceiling is ~360K MEASURED, so the number has a ceiling of its own at roughly 190,000. **Lower it
  freely. Raise it only with a new measurement of worst-case single-turn growth**, and change both
  copies — `healbot.ts:135` and `healbot.tsx:57` — since `probe_twin.py` asserts the two defaults
  are equal, with a mutation check that corrupts one side and requires the comparison to trip.
  Raising it on the strength of "sessions feel short" is the failure mode this rule exists to stop.
- **The 180,000 firing run** is unbought; see §4. The arming half is closed.
- **Startup sweep** for sessions already over the gate when a server restarts. Premise TRUE
  (`consider()` has one call site, no polling, `handled` is per-process and empty on restart) and
  it is ~15 lines reusing `healbot_list`'s query and `describe()`'s scan. Still deliberately not
  built: a restart causing mass retirement is a policy decision. **Rationale correction:**
  `docs/HEADLESS.md` and `HARNESS.md` credited `RETIRE_HARD` with catching the restart case
  mid-turn. It never could — it was inert — and it no longer exists. The single gate catches it, at
  the end of the next turn on that session, which means a session restarted mid-work is not swept
  until it next finishes something.
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

**The reversal in §1 is the same theme one level up, and it is worth separating from the others.**
Those five were claims that outran their evidence. This one was a *fix* that outran its own
consequences: the review established what the predicate did, the first decision resolved what to do
about it, the second decision reversed that — and none of the three said anything about the
threshold, because the threshold had not been wrong in any of them. It only became wrong as a
result of two changes that were each individually correct. What caught it was not a rig and not a
review; it was somebody adding to 256,000 nothing more exotic than "the worst turn we have actually
measured" and reading the answer against a ceiling already written down two documents away. The
suite would have passed. `probe_headless_arm.py` would have cheerfully asserted that 256,000 armed,
and `probe_turn_predicate.py` — the new one, the one written for exactly this defect — would have
confirmed the predicate was per-turn. Both would have been right. The session would still have
died.

The generalisable form: **when a fix changes the semantics of a predicate, every constant sized
against the old semantics is now unverified**, whether or not anyone mentioned it. Re-derive them
before shipping, not after the first `ContextOverflowError`.

The suite's characteristic failure is still passing.
