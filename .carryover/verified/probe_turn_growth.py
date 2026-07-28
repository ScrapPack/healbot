"""Is ~170K the TAIL or the MIDDLE of single-turn growth? — FREE, no server, no model turn.

`RETIRE_AT = 180,000` is DERIVED, not chosen. With one per-turn gate the requirement is

    RETIRE_AT + worst_turn < ceiling

with the ceiling MEASURED at ~360K (`docs/HARDEN.md:227` — last good turn at 359,829, then 25
consecutive `ContextOverflowError`s). Until now `worst_turn` was **one measurement of one turn**
(`docs/HARDEN.md` §6). One data point cannot distinguish a tail from a middle, and the whole
derivation rests on it: if ~170K is the p50 rather than the max, 180,000 is too high.

This probe re-derives `worst_turn` from every session database on disk, for nothing.

WHAT IS MEASURED, and it is not what §6's table shows. §6 is a table of per-STEP occupancy and
was read as a whole-turn span. The quantity the gate actually needs is the END-OF-TURN to
END-OF-TURN delta:

    the gate fires at the end of turn T when O(T) >= RETIRE_AT
    worst case the session sat at O(T-1) = RETIRE_AT - 1
    so peak occupancy = RETIRE_AT + (O(T) - O(T-1))

so `worst_turn` is `max over turns of O(T) - O(T-1)`, not the span from a turn's first step to its
last. Those differ: a turn's first step already carries the whole prior window.

THE SHIPPED SOURCE IS WHAT RUNS. Both `turnFinished()` and `occupancyOf()` are brace-matched out of
`harness/config/opencode/plugin/healbot.ts` and evaluated in node, and `RETIRE_AT` is read from the
same file. Re-implementing any of the three here would measure this probe rather than the harness —
and `turnFinished()` in particular is the entire subject: grouping by message instead of by turn is
the defect Phase 7 spent a phase on.

THE NEGATIVE CONTROL is the same corpus regrouped by the OLD per-step predicate. If the per-turn
grouping were not doing anything, the two distributions would agree. They must not.

CORPORA. `hb/*.db` are this suite's own rig databases (engineered growth loops — a deliberate
worst case). `~/.local/share/opencode/opencode.db` is the real one: it is where HARNESS.md's
"733 real assistant messages" figure comes from, and this probe reproduces that 677/56 split as a
fixture check that it is reading the same corpus. Only token counts, `finish` and roles are read
from it — never message content.

BOTH CORPORA ARE REQUIRED, and this docstring said otherwise until Phase 9. It read "It is
optional; if absent, this prints NOT EXERCISED rather than passing quietly", and `NEXT.md`
inherited the claim. TESTED by running with the file absent: the check is
`r.check(..., have_real, ...)`, so absence is a **FAIL** and the probe exits **1** — the
`[NOT EXERCISED: …]` text is the detail on a failing row, not a pass. The model-specificity
assertion goes red with it, because the 223,258-token off-pin turn lives in that file.

The rig corpus is required for the opposite and more dangerous reason: `worst_turn = 175,148`
exists ONLY in `hb/*.db`, which is gitignored. Absent, the derivation does not fail — it reports
a 48.2% margin instead of 1.3%, in green. See the fixture check on `worst_sol` below.

  venv/bin/python probe_turn_growth.py
"""

import json
import os
import sqlite3
import subprocess
import sys

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import rig  # noqa: E402

PLUGIN = f"{rig.HEALBOT}/harness/config/opencode/plugin/healbot.ts"
HB = f"{SP}/hb"
REAL = os.path.expanduser("~/.local/share/opencode/opencode.db")

# The ceiling is MEASURED, not advertised (docs/HARDEN.md:227). Every conclusion below is against
# this number, so it is named once.
CEILING = 360_000

# The old predicate, verbatim from the code that shipped for two phases. It is the negative
# control: regrouping the same corpus with it must NOT produce the same distribution.
OLD_PREDICATE = "function turnFinished(info) { return Boolean(info.time?.completed || info.finish || info.error) }"


# -------------------------------------------------------------------------------------------
# Extraction — the shipped text, not a copy of it. Same technique as probe_turn_predicate.py.
# -------------------------------------------------------------------------------------------
def extract(source, name):
    """Brace-matched body of `function NAME(...)`. Returns None on a rename, never raises."""
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
                return source[start : i + 1]
    return None


