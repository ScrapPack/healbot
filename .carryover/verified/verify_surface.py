"""The behaviours neither earlier run reached, because in both the block PREDATED the grid:

  1. auto-surface — a block arriving while the grid is open moves the cursor onto it
  2. suppression  — it must NOT steal the cursor when you are already sitting on a blocked
     cell (you are probably mid-decision) or while an answer panel is open
  3. tab cycles a queue of MORE THAN ONE blocked session

Everything is asserted on the position of the selection marker, never on cell text.
"""

import time

from rig import Api, Results, boot, fire, wait_for

PORT = 4715
SP = "/private/tmp/claude-501/-Users-brittonwerdell-Desktop-healbot/ac594553-97c7-4390-a005-9576eb0554eb/scratchpad"
DB = f"{SP}/hb/surf.db"

r = Results()
api = Api(PORT)


def marker(t):
    for i, line in enumerate(t.screen.display):
        idx = line.find("▸")
        if idx != -1:
            return (i, idx)
    return None


def npending(api):
    return len(api("GET", "/permission") or [])


print("== boot ==", flush=True)
t = boot(PORT, DB, cols=120, rows=44)
r.check("fork TUI up", wait_for(lambda: api("GET", "/session?scope=project") is not None, 120, "server") is not None)

try:
    box = []
    quiet = [api("POST", "/session", {})["id"] for _ in range(3)]
    for i, sid in enumerate(quiet):
        fire(api, sid, f"Use the read tool on worker{i}.txt in the current project directory "
                       f"and reply with exactly the word it contains.", box=box, label=f"worker{i}")
    wait_for(lambda: len(box) == 3, 300, "three quiet turns")

    print("\n== grid opened BEFORE any block exists ==", flush=True)
    t.send("/healbot", 1.2)
    t.key("enter", 3.5)
    t.show("grid, three idle sessions, nothing blocked")
    r.check("grid open", t.find("Healbot"))
    r.check("nothing is blocked yet", not t.find("blocked") and not t.find("PERMISSION"))
    start = marker(t)
    r.check("initial cursor position recorded", start is not None, f"marker={start}")

    # ------------------------------------------------------------------ auto-surface
    print("\n== a block arrives while the grid is open ==", flush=True)
    b1 = api("POST", "/session", {})["id"]
    fire(api, b1, "Use the read tool on the absolute path /etc/shells and report its contents.",
         box=box, label="b1")
    wait_for(lambda: npending(api) >= 1, 420, "first permission.asked")
    t.pump(5.0)
    t.show("after the block arrived")
    surfaced = marker(t)
    r.check("the cursor auto-moved onto the newly blocked cell",
            surfaced is not None and surfaced != start, f"marker {start} -> {surfaced}")
    r.check("header now counts one block", t.find("1 blocked"))
    r.check("the newly blocked cell renders as PERMISSION", t.find("PERMISSION"))

    # ------------------------------------------------------------------ suppression: on a block
    print("\n== a SECOND block arrives while the cursor already sits on a blocked cell ==", flush=True)
    b2 = api("POST", "/session", {})["id"]
    fire(api, b2, "Use the read tool on the absolute path /etc/paths and report its contents.",
         box=box, label="b2")
    wait_for(lambda: npending(api) >= 2, 420, "second permission.asked")
    t.pump(5.0)
    t.show("after the second block")
    held = marker(t)
    r.check("the cursor did NOT move off the cell you were deciding on", held == surfaced,
            f"marker {surfaced} -> {held}")
    r.check("header counts both blocks instead", t.find("2 blocked"))

    # ------------------------------------------------------------------ tab cycles a queue
    print("\n== tab cycles a queue of two ==", flush=True)
    t.key("tab", 2.0)
    other = marker(t)
    r.check("tab moved to the OTHER blocked cell", other is not None and other != held,
            f"marker {held} -> {other}")
    t.key("tab", 2.0)
    wrapped = marker(t)
    r.check("tab again wrapped back to the first", wrapped == held,
            f"marker {other} -> {wrapped}")

    # ------------------------------------------------------------------ suppression: answering
    print("\n== a THIRD block arrives while an answer panel is open ==", flush=True)
    t.send("a", 2.5)
    r.check("answer panel opened", t.find("Permission required"))
    answering_at = marker(t)
    b3 = api("POST", "/session", {})["id"]
    fire(api, b3, "Use the read tool on the absolute path /etc/services and report the first line.",
         box=box, label="b3")
    wait_for(lambda: npending(api) >= 3, 420, "third permission.asked")
    t.pump(5.0)
    t.show("third block arrived while answering")
    r.check("the cursor did NOT move while the answer panel was open",
            marker(t) == answering_at, f"marker {answering_at} -> {marker(t)}")
    r.check("the answer panel is still the one you opened", t.find("Permission required"))
    r.check("the grid is still rendered underneath", t.find("Healbot"))
    r.check("header counts all three blocks", t.find("3 blocked"))

    before = npending(api)
    t.key("enter", 3.0)
    cleared = wait_for(lambda: npending(api) == before - 1, 90, "one block cleared")
    r.check("answering cleared exactly the one block", cleared is not None,
            f"{before} pending -> {npending(api)}")
    r.check("still on the control terminal", t.find("Healbot"))
    t.show("final")
finally:
    r.summary()
    t.close()
