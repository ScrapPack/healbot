# E2E — the operator journey, walked

Date 2026-08-03. Mandate: use this system the way a human operator uses it, not the way an
agent reads it. Every phase before this one was built by agents reading source; the
documented operator path — README Quickstart, `hb-fleet.sh start` to an attached cockpit, the
crew as a captain, the grid as a person, the troubleshooting table as a person who has the
symptom — had never been walked start to finish by anyone. This is the record of walking it.

Method: the repo's own tiers (VERIFIED = read the code, cite `file:line`; TESTED = ran it,
exit code captured; INFERRED; SUSPECTED). Exit codes are assigned before they are printed, so
none of them is `tail`'s. Where the docs and the running system disagreed, the disagreement is
written down as a finding rather than smoothed over, and the direction of the repair is named.
Nothing paid was run: the opencode half stops at the last free keystroke, and that boundary is
stated where it falls (§4).

Fifteen findings. Seven were repaired in this change, seven carry probe rows, four are open
items that need an owner's decision rather than a patch.

---

## 1. The cold-start read

Predictions were written from `README.md` alone and sealed before any other file was opened,
then the Quickstart was run verbatim in a throwaway clone. Every command's exit code was
captured. The Quickstart works: a stranger with bun, node, tmux, python and the claude CLI on
PATH gets from `git clone` to four of five tiers READY without deviating from the page.

| Quickstart step | Result |
|---|---|
| `git clone … && cd healbot` | TESTED exit 0, 1.6 s, 102 MB tree (16 MB `.git`) |
| `python3 harness/doctor.py` | TESTED exit **0**, seven WARN rows, no FAIL — see finding 1 |
| `git config core.hooksPath gate/hooks` | TESTED exit 0, silent |
| `git clone sst/opencode …` / `checkout -b healbot 7534d23` / `git apply` | TESTED exit 0, 0, 0 |
| `bun install` | TESTED exit 0, 4,694 packages, 10.2 s |
| `cp -R fork/packages/. …` + `cp -R fork/.opencode/. …` | TESTED exit 0; doctor's `fork overlay` row then reads *all overlay files byte-identical to the checkout* |
| `python3 -m venv … && pip install pyte` | TESTED exit 0 |
| `. harness/env.sh` | TESTED exit 0 |

The reconstitution claim the README makes about itself holds. `git apply` alone leaves the
checkout behind `fork/` (the third-copy trap, `docs/CLONE.md` §8); the closing `cp -R` is what
makes the doctor's overlay row pass, and it did. The tier summary moved from one READY (crew
fleet) to four across the walk, with the claude workflow the only one left NOT YET, because
its blocker is an interactive login.

**Finding 1 — the doctor exits 0 on a clone that can run almost nothing.** TESTED: on the
fresh clone every deficiency — no gate hook, no venv, no `opencode/` checkout, unmaterialized
crew constraints, a signed-out config root — is a WARN, and the process exits 0. The README
says *"fix what it names"*, and it does name all of them, but a reader who chains
`python3 harness/doctor.py && …` gets a green light on a machine where four of five tiers are
NOT YET. The tier block is the honest surface and it is printed; the exit code is the one a
script reads. Not repaired here: WARN-vs-FAIL is the doctor's whole state lattice and
promoting these rows would fail a machine that is deliberately partial (a PC with no tmux, by
design). Named as open item A.

**Finding 2 — `HEALBOT_RETIRE_AT` reads like an environment variable a newcomer can inspect,
and sourcing `env.sh` does not export one.** TESTED: after `. harness/env.sh` the environment
holds `XDG_CONFIG_HOME`, `OPENCODE_DISABLE_EXTERNAL_SKILLS` and `OPENCODE_DISABLE_CLAUDE_CODE`
and no `HEALBOT_*` at all. The README's load-bearing-numbers section names the variable in
parentheses beside 180,000, which invites `echo $HEALBOT_RETIRE_AT` and gets silence. The
number is a default inside the server plugin and the variable is the override; the harness sets
nothing so the default applies. VERIFIED: the arming line the plugin prints is what an operator
can actually read, and `probe_headless_arm.py` asserts both the spelling and the 180,000
default. Repaired in `README.md` by saying so in one clause.

