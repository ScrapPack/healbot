"""Is there still exactly ONE implementation of retirement? — FREE, no server, no model turn.

Phase 6 moved AUTOMATIC retirement out of `healbot.tsx` into the server plugin
`harness/config/opencode/plugin/healbot.ts`, because a `createEffect` in a route component cannot
run headless. Manual retirement (`x`) stayed in the grid, so there were TWO implementations of the
same handoff in two processes with no shared lock. This probe used to be the guard on that
duplication, comparing the two `handoffDocument`s.

PHASE 7 DELETED THE DUPLICATION, so this probe changed job. It no longer compares two documents.
It asserts there is only one — and guards the small, typed-nothing coupling that replaced it.

WHY THE JOB CHANGED. Two findings, both from the Phase 6 review:

  1. The duplication was never safely guarded. The old `document_strings()` extractor (deleted
     with the comparison it served) matched only DOUBLE-QUOTED
     literals, and every line of the document that renders a VARIABLE is a template literal
     (`` `- [ ] ${todo.content}` ``, `` `- ${f}` ``). TESTED by mutating the grid against an
     untouched plugin: it MISSED `- [ ] ` -> `- [x] `, `- [ ] ` -> `* `, a changed file-bullet
     prefix, `slice(0, 2000)` -> `slice(0, 200)`, `files.length > 0` -> `> 3`, dropping
     `input.objective?.trim() ||`, `open.length > 0` -> `>= 0`, and a dropped `.trim()`. It caught
     one thing, `lines.join("\n")`. Both its mutation checks mutated a double-quoted heading —
     the one class of thing the extractor already saw — so they demonstrated the machinery without
     exercising the gap.
  2. The duplication was also a live race. `x` ran a full `retire()` in the TUI while the plugin
     ran another in the server; Phase 6 called the window "narrowed to one request" by a re-read
     before archiving, and the review showed the re-read narrows nothing, because it runs AFTER the
     successor is created and seeded.

Both have one cause — two writers — so Phase 7 removed one. `x` now writes
`metadata: {healbot: {retireRequested: <ms>}}` and the plugin performs the retirement. A successor
is briefed identically however retirement was triggered, because only one thing can brief it.

WHAT IS LEFT TO GUARD, and it is the point of this file now:

  - `RETIRE_AT` is still duplicated, deliberately: the grid needs the number to paint `RETIRE`,
    `N to retire` and the per-cell share, and cannot import it. It is a NUMBER, so it compares
    exactly — this is the duplication that was always safe to test and still is.
  - THE REQUEST CHANNEL is the new coupling and the new risk. The grid writes a metadata key and
    the plugin reads it, with no shared type, no import and no compiler between them. Rename it on
    one side and `x` silently stops working: no error, no log, the cell just never retires. That
    is the same failure shape as the old divergence, so it gets the same treatment.
  - The grid must contain NO second implementation. Asserted directly, so re-adding one is a test
    failure rather than a slow rediscovery.

ASSERTION DISCIPLINE. Every comparison is followed by a MUTATION CHECK: the same predicate re-run
against a deliberately corrupted copy and REQUIRED to fail. Without that, "the two files agree" is
indistinguishable from "my extractor returned nothing twice". Absence checks get the inverse — a
corrupted copy that SHOULD trip them, required to trip.
"""

import os
import re
import sys

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import rig  # noqa: E402

GRID = f"{rig.HEALBOT}/opencode/packages/tui/src/feature-plugins/system/healbot.tsx"
PLUGIN = f"{rig.HEALBOT}/harness/config/opencode/plugin/healbot.ts"
OVERLAY = f"{rig.HEALBOT}/fork/packages/tui/src/feature-plugins/system/healbot.tsx"


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def default_of(source, name):
    """The numeric default in `const NAME = Math.max(1, Number(process.env[...]) || 256_000)`.

    Matches the literal with underscores intact, then strips them — `256_000` and `256000` are
    the same number to TypeScript and must be the same number here, or the check would report a
    difference in formatting as a difference in behaviour.
    """
    m = re.search(rf"const\s+{name}\s*=.*?\|\|\s*([\d_]+)", source, re.S)
    return int(m.group(1).replace("_", "")) if m else None


r = rig.Results()

grid = read(GRID)
plugin = read(PLUGIN)

