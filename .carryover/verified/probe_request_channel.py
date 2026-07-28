"""Does `x` actually reach the server? — FREE, real server, NO model turn.

Phase 7 closed the double-retire race by deleting the grid's own `retire()`. `x` now writes
`metadata: {healbot: {retireRequested: <ms>}}` and the server plugin — the only implementation
left — performs the retirement. `probe_twin.py` asserts that coupling by comparing literals on
both sides, which catches a rename but proves nothing about whether the channel carries anything.

This probe carries something through it, end to end, for free.

WHY IT IS FREE, and this is the part worth understanding rather than trusting. `retire()` branches
at `open.length === 0`: a session with nothing outstanding is archived with NO successor, because
spawning one would burn a fresh window to say "there is no work". A session created over HTTP and
never prompted has no todos, so it takes that branch — which means the whole channel (metadata
write -> `session.updated` -> plugin event hook -> `considerRequest` -> `retire`) can be exercised
with no provider call at all. The half this does NOT cover is the handoff itself; that is
`verify_headless_retire.py`'s 20/20, and it runs the SAME `retire()` from the gate path.

WHAT MAKES THE PASS MEAN SOMETHING. Three independent signals, because "the session ended up
archived" alone would also be true if this script archived it:

  1. The plugin's own log line `request: retiring <id> on the operator's mark`. Only the plugin
     writes it, and this script never PATCHes `time.archived` — it only ever writes metadata.
  2. The archive itself, read back from the server.
  3. A NEGATIVE CONTROL in the same run: a second session is created and left alone, and must
     still be live at the end. Without it, "the session is archived" is compatible with a plugin
     that archives everything it sees.

And one ordering assertion: the marker is written while the session is LIVE, so a pass cannot be
explained by the session having been archived beforehand.

NOTE the kill switch is deliberately OFF-neutral here: `HEALBOT_AUTO_RETIRE=0` disables the
automatic gate only, and the request path is checked BEFORE that flag in the plugin's event hook,
because an operator who wants retirement to be deliberate still wants `x` to work. This probe sets
it to 0 for exactly that reason — it proves the request path is independent of the gate, and it
stops an unrelated occupancy crossing from confusing the result.

  venv/bin/python probe_request_channel.py
"""

import os
import sys
import time

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)

from rig import PROJECT, Api, Results, db, fixtures, git_baseline, serve, wait_for  # noqa: E402

PORT = 4747
DB = db("reqchan")
LOG = f"{SP}/hb/request-channel.log"

r = Results(expect=9)
api = Api(PORT, PROJECT)
server = None


def server_log():
    if not os.path.exists(LOG):
        return ""
    with open(LOG, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def session(sid):
    return api("GET", f"/session/{sid}")


def archived(sid):
    return bool((session(sid).get("time") or {}).get("archived"))


fixtures()
git_baseline()

try:
    print("== a headless server, gate DISABLED, control path live ==", flush=True)
    server = serve(
        PORT,
        DB,
        log=LOG,
        # Gate off on purpose. If this probe passes with the automatic gate disabled, the
        # retirement it observed cannot have come from an occupancy crossing.
        env_extra={"HEALBOT_AUTO_RETIRE": "0"},
    )
    time.sleep(2)
    r.check(
        "the gate is DISABLED for this run",
        "retirement gate DISABLED" in server_log(),
        "so nothing here can be explained by an occupancy crossing",
    )

    target = api("POST", "/session", {})["id"]
    control = api("POST", "/session", {})["id"]
    print(f"  target {target}  control {control}", flush=True)

    # Ordering matters: assert LIVE before writing the marker, or "archived at the end" could be
    # true of a session that was never live in the first place.
    r.check("the target session starts LIVE", not archived(target), target)
    r.check("the control session starts LIVE", not archived(control), control)

    log_before = server_log()
    r.check(
        "the plugin has not mentioned the target yet",
        target not in log_before,
        "baseline, so the log line below cannot be pre-existing",
    )

    # THE ONE CALL THE GRID MAKES. Nothing else in this file writes to the target — in particular
    # it never PATCHes `time.archived`, which is what makes the archive below attributable.
    print("== writing the marker the grid's `x` writes ==", flush=True)
    api("PATCH", f"/session/{target}", {"metadata": {"healbot": {"retireRequested": int(time.time() * 1000)}}})

    ok_archived = wait_for(lambda: archived(target), 60, "target archived by the plugin")
    r.check(
        "the metadata write caused the SERVER to retire the session",
        ok_archived,
        "metadata -> session.updated -> plugin event hook -> considerRequest -> retire",
    )
    r.check(
        "the plugin says so in its own log — a line only it writes",
        f"request: retiring {target}" in server_log(),
        "independent of the archive; this script never writes time.archived",
    )
    r.check(
        "…and it reported the no-successor branch, which is the correct one for an empty session",
        "nothing outstanding, no successor spawned" in server_log(),
        "a successor here would mean burning a fresh window to say there is no work",
    )

    # NEGATIVE CONTROL. Without this, every assertion above is also satisfied by a plugin that
    # archives every session it hears about.
    r.check(
        "the UNMARKED control session is still LIVE",
        not archived(control),
        "only the session that carried the marker was retired",
    )

    # The marker is deliberately left in place rather than cleared, and the archived check inside
    # `considerRequest` is what stops the republished `session.updated` from looping. Assert the
    # loop did not happen: exactly one retirement line for this session.
    r.check(
        "the request fired EXACTLY once — archiving republishes session.updated and must not loop",
        server_log().count(f"request: retiring {target}") == 1,
        f"count={server_log().count(f'request: retiring {target}')}",
    )

except SystemExit:
    raise
except Exception:
    # Failures must look like failures. `sys.exit()` in a `finally` swallows an escaping
    # exception and the rig reports a green summary of whatever happened to run first —
    # see verify_cold.py, where this guard was written.
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    if server:
        server.terminate()
        try:
            server.wait(timeout=10)
        except Exception:
            server.kill()
    ok = r.summary()
    sys.exit(0 if ok else 1)
