# Phase 11 — the maps had rotted, and three of the rot was mine

Date 2026-07-28. Nothing was built in the fork's *code* and nothing was paid for. `NEXT.md` said the
free list was empty and that finding something would itself be the phase. Two surfaces had never
been examined: whether the fork still reproduces from what the repo ships, and whether the `file:line`
citations still point at anything.

The first came back clean and stronger than recorded. The second did not.

| | |
|---|---|
| **Citation rot had no guard, and `fork/README.md` says so** | It names two drift modes. Mode 1 (checkout ahead of overlay) has a documented shell command. Mode 2 — *"upstream moves and the `file:line` citations rot"* — is named as a risk with **no check at all**, which is why every instance so far was found by hand. §1 |
| **Eight stale citations, and THREE were created by Phases 9 and 10** | Editing `HARNESS.md` moved `## Traps` and `## Behavior → file`; editing `probe_twin.py` moved a line `docs/HEADLESS.md` cites. The phases about *"the suite cannot tell passing from not-running"* silently rotted the docs while nothing was looking. §2 |
| **The model-pin citation was ambiguous, and resolved to a blank line** | A bare `opencode.jsonc` line-16 citation — two files carry that name, and the checkout's has a **blank** line 16. It is the citation `probe_turn_growth.py`'s whole `RETIRE_AT` argument rests on. §3 |
| **`probe_twin` guarded 1 of the 17 overlay files** | And the risk fired *this phase*: correcting citations inside two maps needed a manual copy into the checkout. Forgetting either leaves the probe green, the overlay right and the checkout — which every rig actually runs — wrong. §4 |
| **The fork IS fully reproducible, verified harder than recorded** | Base tree 6,330 files, patch applies clean, and applying it to the base **reproduces all 17 overlay files byte-identically**. The README claimed only "applies cleanly". §5 |
| **New guard `probe_citations.py`, free, 14/14** | 930 citations across 24 documents. Free suite **164 → 180**. §1 |

---

## 1. Mode 2 was named as a risk and never checked

`fork/README.md` is unusually careful about how this overlay goes stale, and it lists exactly two
ways. Mode 1 gets a shell command — one that was itself corrected once, after the original used
GNU `diff --include` on a machine shipping BSD diff and exited 2 (*error*) where a caller would read
1 (*differences*). Mode 2 gets a sentence:

> *"**Upstream moves and the `file:line` citations rot.** Every map cites 1.18.5. Re-verify before
> trusting a line number against a newer opencode; the audit found citation drift of one or two
> lines already."*

That is a correct warning with nothing behind it. Every instance found so far was found by hand, one
at a time — the audit found "one or two lines", and Phase 7 found an off-by-one in a `prompt.ts`
citation *asserted as VERIFIED*, by opening the file and discovering the line was blank.

It matters more here than in most repos. `HARNESS.md`'s stated exit test is that from it alone you
can name the file owning any behaviour, and the maps **are** the deliverable. A map whose line
numbers have slid is not a smaller map. It is a wrong one, and it is wrong silently.

`probe_citations.py` is the check: **930 citations across 24 documents, free, 14/14.** It resolves
every `file:line` in the repo's prose and the overlay's maps against the tree and asserts three
things — the file exists, the line exists, the line is not blank.

**An editorial rule falls out of this, and it earned itself immediately.** A citation quoted as
BROKEN must not be written in live `file:line` form — a reader cannot tell a pointer from a
specimen, and neither can the probe. The first draft of this very document tripped its own check
with 1 past-EOF and 8 blank hits, every one of them a stale citation being *discussed*. They are
written as "line 1241 of `healbot.tsx`" instead. `docs/HEADLESS.md`'s erratum about the deleted
`document_strings()` got the same treatment. The alternative — an escape marker the probe skips —
was rejected: it is a hole anyone can use to silence real rot, and it would be used by exactly the
person least inclined to fix the citation.

**What it catches is positional rot. What it cannot catch is semantic rot** — a citation landing on
a real, non-blank line that says something else entirely. Nothing mechanical can check that, and a
probe claiming otherwise would be the exact species this suite keeps finding: green for a reason
unrelated to the claim. That limitation is in its docstring, not buried here.

