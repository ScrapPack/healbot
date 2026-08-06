"""Do this repo's `file:line` citations still point at code? Zero model turns, zero credits.

`fork/README.md` names two ways this overlay goes stale. **Mode 1** — the checkout moves ahead of
the overlay — has a documented shell check, and it is run. **Mode 2** — *"upstream moves and the
`file:line` citations rot"* — is named as a risk and had **no check at all** until Phase 11, which
is why every instance so far was found by hand, one at a time: the audit found "citation drift of
one or two lines already", and Phase 7 found an off-by-one in a `prompt.ts` citation asserted as
VERIFIED, by opening the file and finding the line blank.

That matters more here than in most repos. `HARNESS.md`'s stated exit test is that from it alone
you can name the file owning any behaviour, and the maps are the deliverable — a map whose line
numbers have slid is not a smaller map, it is a wrong one, and it is wrong silently.

WHAT THIS CATCHES: positional rot. A cited line that does not exist, or exists and is blank.
WHAT IT DOES NOT CATCH: semantic rot — a citation that lands on a real, non-blank line that says
something else entirely. Nothing mechanical can check that IN GENERAL, and pretending otherwise
would make this probe the kind of guard this suite keeps finding: green for a reason unrelated to
the claim. One narrow exception since 2026-08-02: a citation whose document QUOTES its target in
the italic `*"…"*` form is read back verbatim by the quote leg; everything short of a quotation
stays unclaimed.

RESOLUTION IS THE WHOLE PROBLEM, and getting it wrong manufactures findings rather than hiding
them. The checkout holds SEVEN files named `prompt.ts` (57 / 1631 / 293 / 37 / 203 / 1 / 131
lines). A first pass at this resolved by shortest path, sent `prompt.ts:1295` — the Phase 7
predicate, which is correct — to the 57-line schema file, and reported **155** citations as past
EOF. All artifacts. So a candidate is only accepted if it actually CONTAINS the cited line, and
`.md` citations prefer this repo over the checkout (both trees have a `PLAN.md`).

SCOPE IS THE OTHER HALF OF THAT PROBLEM. Both the swept documents and the resolver's candidate
set are FILES GIT OWNS — tracked, plus untracked-but-not-ignored, `gate.py:78-91`'s definition
applied to the whole tree instead of to one change. Walking the filesystem instead put state
nobody wrote into both. MEASURED in the main checkout, gate run 20260801-115807: Claude Code's
login auto-installed a plugin marketplace under `harness/claude/plugins/` (gitignored by that
directory's whitelist), and its third-party example docs added twelve fictional citations
(`src/auth/AuthService.ts:45` and kin) AND hijacked resolution — docs/AFK.md's real
`carryover/verified/README.md:159` started landing on the marketplace's own README, "on a blank
line". App-created worktrees under `.claude/worktrees/` were swept as well. Neither is this
repo's prose; both went red as though a citation had rotted. The narrowing this fixes is real,
so the narrowing itself is PRINTED and counted rather than applied in silence.

  venv/bin/python probe_citations.py
"""

import os
import re
import sys

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import rig  # noqa: E402

# RESOLUTION MOVED to gate/citegraph.py. The staleness stage asks the same graph a different
# question — did this push move the lines a document points at — and it cannot get there by
# importing this file: everything below `r = rig.Results(...)` runs at module scope and exits
# from a finally, so importing this probe runs the sweep and kills the importer. What stayed
# here is the verbatim-quote leg, which is this probe's assertion about how documents quote
# rather than shared machinery. No sweep behavior changed: the legs below are byte-identical.
sys.path.insert(0, os.path.join(rig.HEALBOT, "gate"))
import citegraph  # noqa: E402
from citegraph import (  # noqa: E402
    CHECKOUT,
    CITE,
    EXCLUDE,
    HB,
    build_index,
    classify,
    lines_of,
    rel_posix,
    resolve,
    scan,
    sources,
)

# The absent checkout is refused here, not inside citegraph, and the exit code is this probe's
# to own. Exit 3 is the gate's word for cannot-measure (docs/E2E.md item D): a probe that found
# its NAMED input absent has left its claim unmeasured, which is a different fact from sweeping
# and finding rot. The gate maps a tier-1 exit 3 to ERROR; every other nonzero stays BLOCKED.
# This guard must stay ABOVE the try/finally: a sys.exit inside the try is replaced by the
# finally's own verdict exit, which would silently rewrite 3 back into a red 1.
if not citegraph.checkout_present():
    print(
        f"\n!! {CHECKOUT}/.git not found.\n"
        "   `opencode/` is the derived checkout and is gitignored — a fresh clone does not\n"
        "   have it. Rebuild it from fork/README.md, then re-run.\n",
        file=sys.stderr,
    )
    sys.exit(3)

