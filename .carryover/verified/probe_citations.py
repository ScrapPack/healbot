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
something else entirely. Nothing mechanical can check that, and pretending otherwise would make
this probe the kind of guard this suite keeps finding: green for a reason unrelated to the claim.

RESOLUTION IS THE WHOLE PROBLEM, and getting it wrong manufactures findings rather than hiding
them. The checkout holds SEVEN files named `prompt.ts` (57 / 1631 / 293 / 37 / 203 / 1 / 131
lines). A first pass at this resolved by shortest path, sent `prompt.ts:1295` — the Phase 7
predicate, which is correct — to the 57-line schema file, and reported **155** citations as past
EOF. All artifacts. So a candidate is only accepted if it actually CONTAINS the cited line, and
`.md` citations prefer this repo over the checkout (both trees have a `PLAN.md`).

  venv/bin/python probe_citations.py
"""

import os
import re
import sys
from collections import defaultdict

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import rig  # noqa: E402

HB = rig.HEALBOT
CHECKOUT = f"{HB}/opencode"
SKIP = {".git", "node_modules", "venv", "__pycache__", "dist", "build", ".next", "hb"}

# Historical prose, excluded BY NAME rather than by silently narrowing the walk. `REDO-PROMPT.md`
# is the prompt that started the verified redo and describes a tree that no longer exists; its
# citations are a record of what was true then, not pointers anyone should follow now.
EXCLUDE = {".carryover/REDO-PROMPT.md"}

# `:N` or `:N-M` after a path-ish token. The negative lookbehind keeps it from matching the tail of
# a longer path, and the extension list keeps it off prose like "1.18.5".
CITE = re.compile(r"(?<![\w/])([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:ts|tsx|py|sh|jsonc|txt|md)):(\d+)(?:[-–](\d+))?")


def build_index():
    index = defaultdict(list)
    for root in (CHECKOUT, f"{HB}/harness", SP, HB):
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP]
            for fn in filenames:
                index[fn].append(os.path.join(dirpath, fn))
    return index


def sources():
    """The prose that carries citations: this repo's docs and the overlay's maps.

    The checkout is skipped — its map copies are byte-identical to `fork/`'s (probe_twin and the
    drift-mode-1 check both cover that), and walking 6,330 upstream files would drown the result.
    """
    out = []
    for dirpath, dirnames, filenames in os.walk(HB):
        dirnames[:] = [d for d in dirnames if d not in SKIP and d != "opencode"]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            full = os.path.join(dirpath, fn)
            if os.path.relpath(full, HB) in EXCLUDE:
                continue
            out.append(full)
    return sorted(out)


_cache = {}


def lines_of(path):
    if path not in _cache:
        try:
            _cache[path] = open(path, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            _cache[path] = None
    return _cache[path]


def classify(cited, lo, hi, index):
    """-> (verdict, detail). Verdicts: OK | BLANK | PAST_EOF | NOFILE.

    A candidate must CONTAIN the cited line to be considered. That single rule is what separates a
    real finding from the 155 this probe's first draft invented.
    """
    cands = index.get(os.path.basename(cited), [])
    suffix = [p for p in cands if p.endswith("/" + cited)] or cands
    if not suffix:
        return "NOFILE", cited
    # `.md` citations mean this repo's docs, not the checkout's copy of some upstream doc — both
    # trees ship a PLAN.md, and only one of them is the one being cited.
    if cited.endswith(".md"):
        own = [p for p in suffix if not p.startswith(CHECKOUT + os.sep)]
        suffix = own or suffix
    inrange = [p for p in suffix if (L := lines_of(p)) is not None and hi <= len(L)]
    if not inrange:
        biggest = max(suffix, key=lambda p: len(lines_of(p) or []))
        return "PAST_EOF", f"{os.path.relpath(biggest, HB)} has {len(lines_of(biggest) or [])} lines"
    exact = [p for p in inrange if p.endswith("/" + cited)]
    pick = (exact or inrange)[0]
    if all(not s.strip() for s in lines_of(pick)[lo - 1 : hi]):
        return "BLANK", os.path.relpath(pick, HB)
    return "OK", os.path.relpath(pick, HB)


def scan(index, srcs):
    rows = []
    for src in srcs:
        try:
            text = open(src, encoding="utf-8").read()
        except Exception:
            continue
        for m in CITE.finditer(text):
            lo = int(m.group(2))
            hi = int(m.group(3)) if m.group(3) else lo
            verdict, detail = classify(m.group(1), lo, hi, index)
            rows.append((os.path.relpath(src, HB), m.group(1), lo, hi, verdict, detail))
    return rows


r = rig.Results(expect=14)

try:
    index = build_index()
    srcs = sources()
    rows = scan(index, srcs)

    r.check(
        f"the sweep found prose to check — {len(srcs)} documents, {len(rows)} citations",
        len(srcs) >= 20 and len(rows) >= 800,
        "a sweep that silently narrows passes by measuring nothing, so its size is asserted; "
        "this repo carried ~945 citations when the probe was written",
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
            for src, cited, lo, hi, _, detail in bad[:25]:
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

except SystemExit:
    raise
except Exception:
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    ok = r.summary()
    sys.exit(0 if ok else 1)
