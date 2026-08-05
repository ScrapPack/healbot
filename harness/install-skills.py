#!/usr/bin/env python3
"""Install the tracked skills onto this machine: the sync the twins never had.

harness/skills/<name>.md is the canonical half of each twin. Live sessions load the
installed half at ~/.agents/skills/<name>/SKILL.md (both harnesses, fork SKILL.MAP.md
sources 1-2), and Claude Code reaches that directory through a ~/.claude/skills/<name>
symlink. Measured 2026-08-02: the installed healbot-traps served a stale body for two
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

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANON = os.path.join(REPO, "harness", "skills")
AGENTS = os.path.expanduser(os.path.join("~", ".agents", "skills"))
CLAUDE = os.path.expanduser(os.path.join("~", ".claude", "skills"))


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


def surface(name):
    """The ~/.claude/skills/<name> surface. Returns (state, copy_dir): copy_dir is a
    real directory the caller must fill when a symlink cannot exist or already does
    not (a prior fallback), None when the symlink carries the surface. The per-file
    rows that follow a copy dir are where refresh-vs-DRIFT is decided; this state
    only names the surface kind."""
    target = os.path.join(AGENTS, name)
    link = os.path.join(CLAUDE, name)
    if os.path.islink(link):
        if os.path.realpath(link) == os.path.realpath(target):
            return "link ok", None
        return "CONFLICT: links to %s, left alone" % os.path.realpath(link), None
    if os.path.isdir(link):
        return "copy dir", link
    if os.path.lexists(link):
        return "CONFLICT: exists and is not a directory or symlink, left alone", None
    os.makedirs(CLAUDE, exist_ok=True)
    try:
        # target_is_directory: without it, Windows with Developer Mode creates a FILE
        # symlink at a directory target — unusable, reported "linked" (review finding,
        # c3dc440 push). POSIX ignores the flag.
        os.symlink(target, link, target_is_directory=True)
        return "linked", None
    except OSError:
        os.makedirs(link, exist_ok=True)
        return "copy dir (symlink unavailable)", link


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
        state, copy_dir = surface(name)
        bad += "CONFLICT" in state
        print("  %-32s %s" % ("~/.claude/skills/" + name, state))
        if copy_dir:
            for pname, src, rel in rows:
                if pname == name:
                    state = put(src, os.path.join(copy_dir, rel), force)
                    bad += "DRIFT" in state
                    print("  %-32s %s" % ("  " + name + "/" + rel, state))
    print("install-skills: %d file(s) across %d skill(s); %d held or conflicting"
          % (len(rows), len({r[0] for r in rows}), bad))
    print("verify: python3 harness/doctor.py (the skill-twins row)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
