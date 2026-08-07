# docs/AFK.md sizes a token cap from byte counts that have moved

Type: task
Mode: AFK
Status: open
Assignee: -
Blocked by: -

## Question

[docs/AFK.md](../../../docs/AFK.md) §1.6 explains why `--max-tokens` is not a dollar figure, and it
does the arithmetic from two measured file sizes:

> *"In a repo where `HARNESS.md` is 77,936 B and `NEXT.md` is 31,360 B and every iteration re-reads
> them, the counter climbs far faster than the bill does."*

Measured 2026-08-07:

| file | doc says | actual | drift |
|---|---|---|---|
| `HARNESS.md` | 77,936 B | 99,293 B | **+27%** |
| `NEXT.md` | 31,360 B | 11,402 B | **-64%** |
| `docs/REFUSAL-BASELINE.md` | 27,932 B | 28,063 B | +131 B |

§3 then carries the consequence forward as *"a repo with a 78 KB index"* when sizing the cap.

This is not a cosmetic count. The whole point of that section is that cache reads are billed into
`--max-tokens` at full weight, so the operator sets the cap from the index size. The index is 27%
bigger than the number they would set it from, and the second file they were told to add is a third
of its stated size. Anyone following the section under-sizes the cap and gets a loop that aborts
earlier than intended, for a reason the doc gives them no way to see.

`NEXT.md` moved because the prose-reduction branch cut 62 lines from it. `HARNESS.md` has grown
across several phases.

## What would close it

Re-measure and rewrite the two sentences. The harder half is that these are the third and fourth
size claims found stale this way, and `docs/HARDEN.md` §7 already saw the pattern coming:

> **"Deliberately not quoting sizes any more."** `fork/README.md` said "24.1 KB, 566 lines" and
> `HARNESS.md` said "12.8 KB" for one file that was 878 lines at the time.

That rule was adopted in one document and never applied to `docs/AFK.md`. The options are to apply
it here too (drop the byte counts, name the files and tell the operator to `wc -c` them), or to keep
the numbers and accept they need re-measuring every phase.

Applying the rule is the better trade: the sentence needs a *ratio* between index size and cap, not
an absolute, and a ratio does not rot.

## Adjacent, same file, already fixed

`docs/AFK.md` also claimed the `git add -A` fixture hazard was *"gone"* while quoting the sentence
that says it is live. That is corrected — see
[rig-defects 05](../../rig-defects/tickets/05-the-fixture-still-holds-four-model-artifacts.md).
