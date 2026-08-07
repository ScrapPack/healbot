# hb/project still holds four model artifacts on disk

Type: task
Mode: HITL
Status: open
Assignee: -
Blocked by: -

## Question

`rig.fixtures()` declares six files. `ls -A .carryover/verified/hb/project` returns twelve, and the
inner git repo was tracking four that nobody declared:

```
.gitleaks.toml  dns_tunnel_detector.py  linux_triage.sh  requirements.txt
```

All four are refusal-study leavings, committed into the fixture's baseline by
`rig.git_baseline()`'s old `git add -A`. A file that IS the baseline is not a CHANGE, so one run's
output silently stopped appearing in the next run's diff — the single property that function exists
to provide.

**The mechanism is already fixed.** `rig.py` now declares the set as `FIXTURE_FILES`, only those
files enter the baseline, and anything already tracked but undeclared is dropped from the index with
`git rm --cached` on the next rig run. Nothing leaves the disk, so a paid run's evidence survives
and becomes visible as a change again. Residue is printed rather than absorbed.

**What is still open is the disk, and it is an owner call.** The four files are still there. Two
positions, both defensible:

- **Delete them.** The fixture is meant to be a known tree, and four undeclared files mean every
  future run's diff carries four entries that are nothing to do with that run.
- **Leave them.** They are the output of paid turns. `docs/OUTCOME.md` §7 records the last restore
  being done *"on the owner's instruction"*, and deleting measurement residue is not a thing an
  agent should decide.

This is HITL for that reason, and only for that reason.

## What is NOT at stake

No current measurement is invalidated. `HARNESS.md`'s rig-project row is explicit that the evidence
always lived in `hb/*.db` and the project directory only ever held the workload, and the Phase 12
restore was TESTED to have deleted no measurement. No rig asserts on any of the four filenames.

The hazard is latent: a future run that creates a file with one of those four names would see it
not appear in `GET /session/{id}/diff`, which five `verify_*` rigs and `probe_request_channel.py`
all depend on.

## One related correction already made

`docs/OUTCOME.md` §7 claimed the directory was *"back to exactly the seven entries the rig
declares"*. It was twelve. That claim, and the matching one in `docs/AFK.md`, are corrected, and
`HARNESS.md`'s row now records that the restore did not hold.
