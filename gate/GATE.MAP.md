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
filename and a lint error each produced 2, a clean tree produced 0.

## Behaviour → file

| Behaviour | Where |
|---|---|
| Everything | `gate/gate.py` — one file, no dependencies beyond the rig venv |
| Which checks are Tier 1 | `gate.py` `TIER1` |
| Lint scoping | `gate.py` `lint()` |
| The four banned filenames | `gate.py` `BANNED` / `banned_names()` |
| Push enforcement | `gate/hooks/pre-push` — gates the pushed range via `--base <remote sha>`, refuses on exit 2/3 |
| Model review stage | `gate/review.py` — single-pass fresh-context review, typed findings, advisory by default |
| Evidence flow | `gate/publish.py` — attaches both run records to the pushed commit (or its open PR) on GitHub |
| Evidence records | `gate/runs/<timestamp>.json`, `-review.json`, `-publish.json`, plus `publish.log`; all gitignored |

## What it checks

**Tier 1 — static, free, always on** (~0.7s): `probe_rig_contract` (every rig still reports
failure as failure), `probe_citations` (~930 `file:line` citations still resolve),
`probe_twin` (the `fork/` overlay and the `opencode/` checkout have not drifted),
`probe_review_parse` (the review stage's reply parser still holds all three live-failure
shapes).

**Lint — scoped to the changed files:** `ruff` on changed Python; `tsgo --noEmit` plus
`oxlint` on the checkout twins only when the change touches `fork/` TypeScript (since the
2026-07-31 NEXT.md freeze this gate is the build gates' only owner). Repo-wide lint on a mixed tree reports
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

Spend: each review is one `claude -p` call, ~30-120 s of Claude-subscription usage per push
(the record stores the CLI's own `total_cost_usd`). This is standing spend the owner
accepted by wiring the hook; `HEALBOT_REVIEW=off` revokes it at any time. It is not the
metered openai/API credit spend that the paid-run-protocol skill's ask-first rule governs.

Activation: the reviewer needs a logged-in `claude` CLI. Until one exists it reports ERROR
into the record and the advisory push continues. Verified 2026-07-31: the keychain entry
exists on this machine but is not reachable from a non-interactive child process; one
interactive `claude -p 'reply ok'` from the owner's terminal settles it.

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
3 runs each on an unchanged tree: every Tier-1 probe was byte-identical *before* any
canonicalization (the original three, and `probe_review_parse` re-measured the same way when
it joined the tier). That is why there is no tolerance machinery here. Adding a check whose output
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

- Tier 2 is defined but not wired. It needs a phase-boundary trigger, not a per-change one.
- No CI. `.github/` does not exist, and adding it changes what "PR" means for the worktree and
  skills work — a decision, not an oversight. A fresh CI clone also cannot run Tier 1 at all
  (no checkout, no venv), so CI could only ever be ruff + banned-names, honestly labeled.
