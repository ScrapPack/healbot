"""The decision-record store: why a choice went the way it did, and what was rejected.

WHY IT EXISTS. Retirement carries six fields and drops every reason behind them.
`healbot.ts:569-574` filters a session's history to text parts, discarding tool calls, tool
results and reasoning; `:559` deletes completed todos; `:585` and `:589-593` keep one message
each. Worse, `:619-627` archives a session whose `open.length === 0` with NO successor and no
record at all, so the sessions that finished cleanly are exactly the ones that record nothing.
A handoff is never written to disk; its only destination is `POST /session/{id}/prompt_async`.
So the reasoning that produced a decision survives only as long as the session that made it.

WHAT A RECORD IS. A decision anchored to a commit. Not a note, not a summary, not a log line:
a question, the choice, the alternatives WITH the reason each was rejected, the evidence, and
a mandatory classification from the verification discipline (VERIFIED | TESTED | INFERRED |
SUSPECTED). The classification is what makes the store safe to read: an INFERRED record can
never reach the orientation block, which is what lets a lossy free backfill in at all.

WHY MARKDOWN FILES AND NOT A DATABASE. Three reasons, and the first one is not reviewability —
a store that never enters the tree never diffs, so "you can review it" was wrong and is not
claimed here. (1) It preserves the PROMOTION PATH: a record can be exported into a tracked
directory later, and a row in a binary index cannot. (2) It separates durable source from
disposable index, so the index can be deleted and rebuilt without a migration. (3) It
reconciles across the detached worktrees crewmates run in: one file per record, written to a
temp name and `os.replace`d, means two worktrees capturing at once cannot corrupt each other.
`superseded_by` is DERIVED at query time and never stored, so a capture is never a two-file
transaction across concurrent writers. graphify is at most a downstream consumer and never the
store of record: it rewrites graph.json wholesale with no concurrent-write story.

WHY JSON FRONTMATTER AND NOT YAML. There is no YAML parser in the stdlib and this module is
stdlib-only. A hand-rolled YAML subset is a silent-wrong-belief producer — it parses the easy
90% and mis-parses the rest without raising. `json.loads` either returns the document or
refuses by name.

WHERE THE STORE LIVES, and why it is OUTSIDE the project. SETTLED 2026-08-06 by the owner.
To be gitignored in a project you do not own, something must write a `.gitignore` into that
project — which is the exact self-ignoring-config behavior `README.md` already names as a trap
on healbot's own deliverable (`config/config.ts:297-303` seeds one at boot). Not seeding is
worse: a record carries verbatim session text, so a routine `git add -A` in a client repo would
commit the operator's prompts. Out-of-repo also keeps the project key out of every tracked
tree, so `gate.py`'s full-tree home-path scan stays clean. Costs accepted and stated in
`docs/RECORDS.md`: records do not travel with a clone, and they need backing up with the rest
of the home directory.

WHY NOT XDG, which the plan left to the builder to check. The plan's note said to prefer an XDG
path "for consistency with the harness isolation model" after checking `arms.py`'s fail-closed
refusal. Checking it inverts the recommendation, and the reason is bigger than that refusal:

  - `XDG_CONFIG_HOME` is REWRITTEN, twice, on purpose. `harness/env.sh:51-52` points it at the
    harness config root, and `arms.py:256` points it at a materialized A/B arm. A store keyed
    on it would be a different store per harness root and per arm — and the store must SPAN
    those, because a crewmate in a pool slot and the operator in a bare shell are working on
    one project and must see one set of records.
  - `XDG_DATA_HOME` is deliberately never set by anything here. `arms.py:252-265` is a refusal,
    not an assert, whose whole job is to keep `_serve_env` from introducing or moving it,
    because `auth.json` lives there. Keying on a variable the system deliberately does not
    control means two shells can disagree about where the store is, with no error at either.

  A store that silently splits in two is the wrong-belief producer this repo's whole verification
  discipline exists to prevent, so the root is FIXED: `~/.healbot`, overridable only by an
  explicit `HEALBOT_RECORDS`, which exists so a probe can point at a fixture and for no other
  reason. `arms._serve_env` copies `dict(os.environ)` and pops only three named leaks, so a
  fixture root set by a probe does reach a served arm — which is what a fixture wants.

WHY A NON-GIT DIRECTORY IS A REFUSAL. `NotAProject` rather than a fallback to the working
directory. A record's anchor IS a commit sha, so a directory with no commits cannot produce a
well-formed record; and a cwd-derived key would change when you cd into a subdirectory, which
is the same silent split rejected above. Every caller — the hook, the plugin, the doctor row —
treats the refusal as "do nothing", so it costs a would-be record and never a push.

  python3 harness/memory.py path
  python3 harness/memory.py list
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import time

CLASSIFICATIONS = ("VERIFIED", "TESTED", "INFERRED", "SUSPECTED")

# The two tiers. The owner's rule, verbatim from the grilling: memories about 3d modeling are
# worthless context bloat in a backend project. So `project` is the default and the only tier a
# record lands in unless it is explicitly about harness mechanics, which is what `global` holds
# and all it holds.
SCOPES = ("project", "global")

GLOBAL_KEY = "_global"

# A record id has to survive being a filename on three filesystems and a key in a URL-ish
# context, so the alphabet is narrower than the schema strictly needs. Rejecting rather than
# sanitizing: a sanitizer turns two distinct ids into one file and the loser vanishes.
ID_OK = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")

FENCE = "---"


class NotAProject(Exception):
    """`start` is not inside a git repository, so there is no project to key a store to."""


class RecordInvalid(Exception):
    """A record failed validation on the way in. Never on the way out — see `read`."""


# ---------------------------------------------------------------------------------------------
# Where the store is
# ---------------------------------------------------------------------------------------------


def home(env=None):
    """The store home. `HEALBOT_RECORDS` wins; otherwise `~/.healbot`. See the header for why
    this is a fixed path and not an XDG one."""
    env = os.environ if env is None else env
    override = env.get("HEALBOT_RECORDS")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    return os.path.join(os.path.expanduser("~"), ".healbot")


def main_worktree(start=None):
    """The MAIN worktree root, from any tree that shares its repository.

    `git worktree list --porcelain` names the main worktree on its first line, from every tree
    in the set. `--show-toplevel` does not: it answers with the tree you are standing in, so a
    linked worktree and a pool slot would each key their own store and a crewmate's records
    would be invisible to the operator.

    VERIFIED 2026-08-06 on this machine, and asserted in `probe_memory_store.py` over EVERY
    worktree git reports rather than over a hand-picked pair: from the main checkout, from a
    `.claude/worktrees/*` tree and from a `healbot-pool/slots/*` slot, line 1 names the same
    main tree in all three, while `--show-toplevel` returns three different paths. The paths
    themselves are deliberately not quoted here — `gate.py`'s home-path scan refuses a
    machine-anchored path in a public repo, and this docstring is not the recorded corpus.
    """
    p = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=start or os.getcwd(), capture_output=True, text=True,
    )
    if p.returncode != 0:
        raise NotAProject(f"not a git repository: {start or os.getcwd()}")
    first = p.stdout.split("\n", 1)[0].strip()
    if not first.startswith("worktree "):
        raise NotAProject(f"git worktree list gave no worktree line: {first!r}")
    return os.path.realpath(first[len("worktree "):])


def project_key(start=None):
    """-> `<basename>-<10 hex>`, stable for one project across every tree that shares it.

    The basename is there so a human reading `~/.healbot/records/` can tell the directories
    apart; the digest is what actually makes the key unique, because two checkouts of different
    projects are routinely called the same thing. Hashing the REALPATH, so a symlinked route to
    the same checkout does not split the store.
    """
    root = main_worktree(start)
    digest = hashlib.sha1(root.encode("utf-8")).hexdigest()[:10]
    base = re.sub(r"[^a-z0-9]+", "-", os.path.basename(root).lower()).strip("-") or "project"
    return f"{base}-{digest}"


def records_dir(key=None, start=None, env=None):
    """Source of truth. Holds `*.md` and nothing else — see `fingerprint`."""
    return os.path.join(home(env), "records", key or project_key(start))


def derived_dir(key=None, start=None, env=None):
    """Disposable. The index and the pre-rendered orientation block live here, NOT beside the
    records, so `fingerprint` can be a plain listing of the record directory rather than a
    listing with exceptions in it. An exception list is how a derived file eventually gets
    counted as a source one."""
    return os.path.join(home(env), "derived", key or project_key(start))


# ---------------------------------------------------------------------------------------------
# The record itself
# ---------------------------------------------------------------------------------------------


def new_id(seed, when=None, kind="d"):
    """A deterministic id from `seed`. Re-capturing identical material OVERWRITES rather than
    duplicating, which is what makes `backfill` safe to re-run.

    `when` is an epoch second and is a parameter rather than a `time.time()` call inside,
    because a caller that wants determinism (backfill, keyed on the commit's own date) and a
    caller that wants a wall clock (live capture) need different answers from one function.
    """
    stamp = time.strftime("%Y%m%d", time.localtime(time.time() if when is None else when))
    return f"{stamp}-{kind}-{hashlib.sha1(str(seed).encode('utf-8')).hexdigest()[:8]}"


def blank(**over):
    """Every field the schema names, at its empty value. Used by writers and by the probe, so a
    field added here reaches both without a second edit."""
    rec = {
        "id": "",
        "scope": "project",
        "question": "",
        "choice": "",
        "alternatives": [],       # [{option, why_rejected}]
        "rationale": "",          # the PROSE BODY, not frontmatter — see `dumps`
        "evidence": [],           # `file:line` pointers, swept by probe_citations once exported
        "classification": "",     # MANDATORY, one of CLASSIFICATIONS
        "anchor": {"commit_sha": None, "changed_files": []},
        "supersedes": None,       # an id. `superseded_by` is DERIVED — see `heads`
        "captured_at": "",
        "captured_by": "",
    }
    rec.update(over)
    return rec


def validate(rec):
    """-> the record, or raise. Called on the way IN only.

    Reading never validates, on purpose. A record written by an older build must stay readable
    or the store becomes a migration problem; and a reader that refuses is a reader that can
    make the orientation block go empty for a reason nobody sees. Selection filters instead:
    `heads()` drops anything that does not qualify, so a malformed record is inert rather than
    fatal.
    """
    for field in ("id", "question", "choice", "classification", "captured_at"):
        if not str(rec.get(field) or "").strip():
            raise RecordInvalid(f"{field} is required and empty")
    if not ID_OK.match(rec["id"]):
        raise RecordInvalid(f"id {rec['id']!r} is not [a-z0-9][a-z0-9._-]{{2,79}}")
    if rec["classification"] not in CLASSIFICATIONS:
        raise RecordInvalid(
            f"classification {rec['classification']!r} is not one of {'|'.join(CLASSIFICATIONS)} "
            f"— the field is mandatory because an unclassified claim is how INFERRED gets read "
            f"as VERIFIED")
    if rec.get("scope") not in SCOPES:
        raise RecordInvalid(f"scope {rec.get('scope')!r} is not one of {'|'.join(SCOPES)}")
    if not isinstance(rec.get("alternatives"), list):
        raise RecordInvalid("alternatives must be a list")
    for alt in rec["alternatives"]:
        if not isinstance(alt, dict) or "option" not in alt or "why_rejected" not in alt:
            raise RecordInvalid(
                "each alternative needs BOTH `option` and `why_rejected` — an alternative with "
                "no reason attached is the half a commit message already carries")
    if not isinstance(rec.get("evidence"), list):
        raise RecordInvalid("evidence must be a list")
    anchor = rec.get("anchor")
    if not isinstance(anchor, dict) or "commit_sha" not in anchor or "changed_files" not in anchor:
        raise RecordInvalid("anchor must be {commit_sha, changed_files}")
    if not isinstance(anchor["changed_files"], list):
        raise RecordInvalid("anchor.changed_files must be a list")
    return rec


def dumps(rec):
    """-> the file bytes: JSON frontmatter between `---` fences, then the rationale prose.

    The rationale lives in the BODY and not in the frontmatter for one reason worth stating:
    it is the only free-text field of any length, and a multi-paragraph string inside JSON is
    one line of escaped `\\n`s that no human can read or edit. Everything a query touches is
    structured; the one field only a human reads is prose.

    `sort_keys` and a fixed separator so two writes of one record produce identical bytes.
    Backfill determinism is asserted on exactly that.
    """
    head = dict(rec)
    body = str(head.pop("rationale", "") or "")
    text = json.dumps(head, indent=2, sort_keys=True, ensure_ascii=False)
    return f"{FENCE}\n{text}\n{FENCE}\n\n{body.rstrip()}\n"


def loads(text):
    """-> the record, with `rationale` put back from the body.

    Tolerant by construction: a file with no fences, or with unparseable JSON, comes back as a
    record whose fields are empty rather than as an exception. See `validate` for why reading
    never refuses.
    """
    rec = blank()
    if not text.startswith(FENCE):
        return rec
    end = text.find(f"\n{FENCE}", len(FENCE))
    if end < 0:
        return rec
    try:
        head = json.loads(text[len(FENCE):end])
    except (ValueError, TypeError):
        return rec
    if not isinstance(head, dict):
        return rec
    rec.update(head)
    rec["rationale"] = text[end + len(FENCE) + 1:].lstrip("\n").rstrip()
    return rec


def path_of(rec_id, key=None, start=None, env=None):
    return os.path.join(records_dir(key, start, env), f"{rec_id}.md")


def write(rec, key=None, start=None, env=None, reorient=True):
    """-> the path written. Validates, then replaces atomically.

    `os.replace` over a temp file in the SAME directory, because rename is only atomic within a
    filesystem and a temp directory can be on another one. A reader therefore sees either the
    old record or the new one and never a half-written file — which matters here more than it
    usually does, since the readers are other worktrees running concurrently.

    `reorient=False` exists for bulk writers and for one measured reason. Re-rendering the
    orientation block re-reads every record, so a backfill of N records at the default would do
    O(N^2) file reads — 500 records is a quarter of a million of them. Bulk callers render once
    at the end instead. Any single capture keeps the default, because a record that is not in the
    block yet is a record the next session does not see.
    """
    validate(rec)
    # The tier is the record's own property, so a caller never has to remember to route a
    # global record past the project key. An explicit `key` still wins, because that is how a
    # probe points one write at a fixture.
    if key is None and rec.get("scope") == "global":
        key = GLOBAL_KEY
    directory = records_dir(key, start, env)
    os.makedirs(directory, exist_ok=True)
    final = os.path.join(directory, f"{rec['id']}.md")
    tmp = os.path.join(directory, f".tmp-{rec['id']}-{os.getpid()}")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(dumps(rec))
    os.replace(tmp, final)
    if reorient:
        write_orient(key, start, env)
    return final


def read(path):
    """-> the record, or None when the file will not open. Never raises on content."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return loads(fh.read())
    except OSError:
        return None


def record_files(key=None, start=None, env=None):
    """Every `*.md` in the record directory, sorted. `.tmp-*` files are excluded by the
    extension, which is why the temp name has none: a crashed write leaves litter, not a
    record."""
    directory = records_dir(key, start, env)
    try:
        names = sorted(n for n in os.listdir(directory) if n.endswith(".md"))
    except OSError:
        return []
    return [os.path.join(directory, n) for n in names]


def load_all(key=None, start=None, env=None):
    """Every readable record in one tier, in id order."""
    out = []
    for path in record_files(key, start, env):
        rec = read(path)
        if rec is not None:
            out.append(rec)
    return out


def heads(recs):
    """The records nothing supersedes.

    `superseded_by` is derived HERE and never stored, which is what keeps a capture to one file
    write. Storing it would make superseding a two-file transaction, and two worktrees
    superseding the same record at once would leave one of the two writes lost with nothing
    reporting it.

    Death is supersession, never TTL. Time does not invalidate a decision; a code change does,
    and that is what the anchor is for.
    """
    dead = {r.get("supersedes") for r in recs if r.get("supersedes")}
    return [r for r in recs if r.get("id") not in dead]


def superseded_by(recs):
    """-> {superseded id: [ids that superseded it]}. A list because two worktrees can supersede
    one record concurrently and the store must be able to say so rather than pick a winner."""
    out = {}
    for r in recs:
        target = r.get("supersedes")
        if target:
            out.setdefault(target, []).append(r.get("id"))
    return {k: sorted(v) for k, v in out.items()}


# ---------------------------------------------------------------------------------------------
# The derived index
# ---------------------------------------------------------------------------------------------


def fingerprint(key=None, start=None, env=None):
    """A cheap answer to "has the record directory changed since the index was built".

    `(name, mtime_ns, size)` over the `*.md` files, hashed. NOT content: the point is to decide
    whether to re-read the content at all, and a fingerprint that reads every file to decide
    whether to read every file has bought nothing.

    mtime_ns rather than mtime: a 1-second mtime cannot distinguish two writes inside one
    second, which is exactly the rate a backfill writes at.
    """
    parts = []
    for path in record_files(key, start, env):
        try:
            st = os.stat(path)
        except OSError:
            continue
        parts.append(f"{os.path.basename(path)}\0{st.st_mtime_ns}\0{st.st_size}")
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()


def _sqlite():
    """-> the module, or None. `_sqlite3` is a C extension and a Python built without it imports
    fine and fails here — so the fallback is chosen by trying, not by guessing from the
    platform."""
    try:
        import sqlite3
    except ImportError:
        return None
    return sqlite3


def index_path(key=None, start=None, env=None):
    return os.path.join(derived_dir(key, start, env), "index.sqlite3")


def _haystack(rec):
    """One lowercase string per record for `LIKE` matching.

    NO FTS5. It is a compile-time option, so a store that works on this machine would fail to
    build its index on a Python without it — and the corpus is hundreds of records, where a
    full scan costs less than the branch needed to handle both. The index earns its place by
    avoiding the file reads, not by being a search engine.
    """
    bits = [rec.get("question", ""), rec.get("choice", ""), rec.get("rationale", "")]
    bits += [a.get("option", "") for a in rec.get("alternatives", []) if isinstance(a, dict)]
    bits += [str(e) for e in rec.get("evidence", [])]
    return "\n".join(bits).lower()


def rebuild_index(key=None, start=None, env=None):
    """-> (rows, backend). Rebuilds unconditionally. `query` decides WHEN; this decides HOW."""
    recs = load_all(key, start, env)
    rows = [(r.get("id", ""), r.get("classification", ""), r.get("anchor", {}).get("commit_sha"),
             _haystack(r)) for r in recs]
    sqlite3 = _sqlite()
    if sqlite3 is None:
        return rows, "python"
    directory = derived_dir(key, start, env)
    try:
        os.makedirs(directory, exist_ok=True)
        con = sqlite3.connect(index_path(key, start, env))
        with con:
            con.execute("DROP TABLE IF EXISTS rec")
            con.execute("CREATE TABLE rec (id TEXT PRIMARY KEY, class TEXT, sha TEXT, hay TEXT)")
            con.executemany("INSERT OR REPLACE INTO rec VALUES (?,?,?,?)", rows)
            con.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
            con.execute("INSERT OR REPLACE INTO meta VALUES ('fingerprint',?)",
                        (fingerprint(key, start, env),))
        con.close()
    except Exception:  # noqa: BLE001 — a derived index is never worth failing a caller over
        return rows, "python"
    return rows, "sqlite"


def index_fresh(key=None, start=None, env=None):
    """Is the stored fingerprint the current one? A missing index answers False, not an error."""
    sqlite3 = _sqlite()
    if sqlite3 is None:
        return False
    path = index_path(key, start, env)
    if not os.path.exists(path):
        return False
    try:
        con = sqlite3.connect(path)
        row = con.execute("SELECT v FROM meta WHERE k='fingerprint'").fetchone()
        con.close()
    except Exception:  # noqa: BLE001
        return False
    return bool(row) and row[0] == fingerprint(key, start, env)


def query(text="", classification=None, key=None, start=None, env=None):
    """-> matching records, in id order, whether or not an index exists.

    THE INDEX IS DISPOSABLE AND THIS IS WHERE THAT IS TRUE OR NOT. The records are always
    re-read to build the answer; the index only decides which ids are worth looking at, and
    when it is missing or stale every id is. So deleting the index and re-querying returns
    byte-identical output — which is a probe leg, because "disposable" is a claim that decays
    the moment a query starts reading a field only the index has.
    """
    recs = {r.get("id"): r for r in load_all(key, start, env)}
    needle = (text or "").strip().lower()
    ids = None
    if needle and index_fresh(key, start, env):
        sqlite3 = _sqlite()
        try:
            con = sqlite3.connect(index_path(key, start, env))
            like = "%" + needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            ids = {r[0] for r in con.execute(
                "SELECT id FROM rec WHERE hay LIKE ? ESCAPE '\\'", (like,))}
            con.close()
        except Exception:  # noqa: BLE001
            ids = None
    out = []
    for rec_id in sorted(recs):
        rec = recs[rec_id]
        if ids is not None:
            if rec_id not in ids:
                continue
        elif needle and needle not in _haystack(rec):
            continue
        if classification and rec.get("classification") != classification:
            continue
        out.append(rec)
    return out


# ---------------------------------------------------------------------------------------------
# The orientation block
# ---------------------------------------------------------------------------------------------

# Sized on `MAX_DOCUMENT_TAIL` (`harness/config/opencode/plugin/healbot.ts:151`), which is the
# number this harness already uses for "how much prose is worth carrying into a fresh context".
# Reusing it rather than picking a new one, because two caps for one question is how they drift.
ORIENT_CAP = 2000

ORIENT_HEADER = "Decisions already settled in this project (do not re-litigate without new evidence):"


def render_orient(recs, cap=ORIENT_CAP):
    """-> the block, or "" when nothing qualifies.

    FOUR FILTERS, and each one is load-bearing rather than tidy:

      - HEADS ONLY. A superseded decision is exactly the thing a fresh session must not be
        anchored to, and it is the one failure mode that would make this block worse than no
        block at all.
      - VERIFIED or TESTED ONLY. This is what makes a lossy free backfill safe: every backfilled
        record is INFERRED, so none can reach standing context however many of them exist. A
        SUSPECTED record in a system prompt is a hypothesis wearing a fact's clothes.
      - DETERMINISTIC SORT, so two sessions started a second apart get byte-identical text and
        the prompt cache is not invalidated for nothing.
      - TRUNCATION AT A RECORD BOUNDARY. Cutting mid-record would ship half a decision, and half
        a decision reads as a whole one.

    The cap is applied to the RENDERED text, not by assuming the inputs are small. 500 records
    of ordinary length is not a pathological store, and a per-record budget computed from a count
    is a cap that fails exactly when it matters.
    """
    picked = [r for r in heads(recs) if r.get("classification") in ("VERIFIED", "TESTED")]
    picked.sort(key=lambda r: (r.get("id") or ""))
    out, used = [], len(ORIENT_HEADER) + 1
    for rec in picked:
        question = " ".join(str(rec.get("question", "")).split())
        choice = " ".join(str(rec.get("choice", "")).split())
        line = f"- {question} -> {choice} [{rec.get('classification')}]"
        if used + len(line) + 1 > cap:
            break
        out.append(line)
        used += len(line) + 1
    if not out:
        return ""
    return "\n".join([ORIENT_HEADER, *out])


def orient_path(key=None, start=None, env=None):
    return os.path.join(derived_dir(key, start, env), "orient.txt")


def write_orient(key=None, start=None, env=None):
    """Pre-render the block to disk. -> the text written.

    RENDERED IN PYTHON, ON EVERY WRITE, so both injection points reduce to reading one file.
    The selection rules above are where every mistake would live, and a rule implemented twice —
    once in the opencode plugin and once in a shell hook — is a rule that will disagree with
    itself. Here there is one implementation and a probe can assert it.
    """
    text = render_orient(load_all(key, start, env))
    directory = derived_dir(key, start, env)
    try:
        os.makedirs(directory, exist_ok=True)
        path = orient_path(key, start, env)
        tmp = f"{path}.tmp-{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except OSError:
        pass  # a derived file is never worth failing a capture over
    return text


# ---------------------------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------------------------


def capture(payload, start=None, env=None, when=None):
    """-> the path written. The ONE way a record enters the store from outside this module.

    Every capture trigger routes through here — the post-commit hook, the plugin's
    `healbot_decide` tool, and `backfill`. That is deliberate and it is the answer to the
    question the plan left open about how the plugin should write. The alternative was for the
    plugin to build the record in TypeScript, and it would have put a second copy of the project
    key, the frontmatter format, the id rule and the whole validator into a file that cannot
    import this one. Two implementations of one rule is the failure the plan deletes
    `harness/records.py` to avoid; it does not stop being that failure when the second copy is
    in another language.

    `anchor.commit_sha` is left alone when absent. The capturing session does not know the sha
    of the commit its work will land in — that commit does not exist yet — so stamping is the
    post-commit hook's job and an unanchored record is a normal intermediate state, not an error.
    """
    rec = blank()
    for field in rec:
        if field in payload:
            rec[field] = payload[field]
    if not rec["captured_at"]:
        rec["captured_at"] = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if when is None else when))
    if not rec["id"]:
        rec["id"] = new_id(f"{rec['question']}\0{rec['choice']}\0{rec['captured_at']}", when=when)
    return write(rec, start=start, env=env)


