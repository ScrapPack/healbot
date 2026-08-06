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
- **The review bar is severity, fail-closed, plus a path escalation** for `harness/`, `gate/` and
  `fork/`. `gate/review.py`'s `blocking` mode already implements the severity half. Ticket 12 owns
  the trigger point and the spend bound; ticket 13 owns the missing handoff to the captain.
- **Firstmate drives the cockpit.** The captain learns how to talk to firstmate and nothing else.
  Ticket 11.
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
  marker rather than by window is the real question underneath, and it is not sharp yet.
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
- **The PC, and everything downstream of a second machine.**
  [PC: Claude Code login and the conversion checklist](tickets/06-pc-login-and-checklist.md) is
  CLOSED out of scope: the captain is retiring that machine for a RAM fault, so there is nothing to
  log into and no checklist to walk. Windows parity work already in the tree stands on its own and
  is guarded by probes here. If a second machine ever returns it is a fresh effort under a redrawn
  destination, never a resumption. Two live consequences did **not** go out of scope with it: the
  corruption clearance is ticket 15, and ticket 14's "the PC is wanted" rationale is now false and
  carries a note saying so.
