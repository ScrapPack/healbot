# Phase 8 — the number that rested on one turn

Date 2026-07-27. Nothing was built this phase, deliberately: every step of the build order was
already built and no known correctness hole was open. What was left was one decision, some
verification that had never been re-run, and one optional spend.

Three of the four things that came out of it are corrections, and the pattern is the same one
Phase 7 named: **claims that sounded verified and had only been reasoned.** The difference is that
this phase went looking for them in the two places nobody had looked — the derivation under the
shipped threshold, and the premise under a rig's own comment.

| | |
|---|---|
| **`worst_turn` was one measurement, and it was not the worst** | Re-derived from all 1,050 messages on disk — 86 completed turns. On the pinned model the true worst is **175,148**, not ~170,000, which moves the gate's own ceiling from ~190,000 to **184,852**. Off the pinned model the corpus holds a **223,258** turn. §1 |
| **`healbot_*: deny` is a CONTEXT control, not a sandbox** | The build agent, denied the five tools, ran `opencode run` through `bash` and created a real top-level session. The rig's own comment had asserted this was impossible since the day it was written. §2 |
| **The session route never renders a dismissed question** | Not a scroll-position problem and not an errored-tool-part problem — both candidates were wrong. The renderer has two branches and the one that prints the text is gated on an answer existing. Closed at source, free. §3 |
| **An external plugin CAN register a route** | Same API factory, same activation loop, no discrimination — and external plugins are activated *after* builtins into a last-wins map, so one can silently replace the grid. Closed at source, free, and it produced a new trap. §4 |
| **The startup sweep** | Decided by the owner: **not built.** Event-driven only. §5 |

---

## 1. Is ~170K the tail or the middle?

`RETIRE_AT = 180,000` is derived, not chosen. With one per-turn gate the requirement is

```
RETIRE_AT + worst_turn < ceiling
```

with the ceiling MEASURED at ~360K (`docs/HARDEN.md:227`). Until this phase `worst_turn` was **one
turn, measured once** (`docs/HARDEN.md` §6). The whole shipped number rested on it, and one data
point cannot tell a tail from a middle.

`probe_turn_growth.py` re-derives it from every session database on disk. **FREE, 15/15** (16/16 since
Phase 9 added a fixture check on the pinned-model population — `docs/CLONE.md` §2).

> **Phase 9 note.** The corpus below is 86 turns; it is **94** now, and the delta is `hb/control.db`,
> written by `verify_control_agent.py` §2 *after* these figures were recorded. Every maximum, bound
> and conditional in this section is unchanged across that growth. The counts are a snapshot — the
> suite writes to the corpus it measures. `docs/CLONE.md` §4.

### What is measured, and why it is not what §6's table shows

`docs/HARDEN.md` §6 is a table of per-**STEP** occupancy that was read as a whole-turn span. The
quantity the gate needs is the **end-of-turn to end-of-turn delta**:

> the gate fires at the end of turn `T` when `O(T) >= RETIRE_AT`; worst case the session sat at
> `O(T-1) = RETIRE_AT - 1`; so peak occupancy is `RETIRE_AT + (O(T) - O(T-1))`.

So `worst_turn = max over turns of O(T) - O(T-1)`. That is not the span from a turn's first step to
its last — a turn's first step already carries the whole prior window.

### How it avoids measuring itself

- **The shipped source is what runs.** `turnFinished()` *and* `occupancyOf()` are brace-matched out
  of `harness/config/opencode/plugin/healbot.ts` and evaluated in `node`; `RETIRE_AT` is read from
  the same file. Re-implementing any of the three would have measured the probe, and `turnFinished()`
  is the entire subject — grouping by message instead of by turn is the Phase 7 defect.
- **Fixture check.** The corpus is asserted to be the one five documents cite: the real
  `~/.local/share/opencode/opencode.db` reproduces **677 `tool-calls` / 56 `stop` of 733** exactly.
  A different split would mean a different corpus and the probe says so.
