"""Does the claude fleet harness hold its shape? Zero model turns, zero API credits.

Guards the Phase 13 cockpit build (docs/SHIP.md): the parity config dir, the fleet-state
hook's fail-open contract, hb-fleet.sh's five load-bearing tmux guardrails, and every
skill twin in harness/skills/ against its installed half. Every predicate that reads
source carries a mutation check — the same predicate re-run against a deliberately
corrupted copy, required to fail — because a probe that cannot go red is decoration (the
rig-assertion-discipline skill; probe_twin.py is the pattern source for the twin check).

The hook checks here are LIVE executions, not source reads: the hook's one prior defect
(the heredoc consuming the payload's stdin) produced a script that was syntactically
clean, exited 0, and wrote nothing — exactly the shape only a live happy-path check
catches.

  venv/bin/python probe_fleet_claude.py
"""

import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

from rig import MAIN_CHECKOUT, Env, Results

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
HARNESS = os.path.join(REPO, "harness")
CFG = os.path.join(HARNESS, "claude")
HOOK = os.path.join(CFG, "hooks", "fleet-state.sh")
FLEET = os.path.join(HARNESS, "hb-fleet.sh")
ENVSH = os.path.join(HARNESS, "env.claude.sh")
DOCTOR = os.path.join(HARNESS, "doctor.py")
SKILLS_DIR = os.path.join(HARNESS, "skills")
INSTALLED_SKILLS = os.path.expanduser("~/.agents/skills")
# The twin population is DISCOVERED (harness/skills/*.md), so a new twin joins the sweep
# with no edit here — plainspec arrived untracked mid-build and was covered before its
# first commit. The census floor below is the other half: these seven must exist, so a
# twin DELETED from the repo goes red here instead of silently leaving its installed
# copy loading forever.
CORE_TWINS = {"citation-hygiene", "firstmate", "healbot-traps", "paid-run-protocol",
              "phase-close", "rig-assertion-discipline", "tdd"}

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
# 33 through the 2026-08-01 environment-requirement work. The 2026-08-02 cockpit build adds
# eleven: nine for the auth preflight (four predicates, five mutation legs) and two for the
# re-runnable-`start` pane marker. 44. The 2026-08-02 skill-twin generalization (healbot-traps
# drifted for two days while only firstmate was guarded) replaces the four firstmate rows
# with eight population rows — census, frontmatter, shell-hole, identity, each with its
# mutation leg — plus two doctor-wiring rows. 50. The 2026-08-02 settings-migration finding
# (claude 2.1.220's one-time ladder rewrote the pin opus -> opus[1m] in a fresh worktree
# root, and the flipped value passed bool()) hardens the settings row to the pin VALUE and
# adds its mutation leg. 51. The same day's containment in hb_auth_state (the fleet's own
# detector call fired that migration in every unstamped root) adds its guard row and
# mutation leg: the merged floor both branches predicted. 53. Task 0's bring-up residue
# (2026-08-03, live crewmate on 2.1.220) adds six: the busy-before-ready arm order, the
# dialog-specific trust marker, and the version-shaped liveness arm, each with a mutation
# leg, plus a fixture row proving the arm swap rewrites source. 60. The 2026-08-03 operator
# walk (docs/E2E.md) adds five: the C-b ? popup geometry against the rendered card with two
# mutation legs, and the card naming its own exit key with one — the first `hb-fleet.sh
# start` run end to end showed the overlay opening on `kill`, its top 18 rows dropped. 65.
# The same walk's cleanup adds three: `kill` on a pane the fleet had already taken leaked
# tmux's own "can't find pane" under set -eu, so the branch is guarded now — with a mutation
# leg for an unguarded kill-pane and one for reaching at pane_dead, which would refuse to
# reap the dead pane kill exists to reclaim. 68. The 2026-08-03 open-items close (docs/E2E.md
# section 7) adds eleven: kill settling a slot crewmate's pool lease with two mutation legs
# (finding 9), the manifest's slot discriminator with one, the grid pane's full-window split
# with one (finding 11), and the two defects the close's own live test measured — spawn
# re-ensuring the crew window kill can destroy, and spawn's post-lease failure paths
# releasing the lease they just took — each with a mutation leg. 79. The item-B close
# (finding 8) adds two: spawn adopting the pane pid onto the lease, with its leg. 81. The
# item-A close (finding 1) adds two: doctor's exit reading the tier verdicts, with its
# leg. 83. The push review of the close (2026-08-03) found two predicates a mutant could
# survive — the slot conjunct anchored to guard lines instead of the heredoc argv, and
# the release position read without the branch boundary — and hardening the first splits
# its leg in two. 84. The 2026-08-04 close of item E's named residual adds eleven: `down`
# settling every slot lease the fleet still holds, in the order crew-then-leases-then-
# session; the mutation legs in DOWN_LEGS, each asserting the conjuncts it names; a row
# holding the defect leg's crew kill TRUE so it cannot pass on the wrong clause; and a
# COMPUTED coverage row. The review walked this one item down a ladder, every rung a claim
# wider than the thing behind it: the fix dead on the captain's path, two legs dying on a
# conjunct neither named, a conjunct with no leg under a description saying all had one, a
# wrong leg-to-conjunct ratio, and a floor written one short. The coverage claim is
# computed rather than written because of that ladder, and the rungs are not counted here
# for the same reason docs/E2E.md stopped counting them: a tally in prose is a number with
# nothing computing it. 95. The 2026-08-05 tall-pane finding (capture-pane pads to the pane
# HEIGHT and the CLI paints top-down, so `state`'s raw `tail -20` classified a solo
# crewmate unreadable at 49 rows and idle at 23, same marker line, while peek stripped
# blanks the whole time) adds eleven: the shared-reader conjuncts with six legs and a
# computed coverage row, plus three rows run LIVE against a scratch tmux pane: the
# fixture, the shipped reader's extracted body seeing the sentinel through the padding,
# and the recovered pre-fix read missing it. The live pair exists because the trap is
# tmux's own padding, which no source read can prove; tmux joins the environment
# requirements, so skip_max rises 2 -> 5. 106. Ticket 18 (2026-08-05) adds nine: four
# driving doctor's fault function over scratch roots that hold a real puncture, a real
# traversal and a set divergence — one of them the negative control the count-only row it
# replaces never had — three on the row being a FAIL the claude tier reads, and two on the
# installer refusing to write the puncture back. The defect they guard is a row that
# reported PASS at "28/28 surfaced" for as long as the puncture existed, which is the
# a-count-is-not-an-outcome shape this file's own header names. 116.
r = Results(expect=116, skip_max=5)


def sh_n(path):
    return subprocess.run(["sh", "-n", path], capture_output=True).returncode == 0


