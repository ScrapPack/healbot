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

import json
import math
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
# reap the dead pane kill exists to reclaim. 68.
r = Results(expect=68, skip_max=2)


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
except SystemExit:
    raise
except Exception:
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    ok = r.summary()
    sys.exit(0 if ok else 1)
