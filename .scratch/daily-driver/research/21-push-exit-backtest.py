"""What would a checkout predicate have done to the review fix-chains that already happened?

Ticket 21's evidence. The proposed predicate is a PURE FUNCTION of (review record, push
class), so this is a deterministic replay over records already on disk, not a simulation of
model behaviour. Nothing here spends credits and nothing here calls a model.

    venv/bin/python .scratch/daily-driver/research/21-push-exit-backtest.py

THE ONE APPROXIMATION, stated up front. The shipped predicate reads a declared
`Review-chain:` commit trailer to know whether a push is opening new surface or closing a
prior review. No such trailer exists in history, so this replay infers the class from the
commit subject via CLOSING below. That regex is a PROXY and it is not exact: an earlier
version required the plural "findings" and silently filed every singular "review finding
from the X push" as new surface, which moved the headline rate by more than 20 points before
it was caught by reading the classification instead of trusting it. `--show-class` prints
every subject with its class so the next reader can audit it the same way. One subject is
known to classify wrongly today ("the second 3441813 finding": three tokens sit between
"the" and "finding"), and hybrid commits that do substantive work AND close findings have no
correct answer at all. Treat the rates as accurate to a few points, not to the digit.

WHY THE RECORDS ARE READ FROM A PATH RATHER THAN FOUND. The `gate/runs/` rule in .gitignore
means a worktree's own copy is empty, so a replay run from a pool slot would otherwise print
a confident zero. Empty input REFUSES here for the same reason tier2.py
carries a discovery floor: "found nothing" must never render as "found nothing wrong".
"""

import argparse
import collections
import glob
import json
import os
import re
import subprocess
import sys

# Ticket 12 narrowed the path escalation to these three: the things that can make the
# measurement lie. Plain `harness/` was dropped there because it fired on 25 of the last 60
# commits. Whether this narrowed set is itself too wide is ticket 21's question.
ESCALATION = ("gate/", "fork/", ".carryover/verified/probe_")

# A push whose commit subject matches this is CLOSING a prior review rather than opening new
# surface. See the approximation note in the module docstring before trusting it.
CLOSING = re.compile(
    r"^(review\s+)?findings?\s+from\b"      # "review finding(s) from the X push"
    r"|^pre-push:"                          # "pre-push: <repair>"
    r"|^the\s+(\S+\s+){1,3}findings?\b"     # "the three findings", "the second X finding"
    r"|^the\s+\S+\s+finding,",              # "the fifteenth finding, found while..."
    re.I)


def subject(repo, sha):
    """The commit subject, or None when the sha is not in this object store. Every record
    written before 2026-08-03 predates the hook's --head argument and carries no head at
    all; those are absent from the window rather than lost."""
    p = subprocess.run(["git", "log", "-1", "--format=%s", sha],
                       cwd=repo, capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def load(repo, runs):
    """Every review record that reached a verdict AND names a resolvable head commit."""
    paths = sorted(glob.glob(f"{runs}/*-review.json"))
    if not paths:
        sys.exit(f"REFUSING: no *-review.json under {runs}. The records are gitignored, so a "
                 f"worktree copy is empty — point --runs at the main checkout.")
    out, scored, headless = [], 0, 0
    for p in paths:
        try:
            r = json.load(open(p))
        except (OSError, json.JSONDecodeError):
            continue
        if "findings" not in r:
            continue
        scored += 1
        s = subject(repo, r["head"]) if r.get("head") else None
        if s is None:
            headless += 1
            continue
        r["_subj"] = s
        r["_closing"] = bool(CLOSING.search(s))
        out.append(r)
    return out, scored, headless


def obligations(rec, escalation_on_closing):
    """What the push must still repair before it may leave.

    Error-grade is fail-closed exactly as gate/review.py:262 defines it: anything not
    explicitly tagged warning or info counts, so an untagged or "critical" finding cannot
    slip through by being a value the counter ignores. `escalation_on_closing=None` replays
    today's rule, under which every finding obligates."""
    out = []
    for f in rec["findings"]:
        if escalation_on_closing is None:
            out.append(f)
            continue
        if f.get("severity") not in ("warning", "info"):
            out.append(f)
        elif rec["_closing"] and escalation_on_closing and str(f.get("file", "")).startswith(ESCALATION):
            out.append(f)
        elif not rec["_closing"] and f.get("severity") == "warning":
            out.append(f)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.expanduser("~/Desktop/healbot"))
    ap.add_argument("--runs", default=None, help="default <repo>/gate/runs")
    ap.add_argument("--show-class", action="store_true", help="print every subject and its class")
    a = ap.parse_args()
    runs = a.runs or f"{a.repo}/gate/runs"

    recs, scored, headless = load(a.repo, runs)
    closing = [r for r in recs if r["_closing"]]
    opening = [r for r in recs if not r["_closing"]]
    print(f"records with a verdict: {scored}   no head recorded (pre-2026-08-03): {headless}")
    print(f"window: {len(recs)}   closing (repairs): {len(closing)}   opening (new surface): {len(opening)}\n")

    if a.show_class:
        for r in recs:
            print(("CLOSE " if r["_closing"] else "open  ") + r["_subj"][:100])
        print()

    for rows, label in ((closing, "repair"), (opening, "substantive")):
        n = len(rows) or 1
        tot = sum(len(r["findings"]) for r in rows)
        err = sum(1 for r in rows for f in r["findings"]
                  if f.get("severity") not in ("warning", "info"))
        clean = sum(1 for r in rows if not r["findings"])
        print(f"{label:12s} n={len(rows):3d}  mean findings={tot / n:.2f}  "
              f"mean error-grade={err / n:.2f}  clean first try={clean}/{len(rows)} ({100 * clean / n:.0f}%)")
    print()

    print(f"{'rule applied to a REPAIR push':46s} {'discharges':>12s}  expected repairs/chain")
    for esc, label in ((None, "today: every finding obligates"),
                       (True, "error-grade + escalation paths"),
                       (False, "error-grade only")):
        d = sum(1 for r in closing if not obligations(r, esc))
        n = len(closing) or 1
        p = 1 - d / n
        chain = f"{1 / (1 - p):.1f}" if p < 1 else "inf"
        print(f"{label:46s} {d:4d}/{len(closing)} ({100 * d / n:2.0f}%)  {chain:>10s}")
    print()

    cat = collections.Counter()
    for r in closing:
        for f in r["findings"]:
            sev, path = f.get("severity"), str(f.get("file", ""))
            if sev not in ("warning", "info"):
                cat["error-grade (blocks under every rule)"] += 1
            elif path.startswith(ESCALATION):
                cat["warning/info on an escalation path"] += 1
            else:
                cat["warning/info elsewhere"] += 1
    tot = sum(cat.values()) or 1
    print(f"repair-push findings by category (n={sum(cat.values())}):")
    for k, v in cat.most_common():
        print(f"   {v:3d} ({100 * v / tot:2.0f}%)  {k}")

    # Do findings recur? If they did, the exit would need a dedup ledger keyed on finding
    # identity. Measured: they do not, which is why ticket 22 carries no such ledger.
    seen = collections.Counter()
    for r in recs:
        for f in r["findings"]:
            norm = re.sub(r"[^a-z]+", " ", re.sub(r"\d+", "#", (f.get("summary") or "").lower()))
            seen[(f.get("file"), " ".join(norm.split()))] += 1
    total = sum(seen.values())
    print(f"\nfinding identity: {total} findings, {len(seen)} distinct (file, normalised summary) keys, "
          f"{sum(1 for v in seen.values() if v > 1)} keys seen more than once")


if __name__ == "__main__":
    main()
