# Issue tracker: local markdown under `.scratch/`

Issues, specs and wayfinder maps for this repo live as tracked markdown files in `.scratch/`.
There is no GitHub Issues usage here and no `glab`/`gh issue` workflow. Do not create GitHub
issues for this repo unless the captain asks for one by name.

Why local rather than GitHub Issues, recorded so it is not re-litigated by accident:

- The gate and the probe suite can read `.scratch/`. They cannot read GitHub. Anything the
  gate is expected to check has to be in the tree.
- The daily-driver workflow runs offline-capable. A tracker behind a network call is a
  tracker that is down when the network is.
- The repo is already public and `NEXT.md` already publishes working state in detail, so
  tracking `.scratch/` exposes nothing new.

## Conventions

- One effort per directory: `.scratch/<effort-slug>/`
- A spec or PRD is `.scratch/<effort-slug>/SPEC.md`
- Implementation issues are `.scratch/<effort-slug>/issues/<NN>-<slug>.md`, numbered from `01`
- Triage state is a `Status:` line in the header block (see `triage-labels.md` for the role
  strings)
- Comments and conversation append to the bottom of the file under a `## Comments` heading

### When a skill says "publish to the issue tracker"

Create a file under `.scratch/<effort-slug>/`, creating the directory if needed.

### When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The captain normally passes the path or the number.

## Wayfinding operations

`/wayfinder` needs to know where the map, its child tickets, blocking and frontier queries
physically live. Markdown has no native issue types, labels, assignees or dependency edges, so
each one is a line in a header block. The header block is the first thing after the H1 and every
key is present on every ticket, `-` when empty. Keys are fixed so the frontier query can be a
command rather than a reading exercise.

### Layout

```
.scratch/<effort-slug>/
├── MAP.md                    the map, one per effort
└── tickets/
    ├── 01-<slug>.md
    └── 02-<slug>.md
```

The map's identity is its path. There is no `wayfinder:map` label because there is nothing to
label: a file named `MAP.md` inside an effort directory is the map.

### The map

`MAP.md` carries the five sections `/wayfinder` specifies: Destination, Notes, Decisions so far,
Not yet specified, Out of scope. Open tickets are deliberately not listed in it. They are found
by the frontier query below, so the map never drifts from the ticket directory.

### A ticket

```markdown
# <ticket title>

Type: grilling
Mode: HITL
Status: open
Assignee: -
Blocked by: -

## Question

<the decision or investigation this ticket resolves>
```

| Key | Values | Means |
|---|---|---|
| `Type` | `research`, `prototype`, `grilling`, `task` | the `wayfinder:<type>` label |
| `Mode` | `HITL`, `AFK` | whether it resolves only through live exchange with the captain |
| `Status` | `open`, `closed` | closing keeps the file in place, it is never moved or deleted |
| `Assignee` | a name, or `-` | **the claim.** `-` is unclaimed |
| `Blocked by` | ticket numbers, comma separated, or `-` | the dependency edge |

**Refer to a ticket by its title, never by its number**, in everything a human reads. The number
is the identity the query uses; the title is what makes a list legible.

### Claiming

Set `Assignee:` before any work, in its own write, so a concurrent session sees the claim before
the work starts. A claim by a session that dies stays claimed. That failure has already been
measured one level down, in the worktree pool, where the fix was to have the process that
outlives the acquire adopt the lease rather than the acquiring process record itself
(`harness/pool.py`, and docs/E2E.md's open item B). Whatever automates claiming here inherits
that lesson rather than rediscovering it.

### Resolving

Append the answer under a `## Resolution` heading, set `Status: closed`, and add one line to the
map's Decisions so far. The ticket holds the detail; the map only gists it and links. A decision
lives in exactly one place.

**When a fleet is working the map, `/firstmate` is the only writer here and a crewmate never
closes its own ticket.** Those rules and their reasons live in the firstmate skill's "Working a
wayfinder map" section, which owns them. This file owns the format. One rule, one home, because a
rule kept in two places goes stale in one of them.

### Blocking and the frontier

A ticket is **unblocked** when every ticket in its `Blocked by` list is `closed`. The
**frontier** is every ticket that is `open`, unblocked, and unassigned.

Markdown has no dependency UI, so the frontier is a command rather than a view. Run it from the
repo root:

```bash
awk -f .scratch/frontier.awk .scratch/*/tickets/*.md | sort
```

`.scratch/frontier.awk` is the **only** place the blocking rule is implemented. Anything that
renders the frontier calls it rather than reimplementing it, because two implementations of one
rule will disagree and the disagreement will be silent. A ticket that looks takeable in the map
and is not takeable here is a map that has drifted, not a query that is wrong.

TESTED 2026-08-05 against `.scratch/daily-driver`, in both directions: the baseline frontier is
five tickets; closing a blocker admits the two it blocked and drops the blocker itself; assigning
a frontier ticket drops it. The controls matter because the first version of this query was
written inline in this document and was **broken** in a way that returned an empty frontier
rather than an error, which is exactly the silent-pass failure this repo exists to hunt.
