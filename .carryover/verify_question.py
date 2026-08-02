"""QUESTION half of the exit gate: surface a question from a sub-session onto the control
terminal and answer it there.

The first attempt failed on model capability, not code: the local 12B called the instruction
"a trap" and went grepping. Here the turn is constrained via the prompt's `tools` map, which
prompt.ts:1061-1063 turns into per-session permission rules — `{"*": false, "question": true}`
denies every tool and re-allows one, and a blanket `*` deny removes the tool schema outright
(PERMISSION.MAP.md). With `question` the only tool it has, the model has nowhere else to go.
Claude-code and external skills are switched off for the same reason.
"""

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
BASE = "http://127.0.0.1:4601"
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
    "OPENCODE_DB": f"{S}/hb/verify2.db",
    "OPENCODE_DISABLE_CLAUDE_CODE": "1",
    "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
}

print("== boot ==")
t = Term(
    ["bun", "run", "--cwd", f"{REPO}/packages/opencode", "--conditions=browser", "src/index.ts",
     f"{S}/hb/project", "--port", "4601"],
    env=env, cwd=f"{S}/hb/project",
)
t.pump(20)
check("server up", wait_for(lambda: http("GET", "/session?scope=project") is not None, 90, "server") is not None)

try:
    sid = http("POST", "/session", {})["id"]
    print(f"  session {sid}")

    def fire():
        try:
            http("POST", f"/session/{sid}/message", {
                "tools": {"*": False, "question": True},
                "parts": [{"type": "text",
                           "text": "Ask me, using your question tool, which name to use. "
                                   "One question, header 'Name', with exactly two options: "
                                   "alpha and beta."}],
            })
        except Exception as exc:
            print(f"  (prompt thread ended: {exc})")

    threading.Thread(target=fire, daemon=True).start()

    q = wait_for(lambda: http("GET", "/question") or None, 300, "question.asked")
    check("sub-session blocked on a question", bool(q), f"req={q[0]['id']}" if q else "none arrived")
    if not q:
        raise SystemExit(1)
    print(f"  questions: {json.dumps(q[0]['questions'])[:200]}")

    # Open the control terminal AFTER the block exists — this also exercises the path where
    # the grid meets a session that is already waiting.
    t.send("/healbot", 1.2)
    t.key("enter", 2.5)
    t.show("grid with a pending question")
    check("grid route open", t.find("Healbot"))
    check("renders as QUESTION", t.find("QUESTION"))
    check("header counts the block", t.find("1 blocked"))

    t.send("a", 2.5)
    t.show("question prompt open inside the grid")
    opened = t.find("alpha") or t.find("which name")
    check("question prompt renders INSIDE the grid", opened)
    check("grid still visible while answering", t.find("Healbot"))

    if opened:
        t.send("1", 3.0)  # single question -> picking an option submits immediately
        t.show("after answering from the grid")
        cleared = wait_for(lambda: http("GET", "/question") == [], 60, "question cleared")
        check("question cleared server-side", cleared is not None,
              f"GET /question -> {http('GET', '/question')}")
        check("cell left the QUESTION state", not t.find("QUESTION"))
        check("still on the control terminal after answering", t.find("Healbot"))

        # The answer must actually reach the model, not just clear the block.
        time.sleep(6)
        parts = http("GET", f"/session/{sid}/message") or []
        blob = json.dumps(parts)
        check("the chosen answer reached the session", "alpha" in blob,
              "'alpha' present in session messages" if "alpha" in blob else "not found")

finally:
    print("\n== summary ==")
    for name, ok, _ in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n  {len(results) - len(failed)}/{len(results)} passed")
    t.close()