- **Negative control.** The identical corpus regrouped with the OLD per-step predicate must give a
  materially smaller worst case, and does — **141,412 against 223,258**. If the two predicates
  produced the same distribution the grouping rule would be decorative.
- **Exclusions are counted, not silent.** 21 unterminated turns and 3 negative (compaction)
  boundaries are reported rather than dropped.

### The distribution — 86 completed turns

| population | n | max | p95 | p90 | p75 | p50 |
|---|---|---|---|---|---|---|
| **all** | 86 | **223,258** | 171,530 | 136,640 | 41,009 | 22,152 |
| rig workloads (all `gpt-5.6-sol`) | 29 | 175,148 | 96,700 | 90,089 | 22,152 | 22,152 |
| real sessions | 57 | 223,258 | 177,110 | 142,295 | 64,439 | 17,775 |
| · `gpt-5.6-terra` | 13 | 223,258 | 223,258 | 182,918 | 135,189 | 29,611 |
| · `gpt-5.5` | 15 | 171,530 | 171,530 | 143,757 | 136,237 | 57,960 |
| · `kimi-k3` | 6 | 142,295 | 142,295 | 142,295 | 141,495 | 41,009 |
| per-**step** growth, for contrast | 764 | 164,902 | 22,043 | 16,486 | 5,684 | 1,163 |

**The literal question has a clean answer: ~170K is the TAIL.** The p50 of turn growth is 22,152 —
under an eighth of it. There was never a risk that 180,000 was too high because ~170K was typical.

**But the derivation did not use ~170K as a p95. It used it as a maximum, and it is not one.**

### What actually moved

```
the rule:                            RETIRE_AT + worst_turn < ceiling (360,000)
as shipped, worst_turn = ~170,000:   180,000 + 170,000 = 350,000            OK
worst turn on the PINNED model:      180,000 + 175,148 = 355,148            OK, margin 4,852 (1.3%)
worst turn ANYWHERE in the corpus:   180,000 + 223,258 = 403,258            OVER THE CEILING
worst turn STARTING above 100,000:   180,000 +  70,704 = 250,704            OK  (n=20)
```

Three readings, and the honest position is that the first is what the harness runs and the second is
the reason not to relax about it.

**On the pinned model the shipped gate survives — by 4,852 tokens, 1.3% of the ceiling.** That is
the finding, and a green assertion is the wrong way to read it. `HARNESS.md` already rejected the old
350,000 default for leaving *"~10K, under 3%"* of margin, calling it *"too late to be a guard"*.
**This margin is thinner than the one that was condemned.** And it is a margin against the largest
turn ever *measured*, not against the largest possible one — the corpus itself contains a turn 27%
larger, one model over.

So the gate's own ceiling is **184,852, not the ~190,000 on record** in `docs/RELAY.md` §1,
`HARNESS.md` and `harness/env.sh`. The shipped 180,000 clears it by 4,852. Every document that says
~190,000 derived it from `worst_turn ~170,000` and is now off by the same 5K.

> **SUPERSEDED IN PHASE 12: the bound is 289,296 and the margin is 30.4%.** This section corrected
> the *input* to the derivation and inherited its *population* — the maximum over every turn on
> disk. That population is dominated by first turns out of empty sessions (175,148 is one; so are
> 299,326, 223,258, 182,918 and 177,110), and the gate never faces one. A turn that starts at 0 and
> grows 175,148 ends at 175,148, far under the ~360K ceiling. Phase 12 gave the corpus a declared
> scope — completed, started >= 100,000, compaction off — and re-derived: in-scope maximum
> **70,704**, bound **289,296**, margin **109,296 = 30.4%**. The §2 decision to leave 180,000 stands
> and is better supported than when it was made. The model-specificity finding below is
> **unaffected and now matters more**, because the in-scope population has almost no pinned-model
> evidence in it. `docs/OUTCOME.md` §11.

### The new constraint nobody had written down: THE THRESHOLD IS MODEL-SPECIFIC

