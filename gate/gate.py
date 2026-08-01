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


def sh(cmd, cwd=ROOT, timeout=900):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return {"cmd": cmd, "code": p.returncode, "out": p.stdout + p.stderr, "secs": time.time() - t0}
    except FileNotFoundError as exc:
        return {"cmd": cmd, "code": None, "out": f"executable not found: {exc}", "secs": time.time() - t0}
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "code": None, "out": f"TIMEOUT after {timeout}s", "secs": time.time() - t0}


def changed_files(base):
    """Files this change touches. `base` of None means the working tree (staged + unstaged +
    untracked); otherwise a diff against that ref.

    Untracked files are included deliberately. The project's own history is the argument: the
    A/B harness, the refusal corpus and this gate were all untracked while being written, and a
    gate that cannot see a new file cannot guard the change that adds one."""
    if base:
        out = sh(["git", "diff", "--name-only", f"{base}...HEAD"])["out"]
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
            "check": name, "why": why, "cmd": " ".join(cmd), "cwd": os.path.relpath(cwd, ROOT),
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
def lint(files):
    """Lint only the changed files. A repo-wide lint on a mixed Python/TypeScript/Markdown tree
    reports pre-existing findings the change did not cause, and a gate that blames you for other
    people's lint is a gate you learn to ignore."""
    rows = []
    py = [f for f in files if f.endswith(".py") and os.path.exists(f"{ROOT}/{f}")]
    ts = [f for f in files if f.endswith((".ts", ".tsx")) and os.path.exists(f"{ROOT}/{f}")]

    if py:
        r = sh(["ruff", "check", "--no-cache", *py])
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
        if os.path.isdir(f"{oc}/node_modules"):
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
    shell-executes on slash-invoke with no permission check (harness/env.sh:48-53, re-verified
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
def main():
    args = sys.argv[1:]
    base = None
    if "--base" in args:
        base = args[args.index("--base") + 1]
    quiet = "--quiet" in args

    files = changed_files(base)
    print(f"== healbot gate ==  {len(files)} changed file(s)"
          + (f" vs {base}" if base else " in the working tree"), flush=True)
    for f in files[:12]:
        print(f"   {f}", flush=True)
    if len(files) > 12:
        print(f"   … and {len(files) - 12} more", flush=True)

    rows = []
    print("\n-- tier 1: static, free, always on --", flush=True)
    rows += tier1()
    print("\n-- lint: scoped to the change --", flush=True)
    rows += lint(files)
    print("\n-- invariants --", flush=True)
    rows.append(banned_names(files))

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
        "tag": tag, "verdict": verdict, "base": base, "files": files,
        "head": sh(["git", "rev-parse", "--short", "HEAD"])["out"].strip(),
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