> **Narrowed 2026-08-02 — docs/CLONE.md §9.2.** One deliberate exception now exists: a citation
> that QUOTES its target in the italic `*"…"*` form is read back against the cited line by the
> probe's verbatim-quote leg, so the quoting case is claimed and checked (it found three rots on
> its first run). Everything short of a quotation stays exactly as the paragraph above says, and
> the docstring carries the same narrowing.

### The probe's first draft manufactured 155 findings

Worth recording before any of the results below, because it is the reason they can be quoted.

The first resolver picked, among files sharing a basename, the one with the shortest path. The
checkout holds **seven** files named `prompt.ts` — 57, 1631, 293, 37, 203, 1 and 131 lines. So
`prompt.ts:1295` — opencode's own turn predicate, the line the entire Phase 7 finding rests on, and
correct — resolved to the 57-line schema file and was reported as past end of file. Along with 154
others.

Phase 8's rule is that **a failing assertion needs the same scrutiny as a passing one**, and this is
the cheapest possible demonstration: the first move on seeing 155 hits was to open one, which took a
minute and dissolved the entire result. A candidate is now accepted only if it actually *contains*
the cited line, and the resolver bug is pinned as its own assertion so it cannot come back.

---

## 2. Eight stale citations, three of them self-inflicted

**Pre-existing (5).** `FEATURE-PLUGINS.MAP.md` cited lines 1241, 1235 and 1223-1245 of `healbot.tsx`
against a file that is **1,100 lines** — off by roughly 140. Verified against the source, the real
sites are `:1090` (`dialog.clear()` in the palette command), `:1082-1084` (`healbot.open` /
`slashName`) and `:1072-1090` (the whole `route.register` block). The file was already 1,100 lines
before Phase 9, so this is old rot that nothing had ever looked for. Also line 22 of `execution.ts`, whose
own parenthetical already read *"(unbound tag, :23)"* while `Service` sits at `:21`; and
line 188 of `docs/SCAN.md`, whose "19 skills" figure has moved to `:243`.

**Created by Phases 9 and 10 (3).** This is the part worth sitting with:

| citation | was | now | broken by |
|---|---|---|---|
| line 316 of `HARNESS.md` (cited twice) | `## Traps` | blank | Phase 9/10 adding index rows and traps |
| line 110 of `HARNESS.md` | `## Behavior → file` | blank | same |
| line 83 of `probe_twin.py` | `plugin = read(PLUGIN)` | blank | Phase 9 adding the `read()` diagnostic |

Established by checking each line against `1438515`, the commit before Phase 9. **Two phases spent
on "the suite cannot tell everything-passed from almost-nothing-ran" rotted three citations in their
own artifacts, and nothing noticed, because nothing was looking at citations.** The suite went from
141 to 164 assertions across those phases and not one of them could see this.

That third one is doubly dead: `document_strings()` was **deleted** in Phase 7, so the citation
now points at a blank line in a file that no longer contains the function. That reference is
historical on purpose, so it is kept — but rewritten out of `file:line` form, because a stale
pointer that *looks* live is worse than prose.

### And a line citation into a LIVING index is structurally wrong

Demonstrated by accident, an hour after the fix. Adding this phase's own index row and traps to
`HARNESS.md` moved `## Traps` again and re-broke the citation that had just been corrected — the
probe went red immediately, which is the whole point, but the second break says something the first
one did not.

`HARNESS.md` gains rows every phase. Any `HARNESS.md:NNN` citation is therefore guaranteed to rot,
and re-pointing it each time is maintenance with no end. The durable fix is to cite the **section by
name** — `HARNESS.md`'s **Traps** table — which survives every edit that does not rename the
section, and which is more useful to a reader besides: a line number tells you where to look, a
section name tells you what you are looking for. Three citations moved to that form.

The general rule: **line-number citations are for code, which changes under review; section-name
citations are for living documents, which change under everyone.**

---

## 3. The one citation another probe's assertion depends on

A bare `opencode.jsonc` citation to line 16 appears in `HARNESS.md`, `NEXT.md` and the rig README as the model pin — the
thing `probe_turn_growth.py` asserts, and the reason `RETIRE_AT` is verified at all. Phase 8 made
that pin load-bearing; Phase 9 and 10 both restated it.