**Finding 3 — the Quickstart does not say that auth is per-clone.** TESTED: the throwaway
clone's `harness/claude` root was SIGNED OUT, and the doctor said so; the owner's main checkout
was signed in the whole time. VERIFIED at `harness/env.claude.sh`: the credential is keyed to
the config root, so every clone and every pool slot starts signed out. The README's *"one-time
login on first use"* is true per clone and reads as true per machine. Repaired in `README.md`.

Two smaller observations, recorded and not repaired because both are cosmetic: the first
doctor run always WARNs `push gate NOT wired`, because the Quickstart wires the hook on the
line *after* the doctor; and the doctor's own settings-migration containment fired on the fresh
clone exactly as `HARNESS.md`'s trap row predicts (`claude CLI rewrote settings.json —
restored`), leaving `git status` clean, which is the containment working rather than a finding.

---

## 2. The cockpit, one verb

`harness/hb-fleet.sh start` had never been run end to end: prior sessions ran `preflight` and
`up` separately because attach needs a real terminal. It was driven here inside a real pty
(`.carryover/verified/term.py`), twice — once against the stale session left from 2026-08-01,
once against no tmux server at all — so both the create branch and the reuse branch are
exercised.

TESTED, both runs: `preflight` exit 0 with five OK rows, `up` builds bridge + crew, both
optional panes are detected rather than flagged (nvim and the grid, each because the machine
has what it needs), `attach` lands in the cockpit, the status line reads
`hb-main @ healbot` on the left and the key hints on the right, `C-b 1` and `C-b 0` move
between crew and bridge, `C-b d` detaches and the fleet survives it. `start` on a live fleet
reattaches without rebuilding, as documented.

**Finding 4 — the `C-b ?` help overlay opened on its own last third, and the verb it exists to
teach was off-screen.** TESTED at the shipped geometry: the card renders 45 rows at the
popup's inner width and the box held 26, so the visible overlay began at `kill` — `start`,
`help`, `preflight`, `up`, `spawn`, `ls`, `state` and `send` were all above the top edge. A
tmux popup does not scroll and gives no indication that anything was dropped, which is why
three prior sessions had no reason to doubt it: `preflight` reports *display-popup available,
so the help overlay works*, and it does work, in the sense that it appears.

Repaired: the popup is sized to the card (`harness/hb-fleet.sh`, the `?` binding). Re-driven
afterwards, TESTED: the first card line, a middle line, the key map and the last line are all
on screen simultaneously. The guarantee has a stated bound, added after the push review asked
for its scope: tmux clamps a popup to the client's terminal, so the fit holds at 96x36 or
larger and a smaller terminal truncates the card the same way. The cockpit builds its own
session larger than that; an operator attaching from a 24-row window does not get the promise,
and now the binding says so. Guarded: `probe_fleet_claude.py` now derives the card from source —
the header line range plus the key-map heredoc — computes its rendered height against the
popup's declared geometry, and requires the fit, with a mutation leg for the pre-fix numbers
and another for a card grown one line past the box. That pairs with the range check already
there: the old row asserts the card's content is whole, the new one asserts the box can show
it.

**Finding 5 — the card said the popup dismisses with `q`, and `q` leaves it open.** TESTED
twice on tmux 3.7 with a border-shaped predicate: `C-b ?` opens the popup, `q` leaves it up,
Escape closes it. The claim lived in a source comment beside the binding, and the card itself
named no exit key at all — an operator who reads the comment, opens the card and presses `q`
is stuck on a modal box with no listed way out. Repaired: the comment now records what was
measured, and the card's own `?` row names Escape. Guarded by a probe row plus its mutation
leg.

That second measurement is itself a finding about method. The first dismissal check asserted
on the card's text and reported that neither key worked — wrong, because the bridge pane
prints the same card as its login banner, so the text was on screen either way. It is
`term.py`'s documented substring hazard one method up: `exact()` is case-sensitive and still
collides. The sound predicate is the popup's border, which nothing else on that screen draws.

**Finding 6 — the three sources of the help text agree, and the reason is that there is only
one.** VERIFIED at `harness/hb-fleet.sh`: `hb_header()` prints a line range of the script's own
header; `usage()`, `hb_help()` and therefore both the popup and the bridge banner all render
that. TESTED: `hb-fleet.sh help` and the rendered popup carry the same 32 lines. The only text
not shared is the cockpit key map, which is not a command list and lives nowhere else. No
divergence to report — this row exists because the assignment asked for the comparison, and
the answer is that the design forecloses it.

**Finding 7 — a fleet session created before the `@hb_role` marker existed gets a duplicate
pane on its first `start`.** TESTED: the stale 2026-08-01 session's nvim pane carried no
`@hb_role`, so `up`'s idempotence check could not see it and split a second nvim pane beside
it — two nvim panes in the bridge window, both alive. This is the marker doing its job for
every session created since; it cannot retroactively label a pane created before it. Remedy is
one command (`hb-fleet.sh down`, then `start`) and the fresh run had exactly one of each pane.
Recorded rather than repaired: the code is right and the condition can fire at most once per
pre-marker session.

---

## 3. The crew, as a captain

Two crewmates, driven only through the documented verbs — `spawn --brief`, `ls`, `state`,
`peek`, `send`, `occupancy`, `kill` — with no reaching around the script into tmux except to
read a screen the script had already told me to read. `alpha` took a pool slot
(`spawn --slot`) with a brief to write a small report; `beta` took an explicit `--dir` in a
directory the CLI had never seen.

**`state` told the truth at every stage.** TESTED, one crewmate observed through all four:

| Stage | What `state` said |
|---|---|
| booting (t+4 s) | `alive \| screen: unreadable \| hooks: session-start 4s ago` |
| busy (briefed) | `alive \| screen: busy \| hooks: session-start 10s ago` |
| idle (turn done) | `alive \| screen: idle \| hooks: stop 19s ago` |
| blocked (fresh dir) | `alive \| screen: trust-dialog \| hooks: no hook events` |
| killed | `missing \| screen: unreadable` |

The `unreadable` reading during boot is correct rather than a gap: the CLI has painted nothing
matching a marker yet, and the hook channel already carries `session-start`, so the two halves
disagree in the informative direction. The five-state vocabulary earned its keep at `beta`,
whose spawn returned *"beta is at the first-launch trust dialog — attach and answer it once for
this directory"* — the documented path, followed literally: attach, `C-b 1`, Enter on the
dialog's own default, dialog cleared, `state` reads idle. TESTED.

**`send` refuses a busy crewmate, and `--force` behaves as documented.** TESTED with the busy
marker confirmed on screen first: the plain send exits **2** with *"alpha looks busy ('esc to
interrupt' on screen). --force to interrupt-and-queue anyway"*; the same text with `--force`
exits 0, and the crewmate's transcript shows it queued and answered after the in-flight tool
call finished. Note the honest limit the script already documents: three sends landed while
the crewmate was between turns and were accepted, because the refusal reads the screen and the
screen said idle. The refusal is a busy-marker check, not a lock.

**`occupancy` returns a real number.** TESTED: 33,507 then 34,471 tokens on the same crewmate
across two reads, from the transcript rather than the screen; on `beta`, before its first turn,
it printed the transcript path and said there was none yet rather than printing 0. Both are
the documented behaviour.

**Finding 8 — a crewmate's pool lease reports its holder as dead from the moment the spawn
returns.** TESTED: with `alpha` alive and working, `pool.py status` read
*`LEASED hb-main (crew alpha) … — holder pid DEAD; release explicitly if abandoned`*. VERIFIED,
at the time, at line 252 of `harness/pool.py` (the lease dict as it then stood): the lease
recorded `os.getpid()`, and the process that calls
`acquire` is the short-lived `pool.py` invocation inside `spawn`'s command substitution, which
exits seconds later. The crewmate is never the recorded holder, so the liveness hint is
structurally always-dead for exactly the caller the pool was built for, and it advises the
operator to release a slot that is genuinely in use. Not repaired: what pid *should* be
recorded is a design choice (the pane's process, the tmux server, or nothing at all — and
`os.kill(pid, 0)` is already named Mac-only), so it is open item B. Closed the same day;
item B records the design.

**Finding 9 — `kill` leaves the slot leased, confirmed.** TESTED end to end: after
`kill alpha` (exit 0, with the resume hint), `pool.py status` still showed slot-1 leased to
`crew alpha`. The gap was a known one; this is its first measurement from the operator side,
and the manual repair worked exactly as the pool's refusals promise — `release` exited **2**
and printed the uncommitted file rather than destroying it, and `release --discard-work` exited
0, reset the slot and dropped the lease. Closed as item E the same day: `kill` now attempts
that release itself.

**Finding 15 — `kill` on a crewmate that is already gone spoke tmux, not fleet.** Found while
cleaning up rather than while testing. TESTED by killing a crewmate `down` had already taken:
exit 1 with tmux's own `can't find pane: %5`, no `hb-fleet:` prefix — under `set -eu` the
failing `kill-pane` ends the script before its report line. Repaired: the branch now frames the
missing case by name and exits **2**, matching `send` and `brief`, and TESTED at exit 2 with
the crewmate's resume line. Deliberately *not* by reaching for the dead-pane helper those two
use, which the push review's own note might suggest: that helper is true for dead-**or**-
missing, and a dead-but-present pane is exactly what `kill` exists to reclaim, since
`remain-on-exit` leaves corpses holding crew slots. Guarded with two mutation legs, one for an
unguarded `kill-pane` and one for reaching at that helper.