def detype(text):
    """Strip the TypeScript annotations node cannot parse. Deliberately minimal."""
    import re

    text = re.sub(r"\(\s*(\w+)\s*:[^)]*\)", r"(\1)", text, count=1)
    text = re.sub(r"\)\s*:\s*\w+\s*\{", ") {", text, count=1)
    return text


def read_retire_at(source):
    """The shipped default, from the shipped file. `?? 180_000` / `|| 180_000` both spellings."""
    import re

    m = re.search(r"RETIRE_AT\s*=[^\n]*?(\d[\d_]{4,})", source)
    return int(m.group(1).replace("_", "")) if m else None


def evaluate(fn_turn, fn_occ, messages):
    """Run BOTH shipped functions over every message in one node call.

    Returns [(occupancy, turn_over), ...] aligned with `messages`.
    """
    script = (
        f"{fn_occ}\n{fn_turn}\n"
        f"const ms = {json.dumps(messages)}\n"
        "console.log(JSON.stringify(ms.map((m) => [occupancyOf(m.tokens), turnFinished(m)])))"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"node failed: {out.stderr.strip()[:400]}")
    return json.loads(out.stdout.strip())


# -------------------------------------------------------------------------------------------
# Corpus loading. Only the fields this measurement needs are pulled out of `data`.
# -------------------------------------------------------------------------------------------
def load(path):
    """[(msg_id, session_id, role, finish, error?, tokens, model)] in per-session order."""
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    rows = []
    for mid, sid, data in conn.execute("SELECT id, session_id, data FROM message ORDER BY session_id, time_created, id"):
        d = json.loads(data)
        rows.append(
            {
                "id": mid,
                "session": sid,
                "role": d.get("role"),
                "finish": d.get("finish"),
                "error": d.get("error"),
                "tokens": d.get("tokens"),
                "model": d.get("modelID"),
            }
        )
    conn.close()
    return rows


class Turn:
    """One growth observation: how much a turn added, and what it started from.

    `start` is the load-bearing field. A turn that grew 223K from an EMPTY session and a turn that
    grew 223K from 180,000 are the same number and completely different facts about the gate — the
    gate only ever faces the second.
    """

    __slots__ = ("d", "session", "model", "start")

    def __init__(self, d, session, model, start):
        self.d, self.session, self.model, self.start = d, session, model, start


def turns(rows, verdicts):
    """Group assistant messages into TURNS and return the end-of-turn-to-end-of-turn deltas.

    A user message opens a turn. Assistant messages are its steps. The turn closes on the first
    step the SHIPPED predicate calls finished. A turn that never closes (killed run, in-flight
    row) is counted as incomplete and contributes no delta — silently dropping them would let an
    empty corpus report a comfortable maximum.
    """
    by_session = {}
    for row, (occ, over) in zip(rows, verdicts):
        by_session.setdefault(row["session"], []).append((row, occ, over))

    deltas, steps, incomplete, resets, completed = [], [], 0, 0, 0
    for sid, seq in by_session.items():
        prev_turn_end = 0.0  # a session starts empty; its first turn's delta is its own occupancy
        open_turn = None
        for row, occ, over in seq:
            if row["role"] == "user":
                if open_turn is not None:
                    incomplete += 1
                open_turn = []
                continue
            if open_turn is None:
                continue  # assistant rows before any user row: not part of a turn we can bound
            if occ > 0:
                if open_turn:
                    steps.append(Turn(occ - open_turn[-1], sid, row["model"], open_turn[-1]))
                open_turn.append(occ)
            if over:
                completed += 1
                end = open_turn[-1] if open_turn else 0
                if end > 0:
                    d = end - prev_turn_end
                    if d < 0:
                        # occupancy went DOWN across a turn boundary: compaction, or a retirement
                        # handoff. Not growth; excluded, and counted so the exclusion is visible.
                        resets += 1
                    else:
                        deltas.append(Turn(d, sid, row["model"], prev_turn_end))
                    prev_turn_end = end
                open_turn = None
        if open_turn is not None:
            incomplete += 1
    return deltas, steps, incomplete, resets, completed