def changed_in(sha, cwd=None):
    r"""-> the set of paths commit `sha` changed.

    ONE RULE, BOTH CALLS. `_cmd_stamp` and `backfill` each ran this command and each parsed it
    with `.stdout.split()` and no `core.quotePath`, which is the same pair of defects
    `gate/staleness.py:175` carried — a module that sets a flag on one git call and not on its
    sibling (review finding from the f5c21e9 push), found here on both calls (review finding
    from the 3441813 push). Two copies of a parse rule are two chances to fix one of them, so
    there is one function and both callers hold it.

    `core.quotePath=false` because quoting is git's DEFAULT: without it a non-ASCII path arrives
    as `"docs/\303\251.md"`, quotes and octal escapes included. `splitlines()` rather than
    `split()` because `split()` breaks on ALL whitespace, so a path containing a space fragments
    into pieces. `gate/gate.py:117` already parses the identical output with `splitlines()`.

    Both shapes cost the same thing and cost it SILENTLY. The mangled path matches nothing, so
    it is missing from the `anchor.changed_files` this commit writes, and `stamp` never raises
    the revalidation flag for a record whose evidence points into it — the hook goes quiet about
    the file that just moved, which reads exactly like a clean run.

    A FAILING `git` IS NOT DISTINGUISHED from a commit that changed nothing. That is what both
    call sites already did and it is left alone rather than widened under a review finding:
    each of them reaches here only after a `git rev-parse` (`_cmd_stamp`) or a `git log`
    (`commits`, which raises `NotAProject`) has already succeeded in the same directory.
    """
    out = subprocess.run(
        ["git", "-c", "core.quotePath=false",
         "diff-tree", "--no-commit-id", "--name-only", "-r", sha],
        cwd=cwd or os.getcwd(), capture_output=True, text=True)
    return {ln.strip() for ln in out.stdout.splitlines() if ln.strip()}