# ---------------------------------------------------------------------------------------------
# 0. The overlay and the checkout are the same file. `fork/` is what this repo ships; `opencode/`
#    is derived and gitignored. Editing one and testing the other is a way to prove nothing.
# ---------------------------------------------------------------------------------------------
overlay = read(OVERLAY)
r.check(
    "the fork overlay and the checkout hold the same healbot.tsx",
    overlay == grid,
    "otherwise this probe reads one file and the running TUI uses another",
)

# ---------------------------------------------------------------------------------------------
# 1. The soft gate. RETIRE_AT is read by BOTH: the plugin fires on it, the grid paints `RETIRE`
#    and counts `N to retire` off it. Disagree and the border says one thing while the guard does
#    another — the grid would show a calm cell for a session the plugin is about to retire.
# ---------------------------------------------------------------------------------------------
grid_at = default_of(grid, "RETIRE_AT")
plugin_at = default_of(plugin, "RETIRE_AT")
r.check("healbot.tsx declares a RETIRE_AT default", grid_at is not None, str(grid_at))
r.check("healbot.ts (plugin) declares a RETIRE_AT default", plugin_at is not None, str(plugin_at))
r.check(
    "the two RETIRE_AT defaults AGREE",
    grid_at is not None and grid_at == plugin_at,
    f"grid {grid_at} vs plugin {plugin_at}",
)
# MUTATION CHECK. If the extractor silently returned None twice, the equality above would still
# be False-y in a way that looks like a real comparison; and if it returned a constant, the
# comparison could never fail. Corrupt one side and require a difference.
mutated_at = default_of(grid.replace("|| 256_000", "|| 999_000", 1), "RETIRE_AT")
r.check(
    "mutation check: a changed RETIRE_AT default IS detected",
    mutated_at is not None and mutated_at != plugin_at,
    f"mutated grid reads {mutated_at}",
)

# ---------------------------------------------------------------------------------------------
# 2. Both env var names, spelled identically. `fleet.sh` sources `env.sh` once and exports, so
#    server and client read the SAME variables — but only if both spell them the same way.
# ---------------------------------------------------------------------------------------------
for var in ("HEALBOT_RETIRE_AT",):
    r.check(
        f"both files read {var}",
        var in grid and var in plugin,
        f"grid={var in grid} plugin={var in plugin}",
    )
# The hard gate and the kill switch now live ONLY in the plugin — the grid no longer fires, so it
# has no use for either. Asserted so that re-adding a stale copy to the grid is a test failure.
r.check(
    "HEALBOT_RETIRE_HARD is the plugin's alone",
    "HEALBOT_RETIRE_HARD" in plugin and "HEALBOT_RETIRE_HARD" not in grid,
    "a second copy in the grid would be a threshold nothing reads",
)
r.check(
    "HEALBOT_AUTO_RETIRE is the plugin's alone",
    "HEALBOT_AUTO_RETIRE" in plugin and "HEALBOT_AUTO_RETIRE" not in grid,
    "the grid must not gate anything on a switch it no longer honours",
)

# ---------------------------------------------------------------------------------------------
# 3. ONE IMPLEMENTATION. The grid must not carry a handoff document or a retirement flow at all.
#    Phase 7 deleted both; this is what stops them growing back.
# ---------------------------------------------------------------------------------------------
r.check(
    "healbot.ts (plugin) HAS the handoff document — it is the only implementation",
    "function handoffDocument(" in plugin,
    "if this is gone, nothing briefs a successor",
)
grid_code = re.sub(r"/\*.*?\*/", "", grid, flags=re.S)
grid_code = re.sub(r"//[^\n]*", "", grid_code)
r.check(
    "the grid has NO handoffDocument — the twin is gone, not merely synchronised",
    "handoffDocument" not in grid_code,
    "two copies of prose that IS behaviour is the divergence this probe used to chase",
)
# MUTATION CHECK on an ABSENCE assertion. An absence check passes trivially if the extractor is
# looking at the wrong text — e.g. if comment-stripping ate the whole file. Re-run the same
# predicate against a copy that DOES contain the symbol and require it to trip.
r.check(
    "mutation check: a re-added handoffDocument IS detected",
    "handoffDocument"
    in re.sub(r"//[^\n]*", "", re.sub(r"/\*.*?\*/", "", grid + "\nfunction handoffDocument() {}\n", flags=re.S)),
    "proves the absence check above is reading real code, not an empty string",
)
r.check(
    "the grid runs no spawn/seed/archive of its own",
    not any(k in grid_code for k in ("session.create(", "promptAsync(", "time: { archived:")),
    "retirement is the plugin's; the grid only asks for it",
)

