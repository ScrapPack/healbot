"""Backends: an ARM is a runtime CONFIGURATION; a BACKEND is the PROGRAM that runs it.

Everything in this suite has spoken exactly one program's REST API. `rig.py` boots
`bun run --cwd opencode/packages/opencode src/index.ts serve`, `ab.serve_arm()` varies the shell
prelude in front of that same line, and every consumer downstream reads opencode's message shape.
"Both harnesses" has been a claim about a memory symlink and a spec for an external tool
(`docs/AFK.md`, gnhf 0.1.43), not about anything this repo can run. This file is the seam that
makes the second program addressable.

THE NORMALIZED SHAPE IS OPENCODE'S, DELIBERATELY, AND THAT IS THE WHOLE DESIGN.

The tempting move is a neutral third schema both backends map into. It is the wrong one: seven
consumers already read opencode's shape (`ab.assistant_msgs`, `reply_text`, `used_tools`,
`provider_blocked`, `score`, `run_refusal.token_usage`, `pin_result`, and `probe_turn_growth`'s
loader), so a third vocabulary means rewriting all of them and re-verifying every number they
produce. Mapping Claude Code INTO the existing vocabulary costs one function and leaves every
recorded measurement comparable to itself.

That choice has a sharp edge worth stating: the mapping is only honest where the two programs
mean the same thing by a field. Where they do not, the deviation is commented at the line rather
than smoothed over.

WHAT THIS DOES NOT DO, AND THE REASON IS NOT EFFORT.

A Claude Code arm cannot join the refusal A/B study. `ab.PIN` is `openai/gpt-5.6-sol` and the
entire method (`ab.py:14-22`) rests on holding the model identical across arms; Claude Code
serves Anthropic models. A "harness comparison" whose arms run different models is the exact
confound `ab.py` exists to prevent, and it would be that confound at its worst — refusal
disposition is a MODEL property first. So: this backend is for driving and MEASURING Claude Code
sessions (occupancy, retirement, handoff — healbot's product thesis), not for adding a third arm
to Set A. Changing that needs a different study design, not a flag.

The fleet half is also not here. Retirement, the handoff document and the grid live in
`harness/config/opencode/plugin/healbot.ts` as an opencode PLUGIN — in-process, on opencode's
event bus. Claude Code has no equivalent plugin surface, so that half is a port, not a wrapper.
What this file provides is the measurement substrate that port would stand on.

  venv/bin/python probe_backend.py          # free: every check below, no model calls

The one paid smoke, owner's go (Tier 3), which is also what verifies the result-JSON schema
this module parses defensively:

  claude -p 'reply with the single word: ok' --output-format json --max-budget-usd 0.05
"""

import json
import os
import re
import subprocess

import ab


CLAUDE = os.environ.get("HEALBOT_CLAUDE_BIN", "claude")
CC_PROJECTS = os.path.expanduser("~/.claude/projects")

# Claude Code's stop_reason -> opencode's `finish`. This map is the reason normalization is worth
# doing at all: `run_refusal.turn_complete()` treats any finish outside ("tool-calls", "unknown")
# as a completed turn, and healbot.ts's `turnFinished` carries the same exclusion list copied from
# `prompt.ts:1295`. Mapping tool_use -> "tool-calls" makes both predicates work unchanged on a
# Claude Code transcript.
#
# "refusal" -> "content-filter" is the load-bearing row. `ab.provider_blocked()` is the ONLY exact
# discriminator in the scorer — it separates "the model declined in prose" from "the provider
# blocked the turn", which is the floor docs/REFUSAL-BASELINE.md §2b builds on. Anthropic's API
# reports a server-side stop as stop_reason "refusal"; opencode surfaces the same event as
# finish "content-filter". Dropping this row would silently reclassify every provider block as a
# model refusal and invert the one number the study is about.
STOP_REASON = {
    "end_turn": "stop",
    "tool_use": "tool-calls",
    "max_tokens": "length",
    "stop_sequence": "stop-sequence",
    "refusal": "content-filter",
    "pause_turn": "unknown",
}


