"""The QUESTION half: a session blocks on `question.asked` and is answered FROM THE GRID.

Difference from the voided run, and the whole point of redoing this: the turn is NOT
constrained. No `tools` map, no `{"*": false, "question": true}`. The model is handed a
genuinely undecidable choice and has to reach for `question` on its own.

No permission config is set either. `question` is "deny" in the shared default block
(agent/agent.ts:127) but the `build` agent merges `question: "allow"` on top of it
(agent/agent.ts:141-152), and `flags.client` defaults to "cli" (core/src/flag/flag.ts:75-76),
which is in the registration allowlist (tool/registry.ts:202). So a default build session can
already ask.

QuestionPrompt is the harder keyboard case: it binds tab/h/l/j/k/return/escape AND digits
(question.tsx:227-264) and pushes its own mode (:129-134), so it collides with the grid on
nearly every key.
"""

import json
import sys
import time

from rig import Api, Results, boot, db, fire, on_grid, wait_for

PORT = 4714
DB = db("quest")

# Genuine forks in the road, no mention of any tool. Tried in order until one asks.
ASKS = [
    "Set up a linter for this project and write its config file. It has to be either Biome "
    "or ESLint — my team standardised on one of them and getting it wrong means redoing the "
    "work. Do not write any file until that is settled.",
    "I need a test runner configured here. Vitest or Bun's built-in runner — my CI is already "
    "committed to exactly one of them and I have not told you which. Settle that first, then "
    "write the config.",
]

r = Results(expect=27)
api = Api(PORT)


def marker(t):
    for i, line in enumerate(t.screen.display):
        idx = line.find("▸")
        if idx != -1:
            return (i, idx)
    return None


print("== boot ==", flush=True)
t = boot(PORT, DB, cols=120, rows=44)
r.check("fork TUI up", wait_for(lambda: api("GET", "/session?scope=project") is not None, 120, "server") is not None)

