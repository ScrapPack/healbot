"""Does the claude fleet harness hold its shape? Zero model turns, zero API credits.

Guards the Phase 13 cockpit build (docs/SHIP.md): the parity config dir, the fleet-state
hook's fail-open contract, hb-fleet.sh's five load-bearing tmux guardrails, and the
firstmate skill's canonical-vs-installed twin. Every predicate that reads source carries a
mutation check — the same predicate re-run against a deliberately corrupted copy, required
to fail — because a probe that cannot go red is decoration (the rig-assertion-discipline
skill; probe_twin.py is the pattern source for the twin check).

The hook checks here are LIVE executions, not source reads: the hook's one prior defect
(the heredoc consuming the payload's stdin) produced a script that was syntactically
clean, exited 0, and wrote nothing — exactly the shape only a live happy-path check
catches.

  venv/bin/python probe_fleet_claude.py
"""

import json
import os
import re
import subprocess
import sys
import tempfile

from rig import MAIN_CHECKOUT, Env, Results

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
HARNESS = os.path.join(REPO, "harness")
CFG = os.path.join(HARNESS, "claude")
HOOK = os.path.join(CFG, "hooks", "fleet-state.sh")
FLEET = os.path.join(HARNESS, "hb-fleet.sh")
ENVSH = os.path.join(HARNESS, "env.claude.sh")
SKILL_CANON = os.path.join(HARNESS, "skills", "firstmate.md")
SKILL_INSTALLED = os.path.expanduser("~/.agents/skills/firstmate/SKILL.md")

# `env.claude.sh` materializes the untracked half of the config root when it is sourced
# (env.claude.sh:34-36's `ln -s`). `git worktree add` runs no shell, so a fresh pool slot has
# the tracked half and nothing else. `lexists`, not `exists`: a DANGLING symlink means the
# materialization happened and then broke, which is a red the check below should report — the
# requirement only excuses the case where nothing was ever materialized at all.
CONFIG_MATERIALIZED = Env(
    "claude-config-materialized",
    "env.claude.sh has been sourced against THIS checkout, so harness/claude/ holds the "
    "untracked files it creates at source time",
    lambda: os.path.lexists(os.path.join(CFG, "CLAUDE.md")),
)

# 29 rows through Phase 13; the CLAUDE.md split turns one row into five, so 33. The floor is
# also raised to the count the probe actually produces — it read 20 against a recorded 29, and
# a floor nine below the count cannot catch a probe that loses eight rows. Two skips budgeted,
# one per environment-bound row: in the MAIN checkout both requirements hold and this run
# records `"count": 0`, which is the property firstmate asserts at merge-back.
r = Results(expect=33, skip_max=2)


def sh_n(path):
    return subprocess.run(["sh", "-n", path], capture_output=True).returncode == 0


def settings_ok(d):
    return d.get("autoCompactEnabled") is False and bool(d.get("model"))


def hook_events_ok(d):
    hooks = d.get("hooks") or {}
    for event in ("SessionStart", "Stop", "Notification"):
        groups = hooks.get(event) or []
        cmds = [h.get("command", "") for g in groups for h in (g.get("hooks") or [])]
        if not any("fleet-state.sh" in c for c in cmds):
            return False
    return True


def run_hook(event, stdin_text, fleet_dir):
    env = dict(os.environ)
    if fleet_dir is None:
        env.pop("HB_FLEET_DIR", None)
    else:
        env["HB_FLEET_DIR"] = fleet_dir
    p = subprocess.run([HOOK, event], input=stdin_text, text=True,
                       capture_output=True, env=env)
    return p.returncode


def ignored(relpath):
    return subprocess.run(["git", "-C", REPO, "check-ignore", "-q", relpath],
                          capture_output=True).returncode == 0


