"""Analyzer for the submit-verify measurement (single-use rig).

Replays BOTH readers against every captured frame:
  raw3      — the shipped verify's window: `capture-pane -p | tail -3`
  stripped3 — the counterfactual: screen_tail semantics, blanks dropped
              BEFORE the tail (`grep -v '^[[:space:]]*$' | tail -3`)

Blank means the POSIX class: space \t \v \f \r only. NOT python str.strip(),
which also eats NBSP and would diverge from the grep the fleet actually runs.

The shim log gives the instants the real loop sampled; each is mapped to the
nearest dense frame. The stripped counterfactual is then simulated on the
shipped loop's schedule: sample; on match press Enter (not really pressed —
noted as fidelity caveat) and sample again ~1s later; two matches is the
"did not provably clear" exit 1.
"""

import json
import os
import re
import sys

BLANK = re.compile(r"^[ \t\v\f\r]*$")

# What each leg exists to measure. The tall leg is the known blindness (the raw
# window on pure padding); the full leg is the counterpart (the raw window on
# paint). analyze.py verifies the achieved ground from the frames instead of
# trusting the rig's resize arithmetic — run1's full leg asked for a filled pane
# and the CLI reflowed smaller, so the leg ran padded and only this flag says so.
INTENT = {"tall": "padding", "full": "paint"}


def raw3(text):
    return text.splitlines()[-3:]


def stripped3(text):
    return [ln for ln in text.splitlines() if not BLANK.match(ln)][-3:]


def painted(text):
    return sum(1 for ln in text.splitlines() if not BLANK.match(ln))


def echo_pos(text, nonce):
    """The transcript echo's position counting painted lines up from the
    painted bottom, the echo itself counted ("six painted lines above the pane
    bottom" = pos 6, five painted lines below it). None before the echo paints:
    the composer renders the same "❯ " shape, but neither leg's capture caught
    it holding a nonce — type-to-Enter was ~8ms against 10Hz frames."""
    lines = [ln for ln in text.splitlines() if not BLANK.match(ln)]
    for i, ln in enumerate(reversed(lines), 1):
        if ln.startswith("❯") and nonce in ln:
            return i
    return None


def raw_ground(text):
    """What the shipped raw window actually sat on."""
    blanks = sum(1 for ln in raw3(text) if BLANK.match(ln))
    return {0: "paint", 3: "padding"}.get(blanks, "mixed")


def load_leg(legdir):
    frames = []
    meta = {}
    for row in open(os.path.join(legdir, "frames", "index.jsonl")):
        d = json.loads(row)
        if "i" not in d:
            meta = d
            continue
        d["text"] = open(os.path.join(legdir, "frames", d["file"])).read()
        frames.append(d)
    events = {"type": None, "enters": [], "captures": []}
    for line in open(os.path.join(legdir, "tmux-calls.log")):
        ts, _, args = line.partition(" ")
        ts = float(ts)
        if "capture-pane" in args:
            events["captures"].append(ts)
        elif "send-keys" in args and " -l " in " " + args:
            events["type"] = ts
        elif "send-keys" in args and args.rstrip().endswith(" Enter"):
            events["enters"].append(ts)
    send = {}
    for part in ("out", "err", "exit"):
        p = os.path.join(legdir, "send." + part)
        send[part] = open(p).read().strip() if os.path.exists(p) else ""
    nonce = open(os.path.join(legdir, "nonce.txt")).read().strip()
    return meta, frames, events, send, nonce


def nearest(frames, ts):
    return min(frames, key=lambda f: abs(f["t"] - ts))


def classify(frame, nonce):
    return {
        "raw3": nonce in "\n".join(raw3(frame["text"])),
        "stripped3": nonce in "\n".join(stripped3(frame["text"])),
        "anywhere": nonce in frame["text"],
        "painted": painted(frame["text"]),
        "padded": len(frame["text"].splitlines()),
        "echo_pos": echo_pos(frame["text"], nonce),
        "ground": raw_ground(frame["text"]),
    }


def simulate_stripped(frames, samples, nonce):
    """The shipped loop's schedule with screen_tail as the window."""
    if not samples:
        return {"verdict": "no samples recorded", "detail": []}
    detail = []
    tries = 0
    ts = samples[0]
    for hop in range(2):
        c = classify(nearest(frames, ts), nonce)
        detail.append({"t": ts, "match": c["stripped3"]})
        if not c["stripped3"]:
            break
        tries += 1
        ts = samples[hop + 1] if len(samples) > hop + 1 else ts + 1.05
    if tries >= 2:
        verdict = "FALSE FAILURE: exit 1 'did not provably clear' + 2 spurious Enters"
    elif tries == 1:
        verdict = "sent, but after 1 spurious extra Enter"
    else:
        verdict = "sent, cleanly (no spurious Enter)"
    return {"verdict": verdict, "tries": tries, "detail": detail}