def stamp(sha, changed, start=None, env=None):
    """Anchor every unanchored record to `sha`, and report the ones this commit may have moved.

    -> (stamped ids, flagged [(id, evidence pointer)]).

    THE FLAG IS DERIVED AND NEVER STORED. A record whose evidence names a file this commit
    changed is a record worth re-reading, and that is all it is — it is not marked stale on
    disk, because "stale" is a judgment about whether the claim survived and nothing here can
    make it. Writing the flag down would also make it wrong the moment somebody repairs the
    record without clearing a field they do not know exists.

    Revalidation is BY ANCHOR, never by TTL. Time does not invalidate a decision; a change to
    the code the decision was about does.
    """
    changed = set(changed)
    stamped, flagged = [], []
    for rec in load_all(start=start, env=env):
        if not rec.get("anchor", {}).get("commit_sha"):
            rec["anchor"] = {"commit_sha": sha, "changed_files": sorted(changed)}
            try:
                write(rec, start=start, env=env)
                stamped.append(rec["id"])
            except RecordInvalid:
                # A record that cannot be re-validated was hand-edited into an invalid state.
                # Skipping it is right: a post-commit hook must not refuse, and must not
                # silently rewrite something a human broke into something it guesses at.
                continue
        for pointer in rec.get("evidence", []):
            target = str(pointer).split(":")[0]
            if target and target in changed:
                flagged.append((rec["id"], pointer))
    return stamped, flagged


