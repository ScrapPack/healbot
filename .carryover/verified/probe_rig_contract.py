"""Does every rig in this suite still report failure as failure? Zero model turns, zero credits.

This is the guard that would have caught Phase 10's finding, and its absence is why that finding
was available to make. Phase 9 fixed the ten free probes — assertion floor, exception guard — and
touched none of the eleven PAID rigs, which had the same defect in a more expensive place. Nothing
structural stopped the next rig from being written without either.

WHAT WENT WRONG, and why a static probe is the right shape for it:

  - **Six rigs discarded `summary()`'s verdict entirely.** `finally: r.summary(); t.close()` —
    the return value dropped on the floor, no `sys.exit`, so the process ended normally and the
    shell saw 0 however many assertions had failed. Among them `smoke.py`, which the README tells
    you to run FIRST to check the provider works, and `verify_surface.py`, which carried a
    permanently-red assertion (17/18) for five phases precisely because nothing ever surfaced it.
  - **`verify_handoff.py`'s recorded 21/21 was unreachable.** Phase 5 replaced a vacuous check
    with two mutation legs — 21 sites became 22 — and never re-ran the file. The 21/21 is Phase
    4's score, and it is cited in four documents as the evidence for the Phase 4 exit gate.
  - **Ten of twelve paid rigs had no exception guard**, so a crash exited on whatever ran first.

None of that is visible from a green run, because none of those rigs was run. It IS visible from
the source, which is what this probe reads. It never executes a rig; it asserts the contract every
rig must satisfy:

  1. it declares an assertion FLOOR — `Results(expect=N)`
  2. that floor is satisfiable — no greater than the assertions that cannot be skipped
  3. it carries the exception guard, so a crash becomes a failed row rather than a short green
  4. it ACTS on `summary()`'s verdict — a failing run must exit non-zero
  5. and that verdict exit is the LAST thing its `finally` does, so nothing trails it unreachably
  6. no assertion decides that a TURN COMPLETED by counting `fire()`'s box (Phase 12)
  7. every environment-guarded check (`r.check(..., needs=<Env>)`) passes a LAMBDA predicate

Contract 7 arrived with `rig.Env` on 2026-08-01 and guards the mechanism that lets a check say
"this machine does not hold the fact I need" instead of going red in a pool slot. Python
evaluates arguments eagerly, so `r.check("x", open(path).read() == canon, needs=E)` has already
read — and already crashed — before the guard is entered; the protection the author believes
they added runs too late to do anything. `Results.check` raises TypeError on a non-callable,
which catches it at run time; this contract catches it at read time, and a lambda is the one
form that is unambiguous from source. A bare function reference would also be callable, and
requiring the lambda anyway costs nothing (every guarded predicate in this suite is an inline
expression) while keeping the rule one grep away from being verified by eye.

Contract 6 is a different animal from 1–5 and is worth saying why. Those five are about whether a
rig can REPORT a failure. The sixth is about whether it can SEE one. `fire()` appends a turn that
threw and a turn that finished in the same 3-tuple, so `len(box)` counts turns that ENDED, never
turns that RAN — and no rig in the suite had ever read the third element. TESTED in Phase 12:
three `fire()` calls at a dead port filled a box in **9 milliseconds** and satisfied every
completion predicate in the suite. Four `r.check` rows were affected, and the one in
`verify_question.py` had no independent evidence anywhere else in its file. `rig.completed()` is
the fix; this contract is what stops the raw-count idiom coming back.

Every predicate is mutation-checked against a corrupted copy of a real rig, and the corrupted
copy is pushed through THE SAME function the live check calls — per this suite's rule that a
mutation check which re-implements its predicate inline proves only that the inline copy works.

  venv/bin/python probe_rig_contract.py
"""

import ast
import contextlib
import glob
import io
import os
import sys

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
from rig import Env, Results, completed  # noqa: E402

# Entrypoints only. `rig.py` and `term.py` are libraries and own no assertions; `diagnose_*.py`
# are scratch tools that make no claims. If this list ever silently narrows, the sweep below
# passes by measuring nothing — so its size is asserted, and the exclusions are asserted too.
#
# THIS FILE IS DELIBERATELY NOT EXEMPT. It was, in its first version, and a guard that exempts
# itself is the same shape as the defects it exists to catch: the one rig whose contract nobody
# checks. It satisfies its own four predicates and is swept with the rest.
LIB = {"rig.py", "term.py"}


