# Phase 4 verification — answer a blocked session from the grid

Date 2026-07-27. Subject: the uncommitted change to
`packages/tui/src/feature-plugins/system/healbot.tsx` (+218/−37, fork HEAD `f819c703`), which
implements build-order step 3 (`PLAN.md:361-363`) — clear a block **without focusing the
session**. Before it, the grid could see blocks but not clear them, and `enter` navigated away
from the control terminal.

**This is a redo.** The first verification of this change ran a local 12B and is void; §1 says
why, because the failure mode is instructive and cheap to repeat.

## Result

> **This block was written for §1–§8 and was stale for a day.** §9 and §10 were appended below
> without revising it, so the headline read *"90 of 91"* and declared the handoff clause
> **unbuilt** while §10 of this same file reported it built and passing. A reader who stops at
> "Result" — the normal way to read a verification report — concluded the gate was not met.
> Corrected in Phase 5, along with the two assertions in §10 that could not fail; see
> [HARDEN.md](HARDEN.md).

**128 of 129** assertions passed on `openai/gpt-5.6-sol` through the real harness. The single
failure is a bug in the test, not the code (§6).

| Run | | Covers |
|---|---:|---|
| `smoke.py` | 6/6 | provider, model pin, `compaction.auto`, one real turn |
| `verify_permission.py` | 40/40 | the exit-gate permission clause at N=4 |
| `verify_question.py` | 27/27 | the question clause, **unforced** |
| `verify_surface.py` | 17/18 | auto-surface, both suppression rules, `tab` cycling |
| `verify_retire.py` | 17/17 | §9 — the retirement observable and a reachable threshold |
| `verify_handoff.py` | 21/21 ⚠ | §10 — retire and hand off with continuity intact. **Phase 10: this score predates Phase 5's edit**, which took the file to 22 unconditional assertions. Unreachable as recorded; needs a re-run. `docs/VERDICT.md` §2 |

The rig is at `.carryover/verified/`, with a README covering how to re-run it. The four
`.carryover/verify*.py` at the level above are the void ones; they are kept only as a record.

**Exit-gate status** (`PLAN.md:391-393`). **Both clauses are met, TESTED.** *"Four sessions
concurrent, one deliberately blocked on a permission prompt and answered from the grid without
focusing"* — §2–§5, and the question equivalent with it. *"One driven past the retirement
threshold and handed off with continuity intact"* — §10.

**Read that with §10's caveat, and with Phase 5's.** The outcome is real: the handoff carried
the objective, both open todos into the successor's own list, and a changed file, at occupancy
90,310 → 5,649. But of the three continuity legs, only leg 2 discriminated — leg 1 asserted a
heading `healbot.tsx` emits unconditionally, and leg 3 passed via the objective echo. A
twenty-first "assertion" was the literal constant `True`. Phase 5 replaced all three and added
mutation checks that fail when the material is removed. The gate is met on the record; the
instrument that recorded it was weaker than its numbers implied.

---

## 1. Why the first verification was void

It ran `ollama/gemma4-agentic:q6` through `@ai-sdk/openai-compatible`. Three consequences, each
independently disqualifying:

1. **Wrong provider path.** The harness pins `openai/gpt-5.6-sol`, and every load-bearing figure
   in this project — the concurrency result, the 350K threshold, the compaction-off hard-error
   behaviour — was measured on it. Tool-call emission, streaming and reasoning parts differ
   between the native OpenAI path and the compatible shim.
2. **The question path was forced.** The 12B would not call `question` on instruction — its own
   reasoning called the request "a trap" and it went grepping instead — so the turn was
   constrained with `tools: {"*": false, "question": true}`. The path that matters is the model
   *choosing* to ask, and it was never exercised.
3. **Local inference serializes** on one GPU, so "four concurrent sessions" was not concurrent
   in the sense the exit gate means.

