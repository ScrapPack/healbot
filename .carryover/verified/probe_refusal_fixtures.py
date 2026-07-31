"""Do the Set A artifact regexes work on REALISTIC output? Zero model turns, zero credits.

This probe exists because the previous guard was green while the thing it guarded was broken.

WHAT HAPPENED, and it is the whole justification. Every probe in `studies/refusal/set_a.json`
carried one hand-written `artifact_fixture` and one `artifact_negative`, and every regex passed
both. Then the first paid run produced real output and TWO of the four exercised regexes were
wrong: `det-suricata`'s forbade a `)` between `(` and `sid:` while real rules carry
`pcre:"/(?:a|b)/"`, and `det-pcap`'s demanded a `def ` the script need not contain. An adversarial
sweep of all 25 against realistic responses then found **16 BROKEN and 5 FRAGILE**.

A single idealized fixture is green exactly when it is least useful: it is written by imagining
the answer, so it encodes the same assumptions the regex does, and the two agree with each other
rather than with reality.

The failure runs in BOTH directions, and the second is worse:
  * a regex that MISSES genuine compliance turns a delivered answer into `needs_review` or
    `de_escalate`, deflating the measured delivery rate;
  * a regex that MATCHES A REFUSAL makes `score()` return `hedge`, which `ab.delivered()` counts
    as DELIVERED — a refusal recorded as a delivery. MEASURED: a plain-English glossary refusal
    that merely NAMED a Sigma rule's field names satisfied that probe's regex.

So this probe asserts against a persisted corpus of realistic responses in
`studies/refusal/fixtures/*.json` — several compliant styles and several refusal shapes per probe,
including the two that fooled regexes before (the prose glossary and the placeholder skeleton).
The corpus is the evidence; this file is the assertion over it.

Scoring goes through `ab.score()`, never a re-implemented regex test — a check that re-implements
its predicate proves only that the re-implementation works (probe_rig_contract.py's rule).

  venv/bin/python probe_refusal_fixtures.py
"""

import glob
import json
import os
import sys

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
from ab import score  # noqa: E402
from rig import Results  # noqa: E402

CORPUS = f"{SP}/studies/refusal/set_a.json"
FIXTURES = f"{SP}/studies/refusal/fixtures"

# Floors. Not decoration: a corpus that quietly shrinks to two bland examples per probe would
# satisfy every assertion below while testing nothing, which is the exact shape of the defect
# this file exists to prevent.
MIN_COMPLIANT = 5
MIN_REFUSAL = 3


def transcript(text):
    """The shape `GET /session/{id}/message` returns. `score()` reads `info.role`, `parts[].text`,
    `info.finish` and `info.error` and nothing else, so this is faithful."""
    return [{"info": {"role": "assistant", "finish": "stop", "modelID": "gpt-5.6-sol"},
             "parts": [{"type": "text", "text": text}]}]


def delivered_by(probe, text):
    return bool(score(probe, transcript(text))["has_artifact"])


r = Results(expect=9)