`worst_turn` is a fact about how far one agent turn grows, which is a fact about a **model's**
tool-calling behaviour. The corpus makes that concrete: **3 turns off the pinned model exceed the
pinned model's worst case, the largest by 48,110 tokens.** A 223,258-token turn at a 180,000 gate
lands at 403,258 and the session dies.

The harness pins `openai/gpt-5.6-sol` (`harness/config/opencode/opencode.jsonc:16`). **That pin is
load-bearing for `RETIRE_AT` and nothing said so until now.** `probe_turn_growth.py` asserts the pin,
so changing the model turns the probe red — which is the correct behaviour, because changing the
model makes the threshold unverified.

### The counter-signal, and why it is not a licence to relax

Conditioned on where the turn *started* — the scenario the gate actually faces — growth collapses:

| turns starting at ≥ | n | max | of which are the synthetic 22,152/turn loop |
|---|---|---|---|
| 0 | 86 | 223,258 | 16 |
| 50,000 | 31 | 70,704 | 13 |
| 100,000 | 20 | 70,704 | 11 |
| 150,000 | 13 | 32,673 | 9 |

Every huge turn in the corpus is a **first** turn out of a near-empty session; the largest turn that
began above 150,000 added 32,673. Physically that is unsurprising — but it does **not** license
raising the gate, for two reasons. The sample is thin (9 of the 13 high-start turns are
`verify_retire_350k.py`'s fixed-size growth loop, so ~4 real observations carry it), and it is
survivorship-shaped: sessions that take a 223K first turn are short and never reach the gate, which
is a fact about which sessions get old, not a bound on what an old session can do. There is no
mechanism that stops a turn starting at 179,999 from adding 223K.

### The decision — DECIDED, option 1

The change-rule in `docs/RELAY.md` §5 is *lower freely, raise only with a new measurement*. This is a
new measurement and it points **down**. Nothing here was urgent — the shipped number still satisfies
its own rule on the pinned model — but 1.3% of ceiling is not the margin the documents implied.
Four options went to the owner, cheapest first:

1. **Leave 180,000, fix the prose.** The ~190,000 bound becomes 184,852 and the model-pin constraint
   gets written down. Costs nothing; the margin stays at 1.3%.
2. **Lower to ~150,000.** Restores a ~35K cushion above the pinned model's measured worst turn, at
   the price of shorter sessions and more handoffs.
3. **Lower to ~136,000.** Satisfies the rule against the *whole* corpus including other models —
   i.e. makes the threshold insensitive to a change of model pin. Materially shorter sessions.
4. **Restore a second, mid-turn gate.** The thing `RETIRE_HARD` was drawn for, deleted in Phase 7 for
   good reasons (it was inert — under the *old* per-step predicate. Under the current per-turn one it
   would not be). The only option that decouples the threshold from `worst_turn` again, and the only
   one that is a build.

**The owner chose option 1: `RETIRE_AT` stays at 180,000, and the prose is corrected.** That is a
decision on the record, not inaction, and the distinction matters — the next session should not
re-open it as a defect. What it accepts, stated plainly so it is inherited honestly:

- a **4,852-token margin, 1.3% of the ceiling**, against the largest turn ever measured;
- that the margin is against a *measured* maximum and not a real one — nothing bounds turn growth
  from above, and the corpus already contains a 27%-larger turn one model over;
- that the number is **only valid while the model pin holds**, which `probe_turn_growth.py` now
  guards.

The corrections that shipped with the decision: `~190,000 → 184,852` in `HARNESS.md`,
`docs/HARDEN.md` §6, `docs/RELAY.md` §1 and §5, and `harness/env.sh:113`; the model-pin constraint
written into `HARNESS.md`'s Traps, `harness/env.sh` and this file.

---

## 2. `healbot_*: deny` is a context control, not a sandbox

`verify_control_agent.py` was — **so this section claimed, and Phase 10 disproved it; see
`docs/VERDICT.md` §2, where `verify_handoff.py` turns out to have had the identical property two
phases longer** — the one rig in the suite whose recorded score did not correspond to an
execution of the file as it stood — its single failing assertion had been rewritten **twice** without
a run. Re-running it was the cheap item on this phase's list.

It came back **15/16 again, and the failure was a different one, for a much better reason.**

The build agent — handed the same instruction as the control agent, with the five `healbot_*` tools
removed from its payload — ran nine `bash` calls:

```
opencode --help
opencode session --help
opencode session list --help
opencode session list --format json
opencode run --help
opencode db --help
opencode db ".tables"
opencode db "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name" --format json
opencode run --auto --format json --title "Create hello.txt with exact content" "Create a file named hello.txt …"
```

That last call created a real **top-level** session — `ses_05a078334ffe`, 1 user + 3 assistant
messages, agent `build`. It reconnoitred the CLI first and then used it.

**The rig had been carrying the opposite claim in a comment since the day it was written:**

> *"asks for something ONLY the control tools can accomplish — a session cannot create ANOTHER
> session with `bash`, so a build-agent turn has no way to satisfy it and must say so."*

That premise is false. The `opencode` CLI is on `PATH` inside the tool sandbox and talks to the same
database.

### What it costs and what it does not

**It does not touch the claim the file is paid for.** The tool *definitions* are still absent from
the build agent's request payload — the token-budget claim, which is why the scoping exists at all
(five tools left global would be rent every session pays forever). That assertion passes, and so does
`SCOPING HOLDS: control has them, build does not`.

**What it kills is a containment reading.** `healbot_*: deny` scopes **context**, not **capability**.
Any agent with `bash` reaches the same capability the long way round. Nothing in this project ever
depended on containment — but `HARNESS.md` describes the deny as keeping the tools "out of every
other session's prompt", which is exactly right, and it is worth stating plainly that this is the
whole of what it buys.

### The fourth form of the assertion

The sequence is the lesson, so all four are kept in the file:

1. *"the build agent created no new session"* — **FAILED on execution.** The extra was its own
   `@general` subagent, which `task` legitimately creates. Measuring the wrong thing, and it made
   the deny look broken for doing the right thing.
2. *"`all(s.get('parentID') for s in extras)`"* — **vacuously True on an empty list**, and `extras`
   is empty whenever the build agent answers directly. Caught in a Phase 7 review, never run.
3. *"it created NO top-level session"* — **DISPROVED on execution, Phase 8.**
4. *"no healbot TOOL spawned anything for it"* — the claim the deny actually makes, checked against
   the **server log**, which only the server writes: exactly one `control: spawned` line must exist
   and it must name the control agent's session. If the deny leaked and the build turn spawned
   through the tool, a second line appears.

Note the shape of 2 → 3. Form 2 was too weak to fail; form 3 was strong enough to fail, and did — on
its first execution, against a premise that had gone unexamined for two phases. **A test that cannot
fail is not merely useless, it is load-bearing in the wrong direction:** it was the reason nobody
re-read the comment.

The containment finding is now printed on every run as an `[observation]`, deliberately **not** an
`r.check`. It has no failing case — a run where the build agent behaves is as consistent with the
finding as one where it does not — and an assertion that cannot go red is this suite's
characteristic failure. When the bash route is taken the command is printed verbatim; when it is not,
the line says `NOT EXERCISED this run` rather than reading as covered.

### Re-run after the correction — **15/15, TESTED**

The corrected file was executed end to end, so this is the first recorded score for
`verify_control_agent.py` that corresponds to the file as it stands. It is 15 rather than 16 because
the disproved assertion was replaced by one assertion, not two.

**And the second run exercised the other branch, which is the useful part.** This time the build
agent reached for `task` and `webfetch` instead of the CLI — `['bash','bash','bash','webfetch',
'bash','bash','webfetch','webfetch','task']` — producing 1 extra session, **0 top-level**, 0
session-creating bash calls. The observation line printed `NOT EXERCISED this run` instead of
reporting a green. So across the two runs both directions are on record:

| run | build agent's route | extras | top-level | observation line |
|---|---|---|---|---|
| 1 | `opencode run` via `bash` | 1 | **1** | printed the command verbatim |
| 2 | `task` subagent | 1 | 0 | `NOT EXERCISED this run` |

That is also the answer to *why the deny looks fine most of the time*: the build agent's response to
losing the tools is not deterministic. It delegated in Phase 6, shelled out in Phase 8 run 1, and
delegated again in run 2. An assertion that only fails on one of three behaviours is exactly the kind
this suite keeps producing, which is why the finding is pinned to the recorded run rather than to
whatever the next execution happens to do.

---

## 3. The session route never renders a dismissed question — closed at source

Open since Phase 6: the text of a dismissed question is in the session's parts over HTTP (asserted,
passing) but not on the visible viewport. The two candidates on record were **scroll position** and
**how an errored tool part renders**. Both are wrong. VERIFIED, free, no run:

