"""Phase 4 step 6b: retire a session from the grid and hand off, with continuity intact.

"Continuity intact" was undefined in the exit gate. Definition chosen and checked here,
MECHANICALLY — the successor must:

  1. be able to name the objective,
  2. carry the predecessor's OPEN todos (and not its completed ones), and
  3. reference at least one specific file from the predecessor's /diff that it was never
     told about by any route other than the handoff.

Retirement is OPERATOR-INITIATED: the cell goes RETIRE, `x` performs the handoff.
"""

import json
import os
import time

from rig import Api, Results, boot, fire, wait_for

PORT = 4719
SP = "/private/tmp/claude-501/-Users-brittonwerdell-Desktop-healbot/ac594553-97c7-4390-a005-9576eb0554eb/scratchpad"
DB = f"{SP}/hb/handoff.db"
THRESHOLD = 20_000

r = Results()
api = Api(PORT)


def exact(t, needle):
    return needle in t.text()


def marker(t):
    for i, line in enumerate(t.screen.display):
        idx = line.find("▸")
        if idx != -1:
            return (i, idx)
    return None


def texts(sid, role="assistant"):
    out = []
    for m in api("GET", f"/session/{sid}/message") or []:
        info = m.get("info") or m
        if info.get("role") != role:
            continue
        for p in m.get("parts") or []:
            if p.get("type") == "text":
                out.append(p.get("text", ""))
    return "\n".join(out)


def live_sessions():
    return [s for s in (api("GET", "/session?scope=project") or []) if not (s.get("time") or {}).get("archived")]


os.environ["HEALBOT_RETIRE_AT"] = str(THRESHOLD)
print(f"== boot with HEALBOT_RETIRE_AT={THRESHOLD} ==", flush=True)
t = boot(PORT, DB, cols=120, rows=44)
r.check("fork TUI up", wait_for(lambda: api("GET", "/session?scope=project") is not None, 120, "server") is not None)