The first version of that guard is worth its own sentence, because it is this project's
characteristic bug in miniature. It went red against the correct fix — the predicate asserted
the helper's name was absent from the branch, and the fix's own comment explains which helper
it avoids, so the check was reading prose that mentions the helper rather than code that calls
it. Comments are stripped before the predicate runs now. An assertion that its own explanation
can flip is decoration wearing a load-bearing name.

**Finding 10 — an unexplained line in a crewmate's composer, explained.** `peek` showed
`❯ fourth probe line` on `alpha` — text nobody had sent. It is not in the transcript, not in
the fleet's buffers, and not in any brief. Captured with escape sequences rather than guessed
at: the run carries SGR 2, so the CLI renders it **dim**. It is a composer suggestion the CLI
predicted from the three real sends before it, not input. Consequence worth naming, and it is
INFERRED rather than measured: every fleet verb that reads a crewmate through
`capture-pane` — `state`, `peek`, and `send`'s own submit verification — sees suggestion text
and typed text alike, because a plain capture drops the styling that tells them apart. Nothing
misfired here (all three sends verified and cleared), so this is recorded as a hazard with a
mechanism, not as a defect.

---

## 4. The grid, and where the free path ends

The grid was driven in the cockpit's own grid pane, which is `harness/fleet.sh` running the
fork from source. TESTED: `/healbot` renders
`Healbot  0 sessions   a answer · x retire · tab next blocked · enter focus · r refresh · q close`
over *No sessions yet*, and the API agreed — `GET /session` with the directory header returned
`[]`, so the zero was true rather than the wrong-instance trap. Fork build confirmed two ways:
the server's own argv runs `bun run --cwd …/opencode/packages/opencode`, and VERIFIED at
`harness/fleet.sh:73-75` the fallback warning belongs to the branch that resolves the installed
binary, which this run never took.

