# gnhf in healbot — specification

**Written** 2026-07-31 · **gnhf** 0.1.43 · **repo** `~/Desktop/healbot` @ `76b23cc` (branch `main`)

**Revised 2026-08-06.** The watchdog moved into the repo, every launch recipe here was rewritten to
the two-step form it always required, and its token cap became a dollar cap. §3.6 carries the
watchdog's contract; the rows in §5 say which claims were re-checked on that date and which still
date from 2026-07-31.

Every claim below is tiered per this project's method: **TESTED** (I ran it) / **VERIFIED** (I read
the code, cited) / **INFERRED** (stated link is not measured) / **SUSPECTED**. No loop was run —
nothing in this document cost a model turn beyond the sessions that wrote it. **No healbot file was
modified by the checks behind it.**

Companion artifacts. **The watchdog is no longer a scratchpad file.** It is tracked at
`harness/gnhf-watch.sh`, because the first copy was written into a session scratchpad on
2026-07-31, never committed, and had to be written again from this spec once that scratchpad was
collected. Its header carries that reasoning and the sizing rules. The three prompt files went into
that same scratchpad and are tracked nowhere, so `$SCRATCH` below names wherever you write them:

| File | What it is |
|---|---|
| `prompt-free-probes.md` | the objective for run (a) |
| `prompt-vacuous-hunt.md` | the objective for run (b) |
| `prompt-paid-handoff.md` | the objective for run (c) |

---

## 1. The measured CLI surface

### 1.1 Install and shape

```
/opt/homebrew/bin/gnhf -> ../lib/node_modules/gnhf/dist/cli.mjs      # TESTED (readlink)
gnhf --version  ->  0.1.43                                           # TESTED
```

**There are no subcommands.** TESTED: `gnhf run --help` prints the top-level help, because
`commander` consumes `run` as the positional `prompt` argument. The entire interface is
`gnhf [options] [prompt]`, plus `gnhf` bare (resume) and `<prompt> | gnhf` (stdin).

### 1.2 Every flag, as measured

TESTED — verbatim from `gnhf --help` on 0.1.43:

| Flag | Meaning | Default |
|---|---|---|
| `--agent <agent>` | `claude`, `codex`, `rovodev`, `opencode`, `copilot`, `pi`, or `acp:<target-or-command>` | config file (`claude`) |
| `--max-iterations <n>` | Abort after N total iterations | unlimited |
| `--max-tokens <n>` | Abort after N total input+output tokens | unlimited |
| `--stop-when <condition>` | End when the **agent reports** this condition; persisted per run; `""` clears | unset |
| `--prevent-sleep <mode>` | `on`/`off` (also `true`/`false`) | config (`on`) |
| `--worktree` | Run in a separate git worktree | `false` |
| `--current-branch` | Run on the current branch instead of creating `gnhf/<slug>` | `false` |
| `--push` | Push after each successful iteration | `false` |
| `--meteor-frequency <n>` | TUI decoration, 0–5 | `3` |
| `--mock` | Undocumented in help text | `false` |
| `-V, --version`, `-h, --help` | — | — |

`--mock` runs a `MockOrchestrator` with a hardcoded demo prompt and never spawns an agent —
VERIFIED (`dist/cli.mjs` `.option("--mock", "", false)` → `if (options.mock) { const mock = new
MockOrchestrator(); ... return; }`). It is a safe way to preview the TUI; it is **not** a dry run
of your prompt.

### 1.3 Config file

`~/.gnhf/config.yml`, created on first invocation. TESTED — I ran gnhf under an isolated `HOME`
and it materialised the file. **On this machine `~/.gnhf` did not exist before this spec was
written** (TESTED: `ls ~/.gnhf` → No such file or directory), so the first real run creates it.

Effective keys (VERIFIED against the bootstrap golden in `dist/cli.mjs`):

```yaml
agent: claude
maxConsecutiveFailures: 3     # abort after 3 consecutive failed iterations — CONFIG ONLY, no CLI flag
preventSleep: true
# agentPathOverride:  {claude|codex|copilot|pi}: <binary>
# agentArgsOverride:  {claude|codex|copilot|pi}: [extra CLI flags]
# acpRegistryOverrides: {<name>: "<spawn command>"}
# commitMessage: {preset: conventional}
```

`--max-iterations` / `--max-tokens` are **runtime-only and never persisted**. `--stop-when` is
persisted per run (`.gnhf/runs/<runId>/stop-when`) and is reused on resume.

### 1.4 Run state and logs

Per-run directory `<repo>/.gnhf/runs/<runId>/` (VERIFIED, `setupRun`/`resumeRun`):

| File | Contents |
|---|---|
| `prompt.md` | your objective, verbatim |
| `notes.md` | cross-iteration memory, written by the orchestrator; the agent is told **not** to modify it |
| `gnhf.log` | JSONL orchestrator/agent/HTTP lifecycle events with elapsed timings and `error.cause` chains |
| `iteration-<n>.jsonl` | the agent's raw streaming output for iteration *n* |
| `base-commit`, `stop-when`, `commit-message`, schema | run metadata |

**gnhf appends `.gnhf/runs/` to `.git/info/exclude`, not to `.gitignore`** — VERIFIED
(`ensureRunMetadataIgnored` shells `git rev-parse --git-path info/exclude`). This matters for
healbot specifically: `gate/gate.py:78-91` builds its untracked-file list with
`git ls-files --others --exclude-standard`, which honours `info/exclude`, so **gnhf run metadata
will not pollute the gate's changed-file set.** VERIFIED at both ends.

### 1.5 The complete set of stop conditions

VERIFIED by reading the orchestrator. There are six, and it is worth knowing that none of them is
a clock:

1. **`--max-iterations n`** — `getAbortReason()` checks `currentIteration >= maxIterations`
   **before the next iteration begins**. It cannot interrupt one.
2. **`--max-tokens n`** — `getTokenAbortReason()`: `totalInputTokens + totalOutputTokens >= n`.
   Can abort mid-iteration, but only when a usage event arrives.
3. **`--stop-when "<cond>"`** — **self-reported by the agent.** gnhf injects a
   `should_fully_stop` field into the agent's output schema and a "## Stop Condition" section
   into the iteration prompt; the loop ends when the agent sets that boolean. gnhf does not
   evaluate the condition itself. Treat it as a hint, never as a guard.
4. **`maxConsecutiveFailures: 3`** — config only. A complete no-op iteration counts as a failure.
5. **Permanent agent error.** For the claude backend the *only* pattern is
   `/credit balance\s+is\s+too\s+low/i` on stderr (VERIFIED, `isPermanentClaudeError`). Retryable
   errors use exponential backoff.
6. **Signals.** First Ctrl+C = graceful stop after the current iteration; second Ctrl+C and
   `SIGTERM` = immediate force stop.

**What is absent — and this is the load-bearing finding of §1.** There is no wall-clock timeout,
no per-iteration timeout, and no inactivity/stall detector for native agents. VERIFIED: grepping
the bundle for `inactivity` and `idleTimeout` returns **0 hits**; the only `withTimeout(...)` is
on the ACP path (`runPromptTurn`), not on `ClaudeAgent`. `ClaudeAgent.run` spawns and awaits
`close` with no timer. Consequence, and §3 turns on it: **a parked iteration defeats caps 1 and 2
simultaneously** — 1 is only checked between iterations, 2 needs usage events a parked process
never emits.

### 1.6 Token accounting is not billing

VERIFIED (`toTokenUsage$1`):

```js
inputTokens: (usage.input_tokens ?? 0) + (usage.cache_read_input_tokens ?? 0)
```

`--max-tokens` counts **cache reads at full weight**. In a repo where `HARNESS.md` is 77,936 B and
`NEXT.md` is 31,360 B and every iteration re-reads them, the counter climbs far faster than the
bill does. Set the cap for *loop containment*, and do not read it as a dollar figure.

### 1.7 What the `claude` backend actually gets

VERIFIED (`buildClaudeArgs`):

```js
[...userArgs, "-p", prompt, "--verbose", "--output-format", "stream-json",
 "--json-schema", <schema>,
 ...(userSpecifiedPermissionMode ? [] : ["--dangerously-skip-permissions"])]
```

`userSpecifiedPermissionMode` is true only if `agentArgsOverride.claude` contains
`--dangerously-skip-permissions`, `--permission-mode[=]`, or `--permission-prompt-tool[=]`. The
child is spawned `detached: true` with `stdio: ["ignore", "pipe", "pipe"]` — **stdin is ignored**,
so nothing interactive can ever be answered.

Read that together: by default an unsupervised gnhf run against healbot has **no permission
boundary at all**. §3 is written around that fact.

For the other backends: `opencode` is started as a local `opencode serve` with "a blanket allow
rule so tool calls do not block on prompts"; `codex` gets `--full-auto` unless you specify an
execution mode. Same shape, same conclusion.

### 1.8 Guards, all TESTED against throwaway repos

| Condition | Result |
|---|---|
| not a git repository | `This command must be run inside a Git repository...` · exit 1 |
| dirty working tree | `Working tree is not clean. Commit or stash changes first.` · exit 1 |
| `--meteor-frequency 9` | `argument '9' is invalid. must be between 0 and 5` · exit 1 |
| `--worktree --current-branch` | `Cannot combine --current-branch and --worktree.` · exit 1 |

`ensureCleanWorkingTree` is `git status --porcelain` non-empty (VERIFIED). **healbot's tree is
dirty right now** — 2 modified, 9 untracked including `gate/` and the whole A/B study — so gnhf
will refuse until §4 step 3 is done.

### 1.9 Two package-level facts

- **Telemetry is on by default.** Anonymous usage only, no prompts or paths. `GNHF_TELEMETRY=0`
  disables it. Set it: this project's threat model is about what leaves the machine unattended.
- **The npm package ships a file named `SKILL.md`** at
  `/opt/homebrew/lib/node_modules/gnhf/skills/gnhf/SKILL.md` (TESTED, 8,084 B). That filename is
  banned anywhere in the healbot tree — see §3.2. Do not copy it in, and do not install it to
  `~/.agents/skills/` either; §3.3 explains why that is worse.

---

## 2. Three concrete first uses

### Common preamble

All three assume:

- **No `--worktree`.** `gate/GATE.MAP.md` ("No worktree, and that is deliberate") records that
  this repo gitignores `/opencode/`, `node_modules/` and `.carryover/verified/venv/`
  (each named in `.gitignore`), so a healbot worktree "contains no checkout, no deps and no venv — it
  cannot resolve one `file:line` citation or run one probe." A gnhf worktree run would go red on
  Tier 1 in its first iteration and stay red.
- **No `--push`.** The remote is `ScrapPack/healbot`. Publishing is a decision, not a side effect.
- **`--prevent-sleep on`.** Otherwise the Mac sleeps and the "overnight" run is a 20-minute run.
- **Launched with `harness/gnhf-watch.sh` watching gnhf's pid** (§3.6), which supplies the stop
  condition gnhf lacks. The watchdog is a *second* process, not a wrapper: gnhf goes to the
  background, and its pid is the watchdog's only argument.
- **`GNHF_TELEMETRY=0`.**

Two budgets, and conflating them is the expensive mistake: **gnhf spends Claude Code tokens**
(bounded by `--max-tokens`), while healbot's paid tier spends **OpenAI credits on
`openai/gpt-5.6-sol`** through the rigs (bounded by nothing gnhf knows about). "Free" below always
means *free of healbot API credits*. No gnhf run is free of agent tokens.

