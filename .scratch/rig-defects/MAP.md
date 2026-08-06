# Map: defects the review found and nobody fixed

## Destination

**The three verified, still-live defects surfaced by the daily-driver map's ticket 16 are each
repaired or consciously accepted, with the evidence recorded either way.**

Created 2026-08-05. These came out of the calibration of healbot's review bar
([daily-driver ticket 16](../daily-driver/tickets/16-calibrate-the-review-bar.md)): a crewmate
classified every `error`-severity review finding ever produced, and seven were `unacted`. Six of
the seven were then verified factually correct by reading the cited code. Three of those are still
live on `main` and are the tickets here.

They are here rather than on the daily-driver map because that map's Out of scope rules out the
paid measurement backlog by name, and all three are rig or corpus defects. Nothing here blocks a
human from using healbot as a daily driver. If the captain would rather they sat on the
daily-driver map, moving them is a file rename.

Scope: these three only. This is a defect list, not a rig-quality effort.

## Notes

- Every claim in these tickets was verified by reading the code, and the line numbers were
  re-derived at close on 2026-08-05. Re-derive before relying on them; `probe_citations.py` catches
  positional rot but not semantic rot.
- **The corpus is evidence, not state.** `/paid-run-protocol`'s rule is archive, never delete, and
  a recorded run's metadata describes what that run actually did. A repair that edits a completed
  run's record to make it read correctly has falsified evidence rather than fixed a defect. Ticket
  03 turns entirely on this.
- `/rig-assertion-discipline` before touching any probe or rig assertion. Ticket 02 is a specimen
  of exactly the class that skill exists for.

## Decisions so far

None yet. Three open tickets.

## Not yet specified

- **Whether an assertion that cannot fail should be a gate row.** Ticket 02 is the eighth or ninth
  found in this repo. `/rig-assertion-discipline` records the class from experience; nothing
  mechanically detects one. Whether that is checkable at all is a real question and is not sharp.

## Out of scope

- **Re-running any paid study.** Ticket 01 is about a guard on starting one, not about starting one.
- **The rest of the measurement rig.** These three are the ones a review found and a human verified.
  A general rig audit is a different effort.
- **The review bar itself.** Whether `blocking` gets switched on is the daily-driver map's ticket 13.
