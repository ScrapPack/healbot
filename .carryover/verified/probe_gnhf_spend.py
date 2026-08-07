"""Does harness/gnhf-spend.py still cost a gnhf run? Zero model turns, zero credits.

It replaced an inline token counter in `gnhf-watch.sh` that over-counted 2.76x, and it was
TESTED by hand on 2026-08-06 against `.gnhf/runs/you-are-an-unattende-e196d4`. By hand is the
whole problem. Nothing re-ran those tests, so the four defects it was written to remove could
each come back in a green tree. This probe is that hand-testing made permanent.

THE FOUR DEFECTS, each held here as a FIXTURE the correct code prices right and a MUTATION of
gnhf-spend.py's own source that prices it wrong. The mutant is loaded through the same loader
and driven through the same `main()` the live rows use, per this suite's rule that a mutation
check which re-implements its predicate proves only that the re-implementation works:

  1. **Duplicate assistant events.** Claude Code emits one `assistant` event per content block,
     all sharing a message id and a byte-identical usage object. In iteration 1 of that run 50
     of 74 ids repeat and msg_011CdkmrxPbdQbyNENfSUAgZ appears three times. The fixture is that
     shape; the mutant keys the events by position instead of by `message.id` and the same
     three turns cost 3x. On the real iteration 5 it inflates the figure from $2.9902 to
     $6.6845, which is 2.24x.
  2. **assistant + result double-count.** A `result` event carries the iteration's CUMULATIVE
     total, so an iteration that has one must contribute only `total_cost_usd`; the mutant adds
     its turns on top.
  3. **Cross-run contamination.** `.gnhf/runs` is never pruned and the helper takes ONE run
     directory. The mutant globs the siblings, and on the real corpus that reports $29.9351 for
     a run that cost $26.5371: the abandoned run from earlier the same evening charged to the
     live one, which is exactly what happened.
  4. **Cache reads dropped.** They bill at 0.1x input and dominate the bill. Priced from the
     e196d4 run's own deduped usage they are $14.92 of its $26.5371, 56%. The mutant zeroes the
     term, and the all-cache-read fixture then reports $0.0000. That row is what makes "a
     non-zero figure" an assertion rather than a hope: the code CAN report nothing for a fixture
     whose entire cost is cache reads, and once did.

AND THE IN-FLIGHT FLOOR, which is a different kind of claim and gets its own rows. An iteration
with no result event is priced from its deduped assistant events, and that number is a FLOOR,
not an estimate: the usage on an `assistant` event is the one from the underlying message_start,
so `output_tokens` is the partial count at stream open (1, on all three copies of the message
above) and the figure under-reports by exactly the real output. MEASURED on iteration 5 of that
run: $2.9902 against the $3.7918 its own result event carries when it lands, 21% short. A caller
that read it as an estimate would under-cap, which is why the tool prints the two numbers apart.

WHERE THE ANCHORS LIVE. `.gnhf/runs` is in `.git/info/exclude`, so it is local to the checkout
that produced it and absent from a clone, a pool slot and a pruned tree. The five rows that quote
it name the file they open (`needs=`) and record a NOT MEASURED HERE skip there rather than a red
that means "wrong machine". The ten fixture rows are hermetic and run everywhere, so a checkout
without the corpus still measures every defect; what it loses is the anchoring to real dollars,
and it says so out loud.

EVERY ROW HAS BEEN SEEN RED. TESTED 2026-08-06 by installing a broken gnhf-spend.py in a scratch
checkout (this probe, `rig.py` and the real corpus, one deliberately wrong subject) and reading
which rows went red: the four defects restored one at a time (10/15, 10/15, 4/15, 7/15), the
result total dropped (7/15), the in-flight price dropped (8/15), and the cache-read line
refactored so the mutant's anchor no longer matched it (13/15, red on exactly the two rows that
notice that). Across the seven, all fifteen rows were observed failing, and the unmutated control
in the same harness was 15/15. The corpus requirements were driven the same way: absent, the five
rows skip and the run is 10/10 with the skips named; present but holding the wrong iterations,
they RUN and go red, which is what keeps the requirement from replacing the measurement.

  venv/bin/python probe_gnhf_spend.py
"""

import contextlib
import glob
import io
import json
import os
import shutil
import sys
import tempfile
import types

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
from rig import Env, Results  # noqa: E402

HEALBOT = os.path.dirname(os.path.dirname(SP))
SPEND = f"{HEALBOT}/harness/gnhf-spend.py"
RUNS = f"{HEALBOT}/.gnhf/runs"
E196 = f"{RUNS}/you-are-an-unattende-e196d4"      # the run all four defects were measured on
C635 = f"{RUNS}/you-are-an-unattende-c63591"      # the abandoned run beside it, defect 3's prey

