# Clear the PC's commits of RAM-corruption risk

Type: task
Mode: HITL
Status: open
Assignee: -
Blocked by: -

## Question

The PC is being retired for a RAM fault and instability, reported by the captain 2026-08-05. Work
committed from that machine has to be investigated and cleared before it is trusted, because
unstable memory can corrupt content silently rather than loudly.

**The exposure is exactly three commits**, identifiable by committer: `eee2e4b`, `eb72fad`, and the
merge `d9fa44e`, all authored `ScrapPack <werdellbritton@gmail.com>`, which is also how they are
told apart from this machine's commits under the pinned noreply address. Four files, 121 insertions
and 15 deletions: `probe_citations.py`, `probe_turn_growth.py`, `term.py`, `NEXT.md`.

## Evidence gathered 2026-08-05, before this ticket existed

- **Object integrity: TESTED clean.** `git fsck --full --strict` exits 0. Only dangling commits,
  trees and blobs, which are ordinary rebase and amend residue. Every reachable object's content
  hashes to its own name, so nothing was corrupted after it was written.
- **Behavior: TESTED clean.** The whole free suite exits 0, including the three probes that own the
  touched files: `probe_citations.py` 21/21, `probe_turn_growth.py` 20/20, and
  `probe_rig_contract.py` 40/40, which reads all 24 rig entrypoints as source.
- **The merge was already gate-verified on this machine after the fact.** `NEXT.md` records gate
  PASS over `fda7d64..d9fa44e` with the run record under `gate/runs/`. That matters because the push
  that landed it was `--no-verify`.
- **Content coherence: VERIFIED by reading the entire diff.** All 121 lines. Every change is a
  deliberate, commented, POSIX-no-op-by-construction edit that names its Windows measurement: the
  `normpath` on `CHECKOUT` and the `rel_posix()` helper, `node -` over stdin instead of `-e` against
  the 32,767-character Windows command-line cap, and the conditional pty import that moves
  enforcement from import time to `Term()`. Corruption produces nonsense or syntax errors, not
  coherent prose with citations.

## What no check can exclude

A bit flip that happened **in memory before the content was hashed** would produce an object that
is internally consistent, passes `fsck`, and could in principle pass the probes while being
semantically wrong. No integrity check can rule that out, because git faithfully recorded whatever
was in RAM.

The mitigation is that the diff is 121 lines and has now been read in full by a human-directed pass,
and that all three touched files are covered by probes with mutation controls. The residual is the
part of those files the probes do not assert on.

**Deciding to accept that residual is the captain's call, not the agent's**, which is why this
ticket is left open with a recommendation rather than closed.

**Recommendation: clear them.** The evidence is as strong as it can get short of rewriting the work,
and the alternative, reverting and redoing three commits of correct platform fixes, costs real work
to chase a risk with no positive indication behind it.

## Also worth one decision, unrelated to corruption

Those three commits carry `werdellbritton@gmail.com` rather than the pinned noreply address, so the
noreply pinning never reached the PC. The owner already accepted personal-email exposure in this
public repo's history, so this is not a new decision, only three more commits under the accepted one.
Recorded so it is not re-discovered as a finding.
