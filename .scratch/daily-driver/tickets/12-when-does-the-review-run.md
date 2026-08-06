# When does the automatic review run, and what bounds its spend

Type: grilling
Mode: HITL
Status: open
Assignee: -
Blocked by: -

## Question

The routing **rule** is decided: severity, fail-closed, plus a path escalation so anything touching
`harness/`, `gate/` or `fork/` always reaches the captain regardless of what the reviewer said.
`gate/review.py`'s `blocking` mode already implements the severity half, where any finding not
explicitly tagged `warning` or `info` exits 2 and an untagged finding blocks.

What is **not** decided is the trigger point, and it is a spend decision as much as a design one.

The measured cost, from `gate/review.py`'s own record: a review runs 30 to 120 seconds, the timeout
has been raised twice to 900 seconds after real diffs blew through 300 and 420, and each run is a
`claude -p` invocation that records `total_cost_usd`. With crew building in parallel across many
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