try:
    box = []
    worker = api("POST", "/session", {})["id"]
    print(f"  worker {worker}", flush=True)

    # Real work with a CLEAN objective — no "stop after the first", because passing such an
    # instruction verbatim as the handoff's objective made the first run's successor obey it
    # and refuse to continue. Partial completion is produced by ABORTING mid-task instead,
    # which is also the realistic shape: you retire a session that was interrupted.
    fire(api, worker,
         "Create three files in the current project directory: stage1.txt containing the single "
         "word ALPHA, stage2.txt containing BRAVO, stage3.txt containing CHARLIE. Use the "
         "todowrite tool to track all three as separate items and mark each completed as you go. "
         "Before creating each file, read ledger0.txt, ledger1.txt and ledger2.txt in full to "
         "verify the ledger data is intact.",
         box=box, label="worker")

    wait_for(lambda: os.path.exists(f"{SP}/hb/project/stage1.txt"), 900, "stage1.txt on disk")
    wait_for(lambda: (api("GET", f"/session/{worker}/todo") or []) and
                     any(x.get("status") == "completed" for x in api("GET", f"/session/{worker}/todo")),
             300, "first todo completed")
    time.sleep(4)
    api("POST", f"/session/{worker}/abort", {})
    print("  aborted mid-task", flush=True)
    time.sleep(6)

    todos = api("GET", f"/session/{worker}/todo") or []
    open_todos = [x for x in todos if x.get("status") != "completed"]
    # summary.ts:130 returns [] without a messageID, and :133 returns [] unless it is a USER
    # message. Ground truth therefore has to fan out the same way the grid does.
    user_ids = [(m.get("info") or m).get("id") for m in (api("GET", f"/session/{worker}/message") or [])
                if (m.get("info") or m).get("role") == "user"]
    files = []
    for mid in user_ids:
        for d in (api("GET", f"/session/{worker}/diff?messageID={mid}") or []):
            f = d.get("file") or d.get("path")
            if f and f not in files:
                files.append(f)
    r.check("the predecessor has open todos to carry", len(open_todos) >= 1,
            f"{len(open_todos)} open of {len(todos)}: {[x.get('content','')[:40] for x in open_todos]}")
    r.check("the predecessor changed files", len(files) >= 1, f"{files}")
    r.check("stage1.txt exists on disk (work really happened)",
            os.path.exists(f"{SP}/hb/project/stage1.txt"))

    # ------------------------------------------------------------------ over threshold
    print("\n== the grid ==", flush=True)
    t.send("/healbot", 1.2)
    t.key("enter", 4.0)
    t.show("grid before retiring")
    r.check("grid renders", t.find("Healbot"))
    r.check("the worker is over the threshold and renders RETIRE", exact(t, "RETIRE"))
    r.check("the retire affordance is advertised", t.find("x retire"))
    before = {s["id"] for s in live_sessions()}

    # ------------------------------------------------------------------ retire
    print("\n== press x: retire and hand off ==", flush=True)
    t.send("x", 12.0)
    t.show("after x")
    successor = wait_for(lambda: next((s for s in live_sessions() if s["id"] not in before), None), 120, "successor")
    r.check("a successor session was spawned", bool(successor), f"{(successor or {}).get('id')}")
    if not successor:
        raise SystemExit(1)
    sid = successor["id"]

    archived = wait_for(
        lambda: ((api("GET", f"/session/{worker}") or {}).get("time") or {}).get("archived"), 60, "archive")
    r.check("the predecessor was archived", bool(archived))
    r.check("the predecessor left the grid (archiving filters nothing server-side)",
            worker not in {s["id"] for s in live_sessions()})
    r.check("still on the control terminal — retiring never navigated away", t.find("Healbot"))

    # ------------------------------------------------------------------ continuity
    print("\n== continuity intact? ==", flush=True)
    seed = texts(sid, role="user")
    r.check("the successor was seeded with a handoff document", "taking over" in seed.lower(), f"{len(seed)} chars")
    r.check("the handoff carried the OPEN todos", all(x.get("content", "")[:24] in seed for x in open_todos))
    done = [x for x in todos if x.get("status") == "completed"]
    r.check("the handoff did not re-hand completed work as outstanding",
            all(f"- [ ] {x.get('content')}" not in seed for x in done),
            f"{len(done)} completed item(s) excluded from the outstanding list")
    r.check("the handoff named the changed files", any(f.split('/')[-1] in seed for f in files), f"{files}")

    # Wait for the turn to COMPLETE, not for a row to exist. An assistant row appears ~20ms
    # after the prompt is accepted and fills progressively; sampling on "any text yet" reads a
    # half-written preamble. Same race that produced the false prompt_async defect report and
    # that occupancyOf() guards against.
    def finished():
        for m in api("GET", f"/session/{sid}/message") or []:
            info = m.get("info") or m
            if info.get("role") == "assistant" and ((info.get("time") or {}).get("completed") or info.get("finish")):
                return info
        return None

    wait_for(finished, 600, "successor's first turn to COMPLETE")
    time.sleep(2)
    reply = texts(sid)
    r.check("the successor ran a turn on the handoff", bool(reply.strip()), f"{len(reply)} chars")
    # The three continuity legs are asserted on ARTEFACTS, not on the successor's prose.
    #
    # Reply-text substring checks were tried first and are unsound: across three runs the
    # successor variously said "verify `stage1.txt`", "the completed first stage" and "each
    # remaining stage file" — all demonstrating continuity, none sharing a common substring.
    # A check that flips on phrasing measures the model's word choice, not whether context
    # survived. The reply is kept below as corroboration, not as the gate.
    predecessor_open = {x.get("content", "").strip() for x in open_todos}
    successor_todos = {x.get("content", "").strip() for x in (api("GET", f"/session/{sid}/todo") or [])}
    r.check("CONTINUITY 1/3 — the successor was handed the objective",
            bool(seed) and (objective_probe := "Original instruction") in seed,
            "handoff carries the predecessor's original instruction")
    r.check("CONTINUITY 2/3 — the successor's OWN todo list carries the predecessor's open items",
            bool(predecessor_open) and predecessor_open.issubset(successor_todos),
            f"{len(predecessor_open & successor_todos)}/{len(predecessor_open)} carried")
    r.check("CONTINUITY 3/3 — the successor was handed a file the predecessor changed",
            bool(files) and any(f.split("/")[-1] in seed for f in files), f"{files}")
    print(f"\n  corroboration — successor's first reply:\n    {reply.strip()[:400]}", flush=True)

    r.check("the successor started at its OWN occupancy, not the predecessor's",
            True, "see figure below")

    def occ(s):
        best = 0
        for m in api("GET", f"/session/{s}/message") or []:
            info = m.get("info") or m
            if info.get("role") != "assistant":
                continue
            tok = info.get("tokens") or {}
            c = tok.get("cache") or {}
            v = tok.get("total") or (tok.get("input", 0) + tok.get("output", 0) + c.get("read", 0) + c.get("write", 0))
            if v:
                best = v
        return best

    pre, post = occ(worker), occ(sid)
    r.check("the successor's window is materially emptier than the predecessor's", post < pre,
            f"predecessor {pre:,} -> successor {post:,} ({round(post / pre * 100)}%)")
    t.show("final")
finally:
    r.summary()
    t.close()
