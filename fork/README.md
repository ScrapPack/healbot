# fork/ — the opencode fork overlay

Everything this project contributes to its opencode fork, at the paths it occupies inside that
tree. **17 files against 6,345 upstream ones** — the fork was never a fork in any meaningful
sense, so it no longer gets its own repository.

| | |
|---|---|
| Upstream | `https://github.com/sst/opencode` |
| Base commit | `7534d23551f665e65080809975b4ca5c7d63807b` — *"chore: update nix node_modules hashes"* |
| Version at base | **1.18.5** |
| Overlay recorded at | fork branch `healbot` @ `7e802c6` |
| Exact diff | [`healbot-fork.patch`](healbot-fork.patch) (`git diff 7534d23 7e802c6`) — TESTED: applies cleanly to the base, re-checked in a throwaway worktree |

## What is here

| Path | What |
|---|---|
| `packages/**/*.MAP.md` (14) | The subsystem maps. Phase 2 output, corrected by Phase 3 and the audit. Indexed from [../HARNESS.md](../HARNESS.md) |
| `packages/tui/src/feature-plugins/system/healbot.tsx` | The control-terminal grid itself. Replaced `healbot-spike.tsx` at `26c9316`; the spike had proved a plugin can register a full-screen route and own the keyboard (PROBE F7) and was retired once the real route landed. Answering a block **from** the grid landed at `25f6f14`, TESTED on `gpt-5.6-sol` ([../docs/VERIFY.md](../docs/VERIFY.md)); retirement and handoff at `392493c`/`b53e0ec`; the error state and the hardening pass in Phase 5 ([../docs/HARDEN.md](../docs/HARDEN.md)). **No byte or line count is quoted** — this row said "24.1 KB, 566 lines" for a file that was already 878 lines, and `HARNESS.md` said 12.8 KB for the same file. `wc` it |
| `packages/tui/src/feature-plugins/builtins.ts` | Upstream file, one line added to register the grid |
| `.opencode/opencode.jsonc` | Project config for the fork — the model pin, references, disabled tools |

`builtins.ts` is a **modified upstream file**, so the copy here is only meaningful against the
base commit. That is what the patch is for.

## Reconstituting a working checkout

The maps cite upstream code by `file:line` and the spike must sit inside `packages/tui` to run,
so working on either needs a real checkout. `opencode/` at the repo root is that checkout and is
**gitignored** — it is derived, not authoritative.

```sh
git clone https://github.com/sst/opencode opencode
cd opencode
git checkout -b healbot 7534d23
git apply ../fork/healbot-fork.patch
bun install          # bun 1.3.14, matches the repo's packageManager pin
bun dev              # runs the TUI from source
```

## Drift

This overlay is a snapshot pinned to `7534d23`. Two ways it goes stale:

1. **The checkout moves ahead of the overlay.** Check with:

   ```sh
   diff -ru fork/packages "$(git rev-parse --show-toplevel)"/opencode/packages \
     --include='*.MAP.md' --include='healbot.tsx' --include='builtins.ts'
   ```

   Re-run the overlay build from the checkout's `HEAD` when they diverge — build from `HEAD`,
   not the working tree, or you will capture someone's in-flight edits.

2. **Upstream moves and the `file:line` citations rot.** Every map cites 1.18.5. Re-verify
   before trusting a line number against a newer opencode; the audit
   ([../docs/REVIEW.md](../docs/REVIEW.md)) found citation drift of one or two lines already.

## Why this is not a fork repo

It was one, briefly (`ScrapPack/healbot-opencode`), created to get the work off a single disk.
It carried 15,169 upstream commits to back up 17 files, and split the project's artifacts
across two repositories that could not resolve each other's paths — which had already caused a
real error: an auditor working inside the fork concluded `docs/SCAN.md` and `docs/PROBE.md`
"were never committed", because this repo's history is invisible from there, and stamped
UNVERIFIED on 33 correct citations across 7 maps. That retraction is in the maps now.

Nothing here is going back upstream, so the fork relationship bought nothing and cost that.