**There are two files named `opencode.jsonc`.** The harness's has the pin on line 16. The checkout's
`.opencode/opencode.jsonc` has **35 lines and a blank line 16**. A reader with the checkout open —
the likelier of the two, since that is where the code is — follows the citation to nothing.

This is not resolver noise; it is a genuinely ambiguous citation that happens to resolve wrong. All
six occurrences now read `harness/config/opencode/opencode.jsonc:16`, and `NEXT.md` says out loud
that there are two files and which one is meant. The probe pins both halves: that a path-prefixed
citation beats a bare basename, and that the pin really is on line 16.

---

## 4. `probe_twin` was guarding one file in seventeen

`probe_twin.py`'s first assertion — *"the fork overlay and the checkout hold the same
healbot.tsx"* — carries the comment *"editing one and testing the other is a way to prove
nothing."* That is exactly right, and it covered **one** of the overlay's 17 files. The other 16 are
14 subsystem maps, `builtins.ts` (the two lines that register the grid at all), and
`.opencode/opencode.jsonc`.

The risk fired during this phase. Correcting citations inside `FEATURE-PLUGINS.MAP.md` and
`SESSION.MAP.md` required copying each into the checkout by hand; forgetting either would have left
`probe_twin` green, the overlay right, and the checkout — which every other rig in this suite
actually runs — wrong.

All 17 are now asserted, with a mutation check that corrupts a copy and requires the comparison to
trip. `fork/README.md`'s drift mode 1 stops being a shell command somebody remembers. **25/25.**

---

## 5. The fork reproduces, and that is now measured rather than asserted

`fork/README.md` records the patch as *"TESTED: applies cleanly to the base, re-checked in a
throwaway worktree."* Applying cleanly is weaker than reproducing. Re-checked, in a throwaway
worktree at `7534d23`:

- the base tree is **6,330** files, the number the README corrected itself to;
- the patch holds **17** `diff --git` headers;
- `git apply --check` and `git apply` both exit 0;
- **and every one of the 17 overlay files is byte-identical to `fork/` afterwards.**

That last line is the one that was never checked. "Applies cleanly" would still be true of a patch
that produced something subtly different from the overlay this repo ships. It does not.

---

## 6. Still open after Phase 11

- **`verify_handoff.py` must be re-run before 21/21 can be quoted.** Unchanged from Phase 10, and
  still the only item that costs money to close. Its floor is 22.
- **Every paid-rig fix from Phase 10 is VERIFIED, with three now TESTED** in a fail-fast
  environment; whether each reaches its floor in a working one still needs the model.
- **Semantic citation rot is unguarded and unguardable mechanically.** `probe_citations.py` proves a
  citation points *somewhere real*, never that it points at *the right thing*. 930 citations now
  resolve; how many describe what they claim to is not a question a probe can answer.
- **The 180,000 gate** (~$2.60) and **an external plugin's route** — both unchanged, both declined.
- **Phase 3's exit gate** — `/code-review ultra`. User-triggered and billed.

Decided in Phase 8 and not re-opened: `RETIRE_AT` stays at 180,000; no startup sweep.

---

## 7. The method note

Phase 9: *a green run is not evidence that the run happened.* Phase 10: *a green run is not evidence
when there was no run at all.* Phase 11 is the same question pointed at the prose:

**The documents are artifacts too, and nothing was checking them.**

Every guard this project has built points at code or at the rigs. The maps — which `HARNESS.md`
calls the deliverable, and whose whole purpose is to let a reader jump straight to the owning file —
had no check at all, and had had none for eleven phases. Eight citations were stale, and the oldest
of them predates every phase that has been reviewing this repo.

The sharper half is the three that are mine. Phases 9 and 10 were *specifically about* silent
failure — about the difference between passing and never running — and they introduced silent doc
rot in their own artifacts while doing it. Not through carelessness in the edit; through editing a
file that other files point *into*, which no tool in the repo modelled. **A citation is a coupling
between two files with no type, no import and no compiler between them** — the same shape as the
metadata request channel `probe_twin` guards from both ends, and the same shape as the recorded
score that outlived its file in Phase 10. This repo now has three guards against that shape, and
each was built only after the coupling had already broken once.

And the note that belongs next to the findings rather than under them: this phase's first result was
155 false positives from its own tool. The finding survived because the rule for a red is the same
as the rule for a green, which Phase 8 wrote down and this phase had immediate cause to use.
