"""Does the staleness join flag what moved and stay quiet about everything else? Zero credits.

`gate/staleness.py` answers a question `probe_citations.py` cannot: the pointer still resolves,
but did the lines it points at move? The risk in a check like this is not that it misses rot.
It is that it cries wolf. A stage that flags a dozen documents per push gets bypassed with
`--no-verify`, which also silently disables the evidence publisher, so a noisy stage costs more
than it finds.

So the assertions below are weighted toward the NEGATIVE direction: a hunk below the span must
not move it, a file that changed elsewhere must be silent, and a document edited on one line
must still report its untouched pointer on another. Every leg that asserts a finding is paired
with one asserting a non-finding, because a check that fires on everything is worthless in the
other direction and passes an absence assertion just as happily as a correct one.

MEASURED 2026-08-06, replaying 176 real pushes recorded in gate/runs/ against today's corpus:
the naive file-level rule flags a mean of 2.59 documents per push; these three filters bring
that to 0.98, with 52% of pushes silent and 7% flagging more than three documents. Those are
the numbers shadow mode exists to replace with live ones.

  venv/bin/python probe_staleness_join.py
"""

import os
import sys

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import rig  # noqa: E402

sys.path.insert(0, os.path.join(rig.HEALBOT, "gate"))
import citegraph  # noqa: E402
import staleness  # noqa: E402

# One hunk shape per fixture, written out rather than generated, so a reader can check the
# arithmetic by eye. (old_start, old_len, new_start, new_len).
INSERT_ABOVE = [(5, 0, 5, 3)]     # three lines added after old line 5
DELETE_ABOVE = [(2, 4, 2, 1)]     # four old lines became one
CHANGE_BELOW = [(50, 2, 50, 9)]   # entirely past any span we cite
OVERLAP = [(9, 4, 9, 4)]          # rewrites old lines 9-12

r = rig.Results(expect=22)

