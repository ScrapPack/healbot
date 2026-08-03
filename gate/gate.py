"""The per-change gate: the layer between "the agent says it is done" and a phase review.

WHY THIS EXISTS. This project's review discipline is real and heavy — docs/REVIEW.md is 15
agents and 1,047 tool calls, docs/HARDEN.md is 67 — but it is PHASE-level and hand-driven.
Between an agent finishing an edit and one of those reviews there was nothing at all: no lint,
no drift check, no evidence, no verdict. Every gate in NEXT.md is a command somebody has to
remember. `fork/README.md` prescribes its drift check the same way, and MEASURED on 2026-07-31
that check had been silently RED — three `.DS_Store` files from a Finder visit had taken the
overlay from 17 files to 20 — because nothing ran it automatically.

WHAT IT IS NOT. It is not `gated-harness` (the external plugin at
~/.claude/plugins/cache/dev-harness/), and adopting that wholesale was considered and rejected:
its run worktree is cut at HEAD, and this repo gitignores `/opencode/`, `node_modules/` and
`.carryover/verified/venv/`, so such a worktree contains no checkout, no deps and no venv — it
cannot resolve a single `file:line` citation or run one probe. Its typed-outcome vocabulary is
worth borrowing and is borrowed below; its isolation model is actively wrong here.

THE ISOLATION CORRECTION, and it is the load-bearing design decision. Tier 1 needs NO worktree.
Every check in it is a pure read of the working tree, and the thing being guarded IS the working
tree, so copying it somewhere else buys nothing and costs the ability to see the checkout. A
worktree only becomes necessary at Tier 3, where a rig boots a real server and mutates state.

DETERMINISM IS MEASURED, NOT ASSUMED. The evidence hashes below are only meaningful if the same
tree produces the same bytes. TESTED 2026-07-31, 3 runs each on an unchanged tree: every Tier-1
probe was byte-identical BEFORE any canonicalization (the original three at ~0.6s for the tier;
probe_review_parse re-measured the same way when it joined, tier now ~0.7s).
That is why this gate can hash raw output and does not need `gated-harness`'s tolerance
machinery. Re-measure before adding a check whose output embeds a time, a path or a count of
anything the filesystem orders.
"""

import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFIED = f"{ROOT}/.carryover/verified"
PY = f"{VERIFIED}/venv/bin/python"
if not os.path.exists(PY) and os.path.exists(f"{VERIFIED}/venv/Scripts/python.exe"):
    # Windows venv layout. The POSIX name stays the default so a missing venv still reports
    # the same "executable not found" ERROR it always has.
    PY = f"{VERIFIED}/venv/Scripts/python.exe"
RUNS = os.environ.get("HEALBOT_GATE_RUNS", f"{ROOT}/gate/runs")

# Typed terminal states. Borrowed verbatim from gated-harness's lattice
# (harness/orchestrator.py:547-559), which is the one part of it that transfers cleanly: a check
# that SAID NO and a check that NEVER RAN are different facts, and collapsing them is how a
# suite reports green for a run that died. This project has the same defect on record —
# docs/CLONE.md, three probes exiting 0 having proven nothing.
PASS = "pass"          # every check ran and every check agreed
BLOCKED = "blocked"    # a check ran and said no — a real finding, escalate to a human
ERROR = "error"        # a check could not run — NOT the same as passing, and not the same as blocked
SKIPPED = "skipped"    # deliberately not run (out of scope for the changed files, or a paid tier)
# The fifth term, added 2026-08-01 for tier2. SKIPPED above is a scoping decision made BEFORE
# anything ran — nothing about the machine could change it. This one is made by a check that
# reached its own line, found the machine missing a fact it named in advance (`rig.Env`), and
# declined to claim a measurement it could not take. It is not PASS: the claim is unmeasured.
# It is not BLOCKED: nothing said no. It is not ERROR: the run was fine, this machine is not
# the one that holds the evidence. Keeping it separate is the same argument as ERROR-vs-PASS —
# a run that measured 30 of 33 things must not report identically to one that measured 33.
DECLARED = "declared-skip"


