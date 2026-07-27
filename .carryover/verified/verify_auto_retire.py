"""Auto-retirement: the gate fires by itself, and no turn runs after it.

The lifecycle this asserts, in the owner's words: the context gate is met, the agent finishes
what it is doing, a handoff goes to a fresh session, the old session is retired, and the
successor picks the work up immediately — with no turn consumption after the gate.

Retirement used to be operator-initiated (`x`). That made the threshold advisory, and an
advisory threshold is not a guard: a 350K run crossed the gate and then burned **25 consecutive
turns** dying with `ContextOverflowError`, because nothing stopped it.

Run at a LOW threshold on purpose. The auto-retire path is threshold-independent — it compares
`occupancyOf` against `RETIRE_AT` and does not care what the number is — so exercising it at
20,000 tests exactly the same code as 256,000 for a few cents instead of a few dollars.

NOTE THE LIMITATION this rig also documents: the trigger is a `createEffect` inside the route
component, so it only runs while the grid is OPEN. That is the normal operating state under
`harness/fleet.sh`, but it is not headless. See HARDEN.md §8.

  venv/bin/python verify_auto_retire.py
"""

import json
import os
import sys
import time

from rig import Api, PROJECT, Results, boot, db, fixtures, fire, git_baseline, on_grid, wait_for

PORT = 4737
DB = db("autoretire")
THRESHOLD = 20_000

os.environ["HEALBOT_RETIRE_AT"] = str(THRESHOLD)
os.environ.pop("HEALBOT_AUTO_RETIRE", None)  # default is ON; make sure nothing disabled it

r = Results()
api = Api(PORT, PROJECT)


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


fixtures()
if os.path.exists(f"{PROJECT}/notes.txt"):
    os.remove(f"{PROJECT}/notes.txt")
git_baseline()

print("== boot, grid OPEN before any work exists ==", flush=True)
t = boot(PORT, DB, cols=120, rows=44)
r.check("fork TUI up", wait_for(lambda: api("GET", "/session?scope=project") is not None, 120, "server") is not None)

try:
    # The trigger is an effect inside the route component, so the grid has to be mounted for it
    # to observe anything. Opening it first is also the realistic shape: the control terminal is
    # the thing you leave running.
    t.send("/healbot", 1.5)
    t.key("enter", 4.0)
    r.check("grid open before the session exists", on_grid(t))

    before = {s["id"] for s in live()}
    worker = api("POST", "/session", {})["id"]
    print(f"  worker {worker}", flush=True)

    box = []
    fire(api, worker,
         "Use the todowrite tool to record exactly three items: 'read the ledgers', "
         "'summarise the ledgers into notes.txt', and 'reconcile the totals'. Mark only the "
         "first completed. Then create notes.txt containing the single word STARTED. Then read "
         "ledger0.txt and ledger1.txt in full with the read tool, with offset=1 and limit=2000 "
         "each, and reply with one sentence about what they contain.",
         box=box, label="worker")

    # ------------------------------------------------------------ it retires ITSELF
    # No `x` is sent anywhere in this file. That is the assertion.
    print("\n== waiting for the gate to fire on its own — no keypress ==", flush=True)
    successor = wait_for(
        lambda: next((s["id"] for s in live()
                      if s["id"] not in before and s["id"] != worker and not s.get("parentID")
                      and "taking over" in texts(s["id"], role="user").lower()), None),
        900, "AUTOMATIC retirement (no operator keypress)")
    r.check("the session retired ITSELF once over the gate — `x` was never pressed", bool(successor),
            f"successor {successor}")
    if not successor:
        raise SystemExit(1)

    archived = wait_for(lambda: ((api("GET", f"/session/{worker}") or {}).get("time") or {}).get("archived"),
                        120, "predecessor archived")
    r.check("the predecessor was archived automatically", bool(archived))

    # ------------------------------------------------------------ it finished first
    # "The agent should finish what it's doing." The turn that crossed the gate must have
    # completed normally, not been cut off — an aborted turn is work the successor has to
    # rediscover, which is the looping-discovery failure this design exists to avoid.
    turns = assistants(worker)
    finishes = [a.get("finish") for a in turns if a.get("finish")]
    r.check("the predecessor's turn was allowed to FINISH before the handoff",
            bool(finishes) and finishes[-1] == "stop", f"finishes={finishes}")
    r.check("no turn ended in error", "error" not in finishes, f"{finishes.count('error')} errored")

    # ------------------------------------------------------------ and stopped there
    # The gate rule: no turn consumption after it is met. Exactly one turn may carry the
    # session over the line (the one whose result crossed it); nothing may run afterwards.
    # TURNS are user messages. Assistant messages are STEPS within a turn — this run produced
    # 6 of them (`tool-calls` x5 then `stop`) for ONE prompt, and an earlier version of this
    # check counted those steps and failed the code for doing exactly what was asked. The gate
    # rule is about turns: nothing new may be accepted once it is met.
    user_turns = [m for m in messages(worker) if (m.get("info") or m).get("role") == "user"]
    r.check("NO NEW TURN RAN AFTER THE GATE — the session ran only the work it was given",
            len(user_turns) == 1,
            f"{len(user_turns)} turn(s), {len(turns)} step(s) within them: {finishes}")
    # The overshoot this measures is why the hard gate exists. Recorded rather than asserted:
    # it is workload-dependent, and the number is the point.
    def occ(a):
        tk = a.get("tokens") or {}
        c = tk.get("cache") or {}
        return tk.get("total") or tk.get("input", 0) + tk.get("output", 0) + c.get("read", 0) + c.get("write", 0)
    peak = max((occ(a) for a in turns), default=0)
    print(f"\n  overshoot: gate {THRESHOLD:,} -> turn finished at {peak:,} "
          f"({round(peak / THRESHOLD, 1)}x the gate) — this is what RETIRE_HARD guards", flush=True)

    # ------------------------------------------------------------ the successor takes over
    seed = texts(successor, role="user")
    r.check("the successor was seeded with a handoff document", "taking over" in seed.lower(), f"{len(seed)} chars")
    r.check("the handoff carries outstanding work", "## Outstanding work" in seed)

    def successor_finished():
        for a in assistants(successor):
            if (a.get("time") or {}).get("completed") or a.get("finish"):
                return a
        return None

    r.check("the successor picked the work up IMMEDIATELY, unprompted",
            wait_for(successor_finished, 600, "successor's first turn") is not None)

    open_todos = {x.get("content", "").strip() for x in (api("GET", f"/session/{worker}/todo") or [])
                  if x.get("status") != "completed"}
    successor_todos = {x.get("content", "").strip() for x in (api("GET", f"/session/{successor}/todo") or [])}
    r.check("the successor's OWN todo list carries the predecessor's open items",
            bool(open_todos) and open_todos.issubset(successor_todos),
            f"{len(open_todos & successor_todos)}/{len(open_todos)} carried")

    # ------------------------------------------------------------ no runaway
    # Guard against the failure mode auto-retirement could plausibly introduce: a successor that
    # trips the gate too and chains forever. It starts near the ~5K floor, so it must not.
    time.sleep(5)
    chain = [s for s in live() if s["id"] not in before and s["id"] != successor and not s.get("parentID")]
    r.check("it did not chain into a second retirement", len(chain) == 0,
            f"{len(chain)} extra session(s)")
    r.check("still on the control terminal throughout", on_grid(t))
    t.show("after automatic retirement")
finally:
    ok = r.summary()
    t.close()
    sys.exit(0 if ok else 1)
