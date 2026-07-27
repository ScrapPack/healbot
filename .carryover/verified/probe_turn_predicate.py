"""Does `turnFinished()` actually distinguish a turn from a step? — FREE, no server, no model turn.

This is the guard on the defect that survived two phases. The plugin's completion predicate was
documented "Has the turn ended?" and read `finish` directly, which `processor.ts:443` sets at every
`step-finish` — so it was true mid-turn, on 733/733 real assistant messages carrying occupancy.
Nothing caught it because the only rig that exercised the gate drove a workload whose token jump
landed on the final step BY CONSTRUCTION, so `finishes[-1] == "stop"` passed either way.

Phase 7 replaced it with opencode's own predicate (`prompt.ts:1295`) and deleted the second gate
that had been silently compensating. That makes this function the single point where per-turn
semantics live: get it wrong and the harness aborts turns mid-flight again, or — worse now that
`RETIRE_HARD` is gone — never fires at all.

HOW THIS TESTS THE REAL SOURCE, not a copy. The predicate is extracted from
`harness/config/opencode/plugin/healbot.ts` by brace-matching `function turnFinished(`, stripped of
its TypeScript annotations, and evaluated in node. A re-implementation of the predicate inside this
probe would prove nothing about the code that ships; this runs the shipped text.

It cannot be imported instead. The plugin must export ONLY its plugin function — `getLegacyPlugins`
(`plugin/index.ts:95-108`) iterates `Object.values(mod)` and calls each as a plugin — so exporting
this helper to make it testable would break the whole guard at load time.

THE CASES are the measured distribution, not invented ones. Across 733 real assistant messages with
occupancy > 0: 677 carried `finish: "tool-calls"` (mid-turn, must be FALSE) and 56 carried
`finish: "stop"` (turn over, must be TRUE). `time.completed` is set on BOTH — per-step, in
`cleanup()` — which is why the old predicate failed and why this one must ignore it.

  venv/bin/python probe_turn_predicate.py
"""

import json
import os
import re
import subprocess
import sys

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import rig  # noqa: E402

PLUGIN = f"{rig.HEALBOT}/harness/config/opencode/plugin/healbot.ts"


def extract(source, name):
    """Brace-matched body of `function NAME(...)`, with TS annotations stripped.

    Returns None rather than raising, so a rename shows up as a named failure below instead of a
    traceback the summary would never reach.
    """
    start = source.find(f"function {name}(")
    if start == -1:
        return None
    brace = source.find("{", source.find(")", start))
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                text = source[start : i + 1]
                break
    else:
        return None
    text = re.sub(r"\(info:\s*\w+\)", "(info)", text)
    text = re.sub(r"\)\s*:\s*boolean\s*\{", ") {", text)
    return text


def run(fn_source, cases):
    """Evaluate the extracted function in node against every case; return a list of bools."""
    script = f"{fn_source}\nconsole.log(JSON.stringify({json.dumps(cases)}.map((c) => turnFinished(c))))"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"node failed: {out.stderr.strip()[:300]}")
    return json.loads(out.stdout.strip())


# name, message, expected
CASES = [
    # --- mid-turn. The 677-message majority. Every one of these was TRUE under the old predicate. ---
    ("mid-turn tool call, time.completed SET", {"finish": "tool-calls", "time": {"completed": 1}}, False),
    ("mid-turn tool call, no time.completed", {"finish": "tool-calls"}, False),
    ("the `unknown` finish opencode also excludes", {"finish": "unknown", "time": {"completed": 1}}, False),
    # --- turn over. The 56-message remainder. ---
    ("turn ended normally", {"finish": "stop", "time": {"completed": 1}}, True),
    ("turn ended, no time.completed", {"finish": "stop"}, True),
    ("length-capped turn", {"finish": "length"}, True),
    ("aborted turn", {"finish": "abort"}, True),
    # --- the error path. A dead turn is over, and a session at the gate with one must hand off. ---
    ("errored turn, no finish at all", {"error": {"name": "ContextOverflowError"}}, True),
    ("errored turn that also says tool-calls", {"finish": "tool-calls", "error": {"name": "X"}}, True),
    # --- the empty row. Exists ~20ms after prompt_async acks and is EMPTY until the turn runs. ---
    ("the empty in-flight row", {}, False),
    ("in-flight row with only time.completed", {"time": {"completed": 1}}, False),
]

r = rig.Results()
source = open(PLUGIN, encoding="utf-8").read()

try:
    fn = extract(source, "turnFinished")
    r.check(
        "turnFinished() was found in the shipped plugin",
        fn is not None,
        "a rename must fail here rather than silently skip every case below",
    )
    if fn is None:
        raise SystemExit(1 if not r.summary() else 0)

    r.check(
        "it does NOT read time.completed — the field that looks authoritative and is per-step",
        "time" not in fn,
        "processor.ts:595-596 sets it in cleanup(), which runs per step; reading it re-creates the bug",
    )
    r.check(
        "it excludes both values opencode excludes",
        '"tool-calls"' in fn and '"unknown"' in fn,
        "prompt.ts:1295 is the reference implementation",
    )

    results = run(fn, [c[1] for c in CASES])
    for (name, _msg, expected), got in zip(CASES, results):
        r.check(
            f"{'TURN OVER' if expected else 'mid-turn '} — {name}",
            got == expected,
            f"expected {expected}, got {got}",
        )

    # ---------------------------------------------------------------------------------------
    # MUTATION CHECK. Everything above passes if the extractor happened to return a function
    # that is correct for unrelated reasons. Re-run the SAME table against the OLD predicate —
    # the one that shipped for two phases — and require it to get the mid-turn cases wrong.
    #
    # This is the only assertion here that proves the table discriminates at all.
    # ---------------------------------------------------------------------------------------
    OLD = (
        "function turnFinished(info) {\n"
        "  return Boolean(info.time?.completed || info.finish || info.error)\n"
        "}"
    )
    old_results = run(OLD, [c[1] for c in CASES])
    old_wrong = [name for (name, _m, exp), got in zip(CASES, old_results) if got != exp]
    r.check(
        "MUTATION CHECK: the OLD per-step predicate FAILS this table",
        len(old_wrong) >= 3,
        f"it gets {len(old_wrong)} case(s) wrong: {old_wrong}",
    )
    r.check(
        "…and specifically it calls a mid-turn tool call 'finished' — the actual defect",
        old_results[0] is True and results[0] is False,
        "677 of 733 measured messages look like this one",
    )

    # ---------------------------------------------------------------------------------------
    # The second gate is gone, so nothing compensates for a mistake here any more.
    # ---------------------------------------------------------------------------------------
    # Strip BOTH comment forms. The constant is still discussed in prose — deliberately, since
    # "this knob was deleted, do not re-add it" is worth saying — so a check that only stripped
    # block comments would fail on the explanation of its own subject.
    code_only = re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", source, flags=re.S))
    r.check(
        "RETIRE_HARD is absent from the plugin CODE — there is no second gate behind this predicate",
        "RETIRE_HARD" not in code_only,
        "while it existed (inert), a per-step predicate was survivable; with it gone it is not",
    )
    r.check(
        "mutation check: the absence check reads real code, not an empty string",
        "RETIRE_HARD" in re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", source + "\nconst RETIRE_HARD = 1\n", flags=re.S)),
        "an absence assertion over over-stripped text passes trivially",
    )

except SystemExit:
    raise
except Exception:
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")

sys.exit(0 if r.summary() else 1)
