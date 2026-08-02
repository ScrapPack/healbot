"""The two behaviours the fleet run did NOT actually exercise, because the blocked cell
happened to already be selected:

  1. auto-surface — a block arriving while the grid is open moves the cursor onto it
  2. tab-jump     — from a NON-blocked cell, tab lands on the blocked one

Both are asserted on the position of the '▸' selection marker, not on cell text.
"""

import json
import os
import sys
import threading
import time
import urllib.request

# Scratch root for the rig's isolated XDG roots, DB and project dir — overridable, disposable.
# term.py lives next to this file (not in the scratch dir, where the original session had it).
S = os.environ.get("HEALBOT_VERIFY_SCRATCH", "/tmp/healbot-legacy-verify")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from term import Term  # noqa: E402

REPO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "opencode")
os.makedirs(f"{S}/hb/project", exist_ok=True)
BASE = "http://127.0.0.1:4605"
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


def marker_col(t):
    """Column of the '▸' selection marker, or None. Cell index = col // cell_width."""
    for line in t.screen.display:
        idx = line.find("▸")
        if idx != -1:
            return idx
    return None


env = {
    "XDG_CONFIG_HOME": f"{S}/hb/config",
    "XDG_DATA_HOME": f"{S}/hb/data",
    "OPENCODE_DB": f"{S}/hb/verify4.db",
    "OPENCODE_DISABLE_CLAUDE_CODE": "1",
    "OPENCODE_DISABLE_EXTERNAL_SKILLS": "1",
}

print("== boot ==")
t = Term(["bun", "run", "--cwd", f"{REPO}/packages/opencode", "--conditions=browser",
          "src/index.ts", f"{S}/hb/project", "--port", "4605"],
         env=env, cwd=f"{S}/hb/project")
t.pump(20)
check("server up", wait_for(lambda: http("GET", "/session?scope=project") is not None, 90, "server") is not None)

try:
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

    # Three quiet sessions first, so the blocked one is NOT index 0.
    quiet = [http("POST", "/session", {})["id"] for _ in range(3)]
    for sid in quiet:
        prompt(sid, "Reply with exactly: OK", {"*": False})
    wait_for(lambda: all(len(http("GET", f"/session/{s}/message") or []) >= 2 for s in quiet), 300, "quiet turns")

    t.send("/healbot", 1.2)
    t.key("enter", 3.0)
    t.show("grid, three quiet sessions")
    start_col = marker_col(t)
    check("grid open with a selection marker", start_col is not None, f"col={start_col}")

    # A NEW session blocks while the grid is open -> auto-surface must move the cursor.
    blocker = http("POST", "/session", {})["id"]
    prompt(blocker, "Use the read tool on the absolute path /etc/hostname and report its contents.")
    pending = wait_for(lambda: http("GET", "/permission") or None, 300, "permission.asked")
    check("new session blocked while grid was open", bool(pending))

    t.pump(4.0)
    t.show("after the block arrived (auto-surface)")
    surfaced_col = marker_col(t)
    check("cursor auto-moved onto the newly blocked cell",
          surfaced_col is not None and surfaced_col != start_col,
          f"marker {start_col} -> {surfaced_col}")

    # Now deliberately move OFF the blocked cell.
    t.key("left", 1.0)
    t.show("moved off the blocked cell")
    off_col = marker_col(t)
    check("cursor moved away from the blocked cell", off_col != surfaced_col,
          f"marker {surfaced_col} -> {off_col}")

    # tab must jump back to it.
    t.key("tab", 1.5)
    t.show("after tab")
    back_col = marker_col(t)
    check("tab jumped back onto the blocked cell", back_col == surfaced_col,
          f"marker {off_col} -> {back_col} (blocked cell at {surfaced_col})")

    t.send("a", 2.5)
    ok = t.find("Allow once")
    check("answer panel opened on the tab-selected cell", ok)
    if ok:
        t.key("enter", 3.0)
        check("cleared", wait_for(lambda: http("GET", "/permission") == [], 90, "cleared") is not None)

finally:
    print("\n== summary ==")
    for name, ok, _ in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [n for n, ok, _ in results if not ok]
    print(f"\n  {len(results) - len(failed)}/{len(results)} passed")
    t.close()
