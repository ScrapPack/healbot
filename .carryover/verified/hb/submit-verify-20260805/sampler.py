"""Dense pane sampler for the submit-verify measurement (single-use rig).

Captures `tmux capture-pane -p` frames at a fixed cadence, stamping each with
wall time, so the analyzer can look up what the pane held at the instant the
shipped verify loop sampled it. The capture invocation matches send's exactly
(plain -p: padded to pane height, no -e, no -N) because the padding IS the
subject under measurement.

Calls the real tmux binary by absolute path so the PATH shim logs only the
send process's own calls.
"""

import json
import os
import subprocess
import sys
import time


def main():
    tmux, sock, pane, outdir, hz, secs = sys.argv[1:7]
    hz, secs = float(hz), float(secs)
    os.makedirs(outdir, exist_ok=True)
    geo = subprocess.run(
        [tmux, "-L", sock, "display", "-p", "-t", pane,
         "#{pane_width} #{pane_height}"],
        capture_output=True, text=True).stdout.strip()
    index = open(os.path.join(outdir, "index.jsonl"), "w")
    index.write(json.dumps({"geometry": geo, "pane": pane,
                            "started": time.time()}) + "\n")
    period = 1.0 / hz
    deadline = time.time() + secs
    i = 0
    while time.time() < deadline:
        t = time.time()
        r = subprocess.run([tmux, "-L", sock, "capture-pane", "-p", "-t", pane],
                           capture_output=True, text=True)
        name = "frame-%03d.txt" % i
        with open(os.path.join(outdir, name), "w") as f:
            f.write(r.stdout)
        index.write(json.dumps({"i": i, "t": t, "rc": r.returncode,
                                "file": name}) + "\n")
        index.flush()
        i += 1
        sleep_for = period - (time.time() - t)
        if sleep_for > 0:
            time.sleep(sleep_for)
    index.close()


if __name__ == "__main__":
    main()
