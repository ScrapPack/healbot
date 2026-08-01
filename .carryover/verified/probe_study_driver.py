"""Does run_study.py hold its three contracts — pluggable scorer, frozen-arms-only launch, hidden checks? FREE.

run_study.py generalizes the refusal driver, and every generalization is a new silent-wrong-
belief surface: a scorer that overwrites spend evidence, a launch path that quietly falls
back to an environment arm, a "hidden" check that leaks into the workspace or re-runs
against a restored tree, a resume that adopts a foreign run directory. Each claim gets a
row here with the violating state actually present, per the suite's rule that green is not
evidence until you know what would have made it red.

The decisive groups: the SCORER seam (study keys merge into rows; driver-reserved keys and
malformed verdicts refuse loudly — instance one, study_refusal.py, is driven through the
same seam against the real Set A corpus); the HIDDEN CHECK (a real script executed against
a real workspace — pass, fail and timeout all RECORDED rather than raised, the workspace
byte-untouched by the harness); the RESERVATION lattice (pending_disposition's four
verdicts, including the new refusal: a complete transcript whose leased workspace vanished
cannot be recovered, only explicitly retried); and the FROZEN AUTHORITIES (corpus.json and
arm manifests written at creation, digest-verified on resume, tamper refusing — plus an AST
row proving the driver references no environment arm at all: ab.ARMS and ab.serve_arm are
unreachable from it, so frozen synthesized arms are the ONLY launch path).

Booting synthesized arms end to end is probe_arm_factory.py's job (19 rows, double-boot
/skill diff); this probe stops at the freeze/verify boundary and spends no server, no model
turn, no pool clone.

  venv/bin/python probe_study_driver.py
"""

import ast
import hashlib
import json
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import ab  # noqa: E402
import arms  # noqa: E402
import run_refusal  # noqa: E402
import run_study  # noqa: E402
import study_refusal  # noqa: E402
from rig import Results  # noqa: E402

r = Results(expect=40)
TMP = tempfile.mkdtemp(prefix="probe-study-driver-")


def message(model="gpt-5.6-sol", provider="openai", finish="stop"):
    return [{
        "info": {
            "role": "assistant",
            "modelID": model,
            "providerID": provider,
            "finish": finish,
            "tokens": {"input": 10, "output": 2, "total": 12, "cache": {"read": 3, "write": 0}},
            "cost": 0.001,
        },
        "parts": [{"type": "text", "text": "rule Fixture { meta: author = \"x\" condition: true }"}],
    }]


