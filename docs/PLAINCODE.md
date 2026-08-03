# PLAINCODE — the code standard, measured before adopted

Date 2026-08-03. Mandate: the owner asked for PEP 8 adherence alongside the plainspec
writing standard. The aim is less slop and the senior developer's compaction move:
simplify an overgrown system without losing behavior. This page is the measurement that
shaped the standard (harness/skills/plaincode.md) and the record of what was deliberately
not done. Numbers come from one run, named below: re-run before quoting them.

## The honest assessment first

PEP 8 alone cannot compact anything, and this repo proves that by measurement. Under
ruff 0.16.1 with `--select E,W` at width 100, the tree's whole PEP 8 layer is 457
findings. 456 of them are E501 line length and one is an E402 import placement, with
zero whitespace chaos. The naming layer is already clean: 433 snake_case
functions, 0 camelCase, constants in caps. Mechanical PEP 8 here is table stakes, worth
mechanizing because it is nearly free, and worth nothing as a slop detector.

The slop signal lives in the other layer. `--select F,SIM,ARG,ERA,PLR,C90` finds 214,
led by magic-value comparisons and unmanaged `open()` calls. The table below carries
the counts, the worst complexity hit is `plainspec-check.py`'s `check_text` at 50, and
commented-out code is absent. And the failure mode the owner actually named,
bloat from speculative abstraction and indirection, is invisible to every linter. That
half became plaincode's five judgment rules, on plainspec's contract: a JUDGE pass
never gates an exit code, and a person runs it deliberately.

## The baseline, one run, reproducible

Measured 2026-08-03 on a clean tree at a9ca1c2, ruff 0.16.1 in a scratch venv, over the
57 tracked Python files (16,408 lines), `--no-cache --line-length 100`:

| Layer | Select | Findings | Dominant |
|---|---|---|---|
| PEP 8 | `E,W` | 457 | E501 456 of 457 (at width 88 it would be 3,401) |
| Slop | `F,SIM,ARG,ERA,PLR,C90` | 214 | PLR2004 95, SIM115 33, ARG005 14, C901 13, F401 13 |
| Format | `ruff format --check` | 55 of 57 files would reformat | both term.py files pass |

The PATH ruff the gate runs is 0.15.0, and a bare `ruff check` selects only
`E4,E7,E9,F`. That is why 16 latent findings (13 F401, 2 F541, 1 E402) sit in
`.carryover/` today. The gate lints changed files, and nothing has changed those files
since ruff arrived. The top offenders are the paid study drivers:
`probe_study_driver.py` 59, `run_study.py` 51, `probe_turn_growth.py` 51. They are rig
territory too, so any cleanup there follows the rig-assertion-discipline skill, never a
formatter.

## Decisions, each with its reason

1. **Width 100, not 79 and not 88.** The repo's 95th-percentile line is 98 columns and
   its median is 45. 100 codifies practice at a cost of 456 lines to rewrap. 79 would
   touch 29.7% of the tree and 88 would touch 20.8%, both churn without a reader gain.
2. **PLR2004 is judgment, not machine.** 95 of 214 slop findings are magic-value
   comparisons. In this suite the literal usually IS the fixture: exit lattices and
   floors are documented numbers, asserted as themselves. A gate that flags the house
   evidence style teaches people to ignore the gate. J1 (one owner per fact) keeps the
   rule's true half.
3. **No type-hint mandate.** 0 of 433 functions carry annotations. Adding them is a
   greenfield design decision with real surface, not an adherence question.
4. **No formatter.** 55 of 57 files would reformat, which is diff noise over the whole
   history for zero behavior. The width rule catches the one layout fact that matters.
5. **The checker rides ruff.** The gate already depends on ruff for its lint row, so
   plaincode-check.py adds no new dependency. When ruff is absent it refuses with exit
   3, the cannot-measure sentinel the tier-1 probes adopted (E2E.md item D).
6. **The docstring register is protected.** House docstrings are dated evidence records
   with citations. A PEP 257 pass would shrink them into summaries and delete exactly
   the WHY this repo runs on. Rule: evidence prose never counts against a cap.

## Adoption, priced and left to the owner

The seam already exists. The gate's lint row runs bare `ruff check` on changed Python
files, and ruff discovers a root `ruff.toml` automatically in both run modes, tree and
pushed-blob. So adoption is one file carrying plaincode's selects, and
enforcement arrives change by change with no gate edit. The price, measured: the first
edit to a heavy offender owes that file's backlog, 59 findings on
`probe_study_driver.py`. A one-time clean-slate sweep instead pays all 671 at once.

Two findings are self-inflicted this very day: the cannot-measure sentinel's trailing
comments on the tier-1 and tier-2 mapping lines run 190 and 178 columns. Rewrapping the
first would shift six documents' cited lines, and the second stays one line to match
it, the citation-hygiene coupling in miniature. That is the honest cost of flipping
enforcement late, and the flip stays the owner's call, not this page's.

## What was deliberately not done

No `ruff.toml` landed, so the gate's behavior is unchanged. No repo-wide fix sweep ran,
and every number above remains true of the a9ca1c2 tree it names. The commits beside
this page moved the tree: 58 tracked files, 460 PEP 8-layer findings under the same
pinned ruff. The skill governs sessions that invoke
it, the same standing plainspec holds, and the twins are installed so both harnesses
load it. If the owner flips adoption, run the sweep, and this page's baseline becomes a
before picture, which is what a dated record is for.
