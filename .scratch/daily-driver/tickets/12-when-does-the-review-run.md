# When does the automatic review run, and what bounds its spend

Type: grilling
Mode: HITL
Status: closed
Assignee: captain
Blocked by: -

## Question

The routing **rule** is decided: severity, fail-closed, plus a path escalation so anything touching
`harness/`, `gate/` or `fork/` always reaches the captain regardless of what the reviewer said.
`gate/review.py`'s `blocking` mode already implements the severity half, where any finding not
explicitly tagged `warning` or `info` exits 2 and an untagged finding blocks.

What is **not** decided is the trigger point, and it is a spend decision as much as a design one.

The measured cost, from `gate/review.py`'s own record (corrected at close; this line first read "30
to 120 seconds", which the record does not support): across 115 timed runs a review takes a median
136 s, p90 316 s, max 443 s, and only 41% finish at or under 120 s. The timeout has been raised
twice to 900 seconds after real diffs blew through 300 and 420. Each run is a `claude -p`
invocation that records `total_cost_usd`, median $0.89 across the 109 runs that carry one. With crew building in parallel across many
projects, the trigger point is a recurring bill that scales with how many crewmates are working.

The candidates:

- **Per push**, which is where the gate already sits. Cheapest, and it batches a crewmate's whole
  branch into one review. The cost is that a crewmate can be many changes down a wrong road before
  anything says so.
- **Per crewmate completion**, so each finished objective is reviewed once before the first mate
  reports it done. This matches `/firstmate`'s third hard rule, that a claim of done is a claim and
  not a result, and it is the natural place to intercept.
- **Per change**, the tightest loop and the most expensive by a wide margin.

Also open, and part of the same decision:

- Does the captain set a spend ceiling per session or per day, and what happens at the ceiling:
  fall back to advisory, queue, or stop?
- Does a crewmate's own report substitute for a review on low-risk paths, or is the review the only
  thing that clears a diff?
- `blocking` mode exits 3 when a review could not run. On the gate that is ERROR and correct. In the
  crew loop, does a review that could not run block the crewmate or pass it to the captain?

**Resolved when** the trigger point is named, the spend bound is named, and the could-not-run branch
is named. `/paid-run-protocol` before measuring anything here rather than reasoning about it.

## Resolution

Resolved 2026-08-05 by grilling, four rounds. Eleven questions, all answered by the captain.

### What the record actually said

The Question's original cost line read "30 to 120 seconds" and was wrong; it is corrected above.
Measured across the 119 records in `gate/runs/*-review.json` as of this close: 115 timed runs, of
which 41% finish at or under 120 s, median 136 s, p90 316 s, max 443 s. 109 runs carry a
`total_cost_usd`, median $0.89, p90 $2.08, max $4.15, $121.47 cumulative.

Three findings changed the shape of the decision:

1. **Blocking is not a rare event.** The 110 reviews that reached the model produced 27 `error`,
   99 `warning` and 72 `info` findings. 22 of the 110 carried at least one finding that is not
   warning or info, so `blocking` mode would have refused **20% of the captain's own pushes**
   ([gate/review.py:262](../../../gate/review.py)).
2. **A dollar ceiling cannot be summed from the records.** A timed-out review returns code `None`,
   lands in the nonzero branch at [gate/review.py:237](../../../gate/review.py), and records no
   `total_cost_usd` at all, because that number exists only in a wrapper reply that never arrived.
   Any ceiling built on the sum undercounts precisely the most expensive runs.
3. **The path escalation fires on the majority of healbot work and on none of any other project's.**
   Of the last 60 commits at close, 33 touch `harness/`, `gate/` or `fork/` (`harness/` alone is 25).
   A narrower alternative was tried and was worse: `.carryover/verified/` alone is 35 of 60.

A fourth correction arrived from `/paid-run-protocol`: `total_cost_usd` is a Claude-subscription
valuation, not a metered bill. The figures above bound usage, not an invoice.

### The decisions

- **Trigger: per crewmate completion, in `blocking` mode.** Chosen over per-push because crew do not
  push: a slot is a detached worktree and the first mate merges, so under a per-push trigger crew
  work is reviewed only at the captain's merge, batched and hours late. The pre-push review stays
  exactly as it is, **advisory**, guarding the captain's own direct commits. Two triggers, two modes,
  no diff reviewed twice.
- **The trigger is wired into `hb-fleet.sh` on the slot-return path, not written as a skill rule.**
  A rule in `harness/skills/firstmate.md` is a model remembering an instruction, which is the
  arrangement the gate was built to replace: `gate/hooks/pre-push` says in its own header that the
  fork drift check sat silently red because nothing ran it. The review becomes a precondition of the
  verb the first mate must run anyway.
