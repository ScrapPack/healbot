# fork/ — the opencode fork overlay

Everything this project contributes to its opencode fork, at the paths it occupies inside that
tree. **17 files against 6,330 upstream ones** — 15 new, 2 modified upstream files — the fork was
never a fork in any meaningful sense, so it no longer gets its own repository.

VERIFIED, and the count above was corrected here: it used to read "against **6,345** upstream
ones". 6,345 is `git ls-tree -r --name-only 509f4c0b1 | wc -l` — the tree size *with the overlay
already in it*. The base tree is 6,330 (`… 7534d23 | wc -l`), and 6,330 + 15 added = 6,345, which
is why the wrong number looked plausible. The **17** is right, from three independent counts:
`git diff --name-status 7534d23 509f4c0b1` lists 17 (15 `A`, 2 `M`), the patch contains 17
`diff --git` headers, and `find fork/packages fork/.opencode -type f` returns 17.

| | |
|---|---|
| Upstream | `https://github.com/sst/opencode` |
| Base commit | `7534d23551f665e65080809975b4ca5c7d63807b` — *"chore: update nix node_modules hashes"* |
| Version at base | **1.18.5** |
| Overlay recorded at | fork branch `healbot` @ `509f4c0b1` — *"phase 7: per-turn gate, RETIRE_HARD deleted, threshold 180,000"* (the relay landed one commit earlier) |
| Exact diff | [`healbot-fork.patch`](healbot-fork.patch) (`git diff 7534d23 509f4c0b1`) — TESTED, and in Phase 11 more strongly than "applies cleanly": in a throwaway worktree at the base, the tree is **6,330** files, the patch holds **17** `diff --git` headers, and `git apply --check` and `git apply` both exit 0. **The byte-identity half of that claim expired — see the correction below.** Applying cleanly would still be true of a patch producing something subtly different from the overlay this repo ships |

**Correction, 2026-08-02.** The row above used to end *"and every one of the 17 overlay files
is byte-identical to `fork/` afterwards"*. That was true when Phase 11 measured it and is
false now, and a fresh-clone walk is what found it: applying the patch to a base checkout
reproduces **15** of the 17 byte-for-byte and leaves two behind — `packages/core/src/session/SESSION.MAP.md`
and `packages/tui/src/feature-plugins/FEATURE-PLUGINS.MAP.md`. TESTED by `cmp` over all 17
in a clone reconstituted exactly as this file prescribes.

The mechanism is this file's own drift mode 2, one level up. The patch was last cut at
`045e416` (Phase 7). Phase 11 (`16ec8e7`) corrected `file:line` citations inside those two
maps and copied each into the local checkout **by hand** — which kept `fork/` and
`opencode/` in agreement, so `probe_twin.py` stayed green on the machine that made the
change, while the patch, a third copy that nothing compares against anything, silently
stopped reproducing the overlay. Both differences are citation text in `.MAP.md` files; all
five code paths in the overlay (`healbot.tsx`, `builtins.ts`, `.opencode/opencode.jsonc`
included) are byte-identical.

**`fork/` is the authority, the patch is the base-relative bootstrap**, so the repair is a
step in the reconstitution below rather than a regenerated patch: regenerating would break
the one provenance this artifact has (the fork branch it was cut from no longer exists as a
repository) to fix two lines of prose. The end state is checked either way —
`harness/doctor.py` compares all 17 and `probe_twin.py` asserts them with a mutation
control, which is how this was found.

## What is here

