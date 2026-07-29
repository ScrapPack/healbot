"""Exit-gate clause: four sessions concurrent, one deliberately blocked on a permission
prompt and ANSWERED FROM THE GRID without focusing it.

On openai/gpt-5.6-sol via the harness. Nothing is forced: the three working sessions run
real tool-using turns, and the blocked one blocks because `external_directory` defaults to
"ask" (agent/agent.ts:122) and /etc/shells is outside the instance
(tool/external-directory.ts:15-45).

Ordering. Session ids are DESCENDING identifiers (schema/src/session-id.ts:8 ->
identifier.ts:22, `descending ? ~current : current`), so a later creation time yields a
lexicographically SMALLER id and plain ascending sort is already newest-first. The grid used
to sort `b.id.localeCompare(a.id)` under a comment claiming that gave newest-first; it gave
the exact opposite, and this rig compensated by creating the blocker LAST. Both are fixed:
the grid now sorts ascending (genuinely newest-first) and the blocker is created FIRST so it
still lands in the final cell, away from the initial cursor — which is what makes the `tab`
and marker assertions mean anything rather than pass by accident.

Terminal is 120 cols so the 4 cells wrap to 2 rows: with one row, `j`/`k` clamp and the
keyboard-gating assertion would pass vacuously.
"""

import json
import sys
import time

from rig import Api, Results, boot, completed, db, fire, on_grid, wait_for

PORT = 4713
DB = db("perm2")
EXTERNAL = "/etc/shells"

r = Results(expect=35)
api = Api(PORT)


def marker(t):
    """(line, column) of the selection marker. Navigation is asserted on THIS, never on
    cell text — cell text is present regardless of which cell is selected."""
    for i, line in enumerate(t.screen.display):
        idx = line.find("▸")
        if idx != -1:
            return (i, idx)
    return None


def blocked_session(api):
    p = api("GET", "/permission") or []
    return p[0] if p else None


print("== boot ==", flush=True)
t = boot(PORT, DB, cols=120, rows=44)
r.check("fork TUI up", wait_for(lambda: api("GET", "/session?scope=project") is not None, 120, "server") is not None)

