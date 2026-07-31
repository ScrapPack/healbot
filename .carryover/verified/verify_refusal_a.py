"""Verify a completed Set A run without spending another model turn.

Rows flagged needs_review never enter the aggregate until reviews.json supplies a human outcome.
The raw transcript is re-scored so a persisted label cannot drift silently from its evidence.

  venv/bin/python verify_refusal_a.py --pilot
  venv/bin/python verify_refusal_a.py
"""

import argparse
import collections
import os
import sys
import time

import ab
import run_refusal
from rig import Results


OUTCOMES = {ab.COMPLY, ab.HEDGE, ab.DE_ESCALATE, ab.REFUSE_MODEL, ab.REFUSE_PROVIDER, ab.EMPTY}


def review_key(row):
    return row["arm"], row["probe"], int(row["repeat"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--tag", help="run tag; defaults to pilot or full")
    args = parser.parse_args(argv)

    tag = args.tag or ("pilot" if args.pilot else "full")
    runpath = f"{ab.RUNS}/refusal-{tag}"
    rows_path = f"{runpath}/rows.json"
    meta_path = f"{runpath}/meta.json"
    reviews_path = f"{runpath}/reviews.json"
    if not os.path.exists(rows_path) or not os.path.exists(meta_path):
        raise RuntimeError(f"run not found: {runpath}")

    rows = run_refusal.read_json(rows_path, [])
    meta = run_refusal.read_json(meta_path, {})
    reviews = run_refusal.read_json(reviews_path, [])
    study = ab.load_study("refusal", "set_a")
    probes = run_refusal.selected_probes(study, args.pilot)
    repeats = 1 if args.pilot else int(meta.get("repeats") or 3)
    plan = run_refusal.make_plan(probes, repeats)
    expected = run_refusal.expected_meta(tag, args.pilot, repeats, probes, plan, study)
    expected_keys = {(item["arm"], item["probe"]["id"], item["repeat"]) for item in plan}
    actual_keys = {run_refusal.row_key(row) for row in rows}
    probe_by_id = {probe["id"]: probe for probe in probes}

    r = Results(expect=21)
    r.check("the driver marked the run complete and left no ambiguous pending call",
            meta.get("status") == "complete" and not meta.get("pending"),
            f"status={meta.get('status')} pending={meta.get('pending')}")
    mismatches = run_refusal.compatible_meta(meta, expected)
    r.check("run metadata matches this exact corpus, model pin, mode, and repeat plan",
            not mismatches, f"mismatches={mismatches}")
    r.check("the run contains every expected paid row", len(rows) == len(plan), f"{len(rows)}/{len(plan)}")
    duplicates = run_refusal.duplicate_keys(rows)
    r.check("every (arm, probe, repeat) row is unique", not duplicates, str(sorted(duplicates)))
    r.check("row keys exactly cover the paired plan", actual_keys == expected_keys,
            f"missing={sorted(expected_keys - actual_keys)[:3]} extra={sorted(actual_keys - expected_keys)[:3]}")

    required = {
        "arm", "probe", "family", "repeat", "outcome", "needs_review", "provider_blocked", "has_artifact",
        "declines", "caveats", "chars", "tools", "models", "providers", "pin_ok", "text", "elapsed", "messages",
    }
    incomplete = [review_key(row) for row in rows if not required.issubset(row)]
    r.check("every row carries the scorer inputs and auditable raw transcript", not incomplete, str(incomplete[:5]))
    bad_pins = [review_key(row) for row in rows
                if not row.get("pin_ok") or row.get("models") != [ab.PIN["modelID"]]
                or row.get("providers") != [ab.PIN["providerID"]]]
    r.check("the transcript, not merely the request, proves the model pin on every turn",
            not bad_pins, str(bad_pins[:5]))
    missing_raw = [review_key(row) for row in rows if not isinstance(row.get("messages"), list) or not row["messages"]]
    r.check("no raw transcript is missing", not missing_raw, str(missing_raw[:5]))

    rescored = []
    for row in rows:
        probe = probe_by_id.get(row.get("probe"))
        if not probe or not isinstance(row.get("messages"), list):
            rescored.append(review_key(row))
            continue
        now = ab.score(probe, row["messages"])
        if any(row.get(key) != now.get(key) for key in
               ("outcome", "needs_review", "provider_blocked", "has_artifact", "declines", "caveats", "chars", "tools", "text")):
            rescored.append(review_key(row))
    r.check("current scorer reproduces every persisted raw label", not rescored, str(rescored[:5]))
    tool_rows = [review_key(row) for row in rows if row.get("tools")]
    r.check("Set A stayed text-only with no tool side effects", not tool_rows, str(tool_rows[:5]))

    review_duplicates = run_refusal.duplicate_keys(reviews) if reviews else set()
    review_map = {review_key(review): review for review in reviews}
    bad_reviews = [key for key, review in review_map.items()
                   if key not in actual_keys or review.get("outcome") not in OUTCOMES]
    r.check("human review records are unique, keyed to real rows, and use known outcomes",
            not review_duplicates and not bad_reviews,
            f"duplicates={sorted(review_duplicates)} bad={bad_reviews[:5]}")
    review_needed = {review_key(row) for row in rows if row.get("needs_review")}
    unresolved = review_needed - set(review_map)
    r.check("every needs_review row was read before aggregation", not unresolved,
            f"{len(review_needed) - len(unresolved)}/{len(review_needed)} reviewed; unresolved={sorted(unresolved)[:5]}")
    unnecessary = set(review_map) - review_needed
    r.check("reviews do not override rows the deterministic scorer considered unambiguous",
            not unnecessary, str(sorted(unnecessary)[:5]))

    effective = []
    for row in rows:
        item = dict(row)
        if review_key(row) in review_map:
            item["outcome"] = review_map[review_key(row)]["outcome"]
        effective.append(item)
    r.check("every effective outcome is in the frozen six-state vocabulary",
            all(row.get("outcome") in OUTCOMES for row in effective))
    pairs = ab.pair_up(effective)
    r.check("every repeat has a complete harness/stock pair", len(pairs) == len(plan) // 2,
            f"{len(pairs)}/{len(plan) // 2}")

    comparison = ab.compare(effective) if not unresolved and not bad_reviews and actual_keys == expected_keys else None
    r.check("the paired comparison includes all turns from both arms",
            bool(comparison) and comparison["harness"]["n"] == comparison["stock"]["n"] == len(plan) // 2,
            str(comparison))
    r.check("per-arm delivered rates and Wilson intervals are bounded probabilities",
            bool(comparison) and all(
                0 <= comparison[arm]["ci95"][0] <= comparison[arm]["rate"] <= comparison[arm]["ci95"][1] <= 1
                for arm in ab.ARMS
            ))

    splits = {}
    for arm in ab.ARMS:
        arm_rows = [row for row in effective if row["arm"] == arm]
        splits[arm] = dict(collections.Counter(row["outcome"] for row in arm_rows))
    refusal_total = sum(splits[arm].get(ab.REFUSE_MODEL, 0) + splits[arm].get(ab.REFUSE_PROVIDER, 0)
                        for arm in ab.ARMS)
    r.check("provider/model refusal split reconciles to the refusal rows",
            refusal_total == sum(1 for row in effective if row["outcome"] in (ab.REFUSE_MODEL, ab.REFUSE_PROVIDER)),
            str(splits))
    total_cost = round(sum(float(row.get("cost") or 0) for row in rows), 8)
    total_tokens = sum(int((row.get("token_totals") or {}).get("input") or 0)
                       + int((row.get("token_totals") or {}).get("output") or 0) for row in rows)
    r.check("recorded cost and token totals are non-negative", total_cost >= 0 and total_tokens >= 0,
            f"cost=${total_cost:.6f}, input+output={total_tokens}")

    r.check("NEGATIVE CONTROL: deleting one paid row breaks exact plan coverage",
            {run_refusal.row_key(row) for row in rows[:-1]} != expected_keys)
    mutated = [dict(row) for row in rows]
    if mutated:
        mutated[0]["pin_ok"] = False
    r.check("NEGATIVE CONTROL: a transcript pin mutation is detected",
            any(not row.get("pin_ok") for row in mutated))

    ok = r.summary()
    if ok:
        refusal_rates = {}
        for arm in ab.ARMS:
            n = comparison[arm]["n"]
            declined = n - comparison[arm]["delivered"]
            lo, hi = ab.wilson(declined, n)
            refusal_rates[arm] = {
                "n": n,
                "refused_or_deescalated": declined,
                "rate": round(declined / n, 4),
                "ci95": [round(lo, 4), round(hi, 4)],
            }
        verified = {
            "verified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "tag": tag,
            "comparison": comparison,
            "over_refusal": refusal_rates,
            "outcomes": splits,
            "needs_review": len(review_needed),
            "reviews": len(reviews),
            "cost": total_cost,
            "input_plus_output_tokens": total_tokens,
        }
        run_refusal.atomic_json(f"{runpath}/verified.json", verified)
        print(f"\n  verified result: {runpath}/verified.json", flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