def occupancy(tokens):
    """Live context occupancy of ONE assistant message.

    Mirrors the shipped gate's `occupancyOf` (`harness/config/opencode/plugin/healbot.ts:312-318`)
    exactly, including the prefer-total-then-fall-back-to-the-sum order. Reimplemented rather than
    imported because that one is TypeScript inside the plugin; `probe_backend.py` asserts the two
    agree on a constructed case, so a divergence is caught rather than assumed away.
    """
    if not tokens:
        return 0
    total = tokens.get("total") or 0
    if total > 0:
        return total
    cache = tokens.get("cache") or {}
    return (tokens.get("input") or 0) + (tokens.get("output") or 0) + \
           (cache.get("read") or 0) + (cache.get("write") or 0)


def project_slug(directory):
    """Claude Code's on-disk name for a working directory.

    Every non-alphanumeric character becomes a dash. VERIFIED against the real directory names
    under ~/.claude/projects rather than derived from documentation — the worktree entries are
    what pin it, since a path containing both `/` and `.` (`.../Vintage/.claude-worktrees/...`)
    produces the double dash `Vintage--claude-worktrees` that a `/`-only rule would not.
    `probe_backend.py` re-checks this against whatever is on disk.
    """
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(directory))


def transcript_path(session_id, directory):
    return f"{CC_PROJECTS}/{project_slug(directory)}/{session_id}.jsonl"


def _tokens(usage):
    """Anthropic usage -> opencode's token block.

    `total` is set to the four-part sum, which opencode does NOT do — there it is the provider's
    own figure. The deviation is deliberate and bounded: `occupancyOf` prefers `total` when it is
    positive and otherwise sums exactly these four, so writing the sum in makes both branches
    agree instead of leaving `run_refusal.token_usage` to report a total of 0 for every turn.
    INFERRED from that fallback's construction, not verified against opencode's provider figures —
    and it does not need to be, because a Claude Code total is never compared to an opencode one
    (see the model-pin note in the module docstring).

    `reasoning` is 0 and that is a real gap, not a placeholder: extended thinking is billed inside
    output_tokens and Anthropic reports no separate count, so a thinking-heavy turn looks like a
    verbose one. Occupancy is unaffected (the tokens are counted once, in output).
    """
    usage = usage or {}
    read = usage.get("cache_read_input_tokens") or 0
    write = usage.get("cache_creation_input_tokens") or 0
    inp = usage.get("input_tokens") or 0
    out = usage.get("output_tokens") or 0
    return {
        "input": inp,
        "output": out,
        "reasoning": 0,
        "cache": {"read": read, "write": write},
        "total": inp + out + read + write,
    }


def _parts(content):
    """Anthropic content blocks -> opencode parts.

    `thinking` blocks are dropped rather than mapped to text. They must be: `ab.reply_text()`
    feeds `score()`, and the DECLINE patterns are first-person ("I cannot help with...") — a model
    that reasons "I can't just refuse this" and then complies would score as a refusal on its own
    scratchpad. That is the naive-scorer inversion `ab.py:210-220` was written to prevent,
    arriving by a different door.
    """
    out = []
    for block in content or []:
        if not isinstance(block, dict):
            continue
        kind = block.get("type")
        if kind == "text" and block.get("text"):
            out.append({"type": "text", "text": block["text"]})
        elif kind == "tool_use" and block.get("name"):
            out.append({"type": "tool", "tool": block["name"]})
    return out


def normalize(records, session_id=None):
    """A Claude Code transcript (parsed JSONL records) -> opencode-shaped messages.

    Sidechain records are excluded. They are sub-agent turns (`isSidechain: true`), which have
    their own model and their own token accounting; folding them into the parent would double
    count occupancy and let a sub-agent's text answer for the main agent's disposition.
    """
    msgs = []
    for rec in records:
        if not isinstance(rec, dict) or rec.get("isSidechain"):
            continue
        if session_id and rec.get("sessionId") not in (None, session_id):
            continue
        kind = rec.get("type")
        if kind not in ("user", "assistant"):
            continue
        message = rec.get("message") or {}
        content = message.get("content")
        if kind == "user":
            # A user record is either the real prompt (content is a plain string) or a tool
            # RESULT wearing the user role, which is a transport detail and not a turn.
            if not isinstance(content, str):
                continue
            msgs.append({"info": {"role": "user", "time": rec.get("timestamp")},
                         "parts": [{"type": "text", "text": content}]})
            continue
        stop = message.get("stop_reason")
        msgs.append({
            "info": {
                "role": "assistant",
                "modelID": message.get("model"),
                # Claude Code does not name a provider in the transcript. Direct API is the
                # default; Bedrock and Vertex are selected by environment and would need to be
                # read from it. Left honest rather than guessed at per-message.
                "providerID": "anthropic",
                "finish": STOP_REASON.get(stop, stop),
                "tokens": _tokens(message.get("usage")),
                "cost": 0.0,  # not in the JSONL; the -p result JSON carries total_cost_usd
                "time": rec.get("timestamp"),
            },
            "parts": _parts(content),
        })
    return msgs


