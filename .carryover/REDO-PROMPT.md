# Redo prompt — paste into a fresh session rooted at `~/Desktop/healbot`

---

There is an uncommitted change in this project's opencode checkout that implements the
Phase 4 "answer from the grid" feature. It typechecks and lints clean and was derived by
reading source, but **its live verification is invalid and must be redone**. Your job is to
redo the verification properly, then report honestly at the correct evidence tier.

## Where things are

- Project root `~/Desktop/healbot`. Read `HARNESS.md` first — it is the index — then
  `docs/REVIEW.md`, which corrects earlier phases.
- The fork checkout is `~/Desktop/healbot/opencode`. It is gitignored from the healbot repo
  but has its own git history; HEAD is `f819c703`.
- The change: `packages/tui/src/feature-plugins/system/healbot.tsx`, +218/−37, uncommitted.
  A copy is at `~/Desktop/healbot/healbot-answer-in-grid.patch`.
- A pty+pyte test rig is in `~/Desktop/healbot/.carryover/` (`term.py` plus four
  `verify*.py`). **Its results do not count** — see below — but the driver itself is sound
  and saves you rebuilding it. Adapt, don't trust.

## What the change does

Implements build-order step 3 (`PLAN.md:361-363`) — answer a blocked session from the grid
without focusing it — which the phase 4 run had left unbuilt, so the grid could *see* blocks
but not clear them, and `enter` navigated away from the control terminal.

- `a` on a blocked cell docks the session route's own `PermissionPrompt` / `QuestionPrompt`
  below the grid, which keeps rendering above it. This is reuse, as prescribed by
  `FEATURE-PLUGINS.MAP.md:271` step 11 — not a reimplementation.
- `tab` cycles the blocked queue; a block arriving while the grid is open moves the cursor
  onto it, unless you are answering or already sitting on a blocked cell.
- The cold-start reconcile now carries **full request bodies** keyed by session, not just a
  `Set` of ids. Colouring a border needs an id; *rendering* a prompt needs the request.
- Grid bindings moved to `OPENCODE_BASE_MODE` + `enabled: !answering()`. This is load-bearing:
  `mode()` is a require-condition (`keymap.tsx:57-59`), so the previously mode-less bindings
  were live in **every** mode and would have fired underneath the prompts on
  `j/k/h/l/1-9/return/escape`.
- Two defects fixed in passing: `question.rejected` was never subscribed (a rejected
  pre-attach question pinned its cell yellow forever), and a post-reply staleness window
  where the store's live list empties before the async reconcile lands, letting a stale cold
  entry win the fallback and re-render an answered request.

Current gate status: `tsgo --noEmit` exit 0, `oxlint` 0 errors (4 warnings, all pre-existing
patterns in that file).

## Why the previous verification is void

It ran `ollama/gemma4-agentic:q6` through `@ai-sdk/openai-compatible`. Three consequences:

1. **Wrong provider path.** The harness pins `openai/gpt-5.6-sol`, and every load-bearing
   figure in this project — the concurrency result, the 350K retirement threshold, the
   compaction-off hard-error behaviour — was measured on it. Tool-call emission, streaming
   and reasoning parts differ between the native OpenAI path and the compatible shim.
2. **The question path was forced.** The 12B would not call `question` on instruction (its
   own reasoning called the request "a trap" and it went grepping instead), so the turn was
   constrained with `tools: {"*": false, "question": true}`. The path that actually matters
   is the model *choosing* to ask. It was never exercised.
3. **Local inference serializes** on one GPU, so "four concurrent sessions" was not
   concurrent in the sense the exit gate means.

What does survive, being model-independent: grid rendering, the keybinding-mode gating,
`a`/`tab` behaviour, selection-marker movement, and the reply endpoints clearing a block
server-side. Re-confirm them anyway; do not inherit the claims.

## The gate you are trying to clear

`PLAN.md:379-381`: four sessions concurrent, one deliberately blocked on a permission prompt
and **answered from the grid without focusing**, one driven past the retirement threshold and
handed off with continuity intact. The handoff clause is a separate, still-unbuilt piece —
scope yourself to the blocked-permission clause plus the question equivalent.

