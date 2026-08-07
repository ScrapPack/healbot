# RECORDS.md — the decision-record store (Phase 15, 2026-08-06)

What was built, what it refuses to do, and the three things an operator has to know about it.

## 1. Why it exists

Retirement carries six fields and drops every reason behind them. `healbot.ts:500-505` filters a
session's history to text parts, which discards tool calls, tool results and reasoning; `:490`
deletes completed todos; `:516` and `:520-524` keep one message each. The handoff is never
written to disk — its only destination is `POST /session/{id}/prompt_async` at `:581`.

Worse than the lossiness is the hole at `:550-558`: a session whose `open.length === 0` is
archived with **no successor and no record at all**. The sessions that finished their work
cleanly are exactly the ones the store never hears from.

So the reasoning behind a decision survives only as long as the session that made it. A later
session re-opens a settled question, reaches a different answer for no better reason, and nothing
in the repository can tell it that the ground was already covered.

## 2. What a record is

A decision anchored to a commit. Not a note, not a summary, not a progress log.

| Field | What it holds |
|---|---|
| `id` | `YYYYMMDD-<kind>-<8 hex>`. Deterministic from its own content, so a re-capture overwrites rather than duplicating |
| `scope` | `project` or `global`. The global tier holds harness mechanics and nothing else |
| `question` | The question that was open, as a question |
| `choice` | What was decided |
| `alternatives[]` | Each rejected option **with the reason it was rejected**. The reason is the point |
| `rationale` | The reasoning. Lives in the prose body, not the frontmatter |
| `evidence[]` | `file:line` pointers |
| `classification` | **Mandatory.** `VERIFIED` \| `TESTED` \| `INFERRED` \| `SUSPECTED` |
| `anchor` | `{commit_sha, changed_files[]}`. Stamped by the post-commit hook, not by the capturing session |
| `supersedes` | The id this replaces, or null. `superseded_by` is **derived at query time and never stored** |
| `captured_at` / `captured_by` | When, and by which session or tool |

The classification is what makes the store safe to read. An `INFERRED` record can never reach the
orientation block, and that single rule is what lets a lossy free backfill in at all.

`alternatives[]` is the half nothing else in this system captures. A commit message states the
choice and usually the reasoning; it almost never states what was rejected, because by the time it
is written the rejected options are gone from the author's head.

## 3. Where it lives, and why that is outside the repository

`~/.healbot/records/<project-key>/` — **not in the project**. Settled by the owner on 2026-08-06.

To be gitignored in a project you do not own, something must write a `.gitignore` into that
project. That is the exact self-ignoring-config behaviour the README already names as a trap on
healbot's own deliverable (`config/config.ts:297-303` seeds one at boot). Not seeding is worse: a
record carries verbatim session text, so a routine `git add -A` in a client repo would commit the
operator's prompts.

Out-of-repo also keeps the project key out of every tracked tree, so `gate.py`'s full-tree
home-path scan stays clean.

**The project key is the MAIN worktree root**, resolved from `git worktree list --porcelain` line
1 — never `--show-toplevel`, which answers with the tree you are standing in. TESTED: the main
checkout, a `.claude/worktrees/*` tree and a `healbot-pool/slots/*` slot all resolve to one store.
A crewmate and the operator are working on one project and see one set of records.

**Not XDG.** The plan left this to the builder to check and checking it inverted the
recommendation. `XDG_CONFIG_HOME` is rewritten twice on purpose — `harness/env.sh:51-52` points it
at the harness config root and `arms.py:256` points it at a materialized A/B arm — so a store keyed
on it would be a different store per harness root and per arm, and the store must span those.
`XDG_DATA_HOME` is deliberately never set by anything here (`arms.py:252-265` is a refusal whose
whole job is keeping `_serve_env` from introducing it, because `auth.json` lives there), so keying
on it means two shells can disagree about where the store is with no error at either. The root is
fixed. `HEALBOT_RECORDS` overrides it, and exists so a probe can point at a fixture.

**A directory with no repository is a refusal, not a fallback.** A cwd-derived key would change
when you `cd` into a subdirectory, which is the same silent split; and a record's anchor *is* a
commit sha, so a directory with no commits cannot produce a well-formed record anyway.

### The two costs, stated plainly

**Records do not travel with a clone.** Cloning healbot on a new machine gets you the code and
none of the reasoning. Backfill re-derives an `INFERRED` floor from git history; everything above
that floor is gone.

**Records are lost with the home directory.** Backing them up is an operational requirement, not a
nicety. `~/.healbot/records/` is plain markdown; any file backup covers it. `~/.healbot/derived/`
is disposable and needs no backup.

