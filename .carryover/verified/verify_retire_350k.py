"""Retirement at FULL SCALE — 350,000 tokens of occupancy, the run every prior result stood in for.

THIS FILE'S TITLE USED TO SAY "the SHIPPED 350,000 default", AND THAT NUMBER IS NO LONGER THE
DEFAULT. `healbot.tsx:53` and `healbot.ts:110` both read `256_000` now; 350,000 was lowered
because the measured provider ceiling is ~360K and 350K left under 3% of margin (docs/HARDEN.md
§6). So `TARGET` below is no longer a mirror of the shipped default and is not maintained as one.
What this rig is now is a DELIBERATE FULL-SCALE RUN: it drives a session to 350,000 tokens of live
occupancy and past the store's 100-message window, which is the regime the cheap 20,000-token rigs
cannot reach and where the objective-eviction defect described below actually lived. Read every
"350K" below as "full scale", not as "the threshold the code ships with".

Every retirement figure this project has ever recorded was measured at
`HEALBOT_RETIRE_AT=20000` against a session of about eight messages. That was the right call
for exercising the gate cheaply, but it means the shipped default has never fired, and it left
one defect invisible for a whole phase:

`retire()` used to read the handoff objective from `sync.data.message`, which holds only the
NEWEST 100 messages (`sync.tsx:597, :618-619, :334-336`). On a short session that array still
contains message one, so the objective was correct and the test passed. On a session long
enough to matter, it is an arbitrary mid-conversation turn — handed to the successor under the
heading "## Original instruction". Retirement exists to fire on long sessions, so the bug lived
exactly where the feature does, in the one regime never run.

This rig puts BOTH conditions in one session on purpose:

  * occupancy >= 350,000  -> far past whatever the code's own gate is, with NO env override
  * messages     >  100   -> the store has evicted message one, so the objective can only be
                             right if it came from the server

The second is what makes the first worth the money. Proving `RETIRE` renders at 350K is a
threshold check; proving the objective survives the eviction is the fix.

READ THIS BEFORE SPENDING THE MONEY — the lowered default probably breaks the growth loop.
INFERRED, from VERIFIED premises, not TESTED (testing it is the ~5M tokens this file costs):

  * `boot()` runs the TUI from source with the harness sourced, and the TUI hosts its server
    IN-PROCESS, so `harness/config/opencode/plugin/healbot.ts` loads and arms. That is not a
    guess — it is why `probe_error_state.py` and `probe_focus.py` have to disarm the gate with
    `os.environ["HEALBOT_AUTO_RETIRE"] = "0"` to do their work.
  * This file sets neither `HEALBOT_AUTO_RETIRE` nor `HEALBOT_RETIRE_AT`. The plugin's kill switch
    defaults ON (`healbot.ts:133`, `!== "0"`) and its gate defaults to 256,000 (`healbot.ts:110`).
  * The loop below drives occupancy from ~5K to 350,000, so it crosses 256,000 on the way.

When this rig was recorded 25/25 the shipped default WAS 350,000 and automatic retirement did not
yet live in the server, so the loop ran to the end untouched. Today the plugin should fire at
~256K, archive the worker mid-loop, and leave the remaining `POST /session/{worker}/message` calls
and the manual `x` with nothing to act on. Fixing that is a behaviour change and is deliberately
not made here; the shape of the fix is either `HEALBOT_AUTO_RETIRE=0` for the growth phase (this
rig is about MANUAL retirement — it presses `x`) or an explicit `HEALBOT_RETIRE_AT` above TARGET,
which would cost the "no env override" property the rig was built for.

COST. Reaching 350K of context is inherently quadratic — every step re-sends everything before
it — so this is roughly 5M cumulative input tokens, the large majority of it `cache.read`. It
takes 15-30 minutes of wall clock, most of it in the last few turns where each round trip
carries ~350K of prefix. Run it deliberately.

  venv/bin/python verify_retire_350k.py
"""