**The prompt lives in a file, and that is not a style preference.** Prompt files sit in the
scratchpad — deliberately **outside the repo**, because a prompt file inside `~/Desktop/healbot`
would make the working tree dirty and gnhf would refuse to start (§1.8).

I originally wrote these three invocations with the prompt inline as `"$(cat <<'PROMPT' … PROMPT)"`
and the verification step caught a real defect: **that construct is silently broken under macOS's
`/bin/bash` 3.2.57.** TESTED — a lone apostrophe inside a quoted heredoc nested in `$( )` makes
bash 3.2 treat it as an opening quote, swallow the closing `)`, and die with *"unexpected EOF while
looking for matching `"'"*. Prose with an even number of apostrophes survives by luck; prose with
an odd number does not. `zsh` (this machine's shell) parses it correctly, so the failure appears
only when a run is launched from a `#!/bin/bash` script or a cron entry. `"$(cat <file>)"` is a
plain command substitution and is safe in both.

---

### (a) Overnight — the free probe backlog and its coverage

Free of healbot credits: the probes in `.carryover/verified/README.md` are marked "free —
no model turns, no API credits." Each probe declares and prints its own `Results(expect=N)`
floor; the floors are the expected scores, and prose copies of the totals are exactly what
went stale (NEXT.md is frozen to task + pointers and no longer carries them).

```sh
cd ~/Desktop/healbot
GNHF_TELEMETRY=0 gnhf \
  --agent claude \
  --max-iterations 12 \
  --max-tokens 4000000 \
  --prevent-sleep on \
  --stop-when "gate/gate.py --base main exits 0 AND every probe_*.py in .carryover/verified exits 0" \
  "$(cat "$SCRATCH"/prompt-free-probes.md)" &
GNHF=$!
STALL_MIN=25 MAX_HOURS=8 COST_MAX=60 harness/gnhf-watch.sh "$GNHF"
```

Two commands, and the split is load-bearing. `GNHF_TELEMETRY=0` is gnhf's variable; `STALL_MIN`,
`MAX_HOURS` and `COST_MAX` are the watchdog's, and the watchdog reads nothing else from the
command line but the pid (§3.6). Keep the pair in one `tmux` window, or under `nohup`, so closing
the terminal cannot take gnhf down while the watchdog is still counting (INFERRED, not measured
here).

Why these numbers: iterations sized at one per probe (count probe_*.py at launch; the sweep
in probe_rig_contract.py discovers them the same way). 4M tokens is roughly 330K counted tokens per
iteration, which is generous for read-heavy work in a repo with a 78 KB index — and remember
§1.6, cache reads count in full. `COST_MAX=60` is a dollar ceiling rather than an estimate: the
token counter cannot express one (§1.6), so the watchdog reads gnhf's own per-iteration
`total_cost_usd` instead (§3.6).

**Caveat (INFERRED, high confidence):** `probe_turn_growth.py` is documented RED at 13/16 in
`.carryover/verified/README.md`, while its own floor (`Results(expect=19)`) reflects Phase 12's
re-derivation, and its real-corpus fixture can also go red from live-DB drift (healbot-traps
skill). The prose and the floor were written at different moments. Establish the real baseline
by hand before launching, or the loop will spend an iteration "fixing" a red that is either
already fixed or deliberate.

---

### (b) Self-testing — hunt the vacuous assertion

This is the loop that matches the repo's documented obsession. The project's characteristic
failure is *passing*: `docs/VERDICT.md` records six paid rigs that printed a verdict and exited 0
anyway; `docs/CLONE.md` records three probes that exited 0 from a fresh clone having proven
nothing; `docs/OUTCOME.md` records three `fire()` calls at a dead port satisfying **every**
completion predicate in the suite in 9 ms.

```sh
cd ~/Desktop/healbot
GNHF_TELEMETRY=0 gnhf \
  --agent claude \
  --max-iterations 8 \
  --max-tokens 3000000 \
  --prevent-sleep on \
  --stop-when "three distinct vacuous assertions have been hardened, each with a mutation whose RED was observed and recorded, and probe_rig_contract.py is green at 29/29 or higher" \
  "$(cat "$SCRATCH"/prompt-vacuous-hunt.md)" &
GNHF=$!
STALL_MIN=20 MAX_HOURS=6 COST_MAX=40 harness/gnhf-watch.sh "$GNHF"
```

Note the deliberate asymmetry with (a): a shorter stall window (20 min — this work is
read-and-edit, not server-booting), a lower iteration cap and a lower spend ceiling, because a
vacuous-assertion hunt that finds nothing should stop rather than invent something. NEXT.md's task
section is explicit: *"Do not invent something to build."*

---

### (c) Paid tier — one rig, pre-authorised, hard-capped

**This one is not launched by an agent. The owner types it, after saying yes.** NEXT.md's closing
line is the rule: *"Ask me before spending real API credits on anything beyond a few turns."*

The cheapest useful paid item is NEXT.md's task item 4: `verify_handoff.py` must be **re-run** before its
21/21 can be quoted again — Phase 5 took it to 22 unconditional assertions and never executed it,
so the recorded score is arithmetically unreachable, and HARNESS.md, `docs/VERIFY.md` §10 and the
rig README all cite it as the Phase 4 exit gate's second clause. Its floor is 22. Its workload is
three ~130 KB ledgers read in full plus file creation.