## 4. The three capture triggers

**(i) `gate/hooks/post-commit`.** Zero model calls. A record is captured *during* the work, when
the reasoning is still in the session — which is before the commit it belongs to exists. So it
goes in unanchored and this hook stamps the sha. Capture when the reason is known, anchor when the
sha is known, never ask the agent to predict a sha.

The hook also reports records whose evidence names a file the commit changed. That is
**revalidation by anchor** — the same question `gate/staleness.py` asks of documents, asked of
records. Death is supersession, never TTL: time does not invalidate a decision, a change to the
code it was about does.

The flag is derived and never written into the record. "Worth re-reading" is a fact the hook can
establish; "the claim died" is a judgment only a human can make.

**It does not run in a linked worktree until it reaches `main`.** MEASURED 2026-08-06: every
app-created worktree carries a `config.worktree` pinning `core.hooksPath` to the **absolute** path
of the main checkout's `gate/hooks`, while the main checkout's own config holds the relative
`gate/hooks`. A worktree therefore runs whatever hooks `main` is currently on, and a hook added on
a branch silently does not fire there — `git commit` succeeds, prints nothing and anchors nothing.
Run by hand in the same tree it works. Until this branch merges, anchor with
`python3 harness/memory.py stamp`, and check `git config --show-origin core.hooksPath` before
concluding the hook is broken. The same is true of the pre-push staleness stage.

**(ii) `healbot_decide`.** The only cheap source of `alternatives[]` there will ever be. Every
argument is required, because the raw-JSON-Schema path marks every property required
(`tool/registry.ts:365`) and an "optional" field would be a lie the schema does not tell.

It spawns `harness/memory.py` rather than building the record in TypeScript. Building it in the
plugin would put a second copy of the project-key rule, the id rule, the frontmatter format and
the whole validator into a file that cannot import the first copy. `Bun.spawn` and
`import.meta.dir` are runtime globals, so the plugin's no-imports rule is untouched.

**(iii) The turn-staleness nudge**, at `HEALBOT_CAPTURE_AT` (default `0.5`) of the retirement gate.
A fraction rather than an absolute, because an absolute set beside a gate that moves with
`HEALBOT_RETIRE_AT` would silently end up above it. It sits **above** the `AUTO_RETIRE` kill
switch: `HEALBOT_AUTO_RETIRE=0` disables the retirement gate and nothing else, and below that line
it would silently disable capture too. Delivery is one line appended through
`experimental.chat.system.transform`, so it costs zero extra turns.

**The 0.5 is a guess and is stated as one.** Nothing has measured where useful decisions actually
accumulate in a session.

## 5. Retrieval: one pull tool and one capped block

Retrieval is **pull**. Tool definitions are the largest standing token cost in this harness — 11
shipped tools measure 19,898 B — so a store that pushed its contents into every prompt would spend
the budget the harness exists to protect on records nobody asked for.

`healbot_recall` has **no path argument, permanently**. The project comes from the plugin's own
directory, so no model and no instruction reaching one through a file, a web page or another
session's output can name a different project's store. A `project` argument would put cross-project
reads one prompt injection away.

The one exception to pull is the **orientation block**, capped at 2,000 bytes — `MAX_DOCUMENT_TAIL`
(`healbot.ts:151`) reused rather than a second number invented. Four selection rules:

1. **Heads only.** Anchoring a fresh session to a decision already reversed is the one failure mode
   that makes the block worse than no block.
2. **`VERIFIED` or `TESTED` only.** This is what makes the free backfill safe.
3. **Deterministic sort**, so two sessions started a second apart get identical bytes and pay no
   prompt-cache miss.
4. **Truncation at a record boundary.** Half a decision reads as a whole one.

TESTED at 500 synthetic records: 2,000 bytes, every line a complete entry.

Both injection points — the opencode plugin's `system.transform` and
`harness/claude/hooks/memory-orient.sh` — shell out to `memory.py orient` and render nothing
themselves. A rule written once in TypeScript and once in shell is a rule that will disagree with
itself on the day it matters.

The block is snapshotted **per session**, so a capture by another worktree mid-session does not
move bytes in a prompt the session already paid to cache.

## 6. Backfill

`memory.py backfill [<rev-range>] [--limit N]`. Mechanical, zero model calls, safe to re-run — ids
are deterministic from the commit's own date and sha, so a second run overwrites rather than
duplicating. TESTED: two runs produce byte-identical files.

Every backfilled record is `INFERRED`, so **none can reach the orientation block**. That is the
whole safety argument: hundreds of commits can be imported without a human reading one of them and
standing context is unchanged.

