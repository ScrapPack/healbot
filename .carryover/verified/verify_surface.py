"""The behaviours neither earlier run reached, because in both the block PREDATED the grid:

  1. auto-surface — a block arriving while the grid is open moves the cursor onto it
  2. suppression  — it must NOT steal the cursor when you are already sitting on a blocked
     cell (you are probably mid-decision) or while an answer panel is open
  3. tab cycles a queue of MORE THAN ONE blocked session

Everything is asserted on the position of the selection marker, never on cell text.
"""

import sys
import time

from rig import Api, Results, boot, db, fire, on_grid, wait_for

PORT = 4715
DB = db("surf")

r = Results(expect=18)
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
    r.check("grid open", on_grid(t))
    # `not t.find("blocked")` is what stood here, and it was the suite's one recorded failing
    # assertion (17/18) for five phases — a TEST bug, never a code one. The grid's FOOTER is
    # `a answer · x retire · tab next blocked · enter focus · …` (`healbot.tsx:997`), so the
    # substring "blocked" is on screen whenever the grid is open and the predicate was False by
    # construction. Until Phase 10 this rig discarded `summary()`'s verdict and exited 0
    # regardless, which is why a permanently-red assertion could sit here that long.
    #
    # The header is the thing that actually counts blocks, and it is rendered inside
    # `<Show when={blocked() > 0}>` (`healbot.tsx:963`) — VERIFIED at source — so `\d+ blocked`
    # is absent exactly when nothing is blocked. That is the shape `search()` exists for, and
    # `1 blocked` / `2 blocked` / `3 blocked` are what the later legs of this rig assert.
    # `exact()` for the cell label: labels are uppercase, `find()` is case-INSENSITIVE, and it
    # is strictly narrower — if the old `find` half passed, this passes too.
    r.check("nothing is blocked yet", not t.search(r"\d+ blocked") and not t.exact("PERMISSION"))
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
    r.check("the grid is still rendered underneath", on_grid(t))
    r.check("header counts all three blocks", t.find("3 blocked"))

    before = npending(api)
    t.key("enter", 3.0)
    cleared = wait_for(lambda: npending(api) == before - 1, 90, "one block cleared")
    r.check("answering cleared exactly the one block", cleared is not None,
            f"{before} pending -> {npending(api)}")
    r.check("still on the control terminal", on_grid(t))
    t.show("final")
except SystemExit:
    raise
except Exception:
    # Failures must look like failures. `sys.exit()` inside a `finally` DISCARDS the escaping
    # exception, so a rig that crashed still exits on summary()'s verdict over whatever ran
    # first. Backfilled in Phase 10 with the exit-code fix below: the two MUST ship together,
    # because adding sys.exit() to a finally without this guard CREATES that defect.
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    ok = r.summary()
    t.close()
    sys.exit(0 if ok else 1)