```sh
# PRE-CONDITION: the owner has said yes, in this session, to spending credits on
# verify_handoff.py and on nothing else.
cd ~/Desktop/healbot
GNHF_TELEMETRY=0 gnhf \
  --agent claude \
  --max-iterations 3 \
  --max-tokens 1500000 \
  --prevent-sleep on \
  --stop-when "verify_handoff.py has been executed exactly once, its real exit code and score are recorded, and every document quoting 21/21 has been corrected to the measured value" \
  "$(cat "$SCRATCH"/prompt-paid-handoff.md)" &
GNHF=$!
STALL_MIN=20 MAX_HOURS=2 COST_MAX=15 harness/gnhf-watch.sh "$GNHF"
```

Caps rationale: `--max-iterations 3` bounds *iterations*, not dollars — the spend is one rig
invocation, and the prompt is what bounds that. Three leaves room for pre-flight, the run, and the
document corrections. `MAX_HOURS=2` is the real money guard, sized against the ~6–11 minute wall
clock recorded for a comparable rig in `.carryover/verified/README.md`, the paragraph opening
"Costing, REDONE for the 180,000 target".

**`COST_MAX=15` does not cap this run's healbot credits, and reading it that way is the expensive
mistake the preamble names.** It caps gnhf's own Claude Code spend. `verify_handoff.py` bills a
different account, and nothing on either of these two command lines bounds it: the prompt does.

---

## 3. The safety contract

### 3.1 The default is no boundary

**VERIFIED, and it is the first thing to internalise:** gnhf appends
`--dangerously-skip-permissions` to every `claude` invocation unless `agentArgsOverride.claude`
already carries a permission flag (§1.7). An overnight gnhf run against healbot has, by default,
unrestricted tool access to the machine.

The premise "a headless session parked on a permission ask waits forever and consumes nothing, so
caps never fire" is **half right, and the half that is wrong is the more dangerous half**:

- Under gnhf's **default** claude args, a permission ask cannot occur, so the loop cannot park on
  one. What it can do instead is `npm install`.
- If you **restore** permissions via `agentArgsOverride.claude`, the ask becomes possible again —
  and `stdio[0]` is `"ignore"` (VERIFIED), so nothing can answer it, and there is no timeout
  anywhere (§1.5) to end it. The repo has the same hazard measured on its own harness:
  HARNESS.md:385 — *"No timeout on a pending permission — a client that ignores `permission.asked`
  hangs that tool call forever. TESTED: it hangs indefinitely."*

Both branches need the watchdog in §3.6, for opposite reasons. Choose deliberately, and write the
choice down.

### 3.2 The four banned filenames

`AGENTS.md`, `CLAUDE.md`, `CONTEXT.md`, `SKILL.md` are banned **anywhere in the tree**
(HARNESS.md:9-13, now enforced at `gate/gate.py:220`). The first three auto-ingest into every
session's context via `packages/opencode/src/session/instruction.ts:64-68`; `SKILL.md` collides
with opencode's `**/SKILL.md` skill glob — and per `gate/gate.py:223-230`, *"a `SKILL.md` body
containing `` !`cmd` `` shell-executes on slash-invoke with no permission check
(`harness/env.sh:63-68`, re-verified 2026-07-31 against 1.18.5 … still unfixed)."* Maps are
`<DIR>.MAP.md`.

Two live traps this creates for gnhf specifically:

- **The gnhf package ships `skills/gnhf/SKILL.md`** (§1.9). An agent told to "install the gnhf
  skill" will copy a banned filename into the tree. Every prompt must forbid it explicitly.
- **A committing loop hides the violation from the gate.** `gate/gate.py:78-91` with no `--base`
  reports the *working tree*, and gnhf commits after every successful iteration — so the tree is
  clean and `changed_files` is empty, `lint()` skips, and `banned_names([])` returns PASS having
  checked nothing. VERIFIED at both ends. **Inside a gnhf loop the gate must always be run as
  `gate/gate.py --base main`.** All three prompts in §2 do.

### 3.3 The A/B refusal study is live; its stock arm is fragile

`.carryover/verified/AB-HANDOFF.md` describes a running harness-vs-stock comparison. **Off-limits
to any autonomous loop:**

```
.carryover/verified/ab.py
.carryover/verified/run_refusal.py
.carryover/verified/probe_refusal_driver.py
.carryover/verified/probe_refusal_scoring.py
.carryover/verified/verify_refusal_a.py
.carryover/verified/verify_refusal_b.py
.carryover/verified/studies/
.carryover/verified/README.md
.carryover/verified/AB-HANDOFF.md
.carryover/verified/hb/ab-refusal-pilot-{harness,stock}.db{,-wal,-shm}
docs/REFUSAL-BASELINE.md
harness/config/opencode/plugin/healbot.ts        <- the harness ARM itself
harness/config/opencode/opencode.jsonc           <- the harness ARM itself
```

**Correction to the brief, and you should know it before writing any prompt that names the file:
`docs/AB-REFUSAL.md` does not exist.** TESTED — `find` across the tree returns only
`hb/ab-refusal-pilot-*.db`, and `AB-HANDOFF.md` lists `docs/AB-REFUSAL.md` under *MISSING — build
these*. It is the study's future output. `docs/REFUSAL-BASELINE.md` **does** exist (27,932 B,
untracked) and is the document the study is trying to falsify.

**The stock arm is defined by the ambient environment, so ordinary tidying corrupts it.**
`ab.py:93-94` defines it as *"stock opencode: gpt.txt (9,284 B), 18 skills,
~/.config/opencode/AGENTS.md (8,091 B) loaded — displaces ~/.claude/CLAUDE.md"*. Therefore:

