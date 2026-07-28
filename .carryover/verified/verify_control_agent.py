"""The control agent — build-order step 5, the last non-optional unbuilt step.

`PLAN.md:378`: "Control agent. Its own session in the same server, with tools to spawn / prompt /
abort / retire the others (POST /session, /prompt_async, /abort). Same registry you see."

This rig asserts, as a PAIR, that the same instruction sent to two different agents produces
opposite tool calls:

  * Under `agent: "control"` the healbot tools must be present and used.
  * Under the default `build` agent they must be ABSENT — not merely refused, absent, removed from
    the request payload before the model ever sees them.

The second bullet is the one that matters for this project's founding purpose. Tool definitions are
the largest single block of standing context (11 shipped tools measure 19,898 B), so five more left
global would be rent every session pays forever for a capability one agent uses. The scoping is a
global `healbot_*: deny` plus an `allow` in the control agent's own frontmatter, and it works
because `Permission.disabled` (`permission/index.ts:204-215`) removes a tool exactly when the LAST
matching rule is `pattern: "*"` with `action: "deny"`, while the agent's permission is merged last
(`agent/agent.ts:293`).

WHAT ACTUALLY NEEDS THE MODEL TURN, AND WHAT DOES NOT. The bullets above used to be introduced as
"the two things that cannot be established without a model turn", and that half-sentence was
queueing paid work needlessly. The DISABLED SET is free and deterministic: `opencode debug agent
<name>` prints it, via a `resolveTools` (`cli/cmd/debug/agent.handler.ts:88-98`) that calls the
same `Permission.disabled` over the same merged ruleset, with the session-creating branch gated
behind `if (toolID)` (`:43-58`), so without `--tool` there is no session and no provider call.
TESTED under this harness with an isolated `OPENCODE_DB`: `debug agent build` reports all five
`healbot_*` **false**, `debug agent control` all five **true**, 0 sessions in the DB afterwards.

The caveat, and it is why the free check does not replace this file: `agent.handler.ts` is a
SEPARATE function calling the same predicate, not the request path. The request path
(`session/llm/request.ts:208-214`) additionally merges session-level permission into the ruleset
and filters on `input.user.tools`. Both are empty under this harness, so the two are
equivalent-under-this-config, not identical.

What only a turn can show is EXECUTION: that the model, handed no tool names, reaches for the five
under `control` and demonstrably cannot under `build`. That is what this file pays for.

ASSERTION DISCIPLINE, and it shapes the prompt. The instruction below deliberately does NOT name
any tool. If it did, the tool names would appear in the user message and any assertion scanning the
session's parts would match that text rather than a real call — and the negative half would be
unfalsifiable. Assertions key on parts of `type: "tool"` and read their `tool` field
(`gen/types.gen.ts:294-305`), never on message text. The negative is additionally guarded by
asserting the build turn RAN and produced tool calls of its own, so "no healbot call" cannot pass
because nothing happened at all.

`HEALBOT_AUTO_RETIRE=0`: this rig tests the control surface, not the gate. The tools work either
way, and leaving the gate armed would let it act on the sessions under test.

  venv/bin/python verify_control_agent.py
"""

import json
import os
import sys
import time

from rig import PROJECT, WORK, Api, Results, db, fire, fixtures, git_baseline, serve, wait_for

PORT = 4745
DB = db("control")
LOG = f"{WORK}/control-agent.log"

# The instruction. Names no tool, and asks for something the control tools accomplish directly.
#
# THE PREMISE UNDER THIS COMMENT WAS FALSE AND IS NOW DISPROVED, TESTED. It read: "asks for
# something ONLY the control tools can accomplish — a session cannot create ANOTHER session with
# `bash`, so a build-agent turn has no way to satisfy it and must say so." On the Phase 8 re-run the
# build agent, denied the five tools, went looking with `opencode --help` / `session --help` /
# `run --help` and then ran
#
#     opencode run --auto --format json --title "..." "Create a file named hello.txt ..."
#
# which created a real TOP-LEVEL session (`ses_05a078334ffe`, 1 user + 3 assistant messages, agent
# `build`). The CLI is on PATH inside the tool sandbox, and it talks to the same DB.
#
# What that costs and what it does not. It does NOT touch the claim this file is paid for: the tool
# DEFINITIONS are still absent from the build agent's request payload, which is the token-budget
# claim, and it still passes. What it kills is a containment reading nobody should have had —
# `healbot_*: deny` scopes CONTEXT, not CAPABILITY. Any agent with `bash` can reach the same
# capability the long way round. See docs/GROWTH.md.
TASK = (
    "Report how many other sessions are currently running in this project. Then start a new, "
    "separate session whose job is to create a file called hello.txt in the project directory "
    "containing exactly the word HELLO. Do not create hello.txt yourself — a different session "
    "must do it. Finish by stating the id of the session you started."
)

