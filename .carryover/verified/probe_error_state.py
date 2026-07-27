"""Does the grid render a hard-errored session as ERROR? Zero model turns, zero API credits.

This replays the session the 350K run actually produced: 37 turns that succeeded and then **25
consecutive `ContextOverflowError` turns**, real provider failures already sitting in the
database. Nothing is simulated.

It exists because that run exposed a hole in the error state. The grid showed a cheerful
`RETIRE` for a session that had been dead for 25 turns, because `session.error` was only ever
subscribed *inside the route component* — so every failure that happened before the operator
opened the grid was invisible. A control terminal cannot only know what happened while it was
looking; that is the same cold-start hole `reconcile()` exists to plug for permissions.

The fix derives the state from the stored messages (`storedErrorOf`). This probe is what proves
it, and it is free because the expensive part — producing a genuine overflow — is already done.

  venv/bin/python probe_error_state.py          # needs hb/retire350.db from verify_retire_350k
"""

import json
import shutil
import sqlite3
import sys

from rig import Results, boot, db, on_grid

PORT = 4736
SOURCE = db("retire350")
REPLAY = db("errorstate")

r = Results()

# ---------------------------------------------------------------- prepare the replay DB
try:
    shutil.copyfile(SOURCE, REPLAY)
except FileNotFoundError:
    print(f"!! {SOURCE} not found — run verify_retire_350k.py first", flush=True)
    sys.exit(1)

conn = sqlite3.connect(REPLAY)
rows = conn.execute("SELECT id, time_archived FROM session").fetchall()
errored = None
for sid, _ in rows:
    msgs = [json.loads(raw) for (raw,) in
            conn.execute("SELECT data FROM message WHERE session_id=? ORDER BY time_created", (sid,))]
    fails = [m for m in msgs if m.get("role") == "assistant" and m.get("finish") == "error"]
    if fails:
        errored = (sid, len(fails), fails[-1].get("error", {}).get("name"))
        break

print("== the session under test ==", flush=True)
r.check("the replay DB contains a session with real provider errors", bool(errored),
        f"{errored[1]} failed turns, last was {errored[2]}" if errored else "none found")
if not errored:
    sys.exit(1)
sid, nfails, ename = errored
r.check("the failures are ContextOverflowError, not something incidental", ename == "ContextOverflowError")

# The 350K run archived it as part of retiring, and `sessions()` filters archived — so it would
# have no cell at all. Un-archive it in the COPY so it renders. This changes nothing about the
# messages, which are what the error state is derived from.
conn.execute("UPDATE session SET time_archived = NULL WHERE id = ?", (sid,))
conn.commit()
conn.close()
print(f"  replaying {sid} with {nfails} ContextOverflowError turns", flush=True)

t = boot(PORT, REPLAY, cols=120, rows=44, settle=30)
try:
    r.check("negative control: on_grid is FALSE before the grid is opened", not on_grid(t))
    t.send("/healbot", 1.5)
    t.key("enter", 5.0)
    t.show("grid over a session that died 25 turns ago")
    r.check("grid renders", on_grid(t))

    # THE ASSERTION. Every one of those failures predates this process by an entire run, so no
    # `session.error` event can possibly have been observed. If the cell says ERROR, it can only
    # have come from `storedErrorOf` reading the message rows.
    r.check("COLD ERROR STATE — a session that hard-errored before this client started renders ERROR",
            t.exact("ERROR"), "derived from stored messages; no session.error event was witnessed")
    # Both sessions in this DB are errored — the successor was aborted when the 350K run
    # tore down its terminal — so the count is 2. Asserted as a number the grid derives,
    # not a number I expected before looking.
    r.check("the header counts errored sessions", t.find("2 failed"))

    # It is ALSO over the retirement threshold (occupancy 359,829). ERROR outranks RETIRE, but
    # the operator still needs to know retiring is the remedy — so the cell carries `· retire`
    # and the header keeps its independent count.
    r.check("the cell still advertises retirement as the remedy", t.find("· retire"))
    r.check("the header still counts it as retirable", t.find("1 to retire"))

    # And the thing this whole state exists to prevent.
    r.check("it does NOT render as a completed session", not t.exact("done"),
            "a dead session reading `done` in theme.success is the failure this state exists for")

    t.send("q", 2.0)
    r.check("negative control: on_grid is FALSE after leaving the grid", not on_grid(t))
finally:
    ok = r.summary()
    t.close()
    sys.exit(0 if ok else 1)