# The four defects restated as the source edit that brings each one back. Each must match
# gnhf-spend.py exactly once and that count is a row of its own: zero matches would mean the
# file moved under this probe and every detection below silently stopped restating a defect.
M1 = ('by_id[msg["id"]] = (msg.get("model"), msg["usage"])',
      'by_id[len(by_id)] = (msg.get("model"), msg["usage"])')
M2 = ("if finished:\n            continue",
      "if False:\n            continue")
M3 = ('os.path.join(run_dir, "iteration-*.jsonl")',
      'os.path.join(run_dir, "..", "*", "iteration-*.jsonl")')
M4 = ('+ usage.get("cache_read_input_tokens", 0) * rate[2]',
      '+ usage.get("cache_read_input_tokens", 0) * 0')

# STRICTLY WEAKER than the rows they guard, per rig.Env: each requirement is that a file is
# there, the rows pin what is in it. A corpus that is present and has CHANGED satisfies the
# requirement, runs the rows and goes red, which is the finding. TESTED against a corpus of the
# right names holding the wrong iterations.
#
# Two requirements rather than one. Each names exactly what its rows
# open, so a partial corpus measures what it can and says what it could not.
CORPUS = Env(
    "gnhf-run-corpus",
    "this checkout holds the two recorded gnhf runs the dollar anchors quote. `.gnhf/runs` is "
    "in .git/info/exclude, so it is local to the checkout that produced it and neither a clone "
    "nor a pool slot has it",
    lambda: all(glob.glob(f"{d}/iteration-*.jsonl") for d in (E196, C635)),
)
CORPUS_IN_FLIGHT = Env(
    "gnhf-run-iteration-5",
    "the e196d4 run still holds `iteration-5.jsonl`. The two floor rows strip its result event "
    "to recover that iteration as gnhf-watch.sh saw it mid-run, and no other iteration is "
    "interchangeable with it because both rows quote its measured dollars",
    lambda: os.path.exists(f"{E196}/iteration-5.jsonl"),
)


def load(patch=None):
    """The module under test, built from source text so a mutant goes through this same loader.

    `harness/gnhf-spend.py` cannot be imported by name, a hyphen not being an identifier, and
    reading the file every time is also what keeps a stale .pyc from answering for the source.
    """
    src = SOURCE if patch is None else SOURCE.replace(*patch, 1)
    mod = types.ModuleType("gnhf_spend_under_test")
    mod.__file__ = SPEND
    exec(compile(src, SPEND, "exec"), mod.__dict__)
    return mod


def money(mod, run_dir):
    """`(stdout, stderr, exit code)` from the module's own `main()`.

    `main()` is driven rather than `spend()` because gnhf-watch.sh reads that printed line: the
    "%.4f %.4f" shape, the unpriced-model warning on stderr and the exit code are the contract
    the caller depends on, not decoration around the arithmetic.

    `sys.argv` is restored on the way out and NOT in a `finally`, deliberately. A `finally` here
    would be a second one in this file, and `probe_rig_contract`'s fifth contract reads every
    `try/finally` in a rig and requires the verdict exit to be its last statement. That rule is
    worth more than this restore, which nothing needs on the failing path: an exception from
    `main()` goes to the crash guard, which records a red row and exits, and neither `rig.py` nor
    `term.py` reads `sys.argv` on the way.
    """
    out, err = io.StringIO(), io.StringIO()
    argv = sys.argv
    sys.argv = ["gnhf-spend.py", run_dir]
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = mod.main()
    sys.argv = argv
    return out.getvalue().strip(), err.getvalue().strip(), code


def assistant(mid, inp=0, write=0, read=0, out=1):
    """One `assistant` event, modelled on msg_011CdkmrxPbdQbyNENfSUAgZ's from iteration 1 with
    the content block dropped. `out` defaults to 1 because that is what all three of its copies
    carry: the message_start partial, and the entire reason the in-flight number is a floor."""
    return {"type": "assistant", "message": {
        "model": "claude-opus-5", "id": mid, "type": "message", "role": "assistant",
        "content": [{"type": "text", "text": "..."}], "stop_reason": None,
        "usage": {"input_tokens": inp, "cache_creation_input_tokens": write,
                  "cache_read_input_tokens": read, "output_tokens": out,
                  "cache_creation": {"ephemeral_5m_input_tokens": 0,
                                     "ephemeral_1h_input_tokens": write},
                  "service_tier": "standard"}}}


def result(cost):
    """One `result` event. Its total is CUMULATIVE for the iteration, which is why an iteration
    that has one must not also have its turns counted."""
    return {"type": "result", "subtype": "success", "total_cost_usd": cost,
            "num_turns": 1, "is_error": False}


