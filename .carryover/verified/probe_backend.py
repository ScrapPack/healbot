"""Does the Claude Code backend actually read Claude Code? Zero model turns, zero API credits.

Every assertion below runs against transcripts Claude Code has ALREADY written on this machine,
so the normalizer is checked against real recorded output rather than against a fixture someone
wrote to match it. That distinction is not academic here: the two artifact regexes corrected on
2026-07-31 both passed their own hand-written fixtures while failing every real response.

What this cannot check is the paid half — the `-p` result JSON and whether a spawned turn comes
back at all. `backend.ask()` parses that schema defensively for exactly that reason. See the
smoke command in `backend.py`'s docstring; it is Tier 3, owner's go.

  venv/bin/python probe_backend.py
"""

import glob
import os
import re
import shutil
import subprocess
import sys

import ab
import backend
from rig import Env, Results

# ab.HEALBOT rather than a local dirname chain: the first version of this line was one directory
# short and pointed at .carryover, which made the slug resolve to a project that has never
# existed. Deriving it twice is how the two drift.
HEALBOT = ab.HEALBOT
PLUGIN = f"{HEALBOT}/harness/config/opencode/plugin/healbot.ts"


def corpus_dirs():
    return [os.path.basename(p) for p in glob.glob(f"{backend.CC_PROJECTS}/*") if os.path.isdir(p)]


# WHICH corpus is in effect is an environment fact, not a repository one: `backend.CC_PROJECTS`
# honors CLAUDE_CONFIG_DIR (the 2026-08-01 fix in docs/SHIP.md), so under the fleet harness it
# resolves to harness/claude/projects — a young corpus holding one directory per checkout — and
# under a plain shell to the owner's ~/.claude/projects, which has years of them. The dotted-path
# row below needs evidence only the second kind carries. MEASURED in slot-2: 3 directories, none
# with a doubled dash, and the row went red for a corpus that simply has not seen a dotted path.
#
# The requirement is deliberately WEAKER than the row it guards — "some name carries a doubled
# dash" versus "the `--claude-worktrees-` names are there". A corpus with dotted paths that are
# not those ones satisfies the requirement, runs the row, and goes red, which is the finding. A
# requirement as strong as its check would have replaced the measurement with a tautology.
CORPUS_DOTTED = Env(
    "corpus-dotted-path",
    "the transcript corpus in effect (CLAUDE_CONFIG_DIR selects it) holds a project directory "
    "whose name carries a doubled dash — the signature of two adjacent non-alphanumerics in the "
    "source path, which is what a dot-prefixed directory produces",
    lambda: any("--" in d for d in corpus_dirs()),
)

