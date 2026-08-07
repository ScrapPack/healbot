#!/usr/bin/env python3
"""plaincode-check: the scriptable half of harness/skills/plaincode.md.

The skill file is the spec (installed twin: ~/.agents/skills/plaincode/SKILL.md, this
checker alongside as check.py). Where a rule's test is mechanical it runs here, through
ruff, and the finding is a VIOLATION. Where a rule takes judgment the checker prints the
JUDGE checklist and never fails the exit code, plainspec-check's contract exactly.

    python3 plaincode-check.py FILE...        both layers, findings + the JUDGE checklist
    python3 plaincode-check.py --layout FILE  the PEP 8 layer alone (rule 1)
    python3 plaincode-check.py --selftest     every fixture, fire and clean legs both

Exit codes follow the gate's lattice (gate/GATE.MAP.md, exit codes): 0 clean of
violations (JUDGE flags allowed), 1 at least one violation, 2 usage, 3 ruff absent or
ruff itself broken, the declared cannot-measure refusal. A missing or unreadable INPUT
file surfaces as ruff's own E902 finding and exits 1 with the rest. The engine is ruff because the gate's
own lint row already runs ruff on every changed Python file (gate/gate.py lint()), so the
dependency is one the repo has already accepted, and adopting the same selects repo-wide
is a one-file decision recorded in docs/PLAINCODE.md, deliberately not taken here.

Deviations and known limits, kept honest in one place:
- PLR2004 (magic values) is deliberately ABSENT from the mechanized selects. Measured
  2026-08-03: 95 of the repo's 214 slop-layer findings are PLR2004, and most are probe
  assertion literals where the number IS the documented fixture (exit lattices, floors).
  A gate that flags the house evidence style teaches people to ignore the gate. The rule
  survives as judgment J1: a number that appears twice gets one owner.
- PLR0917 is excluded: preview-classified in some ruff versions, and PLR0913 already
  bounds the argument count. The two selects below must parse on the PATH ruff the gate
  uses (0.15.0 at measurement time).
- The width is 100, measured against the repo (p95 = 98), not PEP 8's 79. The choice and
  its counts live in docs/PLAINCODE.md; changing it here without changing the spec is
  the drift this file's twin arrangement exists to prevent.
- Findings are ruff's, so a `# noqa` with a reason silences a row here too, the same
  escape the gate's lint row honors. A bare noqa without a reason is judgment J4's
  business.
"""

import json
import shutil
import subprocess
import sys

WIDTH = "100"
# Rule 1, the PEP 8 layer: layout, whitespace, imports-at-top. E501 arms at WIDTH.
LAYOUT = "E,W"
# Rules 2-6, the slop layer: dead code (F401/F841 and kin), unused arguments (ARG),
# commented-out code (ERA), complexity and size budgets (C901, PLR091x), and the
# say-it-shorter family (SIM).
SLOP = "F,ARG,ERA,SIM,C901,PLR0911,PLR0912,PLR0913,PLR0915"

JUDGE = [
    "J1 one owner per fact: a threshold, path, or magic number that appears twice gets "
    "one named owner; pointers everywhere else (the prose-copy rule, applied to code)",
    "J2 inline single-use indirection: a helper with one caller earns its name or "
    "becomes its body — count the callers before keeping the layer",
    "J3 no speculative generality: no parameter, branch, or abstraction for a caller "
    "that does not exist; the burden of proof is on the abstraction",
    "J4 comments carry WHY and evidence, never WHAT: a comment restating its line is "
    "slop; a comment with a date, a measurement, or a file:line is load-bearing",
    "J5 deletion is the first fix: when a rule fires, ask whether the code can GO "
    "before asking how it can conform",
]


def find_ruff():
    return shutil.which("ruff")


def run_ruff(ruff, select, paths, stdin_text=None, stdin_name=None):
    """-> (findings, hard_error). Findings are ruff's JSON rows. ruff's exit contract is
    0 clean and 1 findings, JSON on stdout either way; any other exit means ruff ITSELF
    broke (usage error, unloadable config) with EMPTY stdout and the reason on stderr —
    which `json.loads(p.stdout or "[]")` alone would launder into a clean run. The
    returncode gate below is the repair."""
    cmd = [ruff, "check", "--no-cache", "--line-length", WIDTH,
           "--select", select, "--output-format", "json"]
    if stdin_text is not None:
        cmd += ["--stdin-filename", stdin_name or "stdin.py", "-"]
        p = subprocess.run(cmd, input=stdin_text, capture_output=True, text=True)
    else:
        p = subprocess.run([*cmd, *paths], capture_output=True, text=True)
    if p.returncode not in (0, 1):
        return [], ((p.stderr or p.stdout).strip() or f"ruff exited {p.returncode}")[:300]
    try:
        return json.loads(p.stdout or "[]"), None
    except ValueError:
        return [], (p.stderr or p.stdout).strip()[:300]


def report(findings, label):
    for f in sorted(findings, key=lambda f: (f.get("filename", ""),
                                             f.get("location", {}).get("row", 0))):
        loc = f.get("location", {})
        print(f"{f.get('filename')}:{loc.get('row')}:{loc.get('column')}: "
              f"VIOLATION [{f.get('code')}] {f.get('message')}  ({label})")


