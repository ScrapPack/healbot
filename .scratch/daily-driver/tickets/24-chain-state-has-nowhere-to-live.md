# Chain state has nowhere to live, so the attempt cap cannot count

Type: task
Mode: AFK
Status: open
Assignee: -
Blocked by: 22

## Question

[A push declares what it closes](22-a-push-declares-what-it-closes.md) carries an attempt cap, taken
from [when does the automatic review run](12-when-does-the-review-run.md): three attempts, then the
captain. That cap needs to know which attempt this is. **Nothing in the push exit can answer that
question today**, and the ticket that names the cap does not solve it.

The reason is the same one that makes the whole store write-only. The `gate/runs/` rule in
`.gitignore` keeps every record untracked, so:

- a fresh clone has no history at all and every chain looks like attempt one;
- a pool slot is a detached worktree with its own empty `gate/runs/`, so a crewmate cannot see the
  attempts the main checkout recorded, and vice versa;
- the records are the only place a chain's prior attempts exist, and `gate/review.py` never reads
  them back (`gate/review.py:45`, `gate/review.py:285`, `gate/review.py:286` are define, mkdir,
  write).

So a cap implemented by counting records is a cap that counts to one forever in exactly the
environment the fleet runs in. That is worse than no cap: it reads as enforcement and enforces
nothing.

## What to decide

Where chain state lives, given that it must survive a worktree boundary and a fresh clone.

1. **In the commits themselves.** The `Review-chain:` trailer already names the review being
   closed. Attempt number is then a `git log` over commits carrying the same chain id, which needs
   no store at all and is correct across every worktree because the commits are the shared object.
   Cheapest, and it inherits git's own durability.
2. **A tracked ledger.** Rejected once already in
   [a non-blocking finding leaves as a proposed stub](23-findings-leave-as-stubs.md), for reasons
   that apply here unchanged.
3. **Accept no cap.** Defensible if the discharge rate is high enough that chains die on their own.
   The measured rates argue both ways: error-grade-only discharges 88% of repair pushes, so a cap
   would rarely bind, which is an argument for skipping it AND an argument that it is cheap.

(1) is the obvious answer and this ticket exists to confirm it rather than to discover it. The
trap worth naming before somebody hits it: a chain id derived from a review record timestamp is
only meaningful on the machine that produced the record. If the trailer is going to be the store,
the id has to be resolvable without the record, or the trailer has to carry enough to stand alone.

## Done looks like

A push that is the third closing attempt on one chain is identified as such from a fresh clone,
with no `gate/runs/` present. TESTED with the control in the other direction: the first closing
attempt on the same chain reports attempt one from the same clone.