> **Corrected 2026-08-02.** This paragraph originally cited `ab.py:78-80` and quoted the arm as
> *"gpt.txt (9,284 B), **18 skills**, `~/.claude/CLAUDE.md` loaded."* That string was rewritten on
> 2026-07-31 — the same day this document was written — and `ab.py`'s own comment beside it calls
> the old wording *"a false claim being written into every run's meta.json"*: the three global
> memory files were consolidated into one canonical file, and `~/.config/opencode/AGENTS.md` is
> slot 0 of `instruction.ts`'s `globalFiles` whose resolution loop `break`s on the first match, so
> it **displaces** `~/.claude/CLAUDE.md` rather than adding to it. C2 went 698 B → 8,091 B. The
> bullet below about creating that file therefore describes a hazard that has **already fired**.
> Found by the verbatim-quote leg of `probe_citations.py`, which did not exist when this was
> written.

- **Creating `~/.config/opencode/AGENTS.md` corrupts the stock arm.** TESTED: it does not exist
  today, and `~/.config/opencode/` currently holds only `opencode.jsonc`, `package.json`,
  `package-lock.json`, `.gitignore`, `node_modules`. Any agent that "adds project instructions"
  there silently changes the thing under measurement.
- **Adding anything to `~/.agents/skills/` corrupts it too** — the skill count is part of the arm
  definition (confound C3).
- **Do not `rm -rf ~/.claude/CLAUDE.md`, do not edit it, do not "clean up" `~/.config/opencode`.**
  Their *presence* is the independent variable.

⚠ **Discrepancy the owner must resolve before trusting a stock-arm result.** TESTED:
`ls ~/.agents/skills | wc -l` returns **16**, not the 18 recorded in `ab.py:80`. Either the arm
definition is stale, or opencode counts a different set (bundled or project-level skills), or two
skills were removed since the pilot. I did not determine which. Whichever it is, it demonstrates
the point: **the stock arm's definition is a claim about a directory outside the repo that nothing
in the repo checks.** A pre-flight assertion on that count belongs in `ab.py`, and §4 step 5 makes
it a manual check meanwhile.

### 3.4 No package installs. Ever.

HARNESS.md:354, quoted: *"It now holds **84 entries and 94 MB including `node_modules`** — a model
in some earlier run shelled out to `npm install`."* That same directory produced a turn measuring
**299,326 tokens**, 71% above the 175,148 on record, which took `probe_turn_growth.py` red.

The repair is on record and so is the live residual risk (HARNESS.md:354): the directory was
**restored at the end of Phase 12, 94 MB → 1.8 MB**, and the removed residue included a
model-created `.gitignore` holding `node_modules/`. So the protection that was silently absorbing
this is **gone**: *"a future run that shells out to `npm install` will have `git_baseline()`'s
`git add -A` commit `node_modules` into `hb/project/.git`."*

An unsupervised loop that runs one package install therefore does three things at once: bloats the
repo, corrupts the corpus that sizes `RETIRE_AT`, and commits the damage into a git baseline. Every
prompt in §2 bans installs by name (`npm`, `pnpm`, `yarn`, `bun`, `pip`, `brew`). If a task
genuinely needs a dependency, that is an ASK, and the loop must record `success=false`.

### 3.5 The corpus is evidence, not scratch

`.carryover/verified/hb/*.db` is `probe_turn_growth.py`'s corpus. The rig README's "Assertion
discipline" section and the paid-run-protocol skill carry the rule: archive a rig DB under a
name that still matches `hb/*.db` (`quest.db` becomes `quest-phase12a.db`); deleting it removes
the evidence sizing RETIRE_AT. And from the README: *"DO NOT clear `hb/project` or drop a DB to make this
green — that deletes the measurement to restore the number."* A loop optimising for green is
exactly the process that would do this. Ban deletion, allow archival-with-rename.

### 3.6 The blocked-on-ask watchdog is the primary stop condition

Because §1.5 establishes that gnhf ships no clock, the AFK loop must be wrapped. The watchdog is
tracked at `harness/gnhf-watch.sh`, and it is **a second process, not a wrapper**. It takes one
argument, and that argument is gnhf's pid. Start gnhf in the background, capture `$!`, hand that
over:

```sh
GNHF_TELEMETRY=0 gnhf --agent claude --max-iterations 12 ... "$(cat "$SCRATCH"/prompt.md)" &
GNHF=$!
STALL_MIN=25 MAX_HOURS=8 COST_MAX=60 harness/gnhf-watch.sh "$GNHF"
```

**Passing gnhf's own flags to the watchdog is the mistake every recipe in this document used to
teach.** It is now fatal instead of silent. TESTED 2026-08-06:

| Invocation | Result |
|---|---|
| `harness/gnhf-watch.sh --agent claude --max-iterations 12` | `FATAL: '--agent' is not a pid. Start gnhf first, then pass its pid.` · exit 1 |
| `harness/gnhf-watch.sh 999999`, no such process | `FATAL: no live process with pid 999999` · exit 1 |
| `BILL_MAX=3000000 harness/gnhf-watch.sh <live pid>` | `FATAL: BILL_MAX is gone; it over-counted ~2.8x. Use COST_MAX (US dollars).` · exit 1 |

Why it had to become fatal rather than a usage warning: with `--agent` as `$1`, `kill -0 --agent`
fails, so the poll loop never ran once, and the script fell through to its own *"exited on its
own; nothing to stop"* line and exited **0**. A watchdog that exits 0 having watched nothing is
indistinguishable from one that watched a clean run: this repo's characteristic failure
(`docs/VERDICT.md`, `docs/CLONE.md`, `docs/OUTCOME.md`), landing on the one component whose entire
job is to be the thing you did not have to check.

**Environment.** Nothing else is read from the command line.

| Variable | Meaning | Default |
|---|---|---|
| `STALL_MIN` | minutes without an `iteration-*.jsonl` write before the run is called stalled | `25` |
| `MAX_HOURS` | wall-clock ceiling | `8` |
| `COST_MAX` | **US dollars**, decimal accepted. `0` disables the spend cap | `0` |
| `SPEND_FAIL_MAX` | **which** consecutive spend-accounting failure stops the run; the ones before it are tolerated. Dead unless `COST_MAX` is above zero | `3` |
| `BILL_MAX` | **refused with a fatal error.** It counted tokens, not dollars | gone |

