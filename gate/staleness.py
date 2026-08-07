"""Which documents point at lines this push moved?

`probe_citations.py` asks whether every pointer still lands on a real non-blank line. That is
positional rot and it is caught the moment it happens. This asks the different question: the
pointer still resolves, but did the thing it pointed at move out from under it? A citation that
slid three lines down is green to the probe and wrong to a reader.

WHY IT EXISTS. `gate/review.py:75` scopes the model reviewer to the change, so a document a
change invalidates but does not touch is out of scope by construction. That is the measured
cause of the repair loop: the rot is found later, by a session that went looking, days and
sometimes hundreds of commits after the change that caused it.

WHY IT IS NOT A gate.py ROW. A finding here is advice, never a refusal. `gate.py` maps a
nonzero tier-1 exit to BLOCKED and its own ERROR state to exit 3, so a row could not report
"you might want to re-read this" without also owning the power to refuse a push. This is a
separate stage on the same hook: `HEALBOT_STALE=off` skips it, and every other value runs it
advisory. EVERY PATH EXITS 0, and the hook appends `|| true` on top of that.

There is deliberately NO blocking mode. `review.py` has one and this does not, because a
finding here is a prompt to go and read something, never a claim that a document is wrong —
the stage cannot tell a moved pointer from a false claim, and refusing a push over a signal
that cannot distinguish those trains the operator to reach for `--no-verify`, which also
silently disables the evidence publisher. If a blocking mode is ever wanted it arrives with
the operator-visible output, not before it.

WHY IT IS RANGE-ONLY. It runs on `base...head` and declines working-tree mode outright.
`gate.changed_files` unions `git ls-files --others --exclude-standard` when base is None, while
`git diff -U0` emits nothing for an untracked file, so every citation into a newly added file
would classify as rewritten against an empty old side. Scoping to hook mode makes that class
unreachable rather than filtered, which is the difference between a rule and a patch.

FALSE POSITIVES ARE THE WHOLE DESIGN. A check that flags a dozen documents per push gets
bypassed, and `--no-verify` also disables the evidence publisher, so a noisy stage costs more
than it finds. Three filters run in order and each one is an ANSWER, not a heuristic:

  1. the cited span must actually have moved or been rewritten, computed from the hunks that
     precede it rather than from one file-wide offset;
  2. anchor confirmation — the bytes at the cited span are compared on both sides, so a file
     that changed somewhere else entirely is silent;
  3. the citing line must not itself have been written by this push, tested per line, because
     an author editing the citation is already looking at it.

  venv/bin/python gate/staleness.py --base <sha> --head <sha>
"""

import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import citegraph  # noqa: E402

ROOT = citegraph.HB
RUNS = os.environ.get("HEALBOT_GATE_RUNS", f"{ROOT}/gate/runs")

# `@@ -old_start,old_len +new_start,new_len @@`. A missing length means 1, which is git's
# shorthand for a single line and the one form that silently breaks a naive int() parse.
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def _sh(cmd, cwd=None):
    """-> stdout, or None when git said no. A missing blob and a missing file are both
    ordinary here (a path created by this push has no base side), so a nonzero exit is data
    rather than an error.

    `cwd` is a parameter for the same reason `join`'s `edited_of` is: so a contract can be
    asserted against a fixture repository built to exercise it, instead of against whatever
    this repository's history happens to contain.
    """
    p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


def blob(rev, path):
    """Lines of `path` at `rev`, or None when it did not exist there."""
    out = _sh(["git", "show", f"{rev}:{path}"])
    return None if out is None else out.split("\n")


def parse_hunks(text):
    """-> [(old_start, old_len, new_start, new_len)] from unified-diff text.

    Split from the git call so the arithmetic is testable without a repository. The
    length-elided form `@@ -7 +7 @@` is git's shorthand for a single line and is the one that
    breaks a naive parse: read as 0 it makes every following citation shift by the wrong
    amount, silently.
    """
    found = []
    for line in (text or "").split("\n"):
        m = HUNK.match(line)
        if m:
            found.append((
                int(m.group(1)), 1 if m.group(2) is None else int(m.group(2)),
                int(m.group(3)), 1 if m.group(4) is None else int(m.group(4)),
            ))
    return found