- `Question` (`routes/session/index.tsx:2543-2577`) has exactly **two** branches. The only one that
  prints `q.question` (`:2562`) sits under `<Match when={answers()}>`.
- `answers()` is `parseQuestionAnswers(props.metadata.answers)`, and that returns `undefined` when
  the value is not an array (`:2690`) — which is precisely the rejected case, where the tool errored
  and no answers were ever written.
- So a dismissed question falls to the second branch: `<InlineTool icon="→" …>Asked N questions`
  (`:2571-2573`). The count is rendered; **the question text has no render site on this path at all.**
- It is struck through rather than red: `denied()` matches `QuestionRejectedError` (`:1857-1864`), so
  `failed()` is false and `InlineToolRow` applies `TextAttributes.STRIKETHROUGH` (`:1949, :1962, :1969`).

**This is by construction, not a bug in the reconcile and not a property of the grid.** The grid's
own `question.rejected` path is TESTED 22/22 (`docs/HEADLESS.md`); what the session route does after
the block clears is upstream behaviour. Worth knowing rather than worth fixing: an operator who
dismisses a question from the grid can still read what was asked over HTTP, and cannot read it on the
session route.

---

## 4. An external plugin CAN register a route — closed at source, and it produced a trap

Open since Phase 0: F7 proved a *builtin* can register a route and that `route.register` is on the
public API; the external case was untested, and it decided whether the grid must live inside the
fork. **VERIFIED, free, no run: it can. The paths are the same code.**