Assert at least: the block renders as `PERMISSION`/`QUESTION` and is counted in the header;
`a` mounts the prompt *inside* the grid; the grid is still rendered while answering; the
reply clears the block server-side (`GET /permission`, `GET /question` return `[]`); the
answer **reaches the model**, not merely clears the block; the route never changed; and the
other sessions were not stalled. Assert navigation on the `▸` marker's position, not on cell
text — cell text is present regardless of which cell is selected.

## Traps — do not rediscover these

1. **Do NOT set `XDG_DATA_HOME`.** `Global.Path.data` derives from it (`core/src/global.ts:11`)
   and `auth.json` lives there (`auth/index.ts:10`). OpenAI is on **oauth**, so redirecting it
   strands the credentials and `gpt-5.6-sol` fails to resolve. Isolate the database *only*,
   with an absolute `OPENCODE_DB` — `database.ts:44-46` returns it directly, bypassing the
   data dir. This is exactly the mistake that made the previous run reach for a local model.
2. **Do NOT set `OPENCODE_DISABLE_DEFAULT_PLUGINS`.** Those are the provider auth plugins;
   with OpenAI on oauth it produces `ProviderModelNotFoundError`. `harness/env.sh` says so in
   its NOT-SET list.
3. Source the harness for the run: `. ~/Desktop/healbot/harness/env.sh`. It exports
   `XDG_CONFIG_HOME` (the harness config, which is where the `gpt-5.6-sol` pin and
   `compaction.auto=false` live), `OPENCODE_DISABLE_EXTERNAL_SKILLS` and
   `OPENCODE_DISABLE_CLAUDE_CODE`. It does not touch `XDG_DATA_HOME`, which is correct.
4. Run the fork from source, and pass the project directory **positionally** — the instance
   directory comes from the `project` arg (`cli/cmd/tui.ts:77-80`), not from `bun --cwd`:
   `bun run --cwd ~/Desktop/healbot/opencode/packages/opencode --conditions=browser src/index.ts <projectdir> --port <port>`
5. A from-source run resolves the channel to `local`, so it uses `opencode-local.db`, not
   `opencode.db` (`database.ts:48-54`). Do not read an empty session list as a bug.
6. The TUI **cannot attach to an external server** — `--port` means "port to listen on", so it
   always hosts its own. The cold-start reconcile (a client meeting a block that predates it)
   is therefore unreachable today and needs the long-lived `opencode serve` architecture from
   `PLAN.md:335`. Do not burn time trying; note it as untestable.
7. Permission trigger: the default ruleset is `"*": "allow"`, so bash does **not** prompt.
   `external_directory: "ask"` is the reliable trigger (`agent.ts:119-136`) — have a session
   read an absolute path outside the project dir.
8. `question` is `"deny"` by default (`agent.ts:127`), so set `permission: {question: "allow"}`.
   Registration is separately gated on `flags.client` being in `["app","cli","desktop"]`
   (`tool/registry.ts:202`); `OPENCODE_CLIENT` defaults to `"cli"`, so it is registered — this
   settles HARNESS.md's first "Still open" row, and a real question did fire and get answered.
9. `escape` is **destructive** on both prompts — `escapeKey="reject"` (`permission.tsx:406`)
   and question's escape calls `reject()` (`question.tsx:281`). There is no back-out key. The
   footer says `esc reject` for that reason. Decide whether that is acceptable for a control
   terminal, where you may open the panel on the wrong cell.
10. Sessions can be created and prompted over HTTP against the TUI's own server
    (`POST /session`, then `POST /session/{id}/message` with `{parts:[{type:"text",text:…}]}`),
    which is the realistic control-terminal shape: work runs elsewhere, the grid supervises.
    Fire prompts from a thread — that endpoint blocks until the turn completes.

## Report honestly

Classify every claim: VERIFIED (read source, cite file:line), TESTED (ran it), INFERRED,
SUSPECTED. The previous session reported the exit gate as TESTED on the strength of a
local-model run; do not repeat that. If something is not established on `gpt-5.6-sol`, say so.

## Afterwards

Do not commit or push unless asked. If asked, note that the project commits per verified step
with a detailed message, and that `~/Desktop/healbot/fork/` — the overlay that actually ships,
since `opencode/` is gitignored — is stale at `26c9316`, behind `951f2021`, `f819c703` and
this change.

---

*Context this prompt exists: the implementation and its first verification were done from a
session rooted in an unrelated project (`the-union`). No code landed there — verified: HEAD
unchanged, clean status, no files touched — but the scratch rig was namespaced to it and has
been purged. This is the clean redo.*
