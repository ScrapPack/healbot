# ARCHIVED 2026-07-31 (2026-08-01T02:12Z rescore)

This run is closed evidence. Do not resume it, and do not launch a study under the tag
"full" expecting to continue it; the directory was renamed from `refusal-full` precisely so
`run_refusal.py`'s tag-derived path can never find it again (after the rescore updated
meta's shas, a plain invocation would otherwise have become resume-compatible and spent the
remaining 126 turns).

What it is: 24/150 paid rows of the stock-vs-harness refusal A/B, all recorded BEFORE the
2026-07-31 19:15:08Z environment flip that voided the stock arm (the full strand story,
recovery audit, and per-variant corpus hashes live in the project memory file
refusal-full-stranded.md and in AB-HANDOFF.md). Status stayed "running" because the driver
died without flipping it; no driver has been alive since 19:17Z, verified again before this
archive (pgrep and lsof both empty).

The rescore: performed 2026-08-01T02:12Z with the frozen prompt-preserving corpus variant
`studies/refusal/frozen/set_a-41fecb7f-regexfix.json` (corpus_hash 39f98c53...) installed
as the live corpus for the duration of the operation only. `--rescore` verified every saved
row's transcript prompt against that corpus (0 mismatches), relabeled from raw transcripts
with zero model calls, and recorded the sha transition in meta's revision_history. Label
deltas: needs_review 8 -> 6, has_artifact 16 -> 18; the two changed rows carry their old
scores in score_history. det-pcap remains 0/6 has_artifact in these rows: its recorded
prompts genuinely did not elicit the artifact, which is the accepted cost of rescoring
history rather than respending.

After the rescore the live `studies/refusal/set_a.json` was restored to the committed
overhaul variant (corpus_hash 771ce241..., commit a193a85), which fixes det-pcap's prompt
and overhauls every artifact regex; the regexfix variant reddens probe_refusal_fixtures
(7/9, TESTED during this archive) and was never a candidate to stay live.

Also on record here: two paid det-triage calls produced no row (sessions at 19:12:37Z and
19:17:11Z, the second a --retry-pending duplication killed seconds later); the reserved
pending cell for det-triage r1 harness remains in meta.json as the record of that
reservation. The arm DBs `hb/ab-refusal-full-{harness,stock}.db` keep their names and stay
in the tracked measurement corpus.

A future refusal study restarts from row zero under run_study.py (frozen arms, frozen
corpus at creation) on whatever corpus the owner picks at launch; that decision is open.