def rigs():
    out = []
    for path in sorted(glob.glob(f"{SP}/probe_*.py") + glob.glob(f"{SP}/verify_*.py") + [f"{SP}/smoke.py"]):
        name = os.path.basename(path)
        if name in LIB or name.startswith("diagnose_"):
            continue
        out.append(name)
    return out


def read(name):
    with open(f"{SP}/{name}", encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------------------------------
# The four predicates. Each takes SOURCE TEXT, so the mutation checks below can hand them a
# corrupted copy and get the same code path the live sweep gets.
# ------------------------------------------------------------------------------------------
def floor_of(src):
    """The N in `Results(expect=N)`, or None if the rig declares no floor.

    BOTH call shapes are in use and both must be recognised: `Results(...)` after
    `from rig import Results`, and `rig.Results(...)` after `import rig`. A first version of this
    matched only the bare Name and reported five probes as floorless that were not — a
    false-negative sweep is the same failure as a vacuous assertion, one polarity over, and it
    would have sent the reader to "fix" files that were already correct.
    """
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        named = (isinstance(f, ast.Name) and f.id == "Results") or (
            isinstance(f, ast.Attribute) and f.attr == "Results"
        )
        if not named:
            continue
        for kw in node.keywords:
            if kw.arg == "expect" and isinstance(kw.value, ast.Constant):
                return kw.value.value
    return None


def reachable(src):
    """How many `r.check(...)` sites are NOT inside a conditional and NOT inside an except
    handler — i.e. the assertions a complete run cannot legitimately skip.

    Conditionals are excluded because a rig may hold a check behind a branch that legitimately
    does not fire; the guard's own `r.check("UNEXPECTED EXCEPTION", ...)` is excluded because it
    fires only when something went wrong. A floor above this number is unsatisfiable and would
    make the rig fail on a perfect run.
    """
    n = 0
    stack = []

    class V(ast.NodeVisitor):
        def visit(self, node):
            nonlocal n
            branch = isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.ExceptHandler))
            if branch:
                stack.append(node)
            if isinstance(node, ast.Call):
                f = node.func
                if (
                    isinstance(f, ast.Attribute)
                    and f.attr == "check"
                    and isinstance(f.value, ast.Name)
                    and f.value.id == "r"
                    and not any(isinstance(s, (ast.If, ast.For, ast.While)) for s in stack)
                    and not any(isinstance(s, ast.ExceptHandler) for s in stack)
                ):
                    n += 1
            self.generic_visit(node)
            if branch:
                stack.pop()

    V().visit(ast.parse(src))
    return n


def upper_bound(src):
    """The most assertions a run of this rig can produce, or None when that is not computable.

    A floor above this number fails a PERFECT run, which is worse than no floor: it trains the
    reader to ignore the one signal the floor exists to give.

    None is returned when any `r.check` sits inside a `for`/`while` — one call site there emits
    an unknown number of rows (`probe_turn_predicate.py` drives an 11-case table through a single
    site, which is why a first version of this check reported its floor of 18 as unsatisfiable
    against a "reachable" count of 7). Static analysis cannot bound that, and the honest move is
    to say so and count the exclusion out loud rather than to quietly widen the predicate until
    everything passes.
    """
    n, stack, looped = 0, [], False

    class V(ast.NodeVisitor):
        def visit(self, node):
            nonlocal n, looped
            branch = isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.ExceptHandler))
            if branch:
                stack.append(node)
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Attribute) and f.attr == "check" and isinstance(f.value, ast.Name) and f.value.id == "r":
                    if any(isinstance(x, (ast.For, ast.While)) for x in stack):
                        looped = True
                    elif not any(isinstance(x, ast.ExceptHandler) for x in stack):
                        n += 1
            self.generic_visit(node)
            if branch:
                stack.pop()

    V().visit(ast.parse(src))
    return None if looped else n


def records_crash(node):
    """Does this `try` have an except handler that turns a crash into a FAILED assertion?

    Not merely "is there an except" — the handler must record a failure, or the rig still
    reports a green summary of whatever ran before it died.
    """
    for h in node.handlers:
        for sub in ast.walk(h):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "check":
                if len(sub.args) >= 2 and isinstance(sub.args[1], ast.Constant) and sub.args[1].value is False:
                    return True
    return False


