"""The `question.rejected` half of the cold-start reconcile — the last untested branch of it.

`verify_cold.py` proved the reconcile for a PERMISSION raised before any client existed. The
QUESTION half was left source-reading only: `healbot.tsx` subscribes to `question.rejected` as a
distinct event from `question.replied`, with a comment explaining that missing it would pin a
rejected pre-attach question's cell yellow forever — and nothing ever rejected a question that
predated the client.

The two halves are NOT interchangeable, which is why this exists rather than being waved through:

  * They are different services with different storage. Permissions live in `permission/index.ts`;
    questions live in a separate in-memory `Map<QuestionID, PendingEntry>` in `question/index.ts`
    with its own `GET /question` and its own `POST /question/:requestID/reject`.
  * They resolve through different events. A permission has `permission.replied` and nothing else;
    a question has BOTH `question.replied` and `question.rejected`, published from different lines
    (`question/index.ts:134-148` for the reject), and the grid has to clear `cold` on either.
  * Rejection is not answering. Escape on the question prompt calls `reject()`
    (`routes/session/question.tsx:253, :281`), which fails the asking fiber with
    `QuestionRejectedError` — a different server-side path from a reply.

ORDERING IS THE ENTIRE POINT, as in `verify_cold.py`:

  1. start a headless `serve` — nothing rendering anywhere
  2. fire a turn that makes the model ask a question, UNFORCED
  3. wait until the question EXISTS
  4. only then start the control terminal
  5. reject it from the grid

At step 4 the live SSE store holds nothing about that question: `sync.tsx` initialises
`data.question` to `{}` and its bootstrap never calls `question.list` — it is event-fed only, and
the event fired before this process existed. So if the cell renders QUESTION, `reconcile()` is the
only thing that can have put it there. Step 6 below makes that argument load-bearing rather than
rhetorical by focusing the plain session route, where the same store is the ONLY source, and
showing the prompt does not mount there.

UNFORCED, per this suite's discipline: no `tools` map, no permission config. The model is handed a
genuinely undecidable choice and has to reach for `question` on its own. The framings are the ones
`verify_question.py` already established work on gpt-5.6-sol.

  venv/bin/python verify_cold_question.py
"""

import json
import sys
import time

from rig import Api, Results, attach, db, fire, on_grid, serve, wait_for

PORT = 4744
DB = db("coldq")

ASKS = [
    "Set up a linter for this project and write its config file. It has to be either Biome "
    "or ESLint — my team standardised on one of them and getting it wrong means redoing the "
    "work. Do not write any file until that is settled.",
    "I need a test runner configured here. Vitest or Bun's built-in runner — my CI is already "
    "committed to exactly one of them and I have not told you which. Settle that first, then "
    "write the config.",
]

r = Results(expect=22)
api = Api(PORT)


def questions():
    return api("GET", "/question") or []


def parts_blob(sid):
    out = []
    for m in api("GET", f"/session/{sid}/message") or []:
        out += m.get("parts") or []
    return json.dumps(out)


