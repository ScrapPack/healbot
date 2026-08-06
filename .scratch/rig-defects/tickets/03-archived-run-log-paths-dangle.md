# The archived run's log paths point at a directory that no longer exists

Type: grilling
Mode: HITL
Status: open
Assignee: -
Blocked by: -

## Question

All six `launches[].logs` entries in the archived refusal run's `meta.json` are absolute paths into
`.../ab-runs/refusal-full/`. That directory does not exist. The run was archived by renaming its
directory to `refusal-full-archived-20260731`, and the recorded paths did not move with it. Verified
6 of 6 still dangling on `main`.

This is HITL rather than a task because the obvious repair is the one thing that might be wrong.

**Rewriting the paths falsifies the record.** `/paid-run-protocol`'s discipline is archive, never
delete, and the reason is that a completed run's metadata is evidence of what that run actually did.
When those launches ran, they really did write to `.../ab-runs/refusal-full/`. Editing the record so
it names a path the run never used makes the file read correctly and describe something that did not
happen. That is the same class of harm as a stale verbatim quote, which `probe_citations.py` treats
as worse than a stale pointer precisely because it puts words in the source's mouth.

So the question is not how to fix the paths. It is what a reader of archived evidence should be able
to rely on.

## The options

- **Leave the paths and record the rename.** Add a line to the archived run's `ARCHIVED.md` saying
  the directory was renamed on 2026-07-31 and that recorded absolute paths predate it. Evidence
  stays true, and the reader gets what they need to resolve it. Cheapest and least destructive.
- **Rewrite the paths to the current location.** The file reads correctly and a tool following it
  finds the logs. It also asserts the run wrote somewhere it did not.
- **Make them relative.** Arguably a truer statement of the run's own structure, since the logs did
  sit beside the meta. Still an edit to a completed record, and it loses the fact that the path was
  absolute at the time.
- **Do nothing, deliberately.** Record that dangling paths inside an archived run are expected after
  a rename and are not a defect. Cheapest of all, if the captain agrees the reader is not owed more.

There is a general decision hiding under the specific one: **does archiving by rename carry an
obligation to leave a forwarding note, or does the archive directory's own name do that job?** The
answer applies to every future archive, not just this run.

## Constraints

- Whatever is chosen, do not edit the run's row data, scores, or `status` field. This is about
  `launches[].logs` and nothing else.
- Check whether the log files still exist at all before deciding. A forwarding note pointing at
  files that were never carried is worth less than one pointing at files that were.

**Resolved when** the reader-obligation question is answered, the chosen option is applied, and the
answer is written where the next archive-by-rename will find it rather than only in this ticket.
