---
name: paid-run-protocol
description: Protocol for anything that spends healbot API credits, verify_*.py rigs, run_refusal.py studies, smoke.py, or driving model turns by hand. Invoke BEFORE running any of them. Covers ask-first, costing, corpus preservation, freeze-at-launch, and post-run accounting.
---

# Paid run protocol

## Rule zero

Ask the owner before spending real API credits on anything beyond a few turns. Items listed
as PAID in NEXT.md's task list are offers, not authorizations; each is still ask-first.

Scope note: "credits" means the metered openai/API spend the rigs and studies burn. The
pre-push review stage's claude call is Claude-subscription usage, standing spend recorded
in gate/GATE.MAP.md's "The model review stage" section; HEALBOT_REVIEW=off revokes it at
any time. It is not an ask-first event per push.

## Cost it before asking

Use the rig README's costing method (`.carryover/verified/README.md`, the costing
paragraphs): cumulative context is quadratic, every turn re-sends everything before it, so
spend scales N(N+1)/2 in turns. Check the provider tier cliff: the 272,000 context tier
DOUBLES every rate above it, so the estimate only holds while the largest single request
stays under it; state the margin in turns. Give the owner a dollar range and wall-clock
estimate (worked example on record: ~$2.60, range $1.75-5, ~6-11 min).

## Before launch

- Free suite green and gate PASS first. Never debug free problems at paid prices.
- **Pair pending free-to-write repairs with the run.** A repair made after paying edits the
  file the new score describes, which orphans the score (the Phase 10 defect).
- **Single-use rigs:** some compare the grid header to a DB literal and pass only on a
  pristine database. Derive counts from what the rig created, or archive the DB first.
- **Studies (run_refusal.py):** the run directory must be the corpus authority. Snapshot the
  corpus and scorer bytes into the run dir at launch; an in-place edit to the live
  `studies/` corpus after paid rows exist orphans the spend (this stranded refusal-full at
  24/150 rows).
- **No environment mutation while a study is in flight.** Check on-disk study state (any
  `hb/ab-runs/*/meta.json` with status "running"), not process liveness; the
  apply-symlinks.sh incident fired one minute after the driver died, through a pgrep-only
  guard, and voided the stock arm.

## During

- Never set XDG_DATA_HOME. auth.json lives there and OpenAI is on oauth; isolate the DB
  only.
- Capture real exit codes (assign output first; never trust a pipe tail's status).
- The model pin is load-bearing: the driver re-reads the pin from returned transcripts and
  aborts on drift. Do not "fix" that.

## After

- **Archive, never delete.** Rig DBs are the corpus `probe_turn_growth.py` derives
  `worst_turn` from (the `hb/*.db` glob). To make a single-use rig re-runnable, archive its
  DB under a name that still matches the glob (`quest.db` becomes `quest-phase12a.db`).
  Deleting one removes the evidence sizing RETIRE_AT.
- **The corpus is tracked in git (since 2026-07-31).** A NEW paid DB needs its own negation
  line in `.gitignore`'s `hb/*` block or it is silently unprotected. Before committing a
  corpus update, fold the WAL in: `sqlite3 file.db "PRAGMA wal_checkpoint(TRUNCATE);"`, so
  the committed bytes are self-contained.
- **The score you record describes the file at that moment.** Bump the rig's
  `Results(expect=N)` floor to what the run produced, and revise every document the run
  contradicts, in the same change.
- **Cost accounting is blind on the oauth openai provider:** `info.cost` records 0.0 while
  token counts are real. Derive cost from tokens and a price table; never report the zero
  as a measurement.
