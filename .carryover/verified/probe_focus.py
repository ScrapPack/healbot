"""FOCUS — `enter` on a cell opens that session. Zero model turns, zero API credits.

Build-order step 4, and until now the only step that was written and never run. It is three lines
of code (`healbot.focus` -> `api.route.navigate("session", { sessionID })`), and the Phase 4 exit
gate was explicitly about answering a block WITHOUT focusing — so nothing ever exercised the one
key that leaves the grid. `.carryover/verify_nav.py` was in the void set. An untested three-line
path is still an untested path, and this one is the only way out of the control terminal into a
session.

WHY THIS PROBE IS NOT JUST `not on_grid()`. The session route's fetch can fail
(`routes/session/index.tsx:284-292`), and when it does it toasts `Session not found: <id>` and
navigates to HOME. A naive "the grid header is gone" assertion scores that bounce as success —
the same shape of vacuous pass this suite keeps producing. So focus is asserted POSITIVELY, on
three independent signals, and the bounce is asserted against explicitly.

THE IDENTITY ASSERTION, which is the one that matters. "We are on a session route" is far weaker
than "we are on THE session route for the cell that was selected". The sidebar renders the
session's own id verbatim, so the probe focuses cell 0, asserts cell 0's id is on screen and
cell 1's is NOT, then moves the cursor and repeats with the two swapped. A predicate that matched
whatever session happened to open could not survive being run twice with opposite expectations.

It replays the 350K run's real database — two genuine sessions with real titles, real messages and
real provider errors — so the whole thing is free.

  venv/bin/python probe_focus.py          # needs hb/retire350.db from verify_retire_350k
"""

import os
import shutil
import sqlite3
import sys

from rig import Results, boot, db, marker_col, on_grid, pin_fixture_project

# Rendering test, not a lifecycle test. One replayed session sits at occupancy 359,829, well over
# the 256,000 gate, so with the guard armed the server would retire it out from under these
# assertions. Since Phase 6 the guard lives in the SERVER plugin — but `boot()` starts a TUI that
# hosts its own server in-process, and that server loads the harness config plugins too, so the
# switch is still required here and still reaches it through the environment.
os.environ["HEALBOT_AUTO_RETIRE"] = "0"

PORT = 4152
SOURCE = db("retire350")
REPLAY = db("focus")

# Home-only: the session route passes no `placeholders` to `<Prompt>`, and Prompt returns an
# undefined placeholder for an empty list (`component/prompt/index.tsx:1310-1318`), so this string
# cannot appear there. It is the leg that separates "landed on the session" from "bounced home".
HOME = r"Ask anything\.\.\."
# Session-route-only: the sidebar Context block (`feature-plugins/sidebar/context.tsx:41-44`).
# Grid cells render a bare `NN%` but never the word "used"; home renders no sidebar at all.
# Requires width > 120 (`routes/session/index.tsx:264`) — hence cols=170 below, NOT the 120 the
# navigation rigs use to force cells onto multiple rows.
SESSION = r"\d+% used"

r = Results(expect=24)

try:
    shutil.copyfile(SOURCE, REPLAY)
except FileNotFoundError:
    print(f"!! {SOURCE} not found — run verify_retire_350k.py first", flush=True)
    sys.exit(1)

conn = sqlite3.connect(REPLAY)
# Both were archived by the run that produced them, and `sessions()` filters archived — they would
# have no cells at all. Un-archiving the COPY changes nothing about the messages.
conn.execute("UPDATE session SET time_archived = NULL")
conn.commit()
rows = conn.execute("SELECT id, title FROM session").fetchall()
conn.close()

# Session ids are DESCENDING identifiers (`schema/src/session-id.ts:8` -> `identifier.ts:22`), so
# ascending sort is already newest-first — which is the order the grid renders after the Phase 5
# fix. Deriving cell order here rather than hardcoding it means this probe fails if that ordering
# ever regresses, instead of quietly testing the wrong cell.
ordered = sorted(rows, key=lambda row: row[0])
FIRST, SECOND = ordered[0][0], ordered[1][0]

print("== the sessions under test ==", flush=True)
for i, (sid, title) in enumerate(ordered):
    print(f"  cell {i}: {sid}  {title}", flush=True)

r.check("the replay DB has two distinct sessions to tell apart", len(ordered) == 2 and FIRST != SECOND)

# The grid filters on `session.project_id`, and the fixture directory's project identity comes
# from the nearest enclosing git repo — which in a fresh worktree is the healbot checkout, not
# `hb/project`. Unpinned, the grid is empty and there is no cell to focus. See the docstring.
pin_fixture_project(SOURCE)