def run(parent, name, *iterations):
    """A gnhf run directory on disk: one `iteration-N.jsonl` per argument, each a list of
    events written one JSON object per line, exactly as Claude Code streams them."""
    path = os.path.join(parent, name)
    os.makedirs(path)
    for i, events in enumerate(iterations, 1):
        with open(f"{path}/iteration-{i}.jsonl", "w", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event) + "\n")
    return path


def result_total(path):
    """The `total_cost_usd` on an iteration's own result event: gnhf's authoritative number for
    that iteration, and the truth the in-flight floor is a floor against."""
    for line in open(path, errors="replace"):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("type") == "result":
            return rec.get("total_cost_usd")
    return None


def in_flight_iteration_5():
    """Iteration 5 of the e196d4 run with its result event stripped, which is that iteration as
    gnhf-watch.sh saw it WHILE it was still running. Built on demand and cached, so a checkout
    without the corpus never touches the path; the two rows that use it are guarded."""
    path = os.path.join(TMP, "corpus-in-flight")
    if not os.path.isdir(path):
        os.makedirs(path)
        with open(f"{path}/iteration-1.jsonl", "w", encoding="utf-8") as out:
            for line in open(f"{E196}/iteration-5.jsonl", errors="replace"):
                try:
                    kind = json.loads(line).get("type")
                except ValueError:
                    kind = None
                if kind != "result":
                    out.write(line)
    return path


def flight_and_truth():
    """`"<floor> <truth>"` for iteration 5: the in-flight figure priced from its deduped turns,
    and the total its own result event carries. Two INDEPENDENT readings of one file, the floor
    from the assistant events and the truth from the result event, so the ordering between them
    is measured rather than an identity restated."""
    floor = float(money(LIVE, in_flight_iteration_5())[0].split()[1])
    return "%.4f %.4f" % (floor, result_total(f"{E196}/iteration-5.jsonl"))


# One turn's usage, priced by hand against gnhf-spend.py's table at the Opus 5 rates: 1000 fresh
# input at $5, 2000 cache writes at $10, 1,000,000 cache reads at $0.50 and the 1-token output
# partial at $25 per MTok  ->  0.005 + 0.020 + 0.500 + 0.000025 = $0.525025.
TURN = {"inp": 1000, "write": 2000, "read": 1_000_000, "out": 1}
TURN_PRICE = "0.5250"

