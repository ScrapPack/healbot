"""Does `on_grid` actually track the route? Zero model turns, zero API credits.

This is the check that was never run for the predicate it replaces. `t.find("Healbot")` was
the basis of nine "the route never changed" assertions across five rigs, and it is True on
every screen in this project because `Term.find` lowercases and the rig's own project path
contains "healbot". A screen predicate is worthless until it has been shown FALSE somewhere.

  venv/bin/python probe_on_grid.py
"""

import sys

from rig import Results, boot, db, on_grid

PORT = 4731
DB = db("probe_on_grid")

r = Results()
t = boot(PORT, DB, cols=120, rows=40, settle=30)
try:
    t.show("home (nothing opened yet)")
    home = on_grid(t)
    old_home = t.find("Healbot")
    r.check("on_grid is FALSE on the home screen", not home)
    r.check("the OLD predicate t.find('Healbot') is TRUE on the same screen — the collision, shown",
            old_home, "this is why the route assertions could not fail")

    t.send("/healbot", 1.2)
    t.key("enter", 4.0)
    t.show("grid open")
    r.check("on_grid is TRUE on the grid", on_grid(t))

    t.send("q", 3.0)
    t.show("after q")
    r.check("on_grid is FALSE again after leaving the grid", not on_grid(t))
finally:
    ok = r.summary()
    t.close()
    sys.exit(0 if ok else 1)