# ---------------------------------------------------------------------------------------------
# 4. THE REQUEST CHANNEL. The grid writes it, the plugin reads it, and nothing type-checks the
#    pair. Both halves are asserted against the SAME literals, so a rename on either side fails
#    here instead of silently disabling `x`.
#
#    Shape, verified against the route: PATCH /session/{id} accepts `metadata`
#    (httpapi/groups/session.ts:51 -> handlers/session.ts:191-192), which reaches
#    Session.setMetadata (session.ts:763) -> the shared patch(), which publishes
#    SessionV1.Event.Updated with the whole session (session.ts:748). The plugin's `event` hook
#    already receives every event for its directory, so no endpoint is registered anywhere.
# ---------------------------------------------------------------------------------------------
r.check(
    "the plugin declares the request key",
    'const REQUEST_KEY = "healbot"' in plugin,
    "the name the grid has to write",
)
r.check(
    "the plugin reads the request marker",
    'retireRequested' in plugin and "function requestedAt(" in plugin,
    "reader half of the channel",
)
r.check(
    "the grid WRITES that exact key and marker",
    "healbot:" in grid_code and "retireRequested" in grid_code,
    "writer half — a rename on either side silently stops `x` retiring anything",
)
r.check(
    "the grid asks via session.update metadata, not by retiring",
    "metadata: { healbot: { retireRequested:" in grid_code,
    "the whole client side of retirement is this one write",
)
# MUTATION CHECK. Corrupt the grid's key and require the agreement predicate to fail — otherwise
# `"retireRequested" in both` is just asserting that a common English-ish string exists twice.
def channel_agrees(writer, reader):
    """The exact predicate the two checks above rest on, factored out so it can be mutated.

    Written as a function on purpose: a mutation check that re-implements the predicate inline
    proves nothing about the predicate that actually runs.
    """
    return "retireRequested" in writer and "healbot:" in writer and "retireRequested" in reader


r.check(
    "the request channel agrees end to end",
    channel_agrees(grid_code, plugin),
    "same predicate the mutation checks below corrupt",
)
r.check(
    "mutation check: renaming the marker in the GRID IS detected",
    not channel_agrees(grid_code.replace("retireRequested", "retireWanted"), plugin),
    "a writer-side rename must fail this probe, not silently disable `x`",
)
r.check(
    "mutation check: renaming the marker in the PLUGIN IS detected",
    not channel_agrees(grid_code, plugin.replace("retireRequested", "retireWanted")),
    "and a reader-side rename too — the coupling has two ends and both are untyped",
)

# ---------------------------------------------------------------------------------------------
# 5. Exactly one owner of the automatic gate. If the grid still had its own trigger, an operator
#    pressing `x` and the plugin firing would each spawn a successor for the same session.
# ---------------------------------------------------------------------------------------------
r.check(
    "the grid no longer owns an automatic trigger",
    "AUTO_RETIRE" not in re.sub(r"/\*.*?\*/", "", grid, flags=re.S),
    "only the plugin may fire on the gate",
)
r.check(
    "the grid still BINDS `x` — the operator's override survives, as a request",
    "healbot.retire" in grid and "const retire = async" in grid,
    "the keybinding and its handler stay; only the implementation behind them moved",
)

# ---------------------------------------------------------------------------------------------
# 6. The plugin file must export ONLY functions. `getLegacyPlugins` (plugin/index.ts:95-108)
#    iterates Object.values(mod) and throws `TypeError: Plugin export is not a function` on the
#    first export that is not one — so a single exported constant disables the whole guard, at
#    load time, in a log line nobody reads.
# ---------------------------------------------------------------------------------------------
exports = re.findall(r"^export\s+(?:const|let|var|function|class)\s+(\w+)", plugin, re.M)
fn_exports = re.findall(r"^export\s+const\s+(\w+)\s*=\s*async|^export\s+(?:async\s+)?function\s+(\w+)", plugin, re.M)
fn_names = {a or b for a, b in fn_exports}
r.check(
    "healbot.ts (plugin) exports only functions",
    bool(exports) and set(exports) == fn_names,
    f"exports={exports} functions={sorted(fn_names)}",
)
r.check(
    "…and it is registered in the harness config",
    "./plugin/healbot.ts" in read(f"{rig.HEALBOT}/harness/config/opencode/opencode.jsonc"),
    "an unregistered plugin is a file, not a guard",
)

sys.exit(0 if r.summary() else 1)