# A citation that QUOTES its target is a stronger claim than one that merely points at it, and it
# is the one kind of SEMANTIC rot that is mechanically checkable: the document says what the line
# says, so the line can be read back. The header above rules semantic rot out of scope in
# general and names this leg as its one narrow exception, and docs/CITE.md carries the same
# dated narrowing; everything short of a quotation stays unclaimed.
#
# The form carries the claim, exactly as it does for specimen-vs-pointer. Only the ITALIC form
# `*"…"*` counts as a verbatim quote. MEASURED 2026-08-02 over the whole sweep: treating ANY
# quoted span near a citation as verbatim gives 14 mismatches in 23, nearly all of them paraphrase
# ("config loading mutates your disk" against the code it summarizes), scare-quotes, or labels —
# a check that cannot tell those from rot is noise. The italic form gave 6 claims, 3 verified and
# 3 genuinely rotted, no false positives.
QUOTED = re.compile(r'\A[^\n"]{0,40}?\*"([^"]{20,400})"')

# Normalized characters of the quote that must be found at the cited line. Long enough that a
# match is not coincidence, short enough to survive truncation and re-wrapping.
HEAD = 60


def _norm(s):
    """Markdown-insensitive, whitespace-insensitive, case-insensitive. A quote is re-typed prose:
    it wraps at a different column and its emphasis is the quoting author's, not the source's.

    `"` goes too, for the same reason the backticks do — it is delimiter, not content. Quoting a
    Python implicit string concatenation otherwise picks up the `" "` seam between its two
    literals and fails on source the reader sees as one uninterrupted sentence, which is exactly
    what `ab.py:93-94` is.
    """
    s = re.sub(r'[`*_>"]', "", s).replace("—", "-").replace("–", "-").replace("’", "'")
    return re.sub(r"\s+", " ", s).strip().lower()


def quote_frags(q):
    """-> ordered fragments. `…` marks an elision, so each side is matched separately and in
    order rather than as one string that the source never contained."""
    return [f for f in (_norm(p) for p in re.split(r"…|\.\.\.", q)) if len(f) >= 12]


def quote_verdict(pick, lo, hi, quote):
    """-> (verdict, detail). Verdicts: QUOTE_OK | QUOTE_MISMATCH | QUOTE_UNRESOLVED.
    `pick` is resolve()'s choice; None (nothing contains the cited span) files as
    QUOTE_UNRESOLVED here, so the floor leg exercises the same path scan_quotes runs.

    The HEAD of the quote locates it, and the head is the whole assertion. Equality does not
    survive contact with honest quoting: `docs/AFK.md` ends one quote at "it hangs indefinitely."
    where HARNESS.md continues ", but it does not stall other sessions", and quoting a Python
    implicit string concatenation picks up the `" "` seam between its two literals. Sixty
    normalized characters is enough signal to say a line is the one the words came from, and it
    is indifferent to where the quoter chose to stop.

    The match must BEGIN inside the cited span. Two lines of slack are searched so a quote that
    wraps past `hi` still matches, but a match that starts beyond the span is the finding: the
    `HARNESS.md:346` case sat five lines above its text and every character of the quote was
    present in the file, just not where the citation said.
    """
    if pick is None:
        return "QUOTE_UNRESOLVED", "no candidate contains the cited span"
    L = lines_of(pick)
    frags = quote_frags(quote)
    if not frags:
        return "QUOTE_UNRESOLVED", "quote too short to check"
    span = _norm("\n".join(L[lo - 1 : hi]))
    window = _norm("\n".join(L[lo - 1 : hi + 2]))
    pos = window.find(frags[0][:HEAD])
    if pos == -1 or pos >= max(len(span), 1):
        return "QUOTE_MISMATCH", f"{rel_posix(pick)} — wanted {frags[0][:HEAD]!r}"
    for f in frags[1:]:
        nxt = window.find(f[:HEAD], pos)
        if nxt == -1:
            return "QUOTE_MISMATCH", f"{rel_posix(pick)} — elided part {f[:40]!r} absent"
        pos = nxt
    return "QUOTE_OK", rel_posix(pick)


