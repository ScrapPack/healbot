#!/usr/bin/env python3
"""plainspec-check: the scriptable half of the plainspec writing standard.

Implements the machine tests of harness/skills/plainspec.md (installed twin:
~/.agents/skills/plainspec/SKILL.md, alongside this file as check.py). The skill
file is the spec; where a rule's test needs judgment, the finding is a JUDGE flag
and never fails the exit code.

Usage:
    python3 plainspec-check.py [--strict] [--error-message] [--score] FILE ...
    python3 plainspec-check.py --selftest

Repo-scoped exemptions: the nearest `plainspec.toml` at or above each checked file may
carry `[plainspec] disable = ["R8:em-dash"]`. Keys match a finding as "RULE:message" by
prefix, so a whole rule or one of its tests can be ruled out by the repo that owns the
prose. Discovery is upward from the file and never a flag, so a hand run and a gate run
over the same file cannot disagree. Exempted findings are counted and printed with the
score, never silently subtracted. Needs tomllib (Python 3.11+); on an older interpreter
the config is reported and IGNORED rather than half-applied.

Exit codes: 0 clean (JUDGE flags allowed), 1 at least one VIOLATION, 2 usage or
I/O error. --strict adds rules 12-15. --error-message additionally applies rule
14's 3-sentence cap to the whole input (only the caller knows the text IS an
error message). --selftest runs the embedded fire/clean fixtures: every rule must
demonstrate it CAN fire and CAN stay silent, the same two-leg discipline the
repo's probes use. Stdlib only.

Deviations and known limits (the spec stays authoritative):
- "just" flags as JUDGE, not VIOLATION: a script cannot tell verb from noun.
  simply/basically flag before any following word, verb or not.
- Rules 12-13 detect imperatives with a fixed verb list; steps led by a verb
  outside it escape. Rule 13's "numbered list present" half is unimplemented;
  instead, strict mode also applies the step rules to imperative-led bullets.
- Rule 1 pairs match plural and inflection variants of the spec's words.
- Rules 2 and 4 carry stoplists for lookalike nouns (sentence, document, often,
  open...). Contracted negatives ("isn't covered") escape rule 4. ALL-CAPS
  participles are skipped as classification labels (rule-5 carve-out kin).
- Rule 14's apology wordlist runs on all strict-mode prose, since the checker
  cannot locate error-message passages; the sentence cap needs --error-message.
- Rule 11 phrases flag anywhere in the text, not positionally.
- The spec file's own "Test ..." spans are exempt only when the frontmatter
  names the file plainspec; ordinary documents get no such exemption.
- Quoted spans (straight or curly) are exempt up to 400 chars within one
  paragraph; longer or cross-paragraph quotes are scanned. An unpaired quote
  affects at most its own paragraph.
- Findings in a multi-line paragraph cite the paragraph's first line.
- Judgment-pass territory by design: decoration adverbs beyond the -ly variants,
  comma-splice run-ons under the word cap, synonym pairs and hedges outside the
  spec lists, and version tokens ("v2") counting as measurements.
"""

import os
import re
import sys

VIOLATION = "VIOLATION"
JUDGE = "JUDGE"

CONFIG_NAME = "plainspec.toml"


