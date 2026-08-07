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
output is byte-identical across runs: MEASURED 2026-08-03, 4 runs, one sha256 over the full
output. Tier 2 hashes nothing, so nothing depends on that; it is measured because
the gate's determinism note says to measure rather than hope, and it is what Tier 1
membership would require. The row count that used to sit in that sentence is gone rather
than corrected: it is a number with nothing computing it, so every leg added below rotted
it, and `Results(expect=N)` already computes and prints it. Needs `ruff` on PATH, the same
requirement the gate's own lint stage carries.

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

# The two path shapes git's own defaults destroy, and one of them is a BANNED filename so the
# cost lands on an invariant rather than on tidiness: `banned_names` matches by basename, and
# the basename of the quoted form is `CLAUDE.md"` — trailing quote — which is not in BANNED.
ODD_BANNED = "docs/café/CLAUDE.md"
ODD_SPACED = "té st.py"

# MUTATION 3 takes the quoting flag off the shared enumeration. MUTATION 4 stops it reading the
# exit code, so git's `fatal:` text becomes the file list again. Both are the pre-fix source
# restated exactly, and both must match gate.py once — asserted before the legs that use them.
OLD_QUOTE = 'sh(["git", "-c", "core.quotePath=false", *args])'
NEW_QUOTE = 'sh(["git", *args])'
OLD_CODE = '    if r["code"] != 0:\n        return None\n'
NEW_CODE = "    if False:\n        return None\n"

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


def build_scenario(tmp, plant=PLANT):
    """The 20260802-184854 shape: a bare remote holding only the base commit, a work repo
    whose main carries a --no-ff merge bringing MERGED, and the checkout parked on an
    ancestor branch. Returns (work, remote, base, tip), the shas full-length. `plant` is
    the merged file's content: the F841 by default; the sentinel legs pass clean source,
    because a BLOCKED ruff row would win the verdict over the ERROR they exist to see."""
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
    write(f"{work}/{MERGED}", plant)
    git(work, "add", MERGED)
    git(work, "commit", "-q", "-m", "feature")
    git(work, "checkout", "-q", "main")
    git(work, "merge", "-q", "--no-ff", "--no-edit", "feature")
    tip = rev(work, "HEAD")
    git(work, "checkout", "-q", "-b", "parked", base)  # park the checkout on the ancestor
    return work, remote, base, tip


def build_odd(tmp):
    """A gated push whose change carries the two path shapes git quotes by default, one of them
    a banned filename. Returns (work, remote, base, tip).

    NO PARKED CHECKOUT, unlike `build_scenario`: these legs ask what the enumeration RETURNS,
    not which tip it ends at, and a parked checkout would put a second explanation behind every
    red. The quoting premise is structural rather than a config line — `GIT_ENV` points
    `GIT_CONFIG_GLOBAL` and `GIT_CONFIG_SYSTEM` at os.devnull and sets `GIT_CONFIG_NOSYSTEM`, so
    `core.quotePath` sits at git's compiled-in default and no machine can have disabled it under
    the legs. That is asserted rather than assumed: a fixture inheriting ambient git config is
    how a mutation control ends up incapable of failing (review finding from the 2e114b1 push).
    """
    os.makedirs(tmp)
    remote, work = f"{tmp}/remote.git", f"{tmp}/work"
    git(tmp, "init", "-q", "--bare", "remote.git")
    git(tmp, "init", "-q", "-b", "main", "work")
    write(f"{work}/README.md", "odd-path scratch repo for probe_gate_scope.py\n")
    write(f"{work}/.gitignore", "/gate/\n/.carryover/\n/review-stub.sh\n")
    git(work, "add", ".")
    git(work, "commit", "-q", "-m", "base")
    base = rev(work, "HEAD")
    git(work, "remote", "add", "origin", remote)
    git(work, "push", "-q", "origin", "main")          # before the hook wires in: ungated
    git(work, "config", "core.hooksPath", HOOKS)       # the REAL pre-push, from this repo
    write(f"{work}/{ODD_BANNED}", "# a banned filename behind a non-ASCII directory\n")
    write(f"{work}/{ODD_SPACED}", "def clean():\n    return 2\n")  # clean: ruff must not block
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "a quoted path and a spaced one")
    return work, remote, base, rev(work, "HEAD")


