---
name: citation-hygiene
description: Citation and prose-fact hygiene for healbot's documents. Invoke BEFORE editing any .md that contains file:line citations, before inserting or deleting lines in a file other documents cite into, and before quoting a recorded score or figure in prose. Earned in Phase 11 (930 citations swept, eight stale) and re-earned every phase since.
---

# Citation hygiene

A `file:line` citation is an untyped coupling between two files: edit either end and it rots
silently. `probe_citations.py` sweeps every document's citations mechanically (it runs in the
gate's Tier 1, on every gate invocation), but it checks POSITIONAL rot only. The rules below
cover what it cannot.

## The three rules

1. **A citation quoted as BROKEN must not be written in live `file:line` form.** Neither a
   reader nor the probe can tell a pointer from a specimen; docs/CITE.md's first draft
   tripped its own check nine times on stale citations it was discussing. Write it out:
   "line 1241 of healbot.tsx". Do not invent an escape marker; it is a hole that silences
   real rot.
2. **Line numbers are for code; section NAMES are for living documents.** HARNESS.md and
   NEXT.md change shape every phase, so every `HARNESS.md:NNN` is guaranteed to rot
   (demonstrated within an hour of the Phase 11 fix). Cite the section name.
3. **Positional rot is checkable; semantic rot is not, and the probe does not claim it.** A
   citation landing on a real, non-blank line that says something else entirely passes.
   Re-read the target before relying on or repeating a citation.

## Editing a file other documents point into

That is the failure mode: Phases 9 and 10 created three of the eight stale citations by
editing documents that other documents cite. After inserting or deleting lines in a cited
file, grep the repo for citations into it and re-derive each against the verbatim quote the
citing row carries. Never repair by adding a fixed offset: PLAN.md's errata was silently off
by +31, then again by +1, and the offset repair would have missed the row that was wrong
before the shift.

## Prose copies are rot surface

A fact held in four or more prose locations will go stale in at least one (the fire()
finding existed in seven files; per-probe expected scores went stale in five). The rules:

- Numbers live in the probes: `Results(expect=N)` floors assert them and the probe prints
  them. Documents say "every probe exits 0" and cite the probe, not the score.
- A recorded score quoted in prose is a citation to an execution: re-run before quoting, or
  name the execution the number came from.
- Before adding a standing paragraph to a living document, check whether a probe, the gate,
  or a skill already owns the fact. One owner, pointers everywhere else.

## Verify

```
cd .carryover/verified && venv/bin/python probe_citations.py
```

Exit 0 required. The gate runs the same probe on every invocation, so a broken citation in a
changed document blocks the change.
