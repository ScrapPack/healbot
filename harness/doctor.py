"""Healbot preflight: what can THIS machine run, and is what it runs the real harness?

    python harness/doctor.py          (any Python >= 3.9; py/python/python3 all fine)

Exists because "works on the other machine" is a claim nobody can make from here: the
harness was built and measured on macOS, and docs/CLONE.md records what happened the first
time the suite ran in an environment it was not developed in (three probes reported success
having proven nothing). This file is the feedback loop for a second machine — every row is
a fact checked on the machine the command runs on, and the tier summary at the bottom says
which halves of the workflow THIS machine can actually carry, instead of leaving that to be
discovered one silent failure at a time.

Honesty rules, inherited from the rig: a check that cannot run is not a pass (SKIP names
why, and platform-impossible is different from missing); a FAIL is a fact about this
machine, not necessarily a defect in the repo. Stdlib only, no venv required — this is the
tool that tells you whether the venv exists.
"""

import json
import os
import platform
import shutil
import subprocess
import sys

HARNESS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HARNESS)

PASS, FAIL, WARN, SKIP = "PASS", "FAIL", "WARN", "SKIP"
ROWS = []


def row(status, name, detail=""):
    ROWS.append((status, name, detail))


def which(name):
    return shutil.which(name)


def run(cmd, cwd=ROOT):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
        return p.returncode, (p.stdout + p.stderr).strip()
    except FileNotFoundError:
        return None, "not found"
    except subprocess.TimeoutExpired:
        return None, "timeout"


def platform_kind():
    """darwin | wsl | linux | windows — WSL is Linux that can also see the Windows half."""
    if sys.platform == "darwin":
        return "darwin"
    if sys.platform.startswith("linux"):
        rel = platform.release().lower()
        return "wsl" if "microsoft" in rel else "linux"
    if sys.platform == "win32":
        return "windows"
    return sys.platform


KIND = platform_kind()


# -- repo and git ---------------------------------------------------------------------


def check_repo():
    if not os.path.isfile(os.path.join(ROOT, "HARNESS.md")):
        row(FAIL, "repo root", f"no HARNESS.md next to harness/ — doctor is at {HARNESS}, "
                               "which does not look like a healbot checkout")
        return False
    row(PASS, "repo root", ROOT)
    return True


def check_git():
    if not which("git"):
        row(FAIL, "git", "not on PATH — nothing else here works without it")
        return
    code, out = run(["git", "rev-parse", "--is-inside-work-tree"])
    if code != 0:
        row(FAIL, "git repo", out)
        return
    row(PASS, "git", "on PATH, inside a work tree")
    code, out = run(["git", "config", "core.hooksPath"])
    if out == "gate/hooks":
        row(PASS, "push gate wired", "core.hooksPath = gate/hooks")
    else:
        row(WARN, "push gate NOT wired",
            "pushes from this clone skip the gate — run: git config core.hooksPath gate/hooks")


def check_crlf():
    """The .gitattributes guarantee, verified on the working tree: a single CR in an
    executable script is how a Windows checkout dies at the shebang with no useful error."""
    code, out = run(["git", "ls-files", "-z"])
    if code != 0:
        row(SKIP, "CRLF scan", "git ls-files failed; scan not run")
        return
    bad = []
    for rel in out.split("\0"):
        if not rel or not (rel.endswith(".sh") or rel.endswith(".py") or rel.endswith("pre-push")):
            continue
        p = os.path.join(ROOT, rel)
        try:
            with open(p, "rb") as f:
                if b"\r" in f.read():
                    bad.append(rel)
        except OSError:
            continue
    if bad:
        row(FAIL, "CRLF in executable scripts", ", ".join(bad) +
            " — re-clone after .gitattributes, or: git checkout -- <file> with core.autocrlf=false")
    else:
        row(PASS, "line endings", "no CR bytes in any tracked .sh/.py/hook")


# -- environment traps ----------------------------------------------------------------