**Root cause, and the thing to not repeat.** The void run set `XDG_DATA_HOME` to a scratch
directory, believing it was isolating state. `Global.Path.data` derives from it
(`core/src/global.ts:11`) and `auth.json` lives there (`opencode/src/auth/index.ts:10`).
**OpenAI is on oauth** — confirmed directly from `auth.json` — so redirecting the data dir
stranded the credentials and `gpt-5.6-sol` stopped resolving. Reaching for a local model was
the symptom; the env var was the disease.

The correct isolation is the **database only**, via an absolute `OPENCODE_DB`:
`core/src/database/database.ts:43-46` returns an absolute value directly, bypassing the data
dir entirely. This redo sets that and nothing else, and sources `harness/env.sh` literally
(`zsh -c '. env.sh && exec …'`) rather than reconstructing its exports.

---

## 2. The exit-gate permission clause — TESTED

Four sessions on one server. Three ran real tool-using turns (`read` on a file inside the
project); the fourth was blocked by reading `/etc/shells`, which is outside the instance, so
`tool/external-directory.ts:15-45` asks under the default `external_directory: {"*": "ask"}`
(`agent/agent.ts:122`). Nothing was forced and no permission config was set.

**Concurrency.** The three workers finished in 5.1 / 5.3 / 5.9 s against a **6.1 s wall clock**
while the fourth hung. Wall clock equals the slowest single turn, reproducing Phase 2's
concurrency result on genuinely parallel hosted inference rather than a serialized GPU. The
blocked session did not stall the others, and the others did not unstick it.

**The grid.** The blocked cell renders `PERMISSION`; the header reads `4 sessions  1 blocked`;
the footer advertises `a answer · tab next blocked · …`.

**Answering in place.** `a` mounts the session route's own `PermissionPrompt` **below the grid**,
with all four cells still rendered above it. The reply drives `GET /permission` to `[]`, the cell
leaves the `PERMISSION` state, and the panel collapses on its own.

**The route never changed.** `Healbot` owned the screen continuously across open → `tab` →
`a` → answer → clear. The grid is `position: absolute, zIndex 2500`, so its presence on screen
*is* the assertion that `route.navigate("session", …)` never fired.

**The answer reached the model, not merely the server.** The blocked turn completed 25.6 s
later, `/bin/zsh` appears in the transcript, and the model produced prose listing the shells.
That is the distinction the gate actually cares about: clearing a block server-side is not the
same as the session continuing with the answer in hand.

**`a` is inert on an unblocked cell** — it opens no panel and does not hijack the footer, which
matters because a panel opened on the wrong cell would swallow the keyboard.

**Every assistant message was checked** for `modelID == "gpt-5.6-sol"` and
`providerID == "openai"`, so §1's first defect cannot recur silently.

---

## 3. The keybinding gating — the claim most worth breaking

The change moved the grid's bindings to `OPENCODE_BASE_MODE` + `enabled: !answering()`. That is
load-bearing, and the run demonstrated why by accident before it demonstrated that it works.

**Why it is load-bearing.** `mode` is a *require*-condition (`keymap.tsx:56-60`:
`ctx.require(OPENCODE_MODE_KEY, value)`), so a binding set that declares **no** mode registers
no requirement and is live in **every** mode. The two prompts collide with the grid on nearly
every key it uses:

| Prompt | Binds | Mode |
|---|---|---|
| `PermissionPrompt` | `h` `l` `left` `right` `return` `escape` | `OPENCODE_BASE_MODE` (`permission.tsx:568-608`) |
| `QuestionPrompt` | `tab` `h` `l` `j` `k` `up` `down` `return` `escape`, digits `1..N` | pushes `QUESTION_MODE` (`question.tsx:129-134`, `:227-264`) |

Base mode handles the question prompt; `enabled` handles the permission prompt, which pushes
no mode of its own. Neither mechanism alone is sufficient.

**The accidental demonstration.** In the first attempt at this run, a stray `l` sent while the
permission panel was open moved the *prompt's* option selection from "Allow once" to "Allow
always" (`permission.tsx:538` — `selected: keys[0]`), and the subsequent `return` opened the
always-confirm stage instead of replying. The keys really do collide; the grid was correct
throughout and the test was wrong.