def sh(cmd, cwd=ROOT, timeout=900, input=None):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, input=input)
        return {"cmd": cmd, "code": p.returncode, "out": p.stdout + p.stderr, "secs": time.time() - t0}
    except FileNotFoundError as exc:
        return {"cmd": cmd, "code": None, "out": f"executable not found: {exc}", "secs": time.time() - t0}
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "code": None, "out": f"TIMEOUT after {timeout}s", "secs": time.time() - t0}


def changed_files(base, head=None):
    """Files this change touches. `base` of None means the working tree (staged + unstaged +
    untracked); otherwise a diff of base...head, where `head` names the pushed tip (default
    HEAD). A push gated from a checkout parked on another branch MUST pass head, or the
    range collapses to whatever that checkout has: run 20260802-184854 gated a merge push
    as ZERO files because its HEAD was an ancestor of the base. Untracked files stay
    included: a gate that cannot see a new file cannot guard the change that adds one."""
    if base:
        out = sh(["git", "diff", "--name-only", f"{base}...{head or 'HEAD'}"])["out"]
    else:
        tracked = sh(["git", "diff", "--name-only", "HEAD"])["out"]
        untracked = sh(["git", "ls-files", "--others", "--exclude-standard"])["out"]
        out = tracked + untracked
    return sorted({ln.strip() for ln in out.splitlines() if ln.strip()})


# ==========================================================================================
# TIER 1 — always on. Free, static, fast, and MEASURED byte-stable.
# ==========================================================================================
# Deliberately NOT the whole free suite. The rest is Tier 2, owned by tier2.py: probes that boot
# a TUI or a server or read living state, with timing-bearing output — run at phase boundaries,
# never per change. A per-change gate that takes minutes is a gate people route around.
TIER1 = [
    ("rig-contract", [PY, "probe_rig_contract.py"], VERIFIED,
     "every rig still reports failure as failure — floors, guards, verdict exits, no box-counting"),
    ("citations", [PY, "probe_citations.py"], VERIFIED,
     "every file:line citation in the docs still resolves to a real, non-blank line"),
    ("twin", [PY, "probe_twin.py"], VERIFIED,
     "the fork/ overlay and the opencode/ checkout have not drifted apart"),
    ("review-parse", [PY, "probe_review_parse.py"], VERIFIED,
     "the review stage's reply parser still holds all three live-failure shapes"),
]


def tier1():
    rows = []
    for name, cmd, cwd, why in TIER1:
        r = sh(cmd, cwd=cwd)
        rows.append({
            "check": name, "why": why, "cmd": f"{os.path.relpath(cmd[0], ROOT)} {' '.join(cmd[1:])}", "cwd": os.path.relpath(cwd, ROOT),
            "code": r["code"], "secs": round(r["secs"], 2),
            # The hash is the evidence. It is over RAW output because determinism was measured
            # rather than hoped for; if a check is ever added whose output is not byte-stable,
            # this is the line that starts lying.
            "sha256": hashlib.sha256(r["out"].encode()).hexdigest(),
            "tail": r["out"].strip().splitlines()[-1:] or [""],
            "state": PASS if r["code"] == 0 else (ERROR if r["code"] is None else BLOCKED),
            "out": r["out"],
        })
    return rows