One empty session was created through the API to give the roster something to render. That
costs nothing — no model turn, zero tokens — and it was deleted afterwards, so the corpus the
growth probe measures is unchanged. TESTED with it present: the header read `1 session`, the
cell rendered its title with `idle` and `no history`, `r` refreshed, `enter` focused the
session route, and `/healbot` came back to the grid (there is no key back — the documented
behaviour).

**Finding 11 — in the default cockpit the session route renders no session id, because the
grid pane is 110 columns wide.** The sidebar is gated on width > 120 and is the only thing that
renders an id. TESTED in both directions: at 110 columns, focusing the session showed no id
anywhere on screen; widened to 160, the same keystroke produced the sidebar with
`ses_037de5e5effe4h0gxdGO0v54MD`, its context line and its cost line. This is a known
source-level trap that had only ever been discussed as a rig-geometry hazard; the operator
consequence is new, and it is not incidental — the cockpit's bridge window splits three ways,
so 110 is what the grid pane gets by construction on a 220-column terminal. Recorded, not
repaired: the fix is either a layout decision or an upstream width gate, both owner calls.
Open item C. Closed the same day; item C records the layout choice.

**Where the free path ends, and why it ends there.** The `x` retirement key was NOT pressed.
VERIFIED at `harness/config/opencode/plugin/healbot.ts:581`: `retire()` seeds the successor
through `prompt_async` with the handoff document, so pressing `x` on a real session buys a
model turn. Everything up to that keystroke is free and was done; the keystroke itself needs
the owner's go. Also not reached for the same reason: `a` (answering a block requires a session
that is blocked, which requires a turn), and the `x`-writes-a-request half of the relay, whose
free surface is already covered by `probe_request_channel.py`.