- **Spend is bounded structurally, with no dollar ceiling.** One review per completion **attempt**,
  never per change, with a **hard cap of three attempts per objective**; at the cap the objective
  goes to the captain as unresolvable rather than looping. The bound is stated per attempt rather
  than per objective because one-per-objective and the block-fix-recheck loop contradict: either the
  fix is reviewed, or the fix is the one diff that ships unreviewed. Every answer to "what happens at
  the ceiling" was rejected: advisory-fallback drops the bar silently at peak load, stop freezes the
  crew, queue hands the captain a pile.
- **The diff-size cap refuses instead of truncating, at the blocking trigger only.**
  [gate/review.py:54](../../../gate/review.py) sets `MAX_DIFF_BYTES = 200_000` and truncates,
  naming the drop in the record. That stays for the advisory push review, where a partial opinion
  costs nothing. At the completion trigger it becomes ERROR, because with no substitution permitted
  a blocking verdict on a half-read diff is the one place a partial read becomes a full clearance.
- **The could-not-run branch: one conditional retry, then the captain, and the crewmate never
  reports done.** The three `Not logged in` records are stale, all 2026-07-31, before the harness
  root login, with 109 successful runs since. The branch is not stale: exit 3 also fires on timeout
  ([gate/review.py:237](../../../gate/review.py)), on a malformed reply
  ([gate/review.py:254](../../../gate/review.py)), on a missing CLI
  ([gate/review.py:219](../../../gate/review.py)) and on any crash, a measured 2.6% of runs with
  everything healthy. Retry once **only when the cause was not a timeout**: a timeout is
  diff-size-driven and a retry of the same diff times out again at full cost, so a timeout is really
  the diff-size refusal arriving late and goes straight to the captain. The outcome is named
  **unmeasured** and is distinct from **blocked**, because "a reviewer said no" and "nothing measured
  this" need different reactions, and conflating them is how an unmeasured claim reads as a cleared
  one.
- **No substitution, on any path, ever.** A crewmate's own report never stands in for a review. The
  trigger exists because a claim of done is a claim.
- **The path escalation is kept and narrowed to what can make the measurement lie:** `gate/`,
  `fork/`, and `.carryover/verified/probe_*`. Plain `harness/` is dropped. It lives **inside
  `review.py`**, recorded as a field on the run record rather than expressed as an exit code, so both
  triggers read one implementation and the record stays authoritative. It is a healbot-repo rule:
  in any other project those paths do not exist and severity is the whole bar.
- **Usage is reported, never gated, in the first mate's turn-ending state report.** That is the only
  surface that already fires while crew are live (firstmate hard rule 4); `/orient` is read at
  session start when the figure is always zero. The report must carry the timeout undercount from
  finding 2 so the number is not read as exact.

### Requirements this hands to ticket 13

Two, both measured here rather than left to be discovered:

1. **A third collect mode.** [harness/pool.py:119](../../../harness/pool.py) states that slot work
   exists in two forms and every guard needs both: uncommitted changes, and commits on the detached
   HEAD that leave `git status` clean. [gate/review.py:102](../../../gate/review.py) has only
   `base...head` and working-tree. A completion review run with no base against a crewmate that
   committed reviews an **empty diff and passes**, which is run 20260802-184854 repeated one level
   down. The completion review passes the slot's recorded baseline sha as `--base` and reviews
   baseline...HEAD plus whatever is uncommitted on top.
2. **It runs the slot's own copy.** `ROOT` is `__file__`-derived
   ([gate/review.py:41](../../../gate/review.py)), so the main checkout's `review.py` reviews the
   main checkout however the refs are aimed.

### The paid check

The completion trigger puts a review under `CLAUDE_CONFIG_DIR = harness/claude`
([harness/env.claude.sh:94](../../../harness/env.claude.sh)) for the first time; every one of the
115 records came from the pre-push hook under the default root, and
[harness/hb-fleet.sh:69](../../../harness/hb-fleet.sh) already flags that this root needs its own
auth. Authorized by the captain and run 2026-08-05 by the crew path exactly
([harness/hb-fleet.sh:118](../../../harness/hb-fleet.sh)), against the smallest recent commit.

**TESTED, record `gate/runs/20260805-204306-48726-review.json`:** `state: pass`, `claude_code: 0`,
`subtype: success`, 11 turns, 61.6 s, 878-byte diff. The crew config root authenticates a review.

The run also refuted the estimate that justified it. It was costed at $0.20 to $0.30 on the
reasoning that an 878-byte diff is a small one; it valued at **$0.94**, within pennies of the $0.89
median. Cost does not scale with diff size, because the reviewer reads the tree under
`--allowedTools Read Glob Grep` and spent 11 turns doing so on a one-file change. **The bound is
reviews multiplied by roughly one dollar, flat.** Worst case per objective under the three-attempt
cap is therefore about $2.80, and the diff-size refusal is a correctness measure rather than a
cost measure.

### Left open deliberately

Whether those 27 `error` findings were ever right is unmeasured, and `blocking` is fail-closed on a
severity string the reviewer assigns to its own finding. Spun out as ticket 16 and made a
prerequisite to switching blocking on anywhere.
