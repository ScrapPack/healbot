"""Free contract checks for the Set A corpus, plan, resume ledger, and model pin.

  venv/bin/python probe_refusal_driver.py
"""

import copy
import json
import os
import sys
import tempfile

import ab
import run_refusal
from rig import Results


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


r = Results(expect=24)
study = ab.load_study("refusal", "set_a")
errors = run_refusal.validate_study(study)
r.check("the frozen Set A corpus passes every structural and artifact control", not errors, "; ".join(errors))

counts = {family: 0 for family in run_refusal.FAMILIES}
for probe in study["probes"]:
    counts[probe["family"]] += 1
r.check("the corpus is exactly five named families x five probes", len(study["probes"]) == 25 and set(counts.values()) == {5},
        str(counts))

pilot = run_refusal.selected_probes(study, True)
r.check("pilot selection takes exactly one probe from every family",
        len(pilot) == 5 and [probe["family"] for probe in pilot] == list(run_refusal.FAMILIES))
pilot_plan = run_refusal.make_plan(pilot, 1)
r.check("pilot plan is 5 probes x 1 repeat x 2 arms = 10 turns", len(pilot_plan) == 10)
full_plan = run_refusal.make_plan(study["probes"], 3)
r.check("full plan is 25 probes x 3 repeats x 2 arms = 150 turns", len(full_plan) == 150)
r.check("plan order is probe-major and leaves at most one unmatched arm after a crash",
        full_plan[0]["probe"]["id"] == full_plan[1]["probe"]["id"]
        and full_plan[0]["repeat"] == full_plan[1]["repeat"] == 1
        and [full_plan[0]["arm"], full_plan[1]["arm"]] == list(ab.ARMS))

first = {"arm": "harness", "probe": full_plan[0]["probe"]["id"], "repeat": 1}
completed = {run_refusal.row_key(first)}
remaining = [item for item in full_plan
             if (item["arm"], item["probe"]["id"], item["repeat"]) not in completed]
r.check("resume keys omit a completed paid triple", len(remaining) == 149 and remaining[0]["arm"] == "stock")
r.check("a unique row ledger has no duplicate keys", not run_refusal.duplicate_keys([first]))
r.check("duplicate paid triples are detected instead of silently overwritten",
        run_refusal.duplicate_keys([first, dict(first)]) == {run_refusal.row_key(first)})

changed = copy.deepcopy(study)
changed["probes"][0]["prompt"] += " Changed."
r.check("the corpus fingerprint changes when a frozen prompt changes",
        run_refusal.corpus_hash(study) != run_refusal.corpus_hash(changed))

bad_regex = copy.deepcopy(study)
bad_regex["probes"][0]["artifact"] = ".*"
bad_regex_errors = run_refusal.validate_study(bad_regex)
r.check("NEGATIVE CONTROL: a match-everything artifact regex is rejected",
        any("negative" in error or "generic refusal" in error for error in bad_regex_errors),
        "; ".join(bad_regex_errors[:3]))
short = copy.deepcopy(study)
short["probes"].pop()
r.check("NEGATIVE CONTROL: a truncated corpus is rejected before a paid turn",
        any("25" in error or "expected 5" in error for error in run_refusal.validate_study(short)))

expected = run_refusal.expected_meta("fixture", False, 3, study["probes"], full_plan, study)
with tempfile.TemporaryDirectory() as directory:
    meta = dict(expected)
    meta["pending"] = {"arm": "harness", "probe": first["probe"], "repeat": 1, "session": "ses_fixture"}
    run_refusal.checkpoint(directory, [first], meta)
    saved_rows = json.load(open(os.path.join(directory, "rows.json"), encoding="utf-8"))
    saved_meta = json.load(open(os.path.join(directory, "meta.json"), encoding="utf-8"))
r.check("checkpoint atomically round-trips completed rows", saved_rows == [first])
r.check("checkpoint preserves the pre-send pending reservation", saved_meta["pending"]["session"] == "ses_fixture")
r.check("an identical resume plan is metadata-compatible", not run_refusal.compatible_meta(expected, expected))
other = dict(expected)
other["corpus_sha256"] = "0" * 64
r.check("a changed corpus cannot resume under an old paid-run tag",
        run_refusal.compatible_meta(other, expected) == ["corpus_sha256"])

held, models, providers = run_refusal.pin_result(message())
r.check("the returned assistant transcript proves the requested model pin held",
        held and models == ["gpt-5.6-sol"] and providers == ["openai"])
held_wrong, _, providers_wrong = run_refusal.pin_result(message(provider="ollama"))
r.check("NEGATIVE CONTROL: a provider mismatch fails the transcript pin",
        not held_wrong and providers_wrong == ["ollama"])
r.check("a final stop is a recoverable completed turn", run_refusal.turn_complete(message()))
r.check("NEGATIVE CONTROL: a tool-calls step alone is not a completed turn",
        not run_refusal.turn_complete(message(finish="tool-calls")))

item = {"arm": "harness", "probe": {"id": "fixture", "family": "fixture", "artifact": r"rule\s+Fixture"},
        "repeat": 1}
row = run_refusal.scored_row(item, "ses_fixture", message(), 1.25)
r.check("a scored row retains the raw transcript for no-spend re-scoring", row["messages"] == message())
r.check("a scored row carries pin, token, cost, and elapsed evidence",
        row["pin_ok"] and row["token_totals"]["input"] == 10 and row["cost"] == 0.001 and row["elapsed"] == 1.25)

blocked_messages = [{
    "info": {
        "role": "assistant",
        "modelID": "gpt-5.6-sol",
        "providerID": "openai",
        "error": {"name": "UnknownError", "data": {
            "message": '{"error":{"type":"invalid_request","code":"cyber_policy"}}',
        }},
    },
    "parts": [],
}]
blocked_row = {"probe": "blocked", "messages": blocked_messages, **ab.score({"id": "blocked"}, [])}
changed_count = run_refusal.rescore_rows([blocked_row], [{"id": "blocked"}])
r.check("saved raw evidence can be re-scored without another model turn",
        changed_count == 1 and blocked_row["outcome"] == ab.REFUSE_PROVIDER and blocked_row["score_history"])
r.check("re-scoring is idempotent once persisted labels match their raw evidence",
        run_refusal.rescore_rows([blocked_row], [{"id": "blocked"}]) == 0)

sys.exit(0 if r.summary() else 1)
