# gate/ — the per-change gate

The layer between "the agent says it is done" and a phase review. Free, ~1.1s, and it runs
whether or not anybody remembers to run it.

    .carryover/verified/venv/bin/python gate/gate.py            # working tree
    .carryover/verified/venv/bin/python gate/gate.py --base main
    .carryover/verified/venv/bin/python gate/gate.py --quiet    # verdict lines only

Exit codes are the interface: **0 pass · 2 blocked · 3 error**. TESTED 2026-07-31 — a banned
filename and a lint error each produced 2, a clean tree produced 0.

## Behaviour → file

| Behaviour | Where |
|---|---|
| Everything | `gate/gate.py` — one file, no dependencies beyond the rig venv |
| Which checks are Tier 1 | `gate.py` `TIER1` |
| Lint scoping | `gate.py` `lint()` |
| The four banned filenames | `gate.py` `BANNED` / `banned_names()` |
| Evidence records | `gate/runs/<timestamp>.json`, gitignored |

## What it checks

**Tier 1 — static, free, always on** (~0.7s): `probe_rig_contract` (every rig still reports
failure as failure), `probe_citations` (~930 `file:line` citations still resolve),
`probe_twin` (the `fork/` overlay and the `opencode/` checkout have not drifted).

**Lint — scoped to the changed files:** `ruff` on changed Python; `tsgo --noEmit` on the TUI
project only when the change touches `fork/` TypeScript. Repo-wide lint on a mixed tree reports
findings the change did not cause, and a gate that blames you for someone else's lint is a gate
you route around.

**Invariants:** the `AGENTS.md` / `CLAUDE.md` / `CONTEXT.md` / `SKILL.md` filename ban
(`HARNESS.md:9-13`). It held for twelve phases on memory alone; now it is a check.

## What it deliberately does NOT run

- **Tier 2** — the eight free probes that boot a TUI or a server. Free, but tens of seconds, and
  their output embeds timings. Run them at phase boundaries.
- **Tier 3** — every `verify_*` rig. **PAID.** Owner's go, never automatic.

## Three decisions worth not re-litigating

**No worktree, and that is deliberate.** The obvious move is to copy the tree somewhere isolated
first, which is what the external `gated-harness` plugin does (its run worktree is cut at HEAD).
It is wrong here: this repo gitignores `/opencode/`, `node_modules/` and
`.carryover/verified/venv/`, so a healbot worktree contains no checkout, no deps and no venv —
it cannot resolve one `file:line` citation or run one probe. Tier 1 is a pure read of the working
tree and the working tree is the thing being guarded. Isolation becomes necessary at Tier 3,
where a rig boots a real server.

**The evidence hash is over RAW output, because determinism was measured.** TESTED 2026-07-31,
3 runs each on an unchanged tree: all three Tier-1 probes were byte-identical *before* any
canonicalization. That is why there is no tolerance machinery here. Adding a check whose output
embeds a time, a temp path, or a filesystem-ordered count is the change that starts this lying —
re-measure first.

**`error` is not `blocked`, and neither is `pass`.** A check that could not run has left its
claim unmeasured; a check that ran and said no is a finding for a human. Collapsing them is how
a suite reports green for a run that died — this project has that exact defect on record in
`docs/CLONE.md` (three probes exited 0 having proven nothing) and `docs/VERDICT.md` (six paid
rigs printed a verdict and threw it away). The typed-state vocabulary is borrowed from
`gated-harness`; its isolation model is not.

## Why it exists

`docs/REVIEW.md` is 15 agents and 1,047 tool calls; `docs/HARDEN.md` is 67 agents. That review
discipline is real, but it is phase-level and hand-driven, and every gate in `NEXT.md` is a
command somebody has to remember. `fork/README.md` prescribes its drift check the same way —
and MEASURED on 2026-07-31, that check had been silently **red**: three `.DS_Store` files from a
Finder visit had taken the overlay from its declared 17 files to 20. Nothing was running it.
That is the gap this fills.

## Open

- Tier 2 is defined but not wired. It needs a phase-boundary trigger, not a per-change one.
- No PR integration yet. The remote is `ScrapPack/healbot` and `gh` is authed with `repo` +
  `workflow`; a run record is the natural `gh pr comment` payload.
- No CI. `.github/` does not exist, and adding it changes what "PR" means for the worktree and
  skills work — a decision, not an oversight.
