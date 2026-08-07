# PC: Claude Code login and the conversion checklist

Type: task
Mode: HITL
Status: closed
Assignee: -
Blocked by: -

## Question

The Windows bring-up ran 2026-08-05. `harness/doctor.py` reported zero FAIL rows on that machine;
the opencode and per-change-gate tiers read READY, tmux and pty read N/A by design, and the Claude
Code tier waited on one interactive login. Three POSIX assumptions were found and fixed in the same
run.

Two things were asked for and never done. The interactive Claude Code login, which only a human at
that keyboard could do, because the credential is keyed to the `harness/claude/` config root rather
than to the machine and every clone, worktree and pool slot starts signed out. And
`docs/WINDOWS.md`'s conversion checklist, worked through. Both were wanted because every
native-Windows claim in the docs stays INFERRED without them.

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