**Finding 12 — `/healbot` on the installed binary, from the operator's side.** TESTED on the
1.18.5 release under the harness config: the model pin arms (`Build · GPT-5.6 Sol OpenAI` on
the composer) and the palette answers `No matching items`. The troubleshooting row is correct;
what it does not carry is the string an operator actually sees, and *No matching items* is what
they will search for.

---

## 5. The troubleshooting table

Nine of the eleven rows were exercised. Two cannot be triggered without breaking something the
walk had to keep working, and are recorded as such rather than assumed true.

| Row | Verdict |
|---|---|
| `/healbot` does not exist | TESTED — the release binary answers `No matching items` (finding 12) |
| Grid's `x` retires nothing | NOT TRIGGERED — reaching it needs the `x` path, which is paid (§4) |
| API/grid shows 0 sessions | TESTED — with a session present under the repo directory, the same server returned `[]` for a wrong `x-opencode-directory` and for no header at all |
| Session boots with no model pin | TESTED, and the row undersells it — a wrong `HARNESS_ROOT` makes `env.sh` refuse with exit 1 and export nothing, so the described symptom cannot be reached that way on this platform |
| Crewmate spawns signed out | TESTED at the mechanism, in a scratch config root: `claude auth status` exits **1** with `"loggedIn": false` there and **0** in the owner's root. Signing the harness root out to see the refusal itself was declined — it would have blocked §3 |
| Crew constraints stale on a PC | NOT TRIGGERABLE here — the copy-instead-of-symlink branch is Windows-only; the symlink is materialized on this machine |
| Fleet `state` says "no hook events" forever | TESTED — with `HB_FLEET_DIR` unset the hook exits 0, prints nothing and writes nothing; with it set the same payload writes the state file. Fail-open, as documented, and `state` printed `no hook events` for a live crewmate whose file did not exist yet |
| A probe prints green on a fresh clone | TESTED — with the checkout hidden, `probe_twin.py` exits **1** naming the missing checkout and the rebuild page. The floor did its job. (Exit **3** since the item-D close later the same day) |
| tier2 from a worktree slot shows reds | NOT RUN — tier 2 is a phase-boundary tool and the row concerns a slot, not this checkout |
| Gate exit 3 vs 2 | TESTED and the row is WRONG for the commonest case — see finding 13 |
| Grid's `x` / retirement thresholds | covered by the §4 boundary note |

**Finding 13 — the gate's documented exit-code semantics do not hold for a missing checkout.**
`docs/OPERATIONS.md` says *3 = a check could not run (claim unmeasured); 2 = a check ran and
said no*. TESTED with `opencode/` hidden: the citations and twin checks both report that the
derived checkout is absent and name the page that rebuilds it, and the gate exits **2**, not 3.
VERIFIED at `gate/gate.py:124`: a Tier-1 row's state is decided by the subprocess exit code
alone — `PASS` on 0, `ERROR` only when the code is `None` (the executable could not be
launched at `gate/gate.py:73`, or it timed out at `gate/gate.py:75`), `BLOCKED` for every
other nonzero.

The three exits an operator can actually reach here were each measured rather than reasoned
about, after a push review pointed out that two of them were being asserted. TESTED in the
throwaway clone: with `opencode/` absent the gate is **2**; with the venv moved *outside the
tree* and `gate.py` run directly, all four Tier-1 rows are ERROR and the gate is **3**; and on
the real `git push` path with the venv absent, `gate/hooks/pre-push` refuses at **1** by name
before the gate starts, so an operator following the documented workflow never sees the 3. The
first attempt at the middle measurement was contaminated and is worth recording: parking the
venv *inside* the repo put 522 files into the change and the run came back 2, which is the
right answer to a question I had not meant to ask. A probe that ran, discovered its input missing
and exited 1 is therefore BLOCKED, however loudly it says it could not measure anything. The
gate's own lattice comment defines ERROR as *a check could not run*, so the code and the
doc-level gloss disagree; `docs/CLONE.md` §8 already records the exit-2 observation without
reconciling it with the gloss. Repaired at the doc end — `docs/OPERATIONS.md` now says what the
mapping actually is. Teaching Tier 1 to distinguish "ran and failed" from "ran and could not
measure" needs a sentinel exit code across every probe, which is a design change, not a doc
fix: open item D. Closed the same day; item D records the sentinel.

