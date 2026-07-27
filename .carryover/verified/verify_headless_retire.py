"""HEADLESS automatic retirement: the gate fires with no client attached at all.

This is `verify_auto_retire.py`'s lifecycle assertion — gate met, the model call in flight
completes, handoff, retire, successor picks up immediately, no new turn after the gate — run in
the topology that version could not reach.

THAT SECOND CLAUSE USED TO READ "turn finishes", AND IT WAS WRONG. The gate fires at a STEP
boundary, not at the end of a turn. `processor.ts:443-445` assigns `finish` and `tokens` in the
SAME mutation at every `step-finish`, and `:445` is the only site in the session tree that writes
a non-zero `tokens` — so every `message.updated` carrying occupancy at all also carries a set
`finish`, usually `"tool-calls"`, i.e. mid-turn. MEASURED across 733 real assistant messages with
occupancy > 0: zero had a null `finish` (677 `tool-calls`, 56 `stop`). The turn in flight IS
aborted, and overshoot past the gate is bounded by one STEP (~65K measured) rather than one whole
turn (~170K measured) — better than what was designed, arrived at by accident.

WHAT CHANGED AND WHY IT MATTERS. Phase 5's trigger was a `createEffect` inside the Healbot route
component. `verify_auto_retire.py` opens the grid first, and its own docstring records the
limitation: "it only runs while the grid is OPEN". So the 13/13 it earned was real but conditional
on a human watching. `harness/fleet.sh` exists precisely so the server can outlive the terminal,
which means the guard was missing in the topology the architecture was built for.

**No TUI is started anywhere in this file.** There is no pty, no `boot()`, no `attach()`, no
`on_grid` — nothing renders. Every session is driven over HTTP. If a session retires here, the
only thing that can have retired it is the server plugin at
`harness/config/opencode/plugin/healbot.ts` (this line said `auto-retire.ts` until 7b7ce9f
renamed the file; there is no `auto-retire.ts` any more).

Run at a LOW threshold on purpose: the path compares `occupancyOf` against `RETIRE_AT` and does
not care what the number is, so 20,000 exercises the same code as 256,000 for a fraction of the
cost.

ASSERTION DISCIPLINE. "A successor appeared" is not enough on its own — a successor could in
principle be created by anything. So the retirement is ALSO asserted against the server's own log
line, which names the successor id and which only the plugin writes; and the absence of any TUI is
asserted against the process table rather than against the fact that this file does not call
`boot()`. The kill-switch negative control lives in `probe_headless_arm.py`, where it is free.

  venv/bin/python verify_headless_retire.py
"""

import os
import re
import subprocess
import sys
import time

from rig import PROJECT, WORK, Api, Results, db, fire, fixtures, git_baseline, serve, wait_for

PORT = 4743
DB = db("headless")
LOG = f"{WORK}/headless-serve.log"
THRESHOLD = 20_000

r = Results()
api = Api(PORT, PROJECT)
server = None


def messages(sid):
    return api("GET", f"/session/{sid}/message") or []


def texts(sid, role=None):
    out = []
    for m in messages(sid):
        info = m.get("info") or m
        if role and info.get("role") != role:
            continue
        out += [p.get("text", "") for p in (m.get("parts") or []) if p.get("type") == "text"]
    return "\n".join(out)


def assistants(sid):
    return [(m.get("info") or m) for m in messages(sid) if (m.get("info") or m).get("role") == "assistant"]


def live():
    return [s for s in (api("GET", "/session?scope=project") or []) if not (s.get("time") or {}).get("archived")]


def server_log():
    if not os.path.exists(LOG):
        return ""
    with open(LOG, encoding="utf-8", errors="replace") as fh:
        return fh.read()


fixtures()
for stale in ("notes.txt",):
    if os.path.exists(f"{PROJECT}/{stale}"):
        os.remove(f"{PROJECT}/{stale}")
git_baseline()

