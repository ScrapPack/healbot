"""Phase 4 step 6, first increment: the retirement OBSERVABLE.

PLAN.md:379-381 wants a session "driven past the retirement threshold". REVIEW.md §4.3 records
that clause as unadjudicable because nothing was configurable — 350K on a frontier model is
expensive to reach on purpose. HEALBOT_RETIRE_AT makes it cheap.

Asserts, in order:
  * occupancy is read from the assistant message's own tokens (occupancy, not lifetime spend)
  * the env override actually reaches the TUI worker, proven by RETIRE firing at a level that
    the 350K default could never have fired at
  * a blocked session that is ALSO over the threshold renders PERMISSION — blocked outranks
    retire — while the header still counts both
  * answering from the grid reverts the cell to RETIRE rather than to done
"""

import json
import time

from rig import Api, Results, boot, db, fire, on_grid, wait_for

PORT = 4718
DB = db("retire")
THRESHOLD = 20_000
DEFAULT = 350_000

r = Results()
api = Api(PORT)


def marker(t):
    for i, line in enumerate(t.screen.display):
        idx = line.find("▸")
        if idx != -1:
            return (i, idx)
    return None


def exact(t, needle):
    """Case-SENSITIVE screen match. Term.find() lowercases, which makes find("RETIRE")
    match the header's "1 to retire" — the two are distinguishable only by case."""
    return needle in t.text()


def occupancy(sid):
    """Ground truth, server-side: the most recent populated assistant token reading.
    Same expression overflow.ts:21-33 uses, cache.read included."""
    best = 0
    for m in api("GET", f"/session/{sid}/message") or []:
        info = m.get("info") or m
        if info.get("role") != "assistant":
            continue
        tok = info.get("tokens") or {}
        cache = tok.get("cache") or {}
        total = tok.get("total") or (
            tok.get("input", 0) + tok.get("output", 0) + cache.get("read", 0) + cache.get("write", 0)
        )
        if total:
            best = total
    return best


print(f"== boot with HEALBOT_RETIRE_AT={THRESHOLD} ==", flush=True)
import os

os.environ["HEALBOT_RETIRE_AT"] = str(THRESHOLD)
t = boot(PORT, DB, cols=120, rows=44)
r.check("fork TUI up", wait_for(lambda: api("GET", "/session?scope=project") is not None, 120, "server") is not None)

try:
    box = []
    # Created FIRST so it lands in the LAST cell: the grid sorts session ids ascending,
    # and ids are DESCENDING identifiers, so ascending order is newest-first.
    grower = api("POST", "/session", {})["id"]
    quiet = [api("POST", "/session", {})["id"] for _ in range(2)]
    for i, sid in enumerate(quiet):
        fire(api, sid, f"Use the read tool on worker{i}.txt and reply with exactly the word it contains.",
             box=box, label=f"quiet{i}")
    fire(api, grower,
         "Read ledger0.txt, ledger1.txt and ledger2.txt in the current project directory, "
         "each with the read tool, then tell me in one sentence what kind of data they hold.",
         box=box, label="grower")

    wait_for(lambda: len(box) == 3, 600, "all three turns")
    grown = occupancy(grower)
    quiet_occ = [occupancy(s) for s in quiet]
    r.check("the grower crossed the configured threshold", grown >= THRESHOLD,
            f"occupancy {grown:,} >= {THRESHOLD:,}")
    r.check("...and is nowhere near the 350K default, so RETIRE can only come from the override",
            grown < DEFAULT, f"{grown:,} < {DEFAULT:,}")
    r.check("the quiet sessions stayed under the threshold", all(o < THRESHOLD for o in quiet_occ),
            f"{[f'{o:,}' for o in quiet_occ]}")

    # ------------------------------------------------------------------ the grid
    print("\n== the grid ==", flush=True)
    t.send("/healbot", 1.2)
    t.key("enter", 4.0)
    t.show("grid, one session over the retirement threshold")
    r.check("grid renders", on_grid(t))
    r.check("the over-threshold cell renders as RETIRE", exact(t, "RETIRE"))
    r.check("the header counts it", t.find("1 to retire"))
    expected = f"{round(grown / THRESHOLD * 100)}%"
    r.check("the cell shows occupancy as a share of the threshold", t.find(expected),
            f"expected {expected} on screen")
    r.check("the env override reached the TUI worker", exact(t, "RETIRE") and grown < DEFAULT,
            "RETIRE at an occupancy the 350K default could not have triggered")

    # ------------------------------------------------------------------ precedence
    print("\n== blocked outranks retire, but the header keeps both ==", flush=True)
    fire(api, grower, "Now use the read tool on the absolute path /etc/shells and report what it lists.",
         box=box, label="grower2")
    pending = wait_for(lambda: (api("GET", "/permission") or None), 420, "permission on the grown session")
    r.check("the over-threshold session is now also blocked", bool(pending))
    t.pump(5.0)
    t.show("over threshold AND blocked")
    r.check("the cell renders PERMISSION, not RETIRE (blocked outranks)",
            exact(t, "PERMISSION") and not exact(t, "RETIRE"))
    r.check("the header still counts the block", t.find("1 blocked"))
    r.check("the header still counts the retirement, despite the precedence collapse",
            t.find("1 to retire"))

    # ------------------------------------------------------------------ answer, then revert
    print("\n== answering reverts the cell to RETIRE, not to done ==", flush=True)
    t.key("tab", 2.0)
    t.send("a", 2.5)
    r.check("answer panel opened on the blocked cell", t.find("Permission required"))
    t.key("enter", 3.0)
    cleared = wait_for(lambda: api("GET", "/permission") == [], 90, "permission cleared")
    r.check("the block cleared server-side", cleared is not None)
    wait_for(lambda: any(b[0] == "grower2" for b in box), 420, "grower turn to finish")
    t.pump(4.0)
    t.show("after answering")
    r.check("the cell reverted to RETIRE rather than done", exact(t, "RETIRE"),
            f"occupancy now {occupancy(grower):,}")
    r.check("still on the control terminal", on_grid(t))
    print(f"\n  final occupancy: grower={occupancy(grower):,}  quiet={[f'{occupancy(s):,}' for s in quiet]}",
          flush=True)
finally:
    r.summary()
    t.close()