def hunks(base, head, path):
    """-> parse_hunks() over ONE `-U0` diff.

    `-U0` because context lines would merge adjacent edits into one hunk and blur exactly the
    boundary this stage measures. `core.quotePath=false` so a non-ASCII path arrives as itself
    rather than as octal escapes that would never match a citation.
    """
    return parse_hunks(_sh([
        "git", "-c", "core.quotePath=false", "diff", "-U0", f"{base}...{head}", "--", path
    ]))


def shift_for(hs, lo, hi):
    """-> (delta, overlapped) for the old-side span [lo, hi].

    `delta` accumulates ONLY from hunks that end before `lo`, so a citation is corrected by
    what happened above it. A single file-wide offset is the wrong model and produces wrong
    numbers whenever a change both adds above a citation and deletes below it. PLAN.md's own
    errata repaired citations by a fixed offset and was wrong by +31, then by +1.

    `overlapped` is True when any hunk touches the span itself, which is the rewritten case.
    """
    delta, overlapped = 0, False
    for old_start, old_len, _new_start, new_len in hs:
        if old_len == 0:
            # Pure insertion. git names the old line AFTER which text was added, so lines from
            # old_start + 1 onward shift; the span shifts when the insertion is above it.
            if old_start < lo:
                delta += new_len
            continue
        old_end = old_start + old_len - 1
        if old_end < lo:
            delta += new_len - old_len
        elif old_start > hi:
            continue
        else:
            overlapped = True
    return delta, overlapped


def _span(lines, lo, hi):
    """The cited text, or None when the span is not addressable in this version."""
    if lines is None or lo < 1 or hi > len(lines):
        return None
    return "\n".join(lines[lo - 1 : hi])


def classify_span(old, new, lo, hi, hs):
    """-> (state, new_lo, new_hi). States: `moved`, `rewritten`, or None for unaffected.

    ANCHOR CONFIRMATION IS FILTER 2 and it is what keeps this quiet. The bytes at the cited
    span are read on both sides. If the pointer still lands on the same text, this change did
    not touch it however much else it touched the file, and nothing is reported. Only when the
    text under the pointer differs does the hunk arithmetic get consulted, and a `moved`
    verdict additionally requires finding the ORIGINAL text at the corrected position — so a
    corrected line number is a claim the stage has checked, not one it inferred.
    """
    want = _span(old, lo, hi)
    if want is None:
        return None, None, None
    if _span(new, lo, hi) == want:
        return None, None, None
    delta, overlapped = shift_for(hs, lo, hi)
    if delta and _span(new, lo + delta, hi + delta) == want:
        return "moved", lo + delta, hi + delta
    if overlapped:
        return "rewritten", None, None
    # The text under the pointer changed and the original is not at the shifted position
    # either. Rewritten is the honest verdict: a reader must go and look.
    return "rewritten", None, None


def changed_paths(base, head, cwd=None):
    r"""-> the paths this range changed, or None when git could not answer.

    `core.quotePath=false` FOR THE SAME REASON `hunks()` SETS IT three functions up, and this
    call was missing it. With quoting on — git's default — a non-ASCII path arrives as
    `"docs/\303\251.md"`, quotes and octal escapes included, which can never match an index key
    built by walking the filesystem. The citations into that file are then dropped from the join
    SILENTLY, which is the same failure the space case had and the same failure a module is most
    likely to have when it sets a flag on one git call and not on its sibling (review finding
    from the f5c21e9 push). One rule, both calls.
    """
    out = _sh(["git", "-c", "core.quotePath=false", "diff", "--name-only", f"{base}...{head}"],
              cwd=cwd)
    return None if out is None else changed_from(out)


