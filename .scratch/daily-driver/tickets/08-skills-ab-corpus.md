# What corpus and scorer would a real skills A/B need

Type: grilling
Mode: HITL
Status: open
Assignee: -
Blocked by: 03

## Question

The captain wants A/B evaluation of the installed skills, to know which ones need to exist. The rig
for this is built and proven; the study design is what is missing.

**A second question now rides on this one.** Captain's direction 2026-08-05: the Claude Code and
opencode harnesses may load skills by different mechanisms, but they must carry the same skill set,
and whether the two are equally capable is to be settled by A/B measurement rather than by
argument. So this ticket is not only "which skills need to exist" but "which skills each system
needs to be equally capable", and it is the arbiter ticket 18 is told not to pre-empt by reasoning.
Whether that is the same study with a second arm dimension, or a separate one, is part of what this
ticket decides.

**What exists, VERIFIED.** `run_study.py` is a generic paid-study driver over frozen synthesized arms,
base plus exactly one skill delta, with the corpus and every config byte frozen at run creation.
`arms-tdd.json` is the live example: `base`, and `plus-tdd` adding the tdd skill. It has run at scale:
`refusal tdd-full-1`, 150 rows, banked, complete.

**The finding that makes this a real question.** That run paired a **tdd** skill delta with the
**refusal** corpus. It returned a powered null, both arms delivering 75 of 75 at exact McNemar p = 1.0,
and the null is correctly measured. It simply answers a question nobody asked: a TDD skill has no
reason to move security-artifact delivery. What is missing is not the rig. It is a corpus whose outcome
the skill is supposed to move, and a scorer for it.

Three things to decide:

1. **Which skills are even A/B-able.** `run_study.py` carries a hidden executable check: a script
   frozen with the corpus, run after the turn in a disposable pooled worktree, with the body written
   outside the workspace so the model cannot read the test it is scored by. That is exactly right for
   `tdd`, `plaincode`, `diagnose`, which produce checkable work products. It is exactly wrong for
   `wayfinder` and `grill-me`, whose product is a plan.
2. **How to score a planning skill anyway.** Two candidates. Free and structural: score the map
   itself, whether ticket questions are sharp, whether blocking edges are acyclic, whether a decision
   got restated in two places, whether fog graduated or only accumulated. Paid and more useful: score
   **downstream crewmate success**, same objective, one crewmate given a firstmate-decomposed brief and
   one given a wayfinder ticket, both work products scored by a hidden executable check. The second
   converts an unmeasurable planning question into the measurable one the rig was built for. It is
   blocked by ticket 03 because it depends on what a crewmate is actually handed.
3. **Whether to build a Claude-side arm factory.** `arms.py` synthesizes **opencode** config roots:
   its base is `harness/config`, its delta channel is a skill file inside that root, and it serves an
   opencode process. The daily driver is Claude Code. `DECIDED` forbids carrying opencode numbers to
   Claude. So an A/B on the current arms measures opencode and may not transfer to the harness the
   captain actually drives. A Claude-side arm factory does not exist and is real work.

Cost prior, so the spend is not underestimated: the one completed 150-row study cost roughly seven
dollars and returned a null. Planning effects are likely smaller and noisier than refusal-delivery
effects, so a study powered to see them is well over 150 rows. `/paid-run-protocol` before any of it.

**Resolved when** the study design is named: which skill, which corpus, which scorer, which harness,
and whether it is worth paying for. Running it is a separate effort.