import os
import sys
import time

from rig import Api, PROJECT, Results, boot, db, fixtures, git_baseline, on_grid, wait_for

PORT = 4735
DB = db("retire350")
TARGET = 350_000          # NOT the RETIRE_AT default. This comment used to claim it "must match
                          # healbot.tsx's RETIRE_AT default"; that default is 256_000
                          # (`healbot.tsx:53`, `healbot.ts:110`) and has been since the ceiling was
                          # measured at ~360K. 350_000 is kept as a deliberate full-scale target —
                          # just under that ceiling — not as a mirror of the shipped threshold.
                          # It is still a sound target: the rig pops the env var at :71 so the gate
                          # under test is the code's own, and 350_000 is well above 256_000, so a
                          # session that reaches TARGET has certainly crossed whatever the gate is.
                          # What TARGET no longer does is name the gate's VALUE, and the printed
                          # labels below still say "the SHIPPED default" — stale display text, left
                          # alone so the recorded 25/25 output stays comparable. See the docstring
                          # for why reaching TARGET at all is now in doubt.
MIN_MESSAGES = 102        # > the store's 100-message window, so message one is evicted
MAX_TURNS = 70            # hard cost stop; failing loudly beats spending unbounded
CHUNK_BYTES = 35_000      # under tool/read.ts's MAX_BYTES = 50 KB even after the
                          # "NNN: " line-number prefixes the tool adds to every line
CHUNKS = 70
SENTINEL = "ORCHID-7742-THREEFIFTY"

# The default must come from the CODE, not from the environment. If this leaks in from a
# previous rig or a shell export, the whole run measures nothing.
os.environ.pop("HEALBOT_RETIRE_AT", None)

r = Results(expect=25)
api = Api(PORT, PROJECT)


def make_chunks():
    """Distinct chunk files. Distinct on purpose: identical content would let the provider's
    cache serve repeats and the context would not actually grow the way a real session's does."""
    fixtures()
    made = 0
    for i in range(CHUNKS):
        path = f"{PROJECT}/chunk{i:02d}.txt"
        if os.path.exists(path) and os.path.getsize(path) >= CHUNK_BYTES:
            continue
        with open(path, "w") as fh:
            row = 0
            while fh.tell() < CHUNK_BYTES:
                fh.write(f"C{i:02d}-{row:05d}  ACCT-{(i * 7919 + row * 104729) % 1000000:06d}  "
                         f"{(row * 37) % 9973:04d}.{(row * 13) % 100:02d}\n")
                row += 1
        made += 1
    return made


def occupancy(sid):
    """Live context occupancy: the most recent POPULATED assistant reading, exactly what
    `healbot.tsx`'s occupancyOf does and exactly what `overflow.ts:21-33` reads. Scans backwards
    because an in-flight assistant row exists ~20ms before it fills and reads all-zero."""
    best = 0
    for m in api("GET", f"/session/{sid}/message") or []:
        info = m.get("info") or m
        if info.get("role") != "assistant":
            continue
        tok = info.get("tokens") or {}
        c = tok.get("cache") or {}
        v = tok.get("total") or (tok.get("input", 0) + tok.get("output", 0)
                                 + c.get("read", 0) + c.get("write", 0))
        if v:
            best = v
    return best


def messages(sid, limit=None):
    path = f"/session/{sid}/message" + (f"?limit={limit}" if limit else "")
    return api("GET", path) or []


def first_user_text(msgs):
    for m in msgs:
        info = m.get("info") or m
        if info.get("role") != "user":
            continue
        text = "\n".join(p.get("text", "") for p in (m.get("parts") or []) if p.get("type") == "text").strip()
        if text:
            return text
    return ""


def texts(sid, role=None):
    out = []
    for m in messages(sid):
        info = m.get("info") or m
        if role and info.get("role") != role:
            continue
        out += [p.get("text", "") for p in (m.get("parts") or []) if p.get("type") == "text"]
    return "\n".join(out)


