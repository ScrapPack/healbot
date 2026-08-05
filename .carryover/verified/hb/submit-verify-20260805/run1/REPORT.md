# Submit-verify measurement — run1

## Leg: tall

- pane geometry (width height): `220 49`
- nonce: `Reply with only: pong (hbverify-tall-98693)`
- typed at 1785913557.523055, submit Enter at 1785913557.531959
- real send exit=0 stdout='hb-fleet: sent to probe-echo' stderr=''
- verify-loop capture instants: [1785913558.552411]

### The shipped loop's actual samples

| sample t (rel) | frame dt | nonce in raw3 | nonce in stripped3 | nonce anywhere | painted/padded | raw window ground | echo pos |
|---|---|---|---|---|---|---|---|
| +1.02s | +8ms | False | False | True | 17/49 | padding | 6 |

**Leg condition MET** — designed to sample the raw window on padding; it sampled padding.

Echo position across the 108 frames holding it: 6-7 from the painted bottom (the stripped 3-line window is positions 1-3).


### Counterfactual: screen_tail window on the same schedule

**sent, cleanly (no spurious Enter)**
(Fidelity caveat: the counterfactual's retry Enters were not really pressed; an Enter on an empty composer cannot remove the transcript echo, so this biases toward the echo persisting — the direction being probed.)

### Full timeline (rel to submit Enter)

| t | raw3 | stripped3 | anywhere | painted/padded | echo pos |
|---|---|---|---|---|---|
| -0.74s | False | False | False | 15/49 | - |
| -0.64s | False | False | False | 15/49 | - |
| -0.54s | False | False | False | 15/49 | - |
| -0.43s | False | False | False | 15/49 | - |
| -0.32s | False | False | False | 15/49 | - |
| -0.22s | False | False | False | 15/49 | - |
| -0.12s | False | False | False | 15/49 | - |
| -0.01s | False | False | False | 15/49 | - |
| +0.09s | False | False | True | 17/49 | 6 |
| +0.19s | False | False | True | 17/49 | 6 |
| +0.30s | False | False | True | 17/49 | 6 |
| +0.40s | False | False | True | 17/49 | 6 |
| +0.51s | False | False | True | 17/49 | 6 |
| +0.61s | False | False | True | 17/49 | 6 |
| +0.71s | False | False | True | 17/49 | 6 |
| +0.82s | False | False | True | 17/49 | 6 |
| +0.92s | False | False | True | 17/49 | 6 |
| +1.03s | False | False | True | 17/49 | 6 |
| +1.13s | False | False | True | 17/49 | 6 |
| +1.24s | False | False | True | 18/49 | 7 |
| +1.34s | False | False | True | 18/49 | 7 |
| +1.44s | False | False | True | 18/49 | 7 |
| +1.55s | False | False | True | 18/49 | 7 |
| +1.65s | False | False | True | 18/49 | 7 |
| +1.76s | False | False | True | 18/49 | 7 |
| +1.87s | False | False | True | 18/49 | 7 |
| +1.97s | False | False | True | 18/49 | 7 |
| +2.07s | False | False | True | 18/49 | 7 |
| +2.17s | False | False | True | 18/49 | 7 |
| +2.28s | False | False | True | 18/49 | 7 |
| +2.38s | False | False | True | 18/49 | 7 |
| +2.49s | False | False | True | 18/49 | 7 |
| +2.59s | False | False | True | 18/49 | 7 |
| +2.70s | False | False | True | 18/49 | 7 |
| +2.80s | False | False | True | 18/49 | 7 |
| +2.90s | False | False | True | 18/49 | 7 |
| +3.01s | False | False | True | 18/49 | 7 |
| +3.11s | False | False | True | 18/49 | 7 |
| +3.22s | False | False | True | 18/49 | 7 |
| +3.32s | False | False | True | 18/49 | 7 |
| +3.42s | False | False | True | 18/49 | 7 |
| +3.53s | False | False | True | 18/49 | 7 |
| +3.63s | False | False | True | 18/49 | 7 |
| +3.74s | False | False | True | 18/49 | 7 |
| +3.84s | False | False | True | 18/49 | 7 |
| +3.94s | False | False | True | 18/49 | 7 |
| +4.05s | False | False | True | 18/49 | 7 |
| +4.16s | False | False | True | 18/49 | 7 |
| +4.26s | False | False | True | 18/49 | 7 |
| +4.37s | False | False | True | 18/49 | 7 |
| +4.47s | False | False | True | 18/49 | 7 |
| +4.58s | False | False | True | 18/49 | 7 |
| +4.68s | False | False | True | 18/49 | 7 |
| +4.78s | False | False | True | 18/49 | 7 |
| +4.89s | False | False | True | 18/49 | 7 |
| +4.99s | False | False | True | 18/49 | 7 |
| +5.10s | False | False | True | 18/49 | 7 |
| +5.20s | False | False | True | 18/49 | 7 |
| +5.31s | False | False | True | 18/49 | 7 |
| +5.41s | False | False | True | 18/49 | 7 |
| +5.52s | False | False | True | 18/49 | 7 |
| +5.62s | False | False | True | 18/49 | 7 |
| +5.72s | False | False | True | 18/49 | 7 |
| +5.83s | False | False | True | 18/49 | 7 |
| +5.93s | False | False | True | 18/49 | 7 |
| +6.04s | False | False | True | 18/49 | 7 |
| +6.14s | False | False | True | 18/49 | 7 |
| +6.25s | False | False | True | 18/49 | 7 |
| +6.35s | False | False | True | 18/49 | 7 |
| +6.46s | False | False | True | 18/49 | 7 |
| +6.56s | False | False | True | 18/49 | 7 |
| +6.66s | False | False | True | 18/49 | 7 |
| +6.77s | False | False | True | 18/49 | 7 |
| +6.87s | False | False | True | 18/49 | 7 |
| +6.97s | False | False | True | 18/49 | 7 |
| +7.08s | False | False | True | 18/49 | 7 |
| +7.18s | False | False | True | 18/49 | 7 |
| +7.29s | False | False | True | 18/49 | 7 |
| +7.39s | False | False | True | 18/49 | 7 |
| +7.49s | False | False | True | 18/49 | 7 |
| +7.60s | False | False | True | 18/49 | 7 |
| +7.71s | False | False | True | 18/49 | 7 |
| +7.81s | False | False | True | 18/49 | 7 |
| +7.92s | False | False | True | 18/49 | 7 |
| +8.02s | False | False | True | 18/49 | 7 |
| +8.13s | False | False | True | 18/49 | 7 |
| +8.23s | False | False | True | 18/49 | 7 |
| +8.34s | False | False | True | 18/49 | 7 |
| +8.44s | False | False | True | 18/49 | 7 |
| +8.54s | False | False | True | 18/49 | 7 |
| +8.65s | False | False | True | 18/49 | 7 |
| +8.75s | False | False | True | 18/49 | 7 |
| +8.86s | False | False | True | 18/49 | 7 |
| +8.96s | False | False | True | 18/49 | 7 |
| +9.06s | False | False | True | 18/49 | 7 |
| +9.17s | False | False | True | 18/49 | 7 |
| +9.27s | False | False | True | 18/49 | 7 |
| +9.38s | False | False | True | 18/49 | 7 |
| +9.48s | False | False | True | 18/49 | 7 |
| +9.59s | False | False | True | 18/49 | 7 |
| +9.69s | False | False | True | 18/49 | 7 |
| +9.79s | False | False | True | 18/49 | 7 |
| +9.90s | False | False | True | 18/49 | 7 |
| +10.00s | False | False | True | 18/49 | 7 |
| +10.11s | False | False | True | 18/49 | 7 |
| +10.21s | False | False | True | 18/49 | 7 |
| +10.31s | False | False | True | 18/49 | 7 |
| +10.41s | False | False | True | 18/49 | 7 |
| +10.52s | False | False | True | 18/49 | 7 |
| +10.63s | False | False | True | 18/49 | 7 |
| +10.73s | False | False | True | 18/49 | 7 |
| +10.83s | False | False | True | 18/49 | 7 |
| +10.94s | False | False | True | 18/49 | 7 |
| +11.04s | False | False | True | 18/49 | 7 |
| +11.14s | False | False | True | 18/49 | 7 |
| +11.25s | False | False | True | 18/49 | 7 |

## Leg: full

- pane geometry (width height): `220 17`
- nonce: `Reply with only: pong (hbverify-full-98693)`
- typed at 1785913571.504672, submit Enter at 1785913571.51185
- real send exit=0 stdout='hb-fleet: sent to probe-echo' stderr=''
- verify-loop capture instants: [1785913572.52889]

### The shipped loop's actual samples

| sample t (rel) | frame dt | nonce in raw3 | nonce in stripped3 | nonce anywhere | painted/padded | raw window ground | echo pos |
|---|---|---|---|---|---|---|---|
| +1.02s | -9ms | False | False | True | 10/17 | mixed | 8 |

**Leg condition UNMET** — designed to sample the raw window on paint; it sampled mixed.

Echo position across the 111 frames holding it: 7-8 from the painted bottom (the stripped 3-line window is positions 1-3).


### Counterfactual: screen_tail window on the same schedule

**sent, cleanly (no spurious Enter)**
(Fidelity caveat: the counterfactual's retry Enters were not really pressed; an Enter on an empty composer cannot remove the transcript echo, so this biases toward the echo persisting — the direction being probed.)

### Full timeline (rel to submit Enter)

| t | raw3 | stripped3 | anywhere | painted/padded | echo pos |
|---|---|---|---|---|---|
| -0.45s | False | False | False | 11/17 | - |
| -0.35s | False | False | False | 11/17 | - |
| -0.24s | False | False | False | 11/17 | - |
| -0.14s | False | False | False | 11/17 | - |
| -0.03s | False | False | False | 11/17 | - |
| +0.07s | False | False | True | 10/17 | 7 |
| +0.17s | False | False | True | 10/17 | 7 |
| +0.28s | False | False | True | 10/17 | 7 |
| +0.38s | False | False | True | 10/17 | 7 |
| +0.48s | False | False | True | 10/17 | 7 |
| +0.59s | False | False | True | 10/17 | 7 |
| +0.69s | False | False | True | 10/17 | 7 |
| +0.80s | False | False | True | 10/17 | 7 |
| +0.90s | False | False | True | 10/17 | 7 |
| +1.01s | False | False | True | 10/17 | 8 |
| +1.11s | False | False | True | 10/17 | 8 |
| +1.22s | False | False | True | 10/17 | 8 |
| +1.32s | False | False | True | 10/17 | 8 |
| +1.42s | False | False | True | 10/17 | 8 |
| +1.53s | False | False | True | 10/17 | 8 |
| +1.63s | False | False | True | 9/17 | 7 |
| +1.73s | False | False | True | 9/17 | 7 |
| +1.84s | False | False | True | 9/17 | 7 |
| +1.94s | False | False | True | 9/17 | 7 |
| +2.05s | False | False | True | 9/17 | 7 |
| +2.15s | False | False | True | 9/17 | 7 |
| +2.26s | False | False | True | 9/17 | 7 |
| +2.36s | False | False | True | 9/17 | 7 |
| +2.47s | False | False | True | 9/17 | 7 |
| +2.57s | False | False | True | 9/17 | 7 |
| +2.68s | False | False | True | 9/17 | 7 |
| +2.78s | False | False | True | 9/17 | 7 |
| +2.88s | False | False | True | 9/17 | 7 |
| +2.99s | False | False | True | 9/17 | 7 |
| +3.09s | False | False | True | 9/17 | 7 |
| +3.20s | False | False | True | 9/17 | 7 |
| +3.30s | False | False | True | 9/17 | 7 |
| +3.41s | False | False | True | 9/17 | 7 |
| +3.51s | False | False | True | 9/17 | 7 |
| +3.62s | False | False | True | 9/17 | 7 |
| +3.72s | False | False | True | 9/17 | 7 |
| +3.82s | False | False | True | 9/17 | 7 |
| +3.93s | False | False | True | 9/17 | 7 |
| +4.03s | False | False | True | 9/17 | 7 |
| +4.14s | False | False | True | 9/17 | 7 |
| +4.24s | False | False | True | 9/17 | 7 |
| +4.34s | False | False | True | 9/17 | 7 |
| +4.45s | False | False | True | 9/17 | 7 |
| +4.55s | False | False | True | 9/17 | 7 |
| +4.66s | False | False | True | 9/17 | 7 |
| +4.76s | False | False | True | 9/17 | 7 |
| +4.87s | False | False | True | 9/17 | 7 |
| +4.97s | False | False | True | 9/17 | 7 |
| +5.07s | False | False | True | 9/17 | 7 |
| +5.18s | False | False | True | 9/17 | 7 |
| +5.28s | False | False | True | 9/17 | 7 |
| +5.39s | False | False | True | 9/17 | 7 |
| +5.49s | False | False | True | 9/17 | 7 |
| +5.60s | False | False | True | 9/17 | 7 |
| +5.70s | False | False | True | 9/17 | 7 |
| +5.80s | False | False | True | 9/17 | 7 |
| +5.91s | False | False | True | 9/17 | 7 |
| +6.01s | False | False | True | 9/17 | 7 |
| +6.12s | False | False | True | 9/17 | 7 |
| +6.22s | False | False | True | 9/17 | 7 |
| +6.33s | False | False | True | 9/17 | 7 |
| +6.43s | False | False | True | 9/17 | 7 |
| +6.53s | False | False | True | 9/17 | 7 |
| +6.64s | False | False | True | 9/17 | 7 |
| +6.74s | False | False | True | 9/17 | 7 |
| +6.85s | False | False | True | 9/17 | 7 |
| +6.95s | False | False | True | 9/17 | 7 |
| +7.06s | False | False | True | 9/17 | 7 |
| +7.16s | False | False | True | 9/17 | 7 |
| +7.26s | False | False | True | 9/17 | 7 |
| +7.36s | False | False | True | 9/17 | 7 |
| +7.47s | False | False | True | 9/17 | 7 |
| +7.57s | False | False | True | 9/17 | 7 |
| +7.68s | False | False | True | 9/17 | 7 |
| +7.78s | False | False | True | 9/17 | 7 |
| +7.88s | False | False | True | 9/17 | 7 |
| +7.99s | False | False | True | 9/17 | 7 |
| +8.09s | False | False | True | 9/17 | 7 |
| +8.20s | False | False | True | 9/17 | 7 |
| +8.30s | False | False | True | 9/17 | 7 |
| +8.41s | False | False | True | 9/17 | 7 |
| +8.51s | False | False | True | 9/17 | 7 |
| +8.61s | False | False | True | 9/17 | 7 |
| +8.72s | False | False | True | 9/17 | 7 |
| +8.82s | False | False | True | 9/17 | 7 |
| +8.93s | False | False | True | 9/17 | 7 |
| +9.03s | False | False | True | 9/17 | 7 |
| +9.13s | False | False | True | 9/17 | 7 |
| +9.24s | False | False | True | 9/17 | 7 |
| +9.34s | False | False | True | 9/17 | 7 |
| +9.44s | False | False | True | 9/17 | 7 |
| +9.55s | False | False | True | 9/17 | 7 |
| +9.65s | False | False | True | 9/17 | 7 |
| +9.76s | False | False | True | 9/17 | 7 |
| +9.86s | False | False | True | 9/17 | 7 |
| +9.97s | False | False | True | 9/17 | 7 |
| +10.07s | False | False | True | 9/17 | 7 |
| +10.17s | False | False | True | 9/17 | 7 |
| +10.28s | False | False | True | 9/17 | 7 |
| +10.38s | False | False | True | 9/17 | 7 |
| +10.49s | False | False | True | 9/17 | 7 |
| +10.59s | False | False | True | 9/17 | 7 |
| +10.70s | False | False | True | 9/17 | 7 |
| +10.80s | False | False | True | 9/17 | 7 |
| +10.91s | False | False | True | 9/17 | 7 |
| +11.01s | False | False | True | 9/17 | 7 |
| +11.11s | False | False | True | 9/17 | 7 |
| +11.22s | False | False | True | 9/17 | 7 |
| +11.32s | False | False | True | 9/17 | 7 |
| +11.43s | False | False | True | 9/17 | 7 |
| +11.53s | False | False | True | 9/17 | 7 |

## Verdict inputs

- tall: stripped-counterfactual → sent, cleanly (no spurious Enter)
- full: stripped-counterfactual → sent, cleanly (no spurious Enter)

## Run notes (hand-recorded in NOTES.md; regeneration re-appends it verbatim)

Hand-recorded 2026-08-05 after the fdb3e19 push review; the sections above are
analyze.py output over the frames, and analyze.py re-appends this file verbatim
whenever the report is regenerated.

### The full leg's intended condition was not met

The full leg was designed to put the shipped raw `tail -3` window ON PAINT ("a
pane the render fills", measure.sh's header). The shrink target was the painted
count taken on the 49-row pane BEFORE the resize (17); the CLI reflows smaller
when it repaints after a resize, and painted only 9-11 lines on the 17-row pane
it was given. At the full leg's verify sample the raw window sat on the border,
the footer, and one padding row (samples table above: painted 10/17, raw3
False, ground `mixed`) — chrome, never the composer region or the echo, which
sat 7-8 painted lines up. So the run measured a pure-padding case (tall) and a
chrome-straddling case (full), not padding + filled; the raw-window-on-paint
case is unmeasured. It is moot for the shipped reader (send's verify strips
blanks before tailing, screen_tail), and measure.sh now re-measures after every
resize step and records the convergence (resize.txt in future archives), with
the leg-condition flag above catching a miss loudly.

### An unplanned composer write mid-capture (full frames 053-115)

From full/frames/frame-053.txt (about +4.9s after the full submit) to the end
of the capture, the composer holds `Reply with only: pong (hbverify-tall-98694)`
— typed, never submitted. The rig did not send it: full/tmux-calls.log holds
only the leg's own two send-keys (the literal type and one Enter), and 98694 is
not this run's PID (both leg nonces carry 98693). The writer and its route are
unrecorded; 98694 sitting one above the run's own PID suggests a sibling
process started next to the run — INFERRED, not verified. Two things rest on
these frames:

- Classification is unaffected: the stray string contains neither leg's nonce,
  so no column in the tables above ever read it.
- hb-fleet.sh's send comment cites "a stuck composer's input line sits third
  from the bottom (one-line footer, measured)". The measurement is these
  frames: a composer genuinely holding unsubmitted text in a live claude pane,
  its input line third from the painted bottom (input, border, one-line
  footer). Real render, accidental provenance — recorded here so the cite
  carries it.
- The same frames measure the two windows against a held composer on this
  geometry: in frame-053 the input line (row 13 of 17, painted rows 13-15 =
  input, border, footer, then two padding rows) sits INSIDE the stripped
  3-line window and OUTSIDE the raw `tail -3` (footer, padding, padding) —
  the raw window misses a stuck composer whenever any padding trails the
  footer, the strip cannot.
