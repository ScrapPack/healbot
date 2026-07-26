# Phase 3 — Strip

Date 2026-07-26. Deliverable: `harness/` — an isolated opencode config that boots with
**41% less standing context** than the inherited default, with no capability removed.

Governing rule (owner's words): *models are capable in base form; agentic method structures
and command structures can be valuable, but things that are overhead are already covered by
the model architecture.*

Applied as a per-item test — **KEEP** if it grants a capability the model lacks (a tool, an
integration, a real workflow gate, a project-specific fact it cannot infer); **CUT** if it
instructs the model to do what it already does.

---

## Result

Measured in a neutral directory under `openai/gpt-5.6-sol` — **not** the `anthropic.txt`
figures from Phase 1. The default model routes to `gpt.txt` and swaps `edit`+`write` out for
`apply_patch`, so the earlier baseline did not describe this harness.

| Block | Baseline | Stripped | Δ |
|---|---:|---:|---:|
| Base prompt | 9,284 B (`gpt.txt`) | 1,715 B (`agent/build.md`) | **−7,569** |
| Tool definitions (11) | 19,898 B | 19,392 B | −506 *(opt-in, ships OFF)* |
| Skills block | ~7,900 B (18) | ~820 B (1) | **−7,112** |
| `~/.claude/CLAUDE.md` | 698 B | 0 B | −698 |
| **Total, as shipped** | **~36,710 B** | **~21,280 B** | **−15,427 B ≈ −3,857 tok (42%)** |

Commands: 20 → 3. Skills: 18 → 1. Both are byproducts of the skill switch — commands are a
projection of skills.

**Capability removed: none.** All 11 tools remain registered with full schemas. Every cut is
prose, inheritance, or duplication.

### Three caveats on that headline — added after audit

The absolute saving (~15.4 KB) is solid and **cwd-invariant**. The *percentage* and the
*coverage* are not, and the original table overstated both directions in small ways:

1. **The percentage is a neutral-directory best case the harness never actually runs in.**
   Measured from the fork root, baseline standing context is 46,332 B because the project
   `AGENTS.md` (8,748 B) loads — in **both** arms, since we deliberately keep project
   instructions. Same 15.4 KB cut, but that is **33.3%**, not 41%. Phase 4 develops in the fork.
2. **The prompt cut is per-agent.** `build`, `plan` and `general` each define no `prompt`
   (`agent/agent.ts:141,156,182`), so overriding `build` leaves every `plan` session and every
   `general` subagent receiving the full 9,284 B `gpt.txt`. A terminal that spawns subagents
   pays full standing context on each.
3. **The skills row was measured wrong, in the harness's favour.** 6,836 → 475 does not
   reproduce at either position. Two independent wire captures (different rigs, different mock
   providers) both measured Δ = **7,112 B** exactly. The baseline block is 7,794–7,936 B
   depending on where you cut the segment boundary; the stripped block is ~820 B, not 475 —
   and it is cwd-dependent, because the builtin skill's `<location>` renders as a bogus
   `file://` path under the session cwd. 475 B is unreachable in any version.

**Also**: the −506 B tool row requires `HARNESS_TRIM_TOOLS=1`, which `env.sh` ships commented
out. The table above is the as-shipped (trim-off) measurement; with trim on it is 20,776 B.

**And a scope warning for v2.** `packages/core` has no `gpt.txt`, no `~/.claude` ingestion and
no external-skill discovery; its builtin `build` prompt is 190 characters
(`core/src/plugin/agent.ts:13`). 96.7% of this delta is **v1-only**. On the v2 path the
harness's own `build.md` would be a ~1,525-character *addition*. This is another reason the
engine choice is load-bearing.

---

## What was cut, and why

### 1. Base prompt — `gpt.txt` (9,284 B) → `agent/build.md` (1,715 B)

The largest single win, and it needs **no source change**: an agent's own `prompt` *replaces*
the shipped base prompt rather than appending to it
(`session/llm/request.ts:60`, a ternary). Defining `prompt` on `build` swaps the whole file out.

I read `gpt.txt` line by line before cutting. Decisions:

| Kept | Why |
|---|---|
| Glob/Grep preference, tool parallelization, no `echo "===="` chaining | Harness-specific routing and rendering facts |
| **`apply_patch` for edits, never `cat`** | Load-bearing — this model has `apply_patch`, not `edit`/`write` |
| ASCII default | Non-obvious constraint |
| Dirty-worktree rules, never revert others' changes, no destructive git, non-interactive git | Real safety constraints — and directly relevant to a multi-session terminal where agents share a worktree |
| Formatting rules (flat lists, GFM, `file:line`) | Output-format constraints for terminal rendering |
| `commentary` / `final` channels | A harness protocol, not general knowledge — cutting it breaks the mechanism |

| Cut | Why |
|---|---|
| "You are OpenCode… deeply pragmatic, effective software engineer" | Persona framing |
| Editing Approach ("smallest correct changes", "prefer minimal") | Generic engineering judgment |
| Autonomy and persistence (~3 paragraphs) | Modern agentic models do this by default |
| Special user requests ("if asked the time, run `date`") | Trivially obvious |
| Frontend tasks ("avoid AI slop", React patterns) | Generic and situational |
| Final-channel structure guidance | Restates what the model already does |

### 2. Skills — 18 → 1 (6,836 B → 475 B)

`OPENCODE_DISABLE_EXTERNAL_SKILLS=true`. Default-deny; re-add only what earns its place.

The 18 were never configured for this project — opencode silently ingests `~/.claude/skills`
(16) and `~/.agents/skills` (16, near-duplicate), plus one builtin. Skill *metadata* is
injected into every request; only bodies are lazy.

This is also a **security** lever, not just a token one. A `SKILL.md` body containing
`` !`cmd` `` is shell-executed on slash-invoke with **no permission check**
(`session/prompt.ts:1396-1406`), and `/<skill-name>` bypasses the `skill` tool's permission
gate entirely (`command/index.ts:141-149`).

### 3. `~/.claude/CLAUDE.md` — 698 B → 0

`OPENCODE_DISABLE_CLAUDE_CODE=true`. Your global Claude Code instructions are good guidance,
but they are *your* cross-tool preferences leaking into every harness session by accident.
Project-level `AGENTS.md` still loads — deliberately. That is where project-specific facts
belong, and they pass the KEEP test.

### 4. Tool descriptions — 19,898 B → 19,392 B (opt-in)

The smallest win relative to its size, and the most honest section of this document.

Tool definitions are the **largest** block (19,898 B, 54% of baseline standing context), and
the `tool.definition` hook can rewrite any description with zero source change
(`plugin/src/index.ts:334`, triggered `tool/registry.ts:313`). That looked like the biggest
opportunity in the project.

It mostly is not. What actually shipped:

- **`todowrite`: 2,548 → 2,042 B.** Dropped the few-shot "Examples" section. A capable model
  does not need worked examples to keep a list.
- **`bash`: deliberately untouched.** It is the largest tool (5,164 B, 26% of the block) and
  the obvious target. I inspected its generated text line by line: the bulk is harness-specific
  semantics (`workdir` vs `cd`, timeout, output truncation, good/bad examples) and hard safety
  constraints — *"Only commit, amend, push, or create PRs when explicitly requested"* is a
  real behavioral rule models do **not** follow by default. Only ~807 B is the "# Git and
  GitHub" tail, and most of that is constraint rather than filler. **Cutting it would trade
  correctness for ~200 tokens. Declined.**
- **`task`: cannot be trimmed here.** Its subagent roster is appended *after* the hook runs
  (`tool/registry.ts:313-326`). Cut subagents instead if you want those 714 B.

The plugin ships **OFF** (`HARNESS_TRIM_TOOLS=1` to enable) with a refusal guard that rejects
any cut removing >65% of a description. A tool description is not pure overhead, and
over-trimming degrades tool use in ways that are expensive to notice later.

*Correction to Phase 1:* it named tool definitions as the top strip target. That was right
about the size and wrong about the opportunity — most of that block is load-bearing.

---

## What was kept, deliberately

| Kept | Reason |
|---|---|
| All 11 tools, full schemas | Tools are capability. Permission denies would remove them — and only blanket `*` denies actually drop a schema anyway |
| `build`, `compaction` agents | Structural. `defaultInfo()` throws without a visible primary (`agent/agent.ts:337-338`); `compaction` is fetched by hard-coded string |
| `plan`, `explore`, `general`, `title` | Left in place. `explore`+`general` cost 714 B of `task` description — a real cut, but they are genuine parallel-work capability. Revisit if the control terminal makes subagents redundant |
| Project `AGENTS.md` loading | Project-specific facts pass the KEEP test |
| `init`, `review`, `customize-opencode` commands | opencode builtins, lazy, zero standing cost |

---

## The isolation mechanism

**`XDG_CONFIG_HOME` — TESTED, and it closes a Phase 1 open question.**

Phase 1 could not determine whether it worked, and had corrected Phase 0's wrong claim that
`OPENCODE_CONFIG_DIR` isolates config. Result:

```
XDG_CONFIG_HOME=<harness>/config  →  config dir = <harness>/config/opencode   ✓ redirected
```

Skills stayed at 18 under XDG alone — they key off `$HOME`, not the config dir, exactly as
Phase 1 predicted. So isolation needs **both** XDG and the skill switch. That is what
`harness/env.sh` does.

Not set, on purpose:

| Switch | Why not |
|---|---|
| **`OPENCODE_DISABLE_DEFAULT_PLUGINS`** | **Breaks the harness — see below** |
| `OPENCODE_CONFIG_DIR` | Additive; does not isolate (Phase 1 C1) |
| `OPENCODE_DISABLE_AUTOCOMPACT` | Only reaches the legacy compactor. `"compaction": {"auto": false}` in the config file covers both engines (C2) |
| `OPENCODE_DISABLE_PROJECT_CONFIG` | Would also kill project `AGENTS.md`, which we want |
| `OPENCODE_PURE` | **Corrected.** The old reason ("already covered by `OPENCODE_DISABLE_DEFAULT_PLUGINS`") was wrong twice: that switch is itself forbidden, and the two gate *disjoint* sets — `plugin/index.ts:166` internal (auth) plugins, `:177` external ones from the config `plugin` key. Nothing has ever covered external plugins here. Since `trim-tools.ts` **is** an external plugin, setting `PURE` would silently disable the harness's own plugin layer |

---

## Files

```
harness/
├── env.sh                                  # the switch set; source before running opencode
└── config/                                 # = $XDG_CONFIG_HOME
    └── opencode/
        ├── opencode.jsonc                  # model, compaction.auto=false, plugin
        ├── agent/build.md                  # 1,715 B prompt replacing gpt.txt
        ├── plugin/trim-tools.ts            # tool.definition trimming, OFF by default
        ├── .gitignore          ← seeded by opencode, UNTRACKED, and self-ignoring
        ├── package.json        ← UNTRACKED. Pins @opencode-ai/plugin 1.17.10
        ├── package-lock.json   ← UNTRACKED
        └── node_modules/       ← UNTRACKED
```

**Only the first four are tracked.** opencode writes that `.gitignore` into any config dir at
boot (`config/config.ts:297-303`, byte-identical), listing `node_modules`, `package.json`,
`package-lock.json`, `bun.lock` and `.gitignore` itself. Because it ignores itself, `git status`
stays clean and nothing ever surfaces this. That is the "config loading mutates your disk every
boot" trap firing on our own deliverable.

Two consequences: a fresh clone of this repo gets the harness **without** its dependency
manifest or lockfile, and whether `trim-tools.ts` then loads depends on opencode re-seeding
them — untested. The pin is also drifted: `1.17.10` is the installed binary, while the fork we
target is `1.18.5`.

Usage:

```sh
. ~/Desktop/healbot/harness/env.sh
opencode
```

`env.sh` needs `$BASH_SOURCE` to locate itself, so **zsh or bash**. It now validates the path it
resolved and refuses loudly (exporting nothing) in dash or ksh, where it would otherwise have
silently pointed `XDG_CONFIG_HOME` at `$PWD` and booted with an empty config — a harness that
reports "skills disabled" while delivering none of the measured isolation.

---

## Verification

| Check | Result |
|---|---|
| Config dir redirected | ✓ `<harness>/config/opencode` |
| Skills 18 → 1 | ✓ (`customize-opencode`, the builtin) |
| Commands 20 → 3 | ✓ `init`, `review`, `customize-opencode` |
| `build.prompt` replaces base prompt | ✓ 1,715 B served |
| Trim plugin loads clean | ✓ 0 errors; `todowrite` 2,548 → 2,042 B |
| All 11 tools still registered | ✓ |
| **Real model turn end-to-end** | ✓ `opencode run` → correct reply, verified under XDG alone, +skills switch, +claude-code switch, and via `env.sh` |
| **Tool-using turn (file write + read-back)** | ✓ — **corrected, see below.** It works; the original ✗ was a model mix-up |
| Skills/commands floor is cwd-dependent | ✗ 18→1 / 20→3 holds in a neutral dir; in the fork it is 2 skills / 12 commands / 9 agents |
| `env.sh` portable to any POSIX sh | ✗ `${BASH_SOURCE[0]}` is a bash/zsh expansion — now guarded, refuses loudly in dash/ksh |

### The switch that broke the harness

`OPENCODE_DISABLE_DEFAULT_PLUGINS=true` was in the first version of `env.sh`, on Phase 1's
assessment that it "drops the 10 built-in auth plugins… purely provider auth; no prompt
impact." That description was accurate; the conclusion that it was therefore safe was not.

Those auth plugins are what resolve OpenAI models under oauth. With the switch on, every
turn died:

```
ProviderModelNotFoundError: Model not found: openai/gpt-5.6-sol.
Did you mean: gpt-5.6-sol, gpt-5.6-sol-pro, gpt-5.6-sol-fast?
```

Isolated by bisection — config keys, agent file and plugin all passed individually; the
switch alone reproduced it, and removing it fixed it. Removed from `env.sh` with a warning.

**Every measurement in this document was originally taken on a config that could not run a
single turn.** They were re-taken after the fix and are unchanged (tools 19,391 → 19,392 B,
noise), which independently confirms the switch had no prompt impact — it was pure breakage
for zero benefit. This is the entire justification for running a functional smoke test rather
than trusting static measurement.

### The tool-using turn — CORRECTED. It works.

**This section previously reported a failure that does not exist.** Retracted in full; the
correction matters more than the original claim, so it is spelled out.

TESTED under the harness, in a scratch directory:

```
. ~/Desktop/healbot/harness/env.sh
opencode run "Create a file named hello.txt containing exactly the text HELLO,
              then read it back and tell me its contents."
  > build · gpt-5.6-sol
  % Patch 1 file
  → Read hello.txt [offset=1, limit=10]
  "Created and verified `hello.txt`. Its contents are: HELLO"
```

`hello.txt`, 6 bytes, on disk. ~8s. Reproduced three times across two auditors, including with
`HARNESS_TRIM_TOOLS=1`.

**What went wrong originally: the stock-vs-harness comparison silently compared two different
models.** Stock config resolves to the user's global default `ollama/gemma4-agentic:q6`, which
mangled a path (`/var":}/`) and got its own `external_directory` permission auto-rejected. The
harness pins `openai/gpt-5.6-sol`. The decisive control — stock config with **only** the model
forced, `opencode run -m openai/gpt-5.6-sol` — succeeds identically. So the failure was the
model, not `opencode run`, not permissions, and not the strip.

The stated cause was also wrong: `opencode run` does **not** hang on a pending permission. It
prints `auto-rejecting` and returns.

**Consequences.**

- "The strip removed no capability" no longer rests on a defect; it now rests on a passing
  end-to-end tool-using run. Stronger, not weaker.
- Phase 4's stated mitigation ("drive the server API instead, `opencode run` is unreliable")
  was planned around a phantom. Drive the server API for the *real* reasons — v1/v2 accounting
  and the event vocabulary — not this one.
- **Any other stock-vs-harness A/B in this document is suspect for the same reason.** Always
  pass `-m` explicitly when comparing arms.

Separately, and confirmed by direct test: `POST /session/{id}/prompt_async` accepts a prompt
and executes **nothing** — the user message is stored, no assistant turn follows. The
synchronous `POST /session/{id}/message` works. `PLAN.md` builds its Phase 4 spawn path on
`prompt_async`; that needs revisiting.

---

## Still open

- **`/code-review ultra` has not been run.** Per the plan this is where it belongs — there is
  now a real diff to review, and this phase deleted things that could be load-bearing. It is
  user-triggered and billed; I cannot launch it. Run from `~/Desktop/healbot`. The
  multi-agent audit in [REVIEW.md](REVIEW.md) covered assumptions, not the diff, and found two
  live defects in `env.sh` alone — this gate is still worth closing.
- Cutting `explore`/`general` subagents (714 B) is deferred pending the control terminal's
  design — it may make them redundant. Note caveat 2 above: leaving `general` in place also
  means every subagent session pays the full `gpt.txt`.
- Whether `trim-tools.ts` still loads from a fresh clone, given the untracked `package.json`.

**Closed since this document was written** (see [REVIEW.md](REVIEW.md)): the `cache.read`
question — the retirement trigger measures *occupancy*, where `cache.read` is **included**;
the v2 token-accounting contradiction — v2 does not write `session.tokens`, so v1 is a hard
requirement; and N-way concurrency, which is TESTED working.