# ==========================================================================================
# LINT — scoped to what changed
# ==========================================================================================
def lint(files, head=None):
    """Lint only the changed files. A repo-wide lint on a mixed Python/TypeScript/Markdown tree
    reports pre-existing findings the change did not cause, and a gate that blames you for other
    people's lint is a gate you learn to ignore.

    With `head` (a pushed-range run), existence and CONTENT both come from the pushed tip,
    never the working tree: the checkout the hook runs in can sit on another branch and hold
    none of the pushed files (the 20260802-184854 mis-scope), and linting whatever the tree
    happens to have would attest bytes nobody is pushing."""
    rows = []
    py = [f for f in files if f.endswith(".py") and _in_change(f, head)]
    ts = [f for f in files if f.endswith((".ts", ".tsx")) and _in_change(f, head)]

    if py:
        r = _ruff(py, head)
        rows.append({"check": "ruff", "why": f"{len(py)} changed Python file(s)", "cmd": "ruff check",
                     "code": r["code"], "secs": round(r["secs"], 2),
                     "sha256": hashlib.sha256(r["out"].encode()).hexdigest(),
                     "tail": r["out"].strip().splitlines()[-1:] or ["clean"],
                     "state": PASS if r["code"] == 0 else (ERROR if r["code"] is None else BLOCKED),
                     "out": r["out"]})
    else:
        rows.append({"check": "ruff", "why": "no changed Python files", "state": SKIPPED,
                     "code": None, "secs": 0.0, "sha256": "", "tail": [""], "out": ""})

    # TypeScript only matters when the change touches the fork overlay, and it must be run
    # against the CHECKOUT — `tsgo -p` needs the real tsconfig and node_modules, which exist
    # only there (`/opencode/` is gitignored). tsgo + oxlint are the two build gates the
    # phases ran by hand through Phase 12; since the 2026-07-31 NEXT.md freeze this gate is
    # their only owner, so removing either from here removes it from the project.
    if any(f.startswith("fork/") for f in ts):
        oc = f"{ROOT}/opencode"
        # tsgo and oxlint can only read the CHECKOUT, so on a pushed-range run their verdict
        # speaks for the push only when every pushed fork/ blob byte-matches its checkout
        # twin. A mismatch (or a missing twin) leaves the claim unmeasured: ERROR, never a
        # quiet lint of the wrong bytes.
        stale = _stale_twins([f for f in ts if f.startswith("fork/")], head) if head else []
        if stale:
            for name in ("tsgo", "oxlint"):
                rows.append({"check": name,
                             "why": "pushed fork/ TS does not byte-match the checkout twin "
                                    f"({', '.join(stale)}); sync per fork/README.md and re-push",
                             "state": ERROR, "code": None, "secs": 0.0, "sha256": "", "tail": [""], "out": ""})
        elif os.path.isdir(f"{oc}/node_modules"):
            r = sh([f"{oc}/node_modules/.bin/tsgo", "--noEmit", "-p", "packages/tui/tsconfig.json"], cwd=oc)
            rows.append({"check": "tsgo", "why": "changed fork/ TypeScript", "cmd": "tsgo --noEmit",
                         "code": r["code"], "secs": round(r["secs"], 2),
                         "sha256": hashlib.sha256(r["out"].encode()).hexdigest(),
                         "tail": r["out"].strip().splitlines()[-1:] or ["clean"],
                         "state": PASS if r["code"] == 0 else (ERROR if r["code"] is None else BLOCKED),
                         "out": r["out"]})
            # The overlay mirrors the checkout (probe_twin.py verifies all 17 files), so a
            # changed fork/<path> lints as <path> in the checkout. oxlint exits 0 on
            # warnings-only (the recorded baseline is 3 warnings on healbot.tsx), nonzero on
            # errors, which maps onto the same state lattice as every other row.
            mapped = [f[len("fork/"):] for f in ts
                      if f.startswith("fork/") and os.path.exists(f"{oc}/{f[len('fork/'):]}")]
            if mapped:
                r = sh([f"{oc}/node_modules/.bin/oxlint", *mapped], cwd=oc)
                rows.append({"check": "oxlint", "why": f"{len(mapped)} changed fork/ TS file(s)",
                             "cmd": "oxlint", "code": r["code"], "secs": round(r["secs"], 2),
                             "sha256": hashlib.sha256(r["out"].encode()).hexdigest(),
                             "tail": r["out"].strip().splitlines()[-1:] or ["clean"],
                             "state": PASS if r["code"] == 0 else (ERROR if r["code"] is None else BLOCKED),
                             "out": r["out"]})
            else:
                rows.append({"check": "oxlint", "why": "changed fork/ TS has no checkout twin — "
                                                       "probe_twin should be red; investigate",
                             "state": ERROR, "code": None, "secs": 0.0, "sha256": "", "tail": [""], "out": ""})
        else:
            rows.append({"check": "tsgo", "why": "fork/ TS changed but the checkout has no node_modules — "
                                                "see fork/README.md to reconstitute it",
                         "state": ERROR, "code": None, "secs": 0.0, "sha256": "", "tail": [""], "out": ""})
            rows.append({"check": "oxlint", "why": "fork/ TS changed but the checkout has no node_modules — "
                                                  "see fork/README.md to reconstitute it",
                         "state": ERROR, "code": None, "secs": 0.0, "sha256": "", "tail": [""], "out": ""})
    else:
        rows.append({"check": "tsgo", "why": "no changed fork/ TypeScript", "state": SKIPPED,
                     "code": None, "secs": 0.0, "sha256": "", "tail": [""], "out": ""})
        rows.append({"check": "oxlint", "why": "no changed fork/ TypeScript", "state": SKIPPED,
                     "code": None, "secs": 0.0, "sha256": "", "tail": [""], "out": ""})
    return rows


