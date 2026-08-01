"""Tier 2 — the free probes the per-change gate deliberately does not run.

WHAT LIVES HERE. Everything in `.carryover/verified/probe_*.py` that is not in gate.py's
TIER1, discovered by subtraction at run time so a new probe joins this tier by existing —
`--list` enumerates today's membership; FLOOR below owns the count. The tier's character,
measured at its 2026-07-31 birth: some probes boot a TUI or an opencode server (3-99 s
each, minutes together), others are sub-second but read LIVING state (the live
opencode.db, the machine's Claude Code transcripts), and the rest are fast pure checks
that simply carry no byte-stability measurement. Output moves as the machine does.

WHY IT IS NOT TIER 1, in the gate's own terms. Tier 1 hashes raw output because
byte-stability was MEASURED (gate.py module docstring). These probes fail that bar by
construction — elapsed times, live-corpus counts, boot ordering — so a hash here would
claim a determinism nobody measured. The rows below carry NO sha256 field, and that
absence is the honesty, not an oversight. The typed states are the same lattice as
gate.py's: a probe that said no (BLOCKED) and a probe that could not run (ERROR) are
different facts, and neither is PASS.

WHEN IT RUNS. At phase boundaries — a phase close, a session handoff, before anything
paid — never per change (a gate that takes minutes is a gate people route around; see
gate.py's TIER1 comment). The trigger is the phase-close skill
(harness/skills/phase-close.md); gate.py names this file in its every-run footer so the
reminder is structural, and a phase that closed without a `-tier2.json` record in
gate/runs/ is visible by absence — the same absence-is-a-signal property the publish
flow relies on.

    .carryover/verified/venv/bin/python gate/tier2.py          # run the tier
    .carryover/verified/venv/bin/python gate/tier2.py --list   # show what would run
"""

import ast
import glob
import json
import os
import sys
import time

from gate import BLOCKED, ERROR, PASS, PY, ROOT, RUNS, TIER1, VERIFIED, sh

# A glob that matches nothing is the docs/CLONE.md defect — "everything passed" and "almost
# nothing ran" reporting identically. The floor makes that collapse loud: discovering fewer
# probes than this is ERROR (the tier could not run), never a quiet green. It is a MINIMUM,
# not an equality — adding a probe is safe; retiring one means lowering this number in the
# same change, deliberately. (13 at birth; 14 at probe_pool.py; 15 at probe_arm_factory.py.)
FLOOR = 15

# Per-probe watchdog, sized ABOVE the ~20-minute hazard on record: wait_for's deadline is
# checked only between calls to fn, and Api.__call__ defaults to timeout=900, so a probe's
# own internal budget can be held ~15 minutes before its honest red surfaces (HARNESS.md
# "Traps"). A tighter cap here would convert that slow red into a TIMEOUT error.
PROBE_TIMEOUT = 1500


def discover():
    tier1 = {os.path.basename(cmd[1]) for _, cmd, _, _ in TIER1}
    probes = sorted(os.path.basename(p) for p in glob.glob(f"{VERIFIED}/probe_*.py"))
    return [p for p in probes if p not in tier1]


def first_doc_line(name):
    """The probe's own docstring headline is its `why` — one owner for that prose, here
    a pointer. Thirteen hand-copied summaries would be thirteen rot surfaces."""
    try:
        with open(f"{VERIFIED}/{name}", encoding="utf-8") as fh:
            doc = ast.get_docstring(ast.parse(fh.read())) or ""
    except (OSError, SyntaxError):
        return "(docstring unreadable)"
    return doc.strip().splitlines()[0][:160] if doc.strip() else "(no docstring)"


def write_record(rec):
    os.makedirs(RUNS, exist_ok=True)
    path = f"{RUNS}/{rec['tag']}-tier2.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=2)
    return path


def main():
    probes = discover()

    if "--list" in sys.argv[1:]:
        print(f"tier 2 = probe_*.py minus gate.py TIER1 — {len(probes)} probe(s), floor {FLOOR}")
        for p in probes:
            print(f"  {p:<28} {first_doc_line(p)}")
        return 0

    tag = time.strftime("%Y%m%d-%H%M%S")
    head = sh(["git", "rev-parse", "--short", "HEAD"])["out"].strip()
    print(f"== healbot tier 2 ==  {len(probes)} probe(s) discovered, floor {FLOOR}", flush=True)

    if len(probes) < FLOOR:
        # The tier did not run. Write the evidence of THAT, then exit as an error — the
        # claims these probes make are unmeasured, which is not the same as upheld.
        rec = {"tag": tag, "kind": "tier2", "verdict": ERROR, "head": head,
               "floor": FLOOR, "discovered": probes, "checks": []}
        path = write_record(rec)
        print(f"== {ERROR.upper()} ==  discovery found {len(probes)} probe(s), floor is {FLOOR} —"
              f" the tier COULD NOT RUN (wrong tree? renamed dir?)", flush=True)
        print(f"  evidence: {os.path.relpath(path, ROOT)}", flush=True)
        return 3

    rows = []
    for p in probes:
        r = sh([PY, p], cwd=VERIFIED, timeout=PROBE_TIMEOUT)
        row = {
            "check": p, "why": first_doc_line(p), "cmd": f"{os.path.relpath(PY, ROOT)} {p}",
            "cwd": os.path.relpath(VERIFIED, ROOT),
            "code": r["code"], "secs": round(r["secs"], 2),
            "tail": r["out"].strip().splitlines()[-1:] or [""],
            "state": PASS if r["code"] == 0 else (ERROR if r["code"] is None else BLOCKED),
            "out": r["out"],
        }
        rows.append(row)
        mark = {PASS: "ok  ", BLOCKED: "BLOCK", ERROR: "ERROR"}[row["state"]]
        print(f"  [{mark}] {p:<28} {row['secs']:>6.1f}s  {row['tail'][0][:80]}", flush=True)

    blocked = [r for r in rows if r["state"] == BLOCKED]
    errored = [r for r in rows if r["state"] == ERROR]
    verdict = BLOCKED if blocked else (ERROR if errored else PASS)

    rec = {"tag": tag, "kind": "tier2", "verdict": verdict, "head": head,
           "floor": FLOOR, "discovered": probes, "checks": rows}
    path = write_record(rec)

    print(f"\n== {verdict.upper()} ==", flush=True)
    if blocked:
        print("  a probe ran and said no — read its record before calling this drift or defect:", flush=True)
        for r in blocked:
            print(f"    - {r['check']}: {r['tail'][0][:100]}", flush=True)
    if errored:
        print("  a probe COULD NOT RUN — its claim is unmeasured, which is not a pass:", flush=True)
        for r in errored:
            print(f"    - {r['check']}: {r['tail'][0][:100]}", flush=True)
    print(f"  evidence: {os.path.relpath(path, ROOT)}", flush=True)
    print("  NOT run here: Tier 1 + lint (gate.py, every push) and every verify_* rig "
          "(tier 3, PAID — owner's go required).", flush=True)
    return {PASS: 0, BLOCKED: 2, ERROR: 3}[verdict]


if __name__ == "__main__":
    sys.exit(main())