# ---------------------------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------------------------

# `\x1e` (record separator) and `\x1f` (unit separator) rather than a printable delimiter, because
# a commit message is arbitrary text and every printable delimiter has already appeared in one.
LOG_FORMAT = "%H\x1f%aI\x1f%an\x1f%s\x1f%b\x1e"


def commits(rev_range=None, limit=None, start=None):
    """-> [{sha, when, author, subject, body}], newest first."""
    cmd = ["git", "log", f"--format={LOG_FORMAT}"]
    if limit:
        cmd.append(f"-{int(limit)}")
    if rev_range:
        cmd.append(rev_range)
    out = subprocess.run(cmd, cwd=start or os.getcwd(), capture_output=True, text=True)
    if out.returncode != 0:
        raise NotAProject(f"git log failed in {start or os.getcwd()}")
    found = []
    for chunk in out.stdout.split("\x1e"):
        parts = chunk.strip("\n").split("\x1f")
        if len(parts) == 5 and parts[0]:
            found.append(dict(zip(("sha", "when", "author", "subject", "body"), parts)))
    return found


def _cite():
    """`citegraph.CITE`, or None. Imported lazily and by path, so `memory.py` keeps working in a
    project that is not healbot — where `gate/` does not exist and evidence extraction is simply
    not available. A second copy of that regex is the alternative and it is not an improvement:
    the pattern encodes measured decisions (the extension list, the leading-dot rejection) that
    were earned by failures and would be re-earned by a copy."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        sys.path.insert(0, os.path.join(here, "gate"))
        import citegraph
    except ImportError:
        return None
    return citegraph.CITE


def as_record(commit, changed, cite=None):
    """One commit -> one INFERRED record. PURE, so the shape can be asserted without a repository.

    WHAT IS AND IS NOT RECOVERABLE, stated honestly because the whole safety argument rests on it.
    A commit message states the CHOICE and usually the reasoning. It rarely states the question
    and ALMOST NEVER states the alternatives, because by the time it is written the rejected
    options are gone from the author's head. So `alternatives` is always empty here and
    `classification` is always INFERRED — which means no backfilled record can ever reach the
    orientation block, which is exactly what makes a lossy free import safe to run over hundreds
    of commits without reading one of them.

    `supersedes` is ALWAYS None. Commit order is not supersession: two commits touching one
    subject are usually both true, and inferring a chain from chronology would silently retire
    live decisions in bulk. A chain is something a human or a capturing session asserts.
    """
    sha = commit["sha"]
    subject = commit["subject"].strip()
    # This repo's subjects read `<area>: <what changed and why>`, so the area makes the derived
    # question searchable. The question is DERIVED and says so — writing the subject into it
    # would state a question the commit never asked.
    area = subject.split(":", 1)[0].strip() if ":" in subject[:40] else ""
    question = (f"{area}: what was decided at {sha[:8]}?" if area
                else f"What was decided at {sha[:8]}?")
    body = commit["body"].strip()
    evidence = []
    if cite is not None:
        seen = set()
        for match in cite.finditer(f"{subject}\n{body}"):
            pointer = f"{match.group(1)}:{match.group(2)}"
            if pointer not in seen:
                seen.add(pointer)
                evidence.append(pointer)
    return blank(
        id=f"{commit['when'][:10].replace('-', '')}-b-{sha[:8]}",
        scope="project",
        question=question,
        choice=subject,
        alternatives=[],
        rationale=body,
        evidence=evidence,
        classification="INFERRED",
        anchor={"commit_sha": sha, "changed_files": sorted(changed)},
        supersedes=None,
        captured_at=commit["when"],
        captured_by=f"backfill:{commit['author']}",
    )


def backfill(rev_range=None, limit=None, start=None, env=None):
    """-> (written ids, skipped [(id, why)]). Mechanical, zero model calls, safe to re-run.

    Re-running OVERWRITES rather than duplicating, because the id is deterministic from the
    commit's own date and sha. A target whose existing classification is NOT `INFERRED` was
    authored or upgraded by hand, so it is skipped and reported: a backfill that silently
    downgraded a VERIFIED record to INFERRED would remove it from the orientation block, which is
    the one direction this import must never move a record.
    """
    cite = _cite()
    written, skipped = [], []
    for commit in commits(rev_range, limit, start):
        rec = as_record(commit, changed_in(commit["sha"], cwd=start), cite)
        existing = read(path_of(rec["id"], start=start, env=env))
        if existing and existing.get("classification") not in ("", "INFERRED"):
            skipped.append((rec["id"], f"hand-authored as {existing['classification']}"))
            continue
        try:
            # reorient=False: re-rendering re-reads every record, so N writes at the default is
            # O(N^2) file reads. Rendered once below instead.
            write(rec, start=start, env=env, reorient=False)
            written.append(rec["id"])
        except RecordInvalid as exc:
            skipped.append((rec["id"], str(exc)))
    write_orient(start=start, env=env)
    return written, skipped


# ---------------------------------------------------------------------------------------------
# Export — the promotion path
# ---------------------------------------------------------------------------------------------


def _home_predicate():
    """The GATE'S OWN home-path predicate, or None when it cannot be reached.

    Not a second copy. `gate/gate.py:351`'s `_home_anchored` carries a standing 14-row truth
    table validated before every scan, and it already caught one real bug (the `i == 0`
    empty-`before` case) that two ad-hoc controls missed. A re-implementation here would start
    that history over, and the place it would be wrong is a public repository.
    """
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        sys.path.insert(0, os.path.join(here, "gate"))
        import gate
    except Exception:  # noqa: BLE001 — any unreachable gate is the same answer: refuse
        return None
    return getattr(gate, "_home_anchored", None)


def export(dest, ids=None, key=None, start=None, env=None):
    """Copy records into a tracked directory. -> (exported paths, refused [(id, line)]).

    PROMOTION IS EXPLICIT AND ONE RECORD AT A TIME, never a default. Two blockers arm the moment
    a record enters the tree, and both were reasons the store moved out of the repository:

      - A tracked record joins `probe_citations.py`'s sweep, so a rotted evidence pointer turns
        tier 1 RED and REFUSES the push. That converts "flagged for re-reading" into a hard block,
        against the settled decision that this system warns and never blocks. So an exported
        record's evidence is the exporter's problem from then on, and `docs/RECORDS.md` says so.
      - A tracked record joins the full-tree home-path scan on a public repo. Records carry
        verbatim session text.

    So the scrub is FAIL-CLOSED: no predicate, no export. A weaker fallback predicate would be a
    silent downgrade of a check whose entire job is stopping a home path reaching a public
    repository, and "we exported it with the lenient scan" is not a sentence anyone would read
    before the push.
    """
    anchored = _home_predicate()
    if anchored is None:
        raise RecordInvalid(
            "cannot reach gate._home_anchored, so the home-path scrub cannot run — refusing to "
            "export rather than promoting records with a weaker check than the gate's own")
    os.makedirs(dest, exist_ok=True)
    out, refused = [], []
    for rec in load_all(key=key, start=start, env=env):
        if ids and rec.get("id") not in ids:
            continue
        text = dumps(rec)
        hit = next((ln for ln in text.split("\n") if anchored(ln)), None)
        if hit is not None:
            refused.append((rec.get("id"), hit.strip()[:120]))
            continue
        path = os.path.join(dest, f"{rec['id']}.md")
        tmp = f"{path}.tmp-{os.getpid()}"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
        out.append(path)
    return out, refused


# ---------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------


def _cmd_path(argv, env):
    print(records_dir(env=env))
    return 0


def _cmd_list(argv, env):
    recs = load_all(env=env)
    live = {r.get("id") for r in heads(recs)}
    for rec in recs:
        mark = " " if rec.get("id") in live else "S"
        print(f"{mark} {rec.get('id',''):34s} {rec.get('classification',''):9s} "
              f"{(rec.get('question') or '')[:70]}")
    print(f"\n{len(recs)} record(s), {len(live)} live, {len(recs) - len(live)} superseded")
    return 0


def _cmd_query(argv, env):
    text = argv[1] if len(argv) > 1 else ""
    for rec in query(text, env=env):
        print(f"{rec.get('id','')}  [{rec.get('classification','')}]  {rec.get('question','')}")
        print(f"    -> {rec.get('choice','')}")
    return 0


def _cmd_show(argv, env):
    if len(argv) < 2:
        print("show needs a record id", file=sys.stderr)
        return 2
    rec = read(path_of(argv[1], env=env))
    if rec is None:
        print(f"no record {argv[1]}", file=sys.stderr)
        return 1
    print(dumps(rec), end="")
    return 0


def _cmd_reindex(argv, env):
    rows, backend = rebuild_index(env=env)
    print(f"indexed {len(rows)} record(s) via {backend}")
    return 0


def _dir_opt(argv):
    """`--dir <path>`, defaulting to the cwd.

    The plugin needs this and the hook does not. A server process is launched from wherever the
    fleet launched it and holds sessions for several project directories at once, so "the
    project" is a per-call fact there, while a git hook always runs with the cwd inside the tree
    that is committing.
    """
    if "--dir" in argv:
        i = argv.index("--dir")
        if i < len(argv) - 1:
            return argv[i + 1]
    return None


def _cmd_capture(argv, env):
    """Reads ONE json record from stdin. Not from argv: a rationale is prose with newlines and
    quotes in it, and every shell in the path would get a vote on what it says."""
    try:
        payload = json.load(sys.stdin)
    except (ValueError, TypeError) as exc:
        print(f"capture: stdin is not one JSON object ({exc})", file=sys.stderr)
        return 2
    if not isinstance(payload, dict):
        print("capture: stdin must be a JSON object", file=sys.stderr)
        return 2
    try:
        print(capture(payload, start=_dir_opt(argv), env=env))
    except RecordInvalid as exc:
        print(f"capture: refused — {exc}", file=sys.stderr)
        return 2
    return 0


def _cmd_stamp(argv, env):
    """The post-commit trigger's whole body. Prints nothing when there is nothing to say."""
    start = _dir_opt(argv)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=start or os.getcwd(),
                          capture_output=True, text=True)
    if head.returncode != 0:
        return 0  # no commits yet; nothing to anchor to
    sha = head.stdout.strip()
    stamped, flagged = stamp(sha, changed_in(sha, cwd=start), start=start, env=env)
    if stamped:
        print(f"decision records: anchored {len(stamped)} to {sha[:8]}", file=sys.stderr)
    for rec_id, pointer in flagged:
        print(f"decision records: {rec_id} cites {pointer}, which this commit changed — "
              f"re-read it", file=sys.stderr)
    return 0