def changed_from(out):
    """-> the set of paths in `git diff --name-only` output.

    SPLIT FROM THE GIT CALL for the reason `parse_hunks` is: it makes the parsing testable
    without a repository, and this parsing has a failure mode worth a test. The first version
    was `set(out.split())`, which splits on ALL whitespace — so a tracked path containing a
    space fragments into pieces that can never match an index key, and every citation into that
    file is dropped from the join SILENTLY. `gate.py:117` already parses the identical command
    with `splitlines()`; two readings of one command's output is how they disagree.

    """
    return {ln.strip() for ln in (out or "").splitlines() if ln.strip()}


def added_lines(base, head, path):
    """HEAD-side line numbers this change wrote in `path`. Filter 3's input.

    Per LINE, never per document. A document is routinely edited in one section while holding
    a rotted pointer in another, and suppressing the whole file because one line moved is how
    a check goes quiet about the thing it exists to find.
    """
    out = set()
    for _old_start, _old_len, new_start, new_len in hunks(base, head, path):
        out.update(range(new_start, new_start + new_len))
    return out


def invert(rows):
    """-> {cited target: [(citing doc, cited-as, lo, hi, citing line)]}.

    Only `OK` rows enter. `probe_citations.py` already asserts that every cited file exists and
    that no citation points past EOF or at a blank line, and a nonzero tier-1 exit BLOCKS the
    push, so an unresolved citation is refused one stage before this runs. Carrying those rows
    would report one defect twice and hand the join a key that is the raw cited string rather
    than a resolved path.

    Targets inside the checkout are dropped: `opencode/` is gitignored wholesale and is its own
    repository, so no push to this repo can ever change one. They are the majority of the
    corpus, and keeping them would make the index look far better covered than it is.
    """
    inv = defaultdict(list)
    for src, cited, lo, hi, verdict, detail, cline in rows:
        if verdict != "OK" or detail.startswith("opencode/"):
            continue
        inv[detail].append((src, cited, lo, hi, cline))
    return inv


def decide(src, cline, cited, target, lo, hi, old, new, hs, edited):
    """-> a finding dict, or None when a filter suppressed it. PURE: every input is supplied.

    All three filters live here so they can be exercised without a repository. `edited` is the
    set of HEAD-side lines this push wrote in the CITING document, already resolved, or None
    when the push did not touch that document at all.
    """
    state, nlo, nhi = classify_span(old, new, lo, hi, hs)
    if state is None:
        return None  # filters 1 and 2
    if edited and cline in edited:
        return None  # filter 3: the author was already editing this pointer
    return {
        "document": src, "line": cline, "cited": cited,
        "target": target, "span": [lo, hi], "state": state,
        "corrected": [nlo, nhi] if state == "moved" else None,
    }


def join(base, head, changed, inv, edited_of=None):
    """-> findings, one per surviving citation. Loads the two sides, then defers to decide().

    `edited_of` resolves a citing document to the lines this push wrote in it. It is a
    parameter so the filter-3 contract can be asserted against a known input instead of
    against whatever the repository's history happens to contain.
    """
    if edited_of is None:
        def edited_of(path):
            return added_lines(base, head, path)
    findings, cache = [], {}
    for target in sorted(f for f in changed if f in inv):
        old, new = blob(base, target), blob(head, target)
        if old is None or new is None:
            continue  # created or deleted by this push; the citations row owns that class
        hs = hunks(base, head, target)
        for src, cited, lo, hi, cline in inv[target]:
            if src in changed and src not in cache:
                cache[src] = edited_of(src)
            got = decide(src, cline, cited, target, lo, hi, old, new, hs, cache.get(src))
            if got:
                findings.append(got)
    return findings


