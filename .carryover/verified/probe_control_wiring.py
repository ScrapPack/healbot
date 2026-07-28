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
is created and no provider call is made. TESTED under this harness with an isolated `OPENCODE_DB`:
`debug agent build` reports all five `healbot_*` **false**, `debug agent control` reports all five
**true**, and the DB held 0 sessions afterwards. Only EXECUTION of a tool needs a real turn.

The honest caveat: `agent.handler.ts` is a SEPARATE function calling the same predicate, not the
request path. The real one (`session/llm/request.ts:208-214`) additionally merges session-level
permission into the ruleset and filters on `input.user.tools`. Both are empty under this harness,
so the two are equivalent-under-this-config rather than identical — a session-scoped permission
override or a per-request `tools` map would separate them. What `verify_control_agent.py` still
buys, and the reason it is worth a real turn, is that the model actually CALLS the five tools
under `control` and cannot under `build`.

  venv/bin/python probe_control_wiring.py
"""

import json
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

r = rig.Results(expect=14)
server = None


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


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