def scan_quotes(index, srcs):
    """Citations that carry a verbatim quote, with the quote checked back against the line."""
    out = []
    for src in srcs:
        try:
            text = open(src, encoding="utf-8").read()
        except Exception:
            continue
        for m in CITE.finditer(text):
            q = QUOTED.match(text[m.end() :])
            if not q:
                continue
            lo = int(m.group(2))
            hi = int(m.group(3)) if m.group(3) else lo
            _, pick = resolve(m.group(1), hi, index, src)
            verdict, detail = quote_verdict(pick, lo, hi, q.group(1))
            out.append((rel_posix(src), m.group(1), lo, hi, verdict, detail))
    return out


r = rig.Results(expect=21)

try:
    index, idx_dropped = build_index()
    srcs, src_dropped = sources()
    rows = scan(index, srcs)

    print(
        f"\n  git scoping: {len(src_dropped)} document(s) and {len(idx_dropped)} index file(s) "
        f"excluded as not git-owned (ignored, or inside an untracked nested repo)",
        flush=True,
    )
    for rel in src_dropped[:25]:
        print(f"     not git-owned, NOT SWEPT: {rel}", flush=True)
    if len(src_dropped) > 25:
        print(f"     … and {len(src_dropped) - 25} more", flush=True)

    r.check(
        f"the sweep found prose to check — {len(srcs)} documents, {len(rows)} citations",
        len(srcs) >= 40 and len(rows) >= 900,
        "a sweep that silently narrows passes by measuring nothing, so its size is asserted. A "
        "FLOOR, never an equality: the corpus grows, and an equality would go red on every doc "
        "added. MEASURED 2026-08-01 on the git-scoped sweep — 40 documents, 974 citations "
        "(the pre-scoping filesystem walk reported 300 / 1976 in a checkout carrying an "
        "auto-installed plugin marketplace). The document floor is exact because losing one is "
        "itself worth a red; the citation floor leaves ~7% for ordinary prose churn",
    )
    r.check(
        "…and it covers BOTH the phase docs and the overlay maps",
        any(s.startswith("docs/") for s in {x[0] for x in rows})
        and any(s.startswith("fork/") for s in {x[0] for x in rows}),
        "the maps are where citation rot actually lives — they are the ones that cite upstream code",
    )

    covered = {x[0] for x in rows}
    r.check(
        "…including the rig's own README, and the ONE historical doc is excluded BY NAME",
        ".carryover/verified/README.md" in covered and ".carryover/REDO-PROMPT.md" not in covered,
        f"excluded: {sorted(EXCLUDE)} — REDO-PROMPT.md describes a tree that no longer exists, so "
        "its citations are a record rather than pointers. A silently narrowed sweep is the failure "
        "this leg exists to prevent",
    )

    nofile = [x for x in rows if x[4] == "NOFILE"]
    past = [x for x in rows if x[4] == "PAST_EOF"]
    blank = [x for x in rows if x[4] == "BLANK"]

    for label, bad in (("NO SUCH FILE", nofile), ("PAST END OF FILE", past), ("BLANK LINE", blank)):
        if bad:
            print(f"\n  -- {label} --", flush=True)
            for src, cited, lo, hi, _, detail, _cline in bad[:25]:
                span = f"{lo}-{hi}" if hi != lo else f"{lo}"
                print(f"     {src:<52} {cited}:{span}   {detail}", flush=True)

    r.check(
        f"EVERY CITED FILE EXISTS — {len(nofile)} unresolved",
        not nofile,
        "a citation naming a file that is not in the tree cannot be checked by a reader at all",
    )
    r.check(
        f"NO CITATION POINTS PAST THE END OF ITS FILE — {len(past)} past EOF",
        not past,
        "Phase 11 found three: FEATURE-PLUGINS.MAP.md cited healbot.tsx:1223-1245, :1235 and :1241 "
        "against a 1,100-line file. Pre-existing, and nothing had ever looked",
    )
    r.check(
        f"NO CITATION LANDS ON A BLANK LINE — {len(blank)} blank",
        not blank,
        "Phase 7's failure mode exactly — a citation asserted VERIFIED whose line, opened, was "
        "empty. Phase 11 found five, THREE OF THEM CREATED BY PHASES 9 AND 10: editing HARNESS.md "
        "moved `## Traps` and `## Behavior -> file`, and editing probe_twin.py moved the line "
        "docs/HEADLESS.md cites. Nothing noticed, because nothing was looking",
    )

    # --- the verbatim-quote leg -------------------------------------------------------------
    qrows = scan_quotes(index, srcs)
    qok = [x for x in qrows if x[4] == "QUOTE_OK"]
    qbad = [x for x in qrows if x[4] == "QUOTE_MISMATCH"]
    qunres = [x for x in qrows if x[4] == "QUOTE_UNRESOLVED"]
    if qunres:
        print("\n  -- QUOTE CANDIDATES THE RESOLVER COULD NOT CHECK --", flush=True)
        for src, cited, lo, hi, _, detail in qunres[:25]:
            span = f"{lo}-{hi}" if hi != lo else f"{lo}"
            print(f"     {src:<52} {cited}:{span}   {detail}", flush=True)
    if qbad:
        print("\n  -- QUOTE DOES NOT MATCH THE CITED LINE --", flush=True)
        for src, cited, lo, hi, _, detail in qbad[:25]:
            span = f"{lo}-{hi}" if hi != lo else f"{lo}"
            print(f"     {src:<52} {cited}:{span}   {detail}", flush=True)

    r.check(
        f"the sweep found verbatim-quote citations AND VERIFIED THEM AT THEIR LINES — "
        f"{len(qok)} of {len(qrows)} candidates",
        len(qok) >= 5,
        "a floor on VERIFIED quotes, not on candidates scanned: candidates satisfied it while "
        "QUOTE_UNRESOLVED rows silently drained the leg below, so a resolver regression walking "
        "every quote to UNRESOLVED left both legs green over zero verified quotes (review "
        "finding from the 05ba18f push). MEASURED 2026-08-02: 6 in the repo, all in the italic "
        "`*\"…\"*` form. Low by design — the form is the claim, and most quoted spans beside a "
        "citation are paraphrase rather than a quotation of that line",
    )
    r.check(
        f"EVERY VERBATIM QUOTE IS ACTUALLY AT THE LINE IT CITES — {len(qbad)} mismatched",
        not qbad,
        "the one semantic-rot class that is checkable, and it was rotten in three of six when "
        "first run (2026-08-02) — all three invisible to every leg above, because each landed on "
        "a real, non-blank line in a file that exists. docs/HEADLESS.md cited PLAN.md:378 for text "
        "at :393 (Phase 6 moved the body +1 and Phase 7 a further +14; PLAN.md's own errata "
        "recorded that outside citations had moved with it, spot-checked three, and repaired "
        "none); docs/VERIFY.md cited :391-393 for the exit gate at :406-408; and docs/AFK.md "
        "quoted an ab.py arm label that had been rewritten the same day it was written, whose "
        "replacement comment calls the old wording a false claim. A pointer that is merely stale "
        "misleads; a QUOTE that is stale puts words in the source's mouth",
    )
    r.check(
        "MUTATION: an unresolvable quote candidate counts against the floor, not toward it",
        quote_verdict(resolve("no/such/file.py", 1, index)[1], 1, 1,
                      "a fragment long enough to be checkable")[0] == "QUOTE_UNRESOLVED",
        "the regression class the floor above guards: a candidate the resolver cannot walk "
        "must land in UNRESOLVED (draining the verified floor) rather than in OK",
    )

    # --- mutation checks ------------------------------------------------------------------
    # Each corrupts an input and pushes it through `classify` — the same function the sweep above
    # calls — rather than re-implementing the comparison inline.
    real = "packages/opencode/src/session/prompt.ts"
    r.check(
        "MUTATION: a fabricated past-EOF citation IS caught",
        classify(real, 999_999, 999_999, index)[0] == "PAST_EOF",
        "the positive legs above are absence assertions; without this they pass on an empty sweep",
    )
    r.check(
        "MUTATION: a fabricated missing-file citation IS caught",
        classify("no/such/file_xyzzy.ts", 1, 1, index)[0] == "NOFILE",
        "same reasoning, for the other absence leg",
    )
    blank_line = None
    src_lines = lines_of(f"{CHECKOUT}/{real}")
    for i, line in enumerate(src_lines, start=1):
        if not line.strip():
            blank_line = i
            break
    r.check(
        f"MUTATION: a citation to a known-blank line IS caught — prompt.ts:{blank_line}",
        blank_line is not None and classify(real, blank_line, blank_line, index)[0] == "BLANK",
        "found by scanning the real file for its first empty line, so the fixture cannot drift "
        "out from under the check",
    )
    r.check(
        "NEGATIVE CONTROL: a citation known to be CORRECT is not flagged — prompt.ts:1295",
        classify(real, 1295, 1295, index)[0] == "OK",
        "opencode's own turn predicate, the line the whole Phase 7 finding rests on. If the checks "
        "above fired on everything they would be worthless in the other direction",
    )
    # The quote leg gets both controls too. Its assertion above is an ABSENCE, so on its own it
    # would pass just as happily if the matcher were broken shut.
    r.check(
        "MUTATION: a verbatim quote moved off its line IS caught — prompt.ts:1295 quoted at :1296",
        quote_verdict(resolve(real, 1296, index)[1], 1296, 1296,
                      src_lines[1294].strip()[:80])[0] == "QUOTE_MISMATCH",
        "the real line 1295 quoted against line 1296 — one line off, the exact size of the Phase 6 "
        "shift that rotted docs/HEADLESS.md. If the window slack ever widens to swallow an "
        "off-by-one this goes red, which is the point",
    )
    r.check(
        "NEGATIVE CONTROL: a correct verbatim quote is NOT flagged — prompt.ts:1295",
        quote_verdict(resolve(real, 1295, index)[1], 1295, 1295,
                      src_lines[1294].strip()[:80])[0] == "QUOTE_OK",
        "same line, quoted at its own number. Without this the leg above passes by matching "
        "nothing at all",
    )
    r.check(
        "NEGATIVE CONTROL: a TRUNCATED quote is still correct — quoting is not transcription",
        quote_verdict(resolve(real, 1295, index)[1], 1295, 1295,
                      src_lines[1294].strip()[:28])[0] == "QUOTE_OK",
        "docs/AFK.md ends a HARNESS.md quote at 'it hangs indefinitely.' where the source runs on "
        "', but it does not stall other sessions'. That is honest quoting, and an equality check "
        "would have called it rot — which is why the match is a PREFIX",
    )
    r.check(
        "RESOLUTION: prompt.ts:1295 resolves to the 1,631-line session file, not the 57-line schema one",
        classify(real, 1295, 1295, index)[1].endswith("session/prompt.ts"),
        "SEVEN files are named prompt.ts. Resolving by shortest path sent this citation to "
        "packages/schema/src/prompt.ts and manufactured 155 false findings — the resolver bug is "
        "pinned here so it cannot come back",
    )
    r.check(
        "RESOLUTION: a bare `PLAN.md` citation means THIS repo's PLAN.md, not the checkout's",
        classify("PLAN.md", 335, 335, index)[1] == "PLAN.md",
        "the checkout ships packages/plugin/src/v2/effect/PLAN.md, and preferring it turned four "
        "correct citations into blank-line failures",
    )
    r.check(
        "RESOLUTION: a citation with a path prefix beats a bare basename match",
        classify("harness/config/opencode/opencode.jsonc", 16, 16, index)[1].endswith(
            "harness/config/opencode/opencode.jsonc"
        ),
        "opencode.jsonc:16 is the MODEL PIN that probe_turn_growth asserts RETIRE_AT against, and "
        "there are two files by that name; resolving to the checkout's reported it blank",
    )
    r.check(
        "…and that pin really is on line 16",
        "openai/gpt-5.6-sol" in lines_of(f"{HB}/harness/config/opencode/opencode.jsonc")[15],
        "the one citation in this repo that another probe's assertion depends on",
    )
    fp_map = os.path.join(HB, "fork", "packages", "tui", "src", "feature-plugins",
                          "FEATURE-PLUGINS.MAP.md")
    r.check(
        "RESOLUTION: a bare `builtins.ts` from FEATURE-PLUGINS.MAP.md resolves to the map's own "
        "sibling, by rule",
        classify("builtins.ts", 1, 1, index, src=fp_map)[1]
        == "fork/packages/tui/src/feature-plugins/builtins.ts",
        "four files are named builtins.ts and `(exact or inrange)[0]` was os.walk order: Windows "
        "sent this to another package's copy (blank at the cited lines) and this Mac to "
        "core/src/tool's, silently OK off its non-blank lines — MEASURED 2026-08-05 on both. "
        "nearest_to()'s root-stripped proximity is the rule; enumeration order was never one",
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
