# Map: healbot as the daily driver

## Destination

**One cockpit terminal where crew build in parallel across any project, where the captain interacts
through `/firstmate` and `/wayfinder` rather than through tmux, where neovim shows only the diffs a
human must judge, and everything below that bar clears through automatic review.**

Redrawn 2026-08-05 by ticket 01's grilling. The first wording was "Claude Code inside the harness is
the captain's daily driver", which fixed no scope because it named no condition you could test. The
four conditions above are each testable, and each one has tickets under it.

Reaching the end of this map means the captain works this way by default, not that the machinery
exists.

Scope: the human end-to-end path, across every project. Not the measurement rig, not the opencode
half, not the build backlog. **Out of scope** below carries the boundary and the reason.

## Notes

Domain, and the standing preferences every session on this map must consult:

- `HARNESS.md` is the index and the glossary. `docs/agents/` is the tracker, label and domain
  configuration. `NEXT.md`'s `DECIDED` section holds standing decisions that read as defects to a
  fresh reader and are not to be re-opened without evidence.
- Classify every claim VERIFIED, TESTED, INFERRED or SUSPECTED, and never present a lower tier as a
  higher one.
- Skills to invoke before the matching work, not after: `/citation-hygiene` before editing a
  document carrying `file:line` citations, `/rig-assertion-discipline` before touching a probe or
  rig, `/paid-run-protocol` before spending API credits, `/healbot-traps` when behavior contradicts
  expectation. **Ticket 09 is open on whether a harness session can invoke any of them.**
- `/grilling` and `/domain-modeling` are the default resolution pair for a ticket with no more
  specific method.
- Three filenames are banned tree-wide and the gate enforces it: `AGENTS.md`, `CLAUDE.md`,
  `CONTEXT.md`, plus `SKILL.md`. See `docs/agents/domain.md`.
- **This map is planning, not doing.** A ticket resolves a decision. The pull to just build the
  thing is the signal that the way is clear and it is time to hand off.

## Decisions so far

- **The tracker is local markdown under `.scratch/`, tracked, not GitHub Issues.** The gate and the
  probe suite can read the tree and cannot read GitHub. Detail and the wayfinding operations:
  [docs/agents/issue-tracker.md](../../docs/agents/issue-tracker.md).
- **No root `CLAUDE.md`, and the banned-filename invariant is untouched.** Orientation became an
  on-demand slash command instead. Detail: [.claude/commands/orient.md](../../.claude/commands/orient.md),
  trap recorded in [docs/agents/domain.md](../../docs/agents/domain.md).
- **The agent-skills configuration lives in `HARNESS.md`**, not in the file those skills expect,
  because that filename is banned.
- **Four upstream skills installed**: `wayfinder`, `grilling`, `domain-modeling`, `research`, each
  scanned clean for the bang-backtick shell-substitution hole first.
- **[Where the daily-driver workflow actually hurts](tickets/01-where-the-workflow-hurts.md)** — the
  blocker is operator knowledge, not a missing feature; the wanted benefit is parallel work in one
  navigable terminal, not retirement; scope is all projects; crew is the normal shape, not solo. The
  ticket carries the four decisions that followed and the finding that the harness config root
  carries no skills and no plugins.
- **Skills get mirrored into the harness config root**, not shared by symlink and not left out.
  Sharing punctures the isolation silently, which is the failure mode this repo hunts, and mirroring
  is the only option that reproduces on the PC. Ticket 10.
- **[Does CLAUDE_CONFIG_DIR redirect skill resolution](tickets/09-does-config-dir-redirect-skills.md)**
  — yes, for skills and plugins both, so every session the harness has ever launched has run with
  none of either, including the four skills `NEXT.md` orders every session to invoke. Skills VERIFIED
  at source, plugins TESTED free via `claude plugin list`. Settled without spending.