def leg_report(name, legdir, out):
    meta, frames, ev, send, nonce = load_leg(legdir)
    submit = ev["enters"][0] if ev["enters"] else None
    verify_samples = [c for c in ev["captures"] if submit and c > submit]
    out.append("## Leg: %s\n" % name)
    out.append("- pane geometry (width height): `%s`" % meta.get("geometry"))
    out.append("- nonce: `%s`" % nonce)
    out.append("- typed at %s, submit Enter at %s" % (ev["type"], submit))
    out.append("- real send exit=%s stdout=%r stderr=%r"
               % (send["exit"], send["out"], send["err"]))
    out.append("- verify-loop capture instants: %s\n" % verify_samples)
    out.append("### The shipped loop's actual samples\n")
    out.append("| sample t (rel) | frame dt | nonce in raw3 | nonce in "
               "stripped3 | nonce anywhere | painted/padded | raw window "
               "ground | echo pos |")
    out.append("|---|---|---|---|---|---|---|---|")
    grounds = []
    for ts in verify_samples:
        f = nearest(frames, ts)
        c = classify(f, nonce)
        grounds.append(c["ground"])
        out.append("| +%.2fs | %+.0fms | %s | %s | %s | %d/%d | %s | %s |" % (
            ts - submit, (f["t"] - ts) * 1000, c["raw3"], c["stripped3"],
            c["anywhere"], c["painted"], c["padded"], c["ground"],
            c["echo_pos"] or "-"))
    want = INTENT.get(name)
    if want:
        met = bool(grounds) and all(g == want for g in grounds)
        out.append("\n**Leg condition %s** — designed to sample the raw window "
                   "on %s; it sampled %s.\n"
                   % ("MET" if met else "UNMET", want,
                      "/".join(grounds) if grounds else "nothing"))
    poss = [c for c in (classify(f, nonce)["echo_pos"] for f in frames) if c]
    if poss:
        out.append("Echo position across the %d frames holding it: %d-%d from "
                   "the painted bottom (the stripped 3-line window is "
                   "positions 1-3).\n" % (len(poss), min(poss), max(poss)))
    sim = simulate_stripped(frames, verify_samples, nonce)
    out.append("\n### Counterfactual: screen_tail window on the same schedule\n")
    out.append("**%s**" % sim["verdict"])
    out.append("(Fidelity caveat: the counterfactual's retry Enters were not "
               "really pressed; an Enter on an empty composer cannot remove "
               "the transcript echo, so this biases toward the echo "
               "persisting — the direction being probed.)\n")
    out.append("### Full timeline (rel to submit Enter)\n")
    out.append("| t | raw3 | stripped3 | anywhere | painted/padded | echo pos |")
    out.append("|---|---|---|---|---|---|")
    for f in frames:
        c = classify(f, nonce)
        rel = f["t"] - submit if submit else float("nan")
        out.append("| %+.2fs | %s | %s | %s | %d/%d | %s |" % (
            rel, c["raw3"], c["stripped3"], c["anywhere"],
            c["painted"], c["padded"], c["echo_pos"] or "-"))
    out.append("")
    return sim


def main():
    archive = sys.argv[1]
    legs = [d for d in ("tall", "full")
            if os.path.isdir(os.path.join(archive, d, "frames"))]
    out = ["# Submit-verify measurement — %s\n" % os.path.basename(archive)]
    sims = {}
    for leg in legs:
        sims[leg] = leg_report(leg, os.path.join(archive, leg), out)
    out.append("## Verdict inputs\n")
    for leg in legs:
        out.append("- %s: stripped-counterfactual → %s"
                   % (leg, sims[leg]["verdict"]))
    tail_from = len(out) - len(legs) - 1
    # Hand-recorded run facts (the unmet full-leg condition, the unplanned
    # composer write) live in NOTES.md and survive regeneration verbatim.
    notes = os.path.join(archive, "NOTES.md")
    if os.path.exists(notes):
        out.append("\n## Run notes (hand-recorded in NOTES.md; regeneration "
                   "re-appends it verbatim)\n")
        out.append(open(notes).read().rstrip())
    with open(os.path.join(archive, "REPORT.md"), "w") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out[tail_from:]))
    print("report: %s" % os.path.join(archive, "REPORT.md"))


if __name__ == "__main__":
    main()
