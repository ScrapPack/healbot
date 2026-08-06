# Ratify the wayfinder and firstmate contract

Type: grilling
Mode: HITL
Status: closed
Assignee: captain
Blocked by: -

## Question

`/wayfinder` and `/firstmate` overlap structurally and the overlap has two conflicts that need
deciding rather than discovering.

The alignment, which is why this is worth doing at all: a wayfinder ticket and a firstmate brief are
the same object, self-contained and sized to one session; the frontier is the spawnable queue;
claiming by assignment is the pool lease one level up; and one-ticket-per-session is one-objective-
per-crewmate.

**Conflict 1: who writes to the tracker.** `/wayfinder` expects concurrent sessions editing it.
`/firstmate`'s second hard rule is that all crew communication flows through the first mate.

Proposed: the first mate is the sole tracker writer. Crewmates report as they do now; the first mate
verifies, writes the resolution, closes the ticket, and appends the map line. The reason is
`/firstmate`'s third hard rule, that a crewmate's claim of done is a claim and not a result, and
wayfinder's close step is exactly where that rule has to intercept. **A crewmate never closes its own
ticket.** Already written into `docs/agents/issue-tracker.md`; this ticket ratifies or overturns it.

**Conflict 2: HITL tickets are not spawnable at all.** `/wayfinder` is explicit that a HITL ticket
resolves only through live exchange and that an agent answering its own grilling questions has broken
it. So grilling and prototype tickets come back to the captain, and only research and AFK task tickets
reach crewmates.

The consequence worth stating plainly: a map does **not** make the fleet more autonomous. It makes the
queue durable and the captain's decisions explicit. If the captain wants autonomy, that is a different
effort.

Open:

- Ratify or overturn both proposals.
- Does claiming get automated, and if so what adopts the claim? A ticket claimed by a session that
  dies stays claimed. The pool already measured this failure and fixed it by having the process that
  outlives the acquire adopt the lease. Reuse that, do not rediscover it.
- Where does the contract live? `harness/skills/firstmate.md` is the canonical half and
  `harness/install-skills.py` syncs the installed twin, so an edit there is the whole change.

## Comments

Blocks ticket 04, which builds the cockpit frontier view, and ticket 08, whose A/B design depends on
what a crewmate is given.

## Resolution

Grilled and ratified by the captain 2026-08-05. All four proposals stand, one of them for a
different reason than it was proposed for.

**1. The first mate is the only tracker writer. A crewmate never closes its own ticket.**
Ratified, and the grilling found it is closer to forced than chosen. `harness/pool.py` provisions
each slot as a DETACHED WORKTREE of the repo, and `.scratch/` is tracked, so a crewmate holds its
own divergent copy of the map and every ticket. A crewmate "writing a resolution" does not write to
the captain's tracker at all; it writes to a copy needing a commit, a gated push and a merge. The
divergence is not a cost, it is the enforcement mechanism, and it lands `/firstmate`'s third hard
rule exactly where the close happens.

**2. The tracker stays in-repo at `.scratch/`.** Moving it outside the repo to a shared location
would make concurrent crewmate writes physically possible, and that is the reason not to. It would
also throw away the original reason for local markdown over GitHub, which is that the gate and the
probe suite can read the tree.

**3. A HITL ticket is never spawned to be resolved, but MAY be spawned to be prepared.** The
boundary is finding facts versus making decisions. `/grilling` mandates the same split upstream:
facts are the agent's job and never the human's, decisions are the human's. This was ratified on
evidence rather than principle, because fact-gathering before the last two grillings changed the
questions materially both times: the skills gap on ticket 01, and the worktree divergence above.
A preparation brief says what to find and forbids recommending an answer.

**4. `Assignee:` records intent; the fleet manifest records liveness.** No pid on a claim line. The
pool measured this one level down, where the lease first recorded the acquiring process, which exits
immediately on every crew spawn, so a live crewmate read as abandoned. A pid in a markdown file
would be a second copy of what the manifest already knows, and the second copy is the one that goes
stale. A stale claim surfaces by cross-referencing the manifest, which is ticket 04's frontier view.

**Where it lives, and why the decision was applied rather than only recorded.** The map's Notes say
plan, do not do, and this is a `grilling` ticket. But the decision itself was *where the contract
lives*, and a contract that exists only inside a closed ticket is read by nobody: agents read
skills. So the rules are now a "Working a wayfinder map" section in `harness/skills/firstmate.md`,
which owns them, and `docs/agents/issue-tracker.md`'s restatement shrank to a pointer. One rule, one
home. `install-skills.py` held the drift as designed, then `--force` recorded the repo-over-installed
direction; twins are 11/11 byte-identical and the doctor exits 0. The contract now reaches every
session in both config roots.

This unblocks tickets 04 and 11, which are the build work. It does not do that work.
