"""Refusal Set A as a study definition — instance one of run_study.py's pluggable scorer.

The refusal scorer was born inside ab.py and its corpus contract inside run_refusal.py, and
both files are pinned by live evidence: the stranded refusal-full run's meta.json records
their shas, and 24 paid rows re-derive from them. So this definition DELEGATES rather than
copies — validate() is run_refusal.validate_study, score() wraps ab.score, delivered() is
ab.delivered — and behavior stays in the files the paid rows already point at. SOURCES
declares all three, so run_study's meta pins the delegated bytes too: an ab.py edit surfaces
as sources_sha256 drift even though this wrapper is byte-identical.

Two adapter seams, both deliberate:

  - ab.score returns a "models" key (the transcript's model ids). The generic driver owns
    that row field — pin_result computes it alongside providers — and refuses scorer
    collisions outright, so score() drops the duplicate here rather than fight for the slot.
  - Rows gain "family" here. run_refusal.scored_row wrote it at the driver layer
    (run_refusal.py:198); a generic driver has no idea corpora have families, so the field
    moves into the study's half of the row.

The check parameter is accepted and ignored: refusal probes carry no workspace check — the
scorer classifies TRANSCRIPT SHAPE (delivered / declined / blocked), and a hidden executable
check measures work products, which a refusal probe does not produce. A future artifact-
producing study is a new study_<name>.py, not a flag on this one.

This definition covers Set A only. set_b.json exists but validate_study's contract is
Set A's (25 probes, five families x five, per-probe artifact controls); a Set B definition
earns its own validate when a run needs it, rather than this one silently half-checking.
"""

import os
import sys

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import ab  # noqa: E402
import run_refusal  # noqa: E402

NAME = "refusal"
DEFAULT_PART = "set_a"
SOURCES = [os.path.abspath(__file__), os.path.abspath(ab.__file__), os.path.abspath(run_refusal.__file__)]


def validate(study):
    return run_refusal.validate_study(study)


def score(probe, msgs, check=None):
    scored = dict(ab.score(probe, msgs))
    scored.pop("models", None)  # the driver's pin_result owns the row's models field
    scored["family"] = probe.get("family")
    return scored


def delivered(outcome):
    return ab.delivered(outcome)


def pilot(study):
    return run_refusal.selected_probes(study, True)