def check_env_traps():
    if os.environ.get("XDG_DATA_HOME"):
        row(FAIL, "XDG_DATA_HOME is set",
            "auth.json lives under it and OpenAI is on oauth — the harness rule is to never "
            "set it (HARNESS.md Traps). Unset it before running anything.")
    else:
        row(PASS, "XDG_DATA_HOME unset", "auth.json stays where the harness expects it")
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        inside = os.path.normpath(xdg).startswith(os.path.normpath(os.path.join(ROOT, "harness", "config")))
        note = "this shell IS a harness shell (env.sh sourced)" if inside else \
               "set to something other than the harness config — opencode in this shell reads THAT, not the harness"
        row(PASS if inside else WARN, "XDG_CONFIG_HOME", f"{xdg} — {note}")


# -- interpreters and tools -----------------------------------------------------------


def venv_python():
    for rel in ("venv/bin/python", "venv/Scripts/python.exe"):
        p = os.path.join(ROOT, ".carryover", "verified", rel)
        if os.path.exists(p):
            return p
    return None


def check_python():
    v = sys.version_info
    status = PASS if (v.major, v.minor) >= (3, 10) else WARN
    row(status, "python", f"{platform.python_version()} at {sys.executable}")
    vp = venv_python()
    if not vp:
        row(WARN, "rig venv not built",
            "gate + rig need it: python -m venv .carryover/verified/venv, then install pyte "
            "with that venv's pip (.carryover/verified/README.md)")
        return
    code, out = run([vp, "-c", "import pyte"])
    if code == 0:
        row(PASS, "rig venv", f"{os.path.relpath(vp, ROOT)} with pyte importable")
    else:
        row(FAIL, "rig venv broken", f"{os.path.relpath(vp, ROOT)}: import pyte -> {out}")