- **[Mirror skills and plugins into the harness config root](tickets/10-mirror-skills-into-harness-root.md)**
  — built. The redirected root now surfaces all 28 skills, sourced from what the DEFAULT root
  exposes rather than the nine tracked twins, because the captain drives `/wayfinder` and the
  planning skills. `doctor.py` gained its own row for it, TESTED red and green. Plugins deliberately
  deferred to a real `claude plugin` install rather than a hand copy of state the CLI owns.
- **The review bar is severity, fail-closed, plus a path escalation.** `gate/review.py`'s `blocking`
  mode already implements the severity half. The escalation set was narrowed by ticket 12 to `gate/`,
  `fork/` and `.carryover/verified/probe_*`, the things that can make the measurement lie; plain
  `harness/` was dropped because it fired on 25 of the last 60 commits. Ticket 13 owns the missing
  handoff to the captain.
- **Firstmate drives the cockpit.** The captain learns how to talk to firstmate and nothing else.
  Ticket 11.
- **Overnight AFK running is permitted, under stated bounds.** Captain's decision 2026-08-05,
  overriding the Out-of-scope entry on fleet autonomy, which is annotated rather than deleted
  because its reasoning still governs the rest. The bounds, all of them load-bearing: `gnhf`
  drives it (`docs/AFK.md` is the measured spec); **AFK `task` tickets only**, never a `grilling`
  or HITL one; **never `--push`**, so the loop commits to its own branch and every push waits for
  a human, which also keeps the advisory review's fix-chains out of the night; a token cap for
  **loop containment and not as a spend figure**, because `--max-tokens` counts cache reads at
  full weight and climbs far faster than the bill; and `harness/gnhf-watch.sh` is MANDATORY,
  because gnhf ships no clock at all and a parked iteration defeats both its caps at once.
- **The two harnesses may load skills differently; they must carry the same skills.** Captain's
  direction 2026-08-05. The skill SET is the invariant across Claude Code and opencode, the loading
  mechanism is not, and whether the two are equally capable is settled by A/B measurement rather
  than by argument, which is ticket 08's subject. Ticket 18 carries the defect that prompted it: the
  harness config root reaches into the DEFAULT config root for one skill, which is what ticket 10
  recorded as rejected, and the doctor row reports it PASS.
- **[Firstmate drives the cockpit](tickets/11-firstmate-drives-the-cockpit.md)** — `focus` and
  `diff` shipped and TESTED live, both idempotent, both off the captain's command card because they
  are firstmate's tools. Side-by-side was NOT built: it needs `join-pane`, and seven call sites
  enumerate the `crew` window by name, so a joined crewmate would read as dead or missing in `ls`,
  `state`, `send`, `brief`, `kill` and `down`. That needs its own ticket with the census as its
  subject.
- **[Ratify the wayfinder and firstmate contract](tickets/03-wayfinder-firstmate-contract.md)** —
  all four ratified, and the contract now lives in `harness/skills/firstmate.md` where sessions
  actually read it. The first mate is the only tracker writer, which the grilling found is close to
  forced: a slot is a detached worktree, so every crewmate holds a divergent copy of the tracker.
  HITL tickets are never spawned to be resolved but MAY be spawned to be prepared, the line being
  facts versus decisions. `Assignee:` records intent while the manifest records liveness, so no pid
  ever goes on a claim line.
- **Plain `git worktree` per project** for non-healbot crew workspaces. The pool is healbot-only by
  construction and Mac-only by mechanism. Ticket 14.