def row_of(rec, name):
    """One named row from a run record, or {}. Never None, so a predicate reading `.get` on a
    record that was never written is False rather than an AttributeError the crash guard would
    report as an exception instead of as the claim that failed."""
    rows = [c for c in (rec.get("checks", []) if rec else []) if c.get("check") == name]
    return rows[0] if len(rows) == 1 else {}


def tier1_stub_names():
    """The TIER1 probe filenames, read from the real gate module so the stub set cannot
    drift from the list gate.py actually runs. Importing gate.py executes only constant
    and function definitions; its ROOT resolves to this repo and is not used here."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_probe_gate_scope_gate", GATE_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return [cmd[1] for _, cmd, _, _ in mod.TIER1]


def install_gate(work, source=None, first_stub_exit=0):
    """gate.py INSIDE the scratch repo, because gate.py derives ROOT from its own path and
    its git commands must address the scratch repo, not this one. source=None symlinks the
    repo's real file; a string installs a mutated copy. Tier 1 is made inert so the only
    row that can block is the range machinery under test — except when `first_stub_exit`
    makes the first tier-1 stub the subject: the sentinel legs set it to 3 (a declared
    cannot-measure refusal) and 1 (a plain red) to drive the row-state mapping itself."""
    os.makedirs(f"{work}/gate")
    if source is None:
        os.symlink(GATE_PY, f"{work}/gate/gate.py")
    else:
        write(f"{work}/gate/gate.py", source)
    os.makedirs(f"{work}/.carryover/verified/venv/bin")
    os.symlink(sys.executable, f"{work}/.carryover/verified/venv/bin/python")
    for i, name in enumerate(tier1_stub_names()):
        code = first_stub_exit if i == 0 else 0
        write(f"{work}/.carryover/verified/{name}", f"import sys\nsys.exit({code})\n")
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


r = Results(expect=30)
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

    # --- sentinel legs: a tier-1 probe's exit 3 is ERROR, and only 3 is (E2E item D) -----
    # gate.py's tier-1 mapping used to fold every nonzero probe exit into BLOCKED, so a
    # probe that started and then found its own named input absent (probe_twin and
    # probe_citations on a clone without opencode/) reported identically to one that ran
    # and measured a finding. Exit 3 is the declared cannot-measure refusal now — the same
    # code the gate itself exits with on ERROR. These legs plant CLEAN source, because the
    # default scenario's F841 would take ruff to BLOCKED and the verdict lattice would
    # bury the ERROR under it.
    CLEAN = "def unplanted():\n    return 2\n"
    s_work, s_remote, s_base, _st = build_scenario(f"{TMP}/sentinel", plant=CLEAN)
    install_gate(s_work, first_stub_exit=3)
    spush = push(s_work)
    s_rows = (run_record(s_work) or {}).get("checks") or [{}]
    r.check(
        "SENTINEL: a tier-1 probe exiting 3 records ERROR and refuses at gate exit 3",
        spush.returncode != 0 and "REFUSING the push (gate exit 3" in spush.stderr
        and s_rows[0].get("state") == "error"
        and rev(s_remote, "refs/heads/main") == s_base,
        "cannot-measure is neither a pass nor a finding: the claim is unmeasured, the "
        "hook still refuses, and the record says which",
    )
    c_work, c_remote, c_base, _ct = build_scenario(f"{TMP}/sentinel-control", plant=CLEAN)
    install_gate(c_work, first_stub_exit=1)
    cpush = push(c_work)
    c_rows = (run_record(c_work) or {}).get("checks") or [{}]
    r.check(
        "SENTINEL CONTROL: a probe exiting 1 still records BLOCKED at gate exit 2",
        cpush.returncode != 0 and "REFUSING the push (gate exit 2" in cpush.stderr
        and c_rows[0].get("state") == "blocked"
        and rev(c_remote, "refs/heads/main") == c_base,
        "the boundary that keeps the sentinel narrow: only the DECLARED refusal "
        "reclassifies — a crash or a red stays a finding, fail-closed",
    )

    # --- the change scope itself: a path git quotes, and a range git cannot resolve ------
    #
    # Two defects in the one function every change-scoped check reads (review finding from the
    # 3441813 push). `gate/staleness.py` and `harness/memory.py` both parse this same command's
    # output correctly and both cite gate.py for `splitlines()` — gate.py was the copy the
    # other two pointed at and the one still missing `core.quotePath=false`, and it also read
    # `sh()["out"]` (stderr merged in) without ever reading `["code"]`.
    r.check(
        "the quoting mutation still applies to gate.py, exactly once",
        gate_src.count(OLD_QUOTE) == 1,
        f"zero would mean the shared enumeration moved under this probe, and MUTATION 3 below "
        f"would install a gate.py identical to the shipped one — a detection row that cannot "
        f"fail. count={gate_src.count(OLD_QUOTE)}",
    )
    r.check(
        "the exit-code mutation still applies to gate.py, exactly once",
        gate_src.count(OLD_CODE) == 1,
        f"same argument as the quoting count, for MUTATION 4. count={gate_src.count(OLD_CODE)}",
    )

    o_work, o_remote, o_base, o_tip = build_odd(f"{TMP}/odd")
    install_gate(o_work)
    raw = git(o_work, "diff", "--name-only", f"{o_base}...{o_tip}").stdout
    r.check(
        "PREMISE: this scenario's git DOES quote, so the two legs below are controls",
        '"docs/caf\\303\\251/CLAUDE.md"' in raw and '"t\\303\\251 st.py"' in raw,
        f"the legs below assert that the SHIPPED path un-quotes what raw git quotes. If git "
        f"ever stops quoting here — a changed default, or a config reaching the scenario past "
        f"GIT_ENV — they would pass over a gate.py with no flag at all, and this row is what "
        f"says so instead. raw git returned {raw.split()!r}",
    )
    opush = push(o_work)
    o_rec = run_record(o_work)
    r.check(
        "a QUOTED and a SPACED changed path both reach the record as themselves",
        o_rec is not None and o_rec.get("files") == sorted([ODD_BANNED, ODD_SPACED]),
        f"TWO CAUSES, and the surviving entry names which. Octal-escaped and quoted: the "
        f"enumeration stopped passing `core.quotePath=false`. Fragmented into `té` and `st.py`: "
        f"it went back to splitting on all whitespace. got {(o_rec or {}).get('files')!r}",
    )
    r.check(
        "…and the BANNED-filename invariant fires on the quoted one, refusing the push",
        row_of(o_rec, "banned-filenames").get("state") == "blocked"
        and ODD_BANNED in row_of(o_rec, "banned-filenames").get("out", "")
        and opush.returncode != 0 and rev(o_remote, "refs/heads/main") == o_base,
        f"the consequence, and the reason the row above is not enough on its own: BANNED is "
        f"matched by BASENAME, and the basename of the quoted form is `CLAUDE.md\"` — trailing "
        f"quote — which is not in the set. The ban goes quiet on the one file it exists to "
        f"refuse and the remote advances. row={row_of(o_rec, 'banned-filenames').get('state')!r} "
        f"push={opush.returncode} ref_moved={rev(o_remote, 'refs/heads/main') != o_base}",
    )

    r.check(
        "…and lint SCOPES TO the non-ASCII Python file rather than skipping it",
        row_of(o_rec, "ruff").get("state") == "pass"
        and "1 changed Python file(s)" in row_of(o_rec, "ruff").get("why", ""),
        f"the SECOND cost the flag carries, and the two rows above cannot see it. A quoted "
        f"`té st.py` ends in `.py\"`, so `lint`'s `endswith('.py')` stops matching and ruff "
        f"records SKIPPED over changed Python — and a regression in lint SCOPING alone (in "
        f"`_in_change`, not in the enumeration) leaves the file list and the banned row exactly "
        f"as they are here. Without this row that regression is green. "
        f"ruff={row_of(o_rec, 'ruff').get('state')!r} why={row_of(o_rec, 'ruff').get('why')!r}",
    )

    def bad_base(work, base="nosuchref"):
        """gate.py run DIRECTLY on an unresolvable range -> (process, record). Direct because
        the hook validates its base before gate.py sees it (`git cat-file -e`, then a
        merge-base fallback guarded by `[ -n "$base" ]`), so the reachable caller is the
        documented hand-run form — `gate.py --base main`, which docs/AFK.md's autonomous
        stop-condition polls. A dedicated runs dir per call: `run_record` requires exactly
        one record, and the push above already wrote one."""
        runs = f"{work}/gate/runs-{base}"
        p = subprocess.run([sys.executable, f"{work}/gate/gate.py", "--base", base], cwd=work,
                           capture_output=True, text=True, timeout=300,
                           env={**os.environ, **GIT_ENV, "HEALBOT_GATE_RUNS": runs})
        found = glob.glob(f"{runs}/*.json")
        if len(found) != 1:
            return p, None
        with open(found[0], encoding="utf-8") as fh:
            return p, json.load(fh)

    bp, b_rec = bad_base(o_work)
    r.check(
        "a range git CANNOT resolve is ERROR at exit 3, and the record carries git's own text",
        bp.returncode == 3 and (b_rec or {}).get("verdict") == "error"
        and row_of(b_rec, "change-scope").get("state") == "error"
        and "fatal:" in row_of(b_rec, "change-scope").get("out", ""),
        f"UNMEASURED is not CLEAN — gate.py's own lattice says so and `home_paths` already "
        f"refused this on its enumeration. The `fatal:` clause is the diagnosability half: the "
        f"pre-fix code leaked git's message by printing it as the file list, so a fix that "
        f"merely swallowed the failure would trade one silent wrong answer for a silent right "
        f"one. exit={bp.returncode} verdict={(b_rec or {}).get('verdict')!r}",
    )
    r.check(
        "…and every change-scoped row says ERROR rather than SKIPPED or PASS",
        all(row_of(b_rec, n).get("state") == "error"
            for n in ("ruff", "tsgo", "oxlint", "banned-filenames"))
        and row_of(b_rec, "home-paths").get("state") == "pass",
        f"ALL FOUR, not a sample: the rows are the durable artifact, so a verdict of error over "
        f"rows still reading `no changed Python files`, `no changed fork/ TypeScript` and `none "
        f"in the change` would leave fabricated affirmative claims in the record. An earlier "
        f"draft of this row named four and read two, so a later narrowing of lint's unmeasured "
        f"branch to `ruff` alone would have passed it. `home-paths` is the NEGATIVE half: it "
        f"does not read the file list, so it must still measure — a run that reported "
        f"everything unmeasured would pass the first clause and fail here. "
        f"{ {n: row_of(b_rec, n).get('state') for n in ('ruff', 'tsgo', 'oxlint', 'banned-filenames', 'home-paths')} }",
    )

    # --- mutation 3: take the quoting flag back off the shared enumeration ---------------
    q_work, q_remote, q_base, q_tip = build_odd(f"{TMP}/mut-quote")
    install_gate(q_work, source=gate_src.replace(OLD_QUOTE, NEW_QUOTE))
    qpush = push(q_work)
    q_rec = run_record(q_work)
    r.check(
        "MUTATION 3: the quoted paths IS detected — the same predicate, red on the mutant",
        q_rec is not None and q_rec.get("files") != sorted([ODD_BANNED, ODD_SPACED])
        and any(f.startswith('"') for f in q_rec.get("files") or []),
        f"the same record predicate the live leg passed. got {(q_rec or {}).get('files')!r}",
    )
    r.check(
        "MUTATION 3: ...and the banned filename SAILS THROUGH in green",
        row_of(q_rec, "banned-filenames").get("state") == "pass"
        and qpush.returncode == 0 and rev(q_remote, "refs/heads/main") == q_tip,
        "a tracked CLAUDE.md reaches the remote past the invariant that exists to refuse it, "
        "and the record says `none in the change`: the outcome the flag exists to make "
        "impossible, reproduced on demand",
    )

    # --- mutation 4: stop reading the exit code, the way the pre-fix source did ----------
    e_work, _er, _eb, _et = build_odd(f"{TMP}/mut-code")
    install_gate(e_work, source=gate_src.replace(OLD_CODE, NEW_CODE))
    ep, e_rec = bad_base(e_work)
    r.check(
        "MUTATION 4: an unresolvable range exits 0 in green, git's error text as the file list",
        ep.returncode == 0 and (e_rec or {}).get("verdict") == "pass"
        and any("fatal:" in f for f in (e_rec or {}).get("files") or [])
        and row_of(e_rec, "banned-filenames").get("state") == "pass",
        f"the pre-fix behaviour restated: `sh` folds stderr into `out`, so the fatal text "
        f"becomes the change set, no pseudo-path ends in `.py` or is named in BANNED, and the "
        f"gate reports PASS at exit 0 over a scope it never enumerated — which is what the "
        f"autonomous stop-condition in docs/AFK.md polls. exit={ep.returncode} "
        f"verdict={(e_rec or {}).get('verdict')!r} files={(e_rec or {}).get('files')!r}",
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