def swallows_crash(src):
    """Does the rig have a `finally` that EXITS without an except handler recording the crash?

    This is the defect stated exactly, and stating it exactly matters. `sys.exit()` in a
    `finally` discards the in-flight exception, so the process leaves on `summary()`'s verdict
    over the rows that happened to be appended before the crash — a green exit for a rig that
    died. But the danger is the COMBINATION, not the `finally` and not the missing guard alone:

      - `try` + guard + `finally: sys.exit(...)`  — safe: the crash becomes a FAILED row first.
      - no `try` at all (probe_twin.py)           — safe: the exception propagates, traceback,
                                                     non-zero exit. Nothing is there to swallow it.
      - `finally: sys.exit(...)` with NO guard    — THE DEFECT. Seven probes and ten paid rigs.

    An earlier version of this predicate demanded a guard unconditionally and reported
    probe_twin.py — which has no `try` — as defective. That would have forced a 190-line reindent
    to satisfy a check rather than to fix anything, which is how a guard starts costing more than
    it protects.
    """
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Try) and node.finalbody:
            exits = any(True for stmt in node.finalbody for _ in _exit_calls(stmt))
            if exits and not records_crash(node):
                return True
    return False


def _exit_calls(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            if (isinstance(f, ast.Attribute) and f.attr == "exit") or (
                isinstance(f, ast.Name) and f.id == "SystemExit"
            ):
                yield node
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            f = node.exc.func
            if isinstance(f, ast.Name) and f.id == "SystemExit":
                yield node.exc


def _mentions_summary(node):
    return any(
        isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "summary"
        for n in ast.walk(node)
    )


def _verdict_names(tree):
    """Names bound to `r.summary()` — the `ok` in `ok = r.summary()`."""
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _mentions_summary(node.value):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
    return out


def _carries_verdict(call, bound):
    for arg in call.args:
        if _mentions_summary(arg):
            return True
        if any(isinstance(n, ast.Name) and n.id in bound for n in ast.walk(arg)):
            return True
    return False


def acts_on_verdict(src):
    """Does the rig's exit status depend on `r.summary()`?

    Two shapes are in use and both are fine: the verdict inlined into the exit call
    (`sys.exit(0 if r.summary() else 1)`), or bound to a name that an exit call then reads
    (`ok = r.summary()` … `sys.exit(0 if ok else 1)`). Anything else means the summary is
    printed and thrown away, which is what six rigs did.
    """
    tree = ast.parse(src)
    bound = _verdict_names(tree)
    return any(_carries_verdict(c, bound) for c in _exit_calls(tree))


def finally_ends_on_verdict(src):
    """For every `try/finally`, is the LAST statement of the `finally` a verdict-bearing exit?

    `acts_on_verdict` only asks whether such an exit exists ANYWHERE in the file, which a stray or
    unreachable one would satisfy. This asks whether it is the thing that actually runs last — the
    property that was verified by hand across all twenty rigs during the Phase 10 review and, being
    verified by hand, was exactly the kind of thing that should not stay verified by hand.

    Rigs with no `try/finally` are vacuously fine and say so by returning True: they exit at module
    level and an escaping exception propagates (`probe_twin.py`, `probe_turn_growth.py`,
    `probe_turn_predicate.py`).
    """
    tree = ast.parse(src)
    bound = _verdict_names(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and node.finalbody:
            if not any(_carries_verdict(c, bound) for c in _exit_calls(node.finalbody[-1])):
                return False
    return True


def _reads(node, names):
    return [n for n in ast.walk(node) if isinstance(n, ast.Name) and n.id in names]


def _calls(node, fname):
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if (isinstance(f, ast.Name) and f.id == fname) or (isinstance(f, ast.Attribute) and f.attr == fname):
                return True
    return False


def _box_tainted(tree):
    """Names carrying data derived from `fire()`'s box WITHOUT passing through `completed()`.

    `ended = [b for b in box if ...]` is tainted; `threw = [... for ... in ended ...]` is tainted
    through it; `workers = completed(box, "worker")` is NOT, because that call is exactly the
    thing that separates a turn that ran from a turn that threw. Iterated to a fixpoint rather
    than done in one pass — `ast.walk` is not source order, and chaining is two deep in this suite.
    """
    tainted = {"box"}
    for _ in range(8):
        grew = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and _reads(node.value, tainted) and not _calls(node.value, "completed"):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id not in tainted:
                        tainted.add(t.id)
                        grew = True
        if not grew:
            break
    return tainted


def _absence_only(pred, tainted):
    """Is every tainted read in this predicate underneath a `not`?

    `not any(b[0] == "blocker" for b in box)` claims the turn has NOT ended yet. A turn that threw
    puts an entry in the box, which makes that predicate FALSE — red, which is the correct
    outcome. Only POSITIVE completion claims are the defect, so negated reads are exempt. The
    exemption is COUNTED OUT LOUD in the sweep below rather than left to widen silently, and a
    mutation leg strips the `not` to prove it does not swallow the positive form.
    """
    reads = {id(n) for n in _reads(pred, tainted)}
    if not reads:
        return False
    negated = set()
    for n in ast.walk(pred):
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            negated |= {id(x) for x in _reads(n, tainted)}
    return reads <= negated


def _check_calls(tree):
    for n in ast.walk(tree):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "check"
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "r"
            and len(n.args) >= 2
        ):
            yield n


def box_claims(src):
    """Every `r.check` PREDICATE that decides turn completion by counting `fire()`'s box.

    Returns `[(lineno, predicate_source)]`; empty is the contract. Scoped to `args[1]` — the
    predicate — deliberately: the DETAIL string (`args[2]`) should absolutely mention the raw box
    and the exceptions in it, because that is what a human reads when the row goes red.
    """
    tree = ast.parse(src)
    tainted = _box_tainted(tree)
    out = []
    for call in _check_calls(tree):
        pred = call.args[1]
        if not _reads(pred, tainted) or _calls(pred, "completed") or _absence_only(pred, tainted):
            continue
        out.append((call.lineno, (ast.get_source_segment(src, pred) or "?").replace("\n", " ")))
    return out


def box_exemptions(src):
    """The absence claims contract 6 lets through — counted so the exemption cannot widen quietly."""
    tree = ast.parse(src)
    tainted = _box_tainted(tree)
    return [c.lineno for c in _check_calls(tree) if _absence_only(c.args[1], tainted)]


def _guarded_calls(tree):
    return [c for c in _check_calls(tree) if any(kw.arg == "needs" for kw in c.keywords)]


def guarded(src):
    """Every environment-guarded `r.check(..., needs=...)` site — `[(lineno, predicate)]`.

    Counted as well as swept: a contract nobody exercises passes by measuring nothing, and this
    one would read green on the day the last `needs=` was deleted.
    """
    tree = ast.parse(src)
    return [(c.lineno, (ast.get_source_segment(src, c.args[1]) or "?").replace("\n", " ")[:70])
            for c in _guarded_calls(tree)]


def eager_guards(src):
    """Guarded sites whose predicate is NOT a lambda — the shape the guard cannot stop.

    Empty is the contract. `ast.Lambda` is the whole test: an expression node here means the
    predicate was evaluated on the way into `check()`, so an absent environment produced its
    crash or its false answer before anything could decide to skip.
    """
    tree = ast.parse(src)
    return [(c.lineno, (ast.get_source_segment(src, c.args[1]) or "?").replace("\n", " ")[:70])
            for c in _guarded_calls(tree) if not isinstance(c.args[1], ast.Lambda)]


# ------------------------------------------------------------------------------------------
# 22 through Phase 11; Phase 12's contract 6 adds seven — the sweep, the exemption count, a clean
# baseline, three mutation legs and one runtime leg on `completed()` itself. Contract 7 adds
# eleven on 2026-08-01: four static (sweep, exercised-count, clean baseline, two mutation legs in
# both polarities) and six runtime, because the skip machinery has to be shown SKIPPING loudly
# and shown RUNNING again once its requirement is satisfied. A mechanism that only ever
# demonstrates the quiet half is a mechanism nobody can tell from a mute button.
r = Results(expect=40)

try:
    names = rigs()
    r.check(
        f"the sweep found the rigs — {len(names)} entrypoints",
        len(names) >= 22,
        "a sweep that silently narrows to nothing passes by measuring nothing; "
        f"{', '.join(names[:4])} …",
    )
    r.check(
        "NEGATIVE CONTROL: the sweep excludes the libraries",
        not ({"rig.py", "term.py"} & set(names)),
        "rig.py and term.py own no assertions — counting them would make every predicate below "
        "fail for a reason that is not a defect",
    )
    r.check(
        "…and it includes BOTH halves — the free probes and the PAID rigs",
        any(n.startswith("probe_") for n in names) and any(n.startswith("verify_") for n in names),
        "Phase 9 fixed the free half only, and the sweep existing to catch that must not itself "
        "be scoped to the half that was already fixed",
    )

    src = {n: read(n) for n in names}

    # --- 1. every rig declares a floor -----------------------------------------------------
    missing = [n for n in names if floor_of(src[n]) is None]
    r.check(
        "EVERY RIG DECLARES AN ASSERTION FLOOR — Results(expect=N)",
        not missing,
        "without it summary() returns `not failed` over whatever happened to be appended, so a "
        "rig that stopped early reports N/N and exits 0. "
        + (f"missing: {missing}" if missing else "all declare one"),
    )
    r.check(
        "…and every floor is at least 1",
        all((floor_of(src[n]) or 0) >= 1 for n in names),
        "expect=0 is the same as no floor at all, spelled so it looks deliberate",
    )

    # --- 2. every floor is satisfiable -----------------------------------------------------
    boundable = [n for n in names if upper_bound(src[n]) is not None]
    looped = [n for n in names if upper_bound(src[n]) is None]
    unsat = [(n, floor_of(src[n]), upper_bound(src[n])) for n in boundable if (floor_of(src[n]) or 0) > upper_bound(src[n])]
    r.check(
        f"EVERY STATICALLY BOUNDABLE FLOOR IS SATISFIABLE — {len(boundable)} of {len(names)} rigs",
        not unsat,
        "a floor above the most assertions a run can emit fails a PERFECT run. "
        + (f"unsatisfiable: {unsat}" if unsat else "all satisfiable")
        + (
            f" [NOT EXERCISED for {len(looped)} rig(s) that emit checks from inside a loop, so no "
            f"static bound exists for them: {looped}. Their floors are only verified by RUNNING "
            f"them, which the free suite does every phase]"
            if looped
            else ""
        ),
    )

    # --- 3. every rig catches its own crash ------------------------------------------------
    swallow = [n for n in names if swallows_crash(src[n])]
    r.check(
        "NO RIG SWALLOWS ITS OWN CRASH — a `finally` that exits must have a guard",
        not swallow,
        "`sys.exit()` inside a `finally` DISCARDS the escaping exception, so the rig leaves on "
        "summary()'s verdict over whatever ran before it died — a green exit for a dead run. "
        + (f"swallowing: {swallow}" if swallow else "none swallow"),
    )

    # --- 4. every rig acts on the verdict --------------------------------------------------
    mute = [n for n in names if not acts_on_verdict(src[n])]
    r.check(
        "EVERY RIG'S EXIT STATUS DEPENDS ON summary()",
        not mute,
        "six rigs printed the summary and dropped the return value, so a failing run exited 0 — "
        "including smoke.py, the provider check the README says to run first. "
        + (f"verdict discarded: {mute}" if mute else "all act on it"),
    )

    trailing = [n for n in names if not finally_ends_on_verdict(src[n])]
    r.check(
        "…AND THE VERDICT EXIT IS THE LAST THING THE `finally` DOES",
        not trailing,
        "an exit that exists somewhere in the file is not the same as one that runs — cleanup after "
        "it would never execute, and a stray unreachable exit satisfies the check above. "
        + (f"trailing work after the exit: {trailing}" if trailing else f"all {len(names)} end on it"),
    )

    # --- mutation checks -------------------------------------------------------------------
    # Each predicate is re-run against a CORRUPTED copy of a real rig and required to trip. The
    # corrupted copy goes through the same function the sweep above calls; a mutation check that
    # re-implements its predicate inline proves only that the inline copy discriminates.
    sample = "verify_handoff.py"
    good = src[sample]
    r.check(
        f"the mutation sample satisfies all four predicates first — {sample}",
        floor_of(good) is not None
        and floor_of(good) <= reachable(good)
        and not swallows_crash(good)
        and acts_on_verdict(good),
        "a mutation check whose baseline already fails proves nothing about the mutation",
    )
    r.check(
        "MUTATION: dropping the floor IS detected",
        floor_of(good.replace(f"Results(expect={floor_of(good)})", "Results()")) is None,
        "this is the exact source state every paid rig was in before Phase 10",
    )
    r.check(
        "MUTATION: a floor above the reachable count IS detected",
        floor_of(good.replace(f"Results(expect={floor_of(good)})", "Results(expect=999)")) > reachable(good),
        "an unsatisfiable floor is a different defect from a missing one and needs its own leg",
    )
    r.check(
        "MUTATION: removing the guard from a rig that exits in `finally` IS detected",
        swallows_crash(good.replace('r.check("UNEXPECTED EXCEPTION", False, "see traceback above")', "pass")),
        "the guard is the only thing standing between a crash and a green exit code once a "
        "`finally` calls sys.exit — this is the exact pre-Phase-10 state of ten paid rigs",
    )
    r.check(
        "MUTATION (inverted): a rig with NO try block is NOT reported as swallowing",
        not swallows_crash("import sys\nclass R: pass\nr=R()\nsys.exit(0 if r.summary() else 1)\n"),
        "probe_twin.py is this shape. An absence predicate that fires on everything is as useless "
        "as one that fires on nothing, so the negative direction gets its own leg",
    )
    r.check(
        "MUTATION: discarding summary()'s verdict IS detected",
        not acts_on_verdict(good.replace("ok = r.summary()", "r.summary()").replace("sys.exit(0 if ok else 1)", "pass")),
        "this is what six rigs did, and it is why a permanently-red assertion survived five phases",
    )
    r.check(
        "MUTATION: cleanup AFTER the verdict exit IS detected",
        not finally_ends_on_verdict(good.replace("    sys.exit(0 if ok else 1)", "    sys.exit(0 if ok else 1)\n    t.close()")),
        "code after the exit never runs; a rig written that way looks like it cleans up and does not",
    )
    r.check(
        "MUTATION: the INLINED verdict shape is still accepted",
        acts_on_verdict(
            "import sys\nclass R: pass\nr=R()\nsys.exit(0 if r.summary() else 1)\n"
        ),
        "`sys.exit(0 if r.summary() else 1)` is the other legitimate shape — a predicate that "
        "only recognised the two-line form would force a pointless rewrite of four probes",
    )

    # --- contract 6: an assertion must SEE a failed turn, not just count a finished thread ---
    claims = {n: box_claims(src[n]) for n in names}
    offenders = {n: v for n, v in claims.items() if v}
    r.check(
        "NO RIG ASSERTS THAT A TURN COMPLETED BY COUNTING fire()'s BOX",
        not offenders,
        "`fire()` appends a thrown turn and a finished turn in the same 3-tuple, so a count "
        "cannot tell them apart. TESTED: three fire() calls at a dead port satisfied every "
        "completion predicate in the suite in 9ms. Use rig.completed(). "
        + (f"OFFENDERS: {offenders}" if offenders else "none — all completion claims read the payload"),
    )
    exempt = {n: v for n, v in {n: box_exemptions(src[n]) for n in names}.items() if v}
    r.check(
        "…and the ABSENCE exemption is exercised, and is small enough to name",
        0 < sum(len(v) for v in exempt.values()) <= 3,
        f"{exempt} — `not any(b[0] == 'blocker' for b in box)` claims a turn has NOT ended, and a "
        "turn that threw makes it red, which is correct. An exemption nobody exercises is dead "
        "text; one that grows without being counted is how a guard stops guarding",
    )
    sample_box = "verify_question.py"
    fixed = src[sample_box]
    r.check(
        f"the contract-6 mutation sample is CLEAN first — {sample_box}",
        not box_claims(fixed) and "completed(box" in fixed,
        "a mutation check whose baseline already fails proves nothing about the mutation. This is "
        "the file whose worker row had no independent evidence anywhere else in it",
    )
    r.check(
        "MUTATION: reverting a row to the raw-box count IS detected",
        bool(box_claims(fixed.replace('completed(box, "worker")', '[b for b in box if b[0].startswith("worker")]'))),
        "this is the exact source state of four assertion rows before Phase 12 — the shape that "
        "three connection errors satisfy",
    )
    r.check(
        "MUTATION (inverted): routing the SAME claim through completed() is NOT reported",
        not box_claims(
            'class R: pass\nr=R()\nfrom rig import completed\n'
            'box=[]\nw=completed(box,"worker")\nr.check("x", len(w)==3, f"{box}")\n'
        ),
        "a predicate that fires on the fixed form too would force every rig to stop using the box "
        "at all, including in the DETAIL string where the raw exceptions belong",
    )
    r.check(
        "MUTATION: the absence exemption does NOT swallow a positive claim",
        bool(box_claims(
            'class R: pass\nr=R()\nbox=[]\nr.check("x", any(b[0]=="blocker" for b in box))\n'
        ))
        and not box_claims(
            'class R: pass\nr=R()\nbox=[]\nr.check("x", not any(b[0]=="blocker" for b in box))\n'
        ),
        "same predicate, `not` stripped: exempt with it, reported without it. Without this leg the "
        "exemption could be widening to cover everything and the sweep above would still read green",
    )
    r.check(
        "RUNTIME: completed() rejects an exception and keeps a falsy-but-VALID result",
        completed([("w0", 1.0, RuntimeError("boom")), ("w1", 1.0, None), ("w2", 1.0, [])]) ==
        [("w1", 1.0, None), ("w2", 1.0, [])]
        and completed([("w0", 1.0, {}), ("a0", 1.0, {})], "w") == [("w0", 1.0, {})],
        "`None` and `[]` are what this API returns for an empty body and an empty list — a "
        "truthiness test would discard two real completions, so the predicate is isinstance",
    )

    # --- contract 7: an environment guard must be able to stop its own predicate ------------
    eager = {n: v for n, v in {n: eager_guards(src[n]) for n in names}.items() if v}
    guards = {n: v for n, v in {n: guarded(src[n]) for n in names}.items() if v}
    r.check(
        "EVERY ENVIRONMENT-GUARDED CHECK PASSES A LAMBDA",
        not eager,
        "Python evaluates arguments eagerly, so an expression predicate has already run — and "
        "already crashed, if the missing environment is what it reads — before `needs=` can skip "
        "anything. The author sees a guarded row; the machine ran it unguarded. "
        + (f"EAGER: {eager}" if eager else "all guarded predicates are lambdas"),
    )
    r.check(
        f"…and the contract is EXERCISED — {sum(len(v) for v in guards.values())} guarded site(s) "
        f"across {len(guards)} rig(s)",
        sum(len(v) for v in guards.values()) >= 1,
        f"{guards} — a sweep with nothing to sweep passes by measuring nothing, and this one "
        "would read green on the day the last needs= was deleted",
    )
    guard_sample = "probe_backend.py"
    gsrc = src[guard_sample]
    r.check(
        f"the contract-7 mutation sample is CLEAN first — {guard_sample}",
        not eager_guards(gsrc) and len(guarded(gsrc)) >= 1,
        "a mutation check whose baseline already fails proves nothing about the mutation",
    )
    r.check(
        "MUTATION: rewriting a guarded predicate into the EAGER form IS detected",
        bool(eager_guards(gsrc.replace(
            'lambda: bool([d for d in real_dirs if "--claude-worktrees-" in d])',
            'bool([d for d in real_dirs if "--claude-worktrees-" in d])', 1))),
        "this is the shape an author lands on by copying an unguarded row and appending needs= "
        "to it, and it is the one the run-time TypeError catches too late to be useful in review",
    )
    r.check(
        "MUTATION (inverted): an UNGUARDED expression predicate is NOT reported",
        not eager_guards('class R: pass\nr=R()\nr.check("x", 1 == 1)\n'),
        "the contract is scoped to needs= sites. A predicate that fired on every ordinary row "
        "would demand a lambda everywhere in the suite for no reason at all",
    )

    # --- runtime: the skip machinery, driven directly ---------------------------------------
    # The four contract-7 rows above are about SOURCE. These are the behaviour that source is
    # chosen to produce. Both halves are needed and neither substitutes: a lambda that the guard
    # then evaluates anyway satisfies the static contract and defeats the mechanism.
    ABSENT = Env("synthetic-absent", "a fact this machine does not have", lambda: False)
    PRESENT = Env("synthetic-present", "a fact every machine has", lambda: True)
    BROKEN = Env("synthetic-broken", "a fact whose probe blows up", lambda: 1 / 0)
    evaluated = []

    def thunk(value):
        """A predicate that RECORDS having been evaluated, so 'never called' is assertable."""

        def go():
            evaluated.append(value)
            return value

        return go

    def synthetic(expect, skip_max, legs):
        """(verdict, skips) for a synthetic run. `legs` is (env_or_None, thunk) pairs; the
        unguarded ones are called on the way in, exactly as an ordinary row would be."""
        res = Results(expect=expect, skip_max=skip_max)
        with contextlib.redirect_stdout(io.StringIO()):
            for i, (env, th) in enumerate(legs):
                if env is None:
                    res.check(f"synthetic {i}", th())
                else:
                    res.check(f"synthetic {i}", th, needs=env)
            return res.summary(), res.skips()

    evaluated.clear()
    ok_skip, skips = synthetic(2, 1, [(None, thunk(True)), (ABSENT, thunk(False))])
    r.check(
        "RUNTIME: an unsatisfied requirement SKIPS the row, and its predicate is NEVER evaluated",
        ok_skip is True and evaluated == [True]
        and [s["needs"] for s in skips] == ["synthetic-absent"],
        "the skipped leg's predicate returns False, so a guard that evaluated it anyway would "
        "make this verdict False and put a second entry in `evaluated`. Also proves a skipped "
        "row still counts toward the floor: 2 rows, one of them a skip, against expect=2",
    )

    evaluated.clear()
    ok_run, ran_skips = synthetic(2, 1, [(None, thunk(True)), (PRESENT, thunk(False))])
    r.check(
        "RUNTIME: a SATISFIED requirement runs the row, and a red row is still red",
        ok_run is False and ran_skips == [] and evaluated == [True, False],
        "the mechanism's other direction, and the one that matters most: satisfy the "
        "requirement and the check must go back to being an ordinary check, able to fail. A "
        "guard that swallowed the failure would be a mute button with extra steps",
    )

    evaluated.clear()
    ok_over, _ = synthetic(3, 1, [(None, thunk(True)), (ABSENT, thunk(True)), (ABSENT, thunk(True))])
    r.check(
        "RUNTIME: skipping PAST the declared budget is RED",
        ok_over is False,
        "two skips against skip_max=1. Either a requirement stopped holding where it should or "
        "one was added uncounted; the budget is what stops the skip surface widening quietly, "
        "the same job the box exemption's ceiling does for contract 6",
    )

    evaluated.clear()
    ok_blank, _ = synthetic(1, 5, [(ABSENT, thunk(True))])
    r.check(
        "RUNTIME: a run where NOTHING was measured is RED whatever the budget allows",
        ok_blank is False,
        "one row, one skip, budget of five — inside every limit and still worth nothing. This is "
        "the failure the whole mechanism is built to avoid: a probe that quietly became all-skip "
        "and kept reporting green",
    )

    evaluated.clear()
    ok_broken, broken_skips = synthetic(1, 1, [(BROKEN, thunk(True))])
    r.check(
        "RUNTIME: a requirement whose own probe RAISES counts as unsatisfied, not as satisfied",
        ok_broken is False and [s["needs"] for s in broken_skips] == ["synthetic-broken"]
        and evaluated == [],
        "the row is skipped (not measured) rather than run against an environment nobody could "
        "establish — and because that leaves nothing measured, the run is red by the rule above",
    )

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            Results(expect=1, skip_max=1).check("eager", True, needs=ABSENT)
        raised = False
    except TypeError:
        raised = True
    r.check(
        "RUNTIME: needs= with a NON-CALLABLE predicate raises TypeError",
        raised,
        "contract 7's run-time half. The static sweep reads lambdas out of source; this catches "
        "the forms source analysis cannot see, such as a name bound to an already-computed bool",
    )

    # --- runtime: the floor mechanism itself ----------------------------------------------
    # These drive Results directly, so each one prints its own `== summary ==` block. That output
    # is noise in the middle of this probe's own results and, worse, a reader skimming for
    # "N/N passed" can mistake a synthetic block for the real verdict. Captured, not silenced:
    # the value under assertion is the RETURN of summary(), which is what the fix changed.
    def verdict(expect, results):
        """Run a synthetic Results and return summary()'s verdict, swallowing only its printing."""
        res = Results(expect=expect)
        for i, ok in enumerate(results):
            res.check(f"synthetic {i}", ok)
        with contextlib.redirect_stdout(io.StringIO()):
            return res.summary()

    # The four predicates above are about SOURCE. This is the behaviour that source is chosen to
    # produce, and asserting it here is what stops the two drifting.
    r.check("RUNTIME: a full pass returns True", verdict(3, [True] * 3) is True, "3 of 3 with a floor of 3")
    r.check(
        "RUNTIME: a SHORT run returns False even with zero failures",
        verdict(3, [True] * 2) is False,
        "2 of 3, all green — this is the case that reported `2/2 passed` and exit 0 before Phase 9",
    )
    r.check(
        "RUNTIME: a failing row still returns False",
        verdict(3, [True, False, True]) is False,
        "the pre-existing behaviour is intact",
    )
    legacy = Results()
    legacy.check("synthetic", True)
    with contextlib.redirect_stdout(io.StringIO()):
        legacy_ok = legacy.summary()
    r.check(
        "RUNTIME: expect=None keeps the old behaviour",
        legacy_ok is True,
        "the floor is opt-in, so a rig without one must not start failing for a new reason",
    )
    r.check(
        "RUNTIME: the floor is a MINIMUM, not an equality",
        verdict(2, [True] * 5) is True,
        "5 against a floor of 2 — adding an assertion must not turn a rig red, or the floor "
        "becomes bookkeeping nobody maintains and the next author deletes it",
    )

except SystemExit:
    raise
except Exception:
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    ok = r.summary()
    sys.exit(0 if ok else 1)
