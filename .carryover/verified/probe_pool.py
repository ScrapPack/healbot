"""Does the worktree pool's lease/guard state machine refuse what it claims to? — FREE, no clones.

harness/pool.py protects work in slots with refusals: dirty trees, commits on the detached
HEAD, wrong owners, missing baselines. Every one of those guards was born from a live miss —
the 68e9cbe push review caught release orphaning committed work, exercising that fix caught
acquire and status sharing the blind spot, and the f6dcaeb review caught the missing-record
case where restore would reset to HEAD and claim success. Those regressions were then proven
fixed by an interactive command sequence that lived only in a session transcript; this probe
is that sequence as a repo artifact, so the state machine cannot quietly regress.

It builds a miniature pool in a temp dir — real git repos as slots, fabricated acceptance
records, NO payload clones — and drives acquire/release/reset/status/destroy through every
refusal with the violating state actually present (the mutation IS the workload). What each
row would catch: a guard that stops reading work_state, a restore that stops verifying its
baseline, an acquire that leases soiled or unproven slots, an exit that leaves the lattice.

  venv/bin/python probe_pool.py
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

SP = os.path.dirname(os.path.abspath(__file__))
HEALBOT = os.path.dirname(os.path.dirname(SP))
sys.path.insert(0, SP)
sys.path.insert(0, f"{HEALBOT}/harness")
import pool  # noqa: E402
from rig import Results  # noqa: E402

# 24 through the state-machine build; the 2026-08-03 adopt work (docs/E2E.md finding 8:
# acquire recorded its own short-lived pid, so status called every live crewmate's slot
# abandoned) adds eight — the pid-less default, both polarities of the unclaimed marker,
# adopt's three refusal shapes, and both polarities of the DEAD note, whose branch no
# earlier row had ever exercised. 32. The push review adds the pid DOMAIN row (0 and
# negatives refuse at 3, not just unparsable text). 33.
r = Results(expect=33)
TMP = tempfile.mkdtemp(prefix="probe-pool-")


def git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "user.name=probe", "-c", "user.email=probe@local", *args],
        cwd=cwd, capture_output=True, text=True)


def make_slot(name, verdict="pass"):
    slot = f"{pool.SLOTS}/{name}"
    os.makedirs(slot)
    git(slot, "-c", "init.defaultBranch=main", "init", "-q")
    with open(f"{slot}/base.txt", "w") as fh:
        fh.write("base\n")
    git(slot, "add", "base.txt")
    git(slot, "commit", "-qm", "base")
    sha = git(slot, "rev-parse", "HEAD").stdout.strip()
    with open(pool.record_path(slot), "w") as fh:
        json.dump({"slot": name, "sha": sha, "acceptance": {"verdict": verdict}}, fh)
    return slot, sha


def leases():
    return sorted(os.listdir(pool.LEASES))


try:
    # A miniature pool: module constants repointed, three slots — two accepted, one not.
    pool.POOL, pool.SLOTS = TMP, f"{TMP}/slots"
    pool.LEASES, pool.RECORDS = f"{TMP}/leases", f"{TMP}/records"
    os.makedirs(pool.SLOTS)
    os.makedirs(pool.LEASES)
    os.makedirs(pool.RECORDS)
    s1, sha1 = make_slot("slot-1")
    s2, sha2 = make_slot("slot-2")
    s3, _ = make_slot("slot-3", verdict="blocked")

    # -- acquire: exclusivity, order, and the unproven-slot refusal ------------------------
    a1, a2 = pool.acquire("A", "first"), pool.acquire("B", "second")
    r.check("two acquires lease two DISTINCT slots (sorted scan: slot-1 then slot-2)",
            a1 == 0 and a2 == 0 and leases() == ["slot-1.json", "slot-2.json"],
            f"codes {a1},{a2}, leases {leases()}")
    r.check("a third acquire refuses with 2 — the pool is honestly exhausted",
            pool.acquire("C", "third") == 2, "slot-3 exists but must not count")
    r.check("the unaccepted slot was never leased — acceptance!=pass is not leasable",
            not os.path.exists(pool.lease_path(s3)), "slot-3 recorded verdict=blocked")

    # -- release: owner conditions, then the two forms of work ----------------------------
    r.check("release --if-owner with the WRONG owner refuses 2 and keeps the lease",
            pool.release("slot-1", if_owner="Z") == 2 and os.path.exists(pool.lease_path(s1)),
            "conditional release is the retry-safe primitive")
    r.check("release --if-owner with the right owner restores and drops the lease",
            pool.release("slot-1", if_owner="A") == 0 and not os.path.exists(pool.lease_path(s1)),
            "")
    r.check("releasing an unleased slot refuses 2 — a double release is a caller bug",
            pool.release("slot-1") == 2, "")

    with open(f"{s2}/dirt.txt", "w") as fh:
        fh.write("uncommitted\n")
    r.check("release refuses 2 while the slot holds UNCOMMITTED work",
            pool.release("slot-2") == 2, "dirt.txt is present and unignored")
    kept = pool.release("slot-2", keep=True)
    r.check("release --keep drops the lease and walks away", kept == 0 and
            not os.path.exists(pool.lease_path(s2)), "")
    r.check("--keep destroyed NOTHING — the dirt is still on disk",
            os.path.exists(f"{s2}/dirt.txt"), "keep means keep")

    r.check("acquire SKIPS the soiled slot — abandoned state is a human's decision",
            pool.acquire("C", "wants clean") == 0 and leases() == ["slot-1.json"],
            f"leases {leases()} — slot-2 dirty, slot-3 unproven, so slot-1")
    pool.release("slot-1", if_owner="C")

    # -- reset: the leaseless repair path --------------------------------------------------
    r.check("reset refuses 2 while the soiled slot's work is undiscarded",
            pool.reset_cmd("slot-2") == 2, "")
    r.check("reset --discard-work restores, and the dirt is GONE",
            pool.reset_cmd("slot-2", discard_work=True) == 0 and
            not os.path.exists(f"{s2}/dirt.txt"), "")
    pool.acquire("A", "hold for reset-refusal")  # takes slot-1 (sorted, clean)
    r.check("reset refuses 2 on a LEASED slot — that is release's job",
            pool.reset_cmd("slot-1") == 2, "")
    pool.release("slot-1", if_owner="A")

    # -- committed work: status-clean, orphaned by reset, guarded everywhere --------------
    pool.acquire("A", "will commit")  # slot-1
    with open(f"{s1}/feature.txt", "w") as fh:
        fh.write("work\n")
    git(s1, "add", "feature.txt")
    git(s1, "commit", "-qm", "feature")
    r.check("release refuses 2 when HEAD moved off the provisioned sha (git status is clean)",
            pool.release("slot-1") == 2, "the 68e9cbe review's finding, as a control")
    r.check("acquire refuses to lease the committed-work slot to anyone else",
            pool.acquire("B", "unlucky") == 0 and leases() == ["slot-1.json", "slot-2.json"],
            "B got slot-2; slot-1 stayed A's problem")
    pool.release("slot-2", if_owner="B")
    r.check("release --discard-work restores HEAD to the provisioned sha exactly",
            pool.release("slot-1", discard_work=True) == 0 and
            git(s1, "rev-parse", "HEAD").stdout.strip() == sha1,
            "rev-parse is the evidence, not the return code")

    # -- the missing-baseline hole (f6dcaeb review): unknowable is an error, not a default -
    pool.acquire("A", "record about to vanish")  # slot-1
    os.rename(pool.record_path(s1), pool.record_path(s1) + ".hidden")
    rc = pool.release("slot-1", discard_work=True)
    r.check("release --discard-work with NO readable record errors 3 — restore cannot claim a baseline it does not know",
            rc == 3, f"got {rc}")
    r.check("…and the lease survives the refusal — the slot stays somebody's problem",
            os.path.exists(pool.lease_path(s1)), "")
    with open(pool.record_path(s1), "w") as fh:
        json.dump({"slot": "slot-1", "sha": "", "acceptance": {"verdict": "pass"}}, fh)
    r.check("an EMPTY-STRING sha is the same unknowable baseline, not a falsiness loophole",
            pool.release("slot-1", discard_work=True) == 3,
            "the 569e5e0 review's finding: `is None` disagreed with work_state's `if sha`")
    os.rename(pool.record_path(s1) + ".hidden", pool.record_path(s1))
    pool.release("slot-1", if_owner="A")

    # -- destroy refusals (the git-worktree half needs the real repo and is not probed) ----
    r.check("destroy without --really refuses 2", pool.destroy("slot-2") == 2, "")
    pool.acquire("A", "hold")  # slot-1
    r.check("destroy refuses 2 on a leased slot", pool.destroy("slot-1", really=True) == 2, "")
    pool.release("slot-1", if_owner="A")

    # -- status is also a check ------------------------------------------------------------
    r.check("status exits 2 while any slot needs a human (slot-3 is unaccepted)",
            pool.status() == 2, "")
    with open(pool.record_path(s3), "w") as fh:
        json.dump({"slot": "slot-3", "sha": git(s3, "rev-parse", "HEAD").stdout.strip(),
                   "acceptance": {"verdict": "pass"}}, fh)
    r.check("status exits 0 once every slot is accepted, clean and unleased",
            pool.status() == 0, "")
    with open(f"{s3}/late-dirt.txt", "w") as fh:
        fh.write("x\n")
    r.check("status exits 2 again when unleased work appears — the pool self-reports",
            pool.status() == 2, "")

    # -- adopt: the real holder declares itself after the fact (docs/E2E.md finding 8) ----
    # The acquiring process never outlives a lease, so acquire records pid=None and the
    # holder that exists later adopts. Both status branches get a polarity pair: the
    # unclaimed marker fires on a pid-less lease and clears on adoption; the DEAD note
    # fires on a real dead pid and stays silent for a live one. The DEAD branch had no
    # exercise at all before these rows — every earlier status check here ran leaseless.
    def slot1_status_line():
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pool.status()
        return next(ln for ln in buf.getvalue().splitlines() if "slot-1" in ln)

    pool.acquire("A", "adopt exercise")  # slot-1: sorted first among clean, free slots
    r.check("acquire records NO holder pid — the acquirer never outlives the lease",
            (pool.read_json(pool.lease_path(s1)) or {}).get("pid") is None,
            "recording os.getpid() here was E2E finding 8: structurally always-DEAD")
    r.check("status says a pid-less lease makes no liveness claim, explicitly",
            "liveness unclaimed" in slot1_status_line(),
            "silence on a probed pid means alive, so absence-of-claim must be spoken")
    r.check("adopt on an unleased slot refuses 2", pool.adopt("slot-2", 12345) == 2, "")
    r.check("adopt with the wrong owner refuses 2 and records nothing",
            pool.adopt("slot-1", 12345, if_owner="Z") == 2
            and (pool.read_json(pool.lease_path(s1)) or {}).get("pid") is None, "")
    r.check("adopt with a malformed pid errors 3",
            pool.adopt("slot-1", "not-a-pid", if_owner="A") == 3, "")
    r.check("adopt refuses pid 0 and negatives at 3 — the domain, not just the form",
            pool.adopt("slot-1", 0, if_owner="A") == 3
            and pool.adopt("slot-1", -1, if_owner="A") == 3,
            "0 would contradict status's no-claim reading; a negative probes a process "
            "GROUP and reads permanently alive (push-review finding)")
    r.check("adopt records the holder pid on the lease",
            pool.adopt("slot-1", os.getpid(), if_owner="A") == 0
            and (pool.read_json(pool.lease_path(s1)) or {}).get("pid") == os.getpid(), "")
    line = slot1_status_line()
    r.check("NEGATIVE: a LIVE adopted holder draws neither DEAD nor unclaimed",
            "DEAD" not in line and "liveness unclaimed" not in line,
            "this probe's own pid is the live holder")
    corpse = subprocess.Popen(["true"])
    corpse.wait()
    pool.adopt("slot-1", corpse.pid, if_owner="A")
    r.check("a DEAD adopted holder fires the DEAD note — first exercise of that branch",
            "holder pid DEAD" in slot1_status_line(),
            f"pid {corpse.pid} exited and was reaped before the probe read status")

except Exception:
    # A crash must look like a failure. `sys.exit()` in a `finally` discards the escaping
    # exception, so without this guard the probe leaves on summary()'s verdict over whatever
    # ran before it died — a green exit for a dead run.
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(0 if r.summary() else 1)
