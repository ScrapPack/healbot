# Six documents carry a "Still open" section and nothing ever re-checks them

Type: grilling
Mode: HITL
Status: open
Assignee: -
Blocked by: -

## Question

Six phase documents end with a section listing what that phase left unfinished:

| document | section |
|---|---|
| [docs/RELAY.md](../../../docs/RELAY.md) | Still open after Phase 7 |
| [docs/GROWTH.md](../../../docs/GROWTH.md) | Still open after Phase 8 |
| [docs/VERDICT.md](../../../docs/VERDICT.md) | Still open after Phase 10 |
| [docs/CITE.md](../../../docs/CITE.md) | Still open after Phase 11 |
| [docs/SCAN.md](../../../docs/SCAN.md) | Still open |
| [docs/VERIFY.md](../../../docs/VERIFY.md) | Still not built |

Each is correct as of its own phase and none is re-read afterwards. They are written in the present
tense, so a reader who opens one today is told a thing is outstanding with no marker saying which
phase that was true in.

This is not hypothetical. `docs/HARDEN.md` §2 said:

> *"Step 5 (the control agent) does not exist; step 4 (focus) is three lines of code with no test."*

Both shipped. `harness/config/opencode/agent/control.md` exists and `probe_control_wiring.py` holds
it at 16/16, including a row asserting it is the agent that file defines rather than a coincidence
of naming. `probe_focus.py` declares a floor of 24. The sentence was true when written and had been
false for several phases, in a document an operator is pointed at. It is now corrected.

`docs/CITE.md` §6 shows the same shape twice more: it says *"930 citations now resolve"* where
`probe_citations.py` reports **1,098 across 80 documents**, and it holds open an item whose stated
success condition — *"before 21/21 can be quoted"* — is a score that would fail, because
`verify_handoff.py` declares `Results(expect=22)`.

## The question

Not "go fix six sections". Re-reading them by hand is what produced this ticket and it does not
scale — the same read has to happen again next phase.

What is worth deciding is **whether a phase document should carry a forward-looking claim at all.**
Three positions:

1. **Date-stamp and freeze.** "Still open after Phase 8" becomes "Open as of Phase 8, not re-checked
   since". Cheap, honest, and stops the present tense lying. Does nothing to surface items that
   have since closed.
2. **Move the open items out.** A phase document records what a phase measured; what is still open
   is a ticket. That is what `.scratch/*/tickets/` is for, and the frontier already lists them.
   Costs a one-time migration and makes the phase documents purely historical.
3. **Leave them and accept the drift**, on the grounds that these are archives nobody operates from.
   `docs/HARDEN.md` is the counter-evidence: it is linked from `docs/VERIFY.md` as current reading.

(2) is the one that matches what the repo already does everywhere else, and it would have caught
all three findings above at the point somebody closed the work rather than years later. It is also
the most disruptive, which is why this is HITL rather than AFK.

## Related

The mechanical half of this problem — quoted probe scores that no longer match their floor — is
[rig-defects 04](../../rig-defects/tickets/04-prose-quotes-a-floor-nothing-checks.md). That one is
checkable by a probe. This one is not: no script can tell whether a sentence about outstanding work
is still true.