# ==========================================================================================
# BANNED FILENAMES — the repo's own invariant, enforced instead of remembered
# ==========================================================================================
BANNED = {"AGENTS.md", "CLAUDE.md", "CONTEXT.md", "SKILL.md"}


def banned_names(files):
    """HARNESS.md:9-13 bans four filenames anywhere in the tree: the first three auto-ingest into
    every session's context (session/instruction.ts), and SKILL.md collides with opencode's skill
    glob — which matters more than tidiness, because a SKILL.md body containing !`cmd`
    shell-executes on slash-invoke with no permission check (harness/env.sh:63-68, re-verified
    2026-07-31 against 1.18.5, the installed 1.18.0 and upstream 1.18.10 — still unfixed).

    The ban held for twelve phases on memory alone. This makes it a check."""
    hits = [f for f in files if os.path.basename(f) in BANNED]
    return {
        "check": "banned-filenames", "why": "HARNESS.md:9-13 — auto-ingest and the skill-glob shell hole",
        "cmd": "static", "code": 1 if hits else 0, "secs": 0.0,
        "sha256": hashlib.sha256(("\n".join(hits)).encode()).hexdigest(),
        "tail": [f"FOUND: {hits}" if hits else "none in the change"],
        "state": BLOCKED if hits else PASS,
        "out": "\n".join(hits),
    }


# ==========================================================================================
# HOME PATHS — public-repo invariant: live files carry no machine-anchored home path
# ==========================================================================================
HOME_MARKS = ("/Users/", "/home/", ":\\Users\\", ":/Users/")
# The recorded corpus is exempt BY PATH, not by pattern: the session DBs, A/B run records and
# server logs under hb/ are measured artifacts of runs on a named machine. Rewriting them to
# redact is an owner decision about evidence, not a lint's call — and git history retains
# every pre-scrub byte anyway, so the exemption costs nothing history has not already spent.
# Everything OUTSIDE it must derive its paths (env.sh HARNESS_ROOT, doctor.py ROOT, the
# legacy rigs' __file__ pattern) or placeholder them (the plist's install-time render,
# AFK.md's $SCRATCH).
HOME_EXEMPT = (".carryover/verified/hb/",)


def _home_anchored(line):
    """True when the line carries a real machine-anchored home path. A mark hit counts only
    when the next char is alphanumeric — /Users/<you>, /c/Users/... and $-placeholders
    pass. For the slash-rooted marks, the char before must not be a word or relative-path
    continuation (./home/footer imports, api/Users/123 routes) — EXCEPT the single-letter
    drive segment (/c/Users/<name>, the MSYS form harness/env.sh:32-39 documents), which
    counts. A bare '/' before also counts: file:///Users/<name> is an anchored path. The
    drive-colon marks skip the before-guard; their preceder is the drive letter. The first
    shipped draft excluded '/' and all alpha preceders, which passed exactly those two real
    shapes — the 2026-08-02 review's finding, re-derived here."""
    for mark in HOME_MARKS:
        i = line.find(mark)
        while i >= 0:
            after = line[i + len(mark):i + len(mark) + 1]
            if after.isalnum():
                # i == 0 must short-circuit: before would be "", and `"" in <str>` is
                # always True, which silently un-anchors every line-start path. Caught by
                # the truth-table matrix, missed by two ad-hoc poison controls whose lines
                # happened to carry a leading space.
                if mark[0] == ":" or i == 0:
                    return True
                before = line[i - 1]
                msys_drive = before.isalpha() and line[i - 2:i - 1] == "/"
                if msys_drive or not (before.isalnum() or before in "._-~\\"):
                    return True
            i = line.find(mark, i + 1)
    return False


