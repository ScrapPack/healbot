# Ticket 16 — were the review's error findings ever right

Classification of every `error`-severity and untagged finding in healbot's model-review records,
against what the tree did next. Records only; no API credits were spent. Reading and git history
only.

Produced 2026-08-05 by the crewmate `calib` in pooled slot-1, brought into the main tree by the
first mate, who is the only tracker writer. Two edits were made on the way in and nothing else was
touched: eleven citations that this report QUOTES rather than points at (a stub's `x.py`, the
archived run's `ARCHIVED.md`, and `harness/hb-fleet.sh` line 948, which was valid at the reviewed
head and is blank on `main`) were rewritten out of live `file:line` form, because
`probe_citations.py` cannot tell a specimen from a pointer and went red on all eleven. That is
`/citation-hygiene`'s first rule and the same trap `docs/CITE.md`'s first draft hit nine times.

Verified before acceptance, per the first mate's third hard rule that a claim of done is a claim:
the corpus count, the counts table, and the full 27-row table were read; one classification was
independently re-derived against the tree and an attempt to overturn it failed (see the
`gate/hooks/pre-push` row, where the repair commit's own subject confirms the finding's core claim
was real while a later code comment records its escalation as wrong).

## 1. The corpus

| | |
|---|---|
| Glob | `gate/runs/*-review.json`, read from the main checkout (the records are gitignored, so a slot's own copy is empty) |
| Records | **120** |
| Snapshotted | 2026-08-06T00:55:41Z |
| Record states | pass 89, blocked 22, error 6, skipped 3 |
| Records carrying a findings list | 111 |
| ... of which genuine model reviews | **109** |
| ... of which driven by the stub binary | 2 |
| Findings extracted | **27**, across **22** records |

The extraction rule was the brief's: `severity == "error"`, plus any finding with no `severity`
key or a value outside `("error", "warning", "info")`.

**There were no untagged findings.** All 27 carry `severity: "error"` exactly. The severity
histogram over all 111 findings-bearing records is error 27, warning 99, info 72. So the
fail-closed half of `blocking` mode (gate/review.py:24-26, "an untagged finding" blocks) has never
once fired in this corpus; every block was an explicit `error`.

The tree state referenced throughout is `main` = `c0e19cd` (2026-08-05T16:43:40-04:00), which is
`origin/main`. This worktree is detached at `99add3e` (2026-08-01), four days behind, so every
"still present today" claim below was re-derived with `git show main:<path>` rather than by reading
the checkout.

## 2. The counts

| Class | Count |
|---|---|
| **real** | **18** |
| **wrong** | **0** |
| **unacted** | **7** |
| unclassifiable | 0 |
| excluded (not model output) | 2 |

**False-positive rate = wrong / (real + wrong) = 0 / 18 = 0%.**

Read that number narrowly. It covers only the 18 findings the tree acted on. It says nothing about
the **7 unacted** findings, which are excluded from both numerator and denominator. Per the brief,
an unacted finding is not evidence in either direction and is not scored as wrong.

Two further qualifications, both of which cut against reading 0% as a clean bill of health:

- **The denominator is partly self-selecting.** "Real" was established for 15 of the 18 by a repair
  commit that names the finding. A finding the captain judged wrong would tend to leave no repair
  commit and land in "unacted", not in "wrong". The corpus can only weakly distinguish "wrong" from
  "ignored". What it does show is that *no repair commit in the corpus refutes an error-severity
  finding* — the refutations that exist (`2e345a1`: "one refuted by test") all landed on `warning`
  findings, never on an `error` one.
- **I verified 6 of the 7 unacted findings as factually correct anyway** by reading the cited code
  (details in the table and §5). They are unrepaired, not mistaken. So the evidence available does
  not point toward a hidden population of false positives among them.

Excluded: 2 findings (`x.py` line 3, "stub error finding") produced by a stubbed `claude` binary under
`HEALBOT_REVIEW_CLAUDE` during plumbing tests. Both records show `secs` 0.0-0.1,
`result_meta.total_cost_usd: null`, `num_turns: 1`, and cite a path that has never existed in the
repo. They are not model output and cannot be scored as right or wrong. They do, however, count as
blocks: both records carry `state: "blocked"`, and one ran in `mode: "blocking"`.

## 3. The table

All 27, in record order. Summaries are truncated; `severity` is as recorded.

| Record | Cited `file:line` | Sev | Summary (truncated) | Class | Evidence |
|---|---|---|---|---|---|
| `20260731-181116-9691` | `x.py` line 3 | error | stub error | **stub** | plumbing stub, not model output |
| `20260731-181116-9696` | `x.py` line 3 | error | stub error | **stub** | plumbing stub, not model output |
| `20260731-182953-11413` | `gate/review.py:142` | error | The closer-appending repair does not only fix a clean tail cut: if the reply is cut mid-finding, rfind("}") lands on an earlier finding's closing... | **real** | 875e5a2 |
| `20260731-193036-21009` | `NEXT.md:8` | error | The change adds a fifth skill (harness/skills/phase-close.md) that tier2.py names as its only trigger, but NEXT.md — the fresh-session onboarding... | **real** | a7a425f |
| `20260731-195448-23474` | `harness/pool.py:246` | error | `release` guards only on `git status --porcelain`, so work the operator COMMITTED in the detached slot passes the clean check and is then silently... | **real** | f6dcaeb |
| `20260731-200635-25122` | `.carryover/verified/probe_pool.py:103` | error | The row "acquire SKIPS the soiled slot" cannot fail from the guard it names: at that point slot-1 is free and clean and sorts first, so acquire... | **unacted** | still at probe_pool.py:111 on main |
| `20260731-200635-25122` | `.carryover/verified/probe_pool.py:127` | error | The row "acquire refuses to lease the committed-work slot to anyone else" is proven by the lease guard, not the committed-work guard: the prior... | **unacted** | still at probe_pool.py:135 on main |
| `20260731-201829-26649` | `.carryover/verified/arms.py:226` | error | The XDG_DATA_HOME assert cannot fail: `env` is a plain `dict(os.environ)` copy and neither branch of the function ever sets or pops XDG_DATA_HOME, so... | **unacted** | still at arms.py:255 on main |
| `20260731-212534-33952` | `.carryover/verified/probe_study_driver.py:232` | error | The split strands a row that cannot fail: `compatible_meta(recomputed, expected) == []` compares two calls to `expected_meta` with byte-identical... | **real** | 900f13f |
| `20260731-213818-36791` | `.carryover/verified/hb/errorstate.db:None` | error | The commit message claims the delta is "the checkpoint's header touch" with "0 pending frames" and that "the committed bytes were already complete",... | **unacted** | commit message never corrected |
| `20260731-221315-38634` | `.carryover/verified/hb/ab-runs/refusal-full-archived-20260731/ARCHIVED.md` line 4 | error | The rename removes the only spend tripwire rather than adding one: `ab.run_dir` builds the exact path `{RUNS}/refusal-{tag}` and... | **unacted** | run_refusal.py untouched since |
| `20260731-221315-38634` | `.carryover/verified/hb/ab-runs/refusal-full-archived-20260731/meta.json:54` | error | The archived run's `"status": "running"` is left in place permanently, so closed evidence keeps advertising a live run: nothing will ever flip it... | **real** | ba13e0a |
| `20260731-221315-38634` | `.carryover/verified/hb/ab-runs/refusal-full-archived-20260731/meta.json:71` | error | All six `launches[].logs` entries are absolute paths into the old directory `.../ab-runs/refusal-full/server-*.log` (meta.json:71-72, 470-471,... | **unacted** | 6/6 log paths still dangle on main |
| `20260731-221315-38634` | `.carryover/verified/hb/ab-runs/refusal-full-archived-20260731/ARCHIVED.md` line 15 | error | The recorded operation installed `frozen/set_a-41fecb7f-regexfix.json` as the live `studies/refusal/set_a.json` for the duration of the rescore while... | **unacted** | no commit addresses it |
| `20260802-111518-51255` | `.claude/handoffs/handoff-20260801-003744.md:12` | error | Newly-tracked handoff writes `NEXT.md:95` in live file:line form into NEXT.md, and this same change inserts ~15 lines above it, so the cited... | **real** | 2bc89e5 |
| `20260802-155020-94532` | `docs/CLONE.md:487` | error | "seventeen `HARNESS.md:NNN` citations from `docs/AFK.md` and `docs/REVIEW.md`" is a wrong count — MEASURED there are 12 (AFK.md 4: lines 327, 336,... | **real** | 7b9ce27 |
| `20260802-155245-95087` | `docs/CLONE.md:488` | error | The bolded MEASURED claim is wrong on a fresh run: `git grep -o -E 'HARNESS\.md:[0-9]+'` over the tracked tree returns 22 occurrences across seven... | **real** | 90cb709 |
| `20260802-173533-8377` | `harness/hb-fleet.sh:348` | error | The unguarded `t bind ... display-popup` runs on every `up`, but tmux parses a bind-key command string at bind time, so on tmux < 3.2 (e.g.... | **real** | 8ee08a8 |
| `20260802-174748-9919` | `harness/hb-fleet.sh:636` | error | The new preflight comment cites "this script already did, at line 89", but line 89 is `HB_FLEET_DIR=...`; the `. env.claude.sh` source it means is... | **real** | 2e345a1 |
| `20260802-183327-13758` | `docs/SHIP.md:249` | error | The citation `probe_fleet_claude.py:285` (the installed-skill twin) is stale: this change inserted 111 lines above it, so that r.check now lives at... | **real*** | a38b694 (incidental) |
| `20260802-183327-13758` | `harness/hb-fleet.sh:361` | error | The `C-b ?` popup is sized smaller than the card it renders: `hb_help` emits 32 logical lines (22 header + 10 key map) and 12 of the header lines are... | **real** | 4d0f608 |
| `20260803-013538-37728` | `.carryover/verified/probe_citations.py:403` | error | The quote-leg floor counts candidates found (`len(qrows) >= 5`), not quotes actually verified — QUOTE_UNRESOLVED rows satisfy the floor and are... | **real** | b6e97b4 |
| `20260803-014712-38901` | `gate/hooks/pre-push:61` | error | Both new here-docs use an unquoted `EOF` delimiter, so the buffered `$refs` body is re-expanded by the shell: a ref name containing `$` (valid per... | **real** | a2d0801 |
| `20260803-101544-58098` | `NEXT.md:82` | error | This change marks task 0 CLOSED in docs/SHIP.md §5 and pins both markers as MEASURED in hb-fleet.sh, but NEXT.md's task 0 still tells the next... | **real** | c2c2067 |
| `20260803-120357-80318` | `docs/E2E.md:359` | error | The change raises the probe floor to 68 (probe_fleet_claude.py:84) but this change's own suite record still reads "probe_fleet_claude.py runs 65 rows... | **real** | a9ca1c2 |
| `20260804-185654-57291` | `harness/hb-fleet.sh` line 948 | error | `down` puts the entire lease-release loop AFTER `t kill-session`, but the documented captain's seat is the bridge shell INSIDE $HB_RUN... | **real** | 8d20353 |
| `20260805-163831-30533` | `fork/packages/core/src/session/SESSION.MAP.md:391` | error | The path-sharpening sends this SCAN-claim row to the wrong api.ts: the claim it annotates is docs/SCAN.md:90's... | **real** | c0e19cd |
`*` = repaired, but not attributably. See §5.

## 4. Examples

### real — the clearest two

**`20260804-185654` — `harness/hb-fleet.sh` line 948.** The reviewer said `down` puts the lease-release
loop after `t kill-session`, and that since the captain's seat is the bridge shell *inside* the
session, kill-session SIGHUPs the process group running `down` itself, so the release never runs.
It labelled its own conclusion INFERRED, and said why:

> (INFERRED: tmux reproduction was denied approval, not executed)

It also predicted its own guard would miss it: "all five new probe legs are static string checks
that cannot see it". Commit `8d20353` repaired it and confirmed every part, including the reason
the tests had been green:

> MEASURED: `down` sent to the bridge pane of a throwaway fleet left the session gone and slot-1
> still leased. The strand this item exists to close, rebuilt inside its own fix, and green on
> every test I had run, because every one of them drove `down` from a shell outside the session.

An INFERRED finding, raised without the ability to run the reproduction, promoted to MEASURED-true
by the repair.

**`20260805-163831` — `fork/packages/core/src/session/SESSION.MAP.md:391`.** The reviewer said a
path-sharpening had aimed a SCAN-claim row at the wrong `api.ts`, and cited the disambiguating
evidence: the row's own cross-reference names `httpapi/api.ts`, whose `:79` is
`export const OpenCodeHttpApi = HttpApi.make("opencode")`, matching the row's verbatim "block
starts at :79", whereas `protocol/src/api.ts:79` is a generic parameter inside `makeDefaultApi`.
It noted the probe would stay green either way, the target being non-blank. Commit `c0e19cd`:

> I sharpened SESSION.MAP's row to protocol/src/api.ts off a plausible read of makeDefaultApi,
> when the row's own cross-reference (docs/SCAN.md, the lifecycle-agent bullet) names
> httpapi/api.ts [...] An INFERRED pick shipped as settled; the reviewer read the evidence I did
> not.

### wrong — none

No finding in this corpus is classifiable as wrong. I found no error-severity finding that is
mistaken about the code, and no repair commit that refutes one. The two closest calls, neither of
which meets the bar:

- **`20260802-183327` — `harness/hb-fleet.sh:361`** cites the wrong line. At the reviewed head
  `2e345a1`, line 361 is `pane="$(t split-window ...)"`; the popup bind the finding is about is at
  line 348. The *substance* is exact, though, and I measured it: `hb_help` is
  `hb_header` (`sed -n '4,25p'`, 22 lines) plus a 10-line heredoc = **32 logical lines**, of which
  **12 header lines are >=83 columns**, rendering **45 rows** into the `-w 84 -h 28` popup's 26-row
  content area. The finding claimed 32 lines, 12 wide header lines, and "~44 rows". Commit
  `4d0f608` repaired it and independently stated "rendered 45 rows into a 26-row box". A wrong
  line number attached to a correct and precisely-quantified defect is not a false positive.
- **`20260802-155020` — `docs/CLONE.md:487`** says the document's "seventeen" is wrong and offers
  12 for the two named files. The repair `7b9ce27` found the repo-wide truth to be 18 across six
  files — a different number from the finding's — but confirms the finding's own sub-counts exactly
  (REVIEW.md 8, AFK.md 4) and confirms the headline claim that "seventeen" was wrong. Right about
  the defect, narrower in scope than the full correction.

### unacted — the clearest two

**`20260731-200635` — `.carryover/verified/probe_pool.py:103` and `:127`.** Two error findings that
a probe's rows could not fail for the reasons they named. I confirmed both against the code at the
reviewed head `569e5e08`, and both still stand on `main`:

- `:103` ("acquire SKIPS the soiled slot") asserts `acquire("C",...) == 0 and leases() ==
  ["slot-1.json"]`. At that point slot-1 is unleased (released at :88, double-release refused at
  :91) and clean, and sorts first, so `acquire` returns on slot-1 at `pool.py:243-251` without ever
  reaching slot-2. Deleting the `if dirty or committed: continue` guard leaves the row green.
- `:127` ("acquire refuses to lease the committed-work slot to anyone else") is proven by the lease
  guard, not the committed-work guard: the preceding `release` refused (:125-126), so slot-1 is
  still leased to A, and `pool.py:247-248` `continue`s on `os.path.exists(lease_path(slot))` before
  `work_state` is consulted at :249.

The same review's `warning` (tier2.py docstring count) and `info` (empty-string sha) findings were
both fixed within four minutes, by `569cafb9`, whose message enumerates "The 569e5e0 review's two
findings" — the two lower-severity ones. On `main` the two error rows sit unchanged at
`probe_pool.py:111` and `:135`, and `acquire`'s guard order at `pool.py:247-251` is unchanged.

**`20260731-213818` — `.carryover/verified/hb/errorstate.db`.** The reviewer disputed the commit
message of the very commit it was reviewing. `544025c` claimed the delta was "the checkpoint's
header touch" with "0 pending frames" and that "the committed bytes were already complete". The
finding said the real delta is 3 bytes at offsets 94203-94205 inside page 23, advancing a 6-byte
integer by ~1,800,000 ms, i.e. real row content. I checked every number by differing the blobs:

```
sizes: 4730880 4730880
differing byte count: 3
offsets: [94203, 94204, 94205]
range 94203-94205; page_size hdr=4096   page index: 22 (1-based page 23)
header identical (first 100 bytes): True
a bytes: d66acc -> b bytes: f1e243
```

0xF1E243 - 0xD66ACC = 1,799,543 ms = 29.99 minutes. Every particular of the finding checks out,
including the byte offsets, the page number, the byte-identical 100-byte SQLite header, and the
~30-minute advance. Nothing in the history corrects the record.

## 5. Surprises

1. **No untagged findings exist.** `blocking`'s fail-closed clause for untagged findings has never
   fired. Every one of the 27 blocks was an explicit `error`. The fail-closed design is untested by
   this corpus rather than validated by it.

2. **Two of the "27 error findings" are fabricated stubs.** The ticket's figure of 27 (carried from
   ticket 12's close) includes two `x.py` line 3 "stub error finding" records emitted by a stubbed CLI
   during plumbing tests. The real model-finding count is **25**. One of the two stub records ran
   in `mode: "blocking"` and is recorded `state: "blocked"` — a synthetic block sitting in the
   corpus that any naive count of "pushes blocking mode would have refused" will absorb.

3. **The review found real defects in its own reviewer.** The single working-tree-mode record
   (`20260731-182953`, `base: null`) found that `gate/review.py`'s own truncation repair would
   silently complete a reply cut mid-finding into a valid but shortened findings list — turning a
   push-refusing ERROR into a silent PASS. `875e5a2` confirms it in the reviewer's own words:
   "review 2 refuted that repair's first version". Three consecutive commits (`875e5a2`, `cbf7bec`,
   and the round-3 fix) exist because the review stage reviewed itself.

4. **The error findings were not the ones most likely to be fixed.** In `20260731-200635` the
   `warning` and `info` findings were repaired within four minutes and both `error` findings were
   left, and both are still open on `main` today. Severity as the reviewer assigns it did not
   predict what the captain acted on.

5. **One "real" is not attributable to the review** and is marked `real*` in the table.
   `20260802-183327`'s finding on `docs/SHIP.md:249` (the `probe_fleet_claude.py:285` citation is
   stale; the row it names had moved to `:396`) is verifiably correct — I read both lines at
   `2e345a1`, and `:285` there is a comment about `.claude.json`, unrelated non-blank text. The
   citation is gone from `main`. But it was removed by `a38b694`, which rewrote that whole bullet
   to generalize the twin check to the skills population, and whose identical twin `2f67926`
   (17:20) was committed **before the review ran** (18:33). The defect was repaired incidentally by
   work already in flight. Counting it as `real` is the charitable reading; excluding it gives
   17 real and a rate of 0/17, still 0%.

6. **Six of the seven unacted findings are demonstrably correct**, verified by reading the cited
   code: the two `probe_pool.py` rows, the `arms.py` tautological assert, the `errorstate.db` byte
   delta, and both surviving `refusal-full-archived` findings. Only the seventh (`ARCHIVED.md` line 15,
   whether installing a frozen corpus during a `status: running` run violated the repo's
   corpus-edit rule) turns on a judgment about a repo rule rather than a fact about code, and I did
   not adjudicate it. This is the reason the 0% rate should not be read as "the unacted ones were
   probably noise" — where I could check, they were not.

7. **Three unrepaired defects are still live on `main`.** Reported, not fixed, per the brief:
   - `.carryover/verified/arms.py:255` — the `XDG_DATA_HOME` assert still cannot fail. `env` is a
     `dict(os.environ)` copy and nothing between :218 and :255 sets or pops `XDG_DATA_HOME`, so
     both disjuncts derive from `os.environ`. `git log -S'XDG_DATA_HOME' -- arms.py` returns only
     the commit that introduced it.
   - `.carryover/verified/hb/ab-runs/refusal-full-archived-20260731/meta.json` — all **6 of 6**
     `launches[].logs` entries still point into `.../ab-runs/refusal-full/`, a directory that no
     longer exists (the captain's tree holds only `refusal-full-archived-20260731`).
   - The spend tripwire named by `ARCHIVED.md` line 4 was never restored. I confirmed the mechanism:
     `ab.run_dir` is `f"{RUNS}/{study}-{tag}"` + `makedirs(exist_ok=True)` (`ab.py:398-401`), the
     tag defaults to `"full"` (`run_refusal.py:334`), and `run_refusal.py:363-369` runs
     `compatible_meta` only `if meta:` — with the directory renamed away, a bare `run_refusal.py`
     creates an empty `refusal-full`, finds no meta, skips the compatibility check entirely and
     starts from row zero. `run_refusal.py` has not been touched since 2026-07-31T22:13.

8. **No cited file or line pointed at a path that never existed**, except the two stubs' `x.py` line 3.
   Every other cited file resolved at its record's head. Line numbers had drifted in several cases,
   which is expected for records this old and is why every citation above was re-derived at an
   explicit ref rather than read from a checkout.

## 6. Method notes

- Heads: 6 records record a `head` sha. The other 16 predate that field and record only `base`. I
  recovered their heads by matching each record's `files` list against
  `git diff --name-only <base>...<candidate>` over every commit committed at or before the record's
  timestamp, taking the latest match. All 21 resolved uniquely; the 22nd
  (`20260731-182953`) ran in working-tree mode with `base: null` and has no head by construction —
  it was placed by its timestamp and by `875e5a2`'s message, which names it.
- Repair attribution: the repo's convention is a commit subject reading
  `review finding(s) from the <head> push`, where `<head>` is the head of the *reviewed* push. I
  confirmed the convention on two independent pairs before relying on it
  (`b6e97b4`'s parent is `05ba18f` and its subject names `05ba18f`; `a2d0801` names `b6e97b4`).
  10 of the 22 records map to such a commit. The July 31 records predate the convention and were
  traced by reading the next commits touching the cited file.
- One correction made mid-investigation: a push is not always one commit (`05ba18f`'s parent is
  `0c366bf`, not the review's `base` `ecf6397`), so head resolution matched on the full file set of
  the `base...head` range rather than on parentage.