`supersedes` is always null. Commit order is not supersession — two commits touching one subject
are usually both true, and inferring a chain from chronology would silently retire live decisions
in bulk.

A target whose existing classification is not `INFERRED` was authored or upgraded by hand; it is
skipped and reported. A backfill that silently downgraded a `VERIFIED` record would remove it from
the orientation block, which is the one direction this import must never move a record.

Evidence is extracted with `citegraph.CITE` — the gate's own regex object, not a copy. That
pattern encodes measured decisions (the extension list, the leading-dot rejection) each earned by
a failure.

## 7. Export: the promotion path, and the two blockers it arms

`memory.py export <dir> [<id> ...]`. Explicit, one record at a time, never a default.

**A tracked record joins `probe_citations.py`'s sweep**, so a rotted evidence pointer turns tier 1
RED and refuses the push. That converts "flagged for re-reading" into a hard block, against the
settled decision that this system warns and never blocks. An exported record's evidence is the
exporter's problem from then on.

**A tracked record joins the full-tree home-path scan on a public repo.** So `export` scrubs with
`gate._home_anchored` — the gate's own predicate, which carries a standing 14-row truth table
validated before every scan and already caught one real bug two ad-hoc controls missed. The scrub
is **fail-closed**: no predicate, no export. A lenient fallback would be a silent downgrade of the
one check whose job is stopping a home path reaching a public repository.

## 8. What the doctor says, and what it does not

Three rows under the family prefix `record store`. **FAIL only gates a tier.** An empty store is
the ordinary state of every fresh clone and of every project nobody has captured a decision in, so
it WARNs; gating on that would make `doctor` read NOT YET on a machine where the whole workflow
runs. The `store_fail` guard reaches both the Claude and the opencode tiers, because both inject
the orientation block.

Doctor rows exit 1 on FAIL. **That is preflight advice and refuses no push**, so it does not
contradict the advisory posture — say it out loud so nobody reads it as a reversal.

## 9. What this does not do

**No free probe can prove the memory system improves agent behaviour, and not one assertion in
`probe_memory_store.py` tries.** The 68 rows prove mechanism: the store addresses one place from
every tree shape, a record survives a round trip field for field, a malformed record is inert
rather than fatal, the index is genuinely disposable, and a bad record is refused by name on the
way in. A store that does all of that perfectly may still make the agent worse — by spending
context on records it does not need, or by anchoring it to a decision since invalidated. Those are
outcomes, and this suite has one instrument for outcomes.

Three blockers stand between here and measuring it, none solved by this phase. The arm factory
cannot express a memory-on versus memory-off arm: a synthesized arm is the base config plus at
most one delta skill, the plugin lives inside the frozen base, and the serve environment
hard-codes its variables, so both arms would carry the memory system and the contrast would be
empty. The arm factory synthesizes opencode config roots and sets no Claude config root, so the
Claude-side half has no measurement vehicle at all. And neither driver supports a multi-turn
study, while the value of a record is realized when a *later* session retrieves it.

The project's one comparable prior is a powered null: 150 rows, both arms delivering 75 of 75,
exact McNemar p = 1.0.

**Trigger (ii) is proven registered, never proven called.** A free probe proves a well-formed
schema reaches the agent. Only a model chooses to invoke it. That claim is paid.

**The Claude-side output contract is INFERRED, not TESTED.** That a SessionStart hook's
`hookSpecificOutput.additionalContext` reaches the session is read off Claude Code's documented
hook interface; driving a real SessionStart needs a real session, which the free suite cannot
start. Everything on this side of that boundary is tested, including that the hook emits valid
JSON for prose carrying quotes and newlines. If the contract is wrong, the failure is a session
that starts without orientation — which is where every session started before this existed.

**It does not replace `NEXT.md`'s `DECIDED` section.** That list is operator-facing, is read by a
human starting a session, and is deliberately frozen at a constant shape. The store is
agent-facing, per-project, and lives outside the tree. Whether `DECIDED` retires into it is a
separate decision with an existing owner, and this phase does not open it.

## 10. Operator quick reference

```bash
python3 harness/memory.py path             # where this project's records are
python3 harness/memory.py list             # every record, live and superseded
python3 harness/memory.py recall "<text>"  # search, heads only
python3 harness/memory.py orient           # what a fresh session will be told
python3 harness/memory.py backfill --limit 200
python3 harness/memory.py export docs/records/ <id>
```

Switches: `HEALBOT_RECORDS` (store root, for fixtures), `HEALBOT_CAPTURE_AT` (nudge fraction,
default 0.5), `HEALBOT_ORIENT=off` (skip the Claude-side injection).