t = boot(PORT, REPLAY, cols=170, rows=48, settle=30)
try:
    # ------------------------------------------------------------------ home: all three, negated
    # Establishing what each predicate does on a screen where it must be false. A predicate that
    # has never been shown false is not evidence.
    r.check("home: on_grid is FALSE", not on_grid(t))
    r.check("home: the session-route predicate is FALSE", not t.search(SESSION), "no sidebar on home")
    r.check("home: the home predicate is TRUE", bool(t.search(HOME)), "so it can be used as a bounce detector")

    # ------------------------------------------------------------------ the grid
    t.send("/healbot", 1.5)
    t.key("enter", 5.0)
    r.check("grid: on_grid is TRUE", on_grid(t))
    r.check(
        "grid: the session-route predicate is FALSE",
        not t.search(SESSION),
        "cells render a bare NN% but never the word 'used' — so `% used` really does discriminate",
    )
    r.check("grid: the home predicate is FALSE", not t.search(HOME))
    r.check("grid: neither session id is on screen yet", not t.exact(FIRST) and not t.exact(SECOND))
    grid_marker = marker_col(t)
    r.check("grid: a cell is selected", grid_marker is not None, f"marker at column {grid_marker}")

    # ------------------------------------------------------------------ FOCUS, cell 0
    t.key("enter", 9.0)
    t.show("after `enter` on cell 0")

    r.check("FOCUS: the grid is gone", not on_grid(t))
    r.check(
        "FOCUS: it did NOT bounce to home",
        not t.search(HOME),
        "the session route's fetch failure path toasts and navigates home; a bare `not on_grid` "
        "assertion would score that as success",
    )
    r.check("FOCUS: no 'Session not found'", not t.find("Session not found"))
    r.check("FOCUS: the session route rendered", bool(t.search(SESSION)), "sidebar Context block")

    # THE IDENTITY ASSERTION.
    r.check("FOCUS: the SELECTED session's id is on screen", t.exact(FIRST), FIRST)
    r.check(
        "FOCUS: the other session's id is NOT",
        not t.exact(SECOND),
        "so this is the focused session, not merely a session",
    )

    # ------------------------------------------------------------------ back to the grid
    # There is no keybinding for `healbot.open` anywhere — the command is namespace "palette" with
    # slashName "healbot", so the only routes back are ctrl+p and typing `/healbot`. Worth knowing:
    # `enter` is a one-way door with no partner key, and `returnRoute` cannot help because
    # `adapters.tsx:47-52` drops every param but sessionID on the way in.
    t.send("/healbot", 1.5)
    t.key("enter", 5.0)
    r.check("BACK: `/healbot` returns to the grid", on_grid(t))
    r.check(
        "BACK: the selection survived the round trip",
        marker_col(t) == grid_marker,
        f"{marker_col(t)} vs {grid_marker} — `selected` lives in the plugin closure, not the "
        "component, which is why (healbot.tsx's own comment says so)",
    )

    # ROUND-TRIP STATE. Navigating away unmounts the route and fires every `onCleanup`, which
    # discards the component-local `errors` map. The question is whether the ERROR cells come back,
    # and they do — `storedErrorOf` derives the state from stored messages rather than from having
    # witnessed `session.error`, so it survives an unmount exactly as it survives a cold start.
    # Recorded here because "focusing a session silently clears every ERROR cell" is a plausible
    # reading of the code that turns out to be wrong.
    r.check(
        "BACK: the ERROR cells survived the unmount",
        t.exact("ERROR"),
        "storedErrorOf re-derives from messages; the live `errors` map being lost does not matter",
    )
    r.check("BACK: the header still counts them", t.find("2 failed"))

    # ------------------------------------------------------------------ FOCUS, cell 1
    # The same predicate, run with the opposite expectation. If focus ignored the cursor and always
    # opened the same session, everything above would still be green and this would fail.
    t.key("right", 1.5)
    r.check("the cursor moved to the second cell", marker_col(t) != grid_marker, f"marker now {marker_col(t)}")
    t.key("enter", 9.0)
    t.show("after `enter` on cell 1")

    r.check("FOCUS 2: the session route rendered", bool(t.search(SESSION)) and not on_grid(t))
    r.check("FOCUS 2: it did NOT bounce to home", not t.search(HOME))
    r.check("FOCUS 2: now the SECOND session's id is on screen", t.exact(SECOND), SECOND)
    r.check(
        "FOCUS 2: and the first one's is NOT — focus follows the cursor",
        not t.exact(FIRST),
        "the two assertions are the same predicate with opposite expectations, so neither can be "
        "a tautology",
    )
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
    t.close()
    sys.exit(0 if ok else 1)
