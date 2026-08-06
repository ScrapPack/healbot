---
description: Orient a fresh session in this repo, then stop. Replaces pasting NEXT.md by hand.
---

Orient yourself in this repo and report. Do not start work.

This repo cannot carry a root `CLAUDE.md`: `gate/gate.py`'s `BANNED` set refuses that filename
tree-wide, because it auto-ingests into every opencode session, which is the cost this project
exists to remove. So orientation is on demand, here, rather than standing context. That is
deliberate and it is the project's own thesis applied to itself.

Do these in order.

1. Read `HARNESS.md`'s index table and its **Agent skills** section. Stop reading when you can
   name the file that owns any given behavior. Do not read the phase records; follow their
   pointers on demand.
2. Read `NEXT.md`'s `DECIDED` section in full. Those entries are closed on purpose and several
   read as defects to a fresh reader. Treat re-opening one as a finding that needs evidence, not
   as a fix.
3. List the live efforts and their takeable work:

```bash
awk -f .scratch/frontier.awk .scratch/*/tickets/*.md 2>/dev/null | sort
```

4. Read the `## Destination` and `## Decisions so far` sections of each map the command found.
   Not the whole map, and not any ticket body yet.
5. Check the working tree is clean and say what branch you are on.

Then report, in under fifteen lines: the destination of each live effort, what is takeable now
by title, and anything in the tree state that would surprise the captain. Recommend one next
action and wait.

Two standing rules for whatever follows. Classify every claim VERIFIED (read the code, cite the
file), TESTED (ran it, captured the exit code), INFERRED, or SUSPECTED, and never present a lower
tier as a higher one. Invoke `/rig-assertion-discipline` before touching any probe or rig,
`/citation-hygiene` before editing any document carrying `file:line` citations, and
`/paid-run-protocol` before anything that spends API credits.