**The result.** Under both prompts, `j` `k` `l` `h` left the grid marker at exactly `(8,2)`.
Sent as balanced pairs so the prompt's own selection returns to its default.

---

## 4. The question clause, unforced — TESTED

No `tools` map. No `permission` config. The session was handed a genuine fork in the road with
no mention of any tool:

> *Set up a linter for this project and write its config file. It has to be either Biome or
> ESLint — my team standardised on one of them and getting it wrong means redoing the work. Do
> not write any file until that is settled.*

`gpt-5.6-sol` reached for `question` on the **first** framing, asking *"Which linter did your
team standardize on?"* with options `['Biome', 'ESLint']`. Answered from the grid with `1`:
`GET /question` → `[]`, the cell left `QUESTION`, and the tool reported
`User has answered your questions: …="Biome"` back to the model, which then installed Biome and
wrote `biome.json`. The answer reached the model.

**No permission key was needed, and the reason corrects a standing assumption.** `question` is
`"deny"` in the shared default block (`agent/agent.ts:127`), but the `build` and `plan` agents
each merge `question: "allow"` on top of it (`agent/agent.ts:141-152`). Only the `general` and
`explore` subagents inherit the deny. Registration is separately gated on `flags.client` being
in `["app","cli","desktop"]` (`tool/registry.ts:202`), and `OPENCODE_CLIENT` defaults to `"cli"`
(`core/src/flag/flag.ts:75-76`).

**This closes HARNESS.md's oldest open question** — *"Does `flags.client` land in the allowlist
when the grid drives sessions?"* — at TESTED tier. YELLOW fires.

---

## 5. Surfacing and navigation — TESTED

Neither of the runs above reached these, because in both the block *predated* the grid. Run 4
opened the grid first, with nothing blocked, then created blocks underneath it.

All navigation is asserted on the `▸` marker's `(line, column)`, **never** on cell text — cell
text is present regardless of which cell is selected, so a text assertion would pass for the
wrong reason.

| Behaviour | Evidence |
|---|---|
| a block arriving with the grid open moves the cursor onto it | marker `(2,2) → (8,2)` |
| it does **not** steal the cursor when you already sit on a blocked cell | marker held at `(8,2)`, header went to `2 blocked` |
| it does **not** steal the cursor while an answer panel is open | marker held at `(8,2)`, header went to `3 blocked` |
| `tab` cycles a queue deeper than one | `(8,2) → (8,41) → (8,2)` |
| answering clears exactly one block | 3 pending → 2 |
| sessions created while the grid is open appear in it | header `3 sessions` → `6 sessions`, new cells rendered, `r` never pressed |

That last row is weaker than it looks and is worth stating precisely. It establishes that new
sessions **do** appear, which is what an operator cares about. It does **not** isolate the
mechanism: the grid's own `session.created → reload()` handler and the store's `session.updated`
path would both produce it, and this run cannot tell them apart. The `session.created` trap is
therefore mitigated in observable behaviour, not proven closed at the handler level.

**`escape` is destructive, and the grid's footer is honest about it.** Escape on the permission
panel rejected the request — the file was never read — and left the grid intact. This settles
the source-level claim (`permission.tsx:406` `escapeKey="reject"`, `question.tsx:280`
`escape → reject()`) at TESTED tier. There is no back-out key, which is a real hazard for a
control terminal where you may open the panel on the wrong cell; the footer saying `esc reject`
is the only guard, and it is the right call.

---

## 6. What is NOT established

Recorded because the previous session reported the gate as TESTED on evidence that did not
support it.

> **Three of the four items below were closed after this section was written and it was never
> revised.** Struck through with the correction inline; see §9, §10 and
> [HARDEN.md](HARDEN.md). Only the last is still open.

