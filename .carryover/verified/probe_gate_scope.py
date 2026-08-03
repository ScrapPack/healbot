"""Does the pre-push gate gate the PUSHED range, or whatever branch the checkout is parked on?

Run 20260802-184854 is the incident this pins. Main was pushed from a checkout parked on an
ancestor branch; gate.changed_files diffed base...HEAD of that checkout, the range collapsed
to ZERO files, every change-scoped linter skipped, and a plainspec-check.py carrying a real
F841 shipped in green. The fix (bb1b048) hands gate.py the pushed tip: the hook passes
--head "$local_sha", changed_files diffs base...head, lint scopes existence at the pushed
tip and feeds ruff the pushed BLOBS via --stdin-filename, and the run record splits `head`
(the gated tip) from `tree` (the checkout the tier-1 probes read). That fix was verified
with a throwaway scripted repro; this probe is the repro made permanent.

THE HARNESS, built fresh per leg in a temp dir: a scratch bare remote plus a scratch work
repo whose main carries a --no-ff merge bringing one new .py with a planted F841. (One leg
stands apart: the deletion-only leg pushes a pure ref deletion through the real hook from
a scratch repo with no gate and no venv, pinning the ZERO-sha exemption added after the
venv refusal briefly refused deletions from fresh clones.) The base
commit is pushed BEFORE the hook wires in, then the checkout is parked on an ancestor branch
and main is pushed from there, which is the exact 20260802-184854 shape. The push runs THE
REPO'S REAL gate/hooks/pre-push (core.hooksPath at the scratch repo points here), and
HEALBOT_GATE runs the repo's real gate.py through a symlink INSIDE the scratch repo, because
gate.py derives ROOT from its own path and its git commands must address the scratch repo.
Tier 1 is made inert (stub probes enumerated from the real TIER1 list, plus a venv python
symlink), so the only row that can block is the machinery under test; the review stage is
stubbed to exit 0; the publisher is off. Zero model turns, zero credits.

The claims, each with the leg that could turn it red:
  1. the gate's file list is exactly the merged file, though the checkout does not hold it;
  2. ruff runs against the pushed blob (the checkout provably has no copy to lint) and the
     gate goes BLOCKED on the planted F841: refusal is exit 2, and the remote ref holds;
  3. the run record's `head` is the pushed tip and its `tree` is the parked checkout;
  4. MUTATION 1 reverts changed_files to base...HEAD scoping, the pre-bb1b048 source: the
     file list collapses to nothing, ruff never runs, and the push SAILS THROUGH, which is
     the incident reproduced on demand. MUTATION 2 reverts the record's head field to the
     checkout sha; the record predicate the live leg passes must go red on that record.
Mutant records are judged by THE SAME functions the live leg passes, per this suite's rule
that a mutation check which re-implements its predicate proves only the reimplementation.
TESTED 2026-08-02 against the whole pre-fix layer (gate.py and hook from the commit before
bb1b048, the then-16-row probe unchanged): 8/16, exit 1, every live-leg claim red plus both
mutation anchors. The probe detects the regression end to end, not only its installed
mutants. That record predates the deletion leg, which reads only the hook and is orthogonal
to the range machinery that test reverted.

Commit identities and dates are pinned, so the scratch shas are stable and this probe's
output is byte-identical across runs: MEASURED 2026-08-03 at 17 rows, 4 runs, one sha256
over the full output. Tier 2 hashes nothing, so nothing depends on that; it is measured because
the gate's determinism note says to measure rather than hope, and it is what Tier 1
membership would require. Needs `ruff` on PATH, the same requirement the gate's own lint
stage carries.

  venv/bin/python probe_gate_scope.py
"""

import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
from rig import Results  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(SP))
HOOKS = f"{ROOT}/gate/hooks"
GATE_PY = f"{ROOT}/gate/gate.py"

# The planted finding: F841, a local assigned and never used. The same rule the mis-scoped
# gate let ship in plainspec-check.py.
MERGED = "merged_change.py"
PLANT = "def planted():\n    unused = 1\n    return 2\n"

# MUTATION 1, the defect restated exactly: the diff range ends at the checkout's HEAD
# whatever tip is being pushed. MUTATION 2: the record's head silently means tree again.
# Each must match gate.py exactly once, and that count is asserted before the legs run.
OLD_SCOPE = "f\"{base}...{head or 'HEAD'}\""
NEW_SCOPE = 'f"{base}...HEAD"'
OLD_HEAD = '"head": gated, "tree": tree,'
NEW_HEAD = '"head": tree,'

