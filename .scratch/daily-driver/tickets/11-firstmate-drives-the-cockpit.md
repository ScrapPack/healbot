# Firstmate drives the cockpit

Type: task
Mode: AFK
Status: closed
Assignee: captain
Blocked by: 03

## Question

Decided 2026-08-05: the captain does not learn to operate the cockpit. Firstmate operates it on the
captain's behalf, and the only thing the captain learns is how to talk to firstmate.

This came out of the grilling as the actual blocker. Asked why stock Claude Code was still the daily
driver, the answer was "I don't know how to operate within the harness." `docs/E2E.md` is already a
written operator walk and it did not close the gap, so a second document is not the fix. The fix is
that there is less to know.

It is feasible because `harness/hb-fleet.sh` already owns the tmux topology. Pane selection is another
verb alongside `spawn`, `peek` and `state`, not a new mechanism.

The verbs to add, each one a thing the captain currently has to do with tmux keys:

- **focus a crewmate**: bring its pane to the front so "show me what crewmate 3 is doing" is a
  sentence rather than a chord.
- **open a diff in the nvim pane**: the handoff ticket 13 needs, and useful on its own.
- **rearrange**: whatever minimum lets firstmate put the right two panes side by side.

Three constraints that are not negotiable:

1. `/firstmate`'s hard rules still hold. Driving the cockpit is not editing a crewmate's files, and a
   captain typing directly into a crew pane stays authoritative intervention to reconcile with, never
   to fight.
2. Every verb is idempotent and names its skips. `hb-fleet.sh start` already works this way: absent
   capabilities are named skips, never refusals. Match it.
3. Anything firstmate can drive on the captain's behalf comes **off** the `C-b ?` command card. The
   card is a scarce, non-scrolling popup whose geometry has already caused one measured failure, and
   the point of this ticket is that there is less to remember, not more.

Blocked by ticket 03 because the firstmate contract settles what the first mate is allowed to do
before new powers are added to it.

**Done looks like:** the captain can say "show me crewmate 3" and "open that diff" to firstmate and
the cockpit does it, with no tmux keys pressed by the captain, TESTED against a live fleet rather than
argued from the script.

## Comments

Overlaps ticket 04, which renders the frontier in the cockpit. Same file, different verbs. Whoever
takes the second one should read the first one's resolution.

## Resolution

Built and TESTED against a live fleet 2026-08-05. **Two of the three listed verbs shipped. The
third is deliberately not built and the reason is in the code, not in judgement.**

**Shipped: `focus <crewmate|nvim|grid> [--no-zoom]`.** Selects the window, selects the pane, and
zooms it. Crew names resolve through the MANIFEST first, exactly as `send`, `brief` and `kill`
resolve, so an unknown name refuses loudly instead of focusing a guessed pane. A new global
`role_pane()` reads the `@hb_role` marker `up` already sets; `up`'s own `hb_has_role` could not be
reused because it is defined inside the `up)` branch and answers a yes/no question during
construction.

**Shipped: `diff [--dir D] <git-diff-args...>`.** Runs git here, writes the output to a file under
`$HB_FLEET_DIR/diffs/`, and hands nvim only a path this script generated. Two rules made it safe
rather than clever: it always opens a NEW TAB and never touches the buffer the captain was in, and
it never builds an `:r !git diff ...` command line, because that would push caller arguments through
tmux `send-keys` and nvim's command line, two quoting layers deep, where a path with a space or a
pipe is an injection rather than an argument.

**NOT built: rearrange / side-by-side. VERIFIED blocker.** Putting a crew pane beside the nvim pane
means `join-pane`, because they live in different windows, and **seven call sites enumerate
`$HB_RUN:crew` by name**. `pane_dead()` and `pane_exists()` both do, and between them they are
consumed by `spawn`, `state`, `send`, `brief`, `kill`, `down` and now `focus`. A joined crewmate
would vanish from `ls` and read as dead or missing in every one of them. That is not a small change
and it is not this ticket; it needs its own, with the census as its subject. `focus` with zoom
covers the stated need, which was to put the right thing in front of the captain.

**TESTED, on an isolated fleet (`HB_RUN=hb-t11`) so no real manifest was touched.** `focus`, six
branches: a cockpit role pane focuses and zooms; a second identical call leaves it zoomed rather
than toggling it off, which is the idempotence the ticket demanded and the bug the code guards, as
`resize-pane -Z` toggles; a live crew pane switches the session's window, selects and zooms; a
remain-on-exit CORPSE focuses and prints that it is dead, exit 0; a manifest row whose pane tmux no
longer lists refuses, exit 2; an unknown name refuses and lists what exists, exit 2. The crew pane
was real and in the crew window, running a shell rather than claude, which `focus` cannot
distinguish because it reads only pane ids and tmux state.

`diff`, four branches: a real 125-line diff opened in the nvim pane, VERIFIED by capturing the pane
and reading the diff back off it with the original buffer still present as a separate tab; an empty
diff prints "nothing to show" and exits 0, because that is a true answer and an empty buffer would
present it as a failure; bad git arguments surface git's own error, exit 2; a cockpit with no nvim
pane gives a named skip with the plain `git diff` to run instead, exit 3, the repo's
cannot-measure sentinel.

**Constraints honoured.** Both verbs are absent from the `C-b ?` card, which stays the captain's;
the firstmate skill documents them instead, and `hb_header`'s literal `4,25` line range is untouched
so the probe's assertion on it still holds. Both are idempotent. Every absence is a named skip.

**Verified after.** `sh -n` and `bash -n` clean. `probe_fleet_claude.py` 107/107 against floor 107.
Whole free suite exit 0, citations 21/21, twins 11/11, doctor exit 0. The test fleet was taken down
and its state directory removed; `.fleet/` holds only the pre-existing runs.

**Residual, named rather than hidden.** No probe row guards the two new verbs. They were TESTED by
hand against a live fleet, which is stronger evidence than a probe for this kind of tmux behaviour
and weaker for regressions. If they earn a row, `/rig-assertion-discipline` first, and the
idempotence leg is the one that matters because it is the one that was nearly wrong.
