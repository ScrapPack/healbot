"""Does a synthesized arm hold exactly its declared delta — and nothing else? FREE, no model turn.

arms.py's whole claim is byte-level: arm B is arm A plus ONE skill, frozen at launch,
reproducible from the run dir, refusing on any tamper or drift. Every one of those verbs
gets a control here, because each failure mode is silent in exactly the way this suite's
history punishes: a leaked external skill contaminates both arms equally (invisible in the
comparison), a tampered snapshot materializes yesterday's config under today's manifest,
and a moved lockfile swaps the dependency tree under a frozen study.

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

r = Results(expect=17)
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
            "harness/env.sh:48-53 — the body would shell-execute on slash-invoke")

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
    json.dump(m1["base"], open(manifest_path, "w"), indent=2, sort_keys=True)

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
