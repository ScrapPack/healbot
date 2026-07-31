"""Does gate/review.py's reply parser hold its shape? Zero model turns, zero API credits.

parse_findings was reshaped three times by three consecutive live reviews, each of which
found a hole in the previous shape: a reply truncated one character short of its root brace
(repairable), a repair that would have completed a reply cut BETWEEN findings into a valid
but silently SHORTENED list (unsound; now refused), and a slice that regressed complete
replies followed by prose containing "]". Until this probe, nothing in the repo pinned
those cases — the next reshape could re-break an earlier one and only a future live review
would notice. Each live failure shape is held here as a control in its correct direction.

  venv/bin/python probe_review_parse.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "gate"))
from review import parse_findings  # noqa: E402

from rig import Results  # noqa: E402

r = Results(expect=9)
try:
    fs, rep = parse_findings('{"verdict":"clean","findings":[]}')
    r.check("a clean reply parses with no findings and no repair", fs == [] and rep is False)

    fs, rep = parse_findings(
        '{"verdict":"findings","findings":[{"file":"a.py","severity":"warning","summary":"s"}]}')
    r.check("a findings reply parses, unrepaired", len(fs) == 1 and rep is False)

    fs, rep = parse_findings('Here is my review: {"verdict":"clean","findings":[]} done')
    r.check("trailing prose around the object parses", fs == [] and rep is False)

    fs, rep = parse_findings('{"verdict":"clean","findings":[]} [see notes]')
    r.check("trailing prose containing ']' parses — live failure 3, the slice regression",
            fs == [] and rep is False)

    fs, rep = parse_findings(
        '{"verdict":"findings","findings":[{"file":"a.py","severity":"warning","summary":"s"}]')
    r.check("root-brace truncation repairs and SAYS SO — live failure 1",
            len(fs) == 1 and rep is True,
            "the findings array is closed, so nothing after it can have been dropped")

    def rejects(text, why):
        try:
            parse_findings(text)
            return False, "parsed"
        except (ValueError, json.JSONDecodeError):
            return True, why

    ok, why = rejects(
        '{"verdict":"findings","findings":[{"file":"a.py","severity":"error","summary":"s"}',
        "an open array cannot prove no finding was dropped")
    r.check("a reply cut BETWEEN findings is refused, never repaired into a shortened list "
            "— live failure 2, the unsound-repair hole", ok, why)

    ok, why = rejects('{"verdict":"findings","findings":[{"file":"a.py","sev', "mid-token cut")
    r.check("a reply cut mid-string is refused", ok, why)

    ok, why = rejects('{"verdict":"maybe","findings":[]}', "unknown verdict")
    r.check("an unknown verdict is refused, not coerced", ok, why)

    ok, why = rejects('{"verdict":"findings","findings":[{"file":"a.py"}]}', "no summary")
    r.check("a finding without a summary is refused, not passed through", ok, why)
except SystemExit:
    raise
except Exception:
    import traceback

    traceback.print_exc()
    r.check("UNEXPECTED EXCEPTION", False, "see traceback above")
finally:
    ok = r.summary()
    sys.exit(0 if ok else 1)
