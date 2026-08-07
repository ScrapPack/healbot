"""Is the control agent wired up? — FREE, no model turn.

Build-order step 5 has three separate pieces of wiring, each of which fails silently and
differently:

  * The TOOLS come from the server plugin's `tool` hook. If the plugin fails to load, or an export
    trips `getLegacyPlugins`, or a key is renamed, the tools simply are not in the registry and the
    control agent is an agent with nothing to control. There is no error anywhere the operator
    looks — the model just says it cannot do that.
  * The AGENT comes from `<configdir>/agent/control.md`. If the frontmatter is wrong the agent may
    not exist, or may exist as a SUBAGENT — and a subagent's description becomes per-request rent
    on the `task` tool for every other session (`tool/registry.ts:260-273`), which is the exact
    cost this harness exists to remove.
  * The SCOPING is a global deny plus an agent-level allow. Break the deny and five tool
    definitions land in every session's prompt forever; break the allow and the control agent
    cannot use them.

This probe covers what can be established without a model turn: registration, agent identity, and
the static shape of the permission wiring.

THIS PARAGRAPH USED TO SAY THE SCOPING "happens in `resolveTools` at request-prep time and needs a
real turn". That is false, and it was queueing paid work that did not need to be paid for. The
DISABLED SET is free and deterministic: `opencode debug agent <name>` prints it. Its
`resolveTools` (`cli/cmd/debug/agent.handler.ts:88-98`) calls the same `Permission.disabled` over
the same merged ruleset, and the session-creating branch is gated behind `if (toolID)`
(`:43-58` → `createToolContext` → `sessionSvc.create` at `:131`), so without `--tool` no session
is created and no provider call is made. Only EXECUTION of a tool needs a real turn.

That disabled set is now COMPUTED by two rows below rather than recorded here as a hand-run
number. It was prose for a phase, and in that phase `healbot_decide` was allowed back for
`build` while `healbot_recall` was not — the default agent could write a decision record and
never read one — with no row anywhere able to see it, because the static rows read the config
files for the SHAPE of the wiring and never its result (review finding from the 3441813 push).
A measurement kept in a docstring is a claim about a file at a moment; the rows re-take it on
every run.

The honest caveat: `agent.handler.ts` is a SEPARATE function calling the same predicate, not the
request path. The real one (`session/llm/request.ts:208-214`) additionally merges session-level
permission into the ruleset and filters on `input.user.tools`. Both are empty under this harness,
so the two are equivalent-under-this-config rather than identical — a session-scoped permission
override or a per-request `tools` map would separate them. What `verify_control_agent.py` still
buys, and the reason it is worth a real turn, is that the model actually CALLS the five tools
under `control` and cannot under `build`.

  venv/bin/python probe_control_wiring.py
"""

import os
import re
import sys
import time

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import rig  # noqa: E402

PORT = 4153
LOG = f"{rig.WORK}/control-wiring.log"
CONFIG = f"{rig.HEALBOT}/harness/config/opencode"
TOOLS = ["healbot_list", "healbot_spawn", "healbot_prompt", "healbot_abort", "healbot_retire"]

# The MEMORY tools, which are a different question from the five above and were covered by
# nothing. `build` must hold BOTH: `healbot_decide` writes a decision record and `healbot_recall`
# reads one, and an agent allowed to write what it can never read back is the shape this probe
# missed for a whole phase — `docs/RECORDS.md` §5 makes recall the PRIMARY retrieval mechanism and
# the orientation block the capped exception (review finding from the 3441813 push).
MEMORY_TOOLS = ["healbot_decide", "healbot_recall"]

r = rig.Results(expect=16, skip_max=2)
server = None


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


_agent_cache, _agent_why = {}, {}


