---
name: decision-records
description: When to capture a decision record and when not to, and how to read one. Invoke BEFORE re-opening a question that looks settled, BEFORE changing a threshold, schema or default somebody chose deliberately, and AFTER settling a question where real alternatives were rejected. The store lives outside the repo at ~/.healbot/records/; docs/RECORDS.md owns the mechanism.
---

# Decision records

A decision record answers "why is it like this, and what did we already rule out". It exists
because retirement drops every reason: the handoff carries six fields, discards tool calls,
results and reasoning, and archives a session with no open todos with **no record at all**. The
sessions that finished cleanly are the ones that record nothing.

`docs/RECORDS.md` owns the mechanism, the schema and the limits. This skill is the judgment half:
what is worth recording, and what reading one obliges you to do.

## Read before you re-open

Before you change a threshold, a schema, a default or an approach that somebody chose
deliberately, ask the store:

```bash
python3 harness/memory.py recall "<the thing you are about to change>"
```

If a record comes back, you are not looking at an arbitrary choice. Either its reasoning still
holds — in which case leave it alone and say why — or it does not, in which case **supersede it**
rather than editing around it. A change that contradicts a live record without superseding it
leaves the store lying, and the next session reads the lie.

## Capture: three tests, all three must pass

Record a decision when **all** of these are true:

1. **A question was genuinely open.** Not "what does this code do" — that is a fact, and facts
   belong in a comment beside the code.
2. **There were real alternatives, and you rejected them for reasons.** If there was one obvious
   answer there is no decision to record. `alternatives[]` with nothing in it is usually the
   signal that this test failed.
3. **A later session could reasonably reach a different answer.** If the choice is forced by
   something already written down, point at that instead.

**Do not capture:** progress notes, summaries of what you did, restatements of a commit message,
facts about how the code works, or "decisions" invented because you were asked to record one. A
store full of non-decisions is worse than an empty one — it spends the retrieval budget and
trains the reader to skim.

## Classify honestly, because the classification is a filter

`VERIFIED` and `TESTED` records reach the **orientation block** — 2,000 bytes of standing context
in every session on this project. `INFERRED` and `SUSPECTED` records never do.

That is not a formality. It is the rule that lets `memory.py backfill` import hundreds of commits
without a human reading one of them, because every backfilled record is `INFERRED` by
construction. Marking a hunch `VERIFIED` puts it in front of every future session on this project
as settled fact.

- **VERIFIED** — you read the code, you have `file:line`, the evidence directly supports it.
- **TESTED** — you ran something and it confirmed the behaviour.
- **INFERRED** — evidence points that way but at least one link in the chain is unverified.
- **SUSPECTED** — a hypothesis from patterns, not gathered evidence.

## Capturing

From an opencode session, call `healbot_decide`. Every argument is required; pass `[]` explicitly
for the empty lists.

From anywhere else:

```bash
echo '{"question":"...","choice":"...","classification":"TESTED","rationale":"...","evidence":["<path>:<line>"],"alternatives":[{"option":"...","why_rejected":"..."}]}' \
  | python3 harness/memory.py capture
```

You do not supply the commit sha. The record goes in unanchored and `gate/hooks/post-commit`
stamps it, because the commit you are recording against does not exist yet when you capture.

## Superseding

Set `supersedes` to the id of the record you are replacing. Do not edit the old record and do not
delete it — the history of a choice is the part a later session actually needs, and
`healbot_recall` with `include_superseded` is how it gets it.

`superseded_by` is derived at query time and never stored, so two worktrees can supersede one
record without either write being lost.

## What the store does not decide

It does not replace `NEXT.md`'s `DECIDED` section, which is operator-facing, read by a human at
the start of a session, and frozen at a constant shape. It does not replace the dated phase
records under `docs/`, which hold the evidence. It does not create a `CONTEXT.md` or a
`docs/adr/` — both filenames are banned in this tree (`docs/agents/domain.md`) and this skill
must not create either.

## The limit, stated

Nothing has measured whether these records make an agent's work better. The probe proves the
store stores, isolates, supersedes and degrades correctly; it proves nothing about outcomes, and
`docs/RECORDS.md` §9 says why that measurement is currently out of reach. Treat a record as
context worth reading, not as an instruction.
