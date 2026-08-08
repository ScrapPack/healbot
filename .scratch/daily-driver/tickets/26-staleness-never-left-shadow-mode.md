# The staleness stage never left shadow mode, and its calibration is now answerable

Type: task
Mode: AFK
Status: open
Assignee: -
Blocked by: -

## Question

The citation-staleness stage runs on every push and shows nobody anything. Its comment in
`gate/hooks/pre-push` says SHADOW MODE explicitly, and says why: the flag rate was being
calibrated, two replays of historical pushes disagreed by more than 4x on the mean, and both used
today's corpus against old diffs so both were lower bounds. Live records were going to settle it.

**Twenty-six live records now exist and nobody has read them.** Reading them takes seconds and
costs nothing, so the calibration this stage has been waiting on is answerable today.

Read on 2026-08-08 from the main checkout's `gate/runs/*-staleness.json`:

| | |
|---|---|
| records | 26 (24 `measured`, 2 `unmeasured`) |
| total findings | 53 |
| runs flagging nothing | 14 of 24 measured (58%) |
| distribution | bimodal: 0, 0, 0 … then 11, 11, 11, 13 |
| median runtime | 0.21 s (max 0.34 s) |
| the 2 unmeasured | both `git could not diff deadbeef…HEAD`, from plumbing tests, so the refusal path works |

**This is the opposite of the review's behaviour, and that is the finding.** The review is a
fixed-quota producer: roughly two findings per push almost regardless of input, silent on 25% of
repair pushes. Staleness is silent on 58% and then fires hard, and it fires hardest on SMALL
pushes — the 11, 11, 13 runs changed 2, 2 and 10 files. That is what a detector looks like rather
than a generator, and it is what
[the gate blocks on documentation position](25-the-gate-blocks-on-position-not-behaviour.md) needs
as a candidate.

## What to do

1. **Take it out of shadow.** The stage was gated on a calibration that has now happened. Print
   findings by default; keep `HEALBOT_STALE=off`.
2. **Decide whether 58%-silent, 0.21 s and deterministic clears the Tier-1 bar.** It has the three
   properties the gate's own header demands of a blocking row. Whether it should block is a
   separate question and belongs to ticket 25 — do not answer it here, but hand it these numbers.
3. **Re-check the 4x replay disagreement against live data.** The two historical replays were both
   lower bounds by construction. The live records are not, so the disagreement can now be resolved
   or discarded rather than carried as a caveat forever.

## The trap this stage already avoids, worth not breaking

A failure is not a finding. `gate/staleness.py:371` carries that rule and shadow mode withholds
only findings, never the could-not-measure notice. Whatever changes here keeps that split: the two
`unmeasured` records above are the evidence it works, and a stage that renders "I could not
measure" as "I found nothing" is the exact collapse the typed states exist to prevent.

## Done looks like

A push that moves a cited line prints its staleness findings without `HEALBOT_STALE_SHOW=1`, and a
push that moves none prints nothing but the stage header. TESTED both directions against real
pushes, not fixtures, because the shadow-mode records show the two cases are easy to tell apart
only when the corpus is real.

## Numbers in this ticket

Recomputed from `gate/runs/*-staleness.json` in the main checkout, which is gitignored and
therefore absent from a worktree. They are a record of the read on 2026-08-08 and will move with
every push; re-read rather than trusting the table.