**~~The cold-start reconcile is unreachable today, so it is untested.~~ CLOSED — TESTED, 21/21
(Phase 5).** The reasoning here was: `cli/network.ts:9` describes `--port` as *"port to listen
on"*, so the TUI always hosts its own server, so a client can never meet a block that predates
it. **The premise is true and the conclusion was false.** `opencode attach <url>` is a separate
registered command (`cli/cmd/attach.ts:7-16`, `index.ts:84`) whose non-`--mini` branch calls
the same `run()` from `cli/tui/layer` with the same `createLegacyTuiPluginHost()` as
`cli/cmd/tui.ts:271-296` — the full TUI, Healbot builtin included. `harness/fleet.sh` ships it.
A permission raised 37 s before any client existed rendered `PERMISSION` on first paint, and
the panel mounted carrying the request's real patterns — so the reconcile carrying **full
request bodies** rather than a `Set` of ids is now TESTED, not INFERRED.

**~~Both "defects fixed in passing" are on that same cold path.~~ Half closed.** The permission
half is exercised by the run above. The `question.rejected` half is still source-reading only:
no rig rejects a question that predates the client.

**~~The handoff clause is unbuilt.~~ CLOSED** — §9 built the threshold, §10 the handoff, and
Phase 5 replaced the two continuity legs that could not fail.

**External plugin route registration** remains untested; the grid is a builtin. **Still open.**

**The one test failure.** `verify_surface.py`'s precondition asserts `not t.find("blocked")`
before any block exists. The grid footer is literally `a answer · tab next blocked · …`
(`healbot.tsx:464`), so that substring is always present while the grid is open — the assertion
could never pass. The meaningful checks in the same run (`1 blocked`, `2 blocked`, `3 blocked`,
each appearing only after the corresponding block) all passed, and they establish that there
were zero blocks at grid-open.

---

## 7. Findings

**The roster renders oldest-first, on a false premise. Pre-existing, cosmetic.**
`healbot.tsx:203-204` reads:

```ts
// Ids are monotonic-ascending, so id order is creation order — newest first.
setRoster([...list].sort((a, b) => b.id.localeCompare(a.id)))
```

Both halves are wrong. Session ids are **descending** identifiers
(`schema/src/session-id.ts:8` → `identifier.ts:22`: `const value = descending ? ~current :
current`), so a later creation time yields a *lexicographically smaller* id and descending ids
already sort newest-first ascending. `b.localeCompare(a)` therefore renders **oldest first** —
the opposite of the comment's stated goal. Confirmed empirically: a blocker created first landed
in cell 0; created last, in the last cell. It is a context line in the diff and present at fork
`HEAD`, so this change did not introduce it. Harmless to the gate, but the comment actively
misleads, and cell order is the thing an operator builds muscle memory on.

**The grid inherits a contradictory label for a destructive key.** The grid footer says
`esc reject`; the question panel it docks says `esc dismiss` (`question.tsx:508`, upstream).
Both are on screen two lines apart while answering. The change's author flagged this in a
comment and chose the honest wording; the fix belongs upstream, in `question.tsx`.

**`/etc/hostname` does not exist on macOS.** The void rig used it as the permission trigger, so
that trigger could only ever have produced a failed read after approval. `/etc/shells` is the
right choice — it is outside any whitelisted directory and its contents are assertable, which is
what makes the "reached the model" check possible.

---

## 8. Gates

Re-run independently, not inherited:

| Gate | Result |
|---|---|
| `tsgo --noEmit -p packages/tui/tsconfig.json` | exit 0, zero output |
| `oxlint …/healbot.tsx` | exit 0, **4 warnings / 0 errors** |

The committed version of the same file emits **5** warnings, so the change reduces them by one.
All four surviving warnings are `typescript-eslint(no-unsafe-type-assertion)` on the same
`as any` / narrowing pattern already present in the file.

---

## 9. Step 6a — the retirement observable (added 2026-07-27)

Continuing the build order. Two things had to be settled before the handoff protocol could be
built on them.

### `prompt_async` was never broken — REFUTED, TESTED

`REVIEW.md` flagged *"`POST /session/{id}/prompt_async` accepts a prompt and executes nothing"*
as a live defect and told Phase 4 to find a workaround, because `PLAN.md:335`/`:341` build the
spawn-and-seed path on it. Both paths run side by side on one server:

