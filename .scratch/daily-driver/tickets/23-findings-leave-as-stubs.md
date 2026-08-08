# A non-blocking finding leaves as a proposed stub, not as a repair commit

Type: task
Mode: AFK
Status: open
Assignee: -
Blocked by: 22

## Question

[A push declares what it closes](22-a-push-declares-what-it-closes.md) stops a `warning` or `info`
finding from obligating a repair commit. This ticket decides where it goes instead, because the
answer cannot be "nowhere": the `gate/runs/` rule in `.gitignore` keeps the record untracked and
nothing reads it
(`gate/publish.py:154` is the only reader, and it only attaches the newest one as a comment). A
finding dropped from the obligation set with no destination is a finding deleted.

Over the window that is 44 warning/info findings on repair pushes alone, and more if
[does the path escalation apply to a push that only closes findings](21-escalation-on-a-closing-push.md)
drops the escalation rule as well.

Captain's ruling 2026-08-08: **proposed ticket stubs, promoted by firstmate.**

## Why not a ledger, and why not the tracker directly

A tracked ledger file was the obvious build and is wrong twice. It becomes knowledge store #8 in a
repo already carrying seven, and it does the tracker's job in a second format — the frontier query
would not see it, so a finding parked there is invisible to the one command that answers "what is
takeable".

Writing straight into `.scratch/<effort>/tickets/` is wrong for a sharper reason: **the ratified
crew contract makes firstmate the ONLY tracker writer.** That rule lives in
`harness/skills/firstmate.md` under "Working a wayfinder map" and was ratified by
[ratify the wayfinder and firstmate contract](03-wayfinder-firstmate-contract.md). It is close to
forced rather than stylistic: a pool slot is a detached worktree, so every crewmate holds a
divergent copy of `.scratch/`. A gate stage that wrote tickets would be a second writer with a
divergent copy, which is the failure the contract exists to prevent.

The precedent is already set one ticket over.
[Six documents carry a "Still open" section](20-the-still-open-sections-are-never-re-checked.md)
asked the same question about a different artifact — should a forward-looking claim live in prose
or in the tracker — and its option 2 is that open items belong in `.scratch/*/tickets/` because
that is what the repo does everywhere else. Same answer, same reason.

## What to build

The checkout stage writes a stub per non-obligating finding to `.scratch/inbox/`, outside any
effort directory so the frontier query does not see it and no number is claimed. The stub carries
what the finding already has — file, line, severity, summary — plus the review record id and the
pushing commit, so the promoter can find the diff that produced it.

Firstmate promotes a stub into a real ticket under the effort it belongs to, or deletes it. That
promotion is the human judgement the contract protects, and it is where a stub gets a number, a
`Type`, a `Mode` and a place in the blocking graph.

Two properties to get right rather than discover:

1. **A stub must not be silently lost.** It is written by a hook on a push that succeeded, so
   nothing is watching. If `.scratch/inbox/` is unwritable the checkout stage says so on stderr in
   the `unmeasured` voice rather than continuing quietly — a stage that stopped working must never
   read like a clean one. The prose stage in `gate/hooks/pre-push` had exactly that collapse: its
   old form piped the checker's stderr into `grep` and ended in `|| true`, so a crashed checker
   printed the stage header and nothing else, and an ERROR rendered as a clean PASS. The comment
   above that stage's `plainspec-check` call carries the history. (Cited by stage rather than by
   line: the hook is extensionless, so it is out of the sweep's reach the same way `.gitignore`
   is.)
2. **A stub is not a claim that the finding is real.** Ticket 16 measured 7 of 25 error findings
   unacted, six of them factually correct. The inbox is a queue of things a reviewer said, and
   promotion is where somebody decides.

## Done looks like

A push with a `warning` finding writes exactly one stub, the push succeeds, the frontier query is
unchanged, and firstmate can promote that stub into a numbered ticket that the frontier then does
see. TESTED in both directions: an unwritable inbox produces a loud `unmeasured` line and not a
silent pass.