def raises(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
        return None
    except (ValueError, RuntimeError) as exc:
        return str(exc)


def fixture_def(**over):
    base = dict(
        NAME="fixture",
        DEFAULT_PART="set_a",
        SOURCES=[run_study.__file__],
        validate=lambda study: [],
        score=lambda probe, msgs, check=None: {"outcome": "comply", "needs_review": False, "saw_check": check},
        delivered=lambda outcome: outcome == "comply",
    )
    base.update(over)
    return SimpleNamespace(**base)


def walk_files(root):
    out = set()
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            out.add(os.path.relpath(os.path.join(dirpath, name), root))
    return out


try:
    # -- instance one: study_refusal drives through the same seam as any study -------------
    loaded = run_study.load_studydef("refusal")
    r.check("load_studydef('refusal') returns study_refusal with the full contract surface",
            loaded is study_refusal and all(callable(getattr(loaded, a)) for a in
                                            ("validate", "score", "delivered", "pilot")),
            "module identity plus the four callables")
    r.check("load_studydef refuses a study with no definition module",
            raises(run_study.load_studydef, "nosuchstudy") is not None, "")
    r.check("SOURCES pins the wrapper AND both delegated files — behavior cannot drift behind "
            "an unchanged wrapper hash",
            {os.path.basename(p) for p in study_refusal.SOURCES}
            == {"study_refusal.py", "ab.py", "run_refusal.py"}, "")
    seta = ab.load_study("refusal", "set_a")
    r.check("the real Set A corpus passes the generic contract and the study's own validate",
            run_study.validate_generic(study_refusal, seta) == [] and study_refusal.validate(seta) == [],
            "validate delegates to run_refusal.validate_study")
    fixture_probe = {"id": "fixture", "family": "defensive-detection", "artifact": r"rule\s+Fixture"}
    scored = study_refusal.score(fixture_probe, message())
    r.check("study_refusal.score keeps ab.score's verdict, adds family, drops the models collision",
            scored["outcome"] == ab.score(fixture_probe, message())["outcome"]
            and scored["family"] == "defensive-detection" and "models" not in scored,
            f"outcome={scored['outcome']}")
    r.check("delivered delegates ab's binary: comply/hedge yes, the three refusal shapes and empty no",
            all(study_refusal.delivered(o) for o in (ab.COMPLY, ab.HEDGE))
            and not any(study_refusal.delivered(o) for o in
                        (ab.REFUSE_MODEL, ab.DE_ESCALATE, ab.REFUSE_PROVIDER, ab.EMPTY)), "")
    pilot5 = study_refusal.pilot(seta)
    r.check("pilot selection is one probe per family, in family order",
            len(pilot5) == 5 and [p["family"] for p in pilot5] == list(run_refusal.FAMILIES), "")

    # -- the driver's own corpus contract: the check field rules ---------------------------
    fix = fixture_def()
    good = {"study": "fixture", "probes": [
        {"id": "p-one", "prompt": "hello"},
        {"id": "p-two", "prompt": "world", "check": "#!/bin/zsh\nexit 0\n", "check_timeout": 60},
    ]}
    r.check("a shebang'd check with a sane timeout passes the generic contract",
            run_study.validate_generic(fix, good) == [], "")
    bad_shebang = {"study": "fixture", "probes": [{"id": "c-bad", "prompt": "x", "check": "echo hi\n"}]}
    r.check("NEGATIVE CONTROL: a check without a shebang is refused — the driver execs the file directly",
            any("shebang" in e for e in run_study.validate_generic(fix, bad_shebang)), "")
    timeout_abuse = {"study": "fixture", "probes": [
        {"id": "t-orphan", "prompt": "x", "check_timeout": 5},
        {"id": "t-zero", "prompt": "x", "check": "#!/bin/zsh\n", "check_timeout": 0},
    ]}
    abuse_errors = run_study.validate_generic(fix, timeout_abuse)
    r.check("NEGATIVE CONTROL: an orphan check_timeout and a non-positive one are both refused",
            any("without a check" in e for e in abuse_errors)
            and any("positive integer" in e for e in abuse_errors), "; ".join(abuse_errors))

    # -- plan and ledger shapes, generalized to named arms ---------------------------------
    plan = run_study.make_plan(good["probes"], 1, ["a1", "a2"])
    r.check("the plan is probe-major with arms in spec order — a crash strands at most one unmatched arm",
            len(plan) == 4 and plan[0]["probe"]["id"] == plan[1]["probe"]["id"]
            and [plan[0]["arm"], plan[1]["arm"]] == ["a1", "a2"], "")
    first = {"arm": "a1", "probe": "p-one", "repeat": 1}
    completed = {run_study.row_key(first)}
    remaining = [item for item in plan
                 if (item["arm"], item["probe"]["id"], item["repeat"]) not in completed]
    r.check("resume filtering omits a completed paid triple and lands on the sibling arm",
            len(remaining) == 3 and remaining[0]["arm"] == "a2", "")
    r.check("duplicate paid triples are detected instead of silently overwritten",
            run_study.duplicate_keys([first, dict(first)]) == {run_study.row_key(first)}, "")

    # -- the scorer seam: merge, vetting, and the check handoff ----------------------------
    item = {"arm": "a1", "probe": good["probes"][1], "repeat": 1}
    chk = {"script_sha256": "s" * 64, "code": 0, "secs": 0.1, "out": "ok"}
    row = run_study.scored_row(fix, item, "ses_fixture", message(), 1.25, check=chk)
    r.check("a scored row carries pin, token, cost, elapsed evidence and the raw transcript",
            row["pin_ok"] and row["token_totals"]["input"] == 10 and row["cost"] == 0.001
            and row["elapsed"] == 1.25 and row["messages"] == message(), "")
    r.check("the check result reaches the scorer AND lands on the row as workspace_check",
            row["workspace_check"] == chk and row["saw_check"] == chk,
            "score() saw the same evidence the row records")
    hostile = fixture_def(score=lambda p, m, check=None: {"outcome": "x", "needs_review": False, "cost": 1})
    r.check("NEGATIVE CONTROL: a scorer returning a driver-reserved key is refused — spend "
            "evidence is not a scorer's to overwrite",
            "reserved" in (raises(run_study.scored_row, hostile, item, "s", message(), 1.0) or ""), "")
    partial = fixture_def(score=lambda p, m, check=None: {"needs_review": False})
    r.check("NEGATIVE CONTROL: a scorer omitting outcome/needs_review is refused",
            "omitted" in (raises(run_study.scored_row, partial, item, "s", message(), 1.0) or ""), "")
    bare = fixture_def(score=lambda p, m, check=None: "comply")
    r.check("NEGATIVE CONTROL: a bare-label scorer is refused — verdict inputs are part of the record",
            "not a dict" in (raises(run_study.scored_row, bare, item, "s", message(), 1.0) or ""), "")

    # -- hidden checks: run for real against a real workspace ------------------------------
    ws = f"{TMP}/workspace"
    os.makedirs(ws)
    with open(f"{ws}/model-output.txt", "w", encoding="utf-8") as fh:
        fh.write("the model made this\n")
    before = walk_files(ws)
    pass_probe = {"id": "c1", "prompt": "x", "check": "#!/bin/zsh\ntest -f \"$1/model-output.txt\"\n"}
    passed = run_study.run_check(pass_probe, ws)
    r.check("a passing check records code 0 with the script body's sha — the corpus pins the test",
            passed["code"] == 0 and passed["script_sha256"]
            == hashlib.sha256(pass_probe["check"].encode()).hexdigest(), "")
    fail_probe = {"id": "c2", "prompt": "x", "check": "#!/bin/zsh\ntest -f \"$1/absent.txt\"\n"}
    failed = run_study.run_check(fail_probe, ws)
    r.check("NEGATIVE CONTROL: a failing check is RECORDED (code 1), never raised — red is the measurement",
            failed["code"] == 1, f"code={failed['code']}")
    slow_probe = {"id": "c3", "prompt": "x", "check": "#!/bin/zsh\nsleep 5\n", "check_timeout": 1}
    timed = run_study.run_check(slow_probe, ws)
    r.check("NEGATIVE CONTROL: a hung check records code None with a TIMEOUT marker — not a pass, not a crash",
            timed["code"] is None and "TIMEOUT" in timed["out"], "")
    r.check("the workspace is byte-untouched by the harness: same file set, no check script inside — "
            "hidden means the model's tree never contains the test",
            walk_files(ws) == before and not any("study-check-" in f for f in walk_files(ws)),
            f"files: {sorted(walk_files(ws))}")

    # -- the reservation lattice, including the lost-workspace refusal ---------------------
    done, undone = message(), message(finish="tool-calls")
    no_check = {"id": "p", "prompt": "x"}
    with_check = {"id": "p", "prompt": "x", "check": "#!/bin/zsh\n"}
    r.check("a complete transcript with no check recovers — the evidence is whole",
            run_study.pending_disposition({"workspace": None}, no_check, done, False, None, "o") == "recover", "")
    r.check("an incomplete transcript refuses — an ambiguous interrupted call is never repeated silently",
            run_study.pending_disposition({"workspace": None}, no_check, undone, False, None, "o")
            == "refuse-incomplete", "")
    r.check("…and --retry-pending converts that refusal into an explicit, logged duplicate",
            run_study.pending_disposition({"workspace": None}, no_check, undone, True, None, "o") == "retry", "")
    r.check("a checked probe whose lease is still this run's recovers — the workspace evidence survives",
            run_study.pending_disposition({"workspace": "/x"}, with_check, done, False, "o", "o") == "recover", "")
    r.check("NEGATIVE CONTROL: a complete transcript whose workspace lease is gone (or never recorded) "
            "refuses — the check would measure a restored tree and file it under this turn",
            run_study.pending_disposition({"workspace": "/x"}, with_check, done, False, None, "o")
            == "refuse-lost-workspace"
            and run_study.pending_disposition({"workspace": None}, with_check, done, False, None, "o")
            == "refuse-lost-workspace", "")
    r.check("…and only --retry-pending may turn lost evidence into a duplicate call",
            run_study.pending_disposition({"workspace": "/x"}, with_check, done, True, "other", "o") == "retry", "")

    # -- meta: compatibility, drift channels, checkpoint -----------------------------------
    probes = good["probes"]
    expected = run_study.expected_meta(fix, "t1", False, 1, "set_a", probes, plan, good, ["a1", "a2"])
    r.check("an identical resume plan is metadata-compatible", run_study.compatible_meta(expected, expected) == [], "")
    drifted = dict(expected)
    drifted["corpus_sha256"] = "0" * 64
    r.check("NEGATIVE CONTROL: a changed corpus cannot resume under an old paid tag",
            run_study.compatible_meta(drifted, expected) == ["corpus_sha256"], "")
    moved = dict(expected)
    moved["sources_sha256"] = {"x": "0"}
    r.check("NEGATIVE CONTROL: scorer/driver code drift is its own channel — the one --rescore may cross",
            run_study.compatible_meta(moved, expected) == ["sources_sha256"], "")
    ckdir = f"{TMP}/ckpt"
    os.makedirs(ckdir)
    meta_ck = dict(expected)
    meta_ck["pending"] = {"arm": "a1", "probe": "p-one", "repeat": 1, "session": "ses_p", "workspace": None}
    run_study.checkpoint(ckdir, [first], meta_ck)
    saved_rows = json.load(open(f"{ckdir}/rows.json", encoding="utf-8"))
    saved_meta = json.load(open(f"{ckdir}/meta.json", encoding="utf-8"))
    r.check("checkpoint atomically round-trips rows and the pre-send pending reservation",
            saved_rows == [first] and saved_meta["pending"]["session"] == "ses_p", "")

    # -- frozen authorities: corpus and arms written at creation, tamper refused -----------
    armdefs = [arms.define("base"),
               arms.define("plus-delta", skill_name="probe-sd-delta",
                           skill_body="---\nname: probe-sd-delta\ndescription: probe marker\n---\n\nbody\n")]
    runpath = f"{TMP}/run-sd"
    os.makedirs(runpath)
    expected_sd = run_study.expected_meta(fix, "sd", False, 1, "set_a", probes, plan, good,
                                          ["base", "plus-delta"])
    meta_sd = run_study.create_run(runpath, good, armdefs, expected_sd)
    frozen_corpus = json.load(open(run_study.frozen_corpus_path(runpath), encoding="utf-8"))
    r.check("create_run freezes the corpus into the run dir with the meta's exact hash — resumes "
            "and rescores never reread the live studies/ file",
            run_study.corpus_hash(frozen_corpus) == expected_sd["corpus_sha256"], "")
    r.check("…and freezes both arms with per-manifest digests that verify back from disk",
            set(meta_sd["arms"]) == {"base", "plus-delta"}
            and raises(run_study.verify_frozen_arms, runpath, meta_sd) is None,
            "verify_frozen_arms passes on the untouched run dir")
    manifest_path = f"{runpath}/arms/base/manifest.json"
    original = open(manifest_path, encoding="utf-8").read()
    tampered = json.loads(original)
    tampered["delta"] = {"skill_name": "evil"}
    json.dump(tampered, open(manifest_path, "w", encoding="utf-8"), indent=2, sort_keys=True)
    r.check("NEGATIVE CONTROL: an edited arm manifest refuses resume — the authority materialize "
            "trusts is itself digest-pinned",
            "authority" in (raises(run_study.verify_frozen_arms, runpath, meta_sd) or ""), "")
    with open(manifest_path, "w", encoding="utf-8") as fh:
        fh.write(original)
    r.check("NEGATIVE CONTROL: a meta with no frozen arms refuses — a foreign run directory is "
            "never adopted",
            "not a run_study run" in (raises(run_study.verify_frozen_arms, runpath, {"arms": {}}) or ""), "")
    tree = ast.parse(open(run_study.__file__, encoding="utf-8").read())
    env_arm_refs = [node for node in ast.walk(tree)
                    if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                        and node.value.id == "ab" and node.attr in ("ARMS", "serve_arm"))
                    or (isinstance(node, ast.Name) and node.id == "serve_arm")]
    r.check("the driver references NO environment arm — ab.ARMS and ab.serve_arm are unreachable "
            "from run_study.py, so frozen synthesized arms are the only launch path",
            not env_arm_refs, "asserted from the AST, where a docstring mention cannot fool a grep")

    # -- rescore: re-derive from recorded evidence, never re-run the check -----------------
    recheck = {"script_sha256": "s" * 64, "code": 1, "secs": 0.2, "out": "assert failed"}
    v1 = fixture_def()
    saved_row = run_study.scored_row(v1, {"arm": "a1", "probe": with_check, "repeat": 1},
                                     "ses_r", message(), 1.0, check=recheck)
    v2 = fixture_def(score=lambda p, m, check=None: {
        "outcome": "fail" if (check or {}).get("code") != 0 else "comply",
        "needs_review": False, "saw_check": check})
    changed = run_study.rescore_rows(v2, [saved_row], [with_check])
    r.check("rescore re-derives from the RECORDED check result — the released workspace is never "
            "re-executed — and archives the old labels",
            changed == 1 and saved_row["outcome"] == "fail" and saved_row["saw_check"] == recheck
            and saved_row["score_history"][0]["score"]["outcome"] == "comply", "")
    r.check("re-scoring is idempotent once labels match their raw evidence",
            run_study.rescore_rows(v2, [saved_row], [with_check]) == 0, "")
    prompt_row = {"messages": [{"info": {"role": "user"},
                                "parts": [{"type": "text", "text": "the frozen prompt"}]}] + message()}
    r.check("transcript_prompt recovers the user prompt a saved row was actually asked — the "
            "rescore tamper tripwire reads evidence, not the corpus",
            run_study.transcript_prompt(prompt_row) == "the frozen prompt", "")

except Exception:
    # A crash must look like a failure. `sys.exit()` in a `finally` discards the escaping
    # exception, so without this guard the probe leaves on summary()'s verdict over whatever
    # ran before it died — a green exit for a dead run.
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    shutil.rmtree(TMP, ignore_errors=True)
    sys.exit(0 if r.summary() else 1)