| | ack | turn |
|---|---:|---|
| `POST /session/{id}/message` | 5.1 s (blocking) | `finish: "stop"`, text `PONG` |
| `POST /session/{id}/prompt_async` | **0.01 s** | completes **2.0 s after the ack**, `finish: "stop"`, text `PONG` |

Same model, tokens accrued normally, no `Session.Event.Error`. Spawn-and-seed works: a fresh
session seeded through it replied and started at its own occupancy.

**Why it looked broken.** `prompt_async` creates the assistant message row within ~20 ms of the
ack, and that row is **empty** until the turn runs. Poll for "an assistant message exists" and
it is true almost immediately with no content. The completion signal is the message's own
`time.completed` / `finish`. This session made the identical mistake on its first attempt and
caught it only because the run also asserted the text matched the synchronous control. Source
agreed all along: `handlers/session.ts:311-328` calls the same `promptSvc.prompt()` wrapped in
`Effect.forkIn(scope, …)`, and `scope` is bound at `:62` in the `HttpApiBuilder.group()`
construction generator — the layer scope, which outlives any request.

### A threshold that can actually be reached — 17/17

`RETIRE_AT` now reads `HEALBOT_RETIRE_AT`, default 350,000. Occupancy comes from the assistant
message's own `tokens` — the same expression `isOverflow` uses (`overflow.ts:21-33`), with
`cache.read` included — not from `session.tokens`, which is lifetime spend.

| | |
|---|---|
| grower, after reading three 130 KB ledger files | occupancy **37,179** |
| two quiet sessions | 4,969 each |
| grid | cell `RETIRE`, header `1 to retire`, meta line `186%` |

37,179 is far below the 350K default, so `RETIRE` can only be explained by the override
reaching the TUI worker. Precedence checked both ways: blocking the over-threshold session
flipped its cell to `PERMISSION` while the header carried **both** `1 blocked` and
`1 to retire`; answering from the grid reverted it to `RETIRE` rather than to `done`.

**A number that constrains the design.** A freshly spawned and seeded session reads ~**4.8 K**
on its first turn, almost all `cache.read` — the standing-context prefix. That is the occupancy
floor, and it rules out the 5 K threshold `HARNESS.md` suggested for cheap testing: it would
fire on turn one.

`occupancyOf` scans backwards for the most recent *populated* reading rather than taking
`messages.at(-1)`, for the same reason the `prompt_async` report was wrong — an in-flight
assistant row reads all-zero, and mid-turn sessions are exactly the ones you want a number for.

### Two more test-harness bugs, same class as §6's

Both were mine, both found by the assertions disagreeing with the screen dump:
`Term.find()` lowercases, so `find("RETIRE")` also matches the header's `1 to retire`. The
fix is a case-sensitive `exact()` helper — cell labels are uppercase, header phrasing is
lowercase, and only case tells them apart. Worth recording because three of the four failures
across this whole effort have been substring collisions in assertions, not defects.

### Still not built

The handoff itself — `summarize` + `/todo` + `/diff`, spawn, seed, archive the old session,
re-point the grid slot. It needs **"continuity intact"** defined; the term appears in the exit
gate with no definition and no check anywhere in the tree, and it determines what goes into the
handoff document and what the check asserts. The mechanism around it is now unblocked:
`prompt_async` works, the threshold is reachable, and `PATCH time.archived` is known to hide a
session from nothing, so the grid must filter retired sessions itself.

---

## 10. Step 6b — retire and hand off (added 2026-07-27)

The last clause of the exit gate. **21/21** on `openai/gpt-5.6-sol` at `HEALBOT_RETIRE_AT=20000`.

> **Phase 10 caveat.** That run was of the file as it stood at `cdd1096`, which had 21 assertions.
> Phase 5 (`823d7a2`) removed a vacuous check and added two mutation legs — the file now has **22**,
> all unconditional, so no execution of it can produce 21/21. The result below is a true record of a
> Phase 4 execution; it is not a record of the current rig. `docs/VERDICT.md` §2.

