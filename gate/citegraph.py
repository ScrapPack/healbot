"""The citation graph: which document points at which line of which file.

Extracted from `probe_citations.py`, which built this graph on every gate run and threw it
away. Two consumers need it now — that probe, which asserts every pointer still lands on a
real non-blank line, and `staleness.py`, which asks the different question of whether a push
moved the lines a document points at. One resolver, two questions.

WHY A MODULE AND NOT AN IMPORT OF THE PROBE: `probe_citations.py` executes at module scope —
it builds a `Results` object, runs the whole sweep, and exits from a `finally`. Importing it
runs the sweep and kills the importer. Nothing here runs at import: no walk, no `git`, no
`sys.exit`. Import is free and the caller decides when to pay.

STDLIB ONLY, and it does NOT import `rig`. `gate.py` runs outside the rig venv, so a
dependency on the rig would make the gate unable to load its own check. The repo root is
computed the same way `gate.py:39` computes it, from this file's own location.

WHAT MOVED AND WHAT DID NOT: resolution moved (the regex, the git-owned scoping, the index,
the proximity tie-break, the verdicts). The verbatim-quote leg did NOT — it is one probe's
assertion about how documents quote, not shared machinery, and it stays where it is asserted.

Every measured rationale below was earned by a failure and is kept verbatim from the probe.
Deleting a comment that records a measurement is deleting the evidence for a rule.
"""

import os
import re
import subprocess
from collections import defaultdict

# Same expression as gate.py:39, for the same reason: this file's location is the only thing
# that knows where the repo is, and both files sit one directory below the root.
HB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFIED = f"{HB}/.carryover/verified"

# normpath, not f"{HB}/opencode": HB comes back from os.path.dirname with NATIVE separators, so on
# Windows the interpolated form is the mixed string `C:\...\healbot/opencode` while every indexed
# path is normpath'd to all-backslash. `p.startswith(CHECKOUT + os.sep)` — the filter that keeps a
# citation off the CHECKOUT's copy of a colliding name — then matched nothing, and bare `PLAN.md`
# resolved to the checkout's v2/effect/PLAN.md. MEASURED 2026-08-05 on Windows 11. On POSIX
# normpath here is a no-op, so this changes no Mac behavior.
CHECKOUT = os.path.normpath(f"{HB}/opencode")

SKIP = {".git", "node_modules", "venv", "__pycache__", "dist", "build", ".next", "hb"}

# Historical prose, excluded BY NAME rather than by silently narrowing the walk. `REDO-PROMPT.md`
# is the prompt that started the verified redo and describes a tree that no longer exists; its
# citations are a record of what was true then, not pointers anyone should follow now.
EXCLUDE = {".carryover/REDO-PROMPT.md"}

# `:N` or `:N-M` after a path-ish token. The negative lookbehind keeps it from matching the tail of
# a longer path, and the extension list keeps it off prose like "1.18.5".
#
# EXTENSIONLESS DOTFILES ARE OUT OF REACH, and citations into them must not use `file:line`.
# Two clauses exclude them independently: the extension list has no entry for a bare dotfile,
# and the first character class `[A-Za-z0-9_]` rejects the leading dot. So a citation written as
# line 13 of `.gitignore` is not one this pattern can see (spelled out, not in live form, per the
# citation-hygiene skill's first rule). TESTED 2026-08-06 against the regex directly, after three
# documents were found pointing there for the `hb/*` rule, which has never been on line 13
# — rot the sweep ran green over every time, because it never matched the string. Widening the
# pattern is the wrong repair: `.gitignore` has no stable line numbering to cite (one comment
# added in 43d90b9 moved its `hb/*` rule from 48 to 58), so cite the RULE TEXT instead, the way
# HARNESS.md, docs/CLONE.md and the rig README now do.
CITE = re.compile(r"(?<![\w/])([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:ts|tsx|py|sh|jsonc|txt|md)):(\d+)(?:[-–](\d+))?")


class CheckoutAbsent(Exception):
    """`opencode/` is DERIVED and gitignored, so a fresh clone or worktree does not have it.

    Was a module-level `sys.exit(3)` in the probe. It cannot stay an exit: this module is
    imported by `gate.py`, and a module that exits its importer at import time is not a
    library. The exit code it stood for is preserved by the caller — `probe_citations.py`
    catches this ABOVE its try/finally and exits 3, because a sys.exit inside the try is
    replaced by the finally's own verdict exit, which would silently rewrite 3 back into a
    red 1. The gate maps a tier-1 exit 3 to ERROR; every other nonzero stays BLOCKED.

    Raised from build_index() rather than at import, so the failure surfaces when the graph
    is actually wanted. Before this, the first thing to touch the absent checkout was
    `git -C` inside owned_set(), whose CalledProcessError (exit 128, not a repository)
    reached the gate's citations row as a raw traceback instead of a cause. TESTED
    2026-08-02 in a fresh worktree.
    """


