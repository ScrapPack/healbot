# gate/ — the per-change gate

The layer between "the agent says it is done" and a phase review. Free, ~1.1s, and since
2026-07-31 it is the push path: `gate/hooks/pre-push` refuses any push whose commits do not
pass, so it runs whether or not anybody remembers to run it. The hook is versioned; the
wiring is one line of per-clone config (hooks themselves are not versioned by git):

    git config core.hooksPath gate/hooks                        # install the push gate, once
    .carryover/verified/venv/bin/python gate/gate.py            # working tree, by hand
    .carryover/verified/venv/bin/python gate/gate.py --base main
    .carryover/verified/venv/bin/python gate/gate.py --quiet    # verdict lines only

`git push --no-verify` is the deliberate escape hatch; using it ships unverified commits,
so say so wherever the push is discussed.

Exit codes are the interface: **0 pass · 2 blocked · 3 error**. TESTED 2026-07-31 — a banned
filename and a lint error each produced 2, a clean tree produced 0. `tier2.py` adds one more
verdict on the same scale: **`declared-skip` also exits 0** — it is a pass whose record names
the checks this machine could not measure (see Tier 2 below).

The probes speak the same lattice from below since 2026-08-03 (docs/E2E.md item D): a probe
that exits **3** has DECLARED cannot-measure — it started, found the input it names absent
(the missing `opencode/` checkout is the live case), and refused to claim a measurement — and
its row is ERROR, so the gate exits 3, matching the gloss above. Every other nonzero probe
exit stays BLOCKED, crashes included: a broken probe must not downgrade a finding to
retry-shaped. Both directions TESTED through the real hook (`probe_gate_scope.py`'s sentinel
legs). The hook refuses either way; the difference is what the record and the refusal say.

## Behaviour → file

| Behaviour | Where |
|---|---|
| Everything | `gate/gate.py` — one file, no dependencies beyond the rig venv |
| Which checks are Tier 1 | `gate.py` `TIER1` |
| Lint scoping | `gate.py` `lint()` |
| The four banned filenames | `gate.py` `BANNED` / `banned_names()` |
| Push enforcement | `gate/hooks/pre-push` — gates the exact pushed range via `--base <remote sha> --head <pushed sha>`, refuses on exit 2/3; a wholly absent rig venv (fresh clone/worktree) refuses up front by name, with the reconstitution remedy; deletion-only pushes are exempt (nothing to gate) |
| Model review stage | `gate/review.py` — single-pass fresh-context review, typed findings, advisory by default |
| Evidence flow | `gate/publish.py` — attaches both run records to the pushed commit (or its open PR) on GitHub |
| Tier 2 runner | `gate/tier2.py` — the rest of the free suite, at phase boundaries; trigger is the phase-close skill (`harness/skills/phase-close.md`) |
| Environment requirements | `rig.py` `Env` / `Results.check(needs=)` — a check names the machine fact it needs; `tier2.py` `parse_skips()` lifts the declarations into the run record |
| Evidence records | `gate/runs/<timestamp>.json`, `-review.json`, `-publish.json`, `-tier2.json`, plus `publish.log`; all gitignored |

## What it checks

**Tier 1 — static, free, always on** (~0.7s): `probe_rig_contract` (every rig still reports
failure as failure), `probe_citations` (every `file:line` citation still resolves),
`probe_twin` (the `fork/` overlay and the `opencode/` checkout have not drifted),
`probe_review_parse` (the review stage's reply parser still holds all three live-failure
shapes).