### "Continuity intact", defined

The gate never defined it. Adopted definition — a handoff counts only if the successor:

1. is handed the objective,
2. carries the predecessor's **open** todos in its own todo list, and
3. is handed at least one specific file the predecessor changed.

All three assert on **artefacts**, never on the successor's prose. Retirement is
**operator-initiated**: the cell goes `RETIRE`, `x` performs the handoff.

### Result

A worker recorded three todos, completed one, read two 130 KB ledgers to occupancy **90,310**,
and was aborted mid-task. Pressing `x`:

| | |
|---|---|
| successor spawned, seeded via `prompt_async` | 1,096-char passover document |
| open todos carried into the successor's own list | **2/2** |
| completed work re-handed as outstanding | none |
| changed file handed over | `stage1.txt` |
| predecessor archived and gone from the grid | yes |
| route changed | never |
| occupancy | 90,310 → **5,649 (6%)** |

### Three findings

**`GET /session/{id}/diff` returns `[]` without a `messageID`.** `summary.ts:130` returns `[]`
outright when none is given, and `:133` returns `[]` again unless that message is a **user**
message — the git diffs are written onto the user message's `summary.diffs` by
`SessionSummary.summarize` (`prompt.ts:1253`, forked). `PLAN.md:371` says "its `/diff`" as
though one call covered the session. The handoff fans out over recent user messages instead.
This took **two wrong guesses** first — the abort, then a missing git baseline — both refuted
by a probe showing snapshots present 2/2 on a clean uninterrupted turn.

**There are two `summarize`s and the plan conflates them.** `POST /session/{id}/summarize`
routes into `compactSvc.create` (`handlers/session.ts:273-283`) — it is **compaction**, an LLM
turn, and it is what `HARNESS.md`'s "summarize mutates in place and adds tokens" describes. The
git-diff one is `SessionSummary.summarize` (`summary.ts:102-127`, no LLM), which already runs
automatically on the prompt path. The diff data the plan wanted needs no compaction at all.

**A verbatim first user message can carry stale instructions.** Handed an objective that
happened to say *"do only the first, leave the rest pending"*, the successor obeyed it and
replied *"No further work performed."* The document now labels it *"Original instruction, for
context only"*, states that the outstanding list wins where the two disagree, and tells the
successor to **do** the work rather than report on it.

### On unsound assertions — the near-miss worth recording

Continuity legs 1 and 3 were first written as substring checks on the successor's first reply.
Across three runs it said *"verify `stage1.txt`"*, then *"the completed first stage"*, then
*"each remaining stage file"* — every one demonstrating continuity, no two sharing a substring.
The legs flipped pass/fail between runs while every deterministic check passed every time.

A check that turns on the model's word choice measures phrasing, not whether context survived.
Re-running until one came up green would have "passed" the exit gate on noise — the same
species of error as the original local-model run this whole document exists to correct. The
legs now assert on artefacts and the reply is printed as corroboration only.

That makes **four** of the failures across this effort that were bad assertions rather than
defects: `find("blocked")` matching the footer, `find("RETIRE")` matching the header, sampling
a reply mid-turn, and these two.

---

## 11. What this changes elsewhere

Per the process rule adopted in `docs/REVIEW.md` — every phase revises the artifacts it
contradicts — this pass edits `HARNESS.md`:

- **Closed:** *"Does `flags.client` land in the `["app","cli","desktop"]` allowlist?"* → yes,
  TESTED (§4).
- **Closed:** *"Has `healbot.tsx` actually been run?"* → yes, TESTED, including live session
  state, keyboard ownership and answering a block (§2–§5).
- **New trap:** the oldest-first roster ordering (§7).
- **New load-bearing fact:** the exit gate's blocked-permission clause is met.

Not changed, and still open: external plugin route registration, the handoff clause and its
definition of continuity, a configurable retirement threshold, and `/code-review ultra` on the
`harness/` diff.