try:
    print("== a headless server, and nothing else ==", flush=True)
    server = serve(
        PORT,
        DB,
        log=LOG,
        # Into the SERVER's environment, because the SERVER is what enforces the gate now. A rig
        # that exports these into its own process configures nothing.
        env_extra={"HEALBOT_RETIRE_AT": str(THRESHOLD), "HEALBOT_AUTO_RETIRE": "1"},
    )
    time.sleep(2)
    r.check(
        "the guard armed inside the server",
        "headless retirement armed" in server_log(),
        f"soft {THRESHOLD:,}",
    )

    # The load-bearing precondition. Every other assertion in this file is about something that
    # happened with nothing rendering, so "nothing is rendering" has to be a measurement, not an
    # assumption about what this script does or does not call.
    ps = subprocess.run(["ps", "-eo", "command"], capture_output=True, text=True).stdout
    tui_procs = [
        line
        for line in ps.splitlines()
        if ("opencode" in line or "src/index.ts" in line)
        and (" attach " in line or re.search(r"src/index\.ts\s+/", line))
    ]
    r.check(
        "NO TUI IS RUNNING — not attached, not hosted, not anywhere",
        not tui_procs,
        "this is the condition Phase 5's trigger could not survive"
        if not tui_procs
        else f"found {tui_procs[:2]}",
    )

    before = {s["id"] for s in live()}
    worker = api("POST", "/session", {})["id"]
    print(f"  worker {worker}", flush=True)

    box = []
    fire(
        api,
        worker,
        # ORDER IS THE TEST. The big read goes FIRST so its result sits in the input of every
        # step after it — which puts the threshold crossing MID-turn, at a `tool-calls` step,
        # instead of on the final model call. Until Phase 7 this prompt read the ledger LAST, and
        # the consequence was that the only step above the gate was the closing `stop`: the
        # per-step and per-turn predicates behaved identically, and `finishes[-1] == "stop"` below
        # passed BY CONSTRUCTION. MEASURED on that version — steps at 4,999 / 5,165 / 5,236 then
        # `stop` at 36,612 against a 20,000 gate. It proved the gate fires; it never proved the
        # gate waits.
        "First read ledger0.txt in full with the read tool, with offset=1 and limit=1400. "
        "Then use the todowrite tool to record exactly three items: 'read the ledger', "
        "'summarise the ledger into notes.txt', and 'reconcile the totals'. Mark only the "
        "first completed. Then create notes.txt containing the single word STARTED. Then reply "
        "with one sentence about what the ledger contains.",
        box=box,
        label="worker",
    )

    # ---------------------------------------------------------------- it retires itself
    print("\n== waiting for the gate to fire — no keypress, no client ==", flush=True)
    successor = wait_for(
        lambda: next(
            (
                s["id"]
                for s in live()
                if s["id"] not in before
                and s["id"] != worker
                and not s.get("parentID")
                and "taking over" in texts(s["id"], role="user").lower()
            ),
            None,
        ),
        900,
        "HEADLESS automatic retirement",
    )
    r.check(
        "THE SESSION RETIRED ITSELF WITH NOTHING ATTACHED — the Phase 5 gap, closed",
        bool(successor),
        f"successor {successor}",
    )
    if not successor:
        raise SystemExit(1)

    # The discriminating evidence. This line is written by the server plugin and by nothing else;
    # a TUI cannot produce it, and it names the successor the assertion above found.
    log = server_log()
    r.check(
        "the SERVER's own log records the retirement, naming that successor",
        successor in log and "at the gate" in log,
        next((ln for ln in log.splitlines() if successor in ln), "not found"),
    )

    archived = wait_for(
        lambda: ((api("GET", f"/session/{worker}") or {}).get("time") or {}).get("archived"),
        120,
        "predecessor archived",
    )
    r.check("the predecessor was archived automatically", bool(archived))

    # ---------------------------------------------------------------- it finished first
    #
    # An assistant message is a STEP, not a turn — `prompt.ts:1186-1201` creates a new one per
    # step and `processor.ts:443-445` stamps `finish` and `tokens` on each. So this list is the
    # shape of ONE turn, and reading it correctly is the whole point of the block below.
    turns = assistants(worker)
    finishes = [a.get("finish") for a in turns if a.get("finish")]

    def occupancy_of(a):
        t = a.get("tokens") or {}
        if t.get("total"):
            return t["total"]
        cache = t.get("cache") or {}
        return (t.get("input") or 0) + (t.get("output") or 0) + (cache.get("read") or 0) + (cache.get("write") or 0)

    occupancies = [occupancy_of(a) for a in turns if a.get("finish")]
    # THE ASSERTION THAT DISCRIMINATES, and the one this rig lacked. `finishes[-1] == "stop"`
    # below is necessary but not sufficient: it is satisfied by a gate that fires at ANY step
    # boundary, as long as the crossing happened to be the last one. What separates per-turn from
    # per-step is whether a NON-FINAL step was already over the gate and the turn ran on anyway.
    crossed_early = [
        (i, occ) for i, occ in enumerate(occupancies) if occ >= THRESHOLD and i < len(occupancies) - 1
    ]
    r.check(
        "the gate was crossed MID-TURN — otherwise this file cannot tell per-turn from per-step",
        bool(crossed_early),
        f"steps over {THRESHOLD:,} before the last: {crossed_early}"
        if crossed_early
        else f"NOT DISCRIMINATING: only the final step crossed. occupancies={occupancies}",
    )
    r.check(
        "…and the turn RAN ON past that crossing instead of being aborted at it",
        bool(crossed_early) and finishes[-1] == "stop" and len(finishes) > crossed_early[0][0] + 1,
        f"crossed at step {crossed_early[0][0] if crossed_early else '?'} of {len(finishes)}, "
        f"finishes={finishes}",
    )
    r.check(
        "the turn was allowed to FINISH before the handoff",
        bool(finishes) and finishes[-1] == "stop",
        f"finishes={finishes}",
    )
    r.check("no turn ended in error", "error" not in finishes, f"{finishes.count('error')} errored")

    # TURNS are user messages; assistant messages are STEPS within a turn. The second sentence
    # here used to read "the gate rule is about turns"; it is not. The gate is evaluated per STEP
    # and aborts the turn in flight. What survives the correction — and what this assertion
    # actually measures — is that no NEW turn was accepted after the gate was met, which is the
    # property that matters for a successor being the one that continues the work.
    user_turns = [m for m in messages(worker) if (m.get("info") or m).get("role") == "user"]
    r.check(
        "NO NEW TURN RAN AFTER THE GATE",
        len(user_turns) == 1,
        f"{len(user_turns)} turn(s), {len(turns)} step(s): {finishes}",
    )

    def occ(a):
        tk = a.get("tokens") or {}
        c = tk.get("cache") or {}
        return tk.get("total") or tk.get("input", 0) + tk.get("output", 0) + c.get("read", 0) + c.get("write", 0)

    peak = max((occ(a) for a in turns), default=0)
    r.check(
        "occupancy really did cross the gate",
        peak >= THRESHOLD,
        f"{peak:,} vs gate {THRESHOLD:,} ({round(peak / THRESHOLD, 1)}x)",
    )

    # ---------------------------------------------------------------- the handoff is intact
    seed = texts(successor, role="user")
    r.check("the successor was seeded with a handoff document", "taking over" in seed.lower(), f"{len(seed)} chars")
    r.check("the handoff carries outstanding work", "## Outstanding work" in seed)
    # The objective must come from the SERVER's full history, not a window. Here the session is
    # short enough that both agree, so this asserts the section is present and non-empty rather
    # than claiming to have exercised the >100-message path (verify_retire_350k.py owns that).
    objective = seed.split("## Original instruction, for context only", 1)[-1].split("## Outstanding work", 1)[0]
    r.check(
        "the objective section carries the predecessor's actual first instruction",
        "todowrite" in objective and "ledger0.txt" in objective,
        f"{len(objective.strip())} chars",
    )
    # MUTATION CHECK: the same predicate against the section with that material stripped must
    # fail, or it was passing on the document's other mentions of the same words.
    stripped = objective.replace("todowrite", "").replace("ledger0.txt", "")
    r.check(
        "mutation check: stripping the objective DOES break that assertion",
        not ("todowrite" in stripped and "ledger0.txt" in stripped),
    )
    r.check(
        "the handoff names the file the predecessor created",
        "notes.txt" in seed.split("## Files already changed", 1)[-1] if "## Files already changed" in seed else False,
        "diff fan-out over the server's own history",
    )

    # ---------------------------------------------------------------- the successor takes over
    def successor_finished():
        for a in assistants(successor):
            if (a.get("time") or {}).get("completed") or a.get("finish"):
                return a
        return None

    r.check(
        "the successor picked the work up IMMEDIATELY, unprompted",
        wait_for(successor_finished, 600, "successor's first turn") is not None,
    )

    open_todos = {
        x.get("content", "").strip()
        for x in (api("GET", f"/session/{worker}/todo") or [])
        if x.get("status") != "completed"
    }
    successor_todos = {x.get("content", "").strip() for x in (api("GET", f"/session/{successor}/todo") or [])}
    r.check(
        "the successor's OWN todo list carries the predecessor's open items",
        bool(open_todos) and open_todos.issubset(successor_todos),
        f"{len(open_todos & successor_todos)}/{len(open_todos)} carried",
    )

    # ---------------------------------------------------------------- no runaway
    time.sleep(5)
    chain = [s for s in live() if s["id"] not in before and s["id"] != successor and not s.get("parentID")]
    r.check("it did not chain into a second retirement", len(chain) == 0, f"{len(chain)} extra session(s)")
    r.check(
        "the successor started near the floor, not at the predecessor's occupancy",
        max((occ(a) for a in assistants(successor)), default=0) < THRESHOLD,
        f"{max((occ(a) for a in assistants(successor)), default=0):,}",
    )

    # And the server is still serving. A guard that takes the fleet down with it is not a guard.
    r.check("the server is still healthy afterwards", api("GET", "/session?scope=project") is not None)
    r.check("the guard did not report a failure", "retire FAILED" not in server_log(), "no failure lines")

finally:
    if server:
        try:
            server.kill()
        except Exception:
            pass
    ok = r.summary()
    print(f"\n  server log: {LOG}", flush=True)
    sys.exit(0 if ok else 1)