`BILL_MAX` is rejected rather than reinterpreted because the two units are not comparable: a
number meant as a token cap, read as dollars, turns a 3,000,000-token ceiling into a $3M one,
which is no ceiling at all. Its over-counting and the four separate ways it was wrong are recorded
in the watchdog's own header, next to the code that replaced it.

There is no `REPO` variable. Earlier revisions of the recipes above set one and nothing ever read
it; the watchdog takes the repo root from `git rev-parse --show-toplevel`.

Two consequences of the cap being real money rather than a token count. gnhf's `--max-tokens`
cannot express a dollar ceiling at all (§1.6: cache reads count at full weight), so the watchdog
reads gnhf's own per-iteration `total_cost_usd` and adds a floor for the iteration still in
flight. And if `COST_MAX` is above zero while `harness/gnhf-spend.py` is missing, the watchdog
refuses to start, because a cap that cannot be computed is a cap that silently never fires.

That refusal has a running twin, and it is a **fourth stop reason**. A helper that is present but
fails, or prints something that is not two numbers, would report zero spend for the rest of the
night, which reads as comfortably under budget. So the watchdog counts consecutive accounting
failures and stops on the `SPEND_FAIL_MAX`th of them, on the reasoning that being unable to measure
spend and continuing anyway is spending blind. The failures before it are tolerated so that one
transient blip does not kill an eight-hour run.

**The whole leg lives inside the `COST_MAX` test**, counter included. At the default `COST_MAX=0`
there is no accounting to fail and this stop cannot fire, which is the intended shape: it guards a
cap you asked for, never a run you never capped.

`COST_MAX` bounds **gnhf's Claude Code spend only.** It is blind to healbot's own API credits,
which the rigs bill to a different account entirely (§2 preamble). A paid rig running inside the
loop is not capped by it.