r = Results(expect=15, skip_max=5)
TMP = tempfile.mkdtemp(prefix="probe_gnhf_spend.")
try:
    with open(SPEND, encoding="utf-8") as fh:
        SOURCE = fh.read()
    LIVE = load()
    counts = [SOURCE.count(before) for before, _ in (M1, M2, M3, M4)]
    r.check(
        "every mutation below still applies to gnhf-spend.py, exactly once",
        counts == [1, 1, 1, 1],
        f"counts {counts} for defects 1-4. Zero would mean the file moved under this probe and "
        "the mutant stopped restating its defect, leaving every detection below unmeasured",
    )

    # --- defect 1: one message id, one charge -------------------------------------------------
    # The same dict written three times, so the usage is byte-identical the way the real events'
    # is. That is what makes the id the only thing that can tell the copies apart.
    dup = run(TMP, "duplicate-blocks", [assistant("msg_dup", **TURN)] * 3)
    r.check(
        "DEFECT 1: one message id repeated 3x, usage byte-identical, is charged ONCE",
        money(LIVE, dup) == (f"0.0000 {TURN_PRICE}", "", 0),
        "one turn's price, not three. Claude Code emits one assistant event per content block "
        "and every one carries the same id and the same usage object",
    )
    r.check(
        "MUTATION: keying the events by position instead of message.id IS detected",
        money(load(M1), dup) == ("0.0000 1.5751", "", 0),
        "3 x $0.525025 for one turn. This is the arithmetic that made the old counter's raw "
        "event sum meaningless, on the fixture shape iteration 1 supplies 50 times over",
    )

    # --- defect 2: the result event is authoritative for its iteration ------------------------
    done = run(TMP, "finished", [assistant("msg_dup", **TURN)] * 3 + [result(0.90)])
    r.check(
        "DEFECT 2: an iteration with a result event contributes ONLY total_cost_usd",
        money(LIVE, done) == ("0.9000 0.0000", "", 0),
        "the result event's total is CUMULATIVE for the iteration, so its turns are already in "
        "it; the floor is 0.0000 because nothing in this run is still in flight",
    )
    r.check(
        "MUTATION: adding the iteration's turns on top of its result IS detected",
        money(load(M2), done) == (f"0.9000 {TURN_PRICE}", "", 0),
        "the per-turn numbers and the total added together, which is the second of the four "
        "ways the old counter was wrong and the one that compounded the first into 2.76x",
    )

    # --- defect 3: one run directory, never a sibling -----------------------------------------
    siblings = os.path.join(TMP, "runs")
    live_run = run(siblings, "live-run", [result(1.00)])
    run(siblings, "abandoned-run", [result(99.00)])
    r.check(
        "DEFECT 3: the helper reads the run directory it was given, never a sibling",
        money(LIVE, live_run) == ("1.0000 0.0000", "", 0),
        "$99.00 sits in the directory next door and must not appear: .gnhf/runs is never "
        "pruned, so a live run always has abandoned ones beside it",
    )
    r.check(
        "MUTATION: globbing the sibling run directories IS detected",
        money(load(M3), live_run) == ("100.0000 0.0000", "", 0),
        "1.00 + 99.00. The old counter globbed every run directory ever created, so an "
        "abandoned run from earlier the same evening was charged to the live one",
    )

    # --- defect 4: cache reads are priced ------------------------------------------------------
    cache = run(TMP, "cache-only", [assistant("msg_cache", read=1_000_000, out=0)])
    r.check(
        "DEFECT 4: an iteration that is ALL cache reads is PRICED, not dropped",
        money(LIVE, cache) == ("0.0000 0.5000", "", 0),
        "1M cache reads at 0.1x input. They are not 'already paid to write', they bill, and "
        "priced from the e196d4 run's own usage they are $14.92 of its $26.5371",
    )
    r.check(
        "MUTATION: dropping the cache-read term IS detected, the same fixture reports nothing",
        money(load(M4), cache) == ("0.0000 0.0000", "", 0),
        "the row that makes the one above an assertion rather than a hope: the code CAN report "
        "$0.0000 for a fixture whose entire cost is cache reads, and the shipped counter did",
    )

    # --- the in-flight floor -------------------------------------------------------------------
    # `flight` is `done` minus its result event: the same three turns, mid-iteration.
    flight = run(TMP, "in-flight", [assistant("msg_dup", **TURN)] * 3)
    flight_floor = float(money(LIVE, flight)[0].split()[1])
    done_exact = float(money(LIVE, done)[0].split()[0])
    r.check(
        "THE FLOOR: an iteration with no result event prices from its DEDUPED turns, and lands "
        "BELOW the total that replaces them when it finishes",
        money(LIVE, flight) == (f"0.0000 {TURN_PRICE}", "", 0) and flight_floor < done_exact,
        f"${flight_floor} in flight against ${done_exact} landed, over the same three turns. "
        "The gap is output: the usage on an assistant event is the message_start partial",
    )

    # --- the anchors, on the corpus the defects were measured against --------------------------
    r.check(
        "CORPUS: the e196d4 run still costs what it cost, five finished iterations",
        lambda: money(LIVE, E196) == ("26.5371 0.0000", "", 0),
        "the recorded total for the run that produced all four defects. Every iteration has a "
        "result event, so this is gnhf's own arithmetic and the floor is 0.0000",
        needs=CORPUS,
    )
    r.check(
        "CORPUS: ...and the abandoned run beside it still costs 3.3981",
        lambda: money(LIVE, C635) == ("3.3981 0.0000", "", 0),
        "the run from earlier the same evening. Read separately, it is a second anchor; read "
        "together with the one above it is the contamination the next row reproduces",
        needs=CORPUS,
    )
    r.check(
        "CORPUS MUTATION: the sibling glob charges both runs to one, 29.9351, the sum",
        lambda: money(load(M3), E196)[0] == "29.9351 0.0000",
        "defect 3 on the real evidence rather than a fixture: 26.5371 + 3.3981, which is the "
        "$29.92 the old counter was reported against",
        needs=CORPUS,
    )
    r.check(
        "CORPUS: iteration 5's in-flight figure is a FLOOR against its own result event, "
        "$2.9902 priced from the turns against $3.7918 once the iteration landed",
        lambda: flight_and_truth() == "2.9902 3.7918",
        "under, never over, and short by 21%, which is output priced from the message_start "
        "partial. A caller that read this as an estimate would under-cap",
        needs=CORPUS_IN_FLIGHT,
    )
    r.check(
        "CORPUS MUTATION: summing that iteration's assistant events inflates the floor to "
        "$6.6845, 2.24x, and it would have read as a cap that was already blown",
        lambda: money(load(M1), in_flight_iteration_5())[0] == "0.0000 6.6845",
        "defect 1 on the real evidence: 26 of iteration 5's 33 message ids repeat. The fixture "
        "above is that shape at three copies of one id; this is the whole iteration",
        needs=CORPUS_IN_FLIGHT,
    )

except SystemExit:
    raise
except Exception:
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    shutil.rmtree(TMP, ignore_errors=True)
    ok = r.summary()
    sys.exit(0 if ok else 1)
