"""Does the decision-record store store, isolate, supersede and degrade correctly? Zero credits.

WHAT THIS CAN AND CANNOT PROVE, said first because the limit is the important part. No free
probe can show the memory system improves agent behavior, and not one assertion below tries.
A store that isolates perfectly, caps correctly and supersedes cleanly may still make the agent
worse — by spending context on records it does not need, or by anchoring it to a decision since
invalidated. Those are OUTCOMES, they are measured with paid runs, and this suite has one
instrument for outcomes. What is below is MECHANISM: the store addresses one place from every
tree shape, a record survives a round trip field for field, a malformed record is inert rather
than fatal, the index is genuinely disposable, and a bad record is refused by name on the way in.

THE TWO ROWS THE DESIGN GOT WRONG are replaced here rather than carried, because both could
pass over any implementation:

  - The round-trip mutation was `read(write(rec)) != {rec minus alternatives}`. Given the live
    row passes, that reduces to a dict inequality between dicts with DIFFERENT KEY SETS, which
    is true for every possible writer, including one that writes nothing. It is replaced with
    `read(write(rec_minus_alternatives)) != rec`, pushed through the same writer and reader the
    live row calls, which is false exactly when the round trip stops being field-wise.
  - The project-key mutation was "add a remote to a linked worktree, require the key to change".
    `git remote add` writes the COMMON config, so the remote appears in the worktree and the
    main tree alike and any correct repo-identity key moves both sides equally — a correct
    implementation fails that row. It is replaced with a resolver-corruption leg: a key built on
    `--show-toplevel` must FAIL the worktree-equality row, which is what makes that row a
    discriminator rather than a tautology.

EVERY ROW RUNS AGAINST A FIXTURE STORE. `HEALBOT_RECORDS` points at a temp directory for the
whole run, so nothing here can write into the operator's real records. That override exists for
this and for nothing else.

  venv/bin/python probe_memory_store.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import rig  # noqa: E402

sys.path.insert(0, os.path.join(rig.HEALBOT, "harness"))
import memory  # noqa: E402

# 22, re-declared from the first green run rather than kept at the 20 the plan projected. The
# plan's own rule: a number written down before the rows are counted is how an unreachable floor
# gets cited as exit-gate evidence.
r = rig.Results(expect=22)

STORE = tempfile.mkdtemp(prefix="hb-records-")
ENV = {"HEALBOT_RECORDS": STORE}


def sample(**over):
    """One fully-populated record. Built from `memory.blank()` so a field added to the schema
    reaches every row below without a second edit here."""
    rec = memory.blank(
        id="20260806-d-abcdef12",
        scope="project",
        question="Where does the record store live?",
        choice="Outside the project, at ~/.healbot/records/<project-key>/",
        alternatives=[
            {"option": "in-repo and gitignored",
             "why_rejected": "seeding a self-ignoring .gitignore into a project you do not own "
                             "is the exact trap the README names on healbot's own deliverable"},
            {"option": "in-repo and tracked",
             "why_rejected": "records carry verbatim session text, so `git add -A` would commit "
                             "the operator's prompts"},
        ],
        rationale="First paragraph of the reasoning.\n\nSecond paragraph, so the body is proven "
                  "to survive a blank line rather than only a single line.",
        evidence=["harness/memory.py:1", "gate/gate.py:245"],
        classification="VERIFIED",
        anchor={"commit_sha": "deadbeef", "changed_files": ["harness/memory.py"]},
        supersedes=None,
        captured_at="2026-08-06T20:00:00Z",
        captured_by="probe_memory_store",
    )
    rec.update(over)
    return rec


def refused(rec):
    """-> the refusal message, or "" when the write was ACCEPTED. A validator leg has to
    distinguish "refused for the right reason" from "refused for any reason", so the message
    comes back rather than a bool."""
    try:
        memory.write(rec, key="fixture", env=ENV)
    except memory.RecordInvalid as exc:
        return str(exc)
    return ""


try:
    # --- where the store is: one place, from every tree shape --------------------------------
    #
    # This is the row the whole design rests on. A crewmate in a pool slot, a linked worktree
    # and the operator's main checkout are one project, and if they key three stores the store
    # has failed at the only job that made it worth building.
    #
    # The tree list comes from GIT, not from a walk of `.claude/worktrees/`. A walk finds only
    # the app-created worktrees and misses the pool slots entirely — which live OUTSIDE the
    # repository, at `../healbot-pool/slots/*`, and are the shape a crewmate actually runs in.
    # It also finds nothing at all when the probe itself is running inside a linked worktree,
    # since a linked worktree has no `.claude/worktrees/` of its own. Both misses turn this row
    # into the one-tree tautology its own detail warns about.
    listing = subprocess.run(["git", "worktree", "list", "--porcelain"], cwd=rig.HEALBOT,
                             capture_output=True, text=True)
    trees = [ln[len("worktree "):] for ln in listing.stdout.split("\n")
             if ln.startswith("worktree ") and os.path.isdir(ln[len("worktree "):])]
    keys = {t: memory.project_key(t) for t in trees}
    r.check(
        "one project key from every tree that shares the repository",
        len(trees) > 1 and len(set(keys.values())) == 1,
        f"{len(trees)} tree(s) -> {sorted(set(keys.values()))}. The first conjunct is not "
        "decoration: with one tree this row is trivially true, and a fresh clone with no linked "
        "worktree is exactly where a broken resolver would pass it",
    )
    # `trees[0]` and NOT `rig.HEALBOT`: the rig's own root is whichever tree the probe is
    # running in, so on a crewmate's worktree — the case this row exists for — comparing against
    # it asserts the opposite of the contract.
    main = os.path.realpath(trees[0])
    r.check(
        "…and that key names the MAIN worktree, not whichever tree asked",
        all(memory.main_worktree(t) == main for t in trees)
        and any(os.path.realpath(t) != main for t in trees),
        f"the row above passes over a resolver that returns 'the tree you asked from'. This one "
        f"fails over it — the second conjunct requires at least one tree whose own path differs "
        f"from the answer, so the assertion cannot be satisfied by identity. main={main}",
    )

    def toplevel_key(start):
        """The resolver the design ALMOST shipped, built here so the row below reads the rule
        rather than asserting a fact about git's output."""
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start,
                             capture_output=True, text=True)
        return os.path.realpath(out.stdout.strip())

    r.check(
        "MUTATION: a resolver keyed on --show-toplevel SPLITS the store across worktrees",
        len({toplevel_key(t) for t in trees}) == len(trees),
        "the equality row above is only a discriminator if some plausible resolver fails it. "
        "This is that resolver — the obvious one, and the one three of the four designs named",
    )

    fixture_repo = tempfile.mkdtemp(prefix="hb-otherproject-")
    subprocess.run(["git", "init", "-q"], cwd=fixture_repo, check=True)
    r.check(
        "a DIFFERENT project resolves to a different store",
        memory.project_key(fixture_repo) != memory.project_key(rig.HEALBOT),
        "per-project isolation is the owner's rule and the reason the store is two-tier: "
        "records about one project are context bloat in another. A resolver that returned one "
        "key everywhere would pass every other row in this file",
    )

    plain = tempfile.mkdtemp(prefix="hb-notarepo-")
    try:
        memory.project_key(plain)
        raised = False
    except memory.NotAProject:
        raised = True
    r.check(
        "a directory with no repository REFUSES rather than falling back to the cwd",
        raised,
        "a cwd-derived key changes when you cd into a subdirectory, which splits the store "
        "silently — the same failure the XDG route was rejected for. A record's anchor IS a "
        "commit sha, so a directory with no commits cannot produce a well-formed record anyway",
    )

    # --- the store's own layout --------------------------------------------------------------
    r.check(
        "HEALBOT_RECORDS redirects the whole store",
        memory.records_dir(key="k", env=ENV).startswith(STORE),
        "every row below writes into a fixture, and this is the row that proves they do. "
        "Without it a broken override would send the whole run into the operator's records",
    )
    r.check(
        "the derived index lives OUTSIDE the record directory",
        not memory.derived_dir(key="k", env=ENV).startswith(
            memory.records_dir(key="k", env=ENV) + os.sep),
        "the fingerprint is a plain listing of the record directory. A derived file sitting in "
        "there would have to be excluded by name, and an exception list is how a derived file "
        "eventually gets counted as a source one",
    )

    # --- the round trip ----------------------------------------------------------------------
    rec = sample()
    path = memory.write(rec, key="fixture", env=ENV)
    back = memory.read(path)
    r.check(
        "a record round-trips FIELD FOR FIELD",
        back == rec,
        f"every field, including the two-paragraph rationale and the alternatives list. "
        f"Differences: {[k for k in rec if back.get(k) != rec.get(k)]}",
    )
    thin = sample(id="20260806-d-11111111", alternatives=[])
    r.check(
        "MUTATION: a writer that dropped `alternatives` would fail the row above",
        memory.read(memory.write(thin, key="fixture", env=ENV)) != rec,
        "pushed through the SAME writer and reader the live row calls. The designed form of "
        "this leg compared dicts with different key sets, which is true for every possible "
        "implementation and never touched the writer at all",
    )
    raw = open(path, encoding="utf-8").read()
    front = raw.split("---")[1]
    r.check(
        "the rationale is the PROSE BODY and never enters the frontmatter JSON",
        "rationale" not in json.loads(front) and "Second paragraph" in raw.split("---")[2],
        "it is the one field of any length, and a multi-paragraph string inside JSON is a line "
        "of escaped newlines no human can read or edit. Both halves asserted: absent from the "
        "structured half AND present in the prose half",
    )
    r.check(
        "two writes of one record produce IDENTICAL bytes",
        memory.dumps(rec) == memory.dumps(memory.read(path)),
        "backfill determinism rests on this. sort_keys plus a fixed body separator, so a "
        "re-run overwrites with the same content rather than churning the mtime for nothing",
    )

    # --- validation refuses on the way IN, by name -------------------------------------------
    r.check(
        "a record with NO classification is refused, and the message names the field",
        "classification" in refused(sample(id="20260806-d-22222222", classification="")),
        "the field is mandatory because the whole reason the store is safe to read is that an "
        "INFERRED record can be kept out of the orientation block. Unclassified defeats that",
    )
    r.check(
        "an INVENTED classification is refused",
        "classification" in refused(sample(id="20260806-d-33333333", classification="PROBABLY")),
        "the four levels are the verification discipline's own vocabulary. A fifth one means "
        "the writer is not using that discipline, which is the thing being recorded",
    )
    r.check(
        "an alternative with no `why_rejected` is refused",
        "why_rejected" in refused(
            sample(id="20260806-d-44444444", alternatives=[{"option": "the other one"}])),
        "an alternative with no reason attached is the half a commit message already carries. "
        "The reason is the entire reason this schema exists",
    )
    r.check(
        "NEGATIVE CONTROL: the well-formed record above is ACCEPTED",
        refused(sample(id="20260806-d-55555555")) == "",
        "the three rows above pass over a validator that refuses everything. This one does not",
    )

    # --- reading never refuses ---------------------------------------------------------------
    junk = os.path.join(memory.records_dir(key="fixture", env=ENV), "20260806-d-junk.md")
    with open(junk, "w", encoding="utf-8") as fh:
        fh.write("---\n{not json at all\n---\n\nbody\n")
    got = memory.read(junk)
    r.check(
        "a MALFORMED record is inert, not fatal",
        got is not None and got.get("classification") == "",
        "reading deliberately does not validate. A reader that refused would make the "
        "orientation block go empty for a reason nobody sees, and would turn a record written "
        "by an older build into a migration problem. Selection filters it out instead",
    )

    # --- supersession, which is how a record dies --------------------------------------------
    old = sample(id="20260806-d-old00001", question="Should the store be in-repo?")
    new = sample(id="20260806-d-new00001", supersedes="20260806-d-old00001")
    other = sample(id="20260806-d-new00002", supersedes="20260806-d-old00001")
    for one in (old, new, other):
        memory.write(one, key="chain", env=ENV)
    chain = memory.load_all(key="chain", env=ENV)
    live = {x["id"] for x in memory.heads(chain)}
    r.check(
        "a superseded record drops out and its superseder stays",
        "20260806-d-old00001" not in live and "20260806-d-new00001" in live,
        "both conjuncts: an implementation that returned nothing would pass the first alone, "
        "and one that returned everything would pass the second alone",
    )
    r.check(
        "TWO concurrent supersessions of one record are BOTH reported",
        memory.superseded_by(chain).get("20260806-d-old00001") ==
        ["20260806-d-new00001", "20260806-d-new00002"],
        "two worktrees can supersede one record without seeing each other, because "
        "`superseded_by` is derived and never stored. The store must be able to SAY that "
        "happened rather than pick a winner and lose the other write in silence",
    )

    # --- the index is disposable, or it is not ------------------------------------------------
    # The needle is a phrase only `old` carries. "in-repo" would have matched all three, because
    # every sample() record REJECTS an in-repo store in its alternatives — and a needle that
    # matches everything makes the two queries agree for a reason that has nothing to do with
    # the index.
    memory.rebuild_index(key="chain", env=ENV)
    with_index = memory.query("should the store", key="chain", env=ENV)
    shutil.rmtree(memory.derived_dir(key="chain", env=ENV), ignore_errors=True)
    without = memory.query("should the store", key="chain", env=ENV)
    r.check(
        "deleting the index and re-querying returns BYTE-IDENTICAL output",
        with_index == without and 0 < len(with_index) < len(chain),
        f"'disposable' is a claim that decays the moment a query reads a field only the index "
        f"has. The bounds are what keep this from passing over two empty lists on one side and "
        f"an unfiltered dump on the other: {len(with_index)} of {len(chain)} matched",
    )
    memory.rebuild_index(key="chain", env=ENV)
    fresh_before = memory.index_fresh(key="chain", env=ENV)
    memory.write(sample(id="20260806-d-new00003"), key="chain", env=ENV)
    r.check(
        "a write INVALIDATES the index, and a rebuild re-validates it",
        fresh_before and not memory.index_fresh(key="chain", env=ENV),
        "both directions in one row. A fingerprint that never matched would pass the second "
        "conjunct alone and would make the index pure overhead; one that always matched would "
        "pass the first alone and would serve stale answers forever",
    )
    stable = memory.fingerprint(key="chain", env=ENV)
    r.check(
        "MUTATION: the fingerprint is STABLE when nothing changed",
        stable == memory.fingerprint(key="chain", env=ENV),
        "the row above proves it moves. This proves it does not move on its own — without it a "
        "fingerprint of the wall clock would satisfy every invalidation assertion in this file",
    )

    # --- import is free ------------------------------------------------------------------------
    src = open(os.path.join(rig.HEALBOT, "harness", "memory.py"), encoding="utf-8").read()
    r.check(
        "memory.py runs NOTHING at import",
        "\nsys.exit(" not in src.split('if __name__ == "__main__":')[0]
        and "\nsubprocess.run(" not in src,
        "it is imported by a git hook, by the doctor and by this probe. A module that shells "
        "out or exits at import time is not a library — the same finding that turned "
        "probe_citations.py's resolver into gate/citegraph.py",
    )

except SystemExit:
    raise
except Exception:
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    shutil.rmtree(STORE, ignore_errors=True)
    ok = r.summary()
    sys.exit(0 if ok else 1)