# Standing negative controls for _home_anchored, validated before every scan: a predicate
# whose truth table drifts must ERROR the check rather than scan with it. This exists
# because the table already caught a real one — the i == 0 empty-`before` bug above — that
# two ad-hoc poison controls missed. Control strings are assembled at runtime from split
# literals so this file's own source never carries an anchored path, keeping the scan
# self-applicable with no self-exemption (a guard that exempts itself is the defect
# probe_rig_contract.py hunts).
_J = "".join
_MATRIX = (
    (_J(("/Use", "rs/name/x")), True),           # line-start anchor (the i == 0 bug)
    (_J(("cd /Use", "rs/name/repo")), True),
    (_J(('PATH="/Use', 'rs/name/bin"')), True),
    (_J(("/c/Use", "rs/name/x")), True),         # MSYS drive form (review finding)
    (_J(("file:///Use", "rs/name/db")), True),   # file URL (review finding)
    (_J(("C:\\Use", "rs\\name\\x")), True),
    (_J(("C:/Use", "rs/name/x")), True),
    (_J(("/ho", "me/name/x")), True),
    (_J(('import x from "./ho', 'me/footer"')), False),   # relative import
    (_J(("api/Use", "rs/123")), False),                   # route segment
    (_J(("shaped (/c/Use", "rs/...)")), False),           # doc example, placeholder dots
    (_J(("/Use", "rs/<you>/x")), False),                  # placeholder segment
    (_J(("~/ho", "me/x")), False),
    (_J(("path/to/ho", "me/x")), False),
)


