"""Exit-gate clause: four sessions concurrent, one deliberately blocked on a permission,
answered from the grid without focusing it — and the other three unaffected."""

import json
import os
import sys
import tempfile
import threading
import time
import urllib.request

# Scratch root for the rig's isolated XDG roots, DB and project dir. FRESH per run by
# default: the grid-header assertions count EVERY session in the DB (the single-use rig
# trap, HARNESS.md Traps), so a reused root goes red for reasons unrelated to the code
# under test. Set HEALBOT_VERIFY_SCRATCH to keep or reuse a workspace deliberately.
# term.py lives next to this file, not in the scratch dir.
S = os.environ.get("HEALBOT_VERIFY_SCRATCH") or tempfile.mkdtemp(prefix="healbot-legacy-verify-")
print(f"scratch root: {S}")   # a paid run's DB, logs and project dir land here — name it or lose it
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from term import Term  # noqa: E402

REPO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "opencode")
os.makedirs(f"{S}/hb/project", exist_ok=True)
BASE = "http://127.0.0.1:4603"
results = []


def http(method, path, body=None, timeout=600):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
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
            v = fn()
            if v:
                return v
        except Exception:
            pass
        time.sleep(1.0)
    print(f"  !! timed out waiting for {label} after {timeout}s")
    return None


env = {
    "XDG_CONFIG_HOME": f"{S}/hb/config",
    "XDG_DATA_HOME": f"{S}/hb/data",
    "OPENCODE_DB": f"{S}/hb/verify3.db",
    "OPENCODE_DISABLE_CLAUDE_CODE": "1",
    "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
}

print("== boot ==")
t = Term(["bun", "run", "--cwd", f"{REPO}/packages/opencode", "--conditions=browser",
          "src/index.ts", f"{S}/hb/project", "--port", "4603"],
         env=env, cwd=f"{S}/hb/project")
t.pump(20)
check("server up", wait_for(lambda: http("GET", "/session?scope=project") is not None, 90, "server") is not None)

try:
    ids = [http("POST", "/session", {})["id"] for _ in range(4)]
    print("  sessions:", ", ".join(i[-6:] for i in ids))

    def prompt(sid, text, tools=None):
        def run():
            try:
                body = {"parts": [{"type": "text", "text": text}]}
                if tools:
                    body["tools"] = tools
                http("POST", f"/session/{sid}/message", body)
            except Exception as exc:
                print(f"  (thread {sid[-6:]}: {exc})")
        threading.Thread(target=run, daemon=True).start()

    # One blocks on an external-directory read; three do trivial work.
    prompt(ids[0], "Use the read tool on the absolute path /etc/hostname and report its contents.")
    for sid in ids[1:]:
        prompt(sid, "Reply with exactly: OK", {"*": False})

    pending = wait_for(lambda: http("GET", "/permission") or None, 300, "permission.asked")
    check("one of four sessions is blocked", bool(pending),
          f"{pending[0]['permission']}" if pending else "none")

    t.send("/healbot", 1.2)
    t.key("enter", 3.0)
    t.show("four sessions, one blocked")
    check("grid shows all four sessions", t.find("4 sessions"))
    check("exactly one counted as blocked", t.find("1 blocked"))

    # The blocked cell may not be the selected one: tab must find it.
    blocked_sid = pending[0]["sessionID"]
    for _ in range(5):
        if "PERMISSION" in t.text():
            break
        t.key("tab", 0.8)
    t.key("tab", 1.0)
    t.show("after tab-cycling to the blocked cell")

    t.send("a", 2.5)
    t.show("answering the blocked one, three still live")
    opened = t.find("Allow once")
    check("answered the blocked cell found via tab", opened)
    check("grid still visible", t.find("Healbot"))

    if opened:
        t.key("enter", 3.0)
        cleared = wait_for(lambda: http("GET", "/permission") == [], 90, "cleared")
        check("permission cleared without focusing the session", cleared is not None)
        t.pump(2.0)
        t.show("after answering")
        check("still on the control terminal", t.find("Healbot"))
        check("still showing all four sessions", t.find("4 sessions"))

    # The other three must have completed on their own while one was parked.
    done = 0
    for sid in ids[1:]:
        msgs = http("GET", f"/session/{sid}/message") or []
        if len(msgs) >= 2:
            done += 1
    check("the other three were not stalled by the block", done == 3, f"{done}/3 produced a reply")

finally:
    print("\n== summary ==")
    for name, ok, _ in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n  {len(results) - len(failed)}/{len(results)} passed")
    t.close()