# Fixtures: (name, expected_code, firing_source, clean_source). Every mechanized family
# gets both legs — a rule passing only the clean leg is incapable of failing and proves
# nothing (the rig-assertion-discipline rule, plainspec-check's selftest shape).
LONG = "x = 1  #" + " padding" * 15
BRANCHY = "def f(n):\n" + "".join(
    f"    if n == {i}:\n        n += {i}\n" for i in range(11)) + "    return n\n"
WIDE_BRANCHY = "def f(n):\n" + "".join(
    f"    if n == {i}:\n        n += {i}\n" for i in range(13)) + "    return n\n"
RETURNY = "def f(n):\n" + "".join(
    f"    if n == {i}:\n        return {i}\n" for i in range(7)) + "    return n\n"
LONG_BODY = "def f():\n" + "".join(f"    x{i} = {i}\n" for i in range(51)) + "    return x0\n"
FIXTURES = [
    ("layout: a line past 100 columns", "E501", LONG + "\n", "x = 1\n"),
    ("layout: import below code", "E402", "x = 1\nimport os\nprint(os.sep)\n",
     "import os\nprint(os.sep)\n"),
    ("layout: trailing whitespace", "W291", "x = 1 \n", "x = 1\n"),
    ("slop: unused import", "F401", "import os\n", "import os\nprint(os.sep)\n"),
    ("slop: unused local", "F841", "def f():\n    y = 1\n    return 2\n",
     "def f():\n    y = 1\n    return y\n"),
    ("slop: unused argument", "ARG001", "def f(a):\n    return 2\n",
     "def f(a):\n    return a\n"),
    ("slop: commented-out code", "ERA001", "# print('dead')\nx = 1\n",
     "# a real remark about x\nx = 1\n"),
    ("slop: open() without a context manager", "SIM115",
     "def f(p):\n    fh = open(p)\n    return fh.read()\n",
     "def f(p):\n    with open(p) as fh:\n        return fh.read()\n"),
    ("slop: complexity past 10", "C901", BRANCHY, "def f(n):\n    return n\n"),
    ("slop: more than twelve branches", "PLR0912", WIDE_BRANCHY,
     "def f(n):\n    return n\n"),
    ("slop: more than six returns", "PLR0911", RETURNY, "def f(n):\n    return n\n"),
    ("slop: more than fifty statements", "PLR0915", LONG_BODY,
     "def f():\n    return 0\n"),
    ("slop: more than five arguments", "PLR0913",
     "def f(a, b, c, d, e, g):\n    return a + b + c + d + e + g\n",
     "def f(a, b, c):\n    return a + b + c\n"),
]


def selftest(ruff):
    ok = True
    for name, code, bad, clean in FIXTURES:
        # pycodestyle codes are one letter + digits; ERA001 also starts with E, and the
        # first draft's startswith(("E", "W")) sent it to the layout select where ERA is
        # never enabled — the fixture's fire leg went quiet and the selftest caught it.
        select = LAYOUT if code[0] in "EW" and code[1:].isdigit() else SLOP
        fired, err1 = run_ruff(ruff, select, [], stdin_text=bad, stdin_name="fire.py")
        quiet, err2 = run_ruff(ruff, select, [], stdin_text=clean, stdin_name="clean.py")
        fire_codes = {f.get("code") for f in fired}
        quiet_codes = {f.get("code") for f in quiet}
        good = err1 is None and err2 is None and code in fire_codes \
            and code not in quiet_codes
        print(f"  {'PASS' if good else 'FAIL'}  {name} "
              f"(fire={sorted(fire_codes)} clean={sorted(quiet_codes)})")
        ok = ok and good
    print(f"selftest: {'all' if ok else 'NOT all'} {len(FIXTURES)} fixtures "
          f"hold both legs")
    return 0 if ok else 1


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    unknown = flags - {"--layout", "--selftest"}
    if unknown:
        print(f"unknown flag(s): {sorted(unknown)}\n{__doc__.splitlines()[0]}")
        return 2
    ruff = find_ruff()
    if ruff is None:
        print("plaincode-check: ruff is not on PATH, so nothing was measured — the "
              "same engine the gate's lint row needs. Install ruff, then re-run.")
        return 3
    if "--selftest" in flags:
        return selftest(ruff)
    if not args:
        print(f"no files given\n{__doc__.splitlines()[0]}")
        return 2

    total = 0
    for layer, select in (("layout", LAYOUT),) + \
            (() if "--layout" in flags else (("slop", SLOP),)):
        findings, err = run_ruff(ruff, select, args)
        if err is not None:
            print(f"plaincode-check: ruff itself failed on the {layer} layer — "
                  f"nothing measured there: {err}")
            return 3
        report(findings, layer)
        total += len(findings)
    print(f"\n{total} violation(s) across {len(args)} file(s), width {WIDTH}.")
    print("The judgment pass (JUDGE, never the exit code):")
    for j in JUDGE:
        print(f"  {j}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
