#!/usr/bin/env python3
"""Install the tracked skills onto this machine: the sync the twins never had.

harness/skills/<name>.md is the canonical half of each twin. Live sessions load the
installed half at ~/.agents/skills/<name>/SKILL.md (both harnesses, fork SKILL.MAP.md
sources 1-2), and Claude Code reaches that directory through a per-skill symlink in
whichever config root it is pointed at. There are TWO such roots on this machine and
until 2026-08-05 this installer only knew one: ~/.claude/skills for a default session,
and harness/claude/skills for anything launched through env.claude.sh, which redirects
CLAUDE_CONFIG_DIR. mirror_harness_root() below owns the second and carries the evidence.
Measured 2026-08-02: the installed healbot-traps served a stale body for two
days, in green, because nothing synced the halves. harness/doctor.py's skill-twins row
is the sweep for that; this script is the installer whose absence that row used to
report. The checker twins ride along: harness/skills/<name>-check.py installs as
<name>/check.py (plaincode and plainspec ship one today).

Direction is the incident's lesson and is never assumed. A missing installed half is
created. A divergent one is reported and left alone, because the 2026-08-02 incident
was repo-newer and the opposite happens the day someone edits an installed copy: a
diff decides, then --force records the repo-over-installed decision. Installed-newer
is a hand copy back to harness/skills/.

Exit 0: every half in the desired state. Exit 1: drift held, a conflicting link, or a
failed write. Exit 2: not run from a healbot checkout. Windows without Developer Mode
cannot symlink, so the ~/.claude surface falls back to a copied directory there and a
re-run refreshes it (docs/WINDOWS.md owns the platform story).
"""

import argparse
import filecmp
import os
import shutil
import sys

# One definition of "does this path resolve inside that root", shared with the doctor row
# that reports the same property, rather than two copies free to drift. Both files live in
# harness/, so sys.path[0] carries this import for any invocation of this script, and
# doctor.py imports nothing outside the stdlib and executes nothing at import time.
from doctor import resolves_under

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(REPO, "harness", "skills")
AGENTS = os.path.expanduser(os.path.join("~", ".agents", "skills"))
CLAUDE = os.path.expanduser(os.path.join("~", ".claude", "skills"))
HBCLAUDE = os.path.join(REPO, "harness", "claude", "skills")


def pairs():
    """(skill, source path, installed filename) for every tracked half."""
    out = []
    for f in sorted(os.listdir(CANON)):
        if not f.endswith(".md"):
            continue
        name = f[:-3]
        out.append((name, os.path.join(CANON, f), "SKILL.md"))
        chk = os.path.join(CANON, name + "-check.py")
        if os.path.isfile(chk):
            out.append((name, chk, "check.py"))
    return out