---

## 6. The gate, as a contributor

This change is the small real change. It carries repairs for findings 2, 3, 4, 5, 13 and 15,
the `term.py` repair below, eight new probe rows with their mutation legs, and this document.

**Finding 14 — the repo's own instrument for asserting on a rendered terminal could not host
tmux, and nothing had noticed because nothing had tried.** TESTED: driving
`hb-fleet.sh start` through `term.py` raised `TypeError:
Screen.report_device_status() got an unexpected keyword argument 'private'` on the *first*
pump, before any assertion ran. tmux probes its terminal with private device queries at
startup and `pyte.Screen.report_device_status` takes `(self, mode)`. Every rig in the suite
drives the opencode TUI, which sends no such query, so the gap was real and invisible.
Repaired narrowly in `term.py`: a `Screen` subclass that swallows that one private query and
changes nothing else, because that class is what the whole rig renders through. The query is
deliberately left unanswered rather than replied to — an earlier draft wired pyte's reply
channel and a stray `6c` was typed into the captain's shell. TESTED after the repair: stock
`term.py` drives the cockpit and reads its status line.

That repair had to be corrected before this page was true. The first version overrode **two**
handlers and this paragraph said neither accepted the keyword; the push review checked the
dependency and the claim was wrong. VERIFIED by reading the installed pyte in the rig venv
(`Screen.report_device_attributes`, whose own changelog note records the behaviour): it takes
`**kwargs` and has done nothing when `private` is set since pyte 0.7.0, so only the other
handler could raise — which is exactly what the captured traceback named. No live `file:line`
here on purpose: the venv is derived and gitignored, so a citation into it resolves for nobody,
and the citation sweep said so before this page was pushed. The second override was redundant
and the prose was a wrong belief about a dependency, held in the file every rig renders
through. Both removed.

Suite and gate, this change (each exit code captured directly, never through a pipe):

- **Free suite: 22 probes, every one exit 0** — four in the gate's Tier 1 and eighteen in
  tier 2, each against its own declared floor. `probe_fleet_claude.py` finishes this change at
  68 rows against a floor of 68, all 68 measured and passing. It reached that in two steps —
  five rows for the cockpit, three more for finding 15 — and the floor caught its own author
  at each: the first draft declared 66 for five rows and `probe_rig_contract.py` went 39/40 on
  the unsatisfiable floor before the run did, and the count in this very paragraph was left at
  the earlier figure until the push review read it back. A recorded score is a claim about a
  file at a moment, and this page had to be told that twice.
- **`gate/gate.py`: exit 0**, on the working tree and again on the pushed range through the
  hook.

---

## 7. Open items

**A. The doctor's exit code on a partial machine.** Exit 0 with WARN rows is defensible — a
deliberately partial machine must not fail — but it makes `doctor && next-command` a green
light on a clone that can run one tier of five (finding 1). Either the exit code grows a third
state or the docs stop implying it is a gate.

**B. What pid a pool lease should record.** Line 252 of `harness/pool.py`, as the walk found
it, recorded the acquiring
process, which for every crew spawn is a process that exits immediately, so the status line
tells the operator a live crewmate's slot is abandoned (finding 8). The candidates — the crew
pane's own process, the tmux server, or dropping the liveness hint — differ in what they claim
and one of them has to be chosen deliberately.

