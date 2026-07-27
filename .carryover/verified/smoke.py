"""Smoke: does the fork boot from source under the harness, resolve openai/gpt-5.6-sol,
and complete a real turn? Everything downstream is void if this does not hold — that is
exactly the failure the previous run papered over by reaching for a local model."""

import json
import time

from rig import Api, Results, boot, fire, wait_for

PORT = 4711
DB = "/private/tmp/claude-501/-Users-brittonwerdell-Desktop-healbot/ac594553-97c7-4390-a005-9576eb0554eb/scratchpad/hb/smoke.db"

r = Results()
api = Api(PORT)

print("== boot ==", flush=True)
t = boot(PORT, DB)
t.show("tui after boot")

up = wait_for(lambda: api("GET", "/session?scope=project") is not None, 120, "server ready")
r.check("fork TUI boots and serves HTTP", up is not None)

try:
    cfg = api("GET", "/config")
    model = cfg.get("model")
    r.check("harness model pin reaches the server", model == "openai/gpt-5.6-sol", f"config.model={model}")
    r.check(
        "compaction.auto is false (harness)",
        (cfg.get("compaction") or {}).get("auto") is False,
        f"compaction={cfg.get('compaction')}",
    )

    sid = api("POST", "/session", {})["id"]
    print(f"  session {sid}", flush=True)
    box = []
    fire(api, sid, "Reply with exactly: OK", box=box, label="smoke")
    wait_for(lambda: box or None, 300, "turn to finish")

    msgs = api("GET", f"/session/{sid}/message") or []
    assistant = [m for m in msgs if (m.get("info") or m).get("role") == "assistant"]
    used = [(m.get("info") or m).get("modelID") for m in assistant]
    r.check("a real turn completed", len(assistant) > 0, f"{len(assistant)} assistant message(s)")
    r.check(
        "the turn ran on gpt-5.6-sol",
        any(u == "gpt-5.6-sol" for u in used),
        f"modelID={used}",
    )
    prov = [(m.get("info") or m).get("providerID") for m in assistant]
    r.check("provider is openai (native path, not the compatible shim)", any(p == "openai" for p in prov), f"providerID={prov}")
    if box:
        print(f"  turn wall clock: {box[0][1]:.2f}s", flush=True)

    tok = [(m.get("info") or m).get("tokens") for m in assistant]
    print(f"  tokens: {json.dumps(tok)[:400]}", flush=True)
finally:
    r.summary()
    t.close()