def read_transcript(session_id, directory):
    path = transcript_path(session_id, directory)
    records = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except ValueError:
                continue  # a partially flushed final line while a session is live
    return records


class ClaudeCodeBackend:
    """Headless Claude Code, one turn per `ask()`.

    Deliberately spawns the CLI rather than importing an SDK: the CLI is what is installed here
    (2.1.195, `~/.local/bin/claude`, TESTED), it is the surface `docs/AFK.md`'s gnhf drives, and
    it persists a transcript this module can read afterwards — which is what makes a turn
    auditable without re-running it, the same property `ab.save()` exists to preserve.
    """

    name = "claude-code"

    def __init__(self, directory, model=None, permission_mode=None, budget_usd=None, extra_args=()):
        self.directory = directory
        self.model = model
        self.permission_mode = permission_mode
        self.budget_usd = budget_usd
        self.extra_args = list(extra_args)

    def command(self, prompt, resume=None):
        cmd = [CLAUDE, "-p", prompt, "--output-format", "json"]
        if self.model:
            cmd += ["--model", self.model]
        if resume:
            cmd += ["--resume", resume]
        if self.permission_mode:
            cmd += ["--permission-mode", self.permission_mode]
        if self.budget_usd is not None:
            cmd += ["--max-budget-usd", str(self.budget_usd)]
        # --allowed / --disallowed / --tools exist on 2.1.195 but their argument syntax was not
        # verified here, so they are not hardcoded. Pass them through extra_args and they will be
        # recorded in the run's own metadata like any other arm difference.
        return cmd + self.extra_args

    def ask(self, prompt, resume=None, timeout=900):
        """One turn. Returns (normalized_messages, result_json).

        PAID. The result-JSON schema is parsed defensively with .get() because it has not been
        verified against a live call from this file — see the smoke command in the module
        docstring. The transcript half does not depend on it: session_id aside, everything this
        suite measures is re-read from the JSONL, which IS verified.
        """
        proc = subprocess.run(self.command(prompt, resume), cwd=self.directory, capture_output=True,
                              text=True, timeout=timeout)
        try:
            result = json.loads(proc.stdout)
        except ValueError:
            raise RuntimeError(f"claude did not return JSON (exit {proc.returncode}): "
                               f"{proc.stdout[:200]!r} {proc.stderr[:200]!r}")
        sid = result.get("session_id")
        if not sid:
            raise RuntimeError(f"no session_id in claude result: {sorted(result)}")
        return normalize(read_transcript(sid, self.directory), sid), result


class OpencodeBackend:
    """The existing path, given the same two methods so callers stop reaching for `Api` directly.

    A thin wrapper on purpose. `ab.serve_arm()` already encodes the traps that matter (OPENCODE_DB
    is the only isolation; XDG_DATA_HOME would strand the OAuth credentials; the readiness probe
    must hit an API route) and re-implementing them behind an interface would be a second place
    for them to drift.
    """

    name = "opencode"

    def __init__(self, arm, port, db_path, log=None):
        self.arm, self.port, self.db_path, self.log = arm, port, db_path, log
        self.proc = None
        self.api = None

    def start(self, timeout=120):
        self.proc = ab.serve_arm(self.arm, self.port, self.db_path, log=self.log, timeout=timeout)
        self.api = ab.Api(self.port)
        return self

    def session(self, title, agent="build"):
        return self.api("POST", "/session", {"title": title, "agent": agent})["id"]

    def ask(self, prompt, resume=None, timeout=900):
        sid = resume or self.session("backend turn")
        return ab.ask(self.api, sid, prompt, timeout=timeout), {"session_id": sid}

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=10)
