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

Found by the model review of the `7bd4085` push. Worth recording how it was missed: the first mate
noticed the same discrepancy hours earlier, checked ONE entry (`firstmate`, which points at
`~/.agents`), reasoned that per-skill links to a shared canonical source are categorically different
from root-to-root sharing, and closed the question. That reasoning is correct and the sample was
not. The one entry not checked is the one that proves the point.

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