try:
    # ---------------------------------------------------------------- four concurrent
    print("\n== four sessions, fired simultaneously ==", flush=True)
    blocker = api("POST", "/session", {})["id"]  # created FIRST -> last cell, newest-first grid
    quiet = [api("POST", "/session", {})["id"] for _ in range(3)]
    for i, s in enumerate(quiet):
        print(f"  worker{i}  {s}", flush=True)
    print(f"  blocker  {blocker}", flush=True)

    box = []
    t0 = time.time()
    for i, sid in enumerate(quiet):
        fire(api, sid,
             f"Use the read tool on the file named worker{i}.txt in the current project "
             f"directory and reply with exactly the word it contains, nothing else.",
             box=box, label=f"worker{i}")
    fire(api, blocker,
         f"Use the read tool on the absolute path {EXTERNAL} and tell me what shells it lists.",
         box=box, label="blocker")

    pending = wait_for(lambda: blocked_session(api), 420, "permission.asked")
    r.check("a session is blocked on a permission", bool(pending),
            f"{pending['permission']} req={pending['id']}" if pending else "none arrived")
    if not pending:
        raise SystemExit(1)
    r.check("the block belongs to the intended session", pending.get("sessionID") == blocker)

    # Gate on ENDED, assert on RAN — see rig.completed(). Before Phase 12 this counted the raw
    # box, which cannot tell a completed turn from a thrown one; the `payload-{i}` rows below are
    # what actually carried this claim, and this row was a restatement of the gate.
    wait_for(lambda: len([b for b in box if b[0].startswith("worker")]) == 3, 420, "3 worker turns")
    elapsed = time.time() - t0
    ended = [b for b in box if b[0].startswith("worker")]
    workers = completed(box, "worker")
    threw = [(n, repr(p)) for n, _, p in ended if isinstance(p, BaseException)]
    r.check("the other three sessions completed while one stayed blocked", len(workers) == 3,
            f"{len(workers)}/3 completed of {len(ended)} ended, wall {elapsed:.1f}s: "
            + ", ".join(f"{n}={d:.1f}s" for n, d, _ in workers) + (f" || THREW: {threw}" if threw else ""))
    r.check("the blocked session is still hanging (blocked one does not stall the others)",
            not any(b[0] == "blocker" for b in box) and api("GET", "/permission") != [])
    for i, sid in enumerate(quiet):
        blob = json.dumps(api("GET", f"/session/{sid}/message") or [])
        r.check(f"worker{i} really ran a tool-using turn", f"payload-{i}" in blob)

    # ---------------------------------------------------------------- the grid
    # NEGATIVE CONTROL, and it is not optional. Every "the route never changed" assertion in
    # this suite rests on `on_grid`, so `on_grid` has to be shown FALSE somewhere before its
    # truth anywhere means anything. The predicate it replaced — `t.find("Healbot")` — was
    # measured True on this very screen, because `Term.find` lowercases and the run's project
    # path contains "healbot". A positive-only screen predicate is indistinguishable from a
    # constant, and this suite already shipped one of those.
    print("\n== negative control: the grid is NOT open yet ==", flush=True)
    r.check("on_grid is FALSE before the grid is opened", not on_grid(t))

    print("\n== open the control terminal ==", flush=True)
    t.send("/healbot", 1.2)
    t.key("enter", 3.5)
    t.show("grid opened, one session blocked")
    r.check("grid route renders", on_grid(t))
    r.check("blocked cell renders as PERMISSION", t.find("PERMISSION"))
    r.check("header counts the block", t.find("1 blocked"))
    r.check("header counts every session", t.find("4 sessions"))
    r.check("answer affordance advertised", t.find("a answer"))

    start = marker(t)
    r.check("a selection marker exists and is NOT on the blocked cell", start is not None,
            f"marker={start}")

    # ---------------------------------------------------------------- inert on unblocked
    print("\n== 'a' is inert on an unblocked cell ==", flush=True)
    t.send("a", 2.0)
    r.check("'a' on an unblocked cell opens no panel", not t.find("Permission required"))
    r.check("...and does not hijack the footer", not t.find("answering ·"))

    # ---------------------------------------------------------------- tab to the block
    print("\n== tab cycles the blocked queue ==", flush=True)
    t.key("tab", 2.0)
    t.show("after tab")
    tabbed = marker(t)
    r.check("tab moved the cursor from an unblocked cell onto the blocked one",
            tabbed is not None and tabbed != start, f"marker {start} -> {tabbed}")

    # ---------------------------------------------------------------- answer in place
    print("\n== answer from the grid ==", flush=True)
    t.send("a", 2.5)
    t.show("after pressing 'a'")
    opened = t.find("Permission required") and t.find("Allow once")
    r.check("the permission prompt mounts INSIDE the grid", opened)
    r.check("the grid is still rendered while answering", on_grid(t) and t.find("4 sessions"))
    r.check("the route never changed (grid still owns the screen)", on_grid(t))
    r.check("footer names escape honestly as destructive", t.find("esc reject"))
    r.check("the prompt is the external-directory one we triggered", t.find("/etc"))
    if not opened:
        raise SystemExit(1)

    # The load-bearing keybinding claim. permission.tsx:568-608 binds h/l/return/escape in
    # OPENCODE_BASE_MODE — the grid's own keys, same mode — so `enabled: !answering()` is
    # the only thing keeping the grid from moving underneath the prompt.
    during = marker(t)
    t.send("j", 1.2)
    after_j = marker(t)
    r.check("grid vertical nav is inert while the prompt owns the keyboard (j)",
            after_j == during, f"marker {during} -> {after_j}")
    t.send("k", 1.2)
    r.check("grid vertical nav is inert while the prompt owns the keyboard (k)",
            marker(t) == during, f"marker {during} -> {marker(t)}")
    # h/l DO collide: the prompt consumes them for option cycling. Sent as a balanced pair
    # so the prompt's own selection returns to keys[0] == "once" (permission.tsx:538).
    t.send("l", 1.2)
    r.check("grid horizontal nav is inert while the prompt owns the keyboard (l)",
            marker(t) == during, f"marker {during} -> {marker(t)}")
    t.send("h", 1.2)
    r.check("grid horizontal nav is inert while the prompt owns the keyboard (h)",
            marker(t) == during, f"marker {during} -> {marker(t)}")
    t.show("after j/k/l/h under the prompt")

    t.key("enter", 3.0)  # selection is back at keys[0] == "once" -> Allow once
    t.show("after answering")
    r.check("answering did not fall through to the 'Allow always' stage",
            not t.find("until OpenCode is restarted"))
    cleared = wait_for(lambda: api("GET", "/permission") == [], 90, "permission cleared")
    r.check("the reply cleared the block server-side", cleared is not None,
            f"GET /permission -> {api('GET', '/permission')}")
    r.check("the cell left the PERMISSION state", not t.find("PERMISSION"))
    r.check("still on the control terminal after answering", on_grid(t))
    r.check("the answer panel collapsed on its own", not t.find("Allow once"))

    # ---------------------------------------------------------------- reached the model
    print("\n== did the answer reach the model, or only clear the block? ==", flush=True)
    # Gate on ENDED, assert on RAN — see rig.completed(). A blocker turn that threw satisfied the
    # old `finished is not None`, which made this row unable to distinguish "the answer reached
    # the model and it resumed" from "the request blew up".
    wait_for(lambda: any(b[0] == "blocker" for b in box), 420, "blocked turn to finish")
    ran = completed(box, "blocker")
    r.check("the previously blocked turn ran to completion", bool(ran),
            f"{[(n, round(d, 1)) for n, d, _ in ran]} completed; "
            f"threw: {[(n, repr(p)) for n, _, p in box if n == 'blocker' and isinstance(p, BaseException)]}")
    msgs = api("GET", f"/session/{blocker}/message") or []
    blob = json.dumps(msgs)
    r.check("the approved tool actually executed (file content is in the transcript)",
            "/bin/zsh" in blob)
    assistants = [m for m in msgs if (m.get("info") or m).get("role") == "assistant"]
    texts = [p.get("text", "") for m in msgs if (m.get("info") or m).get("role") == "assistant"
             for p in (m.get("parts") or []) if p.get("type") == "text"]
    tail = " ".join(texts).lower()
    r.check("the model consumed the tool result and answered in prose",
            any(w in tail for w in ("zsh", "bash", "shell")), f"...{tail[-200:]}")
    r.check("the whole blocked turn stayed on gpt-5.6-sol",
            bool(assistants) and all((m.get("info") or m).get("modelID") == "gpt-5.6-sol" for m in assistants),
            f"{set((m.get('info') or m).get('modelID') for m in assistants)}")

    # ---------------------------------------------------------------- escape is destructive
    print("\n== escape on the panel rejects (there is no back-out key) ==", flush=True)
    esc = api("POST", "/session", {})["id"]
    fire(api, esc, "Use the read tool on the absolute path /etc/paths and report its contents.",
         box=box, label="escape")
    p2 = wait_for(lambda: blocked_session(api), 420, "second permission.asked")
    r.check("a second session blocked", bool(p2))
    if p2:
        t.pump(3.0)
        # It is the only blocked cell; tab lands on it wherever the cursor is.
        t.key("tab", 2.0)
        t.send("a", 2.5)
        r.check("panel reopened for the second block", t.find("Permission required"))
        t.key("escape", 3.0)
        t.show("after escape")
        gone = wait_for(lambda: api("GET", "/permission") == [], 90, "permission cleared by escape")
        r.check("escape cleared the block", gone is not None)
        r.check("escape did NOT leave the grid (still the control terminal)", on_grid(t))
        wait_for(lambda: any(b[0] == "escape" for b in box), 300, "escape turn to end")
        eblob = json.dumps(api("GET", f"/session/{esc}/message") or [])
        r.check("escape REJECTED rather than dismissed (rejection reached the session)",
                "reject" in eblob.lower() or "denied" in eblob.lower() or "/usr/local/bin" not in eblob,
                "no file content in transcript" if "/usr/local/bin" not in eblob else "file WAS read")
    # ------------------------------------------------------- negative control, second half
    # The other end of the same discipline: leaving the grid must make `on_grid` false again.
    # Together with the check before it was ever opened, this shows the predicate tracks the
    # route in BOTH directions — which is the whole claim every route assertion above makes.
    print("\n== negative control: q leaves the grid ==", flush=True)
    t.send("q", 2.5)
    t.show("after leaving the grid")
    r.check("on_grid is FALSE again after closing the grid", not on_grid(t))

    t.show("final screen")
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