def check_tools():
    for name, why, missing in [
        ("bun", "runs opencode from source (fork/README.md)", WARN),
        ("node", "probe_turn_predicate + the checkout's lint gates", WARN),
        ("claude", "the Claude Code half of the harness", WARN),
    ]:
        if which(name):
            row(PASS, name, which(name))
        else:
            row(missing, f"{name} missing", why)
    if KIND == "windows":
        bash = which("bash") or next((p for p in (
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe") if os.path.exists(p)), None)
        if bash:
            row(PASS, "Git Bash", bash)
        else:
            row(FAIL, "Git Bash missing",
                "Git for Windows is the harness's shell on a PC: env scripts, git hooks, and "
                "Claude Code's hooks all run under it (docs/WINDOWS.md)")


# -- the checkout and the configs -----------------------------------------------------


def check_checkout():
    idx = os.path.join(ROOT, "opencode", "packages", "opencode", "src", "index.ts")
    if not os.path.exists(idx):
        row(WARN, "opencode/ checkout absent",
            "derived, gitignored, required for the TUI/grid/rig — reconstitute per fork/README.md")
        return
    row(PASS, "opencode/ checkout", "present")
    drift = []
    for base in ("packages", ".opencode"):
        top = os.path.join(ROOT, "fork", base)
        for dirpath, _dirnames, filenames in os.walk(top):
            for fn in filenames:
                src = os.path.join(dirpath, fn)
                rel = os.path.relpath(src, os.path.join(ROOT, "fork"))
                twin = os.path.join(ROOT, "opencode", rel)
                try:
                    with open(src, "rb") as a, open(twin, "rb") as b:
                        if a.read() != b.read():
                            drift.append(rel)
                except OSError:
                    drift.append(rel + " (missing in checkout)")
    if drift:
        row(FAIL, "fork overlay drift", ", ".join(sorted(drift)) +
            " — fork/ and the checkout disagree (fork/README.md 'Drift'); probe_twin.py is the full check")
    else:
        row(PASS, "fork overlay", "all overlay files byte-identical to the checkout")


def check_opencode_cli():
    """WHICH opencode a session gets, which is not a question the tiers below can ask.

    README's single-session form is `. harness/env.sh && opencode`, and that runs whatever
    is on PATH. TESTED 2026-08-02 on the 1.18.5 release: it carries the `diff-viewer` and
    `which-key` builtins and **zero** `healbot` strings, so `/healbot` does not exist on it
    — while the harness config still reaches it (the retirement plugin armed at the shipped
    180,000 gate on that same binary). A harness that works except for its headline screen
    is the wrong-belief shape this file exists to remove, so the row names both halves.

    Deliberately never a FAIL and deliberately not wired into the opencode tier: the fork
    path runs from source under bun (`harness/fleet.sh`), so a released binary is optional
    and its absence costs only the single-session convenience form.

    WHAT THIS ROW MAY NOT SAY (push-review finding on its first draft, and it was right): it
    called anything on PATH a RELEASED build, which is an unmeasured claim about a file — a
    `bun link` from the checkout puts a FORK build on PATH and would have been reported
    grid-less on the doctor's own authority, the exact wrong-belief shape three lines up. The
    one case that can be settled cheaply is settled: resolve the symlink chain and see
    whether it lands inside this repo's checkout. Everything else gets the CONDITIONAL — the
    grid is a fork builtin, so a binary not built from `opencode/` does not have it — which
    is true without measuring the bytes. `strings <bin> | grep healbot` is what would settle
    the rest, and reading 138 MB is not this file's job.
    """
    oc = which("opencode")
    fork = os.path.exists(os.path.join(ROOT, "opencode", "packages", "opencode", "src", "index.ts"))
    from_checkout = bool(oc) and os.path.realpath(oc).startswith(
        os.path.realpath(os.path.join(ROOT, "opencode")) + os.sep)
    if oc and from_checkout:
        row(PASS, "opencode CLI", f"{oc} — resolves INTO {os.path.join(ROOT, 'opencode')}, so it is a "
                                  "fork build and has /healbot")
    elif fork and oc:
        row(PASS, "opencode CLI", f"{oc} — does not resolve into opencode/, so `. harness/env.sh && "
                                  "opencode` runs a non-fork build and /healbot is a fork builtin. "
                                  "harness/fleet.sh runs the checkout from source, grid included")
    elif fork:
        row(PASS, "opencode CLI", "not on PATH — fine: harness/fleet.sh runs the fork from "
                                  "source under bun. `. harness/env.sh && opencode` needs one")
    elif oc:
        row(WARN, "opencode CLI without a checkout", f"{oc} — the harness config reaches it "
                                                     "(pin, compaction off, retirement), but /healbot is a fork "
                                                     "builtin; reconstitute per fork/README.md to get the grid")
    else:
        row(WARN, "no opencode at all", "no checkout and nothing on PATH — neither form of the "
                                        "opencode half can start (fork/README.md)")


def check_configs():
    oc = os.path.join(HARNESS, "config", "opencode", "opencode.jsonc")
    if os.path.isfile(oc) and os.path.getsize(oc) > 0:
        row(PASS, "opencode harness config", os.path.relpath(oc, ROOT))
    else:
        row(FAIL, "opencode harness config missing", oc)
    st = os.path.join(HARNESS, "claude", "settings.json")
    try:
        with open(st, encoding="utf-8") as f:
            json.load(f)
        row(PASS, "claude harness settings", os.path.relpath(st, ROOT) + " parses")
    except Exception as exc:  # noqa: BLE001 — any unreadable settings is the same finding
        row(FAIL, "claude harness settings", f"{st}: {exc}")


def check_claude_md():
    """The materialized crew-constraints file. Three honest states: symlink (macOS/Linux),
    in-sync copy (Windows), or drift/absence — and drift is the silent one."""
    target = os.path.join(HARNESS, "claude", "CLAUDE.md")
    canon = os.path.join(HARNESS, "claude", "crew-constraints.md")
    if os.path.islink(target):
        ok = os.readlink(target) == "crew-constraints.md"
        row(PASS if ok else FAIL, "crew constraints materialized",
            "symlink -> " + os.readlink(target))
    elif os.path.isfile(target):
        with open(target, "rb") as a, open(canon, "rb") as b:
            same = a.read() == b.read()
        if same:
            row(PASS, "crew constraints materialized", "copy, in sync (Windows shape)")
        else:
            row(FAIL, "crew constraints STALE",
                "CLAUDE.md is a copy that no longer matches crew-constraints.md — "
                "re-source harness/env.claude.sh (it refreshes drifted copies)")
    else:
        row(WARN, "crew constraints not materialized",
            "source harness/env.claude.sh once in this clone")


# -- platform-bound tiers -------------------------------------------------------------


def check_fleet_and_rig():
    if KIND == "windows":
        row(SKIP, "tmux fleet", "tmux has no native Windows port — the crew fleet runs under "
                                "WSL2 on a PC, by design (docs/WINDOWS.md)")
        row(SKIP, "rig pty", "the rig drives a real pty (term.py: pty/termios/fcntl) — "
                             "POSIX-only, run it under WSL2 on a PC (docs/WINDOWS.md)")
        return
    if which("tmux"):
        row(PASS, "tmux", which("tmux"))
    else:
        row(WARN, "tmux missing", "hb-fleet.sh (the claude crew fleet) needs it")
    try:
        import fcntl  # noqa: F401
        import pty  # noqa: F401
        import termios  # noqa: F401
        row(PASS, "rig pty", "pty/termios/fcntl importable")
    except ImportError as exc:
        row(FAIL, "rig pty", f"POSIX platform without pty support: {exc}")


def tier_summary():
    st = {name: s for s, name, _ in ROWS}

    def ok(*names):
        return all(st.get(n) == PASS for n in names)

    tiers = []
    # The crew-constraints check names its row for the state it found, so keying the guard on
    # one spelling only covered one of the two ways it can fail: a symlink pointing somewhere
    # other than crew-constraints.md FAILs under the "materialized" name and left this tier
    # reading READY over a red row. Match the family, not a spelling.
    crew_fail = any(s == FAIL and n.startswith("crew constraints") for s, n, _ in ROWS)
    claude_ok = ok("git", "claude", "claude harness settings") and not crew_fail
    tiers.append(("claude code workflow (env.claude.sh + settings pin)",
                  claude_ok, "needs git, claude CLI, settings.json, constraints in sync"))
    tiers.append(("opencode workflow (env.sh + fork TUI/grid)",
                  ok("bun", "opencode/ checkout", "opencode harness config"),
                  "needs bun + the reconstituted checkout (fork/README.md)"))
    if KIND == "windows":
        tiers.append(("crew fleet (tmux) and rig/suite (pty)", None,
                      "WSL2-only on a PC, by design — not measurable from native Windows"))
    else:
        tiers.append(("crew fleet (tmux)", ok("tmux"), "hb-fleet.sh"))
        tiers.append(("rig / free suite (pty + venv)", ok("rig venv", "rig pty"),
                      ".carryover/verified — plus the checkout for most probes"))
    tiers.append(("per-change gate (gate/gate.py)", ok("rig venv", "opencode/ checkout"),
                  "tier 1 is static but not checkout-free: probe_twin and the citation "
                  "resolver both read opencode/"))

    print("\n== what this machine can carry "
          f"({KIND}, {platform.platform()}) ==")
    for name, state, need in tiers:
        mark = {True: "READY", False: "NOT YET", None: "N/A  "}[state]
        print(f"  [{mark:7}] {name}\n            {need}")
    print("\n  local models: none configured in this repo — the Mac's local-model pin is "
          "machine state, deliberately absent on a PC (owner decision, docs/WINDOWS.md).")


def main():
    print(f"healbot doctor — {KIND} — repo {ROOT}\n")
    if check_repo():
        check_git()
        check_crlf()
        check_env_traps()
        check_python()
        check_tools()
        check_checkout()
        check_opencode_cli()
        check_configs()
        check_claude_md()
        check_fleet_and_rig()
    width = max(len(n) for _, n, _ in ROWS)
    for status, name, detail in ROWS:
        print(f"  [{status}] {name:<{width}}  {detail}")
    fails = [n for s, n, _ in ROWS if s == FAIL]
    tier_summary()
    if fails:
        print(f"\n{len(fails)} FAIL: {', '.join(fails)}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