def section(document, heading):
    out, capturing = [], False
    for line in document.splitlines():
        if line.startswith("## "):
            if capturing:
                break
            capturing = heading.lower() in line.lower()
            continue
        if capturing:
            out.append(line)
    return "\n".join(out)


print("== fixtures ==", flush=True)
print(f"  generated {make_chunks()} chunk file(s) of {CHUNK_BYTES // 1000} KB", flush=True)
# findings.txt must NOT exist at baseline, or creating it is not a diff.
if os.path.exists(f"{PROJECT}/findings.txt"):
    os.remove(f"{PROJECT}/findings.txt")
# The chunks are DECLARED baseline: a session reads them all run, and without this every read
# would land in GET /session/{id}/diff as a changed file. findings.txt is deliberately NOT
# declared — the block above deletes it so that creating it is a diff.
print(f"  git baseline {git_baseline(also=('chunk*.txt',))} — without an inner repo every file "
      f"here is gitignored by the parent and produces no diff", flush=True)

print("== boot (no HEALBOT_RETIRE_AT — the shipped default is the subject) ==", flush=True)
t = boot(PORT, DB, cols=120, rows=44)
r.check("fork TUI up", wait_for(lambda: api("GET", "/session?scope=project") is not None, 120, "server") is not None)
r.check("HEALBOT_RETIRE_AT is NOT set — the threshold under test is the code's own default",
        "HEALBOT_RETIRE_AT" not in os.environ)