try:
    # -- scripts parse -------------------------------------------------------------
    r.check("hb-fleet.sh parses (sh -n)", sh_n(FLEET))
    r.check("env.claude.sh parses (sh -n)", sh_n(ENVSH))
    r.check("fleet-state.sh parses (sh -n)", sh_n(HOOK))
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
        f.write("if [ broken\nthen fi (\n")
        broken = f.name
    r.check("MUTATION: a syntax-broken script fails sh -n", not sh_n(broken))
    os.unlink(broken)

    # -- settings.json -------------------------------------------------------------
    with open(os.path.join(CFG, "settings.json")) as f:
        settings = json.load(f)
    r.check("settings pin a model and turn autoCompact off", settings_ok(settings))
    mut = dict(settings)
    mut["autoCompactEnabled"] = True
    r.check("MUTATION: autoCompact flipped on is caught", not settings_ok(mut))
    r.check("all three fleet hook events run fleet-state.sh", hook_events_ok(settings))
    mut = json.loads(json.dumps(settings))
    del mut["hooks"]["Stop"]
    r.check("MUTATION: a dropped Stop hook is caught", not hook_events_ok(mut))

    # -- fleet-state.sh, live ------------------------------------------------------
    with tempfile.TemporaryDirectory() as td:
        code = run_hook("stop", "NOT JSON {{{", td)
        state = os.path.join(td, "state")
        wrote = os.listdir(state) if os.path.isdir(state) else []
        r.check("garbage stdin: exit 0, nothing written (fail-open)",
                code == 0 and wrote == [], f"exit={code} wrote={wrote}")

        payload = json.dumps({"session_id": "probe-sid-1", "cwd": "/tmp",
                              "transcript_path": "/tmp/t.jsonl"})
        code = run_hook("notification", payload, td)
        target = os.path.join(td, "state", "probe-sid-1.json")
        rec = json.load(open(target)) if os.path.exists(target) else {}
        r.check("happy path: exit 0 and the state file carries the event",
                code == 0 and rec.get("event") == "notification"
                and rec.get("transcript") == "/tmp/t.jsonl", f"exit={code} rec={rec}")

        before = sorted(os.listdir(os.path.join(td, "state")))
        code = run_hook("stop", json.dumps({"session_id": "../evil"}), td)
        after = sorted(os.listdir(os.path.join(td, "state")))
        r.check("a path-traversal session id writes nothing",
                code == 0 and before == after, f"state dir before={before} after={after}")

    code = run_hook("stop", json.dumps({"session_id": "x"}), None)
    r.check("without HB_FLEET_DIR the hook is a silent no-op", code == 0)

    # -- the claude root must stay OUTSIDE the arm factory's frozen tree -----------
    # arms._base_files() os.walks harness/config/ (arms.py:60,83-92) into every arm
    # snapshot. The first draft put the claude root inside it and probe_arm_factory went
    # red on the banned-filename snapshot check — and post-login this directory holds
    # CREDENTIAL state, which must never be frozen into a run dir. Measured, not styled.
    import arms
    r.check("the claude config root is not under arms' frozen tree",
            not (os.path.commonpath([CFG, arms.BASE]) == arms.BASE),
            f"CFG={CFG} arms.BASE={arms.BASE}")

    # -- config-dir .gitignore is a whitelist --------------------------------------
    rel = "harness/claude/"
    r.check("claude-written state is ignored (.claude.json, .credentials.json, backups/)",
            ignored(rel + ".claude.json") and ignored(rel + ".credentials.json")
            and ignored(rel + "backups/x"))
    r.check("NEGATIVE: the tracked harness files are NOT ignored",
            not ignored(rel + "settings.json") and not ignored(rel + "hooks/fleet-state.sh")
            and not ignored(rel + "crew-constraints.md"))

    # -- the banned-filename convention: safe name tracked, real name materialized --
    # Split four ways on 2026-08-01, and the split makes the probe STRONGER rather than merely
    # quieter in a slot. Three of the four facts are pure reads of THIS checkout and hold on
    # any machine: the tracked file under the safe name, the ignore rule, and — new here —
    # env.claude.sh still containing the `ln -s` that materializes the real name. That last
    # one had NO check at all while the convention lived in a single row: delete the ln -s and
    # the row stayed green on every machine where the symlink already existed, which is every
    # machine the probe had ever run on. Only the fourth fact, the link being on disk right
    # now, is environment-bound, and it is the one a pool slot legitimately cannot have.
    claude_md = os.path.join(CFG, "CLAUDE.md")
    tracked = set(subprocess.run(["git", "-C", REPO, "ls-files", "harness/claude/"],
                                 capture_output=True, text=True).stdout.split())
    r.check("the constraints file is TRACKED under the safe name crew-constraints.md",
            "harness/claude/crew-constraints.md" in tracked
            and os.path.isfile(os.path.join(CFG, "crew-constraints.md")),
            "gate.py:200 bans the real name anywhere in the tracked tree; this is the half git carries")
    r.check("NEGATIVE: the real name is NOT tracked, and is ignored",
            "harness/claude/CLAUDE.md" not in tracked and ignored(rel + "CLAUDE.md"),
            "if this ever goes red the ban is being violated, not worked around")

    def materializes(s):
        # The COMMAND, anchored to both operands. Matching `ln -s` alone would survive a link
        # pointed at some other file, and matching the comment block above it would survive
        # the command's deletion — the failure mode this row exists to catch.
        return bool(re.search(r'ln -s crew-constraints\.md "\$HARNESS_ROOT/claude/CLAUDE\.md"', s))

    envsrc = open(ENVSH).read()
    r.check("env.claude.sh materializes the real name as a symlink at source time "
            "(env.claude.sh:34-36)", materializes(envsrc),
            "the tracked half is inert without this: nothing else in the repo creates the link")
    r.check("MUTATION: dropping the ln -s is caught",
            not materializes(envsrc.replace("ln -s crew-constraints.md", "true #", 1)))

    r.check("…and it IS materialized here, pointing at crew-constraints.md",
            lambda: os.path.islink(claude_md) and os.readlink(claude_md) == "crew-constraints.md",
            f"islink={os.path.islink(claude_md)}", needs=CONFIG_MATERIALIZED)

    # -- hb-fleet.sh guardrails, asserted from source with mutations ---------------
    src = open(FLEET).read()

    def literal_send(s):
        return bool(re.search(r'send-keys -t "\$P" -l -- ', s))

    r.check("prompt text goes through send-keys -l -- (literal, dash-safe)",
            literal_send(src))
    r.check("MUTATION: dropping -l is caught",
            not literal_send(src.replace('send-keys -t "$P" -l -- ',
                                         'send-keys -t "$P" -- ')))

    def sync_off(s):
        return "synchronize-panes off" in s

    r.check("synchronize-panes is pinned off at bootstrap", sync_off(src))

    def history_before_spawn(s):
        # Match the COMMAND, not the guardrail prose above it (the first draft matched
        # the comment and its own mutation check failed), and anchor to the EARLIEST
        # crew-pane creation site — `new-window -n crew` creates the first pane, before
        # any split-window (review finding: the split anchor alone left new-window free
        # to move above the option).
        seen = s.find("set -g history-limit")
        creations = [i for i in (s.find("new-window -d -t \"$HB_RUN\" -n crew"),
                                 s.find("split-window -t \"$HB_RUN:crew\"")) if i > 0]
        return bool(creations) and 0 < seen < min(creations)

    r.check("history-limit is set before any crew pane can exist (binds at creation)",
            history_before_spawn(src))
    r.check("MUTATION: history-limit moved after the earliest crew-pane site is caught",
            not history_before_spawn(src.replace("set -g history-limit", "true #", 1)
                                     + "\nset -g history-limit"))

    def resolve_block(s):
        m = re.search(r"resolve_pane\(\)\s*\{.*?\n\}", s, re.S)
        return m.group(0) if m else ""

    def manifest_resolution(s):
        # resolve_pane must go through the manifest, and ITS BODY may not search tmux by
        # name — a "successful" send to a guessed pane is the failure firstmate's fm-send
        # rule exists to prevent. The first draft checked substring presence across the
        # whole file, which a name-search fallback could never turn red (review finding);
        # this reads the function body itself.
        block = resolve_block(s)
        return ("manifest_get" in block
                and "list-panes" not in block and "list-windows" not in block)

    r.check("resolve_pane's body goes through the manifest and never searches tmux",
            manifest_resolution(src))
    r.check("MUTATION: a tmux-name-search fallback inside resolve_pane is caught",
            not manifest_resolution(src.replace(
                "resolve_pane() {",
                "resolve_pane() {\n  t list-panes -a | grep \"$1\" || true", 1)))

    def pane_env_injection(s):
        # Guardrail 6: panes inherit the tmux SERVER's start environment, so the spawn
        # split must inject THIS run's HB_FLEET_DIR explicitly or hooks write into
        # whichever run started the server (review finding, TESTED cross-run).
        return '-e "HB_FLEET_DIR=$HB_FLEET_DIR"' in s

    r.check("crew spawns inject HB_FLEET_DIR per pane (split-window -e)",
            pane_env_injection(src))
    r.check("MUTATION: dropping the -e injection is caught",
            not pane_env_injection(src.replace('-e "HB_FLEET_DIR=$HB_FLEET_DIR"', "")))

    # -- firstmate skill: canonical vs installed twin, and the shell-hole ban ------
    canon = open(SKILL_CANON).read()
    r.check("firstmate skill has frontmatter name and description",
            canon.startswith("---") and "name: firstmate" in canon
            and "description:" in canon)

    def no_shell_hole(s):
        return not re.search(r"!\s*`", s)

    r.check("skill body contains no !`cmd` shell-substitution pattern "
            "(the env.sh:48-53 hole class)", no_shell_hole(canon))
    r.check("MUTATION: an injected !`cmd` is caught",
            not no_shell_hole(canon + "\nrun !`rm -rf /` now"))

    # ~/.agents/skills/ is OUTSIDE every worktree and holds ONE copy for the machine, installed
    # from whichever checkout last synced it — in practice the main one, since installing from a
    # slot is a write outside the crewmate's worktree and is banned. So from a slot this row
    # compares the SLOT's canonical copy against MAIN's installed copy: green while the slot has
    # not touched the skill, red the moment it does, and red for a reason that is not drift and
    # that the slot must not "fix". VERIFIED 2026-08-01 in this slot: it passed, because the
    # slot had not edited the skill — a row whose colour is decided by an unrelated edit is
    # exactly the kind that should not be reporting into a slot's verdict at all. In the main
    # checkout the requirement holds, the row runs, and a missing install is correctly red.
    r.check("installed SKILL.md is byte-identical to the canonical copy "
            "(twin drift, probe_twin's pattern)",
            lambda: (open(SKILL_INSTALLED).read() if os.path.exists(SKILL_INSTALLED) else "") == canon,
            f"canonical {len(canon)}B at {SKILL_CANON}", needs=MAIN_CHECKOUT)
except SystemExit:
    raise
except Exception:
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    ok = r.summary()
    sys.exit(0 if ok else 1)