**Lint — scoped to the changed files:** `ruff` on changed Python; `tsgo --noEmit` plus
`oxlint` on the checkout twins only when the change touches `fork/` TypeScript (since the
2026-07-31 NEXT.md freeze this gate is the build gates' only owner). On a hook run the scope
is the exact pushed range (`--base <remote sha> --head <pushed sha>`) and ruff lints the
blobs at the pushed tip, never the working tree: the checkout the hook runs in can sit on
another branch and hold none of the pushed files. Run `20260802-184854` is the incident
this closed — a merge push bringing 800+ new lines gated as "0 changed file(s)" because
the range ended at that checkout's HEAD, and every change-scoped linter skipped. Repo-wide lint on a mixed tree reports
findings the change did not cause, and a gate that blames you for someone else's lint is a gate
you route around.

**Invariants:** the `AGENTS.md` / `CLAUDE.md` / `CONTEXT.md` / `SKILL.md` filename ban
(`HARNESS.md:9-13`). It held for twelve phases on memory alone; now it is a check.

## The model review stage

`gate/review.py`, run by the pre-push hook after the deterministic checks pass. Every gate.py
check is static, so a change that lints clean and breaks logic passes untouched; this is the
missing judgment layer, shaped like no-mistakes' reviewer: ONE reviewer, fresh context per
change-set, single pass, typed findings (severity error/warning/info, action
no-op/auto-fix/ask-user, risk low/medium/high). Multi-reviewer adversarial review stays at
phase boundaries, deliberately.

It is NOT a Tier-1 check and must never become one: model output is nondeterministic, so its
record (`gate/runs/<ts>-review.json`) is a log of what one review said, not a re-runnable
measurement, and carries no byte-stability claim. The reviewer is read-only by construction
(`claude -p` with `--allowedTools Read,Glob,Grep`).

Modes via `HEALBOT_REVIEW`: `advisory` (default — findings print and record, push continues
regardless), `blocking` (fail-closed on severity: any finding not explicitly tagged warning
or info refuses the push, exit 2 — "error", "critical", and untagged findings all count; a
review that could not run refuses, exit 3), `off`. Advisory-first is deliberate: quality
feedback must reach the loop; blocking is a separate decision to opt into.

Spend: each review is one `claude -p` call, ~1-7 min of Claude-subscription usage per push
(capped by `HEALBOT_REVIEW_TIMEOUT`, default 900 s after a 1,298-line diff outran the old
420 — a timeout records ERROR with no findings, so the cap should stay above what the diff
honestly needs; the record stores the CLI's own `total_cost_usd`). This is standing spend the owner
accepted by wiring the hook; `HEALBOT_REVIEW=off` revokes it at any time. It is not the
metered openai/API credit spend that the paid-run-protocol skill's ask-first rule governs.

## What it deliberately does NOT run

- **Tier 2** — the rest of the free suite: `probe_*.py` minus Tier 1, discovered by
  subtraction at run time (floor-guarded in `tier2.py`;
  `gate/tier2.py --list` enumerates). Free, but minutes not seconds, and the output embeds
  timings, so no byte-stability claim and no per-row hash — deliberately. Run
  `gate/tier2.py` at phase boundaries; the phase-close skill is the trigger and owns the
  known-red register. Record: `gate/runs/<ts>-tier2.json`; a
  discovery floor makes "found no probes" ERROR instead of a quiet green.

### Tier 2 from a pool slot: declared environment skips

MEASURED 2026-08-01 from a worktree slot: four probes red, none of them a defect. A symlink
`env.claude.sh` materializes at source time and `git worktree add` never runs; an installed
skill under `~/.agents/` owned by whichever checkout last synced it; a transcript corpus
chosen by `CLAUDE_CONFIG_DIR`; session rows keyed to the main checkout's absolute path. The
run said BLOCKED for four things a slot cannot fix and — per the crew constraints — must not
try to. Misleading rather than wrong, which is worse: it is the reading that teaches people
to skim reds.

The mechanism is `rig.Env`. A check declares the machine fact it depends on
(`r.check(name, lambda: ..., needs=MAIN_CHECKOUT)`); when the fact is absent the row records
a **declared skip** carrying the requirement's name and reason, and `tier2.py` lifts every
declaration out of the probe's stdout into `declared_skips` in the run record and prints them
in full under the verdict. The tier's verdict becomes **`declared-skip`** — exit 0, green, and
explicit that not everything here was measured.

Four rules keep it from being a mute button, and all four are asserted by
`probe_rig_contract` (contract 7, eleven rows, both polarities):

- The predicate must be a **lambda**. Python evaluates arguments eagerly, so an expression
  predicate has already run — and already crashed — before `needs=` can decide anything.
  Caught statically by the sweep and at run time by a `TypeError`.
- Skips are **budgeted per rig** (`Results(skip_max=N)`, default 0). Skipping past the budget
  is RED, so the skip surface cannot widen without somebody raising a number on purpose.
- A run where **nothing was measured** is RED whatever the budget allows.
- A requirement must be **strictly weaker than the check it guards**, or the guard has
  replaced the measurement. `probe_backend`'s is the worked example: the requirement is "some
  corpus directory carries a doubled dash", the check is "the `--claude-worktrees-` ones are
  there" — so a corpus with other dotted paths still runs the row, and can still go red.

**A requirement that does not hold where it should is a finding, and the merge-back check is
per requirement, not per verdict.** Every `rig.Env` carries its own reason string: read that
and ask where the requirement MUST hold, rather than working from a list here that goes stale
as requirements are added. A checkout-scoped one must hold in the main checkout —
`main-checkout` by definition, and `claude-config-materialized` because `env.claude.sh` has
been sourced there (VERIFIED 2026-08-01) — so a skip there is a defect, not a status. A
requirement that turns on the SHELL is not, and saying otherwise would be the same over-claim
this mechanism exists to remove: `corpus-dotted-path` reads whichever corpus
`CLAUDE_CONFIG_DIR` selects, so from a plain shell it resolves to `~/.claude/projects` and the
row runs, and from a shell that has sourced `env.claude.sh` it resolves to
`harness/claude/projects`, which holds no dotted path, and the row skips — in the main checkout
too (MEASURED 2026-08-01, both directions). The honest reading of a main-checkout run is
therefore `pass` from a plain shell and `declared-skip` naming exactly that one requirement
from a harness shell; anything else is worth opening the record for.
- **Tier 3** — every `verify_*` rig. **PAID.** Owner's go, never automatic.

## Three decisions worth not re-litigating

`gate/gate.py`'s module docstring and its typed-state constants own the reasoning. This is the
index, because other documents point here by name:

- **No worktree, and that is deliberate.** This repo gitignores `/opencode/`, `node_modules/`
  and `.carryover/verified/venv/`, so a healbot worktree contains no checkout, no deps and no
  venv — it cannot resolve one `file:line` citation or run one probe. Tier 1 is a pure read of
  the working tree and the working tree is the thing being guarded. Isolation becomes necessary
  at Tier 3, where a rig boots a real server.
- **The evidence hash is over RAW output, because determinism was measured.** TESTED
  2026-07-31, 3 runs each on an unchanged tree: every Tier-1 probe was byte-identical before
  any canonicalization. That is why there is no tolerance machinery here. Adding a check whose
  output embeds a time, a temp path, or a filesystem-ordered count is the change that starts
  this lying — re-measure first.
- **`error` is not `blocked`, and neither is `pass`** — and `declared-skip` is none of the
  three. A check that could not run has left its claim unmeasured; a check that ran and said no
  is a finding for a human; a check that found the machine missing a fact it had named in
  advance declined to claim a measurement it could not take. Collapsing them is how a suite
  reports green for a run that died — this project has that exact defect on record in
  `docs/CLONE.md` (three probes exited 0 having proven nothing) and `docs/VERDICT.md` (six paid
  rigs printed a verdict and threw it away). A run that measured 30 of 33 things must not
  report identically to one that measured 33, and the record says which three.

## Why it exists

`gate/gate.py:7-9` owns this, including the MEASURED 2026-07-31 `.DS_Store` trap that is the
worked case: a prescribed drift check that had been silently red because nothing ran it.

## The evidence flow

`gate/publish.py`, spawned detached by the hook after both stages pass. It waits for the
pushed sha to appear on the remote (a failed push never produces it; bounded retries, then a
gave-up record), then posts a markdown summary plus both run records — bulky raw fields
stripped, each full local record pinned by its sha256 — as a COMMIT COMMENT on the pushed
sha, or to `gh pr comment` when the pushed branch has an open PR. Every outcome lands in
`gate/runs/<ts>-publish.json` and `publish.log` (prune the log by hand; nothing reads it).

The auditable property is the point: only the hook runs the publisher, and `--no-verify`
skips the hook, so **a pushed commit with no evidence comment is a commit that shipped
unverified**. Absence is a signal. `HEALBOT_PUBLISH=off` turns publishing off deliberately —
which, per the same property, reads identically to `--no-verify` from the GitHub side.

## Open

- No CI. `.github/` does not exist, and adding it changes what "PR" means for the worktree and
  skills work — a decision, not an oversight. A fresh CI clone also cannot run Tier 1 at all
  (no checkout, no venv), so CI could only ever be ruff + banned-names, honestly labeled.
