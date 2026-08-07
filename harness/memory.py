"""The decision-record store: why a choice went the way it did, and what was rejected.

WHY IT EXISTS. Retirement carries six fields and drops every reason behind them.
`healbot.ts:500-505` filters a session's history to text parts, discarding tool calls, tool
results and reasoning; `:490` deletes completed todos; `:516` and `:520-524` keep one message
each. Worse, `:550-558` archives a session whose `open.length === 0` with NO successor and no
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


def write(rec, key=None, start=None, env=None):
    """-> the path written. Validates, then replaces atomically.

    `os.replace` over a temp file in the SAME directory, because rename is only atomic within a
    filesystem and a temp directory can be on another one. A reader therefore sees either the
    old record or the new one and never a half-written file — which matters here more than it
    usually does, since the readers are other worktrees running concurrently.
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
    files = subprocess.run(["git", "diff-tree", "--no-commit-id", "--name-only", "-r", sha],
                           cwd=start or os.getcwd(), capture_output=True, text=True)
    stamped, flagged = stamp(sha, files.stdout.split(), start=start, env=env)
    if stamped:
        print(f"decision records: anchored {len(stamped)} to {sha[:8]}", file=sys.stderr)
    for rec_id, pointer in flagged:
        print(f"decision records: {rec_id} cites {pointer}, which this commit changed — "
              f"re-read it", file=sys.stderr)
    return 0


COMMANDS = {
    "path": _cmd_path,
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