def compacted(rows, verdicts):
    """Sessions whose occupancy ever fell sharply mid-session — i.e. compaction was ON.

    The harness runs `compaction.auto: false` (`opencode.jsonc`), so those sessions are a
    DIFFERENT regime: their window is capped by something the harness has switched off, which
    bounds how far a turn there could have grown. Named so the figures can be split by it rather
    than pooled silently.
    """
    by_session, hits = {}, set()
    for row, (occ, _over) in zip(rows, verdicts):
        by_session.setdefault(row["session"], []).append((row, occ))
    for sid, seq in by_session.items():
        occs = [occ for row, occ in seq if row["role"] == "assistant" and occ > 0]
        for a, b in zip(occs, occs[1:]):
            if b < a * 0.7:  # a real reset, not the small step-to-step wobble cache accounting makes
                hits.add(sid)
                break
    return hits


def pct(values, p):
    if not values:
        return 0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * len(s) + 0.5)) - 1))
    return s[k]


def describe(label, ts):
    v = [int(t.d) for t in ts]
    if not v:
        print(f"  {label}: (none)")
        return
    print(
        f"  {label}: n={len(v):<4d} max={max(v):>9,}  p95={pct(v,95):>9,}  p90={pct(v,90):>9,}  "
        f"p75={pct(v,75):>9,}  p50={pct(v,50):>9,}  mean={int(sum(v)/len(v)):>9,}"
    )


r = rig.Results(expect=16)

