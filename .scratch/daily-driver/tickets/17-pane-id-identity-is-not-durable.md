# A crewmate's identity is a pane id, and pane ids come back

Type: grilling
Mode: HITL
Status: open
Assignee: -
Blocked by: -

## Question

Every fleet verb that takes a crewmate name resolves it to a tmux pane id through the manifest and
then acts on that id, with nothing checking that the pane is still the crewmate the row describes.
`resolve_pane` is fail-closed against an UNKNOWN name ([harness/hb-fleet.sh:276](../../../harness/hb-fleet.sh))
and says so in its own comment, but it has no defence against a name that is known and stale.

The manifest outlives the tmux server. Pane ids are unique per server and the counter restarts when
the server does, so a fresh fleet re-issues ids the manifest already holds. This repo's own manifest
records three restarts and the collision:

| crewmate | pane | spawned |
| --- | --- | --- |
| task0, trustprobe, hookprobe | %11, %12, %13 | 2026-08-03 10:06 to 10:11 |
| alpha, beta | %4, %5 | 2026-08-03 10:50 |
| alpha, beta | %2, %3 | 2026-08-05 00:48 |
| calib | **%2** | 2026-08-05 20:55 |

Observed live, not reasoned about: with `calib` running, `hb-fleet.sh state` reports **both `alpha`
and `calib` as `alive | screen: busy` on pane `%2`**. `alpha` has been gone for 20 hours. It reads
alive because [harness/hb-fleet.sh:722](../../../harness/hb-fleet.sh) matches the manifest's pane id
against the current crew window and takes whatever it finds, and the screen reader takes the same
id, so the dead row also inherits the live crewmate's screen.

The `sid` is right there in the row and is read two lines earlier, but it is used only to find the
hook-state file. Nothing ever asks whether the pane belongs to that sid.

### Why this is more than a wrong census line

The escalation rule in `harness/skills/firstmate.md` covers one direction: a false `dead` reading
launches a duplicate agent on the same tree. This is the mirror, and every name-taking verb inherits
it. Three consequences, in order of damage:

1. **`kill` kills the wrong crewmate.** It resolves the name to a pane
   ([harness/hb-fleet.sh:1023](../../../harness/hb-fleet.sh)) and calls `kill-pane` on it
   ([harness/hb-fleet.sh:1033](../../../harness/hb-fleet.sh)). With the manifest as it stands,
   `hb-fleet.sh kill alpha` kills `calib`. It then tries to release the pool slot named in
   *alpha's* row, which is the slot `calib` holds. The pool's refusal-while-work-is-held rule is
   the only thing standing between that and a discarded worktree, and it is a backstop, not a
   design. NOT executed: running it would have killed the live crewmate. VERIFIED by reading the
   call chain and by confirming that `%2` is `calib`.
2. **`send` and `brief` type into the wrong session.** Same resolution, at
   [harness/hb-fleet.sh:765](../../../harness/hb-fleet.sh) and
   [harness/hb-fleet.sh:821](../../../harness/hb-fleet.sh). An instruction meant for a retired
   crewmate lands in a live one working a different objective, and both sides look successful.
3. **`focus` shows the captain the wrong crewmate under the right name.** Ticket 11 shipped it as
   the verb that means the captain never has to know tmux. It refuses an unknown name and cannot
   detect a recycled one, so it puts `calib` in front of the captain labelled `alpha`.

That is a claim-of-done problem wearing different clothes: a crewmate that is gone reads as working,
and the cockpit's whole promise is that the captain trusts what the first mate reports.

## What has to be decided

The repair is an identity scheme and there is more than one workable one, which is why this is a
grilling rather than a task:

- **Stamp the pane and check the stamp.** Have `resolve_pane` verify a stamp on the pane before
  returning it, so identity lives with the pane rather than in a file that outlives it. **Use a tmux
  user option, not the pane title.** Spawn already stamps the title with the crewmate's name
  ([harness/hb-fleet.sh:643](../../../harness/hb-fleet.sh)), and that stamp does not survive: with
  `calib` live and spawned as `calib`, the pane title reads `_ calib`, because the process inside
  the pane rewrites its own terminal title and tmux takes it. MEASURED 2026-08-05. A field the
  crewmate can write is not an identity check, and a substring match against it would be a check
  that looks like one. A `set -p @hb_sid` user option is outside the pane process's reach.
- **Scope the manifest to the server that made it.** Record the tmux server's identity at `up` and
  treat rows from an older server as `missing` by construction, which is what they are.
- **Verify by sid against the pane's process**, using the transcript path or the process the pane
  is running.
- **Refuse rather than guess.** Whatever the scheme, the question underneath is whether an
  unverifiable identity should refuse loudly, matching `resolve_pane`'s existing posture toward
  unknown names, rather than act on a best guess.

There is an interim mitigation that needs no decision at all and should be named in the resolution
whichever way it goes: the collision only exists because retired crewmates keep live-looking rows.

## Relationship to the map

`MAP.md`'s "Side-by-side panes, and what that costs the census" item asks whether the census should
address crew panes by marker rather than by window, and frames it as a cost of `join-pane`. This
ticket is the evidence that the framing is too narrow: pane-id identity is already unsafe with no
`join-pane` anywhere near it. Resolve this one first, or resolve them together.

**Resolved when** the identity scheme is named, the behaviour on an unverifiable identity is named,
and it is clear whether the fix covers all four verbs or only the destructive one. TESTED means a
manifest holding a recycled pane id is shown to produce `missing` for the stale row and the correct
crewmate for the live one, in both directions, against a real fleet.