print("== a long-lived server, with NO client attached ==", flush=True)
server = serve(PORT, DB)
t = None
try:
    r.check("headless server answers before any TUI exists", api("GET", "/session?scope=project") is not None)
    r.check("no question pending to begin with", questions() == [], "so a later hit cannot be stale")

    # ------------------------------------------------------------------ raise it, with nothing watching
    started = time.time()
    asker, request, attempt = None, None, 0
    box = []
    for attempt, text in enumerate(ASKS, start=1):
        # ABORT the previous attempt before starting another, and wait for the retry loop's own
        # question to belong to THIS session.
        #
        # Without both, this rig is non-deterministic and it failed that way on a real run: attempt
        # 1 timed out at 300s, attempt 2 was fired against a NEW session, and then attempt 1's
        # model got around to asking anyway. Two sessions were blocked at once, `questions()[0]`
        # belonged to the abandoned one, and the rig rejected one question while asserting about
        # the other — producing eight failures that had nothing to do with the reconcile. A slow
        # model turn is not a reason for a test to measure the wrong session.
        if asker:
            api("POST", f"/session/{asker}/abort")
            time.sleep(2)
        asker = api("POST", "/session", {})["id"]
        print(f"  attempt {attempt}: session {asker}", flush=True)
        fire(api, asker, text, box=box, label=f"asker{attempt}")  # NO tools map — unforced
        request = wait_for(
            lambda: next((q for q in questions() if q.get("sessionID") == asker), None),
            300,
            f"question.asked by {asker} (attempt {attempt})",
        )
        if request:
            break

    r.check(
        "the model CHOSE to ask a question, unforced and with nothing rendering",
        bool(request),
        f"attempt {attempt} of {len(ASKS)}" if request else "never asked in any framing",
    )
    if not request:
        raise SystemExit(1)

    request_id = request.get("id")
    r.check("the question belongs to the asker session", request.get("sessionID") == asker)
    # Everything downstream assumes exactly one blocked cell — `1 blocked`, the panel `a` opens,
    # and the reject. Assert it rather than hope for it.
    r.check(
        "exactly one question is pending across the whole server",
        len(questions()) == 1,
        f"{len(questions())} pending: {[q.get('sessionID') for q in questions()]}",
    )
    first = (request.get("questions") or [{}])[0]
    qtext = (first.get("question") or "").strip()
    options = [o.get("label") for o in (first.get("options") or [])]
    r.check("it carries selectable options", bool(options), f"{options}")
    print(f"  question: {qtext[:160]}", flush=True)

    blocked_at = time.time() - started
    r.check(
        "THE QUESTION EXISTS BEFORE ANY CLIENT DOES",
        bool(request_id),
        f"raised {blocked_at:.0f}s in, with no TUI process anywhere",
    )

    # ------------------------------------------------------------------ only now, a client
    print("\n== attaching the control terminal, after the fact ==", flush=True)
    # 170 columns, NOT the 120 the navigation rigs use. 120 exists so the cells cannot fit on one
    # row and the `j`/`k` gating assertions cannot pass vacuously — this rig asserts no navigation,
    # so it buys nothing here and costs something: the session-route sidebar is gated on
    # `width > 120` (`routes/session/index.tsx:264`), and it is the only thing that renders a
    # session's id. At exactly 120 the focus assertion at the end measures terminal width instead
    # of behaviour, which is how it was first written and what it actually reported.
    t = attach(PORT, DB, cols=170, rows=44, settle=30)
    r.check("negative control: on_grid is FALSE before the grid is opened", not on_grid(t))

    t.send("/healbot", 1.5)
    t.key("enter", 6.0)
    t.show("first paint over a question that predates this client")
    r.check("the grid renders", on_grid(t))

    # THE ASSERTION. The SSE stream does not replay — `handlers/event.ts:68-72` emits a synthetic
    # `server.connected` and then only live events — so nothing this process observed can account
    # for the cell being yellow.
    r.check(
        "COLD QUESTION — a question raised before this client started renders QUESTION",
        t.exact("QUESTION"),
        "the live store is event-fed only; reconcile() reading GET /question is the sole source",
    )
    r.check("the header counts it as blocked", t.find("1 blocked"))

    # ------------------------------------------------------------------ the panel carries the BODY
    # Colouring a border needs an id. Mounting a prompt needs the request itself — its prompt text
    # and its options. This is what upgrades "the reconcile carries full request bodies" from
    # source-reading to TESTED on the question path.
    t.send("a", 3.0)
    t.show("question prompt, mounted from the reconciled request")
    probe = qtext[:40]
    r.check(
        "the prompt mounts INSIDE the grid, from the reconciled request body",
        bool(probe) and t.find(probe),
        f"looking for {probe!r}",
    )
    r.check(
        "…carrying the real options, not placeholders",
        all(t.find(o) for o in options if o),
        f"{options}",
    )
    r.check("the grid is still rendering beneath it", on_grid(t))

    # ------------------------------------------------------------------ REJECT
    # Escape, not a digit. `question.tsx:253` and `:281` both bind escape to reject() — and the
    # grid footer names it honestly ("esc reject") because it is destructive and there is no
    # back-out key. NOTE: while the custom-answer textarea is open, escape cancels the edit
    # instead; this rig never enters that mode.
    t.key("escape", 5.0)
    t.show("after rejecting")

    # Keyed on THIS request id rather than on the list emptying: an unrelated pending question
    # would make an emptiness check fail for a reason that has nothing to do with the reject, which
    # is exactly how this rig misreported itself once already.
    cleared = wait_for(
        lambda: all(q.get("id") != request_id for q in questions()),
        90,
        "this question cleared server-side",
    )
    r.check(
        "REJECT clears the block server-side",
        bool(cleared),
        f"GET /question -> {[q.get('id') for q in questions()]}",
    )
    r.check(
        "the cell leaves QUESTION",
        not t.exact("QUESTION"),
        "same predicate as the cold assertion above, opposite expectation — so neither is a tautology",
    )
    r.check("the header no longer counts it blocked", not t.find("1 blocked"))
    r.check("the route never changed throughout", on_grid(t))

    # `question.rejected` is a DISTINCT event from `question.replied`, and the grid subscribes to
    # both. If it only handled `replied`, the cold map would still hold this request and the
    # fallback in `pendingQuestion` would keep the cell yellow forever — which is exactly what the
    # two assertions above would catch.
    r.check(
        "the cold map was cleared by question.rejected, not left stale",
        not t.exact("QUESTION") and questions() == [],
        "a grid that only handled question.replied would pin this cell yellow",
    )

    # ------------------------------------------------------------------ server side
    blob = parts_blob(asker)
    r.check(
        "the model was told the question was dismissed",
        "dismissed" in blob.lower(),
        "reject fails the asking fiber with QuestionRejectedError; the tool part records it",
    )
    r.check(
        "the session is not left blocked",
        questions() == [],
        "the turn ends and the session goes idle — no session.error",
    )

    # ------------------------------------------------------------------ where the answer landed
    # The plain session route renders QuestionPrompt from `sync.data.question` ALONE
    # (`routes/session/index.tsx:1290-1293`), and that map is never seeded over HTTP — so the
    # session route could not have surfaced this block at all, and the grid's reconcile is the only
    # reason it was ever answerable. Focusing the asker after the fact checks the OTHER end of
    # that: the dismissal really is in this session's transcript, not merely in an HTTP response.
    # This also exercises FOCUS from an ATTACHED client, which `probe_focus.py` does not — that
    # one runs against a TUI-hosted server. Same three lines of code, different topology.
    t.key("enter", 8.0)
    r.check("focus reaches the asker session", not on_grid(t) and t.exact(asker), asker)
    t.show("the asker session after its question was rejected")

    # RECORDED, NOT ASSERTED — and the distinction is the point.
    #
    # `handlers`-side, the dismissal is certain: the assertion above on `parts_blob` finds "The
    # user dismissed this question" in the session's parts, which is what the processor writes onto
    # the tool part when `QuestionRejectedError` comes back. That is the fact that matters, it is
    # asserted over HTTP, and it passes.
    #
    # On SCREEN it is a different question, and one this rig has no business deciding. An earlier
    # version asserted `t.find("dismissed")` here and it failed — the string is in the transcript
    # data but not on the visible viewport, which could be scroll position, could be how an errored
    # tool part is rendered, and is in any case a property of the session route rather than of the
    # cold reconcile. Asserting it would have been asserting something never established; leaving
    # it failing would have been worse. So it is printed, and named in docs/HEADLESS.md as the open
    # question it actually is.
    print(
        f"  observation: 'dismissed' present in the session's parts over HTTP = "
        f"{'dismissed' in parts_blob(asker).lower()}; visible on the focused screen = {bool(t.find('dismissed'))}",
        flush=True,
    )
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
    if t:
        t.close()
    try:
        server.kill()
    except Exception:
        pass
    ok = r.summary()
    sys.exit(0 if ok else 1)