def checkout_present():
    """The check is for `.git`, the thing ls-files actually needs: a half-rebuilt checkout
    directory without a repository dies the same way a missing one does."""
    return os.path.exists(f"{CHECKOUT}/.git")


def rel_posix(path):
    """Repo-relative path in the DOCUMENTS' notation: forward slashes on every platform.

    Every consumer of these strings speaks POSIX — EXCLUDE, the coverage legs' `docs/` and `fork/`
    prefixes, the RESOLUTION legs' `endswith("session/prompt.ts")`, and the citations themselves.
    `os.path.relpath` speaks os.sep, so on Windows each of those compared a backslash path against
    a forward-slash literal and lost: REDO-PROMPT.md was SWEPT despite being excluded by name, and
    four legs asserted a string that cannot occur. MEASURED 2026-08-05 on Windows 11 — a silently
    WIDENED sweep, the same defect class as the narrowing the coverage legs exist to catch.
    `os.sep` is "/" on POSIX, so this is a no-op there and no Mac result moves.
    """
    return os.path.relpath(path, HB).replace(os.sep, "/")


def git_owned(root):
    """Absolute paths of every file git owns under `root`: tracked, plus untracked and not
    ignored. Same pair of commands `gate.py:78-91` uses to decide what a change touches.

    TWO repositories are asked, not one. `/opencode/` is gitignored wholesale by this repo
    and is its own checkout, so asking only the outer repo would empty the index of the
    upstream files the maps actually cite.

    An untracked NESTED repository is reported by `ls-files --others` as one `dir/` entry and is
    never recursed into — which is exactly how an app-created worktree under `.claude/worktrees/`
    stays out of both the sweep and the index. Those directory entries are dropped here.
    """
    owned = set()
    for args in (("ls-files", "-z"), ("ls-files", "--others", "--exclude-standard", "-z")):
        out = subprocess.run(
            ["git", "-C", root, *args], capture_output=True, text=True, check=True
        ).stdout
        for rel in out.split("\0"):
            if rel and not rel.endswith("/"):
                owned.add(os.path.normpath(os.path.join(root, rel)))
    return owned


_owned = None
_cache = {}


def reset_caches():
    """Drop memoized state. The probe and the staleness stage run in separate processes today,
    so this exists for tests that mutate a tree between calls inside ONE process. Without it a
    fixture's second scan would answer from the first fixture's index, which is a probe that
    passes for a reason unrelated to its claim."""
    global _owned
    _owned = None
    _cache.clear()


def owned_set():
    """Memoized union of both repositories."""
    global _owned
    if _owned is None:
        if not checkout_present():
            raise CheckoutAbsent(f"{CHECKOUT}/.git not found")
        _owned = git_owned(HB) | git_owned(CHECKOUT)
    return _owned


def build_index():
    """-> (index, dropped). `dropped` is what the git scoping removed, so the narrowing is a
    measured number rather than an invisible one.

    SCOPE IS HALF THE RESOLUTION PROBLEM. The swept documents and the candidate set are both
    FILES GIT OWNS — tracked, plus untracked-but-not-ignored. Walking the filesystem instead
    put state nobody wrote into both. MEASURED in the main checkout, gate run 20260801-115807:
    Claude Code's login auto-installed a plugin marketplace under `harness/claude/plugins/`,
    and its third-party example docs added twelve fictional citations AND hijacked resolution.
    App-created worktrees under `.claude/worktrees/` were swept as well. Neither is this repo's
    prose; both went red as though a citation had rotted.
    """
    index = defaultdict(list)
    owned = owned_set()
    seen, dropped = set(), set()
    for root in (CHECKOUT, f"{HB}/harness", VERIFIED, HB):
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP]
            for fn in filenames:
                full = os.path.normpath(os.path.join(dirpath, fn))
                if full in seen or full in dropped:  # the four roots overlap
                    continue
                if full not in owned:
                    dropped.add(full)
                    continue
                seen.add(full)
                index[fn].append(full)
    return index, sorted(dropped)


def sources():
    """The prose that carries citations: this repo's docs and the overlay's maps. -> (srcs, dropped).

    The checkout is skipped — its map copies are byte-identical to `fork/`'s (probe_twin and the
    drift-mode-1 check both cover that), and walking the upstream tree would drown the result.
    """
    owned = owned_set()
    out, dropped = [], []
    for dirpath, dirnames, filenames in os.walk(HB):
        dirnames[:] = [d for d in dirnames if d not in SKIP and d != "opencode"]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            full = os.path.normpath(os.path.join(dirpath, fn))
            if rel_posix(full) in EXCLUDE:
                continue
            if full not in owned:
                dropped.append(rel_posix(full))
                continue
            out.append(full)
    return sorted(out), sorted(dropped)


def lines_of(path):
    if path not in _cache:
        try:
            _cache[path] = open(path, encoding="utf-8", errors="replace").read().split("\n")
        except Exception:
            _cache[path] = None
    return _cache[path]