try:
    print("\n== three workers plus one session facing a real fork in the road ==", flush=True)
    quiet = [api("POST", "/session", {})["id"] for _ in range(3)]
    box = []
    for i, sid in enumerate(quiet):
        fire(api, sid,
             f"Use the read tool on worker{i}.txt in the current project directory and reply "
             f"with exactly the word it contains.", box=box, label=f"worker{i}")

    asker, q, attempt = None, None, 0
    for attempt, text in enumerate(ASKS, start=1):
        # Created after the quiet workers, so under the grid's newest-first ordering it
        # lands in cell 0 -- the initial cursor position. This rig therefore asserts the
        # cursor SURFACES onto the block (an event-driven move), not that `tab` reached it.
        asker = api("POST", "/session", {})["id"]
        print(f"  attempt {attempt}: session {asker}", flush=True)
        fire(api, asker, text, box=box, label=f"asker{attempt}")   # NO tools map — unforced
        q = wait_for(lambda: (api("GET", "/question") or None), 300, f"question.asked (attempt {attempt})")
        if q:
            break

    r.check("the model CHOSE to ask a question, unforced", bool(q),
            f"attempt {attempt} of {len(ASKS)}" if q else "never asked in any framing")
    if not q:
        raise SystemExit(1)
    r.check("the question belongs to the asker session", q[0].get("sessionID") == asker)
    print(f"  question: {json.dumps(q[0].get('questions'))[:400]}", flush=True)
    first = (q[0].get("questions") or [{}])[0]
    options = [o.get("label") for o in (first.get("options") or [])]
    chosen = options[0] if options else None
    r.check("the question carries selectable options", bool(options), f"{options}")

    wait_for(lambda: len([b for b in box if b[0].startswith("worker")]) == 3, 300, "worker turns")
    workers = [b for b in box if b[0].startswith("worker")]
    r.check("the other sessions ran to completion alongside the blocked one", len(workers) == 3,
            ", ".join(f"{n}={d:.1f}s" for n, d, _ in workers))

    # ---------------------------------------------------------------- the grid
    print("\n== open the control terminal ==", flush=True)
    t.send("/healbot", 1.2)
    t.key("enter", 3.5)
    t.show("grid with a pending question")
    r.check("grid route renders", on_grid(t))
    r.check("blocked cell renders as QUESTION", t.find("QUESTION"))
    r.check("header counts the block", t.find("1 blocked"))
    start = marker(t)
    r.check("cursor starts off the blocked cell", start is not None, f"marker={start}")

    t.send("a", 2.0)
    r.check("'a' on an unblocked cell opens no panel", not t.find("answering ·"))

    t.key("tab", 2.0)
    tabbed = marker(t)
    r.check("tab moved the cursor onto the blocked cell", tabbed is not None and tabbed != start,
            f"marker {start} -> {tabbed}")

    # ---------------------------------------------------------------- answer in place
    print("\n== answer from the grid ==", flush=True)
    t.send("a", 2.5)
    t.show("question prompt open inside the grid")
    qtext = (first.get("question") or "").strip()
    opened = any(t.find(o) for o in options if o) or (bool(qtext) and t.find(qtext[:24]))
    r.check("the question prompt mounts INSIDE the grid", opened)
    r.check("the grid is still rendered while answering", on_grid(t) and t.find("4 sessions"))
    r.check("the route never changed (grid still owns the screen)", on_grid(t))
    r.check("footer names escape honestly as destructive", t.find("esc reject"))
    if not opened:
        raise SystemExit(1)

    # QuestionPrompt pushes QUESTION_MODE and binds j/k itself. The grid's bindings are
    # OPENCODE_BASE_MODE + enabled:!answering(), so neither should move the grid cursor.
    during = marker(t)
    t.send("j", 1.2)
    r.check("grid nav inert under the question prompt (j)", marker(t) == during,
            f"marker {during} -> {marker(t)}")
    t.send("k", 1.2)
    r.check("grid nav inert under the question prompt (k)", marker(t) == during,
            f"marker {during} -> {marker(t)}")
    t.send("l", 1.2)
    r.check("grid nav inert under the question prompt (l)", marker(t) == during,
            f"marker {during} -> {marker(t)}")
    t.send("h", 1.2)
    r.check("grid nav inert under the question prompt (h)", marker(t) == during,
            f"marker {during} -> {marker(t)}")

    t.send("1", 3.0)  # digit = "Select answer 1"; single question -> picking submits
    t.show("after answering the question")
    cleared = wait_for(lambda: api("GET", "/question") == [], 90, "question cleared")
    r.check("the reply cleared the block server-side", cleared is not None,
            f"GET /question -> {api('GET', '/question')}")
    r.check("the cell left the QUESTION state", not t.find("QUESTION"))
    r.check("still on the control terminal after answering", on_grid(t))
    r.check("the answer panel collapsed on its own", not t.find("esc reject") or not t.find("answering "))

    # ---------------------------------------------------------------- reached the model
    print("\n== did the answer reach the model? ==", flush=True)
    finished = wait_for(lambda: any(b[0].startswith("asker") for b in box), 420, "asker turn to finish")
    r.check("the previously blocked turn ran to completion", finished is not None,
            f"{[(n, round(d, 1)) for n, d, _ in box if n.startswith('asker')]}")
    msgs = api("GET", f"/session/{asker}/message") or []
    blob = json.dumps(msgs)
    r.check("the question tool reported the chosen answer back to the model",
            bool(chosen) and "User has answered your questions" in blob and chosen in blob,
            f"chose {chosen!r}")
    texts = [p.get("text", "") for m in msgs if (m.get("info") or m).get("role") == "assistant"
             for p in (m.get("parts") or []) if p.get("type") == "text"]
    tail = " ".join(texts)
    r.check("the model acted on the answer rather than merely unblocking",
            bool(chosen) and chosen.lower().split()[0] in tail.lower(),
            f"...{tail[-220:]}")
    assistants = [m for m in msgs if (m.get("info") or m).get("role") == "assistant"]
    r.check("the whole asker turn stayed on gpt-5.6-sol",
            bool(assistants) and all((m.get("info") or m).get("modelID") == "gpt-5.6-sol" for m in assistants),
            f"{set((m.get('info') or m).get('modelID') for m in assistants)}")
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
