# PC: Claude Code login and the conversion checklist

Type: task
Mode: HITL
Status: closed
Assignee: -
Blocked by: -

## Question

Manual work that unblocks a decision rather than a decision itself.

The Windows bring-up ran 2026-08-05. `harness/doctor.py` reports zero FAIL rows there; the opencode
and per-change-gate tiers read READY, tmux and pty read N/A by design, and the Claude Code tier waits
on one interactive login. Three POSIX assumptions were found and fixed in the same run.

What remains on that machine:

1. The one interactive Claude Code login. The credential is keyed to the `harness/claude/` config
   root, not to the machine, so every clone, worktree and pool slot starts signed out. Only a human
   at that keyboard can do it.
2. `docs/WINDOWS.md`'s conversion checklist, worked through.

Why it is on this map: every native-Windows claim in the docs is INFERRED until this runs on that
machine, and a daily driver that only exists on one Mac is not a daily driver. This ticket does not
decide anything by itself; it produces the facts that later decisions about a second machine wait on.

**Resolved when** the login is done and the checklist is worked, and the resolution records what the
run found: which checklist items held, which did not, and any new facts later tickets will depend on.

## Resolution

**Ruled OUT OF SCOPE 2026-08-05 and closed, not resolved.** The captain is retiring the PC entirely
for a RAM fault and instability. There is no machine to log in and no checklist to walk, so this
ticket sits past the destination rather than on the route to it. A closed ticket is unambiguously
off the frontier; the map's Out of scope section carries the one-line record.

Nothing here graduates. If a second machine ever returns, it is a fresh effort under a redrawn
destination, not a resumption of this.

Two consequences that do NOT close with it, because they outlive the machine:

1. **The corruption question is live and is now ticket 15.** Work already committed from that PC is
   in this repo's history.
2. **Two decisions cited "the PC is wanted" as part of their reasoning** and that premise is now
   false. Ticket 10 is closed and its decision survives on its primary reason, which was isolation
   rather than portability. **Ticket 14 is still open and its rationale needs revisiting**; a note
   is on it.

What the PC did produce stands on its own: `harness/doctor.py` reported zero FAIL rows there, and
three real POSIX assumptions were found and fixed. Those fixes are in the tree and are guarded by
probes on this machine, independent of whether any PC exists.