# Pinned identity and dates: scratch shas do not move between runs and no machine identity
# leaks into scratch commits. The config isolation keeps the user's global git config
# (hook templates, filters, signing) out of the scenario; the hook and gate inherit it too.
GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "probe", "GIT_AUTHOR_EMAIL": "probe@scratch",
    "GIT_COMMITTER_NAME": "probe", "GIT_COMMITTER_EMAIL": "probe@scratch",
    "GIT_AUTHOR_DATE": "2026-08-02T18:48:54 -0400",
    "GIT_COMMITTER_DATE": "2026-08-02T18:48:54 -0400",
}


def git(cwd, *args):
    """A build-step git call. Failure raises, which the crash guard turns into a red row."""
    return subprocess.run(["git", *args], cwd=cwd, env={**os.environ, **GIT_ENV},
                          capture_output=True, text=True, timeout=120, check=True)


def rev(cwd, ref):
    return git(cwd, "rev-parse", ref).stdout.strip()


def short(cwd, ref):
    """The abbreviated sha, from the same command gate.py records with."""
    return git(cwd, "rev-parse", "--short", ref).stdout.strip()


def write(path, text, mode=0o644):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.chmod(path, mode)


def build_scenario(tmp):
    """The 20260802-184854 shape: a bare remote holding only the base commit, a work repo
    whose main carries a --no-ff merge bringing MERGED, and the checkout parked on an
    ancestor branch. Returns (work, remote, base, tip), the shas full-length."""
    os.makedirs(tmp)
    remote = f"{tmp}/remote.git"
    work = f"{tmp}/work"
    git(tmp, "init", "-q", "--bare", "remote.git")
    git(tmp, "init", "-q", "-b", "main", "work")
    write(f"{work}/README.md", "scratch scenario repo for probe_gate_scope.py\n")
    # The harness half of the scratch tree stays invisible to the scratch git: the gate's
    # home-paths scan reads untracked-unignored files, and the venv python symlink resolves
    # to a real interpreter binary that may embed a builder's home path.
    write(f"{work}/.gitignore", "/gate/\n/.carryover/\n/review-stub.sh\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "base")
    base = rev(work, "HEAD")
    git(work, "remote", "add", "origin", remote)
    git(work, "push", "-q", "origin", "main")          # before the hook wires in: ungated
    git(work, "config", "core.hooksPath", HOOKS)       # the REAL pre-push, from this repo
    git(work, "checkout", "-q", "-b", "feature")
    write(f"{work}/{MERGED}", PLANT)
    git(work, "add", MERGED)
    git(work, "commit", "-q", "-m", "feature")
    git(work, "checkout", "-q", "main")
    git(work, "merge", "-q", "--no-ff", "--no-edit", "feature")
    tip = rev(work, "HEAD")
    git(work, "checkout", "-q", "-b", "parked", base)  # park the checkout on the ancestor
    return work, remote, base, tip


def tier1_stub_names():
    """The TIER1 probe filenames, read from the real gate module so the stub set cannot
    drift from the list gate.py actually runs. Importing gate.py executes only constant
    and function definitions; its ROOT resolves to this repo and is not used here."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_probe_gate_scope_gate", GATE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return [cmd[1] for _, cmd, _, _ in mod.TIER1]


def install_gate(work, source=None):
    """gate.py INSIDE the scratch repo, because gate.py derives ROOT from its own path and
    its git commands must address the scratch repo, not this one. source=None symlinks the
    repo's real file; a string installs a mutated copy. Tier 1 is made inert so the only
    row that can block is the range machinery under test."""
    os.makedirs(f"{work}/gate")
    if source is None:
        os.symlink(GATE_PY, f"{work}/gate/gate.py")
    else:
        write(f"{work}/gate/gate.py", source)
    os.makedirs(f"{work}/.carryover/verified/venv/bin")
    os.symlink(sys.executable, f"{work}/.carryover/verified/venv/bin/python")
    for name in tier1_stub_names():
        write(f"{work}/.carryover/verified/{name}", "import sys\nsys.exit(0)\n")
    write(f"{work}/review-stub.sh", "#!/bin/sh\nexit 0\n", mode=0o755)


def push(work):
    """Drive the gated push: the real hook, the scratch gate, review stubbed, publish off.
    HEALBOT_GATE word-splits in the hook, which is why it can carry interpreter + script."""
    env = {**os.environ, **GIT_ENV,
           "HEALBOT_GATE": f"{sys.executable} {work}/gate/gate.py",
           "HEALBOT_REVIEW_CMD": f"{work}/review-stub.sh",
           "HEALBOT_PUBLISH": "off",
           "HEALBOT_GATE_RUNS": f"{work}/gate/runs"}
    return subprocess.run(["git", "push", "origin", "main"], cwd=work,
                          capture_output=True, text=True, timeout=300, env=env)


def run_record(work):
    """The leg's single gate run record, or None. A leg that produced none has nothing to
    quote, and every predicate below treats None as False, so a mutant leg whose push
    machinery broke cannot pass its detection row vacuously."""
    recs = glob.glob(f"{work}/gate/runs/*.json")
    if len(recs) != 1:
        return None
    with open(recs[0], encoding="utf-8") as fh:
        return json.load(fh)


def files_ok(rec):
    """Claim 1: the gate saw exactly the merged file."""
    return rec is not None and rec.get("files") == [MERGED]


def ruff_row(rec):
    rows = [c for c in (rec.get("checks", []) if rec else []) if c.get("check") == "ruff"]
    return rows[0] if len(rows) == 1 else None


def ruff_blocked_ok(rec):
    """Claim 2: ruff ran, went BLOCKED, and names the planted F841 in the merged file."""
    row = ruff_row(rec)
    return (row is not None and row.get("state") == "blocked"
            and "F841" in row.get("out", "") and MERGED in row.get("out", ""))


def record_scope_ok(rec, work, tip):
    """Claim 3: the record's head is the PUSHED tip and its tree is the parked checkout."""
    return (rec is not None and rec.get("head") == short(work, tip)
            and rec.get("tree") == short(work, "HEAD"))


r = Results(expect=17)
TMP = tempfile.mkdtemp(prefix="probe_gate_scope.")
try:
    r.check(
        "ruff is on PATH, the gate's lint engine",
        shutil.which("ruff") is not None,
        "the planted-F841 legs below need it, and the real gate's lint stage carries the "
        "same requirement, so a machine without it cannot run either",
    )
    with open(GATE_PY, encoding="utf-8") as fh:
        gate_src = fh.read()

    # --- deletion-only leg: a push whose every local sha is ZERO gates nothing -----------
    # The scratch repo deliberately gets NO gate/ and NO venv symlink: the early exemption
    # is the only thing that can let this push through, so a regression carrying a deletion
    # past the ZERO skip hits the hook's venv refusal and the push goes red here. The
    # planted-F841 legs below are the converse guard: they push real commits through the
    # same hook and refuse, so an exemption that swallowed real pushes turns them red.
    dtmp = f"{TMP}/delete"
    os.makedirs(dtmp)
    dwork = f"{dtmp}/work"
    git(dtmp, "init", "-q", "--bare", "remote.git")
    git(dtmp, "init", "-q", "-b", "main", "work")
    write(f"{dwork}/README.md", "deletion-leg scratch repo for probe_gate_scope.py\n")
    git(dwork, "add", ".")
    git(dwork, "commit", "-q", "-m", "base")
    git(dwork, "remote", "add", "origin", f"{dtmp}/remote.git")
    git(dwork, "push", "-q", "origin", "main", "main:todelete")   # both ungated, pre-wire
    git(dwork, "config", "core.hooksPath", HOOKS)                 # the REAL pre-push
    # HEALBOT_* stripped, not inherited: an ambient stub set (HEALBOT_GATE +
    # HEALBOT_REVIEW_CMD + HEALBOT_PUBLISH=off) would leave the hook's needs_venv empty,
    # and a regressed ZERO-sha skip would then reach the stub and exit 0 — green for a
    # reason unrelated to the claim. With them stripped, every stage-reaching path in
    # this venv-less scratch repo refuses, so exit 0 can only mean the skip held.
    denv = {k: v for k, v in os.environ.items() if not k.startswith("HEALBOT_")}
    dpush = subprocess.run(["git", "push", "origin", ":todelete"], cwd=dwork,
                           capture_output=True, text=True, timeout=120,
                           env={**denv, **GIT_ENV})
    r.check(
        "a deletion-only push passes the REAL hook with no venv and no gate installed",
        dpush.returncode == 0,
        "review finding from the b6e97b4 push: the exemption shipped tested only by a "
        "throwaway worktree run — the same disposable-repro shape this probe exists to "
        "replace. Nothing here can gate: any path that reaches a stage hits the venv "
        "refusal (exit 1) or a missing gate.py, so exit 0 alone carries the claim that "
        "the ZERO-sha path reached no stage",
    )

    # --- live leg: the repo's real hook and real gate.py, on the incident's shape --------
    work, remote, base, tip = build_scenario(f"{TMP}/live")
    install_gate(work)
    r.check(
        "fixture: the scenario holds its shape",
        tip != base and rev(work, "HEAD") == base,
        "merge tip ahead of base, checkout parked on the ancestor; a collapsed scenario "
        "would make every claim below vacuous",
    )
    r.check(
        "fixture: the merged file is NOT in the checkout tree at push time",
        not os.path.exists(f"{work}/{MERGED}"),
        "the property that makes the ruff claim attributable to the pushed blob: there is "
        "no checkout copy to lint",
    )
    live = push(work)
    rec = run_record(work)
    r.check(
        "the push was REFUSED",
        live.returncode != 0,
        "the hook exits 1 when the gate says no, and git aborts the transfer",
    )
    r.check(
        "...by the gate's BLOCKED verdict, exit 2, not an ERROR",
        "REFUSING the push (gate exit 2" in live.stderr,
        "a refusal for exit 3 would mean a check could not run, which is a broken harness, "
        "not a detected finding",
    )
    r.check(
        "...and the refusal held: the remote ref did not move",
        rev(remote, "refs/heads/main") == base,
        "a gate that says no while the ref advances is not a gate",
    )
    r.check(
        "the gate wrote exactly one run record",
        rec is not None,
        "the evidence artifact the three claims below quote",
    )
    r.check(
        "CLAIM 1: the gate's file list is exactly the merged file",
        files_ok(rec),
        "base...pushed-tip sees the file the merge brings even though the checkout is "
        "parked before it",
    )
    r.check(
        "CLAIM 2: ruff read the pushed blob and went BLOCKED on the planted F841",
        ruff_blocked_ok(rec),
        "the checkout holds no copy of the file (fixture above), so the finding can only "
        "have come from the blob at the pushed tip",
    )
    r.check(
        "CLAIM 3: the record splits head from tree",
        record_scope_ok(rec, work, tip),
        "head is the pushed tip the lint gated, tree is the parked checkout the tier-1 "
        "probes read; 20260802-184854 is why they are two fields",
    )

    # --- mutation 1: revert changed_files to base...HEAD scoping -------------------------
    r.check(
        "the scope mutation still applies to gate.py, exactly once",
        gate_src.count(OLD_SCOPE) == 1,
        "zero would mean gate.py moved under this probe and the mutant below no longer "
        "restates the 20260802-184854 defect; its detections would be unmeasured",
    )
    m_work, m_remote, _mb, m_tip = build_scenario(f"{TMP}/mut-scope")
    install_gate(m_work, source=gate_src.replace(OLD_SCOPE, NEW_SCOPE))
    mut = push(m_work)
    m_rec = run_record(m_work)
    r.check(
        "MUTATION 1: base...HEAD scoping IS detected, the file list collapses",
        m_rec is not None and not files_ok(m_rec) and m_rec.get("files") == [],
        "the same files_ok the live leg passed, red on the mutant record: the '0 changed "
        "file(s)' collapse of run 20260802-184854",
    )
    r.check(
        "MUTATION 1: ...and ruff never runs, skipped rather than blocked",
        m_rec is not None and not ruff_blocked_ok(m_rec)
        and (ruff_row(m_rec) or {}).get("state") == "skipped",
        "every change-scoped linter skipped is the incident's second half",
    )
    r.check(
        "MUTATION 1: ...and the push SAILS THROUGH in green",
        mut.returncode == 0 and rev(m_remote, "refs/heads/main") == m_tip,
        "the F841 ships and the remote advances: the outcome the fix exists to make "
        "impossible",
    )

    # --- mutation 2: revert the record's head field to the checkout sha ------------------
    r.check(
        "the record mutation still applies to gate.py, exactly once",
        gate_src.count(OLD_HEAD) == 1,
        "same argument as the scope mutation's count",
    )
    h_work, _hr, _hb, h_tip = build_scenario(f"{TMP}/mut-record")
    install_gate(h_work, source=gate_src.replace(OLD_HEAD, NEW_HEAD))
    push(h_work)  # refused, same as the live leg: this mutant's scoping is intact
    h_rec = run_record(h_work)
    r.check(
        "MUTATION 2: a record whose head silently means tree again IS detected",
        h_rec is not None and not record_scope_ok(h_rec, h_work, h_tip),
        "the same record predicate the live leg passed, red on the reverted record shape",
    )

except SystemExit:
    raise
except Exception:
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    shutil.rmtree(TMP, ignore_errors=True)
    ok = r.summary()
    sys.exit(0 if ok else 1)