def _cmd_orient(argv, env):
    """Print the orientation block, re-rendering it first.

    Both injection points call THIS rather than reading the file, so a store whose derived
    directory was deleted still orients — the file is a cache of this command's answer, not the
    answer itself. Prints nothing and exits 0 when nothing qualifies, because an empty store is
    the ordinary state of a new project and not a condition worth reporting.
    """
    try:
        text = write_orient(start=_dir_opt(argv), env=env)
    except NotAProject:
        return 0  # a hook fires wherever the operator happens to be. Silence is the answer.
    if text:
        print(text)
    return 0


# The recall response cap. Larger than the orientation block because recall is PULLED — the model
# asked for it and is spending its own turn on the answer — where the block is standing cost every
# session pays whether it wanted it or not.
RECALL_CAP = 6000


def _cmd_recall(argv, env):
    """`recall <query> [--all]`. Rendered here rather than in the plugin, for the same reason
    `orient` is: the selection and the cap are the rules, and a rule implemented on both sides of
    a process boundary is a rule that will disagree with itself."""
    text = argv[1] if len(argv) > 1 else ""
    every = "--all" in argv
    try:
        recs = query(text, start=_dir_opt(argv), env=env)
    except NotAProject as exc:
        print(f"memory: {exc}", file=sys.stderr)
        return 1
    if not every:
        recs = heads(recs)
    if not recs:
        print("No decision records match that.")
        return 0
    dead = superseded_by(recs) if every else {}
    out, used = [], 0
    for rec in recs:
        block = [f"{rec.get('id')}  [{rec.get('classification')}]  {rec.get('question')}",
                 f"  chose: {rec.get('choice')}"]
        for alt in rec.get("alternatives", []):
            if isinstance(alt, dict):
                block.append(f"  rejected: {alt.get('option')} -- {alt.get('why_rejected')}")
        if rec.get("rationale"):
            block.append(f"  why: {' '.join(str(rec['rationale']).split())}")
        if rec.get("evidence"):
            block.append(f"  evidence: {', '.join(str(e) for e in rec['evidence'])}")
        if rec.get("id") in dead:
            block.append(f"  SUPERSEDED BY: {', '.join(dead[rec['id']])}")
        chunk = "\n".join(block)
        # THE CAP IS APPLIED AFTER RENDERING, and truncation lands on a record boundary. A cap
        # that assumed the inputs were small would be exactly the cap that failed on the store
        # that had grown enough to need one.
        if used + len(chunk) + 1 > RECALL_CAP:
            out.append(f"({len(recs) - len(out)} more not shown — narrow the query)")
            break
        out.append(chunk)
        used += len(chunk) + 1
    print("\n\n".join(out))
    return 0


