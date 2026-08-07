# The harness config root symlinks into the default config root

Type: task
Mode: AFK
Status: open
Assignee: -
Blocked by: -

## Question

`harness/claude/skills/context-handoff` is a symlink to `~/.claude/skills/context-handoff`. That is
a link from the harness config root directly into the DEFAULT config root, which is the thing
[ticket 10](10-mirror-skills-into-harness-root.md)'s resolution records as rejected, in those
words: a symlink from `harness/claude/skills` to `~/.claude/skills` punctures the isolation
silently, which is the exact failure mode this repo exists to hunt.

VERIFIED on disk 2026-08-05. All 28 entries under `harness/claude/skills/` are symlinks, because
`mirror_harness_root()` calls `surface()`, which prefers a symlink and falls back to a copy only
where a symlink cannot exist. Most point at `~/.agents/skills/<name>`, a canonical source outside
both roots, which is defensible and is not what this ticket is about. `context-handoff` is
different: it exists only under `~/.claude/skills`, so the harness root reaches into the default
root to find it. Meanwhile `doctor.py` reports the row PASS at 28/28 "surfaced", so the
puncture is invisible to the check that exists to see it.

## The captain's direction, 2026-08-05

Given at the time this ticket was opened, and it governs the fix:

- **The two systems may LOAD skills differently.** Claude Code and opencode have different
  mechanisms and neither has to change to match the other.
- **The same skills must be CONFIGURED in both.** The skill set is the invariant, not the loading
  path. Divergence in what is available is the defect; divergence in how it is reached is not.
- **Capability parity is settled by measurement, not assertion.** Whether the two systems are
  equally capable is an A/B skills question, which is [ticket 08](08-skills-ab-corpus.md)'s
  subject. This ticket must not decide by argument what that ticket exists to measure.

So the target is not "stop symlinking". It is: every skill in the set is reachable from every root
that needs it, without any root reaching into another root.

## What to decide, and it is narrow

For a skill that exists ONLY under `~/.claude/skills` and has no canonical copy outside both roots:

- **Promote it to the canonical source.** Move the body to `~/.agents/skills/<name>/SKILL.md` and
  link both roots at it. Makes the invariant true by construction and matches every other entry.
- **Copy it into the harness root.** Honours ticket 10's "mirror" wording literally, at the cost of
  a body that can drift from the default root's copy with nothing watching.
- **Leave it out of the harness root.** Smallest change, and it makes the skill sets differ, which
  the captain's direction above rules out.

The first is the only one that satisfies both ticket 10's isolation claim and the direction's
parity claim.

## Constraints

- `probe_fleet_claude.py` asserts every twin's installed `SKILL.md` is byte-identical to its repo
  copy, over `harness/skills/*.md`. Nine skills are tracked twins; the other nineteen are not.
  Whatever is built must not quietly widen or narrow that population.
- **`doctor.py`'s row must be able to fail on this.** It currently counts 28 surfaced and calls that
  PASS. A count is not the claim; the claim is that no root reaches into another. TESTED both
  directions, per the ticket 10 precedent that added the row red and green.
- Do not change what `~/.claude/skills` contains as a side effect. The captain's own root is not
  this ticket's to reorganise.

**Done looks like:** no entry under `harness/claude/skills/` resolves into `~/.claude`, the skill
SET is identical across the roots, `doctor.py` fails when either property is violated, and the
whole thing is TESTED both ways.

## Comments

**Repaired and TESTED both directions 2026-08-05 by the overnight AFK loop. No credits spent;
nothing pushed.** `/rig-assertion-discipline` was invoked before the probe rows and
`/citation-hygiene` before the document edit, as this map's Notes require.

**The option built is the first one, which the ticket recommends and which is the only one
that satisfies both the isolation claim and the parity claim.** The body was promoted, not
copied: `~/.agents/skills/context-handoff/SKILL.md` now holds it, sha256
`c22ab54dd91cd07d9a02944f192e17693d622667fd75e03da1a0a429deaef8e8`, byte-identical to the
body that was under `~/.claude`, and both roots are symlinks at it. **On the constraint
"do not change what `~/.claude/skills` contains":** its SET is unchanged, the body it serves
is unchanged byte for byte, and the entry now has the same shape as its 27 siblings, which
were already symlinks into `~/.agents`. What changed is that the entry is a link rather than
the last real directory in that root. If the captain reads the constraint more strictly than
that, the revert is `rm` the link and restore the directory from the body it points at.