def put(src, dst, force):
    """One file into place, direction rules as in the module docstring."""
    if not os.path.isfile(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        return "installed"
    if filecmp.cmp(src, dst, shallow=False):
        return "in-sync"
    if force:
        shutil.copyfile(src, dst)
        return "forced repo over installed"
    return "DRIFT held: diff to pick a direction, then --force or hand-copy back"


def surface(name, link_root, target):
    """The <link_root>/<name> surface for a skill body at target. Returns (state,
    copy_dir): copy_dir is a real directory the caller must fill when a symlink cannot
    exist or already does not (a prior fallback), None when the symlink carries the
    surface. The per-file rows that follow a copy dir are where refresh-vs-DRIFT is
    decided; this state only names the surface kind.

    link_root became a parameter on 2026-08-05 for the second surface below; the default
    root's call passes exactly what this function used to hard-code."""
    link = os.path.join(link_root, name)
    if os.path.islink(link):
        if os.path.realpath(link) == os.path.realpath(target):
            return "link ok", None
        return "CONFLICT: links to %s, left alone" % os.path.realpath(link), None
    if os.path.isdir(link):
        return "copy dir", link
    if os.path.lexists(link):
        return "CONFLICT: exists and is not a directory or symlink, left alone", None
    os.makedirs(link_root, exist_ok=True)
    try:
        # target_is_directory: without it, Windows with Developer Mode creates a FILE
        # symlink at a directory target — unusable, reported "linked" (review finding,
        # c3dc440 push). POSIX ignores the flag.
        os.symlink(target, link, target_is_directory=True)
        return "linked", None
    except OSError:
        os.makedirs(link, exist_ok=True)
        return "copy dir (symlink unavailable)", link


def mirror_harness_root():
    """Give the claude harness's OWN config root the skills surface it never had.

    VERIFIED 2026-08-05: Claude Code builds the user skills directory as
    join(config_dir, "skills"), where config_dir is CLAUDE_CONFIG_DIR or ~/.claude, and
    unlike its `ide` lookup it adds NO fallback to the default root. env.claude.sh
    redirects CLAUDE_CONFIG_DIR at harness/claude, which carried no skills/ at all, so
    every harness session and every crewmate hb-fleet.sh ever spawned ran with none of
    them -- the four NEXT.md orders each session to invoke included. Evidence, with the
    free `claude plugin list` control that settled the same question for plugins:
    .scratch/daily-driver/research/09-config-dir-skill-resolution.md.

    Mirrors what the DEFAULT root exposes rather than the tracked twins alone, because the
    captain drives /wayfinder and the planning skills, which are installed on this machine
    but tracked elsewhere. So the source here is ~/.claude/skills, not CANON.

    harness/claude/.gitignore ignores that whole root, so the SKILL.md filenames this
    writes never reach gate.py's BANNED check. VERIFIED with git check-ignore before the
    first write; re-check it if that .gitignore ever narrows.

    The source is that root's ENTRIES, and their bodies must live outside both roots. A
    skill installed only under ~/.claude has nowhere else to point, and mirroring it wrote a
    link from the harness root into the DEFAULT root -- which is the arrangement ticket 10
    recorded as rejected, and which context-handoff held from this function's first run
    until 2026-08-05 (ticket 18). This refuses to write one, and reports one already on
    disk, rather than deleting it: dropping the entry would make the two roots carry
    different skill SETS, which the captain's 2026-08-05 direction rules out just as
    firmly. Both faults leave the repair to a human promoting the body to ~/.agents."""
    if not os.path.isdir(CLAUDE):
        print("  %-32s %s" % ("harness/claude/skills", "SKIPPED: no " + CLAUDE))
        return 0
    default_root = os.path.dirname(CLAUDE)
    bad = 0
    for name in sorted(os.listdir(CLAUDE)):
        src = os.path.join(CLAUDE, name)
        if not os.path.isdir(src):
            continue
        if resolves_under(src, default_root):
            bad += 1
            print("  %-32s %s" % ("harness/claude/skills/" + name,
                                  "REFUSED: its body is inside %s, so mirroring it would "
                                  "link this root into the default one. Move the body to "
                                  "%s/%s/ and re-point %s/%s at it, then re-run"
                                  % (default_root, AGENTS, name, CLAUDE, name)))
            continue
        state, copy_dir = surface(name, HBCLAUDE, os.path.realpath(src))
        bad += "CONFLICT" in state
        print("  %-32s %s" % ("harness/claude/skills/" + name, state))
        if copy_dir:
            shutil.copytree(os.path.realpath(src), copy_dir, dirs_exist_ok=True)
    return bad


def main():
    ap = argparse.ArgumentParser(
        description="Install harness/skills/ twins to ~/.agents and ~/.claude.")
    ap.add_argument("--force", action="store_true",
                    help="overwrite a divergent installed half with the repo half")
    force = ap.parse_args().force
    if not os.path.isdir(CANON):
        print("install-skills: no %s — not a healbot checkout shape" % CANON,
              file=sys.stderr)
        return 2
    rows = pairs()
    bad = 0
    for name, src, rel in rows:
        state = put(src, os.path.join(AGENTS, name, rel), force)
        bad += "DRIFT" in state
        print("  %-32s %s" % (name + "/" + rel, state))
    for name in sorted({r[0] for r in rows}):
        state, copy_dir = surface(name, CLAUDE, os.path.join(AGENTS, name))
        bad += "CONFLICT" in state
        print("  %-32s %s" % ("~/.claude/skills/" + name, state))
        if copy_dir:
            for pname, src, rel in rows:
                if pname == name:
                    state = put(src, os.path.join(copy_dir, rel), force)
                    bad += "DRIFT" in state
                    print("  %-32s %s" % ("  " + name + "/" + rel, state))
    bad += mirror_harness_root()
    print("install-skills: %d file(s) across %d skill(s); %d held or conflicting"
          % (len(rows), len({r[0] for r in rows}), bad))
    print("verify: python3 harness/doctor.py (the skill-twins row)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