- **[Were the review's error findings ever right](tickets/16-calibrate-the-review-bar.md)** — 18
  real, 0 wrong, 7 unacted, 2 stub records excluded, so the real corpus is 25 findings and not the
  27 ticket 12 carried. False-positive rate 0% over the acted-on findings, and the honest floor is
  narrower than that number looks: no repair commit in the corpus refutes an error finding, while a
  finding judged wrong would land in `unacted` rather than `wrong`. Six of the seven unacted ones
  were verified factually correct, so they are unrepaired rather than noise. **The captain's ruling
  on switching `blocking` on is still outstanding and is carried on ticket 13.** The result that
  bears hardest on ticket 12: severity as the reviewer assigns it did NOT predict what the captain
  acted on, one review having its `warning` and `info` fixed in four minutes and both its `error`
  findings left open to this day. Worked by a crewmate, records only, no credits.
- **[When does the automatic review run, and what bounds its spend](tickets/12-when-does-the-review-run.md)**
  — per crewmate completion in `blocking` mode, wired into `hb-fleet.sh` on the slot-return path
  rather than written as a skill rule, because a rule a first mate must remember is the arrangement
  the gate was built to replace. The pre-push review stays advisory and unchanged. Spend is bounded
  structurally with no dollar ceiling: one review per completion attempt, three attempts per
  objective, then the captain. No crewmate report ever substitutes for a review. The could-not-run
  branch is named `unmeasured`, distinct from `blocked`, with one retry except on timeout. Measured
  here and worth carrying: `blocking` would have refused 20% of the captain's own pushes, a
  timed-out review records no cost at all so no ceiling can be summed from the records, and the crew
  config root was TESTED able to authenticate a review (`gate/runs/20260805-204306-48726-review.json`,
  $0.94 for an 878-byte diff, which is why the bound is reviews times roughly one dollar and not a
  function of diff size).

- **The push exit needs a checkout counter, and the review is not what has to change.** Measured
  2026-08-08 over the 73-record window, replay in
  [21-push-exit-backtest.py](research/21-push-exit-backtest.py): **77% of every reviewed push is a
  repair of a prior review**, no substantive push in the window came back clean (0 of 17), and the
  expected chain is 4.0 repairs. The mechanism is that a repair commit is itself full-bar
  reviewable surface, so each repair buys fresh obligations; findings do NOT recur (148 findings,
  148 distinct keys, zero repeats), so this is generation and not nagging. The reviewer's quota
  cannot be argued down, so the intervention is on what the quota OBLIGATES, which is a pure
  function over the record and therefore replayable and probe-able. Two captain rulings 2026-08-08:
  non-blocking findings leave as **proposed stubs promoted by firstmate**, preserving the
  firstmate-only-writer contract; and the checkout stage lands **advisory**, leaving the `blocking`
  ruling where ticket 13 carries it. Tickets:
  [a push declares what it closes](tickets/22-a-push-declares-what-it-closes.md),
  [a non-blocking finding leaves as a proposed stub](tickets/23-findings-leave-as-stubs.md), and the
  one open decision,
  [does the path escalation apply to a push that only closes findings](tickets/21-escalation-on-a-closing-push.md)
  — ticket 12's narrowing was semantically right and did not narrow: over `1373e1d..05ff622` the
  kept set touches 37/60 commits (62%) against the 33/60 union it replaced, and on a repair push
  it obligates 4.25x more work than severity does.
- **Three more push-exit stages are unowned, and one of them is ready to close.** Found 2026-08-08
  while ticketing the checkout counter.
  [Chain state has nowhere to live](tickets/24-chain-state-has-nowhere-to-live.md): the attempt cap
  ticket 22 inherits from ticket 12 cannot count, because the records it would count are gitignored
  and a pool slot's copy is empty, so a record-counting cap counts to one forever in exactly the
  environment the fleet runs in. **The commits already carry the answer** via the `Review-chain:`
  trailer.
  [The gate blocks on documentation position, not behaviour](tickets/25-the-gate-blocks-on-position-not-behaviour.md):
  four Tier-1 rows refuse every push while the only judge of behaviour is advisory, so a citation
  moved one line refuses and a flagged logic defect ships — an accident of two reasonable choices
  that nobody has ratified as a principle, and the blocking row is itself blind to source files.
  [The staleness stage never left shadow mode](tickets/26-staleness-never-left-shadow-mode.md): its
  calibration was answerable all along — **26 live records, silent on 58% of pushes, bimodal, median
  0.21 s**, which is a detector rather than a generator and is the natural Tier-1 candidate ticket
  25 needs.

## Not yet specified

In scope, not yet sharp enough to ticket.

- **How a project gets onboarded.** Every project now needs a map, an orientation path, and crew
  workspaces. Whether that is one bootstrap verb, a `/wayfinder` invocation, or nothing at all is
  downstream of tickets 02 and 14.
- **Whether crewmates get the captain's whole skill set.** Ticket 10 gave the harness root all 28,
  and crew live in that root. A crewmate whose world is meant to be its brief may not want all of
  them. Sharpens once a crewmate has actually run with the full set and either used it or drowned
  in it, which nothing has yet.
- **Which plugins the harness root should carry, and installed how.** Ticket 10 deferred this
  deliberately: `claude plugin` owns that state and a hand copy would fork it, and most of the
  captain's plugins currently read `disabled` anyway. Sharpens when a plugin is actually wanted in
  a harness session.
- **Side-by-side panes, and what that costs the census.** Ticket 11 shipped `focus` and `diff` but
  refused `join-pane` on evidence: seven call sites enumerate the `crew` window by name, so a joined
  crewmate reads as dead or missing everywhere. Whether the census should address crew panes by
  marker rather than by window is the real question underneath, and it is not sharp yet. **Ticket 17
  narrows half of it:** pane-id identity turns out to be unsafe already, with no `join-pane`
  involved, so the identity scheme is now its own decision and this item is only the layout half.
- **What else the cockpit sheds once firstmate drives it.** Fewer panes, fewer verbs on the command
  card, possibly a different default layout. The card did not shrink in ticket 11 because nothing on
  it became redundant; that changes as more captain actions become firstmate verbs.
- **Whether `NEXT.md` shrinks once the map holds.** It is the hand-rolled ancestor of this map, it is
  cited by other documents, and it is read by every fresh session. A real decision, not a cleanup.
  Do not touch it before ticket 02 resolves.
- **Whether the map format needs a probe.** The ticket header block and the frontier query are
  exactly the shape this repo turns into a check. Premature until the format has survived use.
- **Whether the pool generalizes after all.** Ticket 14 defers it deliberately. It returns only if
  worktree provisioning time is measured and hurts.

## Out of scope

Ruled beyond this destination. These do not graduate.

- **The paid measurement backlog.** `NEXT.md`'s prompt items 2 through 6. Real, and none of them
  blocks a human from working this way daily. They stay where they live.
- **The opencode half's daily-driver story.** The destination names Claude Code inside the harness.
- **Changing the banned-filename invariant.** An owner decision about a gate-enforced rule with a
  measured rationale, not a step on this route.
- **Retiring `grill-me` or the stale `to-prd` and `to-issues` skills.** The installed set is one
  generation behind upstream, which is worth knowing and is not on the way.
- **Making the fleet autonomous.** A map makes the queue durable and the captain's decisions
  explicit. Only research and AFK task tickets are spawnable, because a HITL ticket resolves only
  through live exchange. Autonomy is a different destination and would be a fresh effort.
  **PARTIALLY OVERRIDDEN by the captain 2026-08-05**, and deliberately not deleted, because the
  reasoning above still governs everything the override does not name. See the Decisions entry on
  the overnight AFK loop: unattended running is now permitted for AFK `task` tickets only, and the
  HITL rule that this paragraph exists to protect is unchanged and is enforced in the loop's own
  objective. A loop that resolves a `grilling` ticket has broken it, exactly as a crewmate would.
- **The PC, and everything downstream of a second machine.**
  [PC: Claude Code login and the conversion checklist](tickets/06-pc-login-and-checklist.md) is
  CLOSED out of scope: the captain is retiring that machine for a RAM fault, so there is nothing to
  log into and no checklist to walk. Windows parity work already in the tree stands on its own and
  is guarded by probes here. If a second machine ever returns it is a fresh effort under a redrawn
  destination, never a resumption. Two live consequences did **not** go out of scope with it: the
  corruption clearance is ticket 15, and ticket 14's "the PC is wanted" rationale is now false and
  carries a note saying so.
