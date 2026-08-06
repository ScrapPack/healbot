"""Does a synthesized arm hold exactly its declared delta — and nothing else? FREE, no model turn.

arms.py's whole claim is byte-level: arm B is arm A plus ONE skill, frozen at launch,
reproducible from the run dir, refusing on any tamper or drift. Every one of those verbs
gets a control here, because each failure mode is silent in exactly the way this suite's
history punishes: a leaked external skill contaminates both arms equally (invisible in the
comparison), a tampered snapshot materializes yesterday's config under today's manifest,
and a moved lockfile swaps the dependency tree under a frozen study. The same applies to the
one env var the arm factory must never touch: four rows drive `arms._serve_env` directly and
two of them compile a MUTATED arms.py, because the way that guard gets violated is a future
edit to serve(), not an input any run can supply.

The decisive rows boot BOTH arms from their materialized configs and read GET /skill off
the live servers: the delta skill must be present in B, absent in A, and B's skill set must
equal A's plus exactly the delta — with a known external skill (healbot-traps, installed on
this machine) absent from both, proving the external scan really is off and the config-dir
channel (skill/index.ts:205-208, unconditional) really is the only one open.

  venv/bin/python probe_arm_factory.py
"""

import json
import os
import shutil
import sys
import tempfile

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import arms  # noqa: E402
from rig import Api, Results, db  # noqa: E402

r = Results(expect=23)
TMP = tempfile.mkdtemp(prefix="probe-arm-factory-")
PORT_A, PORT_B = 4781, 4782
DELTA_NAME = "probe-delta-skill"
DELTA_BODY = """---
name: probe-delta-skill
description: Inert marker skill for probe_arm_factory — proves the config-dir delta channel.
---

# Probe delta skill

If you can read this from a server's /skill list, the synthesized delta channel works.
"""
procs = []


def walk_files(root):
    out = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "node_modules"]
        for f in filenames:
            out.add(os.path.relpath(os.path.join(dirpath, f), root))
    return out