def render(findings):
    """Operator-facing text. Phase 2 records it and prints nothing; the caller decides."""
    if not findings:
        return "  no document points at a line this change moved"
    out = []
    for f in sorted(findings, key=lambda x: (x["document"], x["line"])):
        lo, hi = f["span"]
        span = f"{lo}-{hi}" if hi != lo else f"{lo}"
        if f["state"] == "moved":
            nlo, nhi = f["corrected"]
            fix = f"now at {nlo}-{nhi}" if nhi != nlo else f"now at {nlo}"
        else:
            fix = "content changed, re-read"
        out.append(f"     {f['document']}:{f['line']}  cites {f['cited']}:{span}   {fix}")
    return "\n".join(out)


def main(argv, env):
    mode = env.get("HEALBOT_STALE", "advisory")
    if mode == "off":
        return 0
    def opt(name):
        """-> the value, None when the flag is absent, or "" when it is present with none.

        The three cases must stay distinct. Collapsing the last two into None turned a typo
        into a silent `return 0` that read exactly like a deliberate working-tree invocation,
        which is the same failure-looks-like-success shape the guard below exists to prevent.
        """
        if name not in argv:
            return None
        i = argv.index(name)
        return argv[i + 1] if i < len(argv) - 1 else ""

    base, head = opt("--base"), opt("--head")
    if base == "" or head == "":
        print("staleness: NOT MEASURED — --base or --head given with no value", file=sys.stderr)
        return 0
    if not base:
        return 0  # working-tree mode is out of scope by design; see the header
    head = head or "HEAD"

    t0 = time.time()
    findings, unmeasured, inv, changed = [], None, {}, set()
    try:
        if not citegraph.checkout_present():
            unmeasured = "opencode/ checkout absent"
        else:
            index, _ = citegraph.build_index()
            srcs, _ = citegraph.sources()
            inv = invert(citegraph.scan(index, srcs))
            # `_sh` returns None on any nonzero git exit — an unfetched base, a typo'd sha on
            # the standalone invocation, unrelated histories. An unreachable range is
            # UNMEASURED, which is a different fact from a clean one, and keeping the two apart
            # is the same argument gate.py's ERROR-versus-PASS lattice makes.
            got = changed_paths(base, head)
            if got is None:
                unmeasured = f"git could not diff {base}...{head}"
            else:
                changed = got
                findings = join(base, head, changed, inv)
    except citegraph.CheckoutAbsent:
        unmeasured, findings = "opencode/ checkout vanished mid-sweep", []
    except Exception as exc:  # noqa: BLE001 — a stage that cannot measure must still report
        unmeasured, findings = f"{type(exc).__name__}: {exc}", []

    if unmeasured:
        record = {"state": "unmeasured", "why": unmeasured, "base": base, "head": head}
    else:
        record = {
            "state": "measured", "base": base, "head": head,
            "documents": len({f["document"] for f in findings}),
            "citations": len(findings),
            "targets_indexed": len(inv), "changed": len(changed),
        }
    record.update({"mode": mode, "secs": round(time.time() - t0, 3), "findings": findings})

    # The record is this stage's whole deliverable, and an unwritable runs directory is still
    # not grounds to refuse a push. Measuring and writing are guarded separately so the failure
    # is named: "could not measure" and "measured but could not write it down" are different
    # facts, and a single guard around both would report them identically.
    try:
        os.makedirs(RUNS, exist_ok=True)
        path = f"{RUNS}/{time.strftime('%Y%m%d-%H%M%S')}-staleness.json"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2)
    except OSError as exc:
        print(f"staleness: measured, but could not write its record ({exc})", file=sys.stderr)

    # A FAILURE IS NOT A FINDING, and shadow mode only withholds findings.
    if unmeasured:
        print(f"staleness: NOT MEASURED — {unmeasured}", file=sys.stderr)
        return 0

    # Findings themselves stay quiet while the flag rate is calibrated. Two replays of
    # historical pushes disagreed by more than 4x on the mean, and both read today's corpus
    # against old diffs, so both are lower bounds. Live records settle it.
    if env.get("HEALBOT_STALE_SHOW") == "1":
        print(f"\n-- citation staleness ({len(findings)} citation(s)) --")
        print(render(findings))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ))