def agent_tools(name):
    """-> {tool: enabled?} for one agent, or None when `debug agent` could not ANSWER.

    Cached, because it shells out and two rows read it.

    THE RETURN VALUE ANSWERS ONE QUESTION AND NEVER THE OTHER: did the command produce a map.
    What is IN the map is the rows' business. That separation is what `rig.Env` requires — a
    requirement must be strictly weaker than the check it guards — so a machine where the
    command answers and the permission is wrong still goes RED, which is the finding, while a
    machine where it cannot answer declares a NAMED skip instead of a red meaning "wrong
    machine". The first draft returned None for both cases and discarded `returncode` and
    stderr, so a provider-auth failure and a genuinely wrong permission printed the same
    `got None` and both turned the rows red; a timeout raised straight into the UNEXPECTED
    EXCEPTION row and exit 1 (review finding from the a90dac0 push). `_agent_why` carries the
    cause into the skip note, because a skip nobody can diagnose is its own dead end.
    """
    import subprocess

    if name in _agent_cache:
        return _agent_cache[name]
    try:
        out = subprocess.run(
            ["/bin/zsh", "-c", f". {rig.ENVSH} && exec {rig.OC} debug agent {name}"],
            cwd=rig.HEALBOT, capture_output=True, text=True, timeout=180,
            env={**os.environ, "OPENCODE_DB": rig.db("controlwiring-debug")},
        )
    except subprocess.TimeoutExpired:
        _agent_why[name] = "timed out after 180s"
        _agent_cache[name] = None
        return None
    if out.returncode != 0:
        tail = (out.stderr or out.stdout).strip().splitlines()[-1:] or [""]
        _agent_why[name] = f"exit {out.returncode}: {tail[0][:160]}"
        _agent_cache[name] = None
        return None
    found = dict(re.findall(r'"(healbot_[a-z_]+)":\s*(true|false)', out.stdout))
    if not found:
        # Exit 0 with no map is its own failure: the command ran and told us nothing, which is
        # not the same as telling us the tools are disabled.
        _agent_why[name] = f"exit 0 but no healbot_* map in {len(out.stdout)} B of output"
        _agent_cache[name] = None
        return None
    _agent_cache[name] = {k: v == "true" for k, v in found.items()}
    return _agent_cache[name]


def _debug_agent_ready():
    """RAISES rather than returning False, so the cause reaches the printed note. `Env.satisfied`
    catches and renders it as `could not establish: …`; a bare False would print the requirement's
    name and lose which agent failed and why, which is the diagnosability half of the finding."""
    missing = [n for n in ("build", "control") if agent_tools(n) is None]
    if missing:
        raise RuntimeError("; ".join(f"{n} — {_agent_why.get(n, 'unknown')}" for n in missing))
    return True


DEBUG_AGENT = rig.Env(
    "debug-agent-answers",
    "`opencode debug agent` runs and prints a healbot_* permission map — it needs the derived "
    "opencode/ checkout and a resolvable default model, and it is the one command the two "
    "permission-result rows read",
    _debug_agent_ready,
)


# The ordinary absent-checkout case. Without it this probe timed out for 90s, reported red rows
# and an UNEXPECTED EXCEPTION and exited 1 — "a check ran and said no" for a check that could not
# run, the ERROR-versus-BLOCKED collapse the gate's state lattice exists to prevent.
# `probe_staleness_join.py` was corrected for this and this probe was never backfilled; exit 3 is
# the cannot-measure verdict and `gate.py` maps it to ERROR.
#
# IT SITS ABOVE THE SEVEN STATIC ROWS, WHICH DO NOT NEED THE CHECKOUT, and that costs their
# coverage in a fresh clone or a linked worktree. Deliberate, and the alternatives are worse
# rather than merely more work (review finding from the a90dac0 push, action no-op). Moving the
# exit BELOW them hides a red: a static row that failed would be recorded and then buried under
# exit 3, cannot-measure masking a finding. Hoisting the rows ABOVE the try to keep the exit
# pre-try loses them the UNEXPECTED EXCEPTION guard, so a `FileNotFoundError` on the config read
# would traceback out at exit 1 with no row and `Results(expect=)` would never judge it. The
# principled third option is a `rig.Env` on the server-dependent rows, the way `DEBUG_AGENT`
# guards the two permission rows above — that recovers the seven and is the right shape, but it
# restructures the server setup and every runtime row, which is more risk than a no-op finding
# earns inside a repair. Nothing here is silently wrong: exit 3 says UNMEASURED out loud.
sys.path.insert(0, os.path.join(rig.HEALBOT, "gate"))
import citegraph  # noqa: E402