| Path | What |
|---|---|
| `packages/**/*.MAP.md` (14) | The subsystem maps. Phase 2 output, corrected by Phase 3, the audit, and Phase 7. Indexed from [../HARNESS.md](../HARNESS.md). Phase 7's correction was to `feature-plugins/FEATURE-PLUGINS.MAP.md`, which had described the grid as **unbuilt** ("*To add the grid:* import it and append to the array") and the long-deleted `system/healbot-spike.tsx` as the registered plugin. Both were true when the map was written at `c9323db` and false from fork `26c9316` onward; the map now records that `Healbot` is imported at `builtins.ts:11` and is the last array entry, and it retracts the spike section by name rather than deleting it |
| `packages/tui/src/feature-plugins/system/healbot.tsx` | The control-terminal grid itself. Replaced `healbot-spike.tsx` at `26c9316`; the spike had proved a plugin can register a full-screen route and own the keyboard (PROBE F7) and was retired once the real route landed. Answering a block **from** the grid landed at `25f6f14`, TESTED on `gpt-5.6-sol` ([../docs/VERIFY.md](../docs/VERIFY.md)); retirement and handoff at `392493c`/`b53e0ec`; the error state and the hardening pass in Phase 5 ([../docs/HARDEN.md](../docs/HARDEN.md)). Then it gave retirement up in two steps. At `88f7ce8` it **stopped owning the automatic gate** — that moved to a server plugin so it can run headless ([../docs/HEADLESS.md](../docs/HEADLESS.md)) — and this row used to stop there, saying "the grid keeps manual `x`". At `509f4c0b1` it **stopped owning retirement at all**: `x` no longer retires anything, it writes `metadata: {healbot: {retireRequested: <ms>}}` through `session.update` and the server plugin, now the only implementation of retirement anywhere, performs it. The grid still paints the `RETIRE` border off its own `RETIRE_AT` (`healbot.tsx:57` `RETIRE_AT`, and its three readers `stateOf`, `share`, `retirable`), which is a threshold copy, not an implementation. Consequence worth knowing before you run the fork bare: without the harness plugin loaded, **neither** automatic nor manual retirement works — previously `x` still did. The file got substantially smaller in that change; the duplicate `retire()` and the `handoffDocument` twin are gone. **No byte or line count is quoted** — this row said "24.1 KB, 566 lines" for a file that was already 878 lines, and `HARNESS.md` said 12.8 KB for the same file. `wc` it |
| `packages/tui/src/feature-plugins/builtins.ts` | Upstream file, **two** lines added to register the grid: the import at `:11` and the array entry at `:36`, which is last, so the grid activates last and wins any route-id collision. This row said "one line"; the diff is `+2/-0` |
| `.opencode/opencode.jsonc` | Project config for the fork — the model pin, references, disabled tools |

`builtins.ts` **and** `.opencode/opencode.jsonc` are **modified upstream files** — both exist at
`7534d23` and the overlay edits them; the other 15 paths are new. So neither copy here is
meaningful except against the base commit. That is what the patch is for. (This paragraph used to
name only `builtins.ts`. VERIFIED by `git diff --name-status 7534d23 509f4c0b1`, which marks
exactly those two `M`.)

## Reconstituting a working checkout

The maps cite upstream code by `file:line` and the grid must sit inside `packages/tui` to run,
so working on either needs a real checkout. `opencode/` at the repo root is that checkout and is
**gitignored** — it is derived, not authoritative. (This sentence said "the spike"; that file was
deleted at `26c9316`.)

```sh
git clone https://github.com/sst/opencode opencode
cd opencode
git checkout -b healbot 7534d23
git apply ../fork/healbot-fork.patch
bun install          # bun 1.3.14, matches the repo's packageManager pin
cd ..
cp -R fork/packages/. opencode/packages/     # bring the overlay to CURRENT — see the correction above
cp -R fork/.opencode/. opencode/.opencode/
python3 harness/doctor.py                    # its "fork overlay" row is the check on the two lines above
cd opencode && bun dev                       # runs the TUI from source
```

**Retirement does not work from this checkout alone**, as of `509f4c0b1`. The only implementation
lives in the harness's server plugin, which is not in the overlay; without it, the grid's `x`
writes a request nobody reads and the automatic gate never arms. Load the harness config too —
see [../docs/HEADLESS.md](../docs/HEADLESS.md).