r = Results(expect=16, skip_max=1)
try:
    # --- the program exists -------------------------------------------------------------------
    binary = shutil.which(backend.CLAUDE)
    version = ""
    if binary:
        version = subprocess.run([binary, "--version"], capture_output=True, text=True).stdout.strip()
    r.check(f"the Claude Code CLI is installed and reports a version — {version or 'ABSENT'}",
            bool(binary) and bool(re.match(r"\d+\.\d+", version)),
            "without this every check below would pass vacuously against transcripts alone")

    # --- the path derivation ------------------------------------------------------------------
    # Checked against whatever is actually on disk. A slug rule that is merely self-consistent
    # would agree with itself forever and still point at nothing.
    real_dirs = corpus_dirs()
    ours = backend.project_slug(HEALBOT)
    r.check(f"project_slug derives this repo's real transcript directory — {ours}",
            ours in real_dirs,
            f"{len(real_dirs)} project directories on disk; the rule is re.sub(r'[^A-Za-z0-9]', '-', abspath)")

    # The worktree entries are the ones that discriminate: their paths contain BOTH a slash and a
    # dot, so a slash-only rule produces a different name and this check is how we find out.
    r.check("…including paths with dots as well as slashes — the `--claude-worktrees-` directories",
            lambda: bool([d for d in real_dirs if "--claude-worktrees-" in d]),
            f"a `/`-only rule yields '-claude-worktrees' without the doubled dash and would miss "
            f"these; {len(real_dirs)} directories in {backend.CC_PROJECTS}",
            needs=CORPUS_DOTTED)

    transcripts = sorted(glob.glob(f"{backend.CC_PROJECTS}/{ours}/*.jsonl"), key=os.path.getsize, reverse=True)
    sid = os.path.basename(transcripts[0])[:-6] if transcripts else None
    r.check(f"transcript_path resolves a recorded session — {sid}",
            bool(sid) and os.path.exists(backend.transcript_path(sid, HEALBOT)),
            f"{len(transcripts)} recorded sessions for this repo")

    records = backend.read_transcript(sid, HEALBOT)
    msgs = backend.normalize(records, sid)
    assistants = ab.assistant_msgs(msgs)

    # --- the normalizer, against real recorded output -----------------------------------------
    r.check(f"normalize produces messages ab.assistant_msgs accepts — {len(assistants)} assistant of {len(msgs)} from {len(records)} records",
            len(assistants) > 0 and len(msgs) < len(records),
            "fewer messages than records is expected: tool results, attachments and titles are not turns")

    text = ab.reply_text(msgs)
    r.check(f"ab.reply_text reads assistant prose out of it — {len(text)} chars",
            len(text) > 200,
            "this is the string score() classifies; empty here would score every turn as EMPTY")

    tools = ab.used_tools(msgs)
    r.check(f"tool_use blocks survive as opencode tool parts — {len(tools)} distinct tools",
            len(tools) > 0,
            f"{sorted(tools)[:6]}")

    prompts = [m for m in msgs if (m.get("info") or {}).get("role") == "user"]
    r.check(f"the user's own prompts survive as role=user text — {len(prompts)} of them",
            len(prompts) > 0,
            "run_refusal.transcript_prompt reads these to prove a saved row was asked what the corpus says")

    # Negative control on the one mapping that could silently invert a refusal score.
    thinking = [b.get("thinking", "") for rec in records
                for b in ((rec.get("message") or {}).get("content") or [])
                if isinstance(b, dict) and b.get("type") == "thinking"]
    leaked = [t for t in thinking if t and t[:120] in text]
    r.check(f"thinking blocks are NOT in the scored text — {len(thinking)} present, {len(leaked)} leaked",
            bool(thinking) and not leaked,
            "first-person reasoning ('I can't just refuse this') would score as a refusal under DECLINE")

    sidechain = [rec for rec in records if rec.get("isSidechain")]
    kept = [m for m in msgs if (m.get("info") or {}).get("time") in
            {rec.get("timestamp") for rec in sidechain}] if sidechain else []
    r.check(f"sub-agent (sidechain) turns are excluded — {len(sidechain)} present, {len(kept)} kept",
            not kept,
            "folding them in would double-count occupancy and let a sub-agent answer for the main agent")

    # --- occupancy, against the SHIPPED gate ---------------------------------------------------
    real = next((rec for rec in records if rec.get("type") == "assistant"
                 and ((rec.get("message") or {}).get("usage") or {}).get("cache_read_input_tokens")), None)
    usage = (real.get("message") or {}).get("usage") if real else {}
    manual = sum(usage.get(k) or 0 for k in
                 ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    got = backend.occupancy(backend._tokens(usage))
    r.check(f"occupancy of a real recorded message equals its four-part sum — {got:,}",
            got == manual and got > 0,
            "input + output + cache.read + cache.write, the quantity HEALBOT_RETIRE_AT is denominated in")

    r.check("occupancy prefers an explicit total when one is positive — 999",
            backend.occupancy({"total": 999, "input": 1, "output": 1, "cache": {"read": 1, "write": 1}}) == 999,
            "the shipped formula's first branch; a backend that always summed would disagree with the gate")

    # Read the shipped plugin rather than trusting this file's copy of its arithmetic. A rename or
    # an edit there must fail HERE, which is the same guard probe_turn_growth applies to RETIRE_AT.
    shipped = open(PLUGIN, encoding="utf-8").read()
    body = shipped.split("function occupancyOf", 1)[-1].split("\n}", 1)[0] if "function occupancyOf" in shipped else ""
    r.check("the shipped occupancyOf still has the shape this file mirrors",
            all(token in body for token in ("tokens.total", "tokens.input", "tokens.output",
                                            "cache?.read", "cache?.write")),
            f"{PLUGIN.replace(HEALBOT + '/', '')}:312-318 — if this goes red the two have drifted, fix both")

    # --- the discriminator the whole refusal study rests on ------------------------------------
    def one(stop_reason):
        return backend.normalize([{"type": "assistant", "message": {
            "role": "assistant", "model": "claude-fable-5", "stop_reason": stop_reason,
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "content": [{"type": "text", "text": "..."}]}}])

    r.check("a provider REFUSAL maps to content-filter, so ab.provider_blocked still fires",
            ab.provider_blocked(one("refusal")),
            "the one exact discriminator in the scorer: provider block vs model declining in prose")

    r.check("NEGATIVE CONTROL: an ordinary end_turn does not trip it",
            not ab.provider_blocked(one("end_turn")),
            "if this passed too, the check above would be measuring nothing")

    import run_refusal
    r.check("a mid-turn tool_use step is NOT reported as a completed turn",
            not run_refusal.turn_complete(one("tool_use")) and run_refusal.turn_complete(one("end_turn")),
            "tool_use -> 'tool-calls' keeps the per-turn predicate that Phase 7 spent two phases getting right")

    # --- the blocker, asserted rather than left in prose ---------------------------------------
    # A Claude Code arm cannot join Set A, and this records why in the suite instead of in a
    # document nobody re-reads. If Claude Code ever serves the pinned model this goes red, which
    # is the correct time to revisit the module docstring.
    recorded_models = {(rec.get("message") or {}).get("model") for rec in records
                       if rec.get("type") == "assistant"} - {None}
    r.check(f"THE MODEL PIN BLOCKS A THIRD ARM — Claude Code records {sorted(recorded_models)}, "
            f"ab.PIN is {ab.PIN['providerID']}/{ab.PIN['modelID']}",
            ab.PIN["modelID"] not in recorded_models and ab.PIN["providerID"] != "anthropic",
            "Set A holds the model identical across arms (ab.py:14-22); a Claude Code arm would vary "
            "model AND harness at once, and refusal disposition is a model property first. This "
            "backend is for driving and measuring Claude Code, not for adding an arm to Set A")

except SystemExit:
    raise
except Exception:
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    ok = r.summary()
    sys.exit(0 if ok else 1)
