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

import contextlib
import glob
import io
import os
import shutil
import subprocess
import sys
import tempfile

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

r = rig.Results(expect=31)

# The ordinary absent-checkout case, caught BEFORE the try so the exit is not swallowed by the
# finally. `probe_citations.py:80` does the same thing for the same reason and this probe was
# the one file of the three that had neither this nor the mid-sweep catch below: with opencode/
# absent it fell to `except Exception`, went red and exited 1, which `gate/tier2.py` maps to
# BLOCKED — "a check ran and said no" — for a check that could not run at all. Exit 3 is the
# cannot-measure verdict and `gate.py` maps it to ERROR (review finding from the b480659 push).
if not citegraph.checkout_present():
    print(f"\n!! {citegraph.CHECKOUT}/.git not found. UNMEASURED, not failed.\n", file=sys.stderr)
    sys.exit(3)

vanished = False

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

    # A fixture repository carrying BOTH path shapes the real one does not have, because the two
    # of them catch two different regressions through the SHIPPED git path:
    #
    #   - the NON-ASCII name fails if `changed_paths` stops passing `core.quotePath=false`;
    #   - the SPACED name fails if `changed_paths` stops routing through `changed_from` — an
    #     inlined `set(out.split())` there would bypass the pure leg below entirely, which tests
    #     `changed_from` on a literal and never touches the wiring.
    #
    # A previous draft dropped the space to make the two legs "fail for different reasons" and
    # bought that tidiness with the wiring coverage (review finding from the 4c4ff85 push). Both
    # shapes, one fixture, is strictly stronger than either.
    #
    # `core.quotePath` IS PINNED TRUE, and that pin is load-bearing. It is git's default, so an
    # earlier draft left it ambient — and on a machine that had disabled it globally the leg
    # would pass whether or not the shipped code carried the flag, which is an assertion
    # incapable of failing dressed as a mutation control (review finding from the 2e114b1 push).
    _fx = tempfile.mkdtemp(prefix="hb-quote-")
    _g = lambda *a: subprocess.run(["git", "-C", _fx, *a], capture_output=True, text=True)  # noqa: E731
    _g("init", "-q")
    _g("config", "user.email", "probe@healbot.local")
    _g("config", "user.name", "probe")
    _g("config", "core.quotePath", "true")
    open(os.path.join(_fx, "seed.md"), "w", encoding="utf-8").write("x\n")
    _g("add", "-A")
    _g("commit", "-q", "-m", "seed")
    _base = _g("rev-parse", "HEAD").stdout.strip()
    for _name in ("café.md", "two words.md", "plain.md"):
        open(os.path.join(_fx, _name), "w", encoding="utf-8").write("y\n")
    _g("add", "-A")
    _g("commit", "-q", "-m", "a non-ASCII path, a spaced path, and a plain one")
    _seen = staleness.changed_paths(_base, "HEAD", cwd=_fx)
    r.check(
        "a NON-ASCII and a SPACED changed path both survive the shipped git path intact",
        _seen == {"café.md", "two words.md", "plain.md"},
        f"git quotes such a path as a `\\303\\251` escape by default, and an escaped key can "
        f"never match an index built by walking the filesystem — so the citations into that file "
        f"are dropped from the join SILENTLY. `hunks()` sets `core.quotePath=false` for exactly "
        f"this and the --name-only call did not (review finding from the f5c21e9 push). "
        f"got {sorted(_seen or [])}",
    )
    shutil.rmtree(_fx, ignore_errors=True)

    r.check(
        "MUTATION: a changed path containing a SPACE stays one path",
        staleness.changed_from("docs/a b.md\ngate/x.py\n") == {"docs/a b.md", "gate/x.py"},
        "`set(out.split())` splits on ALL whitespace, so such a path fragments into keys that "
        "can never match an index entry and every citation into it is dropped from the join "
        "SILENTLY — a check going quiet about the one file somebody just renamed, which reads "
        "exactly like a clean run. gate.py:91 already parses this command with splitlines()",
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
    head = staleness._sh(["git", "rev-parse", "HEAD"]).strip()
    log = staleness._sh(["git", "rev-list", "--max-count=60", head]).split()
    found, rng, candidates, reported = [], None, 0, 0
    for sha in log[1:]:
        changed = set((staleness._sh(["git", "diff", "--name-only", f"{sha}...{head}"]) or "").split())
        cand = sum(len(inv[t]) for t in changed if t in inv)
        if not cand:
            continue
        got = staleness.join(sha, head, changed, inv)
        candidates += cand
        reported += len(got)
        if got and rng is None:
            found, rng = got, (sha, head)
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
        f"THE FILTERS SUPPRESS THROUGH THE REAL GIT PATH — {reported} reported of "
        f"{candidates} citation-range pair(s)",
        candidates > reported > 0,
        "the one leg that exercises the filters end to end on real diffs rather than on "
        "fixtures, and DELIBERATELY COARSE: it asserts the filters do something and not "
        "everything. It does NOT isolate a filter, and two earlier drafts of this sentence "
        "claimed it did and then quoted a ratio to prove it. Both numbers were measured "
        "against a window this file has since changed, which is why neither is here now "
        "(citation-hygiene: delete the number, never correct it). Disabling one filter "
        "leaves the other two suppressing, so this predicate holds and the FIXTURE legs "
        "above are what go red. What the boolean catches is the class no fixture can: all "
        "three filters degrading together against real git output. `reported > 0` is the "
        "quieter half, and a stage that suppresses everything is the worse failure",
    )
    r.check(
        "NEGATIVE CONTROL: with NO changed files the join reports nothing",
        staleness.join(rng[0] if rng else "HEAD~1", head, set(), inv) == [],
        "narrow by construction — join's only loop is over `changed`, so this catches exactly "
        "one mutation, a join that walked the index instead of the change. It is kept because "
        "that mutation is real and nothing else here would catch it, and it is NOT the leg that "
        "proves the filters work; the one above it is (review finding from the 7e6673b push)",
    )

    # --- main(): the exit contract, asserted instead of claimed ---------------------------
    # THIS BLOCK IS THE POINT OF THE WHOLE FILE. Four consecutive reviews caught defects in
    # main() and this probe caught none of them, because nothing here called it: the header
    # said "every path exits 0" while three separate paths did not, and each was found by a
    # reader rather than by a run. A claim about behavior that no assertion touches is prose,
    # and prose is what wrote the defects. Every path below is EXERCISED, not described.
    def run_main(args, environ=None, runs=None):
        """-> (exit code, stderr, records written). Redirects the stage's own output so a
        failure surfaces as a value rather than as noise in this probe's log.

        NO try/finally, deliberately, and `with` is used instead because it is not an ast.Try.
        probe_rig_contract's contract 5 requires the verdict exit to be the last statement of
        EVERY finally in the file, not just the outer one, and it refused this push when a
        first draft restored state in one. Restoring only on the normal path is also the right
        behavior here: main() raising is itself a defect, and the outer guard should see it
        rather than have it tidied away.
        """
        prev = staleness.RUNS
        staleness.RUNS = runs if runs is not None else tempfile.mkdtemp(prefix="stale-")
        box = io.StringIO()
        with contextlib.redirect_stderr(box), contextlib.redirect_stdout(io.StringIO()):
            code = staleness.main(args, environ or {})
        wrote = glob.glob(f"{staleness.RUNS}/*-staleness.json") if runs is None else []
        staleness.RUNS = prev
        return code, box.getvalue(), wrote

    paths = {
        "no arguments": ([], {}),
        "trailing --base with no value": (["--base"], {}),
        "unresolvable sha": (["--base", "deadbeefdeadbeef", "--head", "HEAD"], {}),
        "a real range": (["--base", rng[0] if rng else "HEAD~1", "--head", head], {}),
        "HEALBOT_STALE=off": (["--base", "HEAD~1"], {"HEALBOT_STALE": "off"}),
    }
    codes = {name: run_main(*a)[0] for name, a in paths.items()}
    r.check(
        f"EVERY PATH OUT OF main() EXITS 0 — {len(codes)} exercised",
        set(codes.values()) == {0},
        "the stage must never refuse a push, and saying so in a header is not a check. Three "
        "commits running, that sentence was false in a different place each time: unguarded "
        "build_index, an unwritable runs directory, and a valueless --base. "
        + (f"nonzero: {[k for k, v in codes.items() if v]}" if any(codes.values()) else "all 0"),
    )
    r.check(
        "MUTATION: an unwritable runs directory does not make it refuse",
        run_main(["--base", rng[0] if rng else "HEAD~1", "--head", head],
                 runs="/dev/null/not-a-directory")[0] == 0,
        "the second of the three, and the one the review did not reach — it was found only by "
        "enumerating the paths and running each. os.makedirs raises OSError here",
    )
    code, err, wrote = run_main(["--base", "deadbeefdeadbeef", "--head", "HEAD"], {})
    r.check(
        "AN UNMEASURED RUN SAYS SO, with no HEALBOT_STALE_SHOW set",
        "NOT MEASURED" in err and len(wrote) == 1,
        "shadow mode withholds FINDINGS. It was briefly withholding FAILURES too, which sent "
        "every defect into a gitignored record nothing printed — a stage that had stopped "
        "measuring reading exactly like one that measured cleanly, the shape this suite hunts",
    )
    code, err, wrote = run_main(["--base", rng[0] if rng else "HEAD~1", "--head", head], {})
    r.check(
        "NEGATIVE CONTROL: a run that DID measure stays silent",
        err == "" and len(wrote) == 1,
        "the other half, and the one that makes the leg above mean something: if the stage "
        "printed on every run, 'it printed' would assert nothing about failure",
    )
    r.check(
        "MUTATION: a valueless --base is NOT mistaken for working-tree mode",
        "NOT MEASURED" in run_main(["--base"], {})[1],
        "opt() first collapsed absent and valueless into None, so a typo returned 0 in silence "
        "and was indistinguishable from a deliberate bare invocation (review finding from the "
        "7e42452 push). Working-tree mode is declined deliberately; a typo is not",
    )
    r.check(
        "HEALBOT_STALE=off writes NO record at all",
        run_main(["--base", "HEAD~1"], {"HEALBOT_STALE": "off"})[2] == [],
        "off means off. A stage that still swept and still wrote would cost what the switch "
        "exists to save, and the switch would look like it worked",
    )

except SystemExit:
    raise
except citegraph.CheckoutAbsent:
    # The checkout going away DURING the sweep, which the pre-check above cannot cover. A
    # `sys.exit(3)` raised in here would be DISCARDED by the finally, so the verdict travels
    # as a flag — the same mechanism probe_citations.py uses, for the same reason.
    vanished = True
    print(f"\n!! {citegraph.CHECKOUT}/.git vanished mid-sweep. UNMEASURED, not failed.\n",
          file=sys.stderr)
except Exception:
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    if vanished:
        sys.exit(3)
    ok = r.summary()
    sys.exit(0 if ok else 1)