def _cmd_backfill(argv, env):
    """`backfill [<rev-range>] [--limit N]`."""
    limit = None
    if "--limit" in argv:
        i = argv.index("--limit")
        limit = argv[i + 1] if i < len(argv) - 1 else None
    rev = next((a for a in argv[1:] if not a.startswith("--")
                and argv[argv.index(a) - 1] not in ("--limit", "--dir")), None)
    written, skipped = backfill(rev, limit, start=_dir_opt(argv), env=env)
    print(f"backfilled {len(written)} record(s), all INFERRED")
    for rec_id, why in skipped:
        print(f"  skipped {rec_id}: {why}")
    return 0


def _cmd_export(argv, env):
    """`export <dir> [<id> ...]`."""
    if len(argv) < 2:
        print("export needs a destination directory", file=sys.stderr)
        return 2
    ids = {a for a in argv[2:] if not a.startswith("--")} or None
    try:
        out, refused = export(argv[1], ids, start=_dir_opt(argv), env=env)
    except RecordInvalid as exc:
        print(f"export: refused — {exc}", file=sys.stderr)
        return 2
    print(f"exported {len(out)} record(s) to {argv[1]}")
    for rec_id, line in refused:
        print(f"  REFUSED {rec_id}: carries a machine-anchored home path — {line}",
              file=sys.stderr)
    return 1 if refused else 0


COMMANDS = {
    "path": _cmd_path,
    "orient": _cmd_orient,
    "recall": _cmd_recall,
    "backfill": _cmd_backfill,
    "export": _cmd_export,
    "list": _cmd_list,
    "query": _cmd_query,
    "show": _cmd_show,
    "reindex": _cmd_reindex,
    "capture": _cmd_capture,
    "stamp": _cmd_stamp,
}


def main(argv, env):
    """EVERY PATH RETURNS AN INT, and `NotAProject` is a named refusal rather than a traceback:
    this is invoked from a git hook, and a hook that tracebacks is a hook the operator disables."""
    if not argv or argv[0] not in COMMANDS:
        print(f"usage: memory.py {{{'|'.join(sorted(COMMANDS))}}} [args]", file=sys.stderr)
        return 2
    try:
        return COMMANDS[argv[0]](argv, env)
    except NotAProject as exc:
        print(f"memory: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ))
