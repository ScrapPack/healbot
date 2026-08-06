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
separate stage on the same hook, shaped on `review.py`: `HEALBOT_STALE` is `advisory` by
default, `blocking` opts in, `off` skips. In advisory mode every path exits 0.

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


def _sh(cmd):
    """-> stdout, or None when git said no. A missing blob and a missing file are both
    ordinary here (a path created by this push has no base side), so a nonzero exit is data
    rather than an error."""
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
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
    base = head = None
    if "--base" in argv:
        base = argv[argv.index("--base") + 1]
    if "--head" in argv:
        head = argv[argv.index("--head") + 1]
    if not base:
        return 0  # working-tree mode is out of scope by design; see the header
    head = head or "HEAD"

    t0 = time.time()
    if not citegraph.checkout_present():
        record = {"state": "unmeasured", "why": "opencode/ checkout absent"}
        findings = []
    else:
        index, _ = citegraph.build_index()
        srcs, _ = citegraph.sources()
        inv = invert(citegraph.scan(index, srcs))
        changed = set(_sh(["git", "diff", "--name-only", f"{base}...{head}"]).split())
        findings = join(base, head, changed, inv)
        record = {
            "state": "measured", "base": base, "head": head,
            "documents": len({f["document"] for f in findings}),
            "citations": len(findings),
            "targets_indexed": len(inv), "changed": len(changed),
        }
    record.update({"mode": mode, "secs": round(time.time() - t0, 3), "findings": findings})

    os.makedirs(RUNS, exist_ok=True)
    path = f"{RUNS}/{time.strftime('%Y%m%d-%H%M%S')}-staleness.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)

    # Shadow mode: the record is written, the operator sees nothing. The two independent
    # calibrations of the flag rate disagreed by more than 4x on the mean and 5x on the worst
    # case, and both used today's corpus against historical diffs, so both are lower bounds.
    # No number goes into a document until live records produce one.
    if env.get("HEALBOT_STALE_SHOW") == "1":
        print(f"\n-- citation staleness ({record.get('citations', 0)} citation(s)) --")
        print(render(findings))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ))
