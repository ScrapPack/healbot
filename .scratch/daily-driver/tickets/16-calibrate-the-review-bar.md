# Were the review's error findings ever right

Type: task
Mode: AFK
Status: closed
Assignee: calib
Blocked by: -

## Question

Ticket 12 chose per-crewmate-completion in `blocking` mode. `blocking` is fail-closed on a severity
string the reviewer model assigns to its own finding: anything not explicitly `warning` or `info`
refuses, and an untagged finding refuses too
([gate/review.py:238](../../../gate/review.py)). Nobody has ever checked whether those findings were
right.

The scale, measured at ticket 12's close from the 119 records in `gate/runs/*-review.json`: 110
reviews reached the model and produced 27 `error` findings, spread across 22 reviews. So `blocking`
would have refused **20% of the captain's own pushes**. Under the new trigger that same bar sits
between every crewmate and its claim of done.

If the false-positive rate is high, ticket 12 built a bottleneck rather than a bar, and the noise
lands on the captain instead of on the crew. That is worth knowing before crew live under it, not
after.

The evidence already exists and costs nothing to read. The captain has been acting on review
findings by hand for weeks, and the acts are in the history: commit c0e19cd is literally a commit of
review fixes, and d7d95ca's subject names the finding it repairs. So each `error` finding can be
read against what the tree did next.

## Method

Records only. **No API credits.** Do not re-run any review.

1. Pull every finding tagged `error`, plus every untagged finding, from `gate/runs/*-review.json`,
   with its file, line, summary and the record it came from.
2. For each, read the cited file:line as it stood at that record's `head`, and read what the tree
   did next: a following commit that repairs it, a commit message naming it, or nothing at all.
3. Classify each: **real** (the finding named a defect and the tree repaired it), **wrong** (the
   finding was mistaken about the code, verifiable by reading the cited lines), or **unacted**
   (nobody did anything, which is not evidence either way and must not be scored as wrong).
4. Report the counts and the rate, and quote the clearest two of each class.

Classification is a factual determination against the tree, so it is delegable. Whether the
resulting rate is acceptable is the captain's call and is NOT part of this ticket.

**Resolved when** the three counts exist with the per-finding classification behind them, and the
captain has ruled on whether the rate clears `blocking` to be switched on. Until that ruling,
`blocking` mode stays off at every trigger.

## Resolution

Closed 2026-08-05 on the measurement half. Worked by the crewmate `calib` in pooled slot-1, records
only, no API credits. Full report, brought into the tree by the first mate:
[16-review-bar-calibration.md](../research/16-review-bar-calibration.md).

**The ruling is NOT in this ticket.** The resolved-when above has two halves and only the first is
delivered. The captain has not ruled on whether the rate clears `blocking`, and closing this ticket
does not make that ruling. It is carried on ticket 13, which cannot meet its done-condition until
it exists. Do not read a closed 16 as a live `blocking` mode.

### The counts

**real 18, wrong 0, unacted 7, unclassifiable 0**, plus **2 excluded**. False-positive rate
**0 / 18 = 0%**, over the acted-on findings only.

Read it narrowly, for four reasons the report establishes rather than asserts:

1. **The denominator is self-selecting.** "Real" rests for 15 of the 18 on a repair commit naming
   the finding. A finding the captain judged wrong would leave no repair commit and land in
   `unacted`, not in `wrong`, so the corpus can barely separate "wrong" from "ignored". The honest
   floor is: **no repair commit in the corpus refutes an error-severity finding.** The refutations
   that do exist all landed on `warning` findings.
2. **One "real" is not attributable to the review.** The `docs/SHIP.md` stale-citation finding was
   repaired incidentally by work already in flight, whose twin commit landed before the review even
   ran. Excluding it gives 17 real and a rate of 0/17, still 0%.
3. **The unacted findings are not noise.** Six of the seven were verified factually correct by
   reading the cited code. They are unrepaired, not mistaken. The seventh turns on a judgment about
   a repo rule rather than a fact about code and was deliberately not adjudicated.
4. **The corpus is 25, not 27.** Two of the "27" are `x.py` stub findings emitted by a stubbed CLI
   during plumbing tests, with `total_cost_usd: null` and a path that has never existed. One of
   them ran in `mode: "blocking"` and is recorded `state: "blocked"`, so it is a synthetic block
   sitting in the corpus that any naive count of "pushes blocking would have refused" absorbs.
   Ticket 12's close carried the 27 figure; it is corrected here rather than there, because 12's
   figure described the extraction rule it stated and this one describes what the model actually
   produced.

### The finding that bears on ticket 12

**Severity, as the reviewer assigns it, did not predict what the captain acted on.** In one review
the `warning` and `info` findings were both repaired within four minutes and both `error` findings
were left; both are still open on `main` today. Ticket 12 gates crew work on exactly that severity
string. This does not overturn 12, whose bar is fail-closed by design, but it is direct evidence
that the bar's stringency and the captain's actual priorities are not the same ordering, and it
belongs in front of whoever rules on switching `blocking` on.

Two smaller results in the same direction: **no untagged finding has ever existed**, so `blocking`'s
fail-closed clause for untagged findings is untested by this corpus rather than validated by it;
and the review stage has **found real defects in itself**, including one where its own truncation
repair would have turned a push-refusing ERROR into a silent PASS.

### Carried forward, not fixed

The brief forbade repairs, so three defects the report verified as still live on `main` need a home:

1. **A missing spend tripwire.** With the archived run directory renamed away, a bare
   `run_refusal.py` recreates an empty run directory, finds no meta, skips the compatibility check
   entirely and starts from row zero. That is a paid-run hazard and the most urgent of the three.
2. The `XDG_DATA_HOME` assert in `.carryover/verified/arms.py` still cannot fail.
3. All six `launches[].logs` entries in the archived run's `meta.json` point into a directory that
   no longer exists.

### Process notes worth keeping

The report's own method section records two corrections it made mid-investigation, which is why its
head-resolution is trustworthy: 16 of 22 records predate the `head` field and were resolved by
matching each record's file list against candidate ranges, and the resolution had to move from
parentage to the full `base...head` file set once a push turned out not to be one commit.

Bringing the report into the tree required rewriting eleven of its citations out of live
`file:line` form. They were specimens, quoting what a finding cited rather than pointing at code,
and `probe_citations.py` cannot tell the two apart: it went red on all eleven, exactly as
`docs/CITE.md`'s first draft did. Green at 21/21 after.
