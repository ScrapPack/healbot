"""Does `harness/fleet.sh` — the shipped deliverable — actually do what it claims?

Zero model turns, zero API credits. `verify_cold.py` proves the serve+attach ARCHITECTURE;
this proves the SCRIPT an operator actually runs, which is a different artifact and the one
that ships.

Three claims, and the second is the whole reason the script exists:

  1. it starts a server and attaches a control terminal that has the grid
  2. closing the control terminal does NOT take the server down
  3. running it again REUSES that server rather than starting a second one

  venv/bin/python probe_fleet.py
"""

import os
import subprocess
import sys
import time

from rig import Api, PROJECT, Results, fixtures, on_grid, wait_for
from term import Term

HEALBOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FLEET = f"{HEALBOT}/harness/fleet.sh"
PORT = 4734

r = Results(expect=10)
api = Api(PORT, PROJECT)


def running():
    out = subprocess.run(["pgrep", "-f", f"serve --port {PORT}"], capture_output=True, text=True)
    return [p for p in out.stdout.split() if p]


fixtures()
for pid in running():  # a leftover from an aborted run would make claim 3 pass vacuously
    subprocess.run(["kill", pid])
time.sleep(1)

t1 = t2 = None
try:
    r.check("no server is running on the port to begin with", not running(),
            "otherwise 'reuse' would pass for the wrong reason")

    # ---------------------------------------------------------------- first invocation
    print("== fleet.sh, first invocation ==", flush=True)
    t1 = Term(["/bin/zsh", "-c", f"exec {FLEET} {PROJECT} {PORT}"], cwd=PROJECT, cols=120, rows=44)
    t1.pump(45)
    t1.show("fleet.sh, first run")
    # Asserted on the PROCESS TABLE, not on the screen. fleet.sh does echo "starting server",
    # but the TUI it hands off to clears the screen a second later, so a screen assertion here
    # measures render timing rather than behaviour — and it failed for exactly that reason on
    # the first run of this probe.
    r.check("the server came up", wait_for(lambda: api("GET", "/session?scope=project") is not None, 60,
                                           "server") is not None)
    r.check("exactly one server process", len(running()) == 1, f"{len(running())} pid(s)")

    r.check("negative control: on_grid is FALSE before the grid is opened", not on_grid(t1))
    t1.send("/healbot", 1.5)
    t1.key("enter", 4.0)
    t1.show("grid over the fleet")
    r.check("the control terminal has the Healbot grid", on_grid(t1))

    # ---------------------------------------------------------------- the fleet survives
    print("\n== close the control terminal ==", flush=True)
    t1.send("q", 1.5)
    r.check("negative control: on_grid is FALSE after leaving the grid", not on_grid(t1))
    t1.close()
    t1 = None
    time.sleep(4)
    r.check("THE SERVER SURVIVES the control terminal closing", bool(running()),
            "this is the entire point of the fleet architecture")
    r.check("...and is still answering", api("GET", "/session?scope=project") is not None)
    before = running()

    # ---------------------------------------------------------------- reattach, not restart
    print("\n== fleet.sh again: reattach, do not restart ==", flush=True)
    t2 = Term(["/bin/zsh", "-c", f"exec {FLEET} {PROJECT} {PORT}"], cwd=PROJECT, cols=120, rows=44)
    t2.pump(35)
    t2.show("fleet.sh, second run")
    # PID IDENTITY is the assertion, not the "reusing the server" line fleet.sh prints — the
    # TUI clears that off the screen within a second or two. Same pid before and after means
    # the second invocation attached to the first server; a restart would show a new one.
    r.check("fleet.sh REUSES the running server rather than starting a second",
            bool(before) and running() == before, f"{before} -> {running()}")
    t2.send("/healbot", 1.5)
    t2.key("enter", 4.0)
    r.check("the reattached terminal has the grid too", on_grid(t2))
except SystemExit:
    raise
except Exception:
    # Failures must look like failures. `sys.exit()` inside a `finally` DISCARDS the escaping
    # exception, so a probe that crashed still exits on summary()'s verdict over whatever ran
    # first. probe_request_channel.py:151 named this and guarded against it; it was never
    # backfilled. Phase 9 backfilled it, after a fresh clone crashed seven probes into green
    # exit codes — see Results(expect=...) in rig.py for the other half of the fix.
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    ok = r.summary()
    for t in (t1, t2):
        if t is not None:
            t.close()
    for pid in running():
        subprocess.run(["kill", pid])
    sys.exit(0 if ok else 1)
