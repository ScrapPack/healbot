# Crew workspaces for projects that are not healbot

Type: task
Mode: AFK
Status: open
Assignee: -
Blocked by: -

## Question

healbot is the primary work environment for **all** projects, and the normal shape is crew building in
parallel. Today there is no workspace provisioning for any repo but this one.

VERIFIED: `harness/pool.py` provisions "a full, self-similar healbot tree: a detached worktree of this
repo", rooted at `~/Desktop/healbot-pool`. `/firstmate` already says `--slot` is for healbot work and
everything else needs an explicit `--dir`. So a crewmate on another project gets whatever directory the
captain names, with no isolation, no lease, and nothing stopping two crewmates from colliding in one
tree.

Decided 2026-08-05: **plain `git worktree` per project**, not a generalized pool, and not one clone per
crewmate.

The reasoning, so it is not re-opened. The pool exists because healbot's untracked payload is a large
checkout plus `node_modules` plus a venv, which most projects are not, and its cleverness is entirely
about cloning that payload cheaply. It is also Mac-only twice over: APFS clonefile for the copy, and
`os.kill(pid, 0)` for liveness, which on Windows would terminate the lease holder rather than probe it.
The PC is wanted. Plain worktrees are portable and simple. Generalizing the pool stays available as a
later, measured decision if provisioning time actually hurts.

The work:

- A verb that provisions a worktree for an arbitrary repo and hands it to `spawn` as `--dir`, so the
  captain never names a path.
- Collision safety: two crewmates on one project get two worktrees, and the mechanism refuses rather
  than silently sharing.
- Cleanup that is fail-closed in the same shape the pool already uses. The pool's release refuses over
  uncommitted changes **and** over commits made on a detached HEAD, which look clean to `git status`
  and are orphaned by a reset. Copy that refusal; do not re-derive it.
- Say what happens to a worktree whose crewmate died, and make the answer visible rather than silent.

**Done looks like:** firstmate can spawn two crewmates on a project that is not healbot, each in its own
worktree, and cleanup refuses to discard work in either. TESTED on a real second repo, not on healbot.

## Comments

The pool's own history is the specification for the failure modes here: its lease originally recorded the
acquiring process, which for every crew spawn exits immediately, so a live crewmate's slot read as
abandoned. The fix was to have the process that outlives the acquire adopt the lease. Whatever leases a
worktree here inherits that lesson rather than rediscovering it.

**PREMISE CHANGED 2026-08-05, revisit before building.** The decision above rests partly on "the PC
is wanted", and the captain is now retiring that machine for a RAM fault. Ticket 06 is closed out of
scope. So the portability half of the argument against generalizing the pool is gone, and the
Mac-only mechanisms it objected to, APFS clonefile and the `os.kill(pid, 0)` liveness probe, are no
longer disqualifying on a Mac-only fleet.

What survives unchanged is the fit argument, which was always the stronger one: the pool exists to
clone a large untracked payload cheaply, and most projects do not have one. That still points at
plain worktrees.

Do not treat this as re-decided in either direction. Re-argue it on fit alone when the ticket is
taken, and record which way it went and why.