if not citegraph.checkout_present():
    print(f"\n!! {citegraph.CHECKOUT}/.git not found. UNMEASURED, not failed.\n", file=sys.stderr)
    sys.exit(3)

try:
    # -----------------------------------------------------------------------------------------
    # 1. STATIC — the two halves of the scoping, and the agent's mode.
    # -----------------------------------------------------------------------------------------
    config = read(f"{CONFIG}/opencode.jsonc")
    agent = read(f"{CONFIG}/agent/control.md")

    # `permission/index.ts:190` turns a string value into `{permission, pattern: "*", action}`, and
    # `Permission.disabled` (`:204-215`) removes a tool from the request payload only when the LAST
    # matching rule is `pattern: "*"` with `action: "deny"`. So a BLANKET deny is the one that
    # actually removes the schema; a scoped one would leave the definitions in every prompt and
    # only block execution — all of the token cost, none of the benefit.
    r.check(
        "the config denies healbot_* globally",
        bool(re.search(r'"healbot_\*"\s*:\s*"deny"', config)),
        "a blanket deny is the only kind that removes a tool schema from the prompt",
    )
    r.check(
        "the control agent allows them back",
        bool(re.search(r"healbot_\*\s*:\s*allow", agent)),
        "merged last (agent/agent.ts:293), so it wins the findLast",
    )
    r.check(
        "the control agent is PRIMARY",
        bool(re.search(r"^mode:\s*primary\s*$", agent, re.M)),
        "an agent defined only in config defaults to mode 'all'; a non-primary agent's description "
        "becomes per-request task-tool rent for every other session",
    )
    r.check(
        "it has a description",
        bool(re.search(r"^description:\s*\S", agent, re.M)),
        "the agent picker shows it",
    )
    # The markdown BODY becomes the prompt and REPLACES the base prompt (`config/agent.ts:24-28`
    # assigns it after the frontmatter spread, so a `prompt:` key would be silently clobbered).
    # That replacement is the harness's single largest strip lever, so an empty body would be a
    # quiet regression to the full shipped prompt.
    body = agent.split("---", 2)[-1].strip()
    r.check("its body is a real prompt", len(body) > 500, f"{len(body)} B — it replaces the base prompt")
    r.check(
        "the frontmatter does not also set `prompt:`",
        not re.search(r"^prompt:", agent, re.M),
        "the body overwrites it, so a prompt key would be a silent no-op",
    )

    r.check(
        "the plugin is registered",
        "./plugin/healbot.ts" in config,
        "an unregistered plugin contributes no tools",
    )

    # -----------------------------------------------------------------------------------------
    # 1b. THE DISABLED SET, COMPUTED. `opencode debug agent <name>` runs the same
    # `Permission.disabled` over the same merged ruleset as the request path
    # (`cli/cmd/debug/agent.handler.ts:88-98`) and creates no session, so this is free.
    #
    # THIS PROBE ASSERTED IT IN PROSE AND NOWHERE ELSE. The docstring above recorded "TESTED
    # under this harness … `debug agent build` reports all five healbot_* false" as a hand-run
    # measurement, which is a claim about a file at a moment with nothing computing it — and in
    # the interval `healbot_decide` was allowed back for `build` and `healbot_recall` was not,
    # with no row anywhere able to see it (review finding from the 3441813 push). The regex rows
    # above cannot: they read the two config files for the SHAPE of the wiring, never its result.
    # -----------------------------------------------------------------------------------------
    build_set, control_set = agent_tools("build"), agent_tools("control")
    r.check(
        "the BUILD agent holds both memory tools and none of the five fleet tools",
        lambda: all(build_set.get(t) is True for t in MEMORY_TOOLS)
        and all(build_set.get(t) is False for t in TOOLS),
        f"BOTH HALVES, and the split is the whole design. The fleet tools are rent every session "
        f"would pay for a capability only `control` uses; retrieval is not — the recall tool's "
        f"own description names this agent's work, and denying it left the default agent able to "
        f"record decisions it could never read back. The second clause is what keeps this row "
        f"from passing over a blanket `healbot_*: allow` that would put all five definitions in "
        f"every prompt. got {build_set}",
        needs=DEBUG_AGENT,
    )
    r.check(
        "…and the CONTROL agent holds all seven",
        lambda: all(control_set.get(t) is True for t in TOOLS + MEMORY_TOOLS),
        f"the other side of the same predicate, so a global deny that stopped being allowed back "
        f"anywhere would fail here rather than read as correct scoping. got {control_set}",
        needs=DEBUG_AGENT,
    )

    # -----------------------------------------------------------------------------------------
    # 2. RUNTIME, still free — do the tools reach the registry, and does the agent exist?
    # -----------------------------------------------------------------------------------------
    if os.path.exists(LOG):
        os.remove(LOG)
    server = rig.serve(PORT, rig.db("controlwiring"), log=LOG)
    time.sleep(2)
    api = rig.Api(PORT)

    ids = api("GET", "/experimental/tool/ids", timeout=30) or []
    ids = ids if isinstance(ids, list) else (ids.get("ids") if isinstance(ids, dict) else [])
    missing = [name for name in TOOLS if name not in ids]
    r.check(
        "ALL FIVE CONTROL TOOLS ARE REGISTERED",
        not missing,
        f"{len(TOOLS)} present" if not missing else f"missing {missing}",
    )
    # The registry uses the plugin's `tool` record KEY verbatim as the id — no namespacing
    # (`tool/registry.ts:194-198`). Asserting a name that is NOT there keeps the check above from
    # passing on a substring or a stale list.
    r.check(
        "…and nothing invented",
        "healbot_nonexistent" not in ids,
        "negative control on the id list itself",
    )

    # `GET /agent` — the URL the SDK's `app.agents()` uses (`gen/types.gen.ts:3320`). Wrapped
    # because a 404 raises out of urllib and would skip every assertion below it, which is how the
    # first version of this probe reported 9/9 while silently testing nothing about the agent.
    try:
        agents = api("GET", "/agent", timeout=30) or []
    except Exception as exc:
        agents = []
        print(f"  !! GET /agent failed: {exc}", flush=True)
    names = [a.get("name") for a in agents] if isinstance(agents, list) else []
    r.check("the control agent is registered", "control" in names, f"agents: {sorted(n for n in names if n)}")
    control = next((a for a in (agents or []) if a.get("name") == "control"), None)
    r.check(
        "…as a primary agent, per its frontmatter",
        bool(control) and control.get("mode") == "primary",
        f"mode={control.get('mode') if control else None}",
    )
    # Asserted on the DESCRIPTION rather than on a "is it built in" flag. The generated SDK type
    # advertises `builtIn` (`gen/types.gen.ts:1589`) but `grep -rn builtIn packages/opencode/src
    # packages/core/src packages/schema/src` finds no assignment anywhere — the field is stale in
    # the generated types and absent from the payload, so a check on it silently compares None. The
    # claim worth making is that the registered agent is the one THIS file defines, and matching
    # the description proves that directly.
    described = re.search(r"^description:\s*(.+?)\s*$", agent, re.M)
    r.check(
        "…and it is the agent control.md defines, not a coincidence of naming",
        bool(control) and bool(described) and control.get("description") == described.group(1),
        f"server={control.get('description') if control else None!r}",
    )

    # The plugin must not have failed to load. `applyPlugin` catches and publishes rather than
    # crashing, so a broken plugin is a log line and an otherwise healthy server.
    log = read(LOG) if os.path.exists(LOG) else ""
    r.check(
        "the plugin loaded without error",
        "Failed to load plugin" not in log and "Plugin export is not a function" not in log,
        "a plugin that throws on load leaves a healthy server with no tools",
    )
    r.check("…and it armed", "[healbot]" in log, "the plugin's own log line")

except SystemExit:
    raise
except Exception:
    # Failures must look like failures. `sys.exit()` inside a `finally` DISCARDS the escaping
    # exception, so a probe that crashed still exits on summary()'s verdict over whatever ran
    # first. probe_request_channel.py:151 named this and guarded against it; it was never
    # backfilled. Phase 9 backfilled it, after a fresh clone crashed seven probes into green
    # exit codes — see Results(expect=...) in rig.py for the other half of the fix.
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    if server:
        try:
            server.kill()
        except Exception:
            pass
    ok = r.summary()
    sys.exit(0 if ok else 1)