**The count was the defect, not just the symlink.** `doctor.py`'s row reported PASS at
"28/28 surfaced" for as long as the puncture existed. A count is not the claim, and no value
the machine could produce would have turned that row red. It now reports faults, computed by
[config_root_skill_faults](../../../harness/doctor.py) at
[doctor.py:503](../../../harness/doctor.py), which takes both roots as arguments so a probe
can drive it over scratch roots that hold a real puncture.

**One thing found while repairing it, which the ticket does not name.** Pointing the harness
root at `~/.claude/skills/context-handoff` after that entry became a link to `~/.agents`
would have satisfied "resolves into `~/.claude`" — the realpath lands in `~/.agents` — while
keeping exactly the coupling the ticket objects to: the harness root would still traverse the
default root and still break if it moved. So the predicate is
[chain_reaches](../../../harness/doctor.py) at [doctor.py:477](../../../harness/doctor.py),
which compares every hop of the symlink chain and not only its end. The probe row that
discriminates the two asserts `chain_reaches` catches it and `resolves_under` does not.

**What was built, in three parts.**

- `doctor.py`: `resolves_under` ([:467](../../../harness/doctor.py)), `chain_reaches`
  ([:477](../../../harness/doctor.py)), `config_root_skill_faults`
  ([:503](../../../harness/doctor.py)), and the row rewritten
  ([:534](../../../harness/doctor.py)) with a FAIL for punctures
  ([:574](../../../harness/doctor.py)) and a FAIL for set divergence in EITHER direction
  ([:579](../../../harness/doctor.py)). Only `missing` was checked before; an entry present
  in the harness root and absent from the default one is the same divergence mirrored.
- `install-skills.py`: `mirror_harness_root` refuses a skill whose body lives inside the
  default root ([install-skills.py:143](../../../harness/install-skills.py)) before it would
  link one, and names the promotion remedy. It refuses and reports rather than deleting the
  entry: dropping it would make the two roots carry different SETS, which the captain's
  direction rules out just as firmly.
- `probe_fleet_claude.py`: nine rows, floor 107 to 116
  ([:122](../../../.carryover/verified/probe_fleet_claude.py), block at
  [:1007](../../../.carryover/verified/probe_fleet_claude.py)). Four drive the shipped
  function over scratch roots holding a puncture, a traversal and a set divergence; one of
  those is the negative control the count-only row never had, asserting that a clean entry of
  the same shape is NOT reported. Three cover the row being a FAIL inside the family
  `root_fail` matches, so it reaches the claude tier rather than being printed. Two cover the
  installer's refusal.

**TESTED, all free, in this order.**

| what | before | after |
|---|---|---|
| `python3 harness/doctor.py` | exit 0, row PASS "28/28 surfaced" with the puncture live | exit 1, FAIL naming `context-handoff`, claude tier NOT YET |
| `python3 harness/doctor.py` after the promotion | — | exit 0, row PASS naming the SET and the isolation |
| `python3 harness/install-skills.py` with the puncture live | — | exit 1, REFUSED on `context-handoff`, 27 others untouched |
| `python3 harness/install-skills.py` after the promotion | — | exit 0, link written straight at `~/.agents` |
| `venv/bin/python probe_fleet_claude.py` | 107/107 exit 0 | 116/116 exit 0 |
| `gate/gate.py` | — | exit 0 at `gate/runs/20260805-234806.json` |

The doctor red was measured on this machine's REAL roots with the defect still on disk, not on
a fixture, which is why the row's evidence string quotes that run.

**What was left, and why.**

- **The twin population is untouched at nine.** `context-handoff` did NOT gain a
  `harness/skills/context-handoff.md`, so `probe_fleet_claude.py`'s byte-identity sweep covers
  the same nine skills it covered before. The Constraints forbid widening or narrowing that
  population, and promoting a body to `~/.agents` is not the same act as tracking it.
- **`~/.agents/skills/context-handoff/` is now an untracked, unguarded body on this machine.**
  Nothing compares it to anything, exactly like the other nineteen untracked skills the
  harness root surfaces. Whether the tracked-twin population should widen to cover the skills
  the captain actually depends on is a real question and it is not this ticket's.
- **`chain_reaches` reports a symlink loop over 40 hops as reaching.** Deliberate: such a
  chain is broken either way and a human should look at it. It is not reachable from anything
  the installer writes.