CLOSED 2026-08-03: the pane's root process, recorded after the fact. Acquire now records no
pid at all, because every real acquirer is short-lived (a shell acquire IS the pool.py
invocation, so the false-DEAD note was never the fleet's alone), and a new `adopt` verb lets
the process that actually outlives the acquire declare itself; spawn adopts the pane's root
pid onto the lease once the pane exists. TESTED live: a working crewmate's slot line now
carries no note at all, and a lease with no recorded pid says "liveness unclaimed" explicitly
rather than staying silent, because silence on a probed pid means alive. The DEAD note fires
exactly when the holder died, which probe_pool now exercises with a real corpse pid, the
first exercise that branch has ever had. The tmux-server candidate was rejected because its
claim is about the fleet rather than the holder: one server, many slots, and a killed
crewmate would read ALIVE, inverting the measured error instead of fixing it.
`os.kill(pid, 0)` stays, so the pool's Mac-only boundary is unchanged.

**C. The cockpit's grid pane is below the sidebar's width gate.** 110 columns against a
gate of 120, so the session route shows no session id in the default layout (finding 11).
Layout change, gate change, or documented as expected — an owner call.

CLOSED 2026-08-03: layout change. The grid pane now splits full window width (`-vf` in
`hb-fleet.sh`), TESTED on the fresh cockpit: bridge 110x24, nvim 109x24, grid 220x24. Full
width is the robust form because attach re-clamps every pane to the client terminal, so the
halved pane needed a ~242-column client while the full-width pane clears the gate on any
terminal of 121 columns or more, the same bound as running fleet.sh bare. The fork's gate is
untouched on purpose: it is upstream code in the derived checkout, not one of the seventeen
overlay files, and growing the overlay by a 2,500-line upstream file to avoid a one-flag
tmux change would buy patch drift forever. Guarded by a probe row and its mutation leg. One
consequence worth knowing: the `@hb_role` marker makes panes idempotent, so a fleet built
before this change keeps its half-width grid until `down` and a fresh `start`.

**D. Tier 1 cannot distinguish "could not run" from "ran and said no."** `gate/gate.py:124`
maps every nonzero probe exit to BLOCKED, so for tier-1 probes the interface is coarser than
`gate/GATE.MAP.md`'s "error is not blocked" paragraph describes (finding 13; the paragraph
was cited here by line and GATE.MAP moved under it, so the pointer is by name now). Note the
rest of the gate does make the
distinction — a broken truth table, a failed enumeration and an unmatched fork twin all reach
ERROR on their own (`gate/gate.py:332`, `:351`, `:175`) — which is what makes the tier-1 hole
narrow enough to be missed. A sentinel exit code for cannot-measure, agreed across the probes,
would close it.

CLOSED 2026-08-03: the sentinel is exit 3, the code the gate itself exits with on ERROR, so
the probes now speak the lattice the gate already speaks (harness/pool.py's docstring
declared the same one). Exactly the two declared refusals adopted it — `probe_citations` and
`probe_twin` on the absent checkout — and nothing else: crashes and red verdicts stay
BLOCKED, deliberately, so a broken probe cannot downgrade a real finding to retry-shaped.
The tier-1 mapping and tier2's row mapping each changed in place by one line, which is why
every `gate/gate.py` citation above still resolves. TESTED end to end through the real hook
by `probe_gate_scope.py`'s two new legs: a tier-1 stub exiting 3 records ERROR and refuses
at gate exit 3, and the control stub exiting 1 still records BLOCKED at gate exit 2, four
runs byte-identical at the new 19-row floor. The scope limit, stated plainly: tier 1 now
distinguishes could-not-measure where a probe declares it, and an undiagnosed crash still
reads BLOCKED, the fail-closed direction. The rewritten mapping lives in
`docs/OPERATIONS.md`'s troubleshooting row and `gate/GATE.MAP.md`'s exit-codes section, and
`docs/CLONE.md`'s fresh-clone table carries a dated note.

**E. Also unchanged and still open, from the crew side.** `kill` leaving the slot leased
(finding 9) is a known gap and now measured from the operator's chair; the manual repair is
`pool.py release`, which refuses to destroy work and says so.

CLOSED 2026-08-03: `kill` settles the lease itself. The manifest row records a `slot` flag
at spawn, and kill's success path runs a plain `pool.py release --if-owner` with the pool's
own lines reaching the terminal uncaptured. TESTED both ways: a clean slot released
("restored, payload kept, lease dropped", slot free again), and a slot holding an
uncommitted file refused, named the file, kept the lease, and kill still exited 0 with the
repair command printed, because a refusal over held work is the pool's guard working rather
than a kill failure. The already-gone branch does not auto-release: a stale row cannot prove
the lease is still that crewmate's, so it names `pool.py status` instead.

Testing this close measured two defects the walk had not reached, both repaired and probed
the same day. Killing the last crewmate destroys the now-empty crew window, and the next
spawn misread the missing window as a full one; spawn now re-ensures the window with the
same line `up` uses. And a spawn that failed after taking its lease leaked it, measured as
slot-1 leased to a crewmate that never existed; spawn's split-refusal and boot-death exits
now release the just-taken lease, while the ready-wait timeout deliberately keeps it because
that crewmate is alive in its pane and may still boot. Still open from the same family:
`down` strands every slot crewmate's lease. Named here rather than silently widened into
this close.
