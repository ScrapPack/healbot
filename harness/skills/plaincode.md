---
name: plaincode
description: Controlled Python mode, the code twin of plainspec. PEP 8 mechanized at the repo's measured width plus compaction rules against slop. Six mechanized rule families run through ruff; five judgment rules take one pass. Use when writing or reviewing Python, when the user says "plaincode", "less slop", "compact this", or invokes /plaincode.
---

# Plaincode: controlled Python

Write code the next reader holds in one pass. Constrain the writer, free the reader.
plainspec covers prose. This standard covers Python and only Python.

## Scope

Covers Python this repo owns: `harness/`, `gate/`, and new rig code alongside the
rig-assertion-discipline skill's own rules. Excludes the derived checkout, recorded
corpora, and vendored code. Every rule is behavior-preserving: a rule is never a reason
to change what code does. The evidence register is protected. A docstring or comment
that carries a date, a measurement, or a `file:line` citation is load-bearing and never
counts against any rule.

## The mechanized layers

Rule 1 is PEP 8, adopted by reference and mechanized: ruff select `E,W` at width 100.
The width is measured, not preferred. The repo's 95th-percentile line is 98 columns
(docs/PLAINCODE.md), so 100 codifies practice. PEP 8's 79 would rewrite 30% of the tree.

Rules 2 through 6 are the slop layer, each a move plus a ruff test:

2. **Delete dead code.** Unused imports, locals, and arguments go. Test: `F401`,
   `F841`, `ARG`.
3. **Delete commented-out code.** Version control remembers it. Test: `ERA`.
4. **One function, one screen of logic.** Complexity stays at or under 10, with
   bounded branches, statements, and returns. Test: `C901`, `PLR0912`, `PLR0915`,
   `PLR0911`.
5. **Arguments earn their seats, at most five.** Test: `PLR0913`.
6. **Say it the short way when the short way is the same claim.** Files close what
   they open. Test: the `SIM` family, `SIM115` included.

## The judgment rules

J1 through J5 are the compaction half. No linter sees them, so they take one deliberate
pass, the same contract as plainspec's rules 1, 4, and 11.

- **J1. One owner per fact.** A threshold, path, or magic number that appears twice
  gets one named owner, with pointers everywhere else. This is the prose-copy rule
  applied to code. It is also why `PLR2004` stays out of the mechanized set. 95 of the
  repo's measured slop findings are assertion literals, and there the number IS the
  fixture.
- **J2. Inline single-use indirection.** A helper with one caller earns its name or
  becomes its body. Count the callers before keeping the layer.
- **J3. No speculative generality.** No parameter, branch, or abstraction for a caller
  that does not exist. The burden of proof is on the abstraction.
- **J4. Comments carry WHY and evidence, never WHAT.** A comment restating its line is
  slop. A comment with a date, a measurement, or a citation is load-bearing.
- **J5. Deletion is the first fix.** When a rule fires, ask whether the code can go
  before asking how it can conform. Lossless means the behavior survives, not the code.

## What this standard deliberately does not require

No type hints: the repo has zero today (0 of 433 functions), and adopting them is a
greenfield decision rather than an enforcement one. No PEP 257 summary docstrings: the
house docstring is a rationale record, and a standard that fights the evidence register
loses. No formatter: `ruff format` would rewrite 55 of 57 files, and layout churn
buries real diffs.

## Running the tests

check.py sits beside this skill. `python3 check.py FILE...` runs both layers and prints
the judgment checklist. `--layout` runs the PEP 8 layer alone. `--selftest` proves
every fixture fires and stays quiet on its clean twin. Exit 0 clean, 1 violations,
2 usage, 3 ruff absent (the gate's cannot-measure sentinel, gate/GATE.MAP.md).

## Adoption, recorded and not taken

The gate already runs ruff on every changed Python file. A root `ruff.toml` carrying
this standard's selects would arm it repo-wide, change by change, with no gate edit.
That flip is the owner's call: the measured cost sits in docs/PLAINCODE.md, and until
it is taken this skill governs sessions, not pushes.

