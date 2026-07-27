"""REVIEW.md §6 item 6: diagnose `prompt_async` before building the spawn path on it.

The audit recorded it as a live defect — "accepts a prompt and executes nothing. The user
message is stored; no assistant turn follows, no error is logged." PLAN.md:335 and :341 build
Phase 4's spawn-and-seed on it, and step 5's control agent too.

Source reading points the other way: handlers/session.ts:311-328 calls the SAME
promptSvc.prompt() as the synchronous handler, wrapped in Effect.forkIn(scope,
{startImmediately: true}), and `scope` is bound at :62 inside the HttpApiBuilder.group()
construction generator — the layer scope, which outlives any single request.

Completion is polled on the assistant message's own `time.completed` / non-empty text, NOT on
the row existing: prompt_async creates the assistant row within ~10ms of the ack, so "a row
exists" is true long before the turn has run and races anyone who checks it.
"""

import json
import threading
import time
import urllib.request

from rig import Api, Results, boot, wait_for

PORT = 4717
SP = "/private/tmp/claude-501/-Users-brittonwerdell-Desktop-healbot/ac594553-97c7-4390-a005-9576eb0554eb/scratchpad"
DB = f"{SP}/hb/async2.db"

r = Results()
api = Api(PORT)
events = []


def watch_events():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/event", timeout=900) as stream:
            for raw in stream:
                line = raw.decode(errors="replace").strip()
                if line.startswith("data:"):
                    try:
                        events.append(json.loads(line[5:].strip()))
                    except Exception:
                        pass
    except Exception:
        pass


def msgs(sid):
    return api("GET", f"/session/{sid}/message") or []


def assistants(sid):
    return [m for m in msgs(sid) if (m.get("info") or m).get("role") == "assistant"]


def text_of(sid):
    return " ".join(
        p.get("text", "")
        for m in msgs(sid) if (m.get("info") or m).get("role") == "assistant"
        for p in (m.get("parts") or []) if p.get("type") == "text"
    ).strip()


def completed(sid):
    """A finished assistant turn: the message carries time.completed, or has real text."""
    for m in assistants(sid):
        info = m.get("info") or m
        if ((info.get("time") or {}).get("completed")) or info.get("finish"):
            return info
    return None


print("== boot ==", flush=True)
t = boot(PORT, DB, cols=120, rows=44)
r.check("fork TUI up", wait_for(lambda: api("GET", "/session?scope=project") is not None, 120, "server") is not None)
threading.Thread(target=watch_events, daemon=True).start()
time.sleep(1.0)

PROMPT = "Reply with exactly the word: PONG"

try:
    # ------------------------------------------------------------------ control: sync
    print("\n== control: the synchronous path ==", flush=True)
    sync_id = api("POST", "/session", {})["id"]
    t0 = time.time()
    api("POST", f"/session/{sync_id}/message", {"parts": [{"type": "text", "text": PROMPT}]})
    sync_wall = time.time() - t0
    r.check("POST /message produced a completed assistant turn", bool(completed(sync_id)),
            f"{sync_wall:.1f}s, text={text_of(sync_id)!r}")

    # ------------------------------------------------------------------ subject: async
    print("\n== subject: prompt_async ==", flush=True)
    aid = api("POST", "/session", {})["id"]
    t1 = time.time()
    resp = api("POST", f"/session/{aid}/prompt_async", {"parts": [{"type": "text", "text": PROMPT}]})
    ack = time.time() - t1
    r.check("prompt_async acks immediately without blocking on the turn",
            ack < max(2.0, sync_wall / 2), f"acked in {ack:.2f}s vs sync {sync_wall:.1f}s; body={resp!r}")

    row_fast = wait_for(lambda: assistants(aid) or None, 30, "assistant row")
    r.check("an assistant row appears within ~ms of the ack", bool(row_fast),
            f"row present {time.time() - t1:.2f}s after ack, text so far={text_of(aid)!r}")

    fin = wait_for(lambda: completed(aid), 240, "async turn to COMPLETE")
    total = time.time() - t1
    r.check("prompt_async ACTUALLY EXECUTES the turn to completion", bool(fin),
            f"completed {total:.1f}s after ack, finish={(fin or {}).get('finish')!r}"
            if fin else "never completed in 240s — the audit's defect reproduces")
    r.check("the async turn produced the same answer as the sync control",
            "PONG" in text_of(aid).upper(), f"{text_of(aid)!r}")
    if fin:
        r.check("the async turn ran on gpt-5.6-sol", fin.get("modelID") == "gpt-5.6-sol",
                f"modelID={fin.get('modelID')!r} providerID={fin.get('providerID')!r}")
        r.check("the async turn accrued tokens like any other",
                bool((fin.get("tokens") or {}).get("input")), json.dumps(fin.get("tokens")))

    errs = [e for e in events if aid in json.dumps(e) and "error" in json.dumps(e).lower()]
    r.check("no Session.Event.Error was published for the async session", not errs,
            f"{len(errs)} error event(s): {json.dumps(errs)[:200]}" if errs else "clean")

    # ------------------------------------------------------------------ the seed shape
    print("\n== the shape step 6 needs: spawn a fresh session and seed it, non-blocking ==", flush=True)
    seeded = api("POST", "/session", {})["id"]
    t2 = time.time()
    api("POST", f"/session/{seeded}/prompt_async", {
        "parts": [{"type": "text", "text":
                   "You are taking over work in progress. Reply with exactly: HANDOFF-ACK"}]})
    seed_ack = time.time() - t2
    sfin = wait_for(lambda: completed(seeded), 240, "seeded turn to complete")
    r.check("a freshly spawned session can be seeded via prompt_async and it runs", bool(sfin),
            f"ack {seed_ack:.2f}s, completed {time.time() - t2:.1f}s, reply={text_of(seeded)!r}")
    if sfin:
        occupancy = (sfin.get("tokens") or {})
        r.check("the seeded session starts at its OWN occupancy, not a parent's",
                occupancy.get("input", 0) < 20000,
                f"first-turn occupancy total={occupancy.get('total')} input={occupancy.get('input')}")

    print(f"\n  event types seen: {sorted(set(e.get('type', '?') for e in events))}", flush=True)
finally:
    r.summary()
    t.close()