def _tree_rel(path):
    """-> (tree, directory components) with the tree root stripped. fork/ mirrors the
    checkout's layout, so proximity must compare LAYOUT positions, not raw prefixes: a
    map under fork/packages/plugin/src is nearest the checkout's packages/plugin/src,
    which a raw-prefix rule would score identically to every other checkout file."""
    for tree, root in (("checkout", CHECKOUT), ("fork", os.path.join(HB, "fork"))):
        if path.startswith(root + os.sep):
            rel = path[len(root) + 1:]
            return tree, [c for c in os.path.dirname(rel).split(os.sep) if c]
    rel = path[len(HB) + 1:] if path.startswith(HB + os.sep) else path
    return "repo", [c for c in os.path.dirname(rel).split(os.sep) if c]


def nearest_to(src, cands):
    """The tie-break is a rule, not enumeration order. `(exact or inrange)[0]` was
    os.walk order: on Windows it resolved four basename-only citations to other
    packages' same-named files (blank at the cited lines), and on this Mac it sent
    FEATURE-PLUGINS.MAP.md's and fork/README.md's bare `builtins.ts` to
    core/src/tool's — the wrong file, silently OK off its non-blank lines (MEASURED
    2026-08-05, both platforms). Nearest wins: longest shared root-stripped directory
    prefix with the citing document, then the document's own tree, then
    posix-lexicographic, so every filesystem picks the same file for a reason."""
    if src is None or len(cands) < 2:
        return cands[0]
    stree, sdir = _tree_rel(src)

    def key(p):
        ptree, pdir = _tree_rel(p)
        shared = 0
        for a, b in zip(sdir, pdir):
            if a != b:
                break
            shared += 1
        return (-shared, 0 if ptree == stree else 1, rel_posix(p))

    return min(cands, key=key)


def resolve(cited, hi, index, src=None):
    """-> (suffix, pick). The ONE resolution path — classify() and the quote leg used to
    carry byte-copies of this block, and the Windows sweep had to fix the separator bug
    in both. `suffix` is the candidate set after the suffix and .md scoping (empty means
    NOFILE); `pick` is None when no candidate contains the cited line (PAST_EOF /
    unresolved), else nearest_to()'s choice.

    A candidate is only accepted if it actually CONTAINS the cited line. That single rule is
    what separates a real finding from the 155 this resolver's first draft invented: the
    checkout holds SEVEN files named `prompt.ts`, and resolving by shortest path sent
    `prompt.ts:1295` to the 57-line schema file.
    """
    cands = index.get(os.path.basename(cited), [])
    # Citations write "/" but the index holds normpath'd paths, which walk os.sep — on
    # Windows a "/"-needle never matches and the fallback silently widens to every basename
    # collision. Normalize the needle, which on POSIX is byte-identical to "/" + cited.
    want = os.sep + cited.replace("/", os.sep)
    suffix = [p for p in cands if p.endswith(want)] or cands
    if not suffix:
        return [], None
    # `.md` citations mean this repo's docs, not the checkout's copy of some upstream doc — both
    # trees ship a PLAN.md, and only one of them is the one being cited.
    if cited.endswith(".md"):
        own = [p for p in suffix if not p.startswith(CHECKOUT + os.sep)]
        suffix = own or suffix
    inrange = [p for p in suffix if (L := lines_of(p)) is not None and hi <= len(L)]
    if not inrange:
        return suffix, None
    exact = [p for p in inrange if p.endswith(want)]
    return suffix, nearest_to(src, exact or inrange)


def classify(cited, lo, hi, index, src=None):
    """-> (verdict, detail). Verdicts: OK | BLANK | PAST_EOF | NOFILE.

    Among surviving candidates, `src` (the citing document) breaks basename ties via
    nearest_to().
    """
    suffix, pick = resolve(cited, hi, index, src)
    if not suffix:
        return "NOFILE", cited
    if pick is None:
        biggest = max(suffix, key=lambda p: len(lines_of(p) or []))
        return "PAST_EOF", f"{rel_posix(biggest)} has {len(lines_of(biggest) or [])} lines"
    if all(not s.strip() for s in lines_of(pick)[lo - 1 : hi]):
        return "BLANK", rel_posix(pick)
    return "OK", rel_posix(pick)


def scan(index, srcs):
    """-> rows of (src, cited, lo, hi, verdict, detail, citing_line).

    `citing_line` is the 1-based line of the CITING document the pointer sits on. The probe
    never needed it; the staleness stage does, because "re-read this" is useless without
    saying where to look. It is appended rather than inserted so existing positional reads
    keep working.
    """
    rows = []
    for src in srcs:
        try:
            text = open(src, encoding="utf-8").read()
        except Exception:
            continue
        for m in CITE.finditer(text):
            lo = int(m.group(2))
            hi = int(m.group(3)) if m.group(3) else lo
            verdict, detail = classify(m.group(1), lo, hi, index, src)
            rows.append(
                (rel_posix(src), m.group(1), lo, hi, verdict, detail,
                 text.count("\n", 0, m.start()) + 1)
            )
    return rows