def settings_ok(d):
    # The pin VALUE, not presence. bool(d.get("model")) survived the one rewrite that has
    # actually happened: claude 2.1.220's one-time settings migration (any config root whose
    # untracked .claude.json lacks migrationVersion >= 13) rewrites exactly the alias "opus"
    # to "opus[1m]" — the 1M-context variant, premium-priced above 200K input — on the first
    # config-loading invocation in that root, which is every fresh worktree, pool slot, and
    # clone. TESTED 2026-08-02: `auth status` and `config list` both fire it and stamp the
    # marker; `--version` does not; sonnet/haiku/opus[1m]/claude-opus-5 pins pass through
    # byte-identical, so the mapping is the alias "opus" alone — exactly what the 2026-08-01
    # model policy pins here. A deliberate pin change updates this literal and settings.json
    # in one commit (probe_turn_growth's pin assertion is the precedent, opencode side).
    return d.get("autoCompactEnabled") is False and d.get("model") == "opus"


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
    r.check("settings pin the model VALUE (opus) and turn autoCompact off",
            settings_ok(settings))
    mut = dict(settings)
    mut["autoCompactEnabled"] = True
    r.check("MUTATION: autoCompact flipped on is caught", not settings_ok(mut))
    mut = dict(settings)
    mut["model"] = "opus[1m]"
    r.check("MUTATION: the CLI migration's rewrite (opus -> opus[1m]) is caught",
            not settings_ok(mut),
            "this exact flip happened 2026-08-02 in a fresh worktree root and passed bool()")
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
            "gate.py:220 bans the real name anywhere in the tracked tree; this is the half git carries")
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

    # -- the three screen markers and the liveness arms, MEASURED 2026-08-03 -------------
    # Task 0's bring-up residue, pinned against claude 2.1.220 with a live crewmate. Each
    # row below guards a fact that was SUSPECTED before that session and is measured now.
    def busy_before_ready(s):
        # The busy footer CONTAINS the ready marker ("… bypass permissions on … esc to
        # interrupt …"), so a screen case that tests ready first reports a working
        # crewmate as idle. Arm order is the whole guarantee.
        #
        # EVERY such block is checked, not the first one found: the file holds three
        # `case "$SCREEN" in` blocks and the first is the spawn loop, which has no busy
        # arm at all. A first-match predicate read that block and went red against
        # correct code — caught here because the mutation leg passed while the live leg
        # failed, which is the shape of a broken predicate rather than a broken subject.
        bodies = re.findall(r'case "\$SCREEN" in(.*?)esac', s, re.S)
        both = [b for b in bodies
                if "HB_BUSY_MARKER" in b and "HB_READY_MARKER" in b]
        return bool(both) and all(
            b.find("HB_BUSY_MARKER") < b.find("HB_READY_MARKER") for b in both)

    r.check("the screen case tests BUSY before READY (the busy footer carries both)",
            busy_before_ready(src),
            "MEASURED 2026-08-03: the idle footer reads `bypass permissions on (shift+tab "
            "to cycle) · ← for agents` and the busy footer inserts `esc to interrupt` into "
            "that same line, so ready-first would classify every working crewmate idle")
    # The swap targets the ARM LINES, not the first name in the file: a plain
    # replace(..., 1) rewrites the variable DECLARATIONS at the top and leaves the case
    # block correctly ordered, so the mutation passed while mutating nothing (caught by
    # this leg going green against a subject it had not changed).
    BUSY_ARM = '*"$HB_BUSY_MARKER"*)  SCR="busy";;'
    READY_ARM = '*"$HB_READY_MARKER"*) SCR="idle";;'
    swapped = (src.replace(BUSY_ARM, "@@ARM@@")
               .replace(READY_ARM, BUSY_ARM)
               .replace("@@ARM@@", READY_ARM))
    r.check("fixture: the arm swap actually rewrote the source",
            swapped != src and BUSY_ARM in swapped and READY_ARM in swapped,
            "a mutation that edits nothing proves nothing; this row fails if the arm "
            "text drifts out from under the two literals above")
    r.check("MUTATION: swapping the busy and ready arms is caught",
            not busy_before_ready(swapped))

    def trust_marker_specific(s):
        # The default must not be a word ordinary replies contain. MEASURED as a real
        # false positive: with the old bare "trust" default, an idle crewmate replying
        # "I trust this result." classified as trust-dialog — blocked on a human decision.
        m = re.search(r'HB_TRUST_MARKER="\$\{HB_TRUST_MARKER:-([^}]*)\}"', s)
        return bool(m) and len(m.group(1).split()) >= 3

    r.check("the trust marker is a dialog-specific phrase, not a common word",
            trust_marker_specific(src),
            "the 2.1.220 dialog's own menu item is `Yes, I trust this folder`; the crew "
            "constraints file uses the bare word twice, so the prose that tripped the old "
            "default is prose this harness ships")
    r.check("MUTATION: reverting the trust marker to a bare word is caught",
            not trust_marker_specific(
                re.sub(r'(HB_TRUST_MARKER="\$\{HB_TRUST_MARKER:-)[^}]*(\}")',
                       r"\1trust\2", src)))

    def version_arm(s):
        # A live crewmate's pane_current_command is the CLI VERSION (`2.1.220`), not
        # `claude`, so without a version-shaped arm every healthy crewmate read
        # `ambiguous` — the state firstmate escalates instead of trusting.
        #
        # The arm must live INSIDE the liveness case and map to alive. An earlier draft
        # paired the pattern with a bare `'LIVE="alive"' in s`, which the pre-existing
        # *claude*|node|bun arm already satisfied: the conjunct could not fail, so a
        # version arm reading `dead`, or the pattern demoted to a comment, passed both
        # legs (review finding from the 40a669b push).
        blk = re.search(r'ROW" \| awk .\{print \$3\}.\)" in(.*?)esac', s, re.S)
        if not blk:
            return False
        arm = re.search(r'\[0-9\]\*\.\[0-9\]\*\.\[0-9\]\*\)\s*LIVE="(\w+)"',
                        blk.group(1))
        return bool(arm) and arm.group(1) == "alive"

    r.check("the liveness case has a version-shaped arm for the renamed process",
            version_arm(src),
            "MEASURED 2026-08-03: `tmux list-panes -F '#{pane_current_command}'` returned "
            "`2.1.220` for a working crewmate, and the composite read `ambiguous` while "
            "the screen and hook channels both said idle")
    r.check("MUTATION: dropping the version arm is caught",
            not version_arm(src.replace("[0-9]*.[0-9]*.[0-9]*)", "__none__)")))

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

    # -- the auth preflight (new 2026-08-02) ---------------------------------------
    # Every predicate below reads source, so every one carries a mutation. The behaviour
    # they guard was MEASURED on claude 2.1.220 the day they were written: `claude auth
    # status` exits 1 with no credential and 0 with one, honours CLAUDE_CONFIG_DIR, and does
    # NOT read .claude.json — a config dir holding a copied profile with a complete
    # oauthAccount block still exits 1.
    def fn_body(s, name):
        # The closing brace is matched at the function's OWN indent (backreference), because
        # some of these are defined inside a case branch and close on `  }` — anchoring to
        # column 0 silently returned "" for those, and every predicate reading an empty body
        # is a predicate that cannot go red.
        m = re.search(r"\n([ \t]*)" + re.escape(name) + r"\(\)\s*\{.*?\n\1\}", s, re.S)
        return m.group(0) if m else ""

    def asks_the_binary(s):
        # Two clauses, one per way this can rot. It must ASK the binary, and it must not
        # degrade into reading the profile — the profile read is green on exactly the state
        # the guard exists to catch, which makes it the tempting and wrong simplification.
        # Body-anchored: the comment block above the function names both `auth status` and
        # `.claude.json`, so a file-wide match would stay green on a gutted function.
        body = fn_body(s, "hb_auth_state")
        return ("auth status" in body
                and ".claude.json" not in body and "oauthAccount" not in body)

    r.check("the auth detector asks `claude auth status`, and never reads the profile file",
            asks_the_binary(src))
    r.check("MUTATION: gutting the auth-status call is caught",
            not asks_the_binary(src.replace('"$HB_CLAUDE" auth status', "true #", 1)))
    r.check("MUTATION: a profile read added alongside it is caught",
            not asks_the_binary(src.replace(
                'if "$HB_CLAUDE" auth status >/dev/null 2>&1; then arc=0; else arc=1; fi',
                'if "$HB_CLAUDE" auth status >/dev/null 2>&1; then arc=0; else arc=1; fi\n'
                '  grep -q oauthAccount "$CLAUDE_CONFIG_DIR/.claude.json"', 1)))

    def contains_the_migration(s):
        # The containment guard for the CLI's one-time settings migration (HARNESS.md
        # Traps): the detector call fires the migration in an unstamped root, so
        # hb_auth_state must snapshot the settings bytes BEFORE the CLI call and
        # byte-restore AFTER it, keeping the stamp. ORDERING is the claim, and the two cp
        # directions are distinct literals, so a snapshot that never restores (or a guard
        # moved off the detector's path entirely) reads as missing. Body-anchored for the
        # same reason as asks_the_binary: the comment block above the function narrates
        # the whole mechanism.
        body = fn_body(s, "hb_auth_state")
        take = body.find('cp "$stf" "$snap"')   # snapshot: settings -> temp
        give = body.find('cp "$snap" "$stf"')   # byte-restore: temp -> settings
        call = body.find("auth status")
        return 0 <= take < call < give and "cmp -s" in body

    r.check("the detector contains the CLI settings migration: snapshot before the call, "
            "byte-restore after, stamp kept",
            contains_the_migration(src),
            "without this, the fleet's first CLI call in any fresh worktree, pool slot, or "
            "clone rewrites the tracked settings.json mid-session (measured 2026-08-02)")
    r.check("MUTATION: a guard whose byte-restore is gutted is caught",
            not contains_the_migration(src.replace('cp "$snap" "$stf"', ": ", 1)))

    def spawn_block(s):
        m = re.search(r"\nspawn\)\n.*?\n  ;;\n", s, re.S)
        return m.group(0) if m else ""

    def auth_before_lease(s):
        # ORDERING, and the workload that could violate it is a --slot spawn: the guard must
        # refuse BEFORE pool.py hands out a worktree, or a spawn that cannot possibly come up
        # still costs the pool a lease. Read from the spawn block alone — `pool.py` also
        # appears in two comments elsewhere in the file.
        block = spawn_block(s)
        guard, lease = block.find("hb_auth_guard"), block.find("pool.py")
        return guard > 0 and lease > 0 and guard < lease

    r.check("spawn refuses a signed-out root BEFORE it leases a pool worktree",
            auth_before_lease(src))
    r.check("MUTATION: the guard moved after the lease is caught",
            not auth_before_lease(src.replace("  hb_auth_guard || exit 2\n", "", 1).replace(
                '  [ -d "${DIR:-}" ]', "  hb_auth_guard || exit 2\n  [ -d \"${DIR:-}\" ]", 1)))

    def usage_range_complete(s):
        # hb_header() prints a LINE RANGE of this file's own header, so inserting a command
        # line shifts the selector paragraph down and a stale end bound silently truncates its
        # last line. Measured twice while building: 22 -> 23 for `preflight`, 23 -> 25 for
        # `start`/`help`, both by hand. The stakes rose when the range stopped feeding only
        # `usage` — the C-b ? popup and the bridge pane's captain card render it too, so a
        # short range now truncates the cockpit's own help, not just an error message.
        m = re.search(r"hb_header\(\) \{ sed -n '4,(\d+)p'", s)
        if not m:
            return False
        end = int(m.group(1))
        lines = s.split("\n")
        if end > len(lines):
            return False
        printed = lines[3:end]  # sed counts from 1; slice from 0
        return (any(line.startswith("#   preflight") for line in printed)
                and printed[-1].rstrip().endswith("is the supported form."))

    r.check("hb_header() still prints the whole header: the preflight line AND the last line "
            "of the selector paragraph", usage_range_complete(src))
    r.check("MUTATION: an end bound one line short is caught",
            not usage_range_complete(re.sub(
                r"(hb_header\(\) \{ sed -n '4,)(\d+)(p')",
                lambda m: m.group(1) + str(int(m.group(2)) - 1) + m.group(3), src, count=1)))

    def card_lines(s):
        """The card exactly as `hb_help` renders it: the header line range with its comment
        prefix stripped, then the static key-map heredoc. Derived from source, never copied,
        so it tracks whatever the header actually holds."""
        m = re.search(r"hb_header\(\) \{ sed -n '4,(\d+)p'", s)
        body = re.search(r"cat <<'EOF'\n(.*?)\nEOF\n", s, re.S)
        if not m or not body:
            return None
        header = [re.sub(r"^#+ ?", "", ln) for ln in s.split("\n")[3:int(m.group(1))]]
        return header + body.group(1).split("\n")

    def card_fits_popup(s):
        """The other half of the range check above. That one asserts the card's CONTENT is
        whole; this asserts the BOX is big enough to show it. A tmux popup does not scroll —
        overflow is dropped off the top with no indication — so a card that outgrows its
        geometry is silently truncated at exactly the end an operator reads first.
        MEASURED 2026-08-03 at the shipped -w 84 -h 28: 45 rendered rows into 26, and the
        overlay opened on `kill`. Wrapping is computed as a terminal wraps (hard, at the
        column), not as textwrap does.

        SCOPE, stated so the row is not read as more than it is: this checks the DECLARED
        geometry. tmux clamps a popup to the client's terminal, so a terminal smaller than
        the declared box truncates the card again and no source check can see that. The
        binding's own comment carries the minimum.
        """
        card = card_lines(s)
        g = re.search(r"display-popup -w (\d+) -h (\d+)", s)
        if card is None or not g:
            return False
        inner_w, inner_h = int(g.group(1)) - 2, int(g.group(2)) - 2  # the border costs one each side
        if inner_w < 1:
            return False
        rendered = sum(max(1, math.ceil(len(ln) / inner_w)) for ln in card)
        return max(len(ln) for ln in card) <= inner_w and rendered <= inner_h

    r.check("the C-b ? popup is big enough to render the whole command card",
            card_fits_popup(src))
    r.check("MUTATION: the pre-fix geometry (-w 84 -h 28) is caught",
            not card_fits_popup(src.replace("display-popup -w 96 -h 36",
                                            "display-popup -w 84 -h 28", 1)))
    r.check("MUTATION: a card grown past the box by one line is caught",
            not card_fits_popup(src.replace(
                "\nCensus is `ls`, never the status bar",
                "\n" + "x" * 40 + "\n" * 3 + "Census is `ls`, never the status bar", 1)))

    def card_names_its_exit(s):
        # The popup is modal and `q` does not close it (TESTED twice, tmux 3.7, 2026-08-03:
        # q reaches the finished command's pane and the box stays up; only Escape closes).
        # A card with no way out is the cockpit's own trap, so the `?` row carries the key.
        card = card_lines(s)
        if card is None:
            return False
        return any(ln.strip().startswith("?") and "esc" in ln.lower() for ln in card)

    r.check("the card's `?` row names the key that closes it", card_names_its_exit(src))
    r.check("MUTATION: dropping the exit hint is caught",
            not card_names_its_exit(src.replace("this card (esc closes)", "this card", 1)))

    def kill_frames_a_missing_pane(s):
        """`kill` must survive its own kill-pane failing. Under `set -eu` a bare
        `t kill-pane` ends the script on tmux's "can't find pane: %N", which names a pane id
        rather than the crewmate — MEASURED 2026-08-03 killing a crewmate that `down` had
        already taken. It must NOT reach for the pane-dead helper the way send and brief do:
        that helper is true for dead-or-missing, and a dead pane is precisely what kill
        reclaims.

        COMMENTS ARE STRIPPED FIRST, and that is not tidiness. The first version of this
        predicate read the raw branch and went red against the correct fix, because the fix's
        own comment explains which helper it avoids — the check was measuring prose that
        mentions the helper, not code that calls it. A predicate that its own explanation can
        flip is the decoration this file exists to keep out.
        """
        branch = s.split("\nkill)", 1)[-1].split("\ndown)", 1)[0]
        code = "\n".join(ln for ln in branch.split("\n") if not ln.lstrip().startswith("#"))
        return ("if ! t kill-pane" in code and "exit 2" in code
                and "pane_dead" not in code)

    r.check("kill frames a pane that is already gone instead of leaking tmux's error",
            kill_frames_a_missing_pane(src))
    r.check("MUTATION: an unguarded kill-pane is caught",
            not kill_frames_a_missing_pane(src.replace("if ! t kill-pane -t \"$P\" 2>/dev/null; then",
                                                       "t kill-pane -t \"$P\"; if false; then", 1)))
    r.check("MUTATION: reaching for pane_dead here — which would refuse to reap a corpse — is caught",
            not kill_frames_a_missing_pane(src.replace(
                '  if ! t kill-pane -t "$P" 2>/dev/null; then',
                '  pane_dead "$P" && exit 2\n  if ! t kill-pane -t "$P" 2>/dev/null; then', 1)))

    def kill_settles_the_lease(s):
        """Finding 9's close (docs/E2E.md): kill's SUCCESS path must attempt a PLAIN pool
        release for a --slot crewmate — plain because the pool refuses while the slot holds
        work and keeps the lease on refusal, so the call is safe by the pool's own design —
        conditionally scoped (--if-owner) to this run's lease, and only AFTER the pane is
        dead. Comments are stripped for the same reason the finding-15 predicate strips
        them: the comment above the call names both the verb and the flag.

        The success path is found STRUCTURALLY, not by raw position: the already-gone
        branch ends at its `exit 2`, and the release must sit after that terminator. The
        first version compared raw find() offsets, which a mutant moving the release INTO
        the already-gone branch — the exact placement that branch's own comment forbids —
        satisfied in green (push-review finding, 2026-08-03)."""
        branch = s.split("\nkill)", 1)[-1].split("\ndown)", 1)[0]
        code = "\n".join(ln for ln in branch.split("\n") if not ln.lstrip().startswith("#"))
        gone, _, success = code.partition("exit 2")
        return ("t kill-pane" in gone and 'pool.py" release' in success
                and 'pool.py" release' not in gone
                and '--if-owner "$HB_RUN"' in success)

    def _mutate_kill(s, old, new):
        # Scope a replacement to the kill branch. spawn's release_slot_on_failure calls
        # the same verb with the same flag EARLIER in the file, so a whole-file
        # first-occurrence replace corrupted that copy and left kill's intact — both legs
        # below FAILED against correct code until scoped (caught by the 79-row floor run,
        # 2026-08-03, the same session that wrote them).
        head, sep, tail = s.partition("\nkill)")
        return head + sep + tail.replace(old, new, 1)

    r.check("kill settles a slot crewmate's pool lease after the pane dies",
            kill_settles_the_lease(src),
            "MEASURED 2026-08-03 (docs/E2E.md finding 9): kill left slot-1 leased to a dead "
            "crewmate; the manual repair is now the automatic attempt, refusal-safe")
    r.check("MUTATION: a kill that never calls release is caught",
            not kill_settles_the_lease(_mutate_kill(src, 'pool.py" release', 'pool.py" status')))
    r.check("MUTATION: an unconditional release (no --if-owner) is caught",
            not kill_settles_the_lease(_mutate_kill(src, ' --if-owner "$HB_RUN"', '')))

    def manifest_records_the_slot(s):
        # The release path above is gated on a persisted discriminator: a --slot spawn's
        # dir IS a pool worktree, but the manifest row never said so before this field.
        # Old rows lack it; manifest_get exits 3 on a missing field, read as not-a-slot.
        # Both conjuncts anchor to the heredoc INVOCATION, not to any '"$USE_SLOT"'
        # occurrence: three guard lines in the spawn block carry that token too, so the
        # first version's loose conjunct passed a mutant that hardcoded the argv to "0" —
        # every row slot=0, kill never releasing, in green (push-review finding).
        block = spawn_block(s)
        return '"slot": int(use_slot)' in block and '"$USE_SLOT" <<' in block

    r.check("spawn's manifest row records whether the dir is a leased pool slot",
            manifest_records_the_slot(src),
            "kill's release attempt is gated on this field")
    r.check("MUTATION: dropping the slot field from the row is caught",
            not manifest_records_the_slot(src.replace('"slot": int(use_slot)', "", 1)))
    r.check("MUTATION: an argv hardcoded to \"0\" (every row not-a-slot) is caught",
            not manifest_records_the_slot(src.replace('"$USE_SLOT" <<', '"0" <<', 1)))

    def down_settles_the_leases(s):
        """Finding 9's OTHER half (docs/E2E.md section 7E): kill learned to settle its own
        crewmate's lease while `down` went on taking the whole session and leaving every
        slot crewmate's lease held. The fix is an ORDER, crew then leases then session, and
        this predicate reads all three positions.

        The RELEASE must precede kill-session. That is not tidiness: kill-session is SIGHUP
        and the captain's seat is the bridge shell inside the session, so a release loop
        after it is killed with the pane running it. MEASURED 2026-08-04 from the bridge
        pane on the first version of this close: session gone, slot-1 still leased, and
        every static leg here green over it. The advisory review found it; this row's
        earlier form had the wrong order LOCKED IN.

        The release must also follow the crew WINDOW's death, because release restores the
        worktree and a reset under a live process is the one thing the pool cannot undo.
        Killing the crew window rather than the session is what leaves the bridge, and so
        the script, alive to finish.

        The stated limit, because a green here is narrower than it looks: no static leg can
        see a SIGHUP. What these rows lock in is the order the live test proved, and the
        live test is the evidence, recorded in docs/E2E.md section 7E.

        Comments are stripped first for the finding-15 reason: this branch's comment names
        kill-session above the command, so an unstripped partition would split at the prose
        and read the ordering off the explanation rather than off the code. Stated without
        a count, because the earlier form of this docstring carried one and it was wrong
        (the advisory review's second finding on the 2d7d7f3 push).

        pane_dead is the wrong helper and its absence is asserted: it answers dead-OR-
        missing, which drops exactly the corpses that still hold leases (remain-on-exit is
        on), where a pane tmux still lists is one kill never took."""
        return all(_down_order(s).values())

    def _down_order(s):
        """The conjuncts, separately, so a mutation leg can name the ONE it flips and prove
        it did not die on a different clause. Written after the review found both new legs
        deleting the same literal and therefore both dying on has_crew_kill rather than on
        the positions they were named for: two legs, one reason, and the conjunct each
        claimed to exercise never exercised at all. That is this suite's signature defect,
        found inside the guard written to close it."""
        branch = s.split("\ndown)", 1)[-1].split("\n*) usage", 1)[0]
        code = "\n".join(ln for ln in branch.split("\n") if not ln.lstrip().startswith("#"))
        # Anchored to `t kill-…`, the tmux helper INVOCATION, not to the bare verb. The
        # branch's own down-notice echo carries the words "kill-session is SIGHUP", and
        # partitioning on the verb split there instead of at the command, which read every
        # later statement as dead code. Comment-stripping does not reach it: this one is a
        # string, not a comment. Third appearance of prose contaminating a positional read
        # in this file, after finding 15's guard and this row's own docstring.
        pre_session, sep, post_session = code.partition("t kill-session")
        census, csep, post_crew = pre_session.partition("t kill-window")
        tail = post_session.split("\n", 1)[1] if "\n" in post_session else ""
        return {
            "has_session_kill": sep != "",
            "has_crew_kill": csep != "",
            "census_first": "pane_exists" in census,
            "no_pane_dead": "pane_dead" not in code,
            "release_after_crew": 'pool.py" release' in post_crew,
            "release_not_in_census": 'pool.py" release' not in census,
            "release_before_session": 'pool.py" release' not in post_session,
            "nothing_after_session": all(ln.strip() in ("", ";;") for ln in tail.split("\n")),
            "scoped": '--if-owner "$HB_RUN"' in post_crew,
        }

    def _mutate_down(s, old, new):
        # Scoped for _mutate_kill's reason, one branch further up: spawn and kill both call
        # the same verb with the same flag EARLIER in the file, so an unscoped
        # first-occurrence replace mutates one of THEM and leaves down's copy intact, a
        # leg that passes against correct code.
        head, sep, tail = s.partition("\ndown)")
        return head + sep + tail.replace(old, new, 1)

    def _pushed_defect_shape(s):
        """The 2d7d7f3 source shape, reconstructed: kill-session moved back ahead of the
        release loop while the crew-window kill STAYS. Built by moving the real line rather
        than by deleting a literal, so has_crew_kill survives and the leg can only be
        caught by the position conjuncts, which is the whole point of it."""
        moved = _mutate_down(s, '  t kill-session -t "$HB_RUN" 2>/dev/null || true\n', "")
        return _mutate_down(moved,
                            '  t kill-window -t "$HB_RUN:crew" 2>/dev/null || true\n',
                            '  t kill-window -t "$HB_RUN:crew" 2>/dev/null || true\n'
                            '  t kill-session -t "$HB_RUN" 2>/dev/null || true\n')

    r.check("down settles every slot lease the fleet still holds: crew, then leases, "
            "then session",
            down_settles_the_leases(src),
            "docs/E2E.md section 7E: kill settled its own crewmate's lease and down left "
            "every one of them held")
    # (label, mutant source, the conjuncts this leg ASSERTS). The named keys are asserted
    # individually, so no leg can pass by dying on a clause it did not claim. A mutation is
    # free to flip OTHER conjuncts as a side effect and several do — the defect shape and
    # the crew-kill leg each flip four — which is harmless for exactly that reason, and is
    # why the leg count is not a coverage claim. The coverage row below COMPUTES the claim
    # instead of stating it: successive review rounds found this description wider than the
    # legs standing behind it (a leg per conjunct, then one to one), so it stops being a
    # description. A conjunct added to _down_order with no leg goes red there.
    DOWN_LEGS = [
        ("a down that never calls release",
         _mutate_down(src, 'pool.py" release', 'pool.py" status'),
         ["release_after_crew"]),
        ("an unconditional release, no --if-owner",
         _mutate_down(src, ' --if-owner "$HB_RUN"', ''),
         ["scoped"]),
        ("the measured defect, the release left after kill-session has SIGHUPed the caller",
         _pushed_defect_shape(src),
         ["release_before_session"]),
        ("a down that never kills the session at all",
         _mutate_down(src, 't kill-session -t "$HB_RUN"', 't list-sessions'),
         ["has_session_kill"]),
        ("a down that never kills the crew window, so release resets a tree under a live "
         "crewmate",
         _mutate_down(src, 't kill-window -t "$HB_RUN:crew"', 't list-windows -t "$HB_RUN"'),
         ["has_crew_kill"]),
        ("a release hoisted into the census, ahead of both kills",
         _mutate_down(src, '  HELD=""\n',
                      '  HELD=""\n  "$VENVPY" "$FLEET_ROOT/pool.py" release "$D" '
                      '--if-owner "$HB_RUN"\n'),
         ["release_not_in_census"]),
        ("a statement left after kill-session, dead on the captain's path",
         _mutate_down(src, '  t kill-session -t "$HB_RUN" 2>/dev/null || true\n',
                      '  t kill-session -t "$HB_RUN" 2>/dev/null || true\n'
                      '  echo "hb-fleet: this line never runs from the bridge pane"\n'),
         ["nothing_after_session"]),
        ("censusing with pane_dead, which drops lease-holding corpses",
         _mutate_down(src, 'pane_exists "$P"', 'pane_dead "$P"'),
         ["census_first", "no_pane_dead"]),
    ]
    for _label, _mutant, _keys in DOWN_LEGS:
        _v = _down_order(_mutant)
        r.check("MUTATION: %s is caught (%s)" % (_label, ", ".join(_keys)),
                all(not _v[k] for k in _keys))

    r.check("the defect leg keeps the crew kill, so it cannot pass on the wrong conjunct",
            _down_order(_pushed_defect_shape(src))["has_crew_kill"],
            "the review's finding on the 8d20353 push: two legs deleting the same literal "
            "both died on has_crew_kill rather than on the positions they named")
    r.check("every conjunct down_settles_the_leases decides on has a leg asserting it",
            {k for _, _, ks in DOWN_LEGS for k in ks} == set(_down_order(src)),
            "COMPUTED, not written: has_session_kill shipped with no leg once, under a "
            "description that said every conjunct had one")

    def spawn_reensures_crew_window(s):
        # kill-pane on the LAST crewmate destroys the now-empty crew window, and spawn's
        # split refusal then misread the missing window as a full one. MEASURED
        # 2026-08-03: the first spawn after such a kill dead-ended on "crew window is
        # full". spawn re-runs the same ensure line `up` uses.
        block = spawn_block(s)
        return "grep -qx crew" in block and "new-window -d" in block

    def _mutate_spawn(s, old, new):
        # Scope a replacement to the spawn block: the ensure line also exists in `up`,
        # and a whole-file first-occurrence replace would mutate that copy instead.
        head, sep, tail = s.partition("\nspawn)")
        return head + sep + tail.replace(old, new, 1)

    r.check("spawn re-ensures the crew window (kill on the last crewmate destroys it)",
            spawn_reensures_crew_window(src))
    r.check("MUTATION: dropping spawn's ensure line is caught",
            not spawn_reensures_crew_window(_mutate_spawn(src, "grep -qx crew", "true #")))

    def spawn_failures_settle_the_lease(s):
        # A spawn that dies AFTER the pool lease must release it — MEASURED 2026-08-03:
        # a refused split leaked slot-1 to a crewmate that never existed. The shape is one
        # helper and exactly five call sites (the dir refusal, the transcript
        # computation, both split refusals, and the boot death), so the count is 6 with
        # the definition. EQUALITY, not a floor: a sixth call site would mean someone
        # wired the ready-wait timeout, where the crewmate is alive in its pane and a
        # release would reset the tree under a live process.
        block = spawn_block(s)
        return block.count("release_slot_on_failure") == 6

    r.check("spawn's post-lease failure paths settle the lease they just took",
            spawn_failures_settle_the_lease(src),
            "definition + dir refusal + transcript failure + both split refusals + the "
            "boot death; the timeout keeps it")
    r.check("MUTATION: a failure path that keeps the lease is caught",
            not spawn_failures_settle_the_lease(_mutate_spawn(
                src, "      release_slot_on_failure\n      exit 1", "      exit 1")))

    def spawn_adopts_the_pane_pid(s):
        # E2E finding 8's fleet half: acquire cannot know the holder because the pane
        # does not exist yet, so spawn records the pane's root pid on the lease AFTER
        # the split, and pool.py status's liveness note becomes true exactly when the
        # crewmate dies instead of always.
        block = spawn_block(s)
        return block.find('pool.py" adopt') > block.find("select-pane") > 0 \
            and "#{pane_pid}" in block

    r.check("spawn adopts the pane's root pid onto the slot lease after the split",
            spawn_adopts_the_pane_pid(src),
            "MEASURED 2026-08-03 (docs/E2E.md finding 8): the recorded acquirer pid died "
            "in seconds, so status called every live crewmate's slot abandoned")
    r.check("MUTATION: a spawn that never adopts is caught",
            not spawn_adopts_the_pane_pid(_mutate_spawn(src, 'pool.py" adopt',
                                                        'pool.py" noop')))

    def grid_pane_full_width(s):
        # The session route's sidebar is the only renderer of a session id and it is gated
        # on width > 120 (upstream session route; the traps registry has the row). A half
        # split gave the grid 110 of the session's 220 columns (docs/E2E.md finding 11),
        # and attach re-clamps panes to the client, so only a full-window split (-f) tracks
        # the client's own width and clears the gate on any 121+ column terminal.
        return "hb_add_pane grid -vf " in s

    r.check("the grid pane splits FULL WINDOW WIDTH, clearing the sidebar's >120 gate",
            grid_pane_full_width(src),
            "TESTED 2026-08-03 at 220x50: the half split rendered no session id at 110 "
            "columns; the full-window split gives the grid the whole window's width")
    r.check("MUTATION: reverting to the half split (-v) is caught",
            not grid_pane_full_width(src.replace("hb_add_pane grid -vf ",
                                                 "hb_add_pane grid -v ", 1)))

    def panes_are_idempotent(s):
        # `start` runs `up` on every invocation, including against a live fleet, so an
        # unguarded split adds a second nvim and a second grid pane per run. The guard is a
        # pane-scoped @hb_role marker checked BEFORE the split — ordering, so the assertion is
        # an ordering one. Negative control MEASURED 2026-08-02: clearing @hb_role on a live
        # nvim pane and re-running `up --nvim` produced the duplicate, which is what makes the
        # marker load-bearing rather than incidentally correct.
        body = fn_body(s, "hb_add_pane")
        check, split = body.find("hb_has_role"), body.find("split-window")
        return check > 0 and split > 0 and check < split and "@hb_role" in body

    r.check("optional bridge panes check their marker BEFORE splitting, so `start` is "
            "re-runnable", panes_are_idempotent(src))
    r.check("MUTATION: dropping the marker check is caught",
            not panes_are_idempotent(src.replace('    hb_has_role "$role" && return 0\n', "", 1)))

    def auth_row_gates_the_tier(s):
        # A doctor row nothing reads is a decoration with a good name. The consequence of a
        # signed-out root is the claude tier reading NOT YET, and that only happens while the
        # row's name is in claude_ok's list.
        return ('"harness claude auth"' in s
                and bool(re.search(r'claude_ok = ok\([^)]*"harness claude auth"[^)]*\)', s)))

    doc = open(DOCTOR).read()
    r.check("doctor's auth row is wired into the claude tier, not merely printed",
            auth_row_gates_the_tier(doc))
    r.check("MUTATION: dropping the row from claude_ok is caught",
            not auth_row_gates_the_tier(doc.replace(', "harness claude auth")', ")", 1)))

    # -- skill twins: harness/skills/*.md vs ~/.agents/skills/<name>/SKILL.md ------
    # Generalized 2026-08-02 from the firstmate-only check, after the incident it could not
    # see: healbot-traps.md gained two trap entries in the repo while the installed copy
    # served the stale body for two days, in green, to every live session — BOTH harnesses
    # load ~/.agents/skills (fork SKILL.MAP.md sources 1-2, the .agents copy winning name
    # collisions). The guarded specimen held while the population drifted; guard the
    # population.
    twins = sorted(fn[:-3] for fn in os.listdir(SKILLS_DIR) if fn.endswith(".md"))
    r.check("skill-twin census: every core twin is present in harness/skills/",
            CORE_TWINS <= set(twins), f"found {twins}")
    r.check("MUTATION: a census missing a core twin is caught",
            not (CORE_TWINS <= set(twins) - {"firstmate"}))

    bodies = {name: open(os.path.join(SKILLS_DIR, name + ".md")).read() for name in twins}

    def loadable(name, s):
        # What the loaders need: frontmatter fences, a name matching the stem (the installed
        # path ~/.agents/skills/<name>/ is derived from it), a description to trigger on.
        return s.startswith("---") and f"name: {name}" in s and "description:" in s

    bad_front = [n for n in twins if not loadable(n, bodies[n])]
    r.check("every twin carries loadable frontmatter (name matches its file stem, "
            "description present)", not bad_front,
            f"offenders: {bad_front}" if bad_front else f"{len(twins)} twins")
    r.check("MUTATION: a stem-mismatched name is caught",
            not loadable("firstmate", bodies["tdd"]))

    def no_shell_hole(s):
        return not re.search(r"!\s*`", s)

    holes = [n for n in twins if not no_shell_hole(bodies[n])]
    r.check("no twin body contains a !`cmd` shell-substitution pattern "
            "(the env.sh:63-68 hole class)", not holes,
            f"offenders: {holes}" if holes else f"{len(twins)} twins")
    r.check("MUTATION: an injected !`cmd` is caught",
            not no_shell_hole(bodies[twins[0]] + "\nrun !`rm -rf /` now"))

    # ~/.agents/skills/ is OUTSIDE every worktree and holds ONE copy for the machine, installed
    # from whichever checkout last synced it — in practice the main one, since installing from a
    # slot is a write outside the crewmate's worktree and is banned. So from a slot this row
    # compares the SLOT's canonical copies against MAIN's installed copies: green while the slot
    # has not touched a skill, red the moment it does, and red for a reason that is not drift
    # and that the slot must not "fix" (the firstmate-era note, VERIFIED 2026-08-01, unchanged
    # by the generalization). In the main checkout the requirement holds, the row runs, and a
    # missing install is correctly red.
    def installed_matches(name, canon, root=INSTALLED_SKILLS):
        p = os.path.join(root, name, "SKILL.md")
        return os.path.exists(p) and open(p).read() == canon

    r.check("every twin's installed SKILL.md is byte-identical to its repo copy "
            "(twin drift, probe_twin's pattern; doctor's `skill twins` row is the "
            "any-machine half)",
            lambda: all(installed_matches(n, bodies[n]) for n in twins),
            f"{len(twins)} twins vs {INSTALLED_SKILLS}", needs=MAIN_CHECKOUT)
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "x"))
        with open(os.path.join(td, "x", "SKILL.md"), "w") as f:
            f.write("body")
        r.check("MUTATION: the identity comparator passes a faithful copy, fails a "
                "one-byte drift, fails an absent install (no machine state read)",
                installed_matches("x", "body", root=td)
                and not installed_matches("x", "bodyx", root=td)
                and not installed_matches("absent", "body", root=td))

    def twin_family_gates_both_tiers(s):
        # Same decoration hazard as the auth row above, doubled: twin drift degrades BOTH
        # workflows, so the doctor's family-matched FAIL must reach both tier verdicts.
        # Family, not name — the row has three state-named spellings (tier_summary's crew
        # constraints comment records why).
        return (bool(re.search(r'twin_fail = any\(s == FAIL and n\.startswith\("skill twin"\)', s))
                and s.count("not twin_fail") >= 2)

    r.check("doctor's skill-twin family gates BOTH workflow tiers, not merely printed",
            twin_family_gates_both_tiers(doc))
    r.check("MUTATION: dropping the twin gate from one tier is caught",
            not twin_family_gates_both_tiers(doc.replace(" and not twin_fail", "", 1)))

    def exit_reads_the_tiers(s):
        # docs/E2E.md finding 1: doctor exited 0 whenever no row was FAIL, so on a fresh
        # clone `doctor && next` read green while four of five tiers printed NOT YET. The
        # exit is three-state now and the middle state must come from the TIER verdicts:
        # tier_summary returns them, main branches on False (NOT YET) — None, the
        # platform-impossible N/A, deliberately does not count.
        return ("return [state for _, state, _ in tiers]" in s
                and "any(state is False for state in tier_states)" in s
                and "sys.exit(2)" in s)

    r.check("doctor's exit reads the tier verdicts: 0 ready, 1 FAIL, 2 NOT YET",
            exit_reads_the_tiers(doc),
            "the tier block was always the honest surface; the exit code now reads it")
    r.check("MUTATION: an exit that bypasses the tier verdicts is caught",
            not exit_reads_the_tiers(doc.replace(
                "any(state is False for state in tier_states)", "False", 1)))

    # -- the redirected root must not reach into the default one (2026-08-05) ------
    # Ticket 18. harness/claude/skills/context-handoff was a symlink into ~/.claude/skills,
    # the arrangement ticket 10 recorded as rejected in those words, and doctor's row
    # reported PASS at "28/28 surfaced" for as long as it existed: a COUNT, which no value
    # the workload can produce turns red. The row now reports faults, and the faults are
    # computed by a function taking both roots as arguments, so these rows drive the SHIPPED
    # predicate over scratch roots holding a real puncture rather than reading its source.
    spec = importlib.util.spec_from_file_location("hb_doctor", DOCTOR)
    hbdoc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hbdoc)

    def roots(td):
        """default root, mirror, and a canonical source outside BOTH — the real shape.

        x  clean:     both roots link at the canonical body.
        p  puncture:  the body lives in the default root, so the mirror links into it.
                      This is context-handoff exactly.
        t  traversal: the mirror links at the DEFAULT root's entry, which links on to the
                      canonical body. realpath lands outside ~/.claude and the coupling is
                      the same, which is the near miss repairing p produces by accident.
        """
        canon, default, mirror = (os.path.join(td, n) for n in ("canon", "default", "mirror"))
        for n in ("x", "t"):
            os.makedirs(os.path.join(canon, n))
        os.makedirs(os.path.join(default, "skills"))
        os.makedirs(mirror)
        os.makedirs(os.path.join(default, "skills", "p"))
        for n in ("x", "t"):
            os.symlink(os.path.join(canon, n), os.path.join(default, "skills", n))
        os.symlink(os.path.join(canon, "x"), os.path.join(mirror, "x"))
        os.symlink(os.path.join(default, "skills", "p"), os.path.join(mirror, "p"))
        os.symlink(os.path.join(default, "skills", "t"), os.path.join(mirror, "t"))
        return default, mirror

    with tempfile.TemporaryDirectory() as td:
        default, mirror = roots(td)
        want, have, missing, extra, punctures = hbdoc.config_root_skill_faults(default, mirror)
        r.check("the faults function names the mirror entries that reach into the default "
                "root, and only those",
                punctures == ["p", "t"] and want == have == {"p", "t", "x"},
                f"punctures={punctures} want={sorted(want)} have={sorted(have)}")
        # The negative control the count-only row never had: the clean entry is the same
        # shape (a symlink to a directory, surfaced identically) and must NOT be reported,
        # or the predicate is a tautology over every mirror entry.
        r.check("NEGATIVE CONTROL: an entry linked at a canonical source outside both roots "
                "is not a puncture, so the predicate is not true of every entry",
                "x" not in punctures and not missing and not extra)
        r.check("the traversal case is caught by chain_reaches and MISSED by realpath alone, "
                "which is why the shipped predicate is not realpath",
                hbdoc.chain_reaches(os.path.join(mirror, "t"), default)
                and not hbdoc.resolves_under(os.path.join(mirror, "t"), default))

    with tempfile.TemporaryDirectory() as td:
        default, mirror = roots(td)
        os.remove(os.path.join(mirror, "x"))
        os.makedirs(os.path.join(mirror, "z"))
        _, _, missing, extra, _ = hbdoc.config_root_skill_faults(default, mirror)
        r.check("set divergence is reported in BOTH directions: the captain's direction is "
                "that the roots carry the same skill SET, and only `missing` was checked",
                missing == ["x"] and extra == ["z"])

    def puncture_row_is_fail_and_gates_the_tier(s):
        # The decoration hazard the auth and twin rows above are guarded against: a fault
        # the row prints but no tier reads changes nothing a human sees. FAIL, and a name
        # inside the family root_fail matches.
        return (bool(re.search(
                    r'row\(FAIL, "claude config-root skills reach into the default root"', s))
                and bool(re.search(
                    r'root_fail = any\(s == FAIL and n\.startswith\("claude config-root '
                    r'skills"\)', s))
                and "not root_fail" in s)

    r.check("doctor's puncture row is a FAIL and gates the claude tier, not merely printed",
            puncture_row_is_fail_and_gates_the_tier(doc),
            "TESTED both ways 2026-08-05 on this machine's real roots: exit 1 with the tier "
            "NOT YET while context-handoff punctured, exit 0 after the body moved to "
            "~/.agents and both roots were pointed at it")
    r.check("MUTATION: demoting the puncture row to a WARN is caught",
            not puncture_row_is_fail_and_gates_the_tier(doc.replace(
                'row(FAIL, "claude config-root skills reach into the default root"',
                'row(WARN, "claude config-root skills reach into the default root"', 1)))
    r.check("MUTATION: dropping the root-fault gate from the claude tier is caught",
            not puncture_row_is_fail_and_gates_the_tier(
                doc.replace(" and not root_fail", "", 1)))

    def installer_refuses_a_cross_root_body(s):
        # doctor reports the fault; the installer is what would otherwise recreate it on the
        # next run. Refuse and report, never delete: dropping the entry would make the two
        # roots carry different SETS, which the same direction rules out.
        body = s[s.find("def mirror_harness_root"):]
        return ("resolves_under(src, default_root)" in body
                and "REFUSED" in body
                and body.find("resolves_under(src, default_root)") < body.find("surface(name"))

    inst = open(os.path.join(HARNESS, "install-skills.py")).read()
    r.check("install-skills refuses to mirror a skill whose body lives in the default root, "
            "BEFORE it would link one", installer_refuses_a_cross_root_body(inst),
            "TESTED 2026-08-05: exit 1 naming context-handoff and the promotion remedy, "
            "27 other entries untouched")
    r.check("MUTATION: dropping the refusal lets the puncture be rewritten, and is caught",
            not installer_refuses_a_cross_root_body(
                inst.replace("resolves_under(src, default_root)", "False", 1)))

    # -- the screen reader: strip the padding, THEN tail (2026-08-05) --------------
    # capture-pane -p pads its output to the pane HEIGHT and the CLI paints top-down,
    # so a bare `tail -N` on a tall, mostly empty pane returns padding and none of the
    # render. MEASURED 2026-08-05 on a solo crewmate holding the crew window alone: at
    # 49 rows the ready marker sat on line 17 and `state` classified unreadable off
    # twenty blank lines; the same pane at 23 rows read idle, same marker line. peek
    # stripped blanks before tailing the whole time; state diverged by omitting the
    # strip. Same defect family as the help-card popup rows above: a variable-size
    # render read through a fixed-size window. The repair is ONE reader, screen_tail,
    # and these conjuncts hold every classification read onto it. The submit verify was
    # the last raw tail, kept while the echo risk (a successful submit echoes its text
    # into the transcript) was unmeasured; a live two-submit measurement (2026-08-05,
    # .carryover/verified/hb/submit-verify-20260805/) kept the echo never nearer than
    # six painted lines above the pane bottom — two-plus clear of a stripped 3-line
    # window at every frame — on both a 49-row and a 17-row pane, so the verify joined
    # screen_tail and the census now pins ZERO raw tails, so one cannot grow back
    # quietly anywhere.
    def _screen_readers(s):
        """The conjuncts, separately, so each leg names the one it flips (_down_order's
        pattern). The census reads comment-stripped code for the finding-15 reason: the
        submit-verify comment narrates the raw tail it replaced."""
        body = fn_body(s, "screen_tail")
        code = "\n".join(ln for ln in s.split("\n") if not ln.lstrip().startswith("#"))
        state_b = code.partition("\nstate)")[2].partition("\nsend)")[0]
        send_b = code.partition("\nsend)")[2].partition("\nbrief)")[0]
        peek_b = code.partition("\npeek)")[2].partition("\noccupancy)")[0]
        raw_tails = [ln for ln in code.split("\n")
                     if "capture-pane" in ln and "| tail" in ln and "grep -v" not in ln]
        return {
            "helper_strips_then_tails": bool(re.search(
                r"capture-pane[^\n|]*\|\s*grep -v '\^\[\[:space:\]\]\*\$'\s*\|\s*tail",
                body)),
            "state_classifies_screen_tail":
                'SCREEN="$(screen_tail "$P" 20' in state_b,
            "send_gate_reads_screen_tail":
                'SCREEN="$(screen_tail "$P" 20)"' in send_b,
            "peek_reads_screen_tail": 'screen_tail "$P"' in peek_b,
            "corpse_dump_reads_screen_tail":
                'screen_tail "$PANE" 15' in spawn_block(s),
            "submit_verify_reads_screen_tail":
                'case "$(screen_tail "$P" 3)"' in send_b,
            "no_raw_tails": len(raw_tails) == 0,
        }

    def _mutate_arm(s, arm, old, new):
        # Scoped like _mutate_spawn and _mutate_down: state's and send's screen_tail
        # calls begin identically, so an unscoped first-occurrence replace mutates
        # whichever arm comes first and leaves the named one intact, a leg that passes
        # against correct code.
        head, sep, tail = s.partition("\n%s)" % arm)
        return head + sep + tail.replace(old, new, 1)

    r.check("every screen read including the submit verify goes through screen_tail "
            "(strip padding, THEN tail); the raw-tail census is ZERO",
            all(_screen_readers(src).values()),
            "MEASURED 2026-08-05 twice: state misread a 49-row solo pane off padding, "
            "and live submits kept the echo two-plus painted lines clear of the "
            "stripped window at every frame (submit-verify-20260805/REPORT.md)")
    SCREEN_LEGS = [
        ("the pre-fix state read, a raw tail -20 of the padded capture",
         _mutate_arm(src, "state",
                     'SCREEN="$(screen_tail "$P" 20 2>/dev/null || true)"',
                     'SCREEN="$(t capture-pane -p -t "$P" 2>/dev/null | tail -20 '
                     '|| true)"'),
         ["state_classifies_screen_tail", "no_raw_tails"]),
        ("a send busy gate reverted to its raw tail",
         _mutate_arm(src, "send",
                     'SCREEN="$(screen_tail "$P" 20)"',
                     'SCREEN="$(t capture-pane -p -t "$P" | tail -20)"'),
         ["send_gate_reads_screen_tail", "no_raw_tails"]),
        ("a peek grown back its own inline pipeline, correct today and free to diverge",
         _mutate_arm(src, "peek",
                     'screen_tail "$P" "${2:-25}"',
                     "t capture-pane -p -t \"$P\" | grep -v '^[[:space:]]*$' "
                     "| tail -\"${2:-25}\""),
         ["peek_reads_screen_tail"]),
        ("a boot-corpse dump back on the raw tail that prints fifteen blanks",
         _mutate_arm(src, "spawn",
                     'screen_tail "$PANE" 15 >&2',
                     't capture-pane -p -t "$PANE" | tail -15 >&2'),
         ["corpse_dump_reads_screen_tail", "no_raw_tails"]),
        ("the submit verify back on its pre-routing raw tail, the line the 2026-08-05 "
         "live measurement retired",
         _mutate_arm(src, "send",
                     'case "$(screen_tail "$P" 3)" in',
                     'case "$(t capture-pane -p -t "$P" | tail -3)" in'),
         ["submit_verify_reads_screen_tail", "no_raw_tails"]),
        ("a helper that tails the padded capture BEFORE stripping, the pre-fix window "
         "wearing the strip as decoration",
         src.replace("| grep -v '^[[:space:]]*$' | tail -\"${2:-25}\"",
                     "| tail -\"${2:-25}\" | grep -v '^[[:space:]]*$'", 1),
         ["helper_strips_then_tails"]),
        ("a helper with the strip deleted outright",
         src.replace(" | grep -v '^[[:space:]]*$'", "", 1),
         ["helper_strips_then_tails"]),
    ]
    for _label, _mutant, _keys in SCREEN_LEGS:
        _v = _screen_readers(_mutant)
        r.check("MUTATION: %s is caught (%s)" % (_label, ", ".join(_keys)),
                all(not _v[k] for k in _keys))
    r.check("every conjunct _screen_readers decides on has a leg asserting it",
            {k for _, _, ks in SCREEN_LEGS for k in ks} == set(_screen_readers(src)),
            "COMPUTED, not written (the down rows' precedent)")

    # The counterfactual, run LIVE: the trap is tmux's own padding, which a source read
    # can pin but never prove. A scratch server on a private socket hosts one 80x49
    # pane whose process paints sixteen filler lines and a sentinel, the measured
    # solo-crewmate geometry (sentinel on row 17, everything below it padding). The
    # shipped reader is executed from its EXTRACTED body, not a retyped copy, so what
    # runs is what ships; the pre-fix read is the recovered pre-fix line verbatim.
    # Zero credits: the pane runs sh, and the server dies in the finally. TESTED
    # 2026-08-05 by hand first: the padded capture is 49 lines, the raw tail-20 holds
    # zero sentinel hits, the stripped read ends on the sentinel, and the state verb
    # reads idle at 49 and at 23 rows against a live scratch manifest.
    TMUX_BIN = Env(
        "tmux-available",
        "a tmux binary is on PATH, so a scratch server can host the tall-pane fixture "
        "(strictly weaker than the checks: they need the capture to actually pad)",
        lambda: shutil.which("tmux") is not None,
    )
    SENTINEL = "HB-PROBE-TALL-PANE-SENTINEL"
    _fx = {}

    def _tmx(*args):
        return subprocess.run(["tmux", "-L", _fx["sock"], *args],
                              capture_output=True, text=True)

    def _screen_fixture():
        if "raw" in _fx:
            return _fx
        _fx["sock"] = "hb-probe-%d" % os.getpid()
        paint = ('i=1; while [ $i -le 16 ]; do echo "filler $i"; i=$((i+1)); done; '
                 'echo "%s"; sleep 120' % SENTINEL)
        _tmx("new-session", "-d", "-s", "fix", "-x", "80", "-y", "49", paint)
        _fx["pane"] = _tmx("list-panes", "-t", "fix", "-F", "#{pane_id}").stdout.strip()
        for _ in range(50):
            _fx["full"] = _tmx("capture-pane", "-p", "-t", _fx["pane"]).stdout
            if SENTINEL in _fx["full"]:
                break
            time.sleep(0.1)
        stub = 't() { tmux -L \'%s\' "$@"; }\n' % _fx["sock"]
        shipped = (stub + fn_body(src, "screen_tail")
                   + "\nscreen_tail '%s' 20\n" % _fx["pane"])
        _fx["shipped"] = subprocess.run(["sh", "-c", shipped],
                                        capture_output=True, text=True).stdout
        prefix = (stub + "P='%s'\n" % _fx["pane"]
                  + 'SCREEN="$(t capture-pane -p -t "$P" 2>/dev/null | tail -20 '
                    '|| true)"\nprintf %s "$SCREEN"\n')
        _fx["raw"] = subprocess.run(["sh", "-c", prefix],
                                    capture_output=True, text=True).stdout
        return _fx

    # No try/finally around the cleanup: probe_rig_contract requires every `finally` in
    # a rig to end on the verdict exit, so an auxiliary cleanup finally is banned shape.
    # A crash between these rows leaks the scratch server for at most the fixture's own
    # sleep: when it ends, the last session dies and the server exits with it.
    r.check("live fixture: the tall pane paints the sentinel at all (guards the "
            "absence claim below against an empty capture)",
            lambda: SENTINEL in _screen_fixture()["full"], needs=TMUX_BIN)
    r.check("live: the SHIPPED reader, body extracted from source, sees the "
            "sentinel through the padding",
            lambda: SENTINEL in _screen_fixture()["shipped"], needs=TMUX_BIN)
    r.check("live MUTATION, the tall-pane case: the recovered pre-fix raw tail -20 "
            "misses the same sentinel on the same pane",
            lambda: SENTINEL not in _screen_fixture()["raw"], needs=TMUX_BIN)
    if "sock" in _fx:
        _tmx("kill-server")
except SystemExit:
    raise
except Exception:
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    ok = r.summary()
    sys.exit(0 if ok else 1)