def home_paths():
    """Full-tree scan, not change-scoped: the invariant is about the tree, and a
    change-scoped check would have grandfathered exactly the files this rule exists for.
    Untracked-unignored files are included for the same reason changed_files includes them
    (gate.py:78-91): a gate that cannot see a new file cannot guard the change adding one —
    the first draft scanned `git ls-files` alone and was blind to this session's own
    untracked LICENSE while it sat in the working tree. The corpus exemption is BY PATH
    only; a stray .db outside it is exactly the artifact this check should name.
    Byte-stable by construction: hits are sorted and content-derived, nothing embeds a time
    or a directory order. Fire capability is OBSERVED, not assumed: a poisoned tracked file
    (/Users/<x> shape with a real segment) went BLOCKED and the cleaned tree PASS with the
    shipped predicate, same session (2026-08-02)."""
    t0 = time.time()
    broken = [s for s, want in _MATRIX if _home_anchored(s) != want]
    if broken:
        return {
            "check": "home-paths",
            "why": "predicate truth table no longer holds — fix _home_anchored before trusting any scan",
            "cmd": "static", "code": None, "secs": round(time.time() - t0, 2),
            "sha256": hashlib.sha256("\n".join(broken).encode()).hexdigest(),
            "tail": [f"{len(broken)} matrix row(s) broken, first: {broken[0]!r}"],
            "state": ERROR, "out": "\n".join(repr(s) for s in broken),
        }
    ls = sh(["git", "ls-files", "-z"])
    others = sh(["git", "ls-files", "-z", "--others", "--exclude-standard"])
    if ls["code"] != 0 or others["code"] != 0 or not ls["out"].strip("\0"):
        # A failed (or empty) enumeration is an UNMEASURED tree, not a clean one — reporting
        # PASS here is the ERROR-vs-PASS collapse the state lattice above exists to prevent.
        # The empty-list guard is the same claim: a healbot checkout with zero tracked files
        # is not a scanned tree, it is a broken `git ls-files`. Carry only the FAILING
        # command's output: when one call succeeds, its NUL-joined file list would bury the
        # actual failure text in the record and in main()'s tail rendering.
        fail = [r for r in (ls, others) if r["code"] != 0] or [ls]
        diag = "\n".join(r["out"] for r in fail)
        return {
            "check": "home-paths",
            "why": "git ls-files failed — the tree could not be enumerated, nothing was measured",
            "cmd": "static", "code": None, "secs": round(time.time() - t0, 2),
            "sha256": hashlib.sha256(diag.encode()).hexdigest(),
            "tail": [f"ls code={ls['code']} others code={others['code']}"],
            "state": ERROR, "out": diag,
        }
    out = ls["out"] + others["out"]
    hits = []
    for rel in out.split("\0"):
        if not rel or rel.startswith(HOME_EXEMPT):
            continue
        try:
            with open(f"{ROOT}/{rel}", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError:
            continue
        for ln, line in enumerate(text.split("\n"), 1):
            if _home_anchored(line):
                hits.append(f"{rel}:{ln} {line.strip()[:80]}")
    hits.sort()
    return {
        "check": "home-paths", "why": "public repo — no machine-anchored home path outside the recorded corpus",
        "cmd": "static", "code": 1 if hits else 0, "secs": round(time.time() - t0, 2),
        "sha256": hashlib.sha256(("\n".join(hits)).encode()).hexdigest(),
        "tail": [f"{len(hits)} hit(s), first: {hits[0]}" if hits else "clean"],
        "state": BLOCKED if hits else PASS,
        "out": "\n".join(hits),
    }


# ==========================================================================================
# PUSHED-RANGE CONTENT — a range run reads blobs at the pushed tip, not the working tree
# ==========================================================================================
def _in_change(path, head):
    """Existence for lint scoping: at the pushed tip when gating a range, else in the tree.
    Filters deletions either way; with `head` it also KEEPS files the checkout does not
    hold, which is the point (see changed_files)."""
    if head:
        return sh(["git", "cat-file", "-e", f"{head}:{path}"])["code"] == 0
    return os.path.exists(f"{ROOT}/{path}")


def _ruff(py, head):
    """One sh()-shaped result for the ruff row. Working-tree mode is the one command it has
    always been. Range mode feeds each pushed blob through stdin, with --stdin-filename
    keeping both the reported path and ruff's config discovery identical to a tree run;
    concatenation is deterministic because `py` arrives sorted."""
    if not head:
        return sh(["ruff", "check", "--no-cache", *py])
    outs, codes, secs = [], [], 0.0
    for f in py:
        blob = sh(["git", "show", f"{head}:{f}"])
        if blob["code"] != 0:
            # An unreadable blob is an unmeasured claim, never an empty file to lint clean
            # (sh() folds stderr into out, so git's error text would otherwise be the
            # "source"): ERROR, same as every other check that could not run.
            return {"cmd": f"git show {head}:{f}", "code": None,
                    "out": blob["out"], "secs": secs + blob["secs"]}
        r = sh(["ruff", "check", "--no-cache", "--stdin-filename", f, "-"],
               input=blob["out"])
        outs.append(r["out"])
        codes.append(r["code"])
        secs += r["secs"]
    code = None if any(c is None for c in codes) else max(codes)
    return {"cmd": "ruff check --stdin-filename", "code": code, "out": "".join(outs), "secs": secs}


def _stale_twins(fork_ts, head):
    """The pushed fork/ blobs whose checkout twin does not byte-match (a missing twin
    counts). Agreement is what lets a checkout lint's verdict speak for the push."""
    stale = []
    for f in fork_ts:
        try:
            with open(f"{ROOT}/opencode/{f[len('fork/'):]}", encoding="utf-8") as fh:
                same = fh.read() == sh(["git", "show", f"{head}:{f}"])["out"]
        except OSError:
            same = False
        if not same:
            stale.append(f)
    return stale


# ==========================================================================================
def main():
    args = sys.argv[1:]
    base = None
    if "--base" in args:
        base = args[args.index("--base") + 1]
    head = None
    if "--head" in args:
        head = args[args.index("--head") + 1]
    if head and not base:
        print("gate.py: --head names a pushed tip and only scopes a --base range", file=sys.stderr)
        return 3
    quiet = "--quiet" in args

    files = changed_files(base, head)
    scope = f" vs {base}...{head}" if head else (f" vs {base}" if base else " in the working tree")
    print(f"== healbot gate ==  {len(files)} changed file(s)" + scope, flush=True)
    for f in files[:12]:
        print(f"   {f}", flush=True)
    if len(files) > 12:
        print(f"   … and {len(files) - 12} more", flush=True)

    # What each half of the run attests. Tier 1 and the invariants read the CHECKOUT tree;
    # lint reads the pushed blobs. When the two commits differ the split is worth a line in
    # the terminal, not just a pair of fields in the record.
    tree = sh(["git", "rev-parse", "--short", "HEAD"])["out"].strip()
    gated = sh(["git", "rev-parse", "--short", head])["out"].strip() if head else tree
    if head and gated != tree:
        print(f"   NOTE: gating {gated} from a checkout at {tree}: tier-1 probes and the "
              "invariant scans read the checkout tree; lint reads the pushed blobs.", flush=True)

    rows = []
    print("\n-- tier 1: static, free, always on --", flush=True)
    rows += tier1()
    print("\n-- lint: scoped to the change --", flush=True)
    rows += lint(files, head)
    print("\n-- invariants --", flush=True)
    rows.append(banned_names(files))
    rows.append(home_paths())

    for r in rows:
        mark = {PASS: "ok  ", BLOCKED: "BLOCK", ERROR: "ERROR", SKIPPED: "skip"}[r["state"]]
        print(f"  [{mark}] {r['check']:<18} {r['secs']:>5.1f}s  {r['tail'][0][:88]}", flush=True)
        if not quiet and r["state"] in (BLOCKED, ERROR) and r["out"]:
            for ln in r["out"].strip().splitlines()[-15:]:
                print(f"          | {ln}", flush=True)

    blocked = [r for r in rows if r["state"] == BLOCKED]
    errored = [r for r in rows if r["state"] == ERROR]
    verdict = BLOCKED if blocked else (ERROR if errored else PASS)

    # The run record. This is the evidence artifact — the thing that survives the terminal
    # scrollback and can be attached to a PR or read by whoever picks the work up. gated-harness
    # keeps only output[-300:] and attaches nothing to the PR; the whole output is kept here
    # because a truncated tail is exactly what you do not have when you need to know why.
    os.makedirs(RUNS, exist_ok=True)
    tag = time.strftime("%Y%m%d-%H%M%S")
    rec = {
        # `head` is the tip of the GATED range (the pushed sha on a hook run); `tree` is the
        # checkout the tier-1 probes read. The 20260802-184854 record is why they are two
        # fields: head silently meant `tree`, and the one place they differed is the one
        # place the scoping broke.
        "tag": tag, "verdict": verdict, "base": base, "files": files,
        "head": gated, "tree": tree,
        "checks": rows,
    }
    path = f"{RUNS}/{tag}.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=2)

    print(f"\n== {verdict.upper()} ==", flush=True)
    if blocked:
        print("  a check ran and said no — this needs a human decision, not a retry:", flush=True)
        for r in blocked:
            print(f"    - {r['check']}: {r['why']}", flush=True)
    if errored:
        print("  a check COULD NOT RUN. This is not a pass — the claim it makes is unmeasured:", flush=True)
        for r in errored:
            print(f"    - {r['check']}: {r['why']}", flush=True)
    print(f"  evidence: {os.path.relpath(path, ROOT)}", flush=True)
    print("  NOT run by this gate: the tier-2 free probes (gate/tier2.py — phase boundaries) "
          "and every verify_* rig (tier 3, PAID — owner's go required).", flush=True)

    # Distinct exit codes so a caller can branch on the KIND of failure, which is the whole point
    # of typing the states. 0 pass / 2 blocked / 3 error.
    return {PASS: 0, BLOCKED: 2, ERROR: 3}[verdict]


if __name__ == "__main__":
    sys.exit(main())
