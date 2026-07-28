"""Phase 5 part B: the cold-start reconcile, against a server that OUTLIVES the client.

This is the one thing `docs/VERIFY.md` §6 said could never be tested. Its reasoning:
`--port` is "port to listen on" (`cli/network.ts:9`), so the TUI always hosts its own server,
so a client can never meet a block that predates it, so `healbot.tsx`'s `reconcile()` is
unreachable and the two defect fixes sitting on it are unexercisable. `HARNESS.md` recorded
the item as **blocked**.

The premise about `--port` is true. The conclusion was false: `opencode attach <url>` is a
separate registered command (`cli/cmd/attach.ts:7-16`, `index.ts:84`) whose non---mini branch
calls the SAME `run()` from `cli/tui/layer` with the SAME `createLegacyTuiPluginHost()` as
`cli/cmd/tui.ts:271-296`, so it is the full TUI and the Healbot builtin loads on it.

Shape of the test, and the ordering is the entire point:

  1. start a headless `serve` -- nothing rendering
  2. fire a turn that blocks on an external-directory permission
  3. wait until the block EXISTS
  4. only then start the control terminal

At step 4 the live SSE store holds nothing about that block: `sync.tsx`'s `permission` map is
populated only by events observed in-process, and the block happened before the process
existed. If the cell still renders PERMISSION, the ONLY thing that can have put it there is
`reconcile()` reading `GET /permission`. That is the assertion.

  venv/bin/python verify_cold.py
"""

import json
import sys
import time

from rig import Api, Results, attach, db, fire, on_grid, serve, wait_for

PORT = 4732
DB = db("cold")
EXTERNAL = "/etc/shells"

r = Results(expect=17)
api = Api(PORT)


def marker(t):
    for i, line in enumerate(t.screen.display):
        idx = line.find("▸")
        if idx != -1:
            return (i, idx)
    return None


print("== start a LONG-LIVED server, with no client attached ==", flush=True)
server = serve(PORT, DB)
t = None
try:
    # An API route, not `/app`: `/app` serves the web UI's HTML and `Api` decodes JSON,
    # so probing it raises inside the try and the finally exits before anything runs.
    r.check("headless server answers before any TUI exists",
            api("GET", "/session?scope=project") is not None)
    r.check("the server reports zero sessions to begin with",
            (api("GET", "/session?scope=project") or []) == [])

    # ------------------------------------------------------------ a block with no witness
    print("\n== raise a permission while NOTHING is rendering ==", flush=True)
    box = []
    blocker = api("POST", "/session", {})["id"]
    print(f"  blocker {blocker}", flush=True)
    fire(api, blocker,
         f"Use the read tool on the absolute path {EXTERNAL} and tell me what shells it lists.",
         box=box, label="blocker")

    pending = wait_for(lambda: (api("GET", "/permission") or None), 420, "permission.asked")
    r.check("a permission is pending on the server", bool(pending))
    if not pending:
        raise SystemExit(1)
    request_id = pending[0].get("id")
    r.check("the pending request belongs to the blocker session",
            pending[0].get("sessionID") == blocker, f"request {request_id}")

    # Everything above happened with no TUI in existence. Recorded explicitly because it is
    # the precondition the whole test turns on, and because the previous architecture could
    # not produce it at all.
    blocked_at = time.time()
    r.check("the block predates any client (no TUI process has run yet)", t is None)

    # ------------------------------------------------------------ NOW attach the client
    print("\n== attach the control terminal AFTER the block already exists ==", flush=True)
    t = attach(PORT, DB, cols=120, rows=44, settle=30)
    r.check("the attached client rendered (opencode attach runs the full TUI)", t.alive)
    r.check("negative control: on_grid is FALSE before the grid is opened", not on_grid(t))

    t.send("/healbot", 1.5)
    t.key("enter", 5.0)
    t.show("grid on first paint, against a pre-existing block")
    r.check("the Healbot builtin loads on the attach path", on_grid(t))

    # THE ASSERTION. The live store cannot know about this block; only reconcile() can.
    r.check("COLD RECONCILE — a block that predates the client renders PERMISSION",
            t.exact("PERMISSION"),
            f"block raised {round(time.time() - blocked_at)}s before the client started")
    r.check("the header counts it", t.find("1 blocked"))
    r.check("the session is visible at all (roster came from the server, not the store)",
            t.find("1 session"))

    # ------------------------------------------------------------ answer it from the grid
    # The reconcile carries FULL REQUEST BODIES, not just ids. VERIFY.md:198-200 called that
    # correct-by-source-reading but INFERRED, because it could not be run. Rendering a border
    # needs an id; mounting a prompt needs the request itself. If the panel opens with the
    # real path in it, the bodies survived.
    print("\n== answer the pre-existing block from the grid ==", flush=True)
    t.key("tab", 2.0)
    t.send("a", 3.0)
    t.show("panel opened on a cold block")
    opened = t.find("Permission required") and t.find("Allow once")
    r.check("the prompt mounts from the RECONCILED request body, not just an id", opened)
    r.check("the reconciled body carried the real request detail", t.find("/etc"))
    r.check("the grid is still on screen while answering", on_grid(t))

    if opened:
        t.key("enter", 3.5)
        cleared = wait_for(lambda: api("GET", "/permission") == [], 120, "permission cleared")
        r.check("the reply cleared the block server-side", cleared is not None)
        r.check("the route never changed", on_grid(t))

        wait_for(lambda: any(b[0] == "blocker" for b in box), 420, "blocked turn to finish")
        blob = json.dumps(api("GET", f"/session/{blocker}/message") or [])
        r.check("the answer reached the MODEL, not just the server", "/bin/zsh" in blob,
                "shell listing present in the transcript")
        r.check("the turn ran on the pinned model",
                '"modelID":"gpt-5.6-sol"' in blob.replace(" ", ""), "gpt-5.6-sol")

    # ------------------------------------------------------------ the server outlives it
    print("\n== the fleet survives the control terminal ==", flush=True)
    t.send("q", 2.0)
    r.check("negative control: on_grid is FALSE after leaving the grid", not on_grid(t))
    t.close()
    t = None
    time.sleep(3)
    r.check("the server is STILL serving after the client exited",
            api("GET", "/session?scope=project") is not None)
    survived = api("GET", "/session?scope=project") or []
    r.check("the session survived the client exiting", any(s["id"] == blocker for s in survived),
            f"{len(survived)} session(s) still on the server")
except SystemExit:
    raise
except Exception as exc:
    # Without this the finally's sys.exit swallows the traceback and the run reports
    # "0/0 passed", which reads like a pass. Failures must look like failures.
    import traceback
    traceback.print_exc()
    r.check(f"UNEXPECTED EXCEPTION: {type(exc).__name__}", False, str(exc)[:200])
finally:
    ok = r.summary()
    if t is not None:
        t.close()
    server.terminate()
    try:
        server.wait(timeout=10)
    except Exception:
        server.kill()
    sys.exit(0 if ok else 1)