Mechanism: poll every 60 s. Resolve **this run's** directory from the `run:start` line in
`.gnhf/runs/*/gnhf.log` carrying the pid you passed, which is the second reason the argument is a
pid and not a flag: a glob over every run directory would charge this run for every earlier one,
and would let an earlier run's files answer the "has anything been written yet" question and fire
the stall detector during bootstrap. Then watch that one directory's `iteration-*.jsonl`
(§1.4 — that file is the agent's live output stream, so its mtime is the only free liveness signal
gnhf offers). If iteration files **exist** and none of them is fresher than `STALL_MIN` minutes, or
`MAX_HOURS` have elapsed, or spend has reached `COST_MAX`, or spend accounting has failed
`SPEND_FAIL_MAX` times running (those last two only when `COST_MAX` is above zero, which is not the
default), send `SIGTERM` — which gnhf treats as an immediate force stop
(§1.5 #6). Then `SIGKILL` after 10 s, and report any surviving `claude` process, since gnhf spawns
it `detached: true`. A forced stop exits 2; gnhf finishing on its own exits 0.

**The two pids are the same pid, and everything above rests on it.** VERIFIED 2026-08-06 in gnhf
0.1.43: the log writer's `formatLine` stamps every line it emits with `pid: process.pid`, so
`run:start` carries gnhf's own pid; and `/opt/homebrew/bin/gnhf` is a direct symlink to
`dist/cli.mjs` whose shebang is `#!/usr/bin/env node`, so `env` execs node in place and the shell's
`$!` is that same process, and the real runs left under `.gnhf/runs/` carry the field. Were it *not*
the same pid, `RUN_DIR` would never resolve, the stall and spend legs would never run at all, and
`MAX_HOURS` would be the only bound left on the night.

That last report is a `pgrep` on gnhf's **flag pair**, `--output-format stream-json --json-schema`,
which `buildClaudeArgs` emits adjacently and unconditionally (§1.7) and which no config can
reorder, because gnhf reserves both flags against `agentArgsOverride`. The first flag alone is the
Claude Code app's as well: MEASURED 2026-08-06 with no gnhf agent running, every process it
matched was an interactive session, and the pair matched none of them.
Still read the list rather than killing from it. And note the failure this narrowing accepts: if a
future gnhf reorders those flags the pair matches nothing, which is also what a clean reap looks
like, so re-check it when gnhf moves off 0.1.43.

The existence test is a separate leg from the freshness test, and it is not a detail: a run that
has not written its first iteration file yet is **starting up**, not stalled, so the stall leg
deliberately does not fire on it. Collapsing the two into one "nothing written recently" test
would kill every run during its own bootstrap.

Defaults: `STALL_MIN=25`, `MAX_HOURS=8`. Tune the stall window **above** the slowest legitimate
single operation. Two documented ones to size against: `verify_question.py` polls three framings at
300 s each and *"a run where the first two framings do not land takes ~10 minutes before it reaches
the grid. That is the rig working, not hanging"* (the healbot-traps skill); and `wait_for` in
`rig.py:595` checks its deadline only between calls to `fn` while `Api.__call__` defaults to
`timeout=900`, so *"a 300s budget can be held for 900"* (the healbot-traps skill). Below ~20 minutes you
will kill working runs.

A forced stop leaves the current iteration uncommitted. That is intentional — the evidence of what
it was doing when it hung is worth more than a clean tree.

### 3.7 Branch and blast radius

- `--worktree` is unusable here (§2 preamble, `gate/GATE.MAP.md`).
- Default branch mode (`gnhf/<slug>`) is correct for (a) and (b): `main` is untouched and the work
  is a reviewable branch of per-iteration commits.
- `--current-branch` only when you have a reason, and never combined with `--push`.
- Commits are **unsigned** by design (README: so signing prompts cannot block the run). If the
  repo ever requires signed commits, that is a conflict to settle before the first run, not at 3am.

---

## 4. Pre-flight checklist

Run every step. Any failure is a stop, not a warning.

```sh
cd ~/Desktop/healbot
```

**1 — gnhf is what you think it is**
```sh
gnhf --version                 # expect 0.1.43
readlink -f "$(command -v gnhf)"
```

**2 — the gate is green, against a base**
```sh
.carryover/verified/venv/bin/python gate/gate.py --base main; echo "gate exit=$?"
# 0 pass · 2 blocked · 3 error. 3 is NOT a pass — a check could not run and its claim is
# unmeasured (gate/GATE.MAP.md). Evidence lands in gate/runs/<timestamp>.json.
```

**3 — the working tree is clean, or gnhf refuses**
```sh
git status --porcelain     # must be EMPTY
```
On 2026-07-31 it was not: TESTED, 12 entries, 2 modified (`.carryover/verified/probe_twin.py`,
`.gitignore`) and 10 untracked, including all of `gate/` and the entire A/B study
(`ab.py`, `run_refusal.py`, `probe_refusal_*.py`, `verify_refusal_*.py`, `studies/`,
`AB-HANDOFF.md`, `docs/REFUSAL-BASELINE.md`). **Commit them; do not stash.** Stashing pulls the live
study's files out from under it, and `git stash -u` on an in-flight run is how you lose a
measurement.

**Re-run this check after step 4, not only before it.** Steps 3 and 4 contradicted each other
until 2026-08-06. `probe_error_state.py` and `probe_focus.py` both open with
`shutil.copyfile(db("retire350"), ...)` (probe_error_state.py:43, probe_focus.py:59) onto
`hb/errorstate.db` and `hb/focus.db`, two files that were then TRACKED, so walking the checklist
in its own documented order dirtied the tree at the last moment and gnhf refused with "Working
tree is not clean" (TESTED 2026-08-05, on the first launch attempt). The recurring diff was one
cell, `project.time_updated`; no session, message or measurement row ever moved. Both files are
now untracked (`.gitignore`), and every other name step 4 writes (`probe_on_grid`,
`controlwiring`, `armdefault`, `armoff`, `armon`, `reqchan`) is ignored as well, so step 4 leaves
the tree clean. Keep the re-check anyway: it is what catches the next probe that writes to a file
still in the corpus.

**4 — the free baseline is real, measured now, not quoted**
```sh
cd .carryover/verified
for p in probe_on_grid probe_error_state probe_focus probe_fleet probe_control_wiring \
         probe_twin probe_headless_arm probe_request_channel probe_turn_predicate \
         probe_turn_growth probe_rig_contract probe_citations; do
  out=$(venv/bin/python $p.py 2>&1); code=$?      # assign first — never `| tail`, see the rig-assertion-discipline skill
  printf '%-26s exit=%s  %s\n' "$p" "$code" "$(printf '%s' "$out" | tail -1)"
done
cd ~/Desktop/healbot
```
Every probe must exit 0; each prints its own floor. Write the actual numbers down — §2(a) flags a documented
disagreement about `probe_turn_growth.py`, and a loop must not be handed an ambiguous baseline.

**5 — the A/B study is idle and its arms are uncorrupted**
```sh
pgrep -fl opencode || echo "no opencode process — good"
ls -la .carryover/verified/hb/ab-refusal-pilot-*.db-wal 2>/dev/null   # any recent mtime = in flight
test ! -e ~/.config/opencode/AGENTS.md && echo "stock arm: no AGENTS.md — good"
ls ~/.agents/skills | wc -l          # record it; ab.py:80 says 18, measured today 16 (see 3.3)
test -e ~/.claude/CLAUDE.md && echo "stock arm: CLAUDE.md present — required, do not remove"
git status --porcelain harness/config/opencode/   # must be EMPTY; that is the harness arm
```
If any refusal DB is being written, **do not launch.** Wait for the run to finish.

**6 — caps and stop conditions are set, and the watchdog is the one you trust**
- [ ] `--max-iterations` set — never unlimited
- [ ] `--max-tokens` set — remembering §1.6, cache reads count in full
- [ ] `--stop-when` set, and understood as agent-self-reported, not enforced (§1.5 #3)
- [ ] `--prevent-sleep on`
- [ ] no `--worktree`, no `--push`
- [ ] gnhf started in the background and `harness/gnhf-watch.sh` handed its `$!`, never gnhf's own
      flags (§3.6). It refuses a non-pid, so a mistake here stops you rather than watching nothing
- [ ] `STALL_MIN` above the slowest legitimate operation, and `COST_MAX` set in **dollars** if this
      run should stop on spend (`BILL_MAX` is refused)
- [ ] `GNHF_TELEMETRY=0`
- [ ] the prompt names its forbidden list explicitly — installs, the four filenames, the A/B
      paths, `hb/*.db` deletion, every paid rig

**7 — decide the permission posture, and write it down (§3.1)**
```sh
cat ~/.gnhf/config.yml 2>/dev/null | grep -A3 agentArgsOverride
```
Default = `--dangerously-skip-permissions`, i.e. no boundary. Anything else = asks become possible,
stdin is ignored, and the watchdog is the only thing that will ever end the run.

**8 — after it exits, before you trust anything**
```sh
git log --oneline main..HEAD
cat .gnhf/runs/<runId>/notes.md
grep -c . .gnhf/runs/<runId>/gnhf.log
.carryover/verified/venv/bin/python gate/gate.py --base main; echo "gate exit=$?"
git status --porcelain harness/config/opencode/   # still empty?
ls ~/.agents/skills | wc -l                       # still the number from step 5?
test ! -e ~/.config/opencode/AGENTS.md && echo "stock arm intact"
du -sh .carryover/verified/hb/project             # 1.8 MB after Phase 12; growth = an install ran
ls .carryover/verified/hb/*.db                    # same set as before, nothing deleted
find . -name 'AGENTS.md' -o -name 'CLAUDE.md' -o -name 'CONTEXT.md' -o -name 'SKILL.md' \
  | grep -v '^./opencode/'                        # must be empty
pgrep -fl claude                                  # nothing orphaned
```

`gnhf` prints a permanent exit summary — branch, elapsed, iterations, token totals, diff stats,
notes/log paths. Read it, but verify against the list above: the summary is gnhf's account of what
it did, and this project's standing rule is that a green run is not evidence that the run happened.

---

## 5. Verification record

What was actually executed to produce this document. No healbot file was touched; no gnhf loop was
started; no model turn was spent by any command below.

| Check | Method | Result |
|---|---|---|
| version / flag surface | `gnhf --version`, `gnhf --help`, `gnhf run --help` | 0.1.43; ten flags; **no subcommands** |
| config bootstrap | ran gnhf under an isolated `HOME` in the scratchpad | `~/.gnhf/config.yml` created with the documented defaults; the real `$HOME` was **not** touched |
| not-a-git-repo guard | ran in an empty scratch dir | exit 1, "must be run inside a Git repository" |
| clean-tree guard | ran in a scratch repo with one modified file | exit 1, "Working tree is not clean" |
| flag validation | `--meteor-frequency 9` | exit 1, "must be between 0 and 5" |
| mutual exclusion | `--worktree --current-branch` | exit 1, "Cannot combine" |
| **all three §2 invocations** | extracted from this file by script, retargeted at a **dirty** scratch repo | all three **parsed their full flag set** and then halted at the clean-tree guard, exit 1 — the intended outcome, and 0 credits. **Recorded 2026-07-31 against the single-command form**, which 2026-08-06 replaced with the two-step form (§3.6). The replacement was parse-checked, not re-executed |
| §2 invocation portability | `bash -n` under `/bin/bash` 3.2.57 **and** `zsh -n` | re-run 2026-08-06 over every block in this file carrying `GNHF=$!`, extracted by script: **4 of 4** (the three §2 recipes and the §3.6 snippet) OK under **both** |
| `gnhf-watch.sh` syntax | `bash -n` | OK. **Re-run 2026-08-06 against `harness/gnhf-watch.sh` as tracked on `wayfinder-adoption`**; the 2026-07-31 result was measured against the scratchpad version this replaced |
| `gnhf-watch.sh` stall detector **and its pid scoping** | **2026-08-06, against the same `wayfinder-adoption` copy.** Two fake runs side by side under one `.gnhf/runs/`: `stall-case`, holding a `run:start` line for pid A and an `iteration-*.jsonl` aged 157 minutes; `bootstrap-case`, holding a `run:start` line for pid B and no iteration file at all. A watchdog started on each pid | A resolved `stall-case`, stopped on *"stalled: no iteration write in 25m"*, killed pid A and exited **2**. B resolved `bootstrap-case`, kept polling and left pid B alone: correctly silent on a run that has written nothing yet, **and** on A's stale file, which is the pid scoping doing its job. The 2026-07-31 row measured the same two legs against the scratchpad script, before run directories were pid-scoped, so this supersedes it rather than repeating it |
| `gnhf-watch.sh` refuses a non-pid | 2026-08-06, three invocations by hand against the tracked script | flags as `$1`, a dead pid, and `BILL_MAX` set each exited **1** with a `FATAL:` line. Transcribed into §3.6 |
| `gnhf-watch.sh` leftover-process report | **2026-08-06**, end to end: the stalled fixture above, plus one process wearing gnhf's documented arg shape standing in for the detached agent, with this machine's interactive Claude Code sessions live alongside it as distractors | the watchdog stopped the pid, exited **2**, and reported **only** the gnhf-shaped process. Not one interactive session reached the report, though several were running throughout. The `--json-schema` half is what discriminates: the first flag alone is the app's too |

The parse check earned its place: it caught the bash 3.2 heredoc defect described in the §2
preamble, which changed the design from inline prompts to prompt files. A spec whose commands were
only eyeballed would have shipped that.

---

## Appendix — what this document does not claim

- **INFERRED:** that `--max-tokens` reliably interrupts a *runaway* iteration. It fires on usage
  events; a long tool-call sequence between events is unbounded. The watchdog is the real bound.
- **INFERRED:** that `SIGTERM` to gnhf always reaps the detached `claude` tree. `terminateClaudeProcess`
  exists and is called, but I did not run a loop to observe it, which is why `gnhf-watch.sh` ends
  with a `pgrep` check and step 8 repeats it.
- **NOT MEASURED:** the actual token cost or dollar cost of any of the three runs in §2. Both the
  `--max-tokens` figures and the `COST_MAX` figures are containment ceilings chosen from
  repo-documented workloads, not predictions.
- **NOT MEASURED:** the `COST_MAX` cap actually firing, or the `SPEND_FAIL_MAX` stop. §5 dates a
  measurement for the stall leg, the pid scoping and the argument refusals; the spend legs have
  none, and no run in this document has been stopped by either. Their arithmetic belongs to
  `harness/gnhf-spend.py`, which carries its own probe in the rig.
- **NOT MEASURED:** whether `--agent opencode` against this repo interacts badly with the A/B
  study's `opencode serve` processes. Both bind local ports and both write session DBs. Until
  someone measures it, **use `--agent claude` and do not run gnhf with the opencode backend while
  the refusal study can start.** SUSPECTED collision, high enough stakes to just avoid.
