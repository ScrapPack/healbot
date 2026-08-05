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
  from the painted bottom (one-line footer)". The measurement is these frames:
  a composer genuinely holding unsubmitted text in a live claude pane, its
  input line third from the painted bottom (input, border, one-line footer).
  Real render, accidental provenance — recorded here so the cite carries it.
- The same frames measure the two windows against a held composer on this
  geometry: in frame-053 the input line (row 13 of 17, painted rows 13-15 =
  input, border, footer, then two padding rows) sits INSIDE the stripped
  3-line window and OUTSIDE the raw `tail -3` (footer, padding, padding) —
  the raw window misses a stuck composer whenever any padding trails the
  footer, the strip cannot.
