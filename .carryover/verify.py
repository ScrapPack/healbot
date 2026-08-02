"""Phase 4 exit-gate verification: answer a blocked session FROM THE GRID, without focusing it.

Isolated end to end — scratch XDG_CONFIG_HOME/XDG_DATA_HOME, scratch OPENCODE_DB, scratch
project dir, local Ollama model. The user's real opencode.db is never opened.

Sessions are created and prompted over HTTP against the TUI's own server, which is the real
control-terminal shape: work runs elsewhere, the grid supervises.
"""

import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

# Scratch root for the rig's isolated XDG roots, DB and project dir. FRESH per run by
# default: the grid-header assertions count EVERY session in the DB (the single-use rig
# trap, HARNESS.md Traps), so a reused root goes red for reasons unrelated to the code
# under test. Set HEALBOT_VERIFY_SCRATCH to keep or reuse a workspace deliberately.
# term.py lives next to this file, not in the scratch dir.
S = os.environ.get("HEALBOT_VERIFY_SCRATCH") or tempfile.mkdtemp(prefix="healbot-legacy-verify-")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from term import Term  # noqa: E402

REPO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "opencode")
os.makedirs(f"{S}/hb/project", exist_ok=True)
BASE = "http://127.0.0.1:4599"
results = []


def http(method, path, body=None, timeout=300):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode()
    return json.loads(raw) if raw else None


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return ok


def wait_for(fn, timeout, label):
    end = time.time() + timeout
    while time.time() < end:
        try:
            value = fn()
            if value:
                return value
        except Exception:
            pass
        time.sleep(1.0)
    print(f"  !! timed out waiting for {label} after {timeout}s")
    return None


env = {
    "XDG_CONFIG_HOME": f"{S}/hb/config",
    "XDG_DATA_HOME": f"{S}/hb/data",
    "OPENCODE_DB": f"{S}/hb/verify.db",
}

print("== boot ==")
t = Term(
    ["bun", "run", "--cwd", f"{REPO}/packages/opencode", "--conditions=browser", "src/index.ts",
     f"{S}/hb/project", "--port", "4599"],
    env=env, cwd=f"{S}/hb/project",
)
t.pump(20)

ready = wait_for(lambda: http("GET", "/session?scope=project") is not None, 90, "server ready")
check("server up on :4599", ready is not None)

try:
    # ---------------------------------------------------------------- permission
    print("\n== permission: block a session, answer it from the grid ==")
    session = http("POST", "/session", {})
    sid = session["id"]
    print(f"  session {sid}")

    def fire_permission():
        try:
            http("POST", f"/session/{sid}/message", {
                "parts": [{"type": "text",
                           "text": "Use the read tool on the absolute path /etc/hostname and "
                                   "tell me exactly what it contains. Do not use bash."}],
            })
        except Exception as exc:
            print(f"  (prompt thread ended: {exc})")

    threading.Thread(target=fire_permission, daemon=True).start()

    pending = wait_for(lambda: http("GET", "/permission") or None, 240, "permission.asked")
    check("session blocked on a permission", bool(pending),
          f"{pending[0]['permission']} req={pending[0]['id']}" if pending else "none arrived")
    if not pending:
        raise SystemExit(1)

    # Open the control terminal.
    t.send("/healbot", 1.2)
    t.key("enter", 2.5)
    t.show("grid opened")
    check("grid route is open", t.find("Healbot"))
    check("blocked session renders as PERMISSION", t.find("PERMISSION"))
    check("header counts the block", t.find("1 blocked"))
    check("answer affordance advertised", t.find("a answer"))

    # Put the cursor on the blocked cell, then answer in place.
    t.send("a", 2.0)
    t.show("after pressing 'a'")
    answered_ui = t.find("Allow once")
    check("permission prompt renders INSIDE the grid", answered_ui)
    check("grid still visible while answering (never navigated away)", t.find("Healbot"))

    if answered_ui:
        t.key("enter", 3.0)   # keys[0] == "once" -> Allow once
        t.show("after answering")
        cleared = wait_for(lambda: http("GET", "/permission") == [], 60, "permission cleared")
        check("permission cleared server-side", cleared is not None,
              f"GET /permission -> {http('GET', '/permission')}")
        check("cell left the PERMISSION state", not t.find("PERMISSION"))
        check("still on the control terminal after answering", t.find("Healbot"))

    # ---------------------------------------------------------------- question
    print("\n== question: block a second session, answer it from the grid ==")
    session2 = http("POST", "/session", {})
    sid2 = session2["id"]
    print(f"  session {sid2}")

    def fire_question():
        try:
            http("POST", f"/session/{sid2}/message", {
                "parts": [{"type": "text",
                           "text": "Call the question tool right now. Ask exactly one question: "
                                   "'Which name should I use?' with exactly two options, "
                                   "'alpha' and 'beta'. Do not do anything else first."}],
            })
        except Exception as exc:
            print(f"  (prompt thread ended: {exc})")

    threading.Thread(target=fire_question, daemon=True).start()

    q = wait_for(lambda: http("GET", "/question") or None, 300, "question.asked")
    check("second session blocked on a question", bool(q),
          f"req={q[0]['id']}" if q else "none arrived")

    if q:
        t.pump(2.0)
        t.show("question surfaced on the grid")
        check("blocked session renders as QUESTION", t.find("QUESTION"))
        # tab cycles the blocked queue; then answer in place.
        t.key("tab", 1.5)
        t.send("a", 2.5)
        t.show("question prompt open in the grid")
        opened = t.find("alpha") or t.find("Which name")
        check("question prompt renders INSIDE the grid", opened)
        check("grid still visible while answering", t.find("Healbot"))
        if opened:
            t.send("1", 3.0)  # single question -> picking an option submits
            t.show("after answering the question")
            qcleared = wait_for(lambda: http("GET", "/question") == [], 60, "question cleared")
            check("question cleared server-side", qcleared is not None,
                  f"GET /question -> {http('GET', '/question')}")
            check("cell left the QUESTION state", not t.find("QUESTION"))
            check("still on the control terminal after answering", t.find("Healbot"))

finally:
    print("\n== summary ==")
    for name, ok, detail in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n  {len(results) - len(failed)}/{len(results)} passed")
    t.close()