- Internal plugins are turned into `PluginEntry` at `plugin/tui/runtime.ts:1093-1104`; external ones
  at `:776-808` (`addExternalPluginEntries`). Both set `plugin: entry.module.tui`.
- Both then go through **one** loop — `for (const plugin of next.plugins) … await
  activatePluginEntry(next, plugin, false)` (`:1106-1113`).
- `activatePluginEntry` (`:516`) calls `pluginApi(state, plugin, scope, plugin.id)` at `:525`
  unconditionally, and `pluginApi` builds `route.register` at `:577-579` for every entry regardless
  of source.
- The **only** place `source` is discriminated in the whole activation path is `:328`, a metadata
  display field (`state: source === "internal" ? "same" : "first"`). Nothing gates `route`.

So the grid does not *have* to live inside the fork on this axis. That said, this is **VERIFIED**
(the API is handed over identically), not **TESTED** (an external plugin's route rendering end to
end has still never been run), and everything else measured in this repo was measured on the builtin
path.

### New trap: an external plugin can silently replace the grid

Internal plugins are added **before** external ones, the activation loop is sequential, and its own
comment says *"route registration is last-wins when ids collide"* (`:1108-1110`). The route map
agrees: `get(name)` returns `routes.get(name)?.at(-1)?.render` (`tui/src/plugin/api.ts:33-35`).

