"""Shared rig for the Phase 4 redo verification.

Differences from the voided carryover run, all deliberate:

  * The harness is SOURCED, not reconstructed — `zsh -c '. harness/env.sh && exec ...'`.
    That is what pins openai/gpt-5.6-sol and compaction.auto=false.
  * XDG_DATA_HOME is NOT set. Global.Path.data derives from it (core/src/global.ts:11) and
    auth.json lives there (opencode/src/auth/index.ts:10); openai is on oauth, so
    redirecting it strands the credentials. Isolation is the DB only, via an absolute
    OPENCODE_DB, which database.ts:43-46 returns directly.
  * OPENCODE_DISABLE_DEFAULT_PLUGINS is NOT set (those are the provider auth plugins).
"""

import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
from term import Term  # noqa: E402

HEALBOT = "/Users/brittonwerdell/Desktop/healbot"
REPO = f"{HEALBOT}/opencode"
ENVSH = f"{HEALBOT}/harness/env.sh"
PROJECT = f"{SP}/hb/project"


def boot(port, db, cols=170, rows=48, settle=25):
    """TUI from source, harness sourced, DB isolated. The TUI hosts its own server on
    `port` (--port is 'port to listen on'; it cannot attach to an external server)."""
    inner = (
        f". {ENVSH} && exec bun run --cwd {REPO}/packages/opencode --conditions=browser "
        f"src/index.ts {PROJECT} --port {port}"
    )
    t = Term(
        ["/bin/zsh", "-c", inner],
        env={"OPENCODE_DB": db, "OPENCODE_CLIENT": os.environ.get("OPENCODE_CLIENT", "cli")},
        cwd=PROJECT,
        cols=cols,
        rows=rows,
    )
    t.pump(settle)
    return t


class Api:
    def __init__(self, port):
        self.base = f"http://127.0.0.1:{port}"

    def __call__(self, method, path, body=None, timeout=900):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.base + path, data=data, method=method, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
        return json.loads(raw) if raw else None


class Results:
    def __init__(self):
        self.rows = []

    def check(self, name, ok, detail=""):
        self.rows.append((name, bool(ok), detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)
        return bool(ok)

    def summary(self):
        print("\n== summary ==", flush=True)
        for name, ok, detail in self.rows:
            print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   ({detail})" if detail else ""))
        failed = [n for n, ok, _ in self.rows if not ok]
        print(f"\n  {len(self.rows) - len(failed)}/{len(self.rows)} passed", flush=True)
        return not failed


def wait_for(fn, timeout, label, interval=1.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            v = fn()
            if v:
                return v
        except Exception:
            pass
        time.sleep(interval)
    print(f"  !! timed out waiting for {label} after {timeout}s", flush=True)
    return None


def marker_col(t):
    """Column of the '>' selection marker. Navigation is asserted on THIS, not on cell
    text — cell text is present regardless of which cell is selected."""
    for line in t.screen.display:
        idx = line.find("▸")
        if idx != -1:
            return idx
    return None


def fire(api, sid, text, tools=None, box=None, label=""):
    """POST /session/{id}/message blocks until the turn completes, so prompts go on a
    thread. `box` collects (elapsed, result_or_exception)."""

    def run():
        started = time.time()
        try:
            body = {"parts": [{"type": "text", "text": text}]}
            if tools:
                body["tools"] = tools
            out = api("POST", f"/session/{sid}/message", body)
            if box is not None:
                box.append((label or sid, time.time() - started, out))
        except Exception as exc:
            if box is not None:
                box.append((label or sid, time.time() - started, exc))

    th = threading.Thread(target=run, daemon=True)
    th.start()
    return th