try:
    source = open(PLUGIN, encoding="utf-8").read()
    fn_turn = extract(source, "turnFinished")
    fn_occ = extract(source, "occupancyOf")
    r.check(
        "turnFinished() and occupancyOf() were both found in the shipped plugin",
        fn_turn is not None and fn_occ is not None,
        "a rename must fail here rather than silently measure nothing",
    )
    if fn_turn is None or fn_occ is None:
        sys.exit(0 if r.summary() else 1)
    fn_turn, fn_occ = detype(fn_turn), detype(fn_occ)

    retire_at = read_retire_at(source)
    r.check(
        f"RETIRE_AT read from the shipped plugin is {retire_at:,}" if retire_at else "RETIRE_AT parsed",
        retire_at == 180_000,
        "this probe's conclusion is about THIS number; reading it from source stops the two drifting",
    )

    # --- corpora ------------------------------------------------------------------------------
    seen, rig_rows, real_rows = set(), [], []
    for name in sorted(os.listdir(HB)):
        if not name.endswith(".db"):
            continue
        for row in load(f"{HB}/{name}"):
            if row["id"] in seen:
                continue  # the same session appears in several rig DBs (replays)
            seen.add(row["id"])
            rig_rows.append(row)
    r.check(
        f"rig corpus loaded from hb/*.db — {len(rig_rows)} deduped messages",
        len(rig_rows) > 0,
        "several of these DBs are byte-different copies of the same run; dedup is by message id",
    )

    have_real = os.path.exists(REAL)
    if have_real:
        real_rows = [row for row in load(REAL) if row["id"] not in seen]
    r.check(
        f"real corpus loaded — {len(real_rows)} messages" if have_real else "real corpus NOT PRESENT",
        have_real,
        "~/.local/share/opencode/opencode.db"
        if have_real
        else "[NOT EXERCISED: the real corpus is absent, so every figure below comes from engineered "
        "rig workloads only — treat the distribution as a worst case, not as typical]",
    )

    # Fixture check: is this the same corpus HARNESS.md measured? 677 tool-calls / 56 stop.
    if have_real:
        occ_rows = [x for x in real_rows if x["role"] == "assistant" and (x["tokens"] or {}).get("total", 0) > 0]
        tc = sum(1 for x in occ_rows if x["finish"] == "tool-calls")
        st = sum(1 for x in occ_rows if x["finish"] == "stop")
        r.check(
            f"fixture check: the real corpus is the one HARNESS.md measured — {tc} tool-calls / {st} stop of {len(occ_rows)}",
            (tc, st, len(occ_rows)) == (677, 56, 733),
            "677/56/733 is the distribution five documents cite; a different split means a different corpus",
        )

    rows = rig_rows + real_rows
    verdicts = evaluate(fn_turn, fn_occ, [{"tokens": x["tokens"], "finish": x["finish"], "error": x["error"]} for x in rows])

    # --- the measurement ----------------------------------------------------------------------
    deltas, steps, incomplete, resets, completed = turns(rows, verdicts)
    r.check(
        f"turns were actually formed — {len(deltas)} completed turns with growth "
        f"({incomplete} unterminated, {resets} negative/compaction boundaries excluded)",
        len(deltas) >= 30,
        "a measurement over a handful of turns cannot answer a tail-vs-middle question",
    )

    rig_sids = {x["session"] for x in rig_rows}
    comp = compacted(rows, verdicts)
    d_rig = [t for t in deltas if t.session in rig_sids]
    d_real = [t for t in deltas if t.session not in rig_sids]

    print("\n  == END-OF-TURN to END-OF-TURN growth, tokens ==")
    describe("ALL              ", deltas)
    describe("rig (5.6-sol)    ", d_rig)
    describe("real sessions    ", d_real)
    by_model = {}
    for t in d_real:
        by_model.setdefault(t.model or "?", []).append(t)
    for m in sorted(by_model, key=lambda k: -max(x.d for x in by_model[k])):
        describe(f"    · {m:<13}", by_model[m])
    print("\n  compaction ON in some real sessions — a regime the harness switches off, so split:")
    describe("  compaction OFF ", [t for t in deltas if t.session not in comp])
    describe("  compaction ON  ", [t for t in deltas if t.session in comp])

    # THE DECISIVE CUT. The gate only ever faces a turn that STARTS just under RETIRE_AT. A 223K
    # first turn out of an empty session is a true observation about turn growth and a poor proxy
    # for that scenario, so condition on where the turn started.
    print("\n  == conditioned on where the turn STARTED — the scenario the gate actually faces ==")
    for floor in (0, 50_000, 100_000, 150_000):
        sel = [t for t in deltas if t.start >= floor]
        # How much of this cut is verify_retire_350k.py's growth loop? It adds a FIXED 35 KB chunk
        # per turn by construction, so it contributes a spike of identical deltas that says nothing
        # about what a real turn can do. Named, because it is most of the high-start sample.
        synth = sum(1 for t in sel if t.d == 22152)
        describe(f"  start >= {floor:>7,} ", sel)
        if sel:
            print(f"                       {synth}/{len(sel)} of these are the synthetic 22,152-per-turn loop")

    print("\n  == per-STEP growth, for comparison (this is what docs/HARDEN.md §6's table shows) ==")
    describe("ALL steps        ", steps)

    worst = max(t.d for t in deltas)
    worst_real = max([t.d for t in d_real], default=0)
    near_gate = [t for t in deltas if t.start >= 100_000]
    worst_near = max([t.d for t in near_gate], default=0)
    # The harness PINS gpt-5.6-sol (harness/config/opencode/opencode.jsonc). Every other model in
    # the corpus is evidence about what an agent turn can do, not about what THIS harness will see.
    sol = [t for t in deltas if t.session in rig_sids or t.model == "gpt-5.6-sol"]
    worst_sol = max([t.d for t in sol], default=0)

    # --- NEGATIVE CONTROL ---------------------------------------------------------------------
    # Regroup the identical corpus with the OLD per-step predicate. If per-turn grouping were not
    # doing anything, these agree. `probe_turn_predicate.py` proves the two predicates differ on
    # message shapes; this proves the difference reaches the NUMBER this phase is about.
    old_verdicts = evaluate(OLD_PREDICATE, fn_occ, [{"tokens": x["tokens"], "finish": x["finish"], "error": x["error"]} for x in rows])
    old_deltas, _os, _oi, _orr, _oc = turns(rows, old_verdicts)
    old_worst = max((t.d for t in old_deltas), default=0)
    print("\n  == negative control: same corpus, OLD per-step predicate ==")
    describe("ALL (per-step)   ", old_deltas)
    r.check(
        f"NEGATIVE CONTROL: per-step grouping gives a materially SMALLER worst case "
        f"({old_worst:,} vs {worst:,})",
        old_worst < worst * 0.75,
        "if the two predicates produced the same distribution, the grouping rule would be decorative "
        "and this whole measurement would be a restatement of the corpus",
    )

    # --- the fixture the number came from -----------------------------------------------------
    # docs/HARDEN.md §6 is the verify_auto_retire.py workload. The DB has been regenerated since
    # that write-up, so the digits differ by ~100 — the SHAPE is the assertion, not the digits.
    big = [t.d for t in d_rig if t.d > 150_000]
    r.check(
        f"docs/HARDEN.md §6's ~170K turn reproduces on the SHIPPED model — {len(big)} rig turn(s) "
        f"above 150,000, largest {max(big):,.0f}" if big else "the ~170K turn reproduces in the rig corpus",
        bool(big),
        "every hb/*.db session is gpt-5.6-sol; if this did not reappear the probe would be reading "
        "the wrong thing",
    )

    # --- the answer to the question this probe was written for --------------------------------
    v = [t.d for t in deltas]
    p50, p90, p95 = pct(v, 50), pct(v, 90), pct(v, 95)
    r.check(
        f"~170K is the TAIL of the distribution, not the middle — p50 {p50:,.0f}, p90 {p90:,.0f}, "
        f"p95 {p95:,.0f}",
        p50 < 0.25 * 170_000,
        "if ~170K had been the p50 the gate would have been wrong by a much larger factor; it is not",
    )
    r.check(
        f"…but it is NOT the maximum, which is what the derivation used it as — max is {worst:,.0f}, "
        f"{worst / 170_000:.2f}x the single measurement the shipped number was sized against",
        worst > 170_000,
        "one measurement of one turn cannot bound a tail. What survives the correction is narrower "
        "than what was written down: see the model-pin assertions below",
    )

    # --- what it means for the shipped number -------------------------------------------------
    print("\n  == the derivation, re-run against the measured distribution ==")
    print(f"     the rule (docs/RELAY.md §1):  RETIRE_AT + worst_turn < ceiling ({CEILING:,})")
    print(f"     as shipped, worst_turn = ~170,000:  {retire_at:,} + 170,000 = {retire_at + 170_000:,}   OK")
    print(f"     worst turn ANYWHERE in the corpus:  {retire_at:,} + {worst:,.0f} = {retire_at + worst:,.0f}"
          f"   {'OK' if retire_at + worst < CEILING else 'OVER THE CEILING'}")
    print(f"     worst turn on the PINNED gpt-5.6-sol: {retire_at:,} + {worst_sol:,.0f} = {retire_at + worst_sol:,.0f}"
          f"   {'OK' if retire_at + worst_sol < CEILING else 'OVER THE CEILING'}   (n={len(sol)},"
          f" margin {CEILING - retire_at - worst_sol:,.0f} = {100 * (CEILING - retire_at - worst_sol) / CEILING:.1f}%)")
    print(f"     worst turn STARTING above 100,000:  {retire_at:,} + {worst_near:,.0f} = {retire_at + worst_near:,.0f}"
          f"   {'OK' if retire_at + worst_near < CEILING else 'OVER THE CEILING'}   (n={len(near_gate)})")
    print(f"     RETIRE_AT implied by each:          < {CEILING - worst:,.0f} (any turn) / "
          f"< {CEILING - worst_sol:,.0f} (pinned model) / < {CEILING - worst_near:,.0f} (near-gate turns)")

    # -------------------------------------------------------------------------------------------
    # THE THRESHOLD IS MODEL-SPECIFIC, AND NOTHING SAID SO UNTIL NOW. `worst_turn` is a fact about
    # how far one agent turn grows, which is a fact about a MODEL's tool-calling behaviour — and the
    # corpus contains a turn 27% larger than anything the pinned model produced. So the derivation
    # is only valid while the pin holds, and this is the assertion that makes the pin load-bearing
    # instead of incidental.
    # -------------------------------------------------------------------------------------------
    pin = open(f"{rig.HEALBOT}/harness/config/opencode/opencode.jsonc", encoding="utf-8").read()
    r.check(
        "the harness still pins gpt-5.6-sol — the model the surviving margin is measured on",
        '"model": "openai/gpt-5.6-sol"' in pin,
        "opencode.jsonc:16. Change the pin and RETIRE_AT is unverified: this corpus has a "
        f"{worst:,.0f}-token turn on another model, which at 180,000 would land at {retire_at + worst:,.0f}",
    )
    off_pin = [t for t in deltas if t.d > worst_sol]
    r.check(
        f"…and that risk is REAL, not hypothetical — {len(off_pin)} turn(s) off the pinned model "
        f"exceed the pinned model's worst case, the largest by {worst - worst_sol:,.0f} tokens",
        bool(off_pin),
        "if this ever goes empty, the model-specificity warning above has lost its evidence and "
        "should be re-argued rather than inherited",
    )
    r.check(
        f"the narrower, scenario-conditioned rule still holds: {retire_at:,} + {worst_near:,.0f} = "
        f"{retire_at + worst_near:,.0f} < {CEILING:,}",
        retire_at + worst_near < CEILING,
        f"n={len(near_gate)} turns actually started above 100,000. This is the weaker claim and it "
        "is the one the owner has to decide is enough"
        + ("" if len(near_gate) >= 10 else " [THIN: fewer than 10 observations carry it]"),
    )
    # -------------------------------------------------------------------------------------------
    # FIXTURE CHECK ON THE PINNED-MODEL POPULATION. The two assertions below are the load-bearing
    # ones in this file, and BOTH get EASIER as `worst_sol` gets SMALLER:
    #     retire_at + worst_sol < CEILING        and        retire_at < CEILING - worst_sol
    # So losing the corpus that holds the big pinned-model turns does not make them fail — it makes
    # them pass more comfortably, in green, while their own detail strings still quote 175,148.
    #
    # MEASURED in Phase 9 by cloning this repo and running the probe in it. `hb/*.db` is gitignored,
    # so a fresh clone has NO rig corpus; `worst_sol` collapses from 175,148 to 6,643 (the real
    # corpus's short gpt-5.6-sol sessions), and the probe reports the gate clearing its ceiling by
    # **173,357 tokens, 48.2%** — against a true margin of 4,852, 1.3%. Both assertions PASSED and
    # the summary read 13/15, so the two reds looked like the known "missing optional corpus".
    #
    # 175,148 is the figure docs/GROWTH.md §1, HARNESS.md and docs/RELAY.md §5 all derive the
    # 184,852 bound from. `>=` is deliberate and the direction matters: a LARGER worst turn is new
    # evidence and must not fail here — it correctly tightens the two assertions below instead. This
    # only catches the corpus going missing, which is the direction nothing else guards.
    # -------------------------------------------------------------------------------------------
    r.check(
        f"fixture check: the pinned-model worst turn is the one on record — {worst_sol:,.0f} >= 175,148",
        worst_sol >= 175_148,
        "175,148 lives ONLY in the gitignored hb/*.db. Without it the two assertions below pass with "
        "a 48.2% margin that is an artifact of the absent corpus, not a fact about the gate. Rebuild "
        "it with verify_retire_350k.py / verify_control_agent.py, or treat every figure below as void",
    )

    # The pinned model is the narrowest defensible reading, and it is the one that makes the margin
    # legible. Its passing is NOT reassurance: HARNESS.md rejected the old 350,000 default for
    # leaving "~10K, under 3%", and this margin is thinner than the one that was called too thin.
    margin = CEILING - retire_at - worst_sol
    r.check(
        f"on the PINNED model the shipped gate survives — but by {margin:,.0f} tokens, "
        f"{100 * margin / CEILING:.1f}% of the ceiling (n={len(sol)} turns)",
        retire_at + worst_sol < CEILING,
        "GREEN IS NOT THE POINT HERE. The margin is against the largest turn ever MEASURED, not "
        "against the largest possible one, and the corpus itself contains a 27%-larger turn one "
        "model over. HARNESS.md called '~10K, under 3%' too thin to be a guard at the old default; "
        "this is thinner. Whether that is acceptable is a policy call, not a test result",
    )
    r.check(
        f"the gate's own ceiling is {CEILING - worst_sol:,.0f}, not the ~190,000 on record — the "
        f"shipped {retire_at:,} clears it by {CEILING - worst_sol - retire_at:,.0f}",
        retire_at < CEILING - worst_sol,
        "docs/RELAY.md §1 derives ~190,000 from worst_turn ~170,000. The measured worst turn on the "
        "pinned model is 175,148, so the true bound is lower than every document says",
    )

except SystemExit:
    raise
except Exception:
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")

sys.exit(0 if r.summary() else 1)
