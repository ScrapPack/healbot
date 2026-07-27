"""Isolate why GET /session/{id}/diff returns [] — abort, or the fixture?

summary.ts:88-99 builds the diff from `snapshot` fields on step-start / step-finish parts and
returns [] unless BOTH ends are present. snapshot/index.ts:167-170 gates tracking on
`state.vcs === "git"`. Two candidate causes, separated here by running one clean, uninterrupted
file-writing turn and inspecting the parts directly.
"""

import json
import time

from rig import Api, PROJECT, Results, boot, db, fire, wait_for

PORT = 4720
DB = db("diffdiag")

r = Results()
api = Api(PORT)

t = boot(PORT, DB, cols=120, rows=44)
r.check("fork TUI up", wait_for(lambda: api("GET", "/session?scope=project") is not None, 120, "server") is not None)

try:
    sid = api("POST", "/session", {})["id"]
    box = []
    fire(api, sid, "Create a file called probe.txt in the current project directory containing "
                   "the single word DELTA. Then stop.", box=box, label="probe")
    wait_for(lambda: box, 300, "clean turn (NOT aborted)")

    msgs = api("GET", f"/session/{sid}/message") or []
    starts, finishes = [], []
    for m in msgs:
        for p in m.get("parts") or []:
            if p.get("type") == "step-start":
                starts.append(p.get("snapshot"))
            if p.get("type") == "step-finish":
                finishes.append(p.get("snapshot"))
    r.check("the turn completed cleanly", bool(box))
    r.check("step-start parts carry a snapshot", any(starts), f"{len([s for s in starts if s])}/{len(starts)}")
    r.check("step-finish parts carry a snapshot", any(finishes), f"{len([s for s in finishes if s])}/{len(finishes)}")

    d = api("GET", f"/session/{sid}/diff") or []
    r.check("GET /diff is non-empty for an UNINTERRUPTED file-writing turn", bool(d),
            json.dumps(d)[:300])

    summaries = [(m.get("info") or m).get("summary") for m in msgs if (m.get("info") or m).get("role") == "assistant"]
    print(f"  assistant summary fields: {json.dumps(summaries)[:400]}", flush=True)
    import os
    print(f"  probe.txt on disk: {os.path.exists(f'{PROJECT}/probe.txt')}", flush=True)
finally:
    r.summary()
    t.close()