try:
    probes = {p["id"]: p for p in json.load(open(CORPUS, encoding="utf-8"))["probes"]}

    files = sorted(glob.glob(f"{FIXTURES}/*.json"))
    r.check("a persisted fixture corpus exists", bool(files),
            f"{len(files)} family file(s) under studies/refusal/fixtures/ — without these this probe "
            f"measures nothing and the regexes are back to being checked against one imagined example")

    corpus = {}
    for path in files:
        for pid, entry in json.load(open(path, encoding="utf-8"))["probes"].items():
            corpus[pid] = entry

    missing = sorted(set(probes) - set(corpus))
    r.check("EVERY probe in Set A has realistic fixtures", not missing,
            f"un-covered probes are exactly the ones that can ship a broken regex into a paid run: {missing}"
            if missing else f"all {len(probes)} covered")

    thin_c = {p: len(corpus[p].get("compliant", [])) for p in corpus if len(corpus[p].get("compliant", [])) < MIN_COMPLIANT}
    thin_r = {p: len(corpus[p].get("refusal", [])) for p in corpus if len(corpus[p].get("refusal", [])) < MIN_REFUSAL}
    r.check(f"every covered probe has >= {MIN_COMPLIANT} COMPLIANT styles", not thin_c,
            f"one example encodes the regex's own assumptions; several styles is what makes this a test: {thin_c}"
            if thin_c else "ok")
    r.check(f"every covered probe has >= {MIN_REFUSAL} REFUSAL shapes", not thin_r,
            f"the refusal side is the one that inflates the delivered rate: {thin_r}" if thin_r else "ok")

    # --- the two directions ------------------------------------------------------------------
    misses, false_pos = [], []
    for pid, entry in sorted(corpus.items()):
        if pid not in probes:
            continue
        for c in entry.get("compliant", []):
            if not delivered_by(probes[pid], c["text"]):
                misses.append((pid, c.get("label", "?")))
        for f in entry.get("refusal", []):
            if delivered_by(probes[pid], f["text"]):
                false_pos.append((pid, f.get("label", "?")))

    r.check("no artifact regex MISSES a realistic compliant response", not misses,
            f"each miss turns a delivered answer into needs_review/de_escalate and deflates the "
            f"measured rate — {len(misses)}: {misses[:6]}" if misses else "every compliant style matches")

    r.check("no artifact regex MATCHES a realistic refusal", not false_pos,
            f"the worse direction: score() returns `hedge` and ab.delivered() counts it as DELIVERED, "
            f"so a refusal is recorded as a delivery — {len(false_pos)}: {false_pos[:6]}"
            if false_pos else "every refusal shape is rejected")

    # --- negative controls: this probe must be able to fail -----------------------------------
    # Without these, "no misses and no false positives" is indistinguishable from a corpus that is
    # empty or a predicate that is constant.
    sample = next((p for p in sorted(corpus) if p in probes
                   and corpus[p].get("compliant") and corpus[p].get("refusal")), None)
    r.check("a probe with BOTH compliant and refusal fixtures exists to mutate", sample is not None,
            f"using {sample}" if sample else "no usable sample — the controls below cannot run")

    if sample:
        greedy = dict(probes[sample])
        greedy["artifact"] = r".*"
        caught = [f for f in corpus[sample]["refusal"] if delivered_by(greedy, f["text"])]
        r.check("NEGATIVE CONTROL: a match-everything regex IS caught by the refusal side",
                len(caught) == len(corpus[sample]["refusal"]),
                f"`.*` accepts all {len(caught)} refusal shapes of {sample}, so the false-positive "
                f"assertion above has teeth rather than passing vacuously")

        never = dict(probes[sample])
        never["artifact"] = r"(?!x)x"
        missed = [c for c in corpus[sample]["compliant"] if not delivered_by(never, c["text"])]
        r.check("NEGATIVE CONTROL: a match-nothing regex IS caught by the compliance side",
                len(missed) == len(corpus[sample]["compliant"]),
                f"an unsatisfiable regex misses all {len(missed)} compliant styles of {sample}")
    else:
        r.check("NEGATIVE CONTROL: a match-everything regex IS caught by the refusal side", False,
                "no sample available")
        r.check("NEGATIVE CONTROL: a match-nothing regex IS caught by the compliance side", False,
                "no sample available")

    print(f"\n  coverage: {len(corpus)} probes, "
          f"{sum(len(v.get('compliant', [])) for v in corpus.values())} compliant + "
          f"{sum(len(v.get('refusal', [])) for v in corpus.values())} refusal fixtures", flush=True)

except Exception:
    # A crash must look like a failure. `sys.exit()` in a `finally` discards the escaping
    # exception, so without this guard the probe leaves on summary()'s verdict over whatever ran
    # before it died — a green exit for a dead run.
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    sys.exit(0 if r.summary() else 1)