def find_config(path):
    """The nearest `plainspec.toml` at or above a checked file, or None.

    Discovery is automatic and upward, never a flag. A flag would mean that whoever forgot to pass
    it got a different answer from the same checker over the same file — a hand run and a gate run
    disagreeing is worse than having no exemption mechanism at all.
    """
    d = os.path.dirname(os.path.abspath(path))
    while True:
        candidate = os.path.join(d, CONFIG_NAME)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def load_exemptions(cfg):
    """Read `[plainspec] disable = [...]` into a set of "RULE" / "RULE:message-prefix" keys.

    A key is a whole rule ("R8") or a rule plus a message prefix ("R8:em-dash"). The RULE half is
    matched EXACTLY and only the message half by prefix — see `is_exempt`, which had to stop
    prefix-matching the whole string once R1 was found exempting R10 through R15. The spec file
    stays authoritative about what the rules ARE; this only records that one repo has decided one
    of them does not apply to it.

    Any failure to read the file is REPORTED and the exemptions are dropped. A config that silently
    stops applying would quietly change every count the checker prints.
    """
    if not cfg:
        return frozenset()
    try:
        import tomllib
    except ImportError:
        print(f"{cfg}: this Python has no tomllib (needs 3.11+) — exemptions IGNORED",
              file=sys.stderr)
        return frozenset()
    try:
        with open(cfg, "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, ValueError) as e:
        print(f"{cfg}: cannot read ({e}) — exemptions IGNORED", file=sys.stderr)
        return frozenset()
    disabled = data.get("plainspec", {}).get("disable", [])
    if not isinstance(disabled, list) or not all(isinstance(k, str) for k in disabled):
        print(f"{cfg}: [plainspec] disable must be a list of strings — exemptions IGNORED",
              file=sys.stderr)
        return frozenset()
    return frozenset(disabled)


def is_exempt(finding, exemptions):
    """Does a (rule, severity, line, msg) finding match any exemption key?

    A key is a whole rule ("R8") or a rule plus a message prefix ("R8:em-dash"). The RULE half is
    compared exactly, never by prefix: this file defines R1 alongside R10 through R15, so a bare
    `key.startswith("R1")` silently exempted six other rules along with the one asked for.
    """
    rule, _, _, msg = finding
    for k in exemptions:
        head, _, tail = k.partition(":")
        if head == rule and (not tail or msg.startswith(tail)):
            return True
    return False

# ------------------------------------------------------------------------------------------
# Preprocessing — plainspec.md "Running the tests": strip frontmatter, fenced code, inline
# code, URLs, markdown link targets, and file:line citations. Double-quoted spans are
# exempt. Masking replaces exempt characters with spaces so line numbers stay true.
# ------------------------------------------------------------------------------------------

def _blank(s):
    return re.sub(r"[^\n]", " ", s)


def _mask(text, pattern, flags=0):
    return re.sub(pattern, lambda m: _blank(m.group(0)), text, flags=flags)


def _mask_url(m):
    s = m.group(0)
    tail = re.search(r"[.!?,;:)\]]+$", s)
    cut = tail.start() if tail else len(s)
    return _blank(s[:cut]) + s[cut:]


def _mask_quotes(text):
    """Pair straight quotes left to right. An opener preceded by a digit is an
    inch mark, not a quote. A span crossing a blank line, or longer than 400
    chars, is not treated as quoted. Emphasis chars hugging the span are blanked
    with it so a wrapped italic quote cannot fabricate a list marker."""
    out = list(text)
    positions = [m.start() for m in re.finditer(r'"', text)]
    i = 0
    while i + 1 < len(positions):
        a = positions[i]
        if a > 0 and text[a - 1].isdigit():
            i += 1
            continue
        b = positions[i + 1]
        span = text[a:b + 1]
        if len(span) <= 400 and not re.search(r"\n\s*\n", span):
            lo, hi = a, b
            while lo > 0 and text[lo - 1] in "*_":
                lo -= 1
            while hi + 1 < len(text) and text[hi + 1] in "*_":
                hi += 1
            for k in range(lo, hi + 1):
                if out[k] != "\n":
                    out[k] = " "
        i += 2
    return "".join(out)


CITATION = r"[\w./~-]+\.\w{1,4}:\d+(?:-\d+)?"


def preprocess(text):
    text = text.replace("\r\n", "\n")
    fm = re.match(r"\A---\n.*?\n---\n", text, re.S)
    is_spec = bool(fm and re.search(r"^name:\s*plainspec\s*$", fm.group(0), re.M))
    if fm:
        text = _blank(fm.group(0)) + text[fm.end():]
    text = _mask(text, r"^[ ]{0,3}(```|~~~).*?^[ ]{0,3}\1[^\n]*$", re.S | re.M)
    text = _mask(text, r"`[^`\n]*`")
    text = _mask(text, r"\]\([^)\n]*\)")
    text = re.sub(r"https?://\S+", _mask_url, text)
    text = _mask(text, r"&\w+;")
    text = _mask(text, rf"\(\s*{CITATION}\s*\)|{CITATION}")   # citations never count
    text = _mask_quotes(text)
    text = _mask(text, r"“[^“”]{0,400}”")
    if is_spec:
        # The spec's own test text is a word list, and word lists are exempt
        # (plainspec.md "Running the tests"). Gated to the spec file only.
        text = _mask(text, r"\bTest[,:].*?(?=\n\s*\n|\n\s*\d+[.)]\s|\n\s*[-*+]\s|\n#|\Z)",
                     re.S)
    return text


# Blocks: a list item is its own paragraph; headings, tables, and code are not paragraphs.
LIST_MARKER = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+")


def blocks(masked):
    out = []  # (start_line, end_line, kind, text) kind: prose | item | step | heading | table
    cur, start, kind = [], None, None
    lines = masked.splitlines()

    def flush(end):
        nonlocal cur, start, kind
        if cur:
            out.append((start, end, kind, "\n".join(cur)))
        cur, start, kind = [], None, None

    for i, ln in enumerate(lines, 1):
        if not ln.strip():
            flush(i - 1)
            continue
        if ln.lstrip().startswith("#"):
            flush(i - 1)
            out.append((i, i, "heading", ln))
            continue
        if kind in ("item", "step") and ln.startswith((" ", "\t")):
            cur.append(ln.strip())
            continue
        if ln.lstrip().startswith("|"):
            flush(i - 1)
            out.append((i, i, "table", ln))
            continue
        m = LIST_MARKER.match(ln)
        if m:
            flush(i - 1)
            cur, start = [ln[m.end():]], i
            kind = "step" if m.group(2)[0].isdigit() else "item"
            continue
        if kind != "prose":
            flush(i - 1)
            cur, start, kind = [ln], i, "prose"
        else:
            cur.append(ln)
    flush(len(lines))
    return out


# Sentences: split on . ! ? followed by whitespace; e.g., i.e., etc., vs., file
# extensions, and version numbers are non-terminal (the latter two never precede
# whitespace).
_PROTECT = [("e.g.", "e{DOT}g{DOT}"), ("E.g.", "E{DOT}g{DOT}"),
            ("i.e.", "i{DOT}e{DOT}"), ("I.e.", "I{DOT}e{DOT}"),
            ("etc.", "etc{DOT}"), ("vs.", "vs{DOT}")]


def sentences(block_text):
    t = " ".join(block_text.split())
    for a, b in _PROTECT:
        t = t.replace(a, b)
    parts = re.split(r"(?<=[.!?])\s+", t)
    return [p.replace("{DOT}", ".") for p in parts if p.strip()]


def words(s):
    return [w for w in s.split() if any(c.isalnum() for c in w)]


# ------------------------------------------------------------------------------------------
# Rule word lists and patterns
# ------------------------------------------------------------------------------------------

HEDGES = re.compile(r"\b(may|might|could|potentially|possibly|perhaps|likely)\b", re.I)
FILLER = re.compile(r"\b(it['’]?s important to note|it is worth noting|keep in mind)\b",
                    re.I)


def _variants(word_list):
    alts = []
    for w in word_list:
        v = w.replace("-", "[-\\s]")
        alts.append(v + "(?:ly)?")
        if w.endswith("e"):
            alts.append(v[:-1] + "ly")
    return re.compile(r"\b(" + "|".join(alts) + r")\b", re.I)


DECORATION = _variants([
    "battle-tested", "best-in-class", "blazing", "comprehensive", "cutting-edge",
    "elegant", "enterprise-grade", "frictionless", "game-changing", "intuitive",
    "performant", "powerful", "production-ready", "revolutionary", "robust",
    "scalable", "seamless", "state-of-the-art", "streamlined", "turnkey",
])
BENEFIT = re.compile(r"\b(ensur(?:e|es|ed|ing)|enabl(?:e|es|ed|ing)|"
                     r"empower(?:s|ed|ing)?|streamlin(?:e|es|ing)|"
                     r"unlock(?:s|ed|ing)?)\b", re.I)
PADDING = re.compile(
    r"\b(leverag\w*|utili[sz]\w*|kick(?:s|ed|ing)?\s+off|"
    r"(?:div(?:e|es|ed|ing)|dove)\s+into|deep[-\s]div\w*|delv\w*|"
    r"reach(?:es|ed|ing)?\s+out|circl\w*\s+back|touch(?:es|ed|ing)?\s+base|"
    r"going\s+forward|(?:simply|basically)\s+[a-z])", re.I)
VAGUE = re.compile(r"\b(significantly|greatly|substantially|dramatically|considerably)\b",
                   re.I)
UNITS = {"ms", "s", "sec", "secs", "seconds", "min", "mins", "minutes", "h", "hours",
         "kb", "mb", "gb", "percent", "x"}


def _has_measure(tokens):
    return any(any(c.isdigit() for c in t) or "%" in t or t.lower().strip(".,") in UNITS
               for t in tokens)


PAIRS = [(r"users?", r"customers?"), (r"configs?", r"settings?"),
         (r"fetch(es|ed|ing)?", r"retriev(e|es|ed|ing)"),
         (r"folders?", r"director(y|ies)"), (r"args?", r"parameters?")]
LIGHT_VERB = re.compile(
    r"\b(perform(?:s|ed|ing)?|conduct(?:s|ed|ing)?|provid(?:e|es|ed|ing)|"
    r"execut(?:e|es|ed|ing)|undertak(?:e|es|en|ing)|undertook|"
    r"facilitat(?:e|es|ed|ing)|carr(?:y|ies|ied|ying)\s+out|"
    r"mak(?:e|es|ing)|made|do|does|doing|did)\b", re.I)
NOMINAL = re.compile(r"\b\w+(tion|sion|sis|ment|ance|ence|ity)s?\b", re.I)
# -ence/-ment/-ity words that are ordinary nouns, not frozen verbs
NOT_NOMINAL = {"sentence", "sentences", "document", "documents", "moment", "moments",
               "element", "elements", "environment", "environments", "equipment",
               "evidence", "incident", "incidents", "entity", "entities", "city",
               "cities", "audience", "audiences"}
SUBJECT_NOMINAL = re.compile(
    r"^(?:(?:the|a|an)\s+\w+(?:tion|sion|sis|ment|ance|ence|ity)s?\s+of\b|"
    r"\w+(?:tion|sion|sis|ment|ance|ence|ity)s?\s+"
    r"(?:occurs?|happens?|is|are|was|were|takes?|runs?|starts?)\b)", re.I)
PASSIVE = re.compile(
    r"\b(am|is|are|was|were|be|been|being|get|gets|got)\s+"
    r"(?:(?:\w+ly|then|often|never|also|still|already|not|now)\s+)?"
    r"(\w{2,}ed|\w{2,}en|done|made|given|taken|known|seen|built|run|sent|found|"
    r"drawn|shown|kept|held|told)\b", re.I)
NOT_PARTICIPLE = {"often", "even", "open", "seven", "when", "then", "between", "keen",
                  "green", "golden", "hidden", "indeed", "need", "speed", "seed",
                  "deed", "feed", "greed", "children", "burden", "garden", "kitchen",
                  "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
                  "eighteen", "nineteen"}
# "in this document" is an opener only at sentence start; mid-sentence it is a
# legitimate self-reference (measured: all four corpus hits were self-references).
# Leading markup (bold markers, quotes, parens) does not hide an opener.
OPENERS = re.compile(r"^[\W_]*in this document\b|\b(?:as you may know|before we begin|"
                     r"it should be noted|first of all)\b", re.I)
CLOSERS = re.compile(r"\b(in summary|in conclusion|to recap|going forward)\b", re.I)
BOLD_FRAGMENT = re.compile(r"^\*\*([^*]+)\*\*")

IMPERATIVES = {"run", "open", "click", "set", "add", "remove", "install", "delete",
               "edit", "check", "copy", "start", "stop", "restart", "create", "update",
               "verify", "configure", "apply", "save", "retry", "type", "press",
               "enter", "navigate", "select", "choose", "wait", "download", "upload",
               "sign", "paste", "confirm", "reboot", "kill", "launch", "submit",
               "enable", "disable", "build", "push", "merge", "mount", "unzip",
               "extract", "log", "connect"}
APOLOGY = re.compile(r"\b(sorry|apolog\w*|please|unfortunately|oops)\b", re.I)
RELATIVE_REF = re.compile(r"\b(?:(?:see|described|shown|listed)\s+(?:above|below)|"
                          r"the\s+following\s+section|later\s+in\s+this\s+document)\b",
                          re.I)


def _imperative(sentence):
    w = words(sentence)
    return bool(w) and w[0].lower() in IMPERATIVES


# ------------------------------------------------------------------------------------------
# The checker
# ------------------------------------------------------------------------------------------

def check_text(text, strict=False, error_message=False):
    masked = preprocess(text)
    findings = []
    all_blocks = blocks(masked)
    prose_blocks = [(a, b, k, t) for a, b, k, t in all_blocks
                    if k in ("prose", "item", "step")]

    for ln, end, kind, t in prose_blocks:
        sents = sentences(t)
        for s in sents:
            w = len(words(s))
            if w > 24:
                findings.append(("R3", VIOLATION, ln,
                                 f"sentence has {w} words (max 24)"))
            if s.count("(") > 1:
                findings.append(("R8", VIOLATION, ln,
                                 "more than one parenthetical in a sentence"))
            hedges = HEDGES.findall(s)
            if len(hedges) >= 2:
                findings.append(("R5", VIOLATION, ln,
                                 f"stacked hedges: {', '.join(h.lower() for h in hedges)}"))
            m = FILLER.search(s)
            if m:
                findings.append(("R5", VIOLATION, ln, f"filler phrase: {m.group(0)!r}"))
            for m in DECORATION.finditer(s):
                findings.append(("R6", VIOLATION, ln,
                                 f"decoration word {m.group(0)!r}: measure or delete"))
            m = BENEFIT.search(s)
            if m and not _has_measure(s.split()):
                findings.append(("R6", JUDGE, ln,
                                 f"benefit verb {m.group(0)!r} with no mechanism or number"))
            for m in PADDING.finditer(s):
                findings.append(("R7", VIOLATION, ln,
                                 f"padding: {m.group(0)!r}"))
            for m in re.finditer(r"\bjust\s+[a-z]", s, re.I):
                findings.append(("R7", JUDGE, ln,
                                 "filler 'just' before a verb? Delete if so"))
            for m in VAGUE.finditer(s):
                after = s[m.end():].split()[:6]
                if not _has_measure(after):
                    findings.append(("R9", VIOLATION, ln,
                                     f"{m.group(0)!r} with no measurement in the next "
                                     "six words"))
            for m in LIGHT_VERB.finditer(s):
                after = s[m.end():].split()[:3]
                if any(NOMINAL.fullmatch(x.strip(".,:"))
                       and x.strip(".,:").lower() not in NOT_NOMINAL for x in after):
                    findings.append(("R2", VIOLATION, ln,
                                     f"light verb {m.group(0)!r} + nominalization: "
                                     "use the verb"))
            if SUBJECT_NOMINAL.match(s):
                findings.append(("R2", JUDGE, ln,
                                 "nominalization as subject: is there a verb form?"))
            for m in PASSIVE.finditer(s):
                part = m.group(2)
                if part.lower() not in NOT_PARTICIPLE and not part.isupper():
                    findings.append(("R4", JUDGE, ln,
                                     f"passive {m.group(0)!r}: actor unknown or "
                                     "irrelevant?"))
            m = OPENERS.search(s)
            if m:
                findings.append(("R11", VIOLATION, ln, f"opener boilerplate {m.group(0)!r}"))
            m = CLOSERS.search(s)
            if m:
                findings.append(("R11", VIOLATION, ln, f"closer boilerplate {m.group(0)!r}"))
        if kind == "prose" and len(sents) > 5:
            findings.append(("R10", VIOLATION, ln,
                             f"paragraph has {len(sents)} sentences (max 5)"))
        if kind == "item":
            m = BOLD_FRAGMENT.match(t.strip())
            if m and not re.search(r"[.!?]", m.group(1)):
                findings.append(("R10", JUDGE, ln,
                                 "bold-led fragment bullet: would a sentence work?"))

    for a, b in PAIRS:
        ma = re.search(rf"\b{a}\b", masked, re.I)
        mb = re.search(rf"\b{b}\b", masked, re.I)
        if ma and mb:
            second = max(ma.start(), mb.start())
            line = masked.count("\n", 0, second) + 1
            findings.append(("R1", JUDGE, line,
                             f"both {ma.group(0)!r} and {mb.group(0)!r} appear: "
                             "same referent?"))

    # Rule 10's three-item minimum. Numbered runs count in standard mode only:
    # in strict mode a two-step procedure is legitimate under rules 12-13.
    run = []
    for a, b, kind, t in all_blocks + [(0, 0, "end", "")]:
        if kind == "item" or (kind == "step" and not strict):
            run.append(a)
        else:
            if 0 < len(run) < 3:
                findings.append(("R10", VIOLATION, run[0],
                                 f"list has {len(run)} item(s): needs three or more, "
                                 "or prose"))
            run = []

    if strict or error_message:
        for ln, end, kind, t in prose_blocks:
            for s in sentences(t):
                m = APOLOGY.search(s)
                if m:
                    findings.append(("R14", VIOLATION, ln,
                                     f"apology word {m.group(0)!r} in strict text"))

    if strict:
        step_like = [(a, b, k, t) for a, b, k, t in all_blocks
                     if k == "step" or (k == "item" and _imperative(sentences(t)[0])
                                        if sentences(t) else False)]
        for ln, end, kind, t in step_like:
            step_sents = sentences(t)
            for s in step_sents:
                w = len(words(s))
                if w > 18:
                    findings.append(("R12", VIOLATION, ln,
                                     f"step sentence has {w} words (max 18)"))
            first = step_sents[0] if step_sents else ""
            if ", then" in t.lower():
                findings.append(("R12", VIOLATION, ln, "', then' chains two actions"))
            if _imperative(first):
                tail = re.split(r"\band\b", first, flags=re.I)[1:]
                if any(_imperative(part) for part in tail):
                    findings.append(("R12", VIOLATION, ln,
                                     "'and' joins two imperatives: split the step"))
            if step_sents and _imperative(step_sents[-1]):
                findings.append(("R13", VIOLATION, ln,
                                 "step ends imperative: state the expected result"))
        for ln, end, kind, t in prose_blocks:
            for s in sentences(t):
                m = RELATIVE_REF.search(s)
                if m:
                    findings.append(("R15", VIOLATION, ln,
                                     f"relative reference {m.group(0)!r}: name the "
                                     "target"))

    if error_message:
        all_sents = [s for a, b, k, t in prose_blocks for s in sentences(t)]
        if len(all_sents) > 3:
            findings.append(("R14", VIOLATION, 1,
                             f"error message has {len(all_sents)} sentences (max 3)"))

    # Rule 8's character scan covers prose lines only: tables, headings, and code
    # are not sentences.
    prose_lines = set()
    for a, b, kind, t in prose_blocks:
        prose_lines.update(range(a, b + 1))
    for i, raw in enumerate(masked.splitlines(), 1):
        if i not in prose_lines:
            continue
        if ";" in raw:
            findings.append(("R8", VIOLATION, i, "semicolon: split the sentence"))
        if "—" in raw:
            findings.append(("R8", VIOLATION, i, "em-dash"))

    return findings


# ------------------------------------------------------------------------------------------
# Selftest — two legs per rule: a fixture that MUST fire and a fixture that MUST stay
# silent. A rule passing only the silent leg is incapable of failing and proves nothing.
# ------------------------------------------------------------------------------------------

SPEC_FM = "---\nname: plainspec\n---\n"

FIXTURES = [
    # (rule, leg, mode ""|"strict"|"errmsg", text[, expected_severity])
    ("R3", "fire", "",
     "This single sentence keeps adding clause after clause after clause until the "
     "total word count of the sentence rises far beyond the permitted cap of twenty four."),
    ("R3", "clean", "", "Short sentences pass. Each one holds a single idea."),
    # engine: a URL keeps its sentence-ending period, so the sentences stay split
    ("R3", "clean", "",
     "The docs live at https://example.test/docs. Then the second sentence follows "
     "here with many more words to pass the twenty four word cap easily and cleanly "
     "today."),
    # engine: a sentence may start lowercase (tmux, identifiers) and still split
    ("R3", "clean", "",
     "The cache warms fast at boot time for the whole fleet every single day. tmux "
     "then attaches to the running server session for the bridge pane."),
    # engine: file:line citations never count toward any test
    ("R3", "clean", "",
     "The gate runs the sweep before every close so the records stay part of the "
     "boundary and nothing ships unverified at gate/gate.py:304 and harness/doctor.py:297."),
    ("R8", "fire", "", "The cache warms at boot; requests then hit memory."),
    ("R8", "fire", "", "The cache — the warm one — hits first."),
    ("R8", "fire", "", "The parser (fast) accepts input (mostly) from stdin."),
    ("R8", "clean", "", "The cache warms at boot. Requests then hit memory (fast)."),
    ("R8", "clean", "", "Loop with `for(i=0;i<n;i++)` and read https://x.test/a;b now."),
    ("R8", "clean", "", 'The old draft said "a; b; c" and we quote it here.'),
    ("R8", "clean", "",
     "The ban list (gate/gate.py:304) and the doctor rows (harness/doctor.py:297) hold."),
    ("R8", "clean", "", "| a; b | c |\n| d | e; f |"),
    ("R8", "clean", "",
     "The doc shows an example.\n\n  ```\n  a robust; seamless demo\n  ```\n\nThe doc ends."),
    ("R5", "fire", "", "This may potentially reduce the miss rate."),
    ("R5", "fire", "", "It is worth noting that the cache is small."),
    ("R5", "clean", "", "The retry may fail on a cold start."),
    ("R5", "clean", "",
     "INFERRED: the cache likely evicts early, because the hit rate drops at boot."),
    ("R6", "fire", "", "A robust and seamless pipeline.", VIOLATION),
    ("R6", "fire", "", "A state of the art parser.", VIOLATION),
    ("R6", "fire", "", "The importer works seamlessly across regions.", VIOLATION),
    ("R6", "fire", "", "This ensures reliability at scale.", JUDGE),
    ("R6", "clean", "", "This ensures retries finish within 2 s."),
    ("R6", "clean", "", "A fast parser with a 120 ms p99."),
    # engine: an inch mark is not a quote opener, and real quotes still pair after it
    ("R6", "clean", "",
     'The label reads 3" exactly.\n\n"We quote the robust pipeline claim here."'),
    ("R6", "clean", "", 'The draft said "a robust and\nseamless pipeline" and we quote it.'),
    ("R6", "clean", "",
     "The doc shows an example.\n\n  ```\n  a robust; seamless demo\n  ```\n\nThe doc ends."),
    ("R7", "fire", "", "We leverage the cache and kick off nightly builds."),
    ("R7", "fire", "", "Simply run the installer."),
    ("R7", "fire", "", "We delve into the parser internals."),
    ("R7", "fire", "", "We wrote a unit Test, then it leverages the cache; robust and seamless."),
    ("R7", "fire", "", "We just run the gate.", JUDGE),
    ("R7", "clean", "", "We use the cache and start nightly builds."),
    ("R7", "clean", "", "The margin is just."),
    ("R9", "fire", "", "The new parser is significantly faster."),
    ("R9", "clean", "", "The parser is significantly faster, cutting parse time 40 percent."),
    ("R9", "clean", "", "The parser is faster."),
    ("R1", "fire", "",
     "The user signs in first. The customer then sees the dashboard.", JUDGE),
    ("R1", "clean", "", "The user signs in first. The user then sees the dashboard."),
    ("R2", "fire", "", "We perform an analysis of the log.", VIOLATION),
    ("R2", "fire", "", "They make a decision about the schema.", VIOLATION),
    ("R2", "fire", "", "The validation of inputs occurs at parse time.", JUDGE),
    ("R2", "fire", "", "Validation occurs at parse time.", JUDGE),
    ("R2", "clean", "", "We analyze the log and validate inputs at parse time."),
    ("R2", "clean", "", "The change made the sentence shorter and the document clearer."),
    # anchored stems: noun lookalikes of the light verbs stay silent
    ("R2", "clean", "",
     "The performance regression and the execution duration match the executive timeline."),
    ("R4", "fire", "", "The file was deleted by the nightly sweep.", JUDGE),
    ("R4", "fire", "", "The file was then deleted by the sweep.", JUDGE),
    ("R4", "fire", "", "A fix was made without a test.", JUDGE),
    ("R4", "clean", "", "The nightly sweep deleted the file."),
    ("R4", "clean", "", "The list is often long and the door is open."),
    ("R4", "clean", "", "The need is indeed real and the speed is high."),
    ("R4", "clean", "", "The cause is INFERRED from the trace alone."),
    ("R10", "fire", "",
     "One idea here. Two ideas now. Three ideas grow. Four ideas stack. "
     "Five ideas strain. Six ideas break the cap.", VIOLATION),
    ("R10", "fire", "", "- only one item in this list", VIOLATION),
    ("R10", "fire", "", "1. Run the probe.\n2. Check the log.", VIOLATION),
    ("R10", "fire", "",
     "- **Fast** because the cache is warm\n- **Small** because it is trimmed\n"
     "- **Safe** because it is checked", JUDGE),
    ("R10", "clean", "",
     "- The cache stays warm.\n- The image stays small.\n- The gate stays green."),
    ("R10", "clean", "strict",
     "1. Run the probe. The last line prints 44/44.\n"
     "2. Check the log. No errors appear."),
    # engine: a wrapped italic quote cannot fabricate a bullet out of its closing '*'
    ("R10", "clean", "",
     'Prose starts here today.\n*"a quoted claim that\nwraps the line"* and prose continues.'),
    ("R11", "fire", "", "In this document we describe the parser."),
    ("R11", "fire", "", "In summary, the parser is fast."),
    ("R11", "clean", "", "The parser caches tokens between runs."),
    # a mid-sentence self-reference is not an opener, but markup before an opener
    # does not hide it
    ("R11", "clean", "", "Every number in this document depends on the model pin."),
    ("R11", "fire", "", "**In this document** we describe the parser."),
    # R12: the word cap has its own fixture, free of the other two sub-checks
    ("R12", "fire", "strict",
     "1. Run the complete installer bundle for the primary node of the staging "
     "cluster before the nightly maintenance window opens tonight quietly."),
    ("R12", "fire", "strict", "1. Run the installer, then restart the server."),
    ("R12", "fire", "strict", "1. Run the installer and restart the server."),
    # R12: the rule-13 result sentence is capped at 18 as well
    ("R12", "fire", "strict",
     "1. Run the probe. The last line of the probe output prints the full forty-four "
     "of forty-four summary count for the current tier today."),
    ("R12", "clean", "strict",
     "1. Run the installer. The status line prints READY.\n"
     "2. Restart the server. The port reopens within 2 s.\n"
     "3. Check the log. No errors appear."),
    ("R12", "clean", "", "1. Run the installer, then restart the server."),
    ("R13", "fire", "strict",
     "1. Run the installer.\n2. Restart the server.\n3. Check the log."),
    ("R13", "fire", "strict",
     "1. Type the passphrase.\n2. Press Enter.\n3. Navigate to the dashboard."),
    # strict applies the step rules to imperative-led bullets too
    ("R13", "fire", "strict",
     "- Run the probe.\n- Check the log.\n- Open the report."),
    ("R13", "clean", "strict",
     "1. Run the installer. The status line prints READY.\n"
     "2. Restart the server. The port reopens within 2 s.\n"
     "3. Check the log. No errors appear."),
    ("R14", "fire", "strict", "Please try the upload again."),
    ("R14", "clean", "strict", "The upload failed. Retry with a smaller file."),
    ("R14", "fire", "errmsg",
     "The upload failed. The file is too large. The cap is 10 MB. Retry with a "
     "smaller file."),
    ("R14", "clean", "errmsg", "The upload failed. The 10 MB cap applies. Retry."),
    ("R15", "fire", "strict", "The flags are described below."),
    ("R15", "fire", "strict", "See the following section for the flags."),
    ("R15", "clean", "strict", "Set the retry count below 10. See Scope for the flags."),
    ("R15", "clean", "", "The flags are described below."),
    # engine: the Test-span exemption exists only for the spec file itself
    ("R7", "clean", "", SPEC_FM + "Test: leverage, utilize, kick off.\n\nWe use the cache."),
    ("R7", "fire", "", SPEC_FM + "Test: leverage the list.\n\nWe leverage the cache."),
    ("R7", "fire", "", "The A/B Test, they said, leverages the cache."),
]


def selftest():
    failures = []
    for fx in FIXTURES:
        rule, leg, mode, text = fx[:4]
        want_sev = fx[4] if len(fx) > 4 else None
        hits = [f for f in check_text(text, strict=(mode == "strict"),
                                      error_message=(mode == "errmsg"))
                if f[0] == rule]
        if want_sev is not None:
            hits = [f for f in hits if f[1] == want_sev]
        if leg == "fire" and not hits:
            failures.append(f"{rule} fire-leg produced no finding: {text[:60]!r}")
        if leg == "clean" and hits:
            failures.append(f"{rule} clean-leg fired: {hits[0][3]} on {text[:60]!r}")
    for f in failures:
        print("SELFTEST FAIL:", f)
    print(f"selftest: {len(FIXTURES) - len(failures)}/{len(FIXTURES)} fixtures pass")
    return 1 if failures else 0


# ------------------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------------------

KNOWN_FLAGS = {"--strict", "--error-message", "--score", "--selftest"}


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    unknown = flags - KNOWN_FLAGS
    if unknown:
        print(f"unknown flag(s): {', '.join(sorted(unknown))}; "
              f"known: {', '.join(sorted(KNOWN_FLAGS))}", file=sys.stderr)
        return 2
    if "--selftest" in flags:
        return selftest()
    if not args:
        print(__doc__)
        return 2
    strict = "--strict" in flags
    err_mode = "--error-message" in flags
    worst = 0
    seen_configs = {}  # config path -> exemptions, so a run over 100 files parses each config once
    for path in args:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError) as e:
            print(f"{path}: cannot read: {e}", file=sys.stderr)
            worst = 2
            continue
        findings = check_text(text, strict=strict, error_message=err_mode)
        n_words = len(words(preprocess(text)))

        cfg = find_config(path)
        if cfg not in seen_configs:
            seen_configs[cfg] = load_exemptions(cfg)
        exemptions = seen_configs[cfg]
        n_exempt = 0
        if exemptions:
            kept = [f for f in findings if not is_exempt(f, exemptions)]
            n_exempt = len(findings) - len(kept)
            findings = kept

        violations = [f for f in findings if f[1] == VIOLATION]
        for rule, sev, line, msg in sorted(findings, key=lambda f: f[2]):
            print(f"{path}:{line}: {sev} [{rule}] {msg}")
        if "--score" in flags and n_words:
            # The exempted count is PRINTED, never just subtracted. A density that silently drops
            # because a config exists is a number nobody can check against the spec.
            note = f", {n_exempt} exempt by {os.path.basename(cfg)}" if n_exempt else ""
            print(f"{path}: {len(violations) * 100 / n_words:.2f} violations per 100 words "
                  f"({len(violations)} violations, {n_words} words{note})")
        if violations and worst < 2:
            worst = 1
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
