"""What a gnhf run has actually cost, in dollars.

    python3 harness/gnhf-spend.py <run-dir>     ->  "<exact> <floor>"

Two numbers, deliberately kept apart rather than added here, because they are not the same kind
of claim. EXACT is gnhf's own `total_cost_usd`, summed over iterations that finished; it needs no
price table and cannot drift. FLOOR is a lower bound for the iteration still running, priced from
its `assistant` events; it is a floor, not an estimate, and the caller must treat it as one.

WHY NOT TOKENS. The previous accounting lived inline in gnhf-watch.sh, counted tokens, and was
wrong four ways at once. All four are MEASURED against .gnhf/runs/you-are-an-unattende-e196d4 on
2026-08-06, where it reported 2,717,201 "billable tokens" against a true $29.92:

  1. It summed `assistant` EVENTS. Claude Code emits one per content block, every one carrying
     the same message id and a byte-identical usage object. In iteration 1, 50 of 74 ids repeat
     and msg_011CdkmrxPbdQbyNENfSUAgZ appears three times. Raw 1,732,432 vs deduped 742,405.
  2. It ALSO summed `result` events, which are each iteration's cumulative total, so the per-turn
     numbers and the total were added together. Compounded with 1, that is 2.76x.
  3. It globbed every run directory ever created. .gnhf/runs is never pruned, so an abandoned run
     from earlier the same evening was charged to the live one.
  4. It excluded cache reads, on the stated theory that they were "already paid to write". They
     are not: cache reads bill at 0.1x input, and on that run they were 55% of the real cost
     ($16.32 of $29.92). A cost metric that omits its largest component is not a cost metric.

WHY output_tokens IS NOT USABLE FROM assistant EVENTS. The usage on an `assistant` event is the
one from the underlying message_start, so output_tokens is the partial count at stream open (1,
typically), not the final figure. Input and both cache fields are correct there; output is not.
That is the entire reason the in-flight number is a floor: measured on iteration 5 of that run,
the floor lands at $2.99 against a true $3.79, and the missing 21% is exactly output.
"""
import json
import os
import sys
import glob

# $/MTok: (fresh input, cache write, cache read, output). Cache write is the 1-hour-TTL rate,
# 2x input, which is what Claude Code uses; cache read is 0.1x input. VERIFIED against the
# published Opus 5 rates and, independently, solved out of that run's own six result events by
# least squares: in 4.987, write 10.004, read 0.500, output 25.110, residual under $0.001.
RATES = {
    "claude-opus-5":     (5.0, 10.0, 0.50, 25.0),
    "claude-opus-4-8":   (5.0, 10.0, 0.50, 25.0),
    "claude-opus-4-7":   (5.0, 10.0, 0.50, 25.0),
    "claude-opus-4-6":   (5.0, 10.0, 0.50, 25.0),
    "claude-fable-5":    (10.0, 20.0, 1.00, 50.0),
    "claude-mythos-5":   (10.0, 20.0, 1.00, 50.0),
    "claude-sonnet-5":   (3.0, 6.0, 0.30, 15.0),
    "claude-sonnet-4-6": (3.0, 6.0, 0.30, 15.0),
    "claude-haiku-4-5":  (1.0, 2.0, 0.10, 5.0),
}
# An unpriced model must over-estimate, never under-estimate, or the cap fails open.
FALLBACK = RATES["claude-fable-5"]


def spend(run_dir):
    exact = 0.0
    floor = 0.0
    unknown = set()
    for path in sorted(glob.glob(os.path.join(run_dir, "iteration-*.jsonl"))):
        finished = False
        by_id = {}
        for line in open(path, errors="replace"):
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("type") == "result":
                cost = rec.get("total_cost_usd")
                if isinstance(cost, (int, float)):
                    exact += cost
                    finished = True
            elif rec.get("type") == "assistant":
                msg = rec.get("message") or {}
                # Keying by message id is what stops defect 1. Summing the events double-counts.
                if msg.get("id") and msg.get("usage"):
                    by_id[msg["id"]] = (msg.get("model"), msg["usage"])
        if finished:
            continue    # the result event is authoritative; adding the turns too is defect 2
        for model, usage in by_id.values():
            rate = RATES.get(model)
            if rate is None:
                unknown.add(model or "<none>")
                rate = FALLBACK
            floor += (usage.get("input_tokens", 0) * rate[0]
                      + usage.get("cache_creation_input_tokens", 0) * rate[1]
                      + usage.get("cache_read_input_tokens", 0) * rate[2]
                      + usage.get("output_tokens", 0) * rate[3]) / 1e6
    return exact, floor, unknown


def main():
    if len(sys.argv) != 2:
        sys.stderr.write("usage: gnhf-spend.py <run-dir>\n")
        return 2
    exact, floor, unknown = spend(sys.argv[1])
    if unknown:
        sys.stderr.write("gnhf-spend: unpriced model(s), charged at top-tier rates: %s\n"
                         % ", ".join(sorted(unknown)))
    print("%.4f %.4f" % (exact, floor))
    return 0


if __name__ == "__main__":
    sys.exit(main())