def raises(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return None
    except (ValueError, RuntimeError) as exc:
        return str(exc)


def mutant_arms(old, new):
    """arms.py recompiled with one line changed, as an isolated namespace. The violation
    the XDG_DATA_HOME guard exists for is a future EDIT to serve(), not a runtime input, so
    its negative control has to be an edit — the same tactic probe_rig_contract.py uses when
    it feeds itself the pre-fix sources out of git. An anchor that does not match exactly
    once raises HERE, so a rotted anchor cannot turn into a vacuous green below."""
    src = open(arms.__file__, encoding="utf-8").read()
    if src.count(old) != 1:
        raise RuntimeError(f"mutation anchor appears {src.count(old)}x in arms.py, want 1 — "
                           f"re-derive it: {old!r}")
    ns = {"__name__": "arms_mutant", "__file__": arms.__file__}
    exec(compile(src.replace(old, new), arms.__file__, "exec"), ns)
    return ns


try:
    # -- define()'s guards, each refused loudly -------------------------------------------
    r.check("define refuses a non-kebab arm name", raises(arms.define, "Bad_Name") is not None, "")
    r.check("define refuses a delta with a name but no body",
            raises(arms.define, "b", skill_name="x") is not None, "half a delta is no delta")
    r.check("define refuses an empty delta body",
            raises(arms.define, "b", skill_name="x", skill_body="  \n") is not None, "")
    hole = raises(arms.define, "b", skill_name="x", skill_body="hi\n!`rm -rf ~`\n")
    r.check("define refuses a delta body carrying the bang-backtick shell hole, and says why",
            hole is not None and "shell" in hole,
            "harness/env.sh:63-68 — the body would shell-execute on slash-invoke")

    # -- freeze(): equality except the delta, determinism, and the filename ban ------------
    run1, run2 = f"{TMP}/run1", f"{TMP}/run2"
    a = arms.define("base")
    b = arms.define("plus-delta", skill_name=DELTA_NAME, skill_body=DELTA_BODY)
    m1 = arms.freeze([a, b], run1)
    r.check("the two arms freeze IDENTICAL config files — the delta is the only difference",
            m1["base"]["files"] == m1["plus-delta"]["files"] and m1["base"]["delta"] is None
            and m1["plus-delta"]["delta"]["skill_name"] == DELTA_NAME,
            f"{len(m1['base']['files'])} files each")
    m2 = arms.freeze([a, b], run2)
    r.check("freeze is deterministic — same inputs, byte-identical manifests in a second run dir",
            m1 == m2, "the manifest carries no timestamp or path that varies per freeze")
    snapshot_files = walk_files(f"{run1}/arms")
    banned = {f for f in snapshot_files if os.path.basename(f) in
              {"AGENTS.md", "CLAUDE.md", "CONTEXT.md", "SKILL.md"}}
    r.check("the tracked snapshot contains NO banned filename — SKILL.md exists only in LIVE",
            not banned, f"snapshot files: {len(snapshot_files)}, banned hits: {sorted(banned)}")
    with open(f"{run1}/arms/plus-delta/_delta_skill.md", "rb") as fh:
        stored = fh.read()
    r.check("the delta body is stored under a safe name with the manifest's exact sha",
            stored == DELTA_BODY.encode()
            and m1["plus-delta"]["delta"]["body_sha256"] == arms._sha(stored), "")

    # -- materialize(): exact delta, byte fidelity, and the three tamper refusals ---------
    live_a = arms.materialize(run1, "base")
    live_b = arms.materialize(run1, "plus-delta")
    delta_rel = m1["plus-delta"]["delta"]["materialize_at"]
    diff = walk_files(live_b) - walk_files(live_a)
    r.check("the live trees differ by EXACTLY the delta skill file",
            diff == {delta_rel} and not (walk_files(live_a) - walk_files(live_b)),
            f"diff: {sorted(diff)}")
    with open(f"{live_b}/{delta_rel}", "rb") as fh:
        materialized = fh.read()
    r.check("the materialized SKILL.md is byte-identical to the frozen body",
            materialized == DELTA_BODY.encode(), "")

    victim = f"{run1}/arms/base/files/opencode/opencode.jsonc"
    original = open(victim, "rb").read()
    with open(victim, "ab") as fh:
        fh.write(b"\n// tampered\n")
    r.check("a tampered snapshot file makes materialize REFUSE, not repair",
            raises(arms.materialize, run1, "base") is not None,
            "a snapshot that cannot reproduce its arm is a finding")
    with open(victim, "wb") as fh:
        fh.write(original)

    body_path = f"{run1}/arms/plus-delta/_delta_skill.md"
    with open(body_path, "ab") as fh:
        fh.write(b"tamper")
    r.check("a tampered delta body makes materialize REFUSE",
            raises(arms.materialize, run1, "plus-delta") is not None, "")
    with open(body_path, "wb") as fh:
        fh.write(DELTA_BODY.encode())

    manifest_path = f"{run1}/arms/base/manifest.json"
    manifest = json.load(open(manifest_path))
    manifest["lockfile_sha256"] = "0" * 64
    json.dump(manifest, open(manifest_path, "w"), indent=2, sort_keys=True)
    drift = raises(arms.materialize, run1, "base")
    r.check("a lockfile-sha mismatch makes materialize REFUSE — dependency drift is loud",
            drift is not None and "lock" in drift.lower(),
            "node_modules is pinned by the frozen lockfile, not by hope")
    manifest["lockfile_sha256"] = None
    json.dump(manifest, open(manifest_path, "w"), indent=2, sort_keys=True)
    legacy = raises(arms.materialize, run1, "base")
    r.check("a manifest with NO lockfile sha refuses too — the guard fails CLOSED, not open",
            legacy is not None and "re-freeze" in legacy.lower(),
            "the 3136cd8 review: a fresh clone froze None and materialized a dep-less arm")
    json.dump(m1["base"], open(manifest_path, "w"), indent=2, sort_keys=True)

    # No inner try/finally: the contract requires every `finally` to end on the verdict
    # exit. raises() absorbs the expected refusal; anything unexpected propagates to the
    # crash guard below, which is the failure path the contract prescribes.
    bare = f"{TMP}/bare-base"
    os.makedirs(f"{bare}/opencode")
    with open(f"{bare}/opencode/opencode.jsonc", "w") as fh:
        fh.write("{}\n")
    real_base, arms.BASE = arms.BASE, bare
    unfit = raises(arms.freeze, [arms.define("base")], f"{TMP}/run3")
    arms.BASE = real_base
    r.check("freeze REFUSES an unconstituted base (no lockfile, no node_modules) outright",
            unfit is not None and "reconstitute" in unfit.lower(),
            "a fresh clone must be a refusal at freeze time, not a silent dep-less arm")

    # -- the XDG_DATA_HOME guard, controlled in BOTH directions (rig-defects ticket 02) ----
    # It used to read `"XDG_DATA_HOME" not in env or env[...] == os.environ.get(...)`, which
    # compared the child env against a live re-read of the source that env was copied from.
    # That caught a direct write to env and nothing else. arms._serve_env now captures the
    # inherited value BEFORE the copy, so the reference is independent of what it checks.
    ANCHOR = '    env.setdefault("OPENCODE_CLIENT", "cli")\n'
    LIVE_ARG, DB_ARG = "/tmp/probe-live", "/tmp/probe.db"
    had_data_home = os.environ.pop("XDG_DATA_HOME", None)
    clean = arms._serve_env(LIVE_ARG, DB_ARG)
    r.check("with XDG_DATA_HOME unset the built env does not carry it, and the pins are the "
            "OPENCODE_DB-only isolation",
            "XDG_DATA_HOME" not in clean and clean["OPENCODE_DB"] == DB_ARG
            and clean["XDG_CONFIG_HOME"] == LIVE_ARG
            and clean["OPENCODE_DISABLE_EXTERNAL_SKILLS"] == "true", "")
    os.environ["XDG_DATA_HOME"] = "/tmp/probe-inherited"
    inherited = arms._serve_env(LIVE_ARG, DB_ARG)
    os.environ.pop("XDG_DATA_HOME", None)
    r.check("an INHERITED XDG_DATA_HOME passes through untouched — the rule is never MOVE it, "
            "and this row is red if a future edit pops it",
            inherited.get("XDG_DATA_HOME") == "/tmp/probe-inherited",
            "the old assert's first disjunct accepted a pop silently")
    direct = mutant_arms(ANCHOR, ANCHOR + '    env["XDG_DATA_HOME"] = "/tmp/probe-x"\n')
    hit = raises(direct["_serve_env"], LIVE_ARG, DB_ARG)
    r.check("an edit that sets XDG_DATA_HOME on the child env is REFUSED, and the message "
            "names the variable and the value it would have shipped",
            hit is not None and "XDG_DATA_HOME" in hit and "/tmp/probe-x" in hit, "")
    sneaky = mutant_arms(ANCHOR, ANCHOR + '    os.environ["XDG_DATA_HOME"] = "/tmp/probe-x"\n'
                                          '    env["XDG_DATA_HOME"] = "/tmp/probe-x"\n')
    leak = raises(sneaky["_serve_env"], LIVE_ARG, DB_ARG)
    os.environ.pop("XDG_DATA_HOME", None)
    r.check("the same edit routed through os.environ is refused too — THIS is the case the "
            "old assert passed, both of its disjuncts reading the source it had just moved",
            leak is not None and "XDG_DATA_HOME" in leak, "")
    if had_data_home is not None:
        os.environ["XDG_DATA_HOME"] = had_data_home

    # -- the decisive rows: boot both arms, read /skill off the live servers --------------
    procs.append(arms.serve(run1, "base", PORT_A, db("armfactory-a"), log=f"{TMP}/a.log"))
    procs.append(arms.serve(run1, "plus-delta", PORT_B, db("armfactory-b"), log=f"{TMP}/b.log"))
    skills_a = {s.get("name") for s in (Api(PORT_A)("GET", "/skill") or [])}
    skills_b = {s.get("name") for s in (Api(PORT_B)("GET", "/skill") or [])}
    r.check("arm B's server lists the delta skill — the config-dir channel is real",
            DELTA_NAME in skills_b, f"skills_b={sorted(skills_b)}")
    r.check("arm A's server does NOT list it — the delta went to exactly one arm",
            DELTA_NAME not in skills_a, f"skills_a={sorted(skills_a)}")
    r.check("B's skill set is A's plus exactly the delta — no other skill moved",
            skills_b == skills_a | {DELTA_NAME}, "set equality, not membership")
    r.check("healbot-traps (installed externally on this machine) reached NEITHER arm — "
            "the external scan is off and the synthesized dir is the only channel",
            "healbot-traps" not in skills_a and "healbot-traps" not in skills_b, "")

except Exception:
    # A crash must look like a failure. `sys.exit()` in a `finally` discards the escaping
    # exception, so without this guard the probe leaves on summary()'s verdict over whatever
    # ran before it died — a green exit for a dead run.
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    for p in procs:
        if p.poll() is None:
            p.kill()
    shutil.rmtree(TMP, ignore_errors=True)
    shutil.rmtree(f"{arms.LIVE}/run1", ignore_errors=True)
    shutil.rmtree(f"{arms.LIVE}/run2", ignore_errors=True)
    sys.exit(0 if r.summary() else 1)