try:
    # --- parse_hunks: the one form that breaks a naive parse ------------------------------
    r.check(
        "parse_hunks reads an ordinary hunk header",
        staleness.parse_hunks("@@ -10,3 +10,5 @@ def f():") == [(10, 3, 10, 5)],
        "the base case; without it the legs below could pass over an empty parse",
    )
    r.check(
        "MUTATION: the LENGTH-ELIDED form `@@ -7 +7 @@` reads as ONE line, not zero",
        staleness.parse_hunks("@@ -7 +7 @@") == [(7, 1, 7, 1)],
        "git's shorthand for a single-line hunk. Read as 0 it is indistinguishable from a pure "
        "insertion, so every citation below it shifts by the wrong amount — silently, because "
        "the resulting line number is still a real non-blank line and the citations probe stays "
        "green over it",
    )

    # --- shift_for: the delta must come from what precedes the span -----------------------
    r.check(
        "an insertion ABOVE the span shifts it down by the inserted count",
        staleness.shift_for(INSERT_ABOVE, 10, 10) == (3, False),
        "the ordinary rot this stage exists to catch",
    )
    r.check(
        "a deletion ABOVE the span shifts it UP",
        staleness.shift_for(DELETE_ABOVE, 10, 10) == (-3, False),
        "four lines became one, so everything below moves up three",
    )
    r.check(
        "NEGATIVE CONTROL: a hunk BELOW the span does not move it",
        staleness.shift_for(CHANGE_BELOW, 10, 10) == (0, False),
        "the single largest false-positive source. A change to the bottom of a file does not "
        "touch a citation into the top of it, and a check that says otherwise is noise",
    )
    r.check(
        "a hunk OVERLAPPING the span reports overlapped, not a shift",
        staleness.shift_for(OVERLAP, 10, 11) == (0, True),
        "the cited lines themselves were rewritten, so no corrected number exists to offer",
    )
    r.check(
        "MUTATION: the delta is NOT a file-wide offset — a change below is excluded from it",
        staleness.shift_for(INSERT_ABOVE + CHANGE_BELOW, 10, 10)
        == staleness.shift_for(INSERT_ABOVE, 10, 10),
        "summing every hunk in the file is the wrong model and produces wrong numbers whenever "
        "a change adds above a citation and deletes below it. PLAN.md's errata repaired "
        "citations by a fixed offset and was wrong by +31, then by +1",
    )

    # --- classify_span: anchor confirmation is the quiet-keeping filter -------------------
    old = [f"line {i}" for i in range(1, 21)]
    moved_new = ["new"] * 3 + old            # three lines inserted at the top
    edited_new = list(old)
    edited_new[9] = "line 10 REWRITTEN"      # the cited line itself changed
    far_new = list(old)
    far_new[17] = "line 18 changed far away"

    r.check(
        "NEGATIVE CONTROL: identical bytes at the cited span report NOTHING",
        staleness.classify_span(old, far_new, 10, 10, CHANGE_BELOW) == (None, None, None),
        "FILTER 2, and the reason this stage is quiet. A file that changed somewhere else "
        "entirely leaves the pointer landing on the same text, so there is nothing to re-read",
    )
    r.check(
        "a span whose text moved is reported as MOVED, with the corrected number",
        staleness.classify_span(old, moved_new, 10, 10, [(0, 0, 1, 3)]) == ("moved", 13, 13),
        "the corrected number is the useful half: 'go re-read this' without saying where is "
        "the work the operator already had to do by hand",
    )
    r.check(
        "a span whose text changed under it is reported as REWRITTEN",
        staleness.classify_span(old, edited_new, 10, 10, OVERLAP)[0] == "rewritten",
        "no corrected number is offered because none exists — the lines are not elsewhere, "
        "they are different",
    )
    r.check(
        "MUTATION: MOVED requires FINDING the original text at the corrected position",
        staleness.classify_span(old, edited_new, 10, 10, INSERT_ABOVE)[0] == "rewritten",
        "the hunks claim a +3 shift, but line 13 of the new side is not the old line 10. A "
        "corrected line number is a claim this stage has CHECKED, not one it inferred from "
        "arithmetic. Without this leg a wrong number would be emitted with full confidence",
    )

    # --- invert: what is allowed into the index ------------------------------------------
    ok_row = ("docs/X.md", "gate/gate.py", 78, 91, "OK", "gate/gate.py", 12)
    bad_row = ("docs/X.md", "nope.ts", 1, 1, "NOFILE", "nope.ts", 13)
    checkout_row = ("fork/M.MAP.md", "prompt.ts", 1, 1, "OK",
                    "opencode/packages/opencode/src/session/prompt.ts", 14)

    r.check(
        "an OK citation into a repo file IS indexed",
        list(staleness.invert([ok_row])) == ["gate/gate.py"],
        "the base case",
    )
    r.check(
        "MUTATION: a citation that did NOT resolve is NOT indexed",
        staleness.invert([bad_row]) == {},
        "probe_citations already asserts every cited file exists and BLOCKS the push when one "
        "does not, so carrying an unresolved row would report one defect twice — and its key "
        "would be the raw cited string rather than a path, which can never match a changed file",
    )
    r.check(
        "MUTATION: a citation into the gitignored checkout is NOT indexed",
        staleness.invert([checkout_row]) == {},
        "opencode/ is its own repository and gitignored wholesale, so no push to this repo can "
        "change one. They are the MAJORITY of the corpus; keeping them would make the index "
        "look several times better covered than it is",
    )

    index, _ = citegraph.build_index()
    srcs, _ = citegraph.sources()
    inv = staleness.invert(citegraph.scan(index, srcs))
    total = sum(len(v) for v in inv.values())
    r.check(
        f"the REAL corpus inverts to a usable index — {len(inv)} targets, {total} citations",
        len(inv) >= 20 and total >= 100,
        "a FLOOR, never an equality: the corpus grows. MEASURED 2026-08-06 — 50 in-repo targets "
        "carrying 292 citations, out of 1,077 swept. Without this floor every leg above passes "
        "over an index the resolver quietly emptied",
    )

    # --- decide: filter 3, per line and not per document ----------------------------------
    args = ("docs/X.md", 12, "gate/gate.py", "gate/gate.py", 10, 10, old, moved_new,
            [(0, 0, 1, 3)])
    r.check(
        "a surviving finding carries the corrected span",
        staleness.decide(*args, None)["corrected"] == [13, 13],
        "what the operator is handed",
    )
    r.check(
        "FILTER 3: a citation on a line THIS PUSH WROTE is suppressed",
        staleness.decide(*args, {12}) is None,
        "an author editing the citation is already looking at it, and telling them to re-read "
        "the thing they just wrote is the noise that gets a stage switched off",
    )
    r.check(
        "MUTATION: filter 3 is PER LINE — a document edited ELSEWHERE still reports",
        staleness.decide(*args, {40, 41})["corrected"] == [13, 13],
        "a document is routinely edited in one section while holding a rotted pointer in "
        "another. Suppressing the whole file because one line moved is how a check goes quiet "
        "about the thing it exists to find",
    )

    # --- render ---------------------------------------------------------------------------
    moved_finding = staleness.decide(*args, None)
    rewritten_finding = dict(moved_finding, state="rewritten", corrected=None)
    r.check(
        "a MOVED finding renders its corrected line number",
        "now at 13" in staleness.render([moved_finding]),
        "the correction is the deliverable",
    )
    r.check(
        "MUTATION: a REWRITTEN finding renders NO corrected number",
        "now at" not in staleness.render([rewritten_finding]),
        "offering a line number for content that was rewritten would assert the text is "
        "elsewhere when it is gone — a confident wrong answer, worse than no answer",
    )

    # --- integration against real history --------------------------------------------------
    found, rng = [], None
    head = staleness._sh(["git", "rev-parse", "HEAD"]).strip()
    log = staleness._sh(["git", "rev-list", "--max-count=60", head]).split()
    for sha in log[1:]:
        changed = set((staleness._sh(["git", "diff", "--name-only", f"{sha}...{head}"]) or "").split())
        if not any(f in inv for f in changed):
            continue
        got = staleness.join(sha, head, changed, inv)
        if got:
            found, rng = got, (sha, head)
            break
    r.check(
        f"INTEGRATION: the join runs on real history and finds something — {len(found)} "
        f"finding(s) over {rng[0][:8] if rng else 'none'}...HEAD",
        bool(found)
        and all(f["state"] in ("moved", "rewritten") for f in found)
        and all((f["corrected"] is not None) == (f["state"] == "moved") for f in found),
        "the pure legs above prove the arithmetic; this proves the git plumbing feeds it. The "
        "consistency clause is the real assertion: a corrected span exists if and only if the "
        "verdict is `moved`",
    )
    r.check(
        "NEGATIVE CONTROL: with NO changed files the join reports nothing",
        staleness.join(rng[0] if rng else "HEAD~1", head, set(), inv) == [],
        "findings must be driven by the CHANGE, not by the corpus. A join that walked the index "
        "instead of the changed set would flag the same documents on every push forever, and "
        "every absence assertion above would still pass",
    )

except SystemExit:
    raise
except Exception:
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    ok = r.summary()
    sys.exit(0 if ok else 1)