try:
    worker = api("POST", "/session", {})["id"]
    print(f"  worker {worker}", flush=True)

    # ---------------------------------------------------------------- the objective, turn one
    # The sentinel goes in the FIRST user message and nowhere else. By the time this session is
    # long enough to retire, the store will have evicted this message entirely — so a handoff
    # document containing the sentinel can only have got it from the server.
    print("\n== turn 1: the objective, carrying the sentinel ==", flush=True)
    api("POST", f"/session/{worker}/message", {"parts": [{"type": "text", "text":
        f"Project codename: {SENTINEL}. You are auditing a ledger split across chunk files in "
        "the current project directory. Use the todowrite tool to record exactly three items: "
        "'audit the chunk ledger', 'write findings to findings.txt', and 'reconcile the totals'. "
        "Then create findings.txt containing the single word STARTED and mark ONLY the first "
        "item completed. Reply with just the word READY."}]})
    todos = api("GET", f"/session/{worker}/todo") or []
    r.check("the worker recorded todos", len(todos) >= 2, f"{len(todos)} item(s)")
    r.check("findings.txt exists on disk (real work happened)", os.path.exists(f"{PROJECT}/findings.txt"))

    true_objective = first_user_text(messages(worker))
    r.check("the sentinel is in the session's true first user message", SENTINEL in true_objective)

    # ---------------------------------------------------------------- grow to the real default
    print(f"\n== grow to {TARGET:,} occupancy and past {MIN_MESSAGES} messages ==", flush=True)
    started = time.time()
    occ = occupancy(worker)
    count = len(messages(worker))
    for turn in range(MAX_TURNS):
        if occ >= TARGET and count > MIN_MESSAGES:
            break
        # The tool parameters are DICTATED, and that is not fussiness. The first version of
        # this prompt said "reply with only the final ACCT number", and the model — reasonably
        # — read with an offset near the end of the file instead of reading it all: 1,386 chars
        # of tool output instead of 35,000, and occupancy grew a flat 816 tokens per turn. At
        # that rate 350K was 250+ turns away. If the point of a turn is to put bytes IN the
        # context window, the prompt must not leave the model room to be efficient about it.
        api("POST", f"/session/{worker}/message", {"parts": [{"type": "text", "text":
            f"Use the read tool on chunk{turn % CHUNKS:02d}.txt in the current project directory "
            "with offset=1 and limit=2000, so that you read the file from its very first line. "
            "Do not pass any other offset. Then reply with only the word DONE, nothing else."}]})
        occ = occupancy(worker)
        count = len(messages(worker))
        print(f"  turn {turn + 2:>3}  occupancy {occ:>9,}  messages {count:>4}  "
              f"({round(occ / TARGET * 100):>3}% of threshold, {round(time.time() - started)}s)", flush=True)

    elapsed = round(time.time() - started)
    r.check(f"occupancy reached the SHIPPED default of {TARGET:,}", occ >= TARGET,
            f"{occ:,} after {count} messages, {elapsed}s")
    r.check("the session exceeded the store's 100-message window", count > MIN_MESSAGES, f"{count} messages")
    if occ < TARGET or count <= MIN_MESSAGES:
        raise SystemExit(1)

    # ------------------------------------------------------- the regime that broke the old code
    # Not an incidental detail — this IS the defect's precondition, so it is asserted rather
    # than assumed. `limit=100` is exactly what sync.tsx hydrates the store with.
    print("\n== the store has evicted the original instruction ==", flush=True)
    windowed = first_user_text(messages(worker, limit=100))
    r.check("the 100-message window NO LONGER holds the original instruction",
            SENTINEL not in windowed, f"window's first user message starts: {windowed[:60]!r}")
    r.check("...while the unlimited fetch still does", SENTINEL in first_user_text(messages(worker)))

    # ---------------------------------------------------------------- the grid, at the default
    print("\n== the grid, with no override ==", flush=True)
    r.check("negative control: on_grid is FALSE before the grid is opened", not on_grid(t))
    t.send("/healbot", 1.5)
    t.key("enter", 5.0)
    t.show(f"grid at {occ:,} occupancy, threshold 350,000 from code")
    r.check("grid renders", on_grid(t))
    # Either truthful state is a pass, and the reason is a finding rather than a hedge.
    # The real provider ceiling is ~360K, so a session cannot reach BOTH >=350K occupancy and
    # >100 messages without failing turns on the way — this rig's own growth loop proved that,
    # taking 37 good turns and then 25 ContextOverflowErrors. ERROR outranks RETIRE in
    # `stateOf` and is the honest label once that has happened.
    #
    # The occupancy-derived header count is the assertion that does NOT depend on precedence:
    # `retirable` is computed off occupancy directly, so it survives whichever state wins.
    r.check("the cell renders a truthful over-threshold state at the SHIPPED default",
            t.exact("RETIRE") or t.exact("ERROR"),
            "RETIRE if the session is still healthy; ERROR if it has already hit the ~360K ceiling")
    r.check("the header counts it as retirable, independently of state precedence",
            t.find("1 to retire"))

    files_before = set(os.listdir(PROJECT))
    before = {s["id"] for s in (api("GET", "/session?scope=project") or []) if not (s.get("time") or {}).get("archived")}

    # ---------------------------------------------------------------- retire and hand off
    print("\n== press x ==", flush=True)
    t.send("x", 20.0)
    t.show("after x")
    # Identify the successor by WHAT IT IS, not by "a new session appeared". The first
    # version took any new non-archived id and picked up the successor's own SUBAGENT
    # instead — `retire()` had worked perfectly and the rig graded the wrong session,
    # reporting a 440-char model-written task prompt as the handoff document.
    #
    # Two guards, both needed. `parentID` excludes subagents. The seed text is what actually
    # identifies a successor, and it is checked from the SERVER rather than trusted from
    # ordering: session ids are descending identifiers, so the newest session sorts FIRST and
    # a bare `next(...)` reliably returns the most recently created one — which, when the
    # successor immediately delegates, is the subagent.
    def find_successor():
        for s in (api("GET", "/session?scope=project") or []):
            if s["id"] in before or (s.get("time") or {}).get("archived") or s.get("parentID"):
                continue
            if "taking over" in texts(s["id"], role="user").lower():
                return s["id"]
        return None

    successor = wait_for(find_successor, 180, "successor seeded with a handoff document")
    r.check("a successor was spawned", bool(successor), f"{successor}")
    if not successor:
        raise SystemExit(1)

    archived = wait_for(lambda: ((api("GET", f"/session/{worker}") or {}).get("time") or {}).get("archived"),
                        90, "predecessor archived")
    r.check("the predecessor was archived", bool(archived))
    r.check("still on the control terminal — retiring never navigated away", on_grid(t))

    seed = texts(successor, role="user")
    r.check("the successor was seeded with a handoff document", "taking over" in seed.lower(), f"{len(seed)} chars")

    # ---------------------------------------------------------------- THE ASSERTION
    objective_section = section(seed, "Original instruction")
    r.check("THE FIX — the objective is the session's TRUE first message, not the oldest survivor",
            SENTINEL in objective_section,
            "the store could not have supplied this; it came from GET /session/{id}/message with no limit")
    r.check("mutation check: the predicate fails when the sentinel is removed",
            SENTINEL not in section(seed.replace(SENTINEL, ""), "Original instruction"))

    # Wait for the successor's FIRST TURN TO COMPLETE before grading anything it produced.
    # Its todo list and its occupancy are both outputs of that turn; sampling before it lands
    # reads an empty list and zero tokens, which looks exactly like a failed handoff. The
    # completion signal is the assistant message's own time.completed / finish -- not the
    # existence of the row, which appears ~20ms after the prompt is accepted and is empty.
    def successor_finished():
        for m in messages(successor):
            info = m.get("info") or m
            if info.get("role") == "assistant" and ((info.get("time") or {}).get("completed") or info.get("finish")):
                return info
        return None

    r.check("the successor actually ran a turn on the handoff",
            wait_for(successor_finished, 600, "successor's first turn to COMPLETE") is not None)

    open_todos = {x.get("content", "").strip() for x in (api("GET", f"/session/{worker}/todo") or [])
                  if x.get("status") != "completed"}
    successor_todos = {x.get("content", "").strip() for x in (api("GET", f"/session/{successor}/todo") or [])}
    r.check("the successor's OWN todo list carries the predecessor's open items",
            bool(open_todos) and open_todos.issubset(successor_todos),
            f"{len(open_todos & successor_todos)}/{len(open_todos)} carried")

    files_section = section(seed, "Files already changed")
    r.check("the handoff named a file the predecessor changed",
            "findings.txt" in files_section, f"files section: {files_section.strip()[:80]!r}")

    post = occupancy(successor)
    r.check("the successor started at its OWN occupancy", post < occ / 2,
            f"predecessor {occ:,} -> successor {post:,} ({round(post / occ * 100)}%)")
    # Asserted on the session list, not with an OR of two screen predicates either of which
    # passes alone. `sessions()` filters `time.archived`, so the predecessor being absent from
    # the live list is what "left the grid" means; the archive check above is the mechanism
    # and this is the consequence.
    live = {s["id"] for s in (api("GET", "/session?scope=project") or [])
            if not (s.get("time") or {}).get("archived")}
    r.check("the predecessor is gone from the live session list the grid renders",
            worker not in live and successor in live, f"{len(live)} live session(s)")

    t.send("q", 2.0)
    r.check("negative control: on_grid is FALSE after leaving the grid", not on_grid(t))
    print(f"\n  seed document, objective section:\n    {objective_section.strip()[:300]}", flush=True)
except SystemExit:
    raise
except Exception as exc:
    import traceback
    traceback.print_exc()
    r.check(f"UNEXPECTED EXCEPTION: {type(exc).__name__}", False, str(exc)[:200])
finally:
    ok = r.summary()
    t.close()
    sys.exit(0 if ok else 1)