r = Results()
api = Api(PORT, PROJECT)
server = None


def parts_of(sid):
    out = []
    for m in api("GET", f"/session/{sid}/message") or []:
        out += m.get("parts") or []
    return out


def tools_called(sid):
    return [p.get("tool") for p in parts_of(sid) if p.get("type") == "tool" and p.get("tool")]


def texts(sid, role=None):
    out = []
    for m in api("GET", f"/session/{sid}/message") or []:
        info = m.get("info") or m
        if role and info.get("role") != role:
            continue
        out += [p.get("text", "") for p in (m.get("parts") or []) if p.get("type") == "text"]
    return "\n".join(out)


def live():
    return [s for s in (api("GET", "/session?scope=project") or []) if not (s.get("time") or {}).get("archived")]


fixtures()
if os.path.exists(f"{PROJECT}/hello.txt"):
    os.remove(f"{PROJECT}/hello.txt")
git_baseline()

try:
    print("== headless server, gate disarmed ==", flush=True)
    server = serve(PORT, DB, log=LOG, env_extra={"HEALBOT_AUTO_RETIRE": "0"})
    time.sleep(2)

    # A quiet session so `healbot_list` has something to report other than the caller itself.
    bystander = api("POST", "/session", {})["id"]
    api("PATCH", f"/session/{bystander}", {"title": "quiet bystander"})
    before = {s["id"] for s in live()}

    # ------------------------------------------------------------------ the control agent
    print("\n== the same instruction, under agent: control ==", flush=True)
    control = api("POST", "/session", {})["id"]
    started = time.time()
    api(
        "POST",
        f"/session/{control}/message",
        {"parts": [{"type": "text", "text": TASK}], "agent": "control"},
    )
    print(f"  control session {control} finished its turn in {time.time() - started:.0f}s", flush=True)

    called = tools_called(control)
    r.check("the control turn ran", bool(called) or bool(texts(control, role="assistant")), f"tools: {called}")
    r.check(
        "THE CONTROL AGENT HAS THE TOOLS AND USED THEM",
        any(t and t.startswith("healbot_") for t in called),
        f"called: {[t for t in called if t and t.startswith('healbot_')]}",
    )
    r.check(
        "it listed the fleet",
        "healbot_list" in called,
        "the tool that reads GET /session + /permission + /question through the plugin's client",
    )
    r.check("it spawned a session", "healbot_spawn" in called, f"all calls: {called}")

    # The spawn must have produced a REAL session, not just a successful-looking tool result.
    spawned = wait_for(
        lambda: next((s["id"] for s in live() if s["id"] not in before and s["id"] != control), None),
        120,
        "the spawned session to appear",
    )
    r.check("a real session was created", bool(spawned), f"{spawned}")
    r.check(
        "…and it is a top-level session, not a subagent",
        bool(spawned) and not next((s for s in live() if s["id"] == spawned), {}).get("parentID"),
        "POST /session, not the task tool",
    )

    # And it was actually SEEDED — a spawn that creates an empty session is a wasted window.
    seed = texts(spawned, role="user") if spawned else ""
    r.check("the spawned session was seeded with work", "hello.txt" in seed.lower(), f"{len(seed)} chars")

    # It runs on its own. This is `prompt_async`, so the control agent's turn did not wait for it.
    did_work = wait_for(
        lambda: os.path.exists(f"{PROJECT}/hello.txt") or bool(tools_called(spawned)),
        600,
        "the spawned session to do its work",
    )
    r.check("the spawned session picked the work up unprompted", bool(did_work), f"tools: {tools_called(spawned)}")
    if os.path.exists(f"{PROJECT}/hello.txt"):
        with open(f"{PROJECT}/hello.txt", encoding="utf-8") as fh:
            body = fh.read().strip()
        r.check("…and produced the file", "HELLO" in body.upper(), f"{body[:40]!r}")

    # The plugin logged it. Only the server writes this line, so it is independent evidence that
    # the tool ran inside the plugin rather than the model narrating a plausible story.
    log = open(LOG, encoding="utf-8", errors="replace").read() if os.path.exists(LOG) else ""
    r.check(
        "the SERVER logged the spawn",
        f"control: spawned {spawned}" in log,
        next((ln for ln in log.splitlines() if "control: spawned" in ln), "not found"),
    )

    # ------------------------------------------------------------------ THE NEGATIVE HALF
    # Same instruction, default agent. If the deny is broken, the definitions are in this session's
    # prompt too and the model — asked to start another session — would reach for them.
    print("\n== the same instruction, under the default build agent ==", flush=True)
    plain = api("POST", "/session", {})["id"]
    api("POST", f"/session/{plain}/message", {"parts": [{"type": "text", "text": TASK}]})

    plain_called = tools_called(plain)
    plain_healbot = [t for t in plain_called if t and t.startswith("healbot_")]
    r.check(
        "the build turn RAN — so the negative below is not vacuous",
        bool(plain_called) or bool(texts(plain, role="assistant")),
        f"tools: {plain_called}",
    )
    r.check(
        "THE BUILD AGENT DOES NOT HAVE THE TOOLS",
        not plain_healbot,
        "same instruction, opposite outcome — the definitions are removed from the request payload, "
        "not merely refused at execution"
        if not plain_healbot
        else f"LEAKED: {plain_healbot}",
    )
    # THE FOURTH FORM OF THIS ASSERTION, and the first one that is both true and falsifiable. The
    # three before it are kept in full because the sequence is the lesson: each was a sharper guess
    # about what the deny guarantees, and the guarantee kept shrinking.
    #
    #   1. "the build agent created no new session" — FAILED on execution. The extra was its own
    #      `@general` subagent, which `task` legitimately creates (`['skill','bash','bash','task']`).
    #      It measured "did anything create a session" when the claim was about the DENIED tools, and
    #      it made the deny look broken for doing the right thing.
    #   2. "all(s.get('parentID') for s in extras)" — vacuously True on an empty list, and `extras`
    #      is empty whenever the build agent answers directly instead of delegating. Caught in a
    #      Phase 7 review before it ever ran; a re-run could have reported 16/16 having validated
    #      nothing.
    #   3. "it created NO top-level session" — DISPROVED ON EXECUTION, Phase 8. It created one, with
    #      `bash` and the `opencode` CLI. See the note on TASK above. This is the interesting one:
    #      form 2 was too weak to fail and form 3 was strong enough to fail, and did — against a
    #      premise the rig had been carrying in a comment since it was written.
    #
    # So state the claim the deny actually makes. It is a CONTEXT control: no top-level session was
    # created by a healbot TOOL. The server logs every `healbot_spawn` it serves and only the server
    # writes that line, so the log is independent of anything the model said or did — if the deny
    # leaked and the build turn spawned through the tool, a second `control: spawned` appears here.
    extras = [s for s in live() if s["id"] not in before and s["id"] not in (control, spawned, plain)]
    top_level = [s for s in extras if not s.get("parentID")]
    log = open(LOG, encoding="utf-8", errors="replace").read() if os.path.exists(LOG) else ""
    spawn_lines = [ln for ln in log.splitlines() if "control: spawned" in ln]
    r.check(
        "…and no healbot TOOL spawned anything for it — the server logged exactly one spawn, the "
        "control agent's",
        len(spawn_lines) == 1 and spawned in spawn_lines[0],
        f"{len(spawn_lines)} spawn line(s): {[ln.split('spawned ')[-1][:20] for ln in spawn_lines]}",
    )
    # The finding itself, surfaced on every run so it cannot quietly stop being exercised without
    # anyone noticing. When the build agent takes the bash route, the command is printed verbatim;
    # when it does not, that is said out loud rather than reading as though the case were covered.
    bash_cmds = [
        ((p.get("state") or {}).get("input") or {}).get("command", "")
        for p in parts_of(plain)
        if p.get("type") == "tool" and p.get("tool") == "bash"
    ]
    escaped = [c for c in bash_cmds if c and ("opencode run" in c or "/session" in c)]
    # NOT an r.check. It has no failing case — a run where the build agent behaves is as consistent
    # with the finding as one where it does not — and an assertion that cannot go red is the exact
    # thing this suite's README calls its characteristic failure. Printed, counted by nobody.
    if escaped and top_level:
        detail = f"{len(top_level)} top-level session(s) created with no healbot tool, via {escaped[0][:90]!r}"
    else:
        detail = (
            f"NOT EXERCISED this run ({len(extras)} extra, {len(top_level)} top-level, "
            f"{len(escaped)} session-creating bash call(s)) — the build agent did not take the bash "
            "route this time, so this run adds no evidence either way. The finding rests on the "
            "Phase 8 run recorded in the TASK note above, not on this line"
        )
    print(f"\n  [observation] CONTAINMENT IS NOT WHAT THE DENY BUYS: {detail}", flush=True)

    # The pair, stated as one fact. This is the assertion the token budget rests on.
    r.check(
        "SCOPING HOLDS: control has them, build does not",
        any(t and t.startswith("healbot_") for t in called) and not plain_healbot,
        f"control called {[t for t in called if t and t.startswith('healbot_')]}, build called none",
    )

    r.check("the guard did not report a failure", "retire FAILED" not in log, "no failure lines")
    r.check("the server is still healthy", api("GET", "/session?scope=project") is not None)

finally:
    if server:
        try:
            server.kill()
        except Exception:
            pass
    ok = r.summary()
    print(f"\n  server log: {LOG}", flush=True)
    sys.exit(0 if ok else 1)