## Drift

This overlay is a snapshot pinned to `7534d23`. Two ways it goes stale:

1. **The checkout moves ahead of the overlay.** Check with:

   ```sh
   root=$(git rev-parse --show-toplevel)
   (cd "$root/fork" && find packages .opencode -type f) | while read -r f; do
     diff -u "$root/fork/$f" "$root/opencode/$f"
   done
   ```

   Re-run the overlay build from the checkout's `HEAD` when they diverge — build from `HEAD`,
   not the working tree, or you will capture someone's in-flight edits.

   **Since Phase 11 this is also an ASSERTION, not only a command somebody remembers.**
   `probe_twin.py` compares all **17** overlay files against the checkout with a mutation check,
   where it previously compared exactly one (`healbot.tsx`). The gap was not hypothetical: Phase 11
   corrected citations inside two of the maps and had to copy each into the checkout by hand, and
   forgetting either would have left the probe green, the overlay right, and the checkout — which
   every rig in the suite actually runs — wrong.

   **Two warnings about this check, both earned.**

   *It cannot see staleness that both copies share.* It compares `fork/` against `opencode/`,
   so it reports what has diverged and nothing else. `FEATURE-PLUGINS.MAP.md` was materially
   wrong — grid described as unbuilt, a deleted file described as registered — in **both** trees
   for months, byte-identical, and this check would have called that clean every time. VERIFIED:
   the repo's `HEAD` copy and the checkout's copy at `88f7ce8cf` compare identical, and both are
   the pre-Phase-7 text. A clean run means "the two trees agree", never "the two trees are right".
   Only re-reading a map against the code it cites catches that, which is drift mode 2 below.

   *The command above replaced one that never ran here.* This block used to prescribe
   `diff -ru fork/packages …/opencode/packages --include='*.MAP.md' --include='healbot.tsx'
   --include='builtins.ts'`. `--include` is GNU diff; macOS ships `Apple diff (based on FreeBSD
   diff)`, which rejects it with a usage message and **exit 2**. TESTED on this machine. Exit 2 is
   *error*, not *differences found* (that is exit 1) — so a caller testing the exit status the
   obvious way read a permanently broken command as permanently dirty, and a caller eyeballing the
   output saw a usage dump instead of a diff. The replacement is POSIX, and it also covers
   `.opencode/opencode.jsonc`, which the include-list silently excluded by living outside
   `packages/`. TESTED: it reports zero differences right now, across all 17 overlay files.

2. **Upstream moves and the `file:line` citations rot.** Every map cites 1.18.5. Re-verify
   before trusting a line number against a newer opencode; the audit
   ([../docs/REVIEW.md](../docs/REVIEW.md)) found citation drift of one or two lines already.

   **This warning stood for eleven phases with nothing behind it, which is why every instance was
   found by hand.** Since Phase 11 it has a check: `probe_citations.py` resolves ~930 citations
   across 25 documents and asserts the file exists, the line exists, and it is not blank. It found
   eight stale — three pointing past the end of `healbot.tsx` by ~140 lines, five landing on blank
   lines, **three of those created by Phases 9 and 10** editing documents that other documents cite
   into. It catches POSITIONAL rot only; a citation landing on a real line that says something else
   is not mechanically checkable and is not claimed. See [../docs/CITE.md](../docs/CITE.md).

## Why this is not a fork repo

It was one, briefly (`ScrapPack/healbot-opencode`), created to get the work off a single disk.
It carried 15,169 upstream commits to back up 17 files, and split the project's artifacts
across two repositories that could not resolve each other's paths — which had already caused a
real error: an auditor working inside the fork concluded `docs/SCAN.md` and `docs/PROBE.md`
"were never committed", because this repo's history is invisible from there, and stamped
UNVERIFIED on 33 correct citations across 7 maps. That retraction is in the maps now.

Nothing here is going back upstream, so the fork relationship bought nothing and cost that.