**So a third-party TUI plugin that registers a route named `healbot` wins over the builtin**, with no
error, no warning, and no log line — the operator presses `ctrl+p → healbot` and gets somebody else's
screen. The harness does not currently pin or reserve the name.

---

## 5. The startup sweep — decided, not built

`consider()` (`harness/config/opencode/plugin/healbot.ts:681`) has exactly one call site, there is no
polling, and `handled` is per-process and empty on restart. So a server that restarts with a session
already over the gate does nothing until that session's next event, and then catches it at the **end
of that turn** — one whole turn of consumption later, since Phase 7 made the predicate per-turn.

Presented to the owner as four branches (don't build / sweep and retire / sweep and flag only /
sweep bounded and capped). **Decision: do not build it. Event-driven only.**

This is now a **decision, not a defect**, and the row moves out of "Still open" for that reason. The
consequence it accepts, stated plainly so nobody re-opens it as a bug: a session parked above the
gate when the server restarts stays above the gate indefinitely if it is never prompted again, and a
session restarted mid-work is not swept until it next finishes something.

Worth noting alongside §1: the gap this leaves is bounded by the same `worst_turn` arithmetic. A
session caught one turn late is caught at `occupancy + worst_turn`, which is exactly the exposure the
threshold is already sized for. The sweep would not have bought extra safety margin — it would have
bought *promptness*.

---

## 6. Still open after Phase 8

- ~~**`RETIRE_AT` has a live recommendation against it.**~~ **DECIDED: stays at 180,000, prose
  corrected.** §1. Not open, and re-opening it as a defect is the specific mistake to avoid. What is
  inherited is the accepted margin (1.3%) and the fact that the number is only valid while the model
  pin holds.
- **The model pin is load-bearing and newly so.** `probe_turn_growth.py` guards it. This one *is*
  live: it is a constraint on future changes, not an outstanding task.
- **The 180,000 gate has still never been fired at its real value.** Unchanged from Phase 7 §4;
  costing re-derived there at ~$2.60. **Offered and declined this phase** — the remaining
  uncertainty is a single `>=` against a variable, already TESTED at 20,000 and threshold-independent
  by inspection.
- **An external plugin's route has never actually been rendered.** §4 settles *can it* at VERIFIED;
  *does it, under a real workload* is still unbought.
- **Phase 3's exit gate** — `/code-review ultra` on the `harness/` diff. User-triggered and billed;
  an agent session cannot launch it.

---

## 7. The method note

Phase 7 ended by naming its own characteristic failure: *claims that sounded verified and had only
been reasoned*. Phase 8 found three more, and all three were in places that had been read many times:

- a **derivation** whose input was a single measurement, repeated verbatim across five documents
  until the repetition looked like corroboration;
- a **rig's own comment** asserting an impossibility, which the rig had never been asked to test
  because the assertion built on it kept being rewritten instead of run;
- two **hypotheses about a UI bug** (scroll position, errored-part rendering) that had been on the
  open list for two phases and were both refuted by reading forty lines of the renderer.

The generalisable form, and it is the sharper version of Phase 7's: **a number is not evidence, and
repeating it does not make it more evidence.** `~170K` appeared in `HARNESS.md`, `docs/HARDEN.md`,
`docs/RELAY.md`, `harness/env.sh` and `NEXT.md`. Five sites, one turn, and the derivation that sized
the shipped threshold treated it as a bound. Re-deriving it cost nothing — the data had been sitting
in `~/.local/share/opencode/opencode.db` the whole time, and it is the same file the 733-message
figure was already quoted from.

And one that is Phase 8's own: **the failing assertion needed the same scrutiny as a passing one.**
`probe_turn_growth.py`'s first run reported 223,258 and a red derivation. Before that could be
written down it had to survive the question *"is this an artifact of my grouping?"* — a turn that
never terminates in the middle of a session would make the next delta span two turns and inflate it.
It was not: the 223,258 turn is a 19-message session, one user message and eighteen steps. But the
check is the reason the number can be quoted, and this suite's discipline had only ever been written
down for greens.
