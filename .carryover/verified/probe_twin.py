"""Do the two retirement implementations agree? — FREE, no server, no model turn.

Phase 6 moved AUTOMATIC retirement out of `healbot.tsx` and into the server plugin
`harness/config/opencode/plugin/auto-retire.ts`, because a `createEffect` in a route component
cannot run headless. Manual retirement (`x`) stayed in the grid, because an operator retiring a
session early is a real feature and it is TESTED.

That leaves TWO implementations of the same handoff, in two processes, in two languages' worth of
distance from each other — and they must not diverge. If they do, a successor gets a different
briefing depending on whether a human pressed a key or a threshold fired, which is exactly the
class of silent divergence this project keeps catching in itself. The two copies cannot share a
module: the harness config directory is not part of the fork's workspace, and the fork checkout is
derived and gitignored, so neither tree can import the other without a path that breaks on any
layout but this one.

So the guard is a test instead of a type. This is the cheapest test in the suite and the one most
likely to catch a real regression, because the failure it guards against is *editing one and
forgetting the other* — which is invisible at runtime, invisible to tsgo, and only shows up as a
successor that was briefed slightly wrong.

ASSERTION DISCIPLINE. Every comparison here is followed by a MUTATION CHECK: the same predicate is
re-run against a deliberately corrupted copy and REQUIRED to fail. Without that, "the two files
agree" is indistinguishable from "my extractor returned nothing twice".
"""

import os
import re
import sys

SP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SP)
import rig  # noqa: E402

GRID = f"{rig.HEALBOT}/opencode/packages/tui/src/feature-plugins/system/healbot.tsx"
PLUGIN = f"{rig.HEALBOT}/harness/config/opencode/plugin/auto-retire.ts"
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


def document_strings(source):
    """Every double-quoted string literal inside `function handoffDocument(...)`.

    Scoped to that function rather than the whole file on purpose: the two files share almost no
    other prose, and comparing whole files would drown the signal. Brace-matched from the opening
    `{` so it stops at the real end of the function.
    """
    start = source.find("function handoffDocument(")
    if start == -1:
        return None
    brace = source.find("{", source.find(")", start))
    if brace == -1:
        return None
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                body = source[brace : i + 1]
                break
    else:
        return None
    # Strip comments first — both copies carry (differently worded) rationale comments, and a
    # comment is not part of the document the successor receives.
    body = re.sub(r"//[^\n]*", "", body)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    return re.findall(r'"((?:[^"\\]|\\.)*)"', body)


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
r.check("auto-retire.ts declares a RETIRE_AT default", plugin_at is not None, str(plugin_at))
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
# 3. THE HANDOFF DOCUMENT. The thing the successor actually reads.
# ---------------------------------------------------------------------------------------------
grid_doc = document_strings(grid)
plugin_doc = document_strings(plugin)
r.check("healbot.tsx has a handoffDocument", bool(grid_doc), f"{len(grid_doc or [])} literals")
r.check("auto-retire.ts has a handoffDocument", bool(plugin_doc), f"{len(plugin_doc or [])} literals")
r.check(
    "the handoff documents are IDENTICAL, literal for literal",
    bool(grid_doc) and grid_doc == plugin_doc,
    "same headings, same ordering rule, same fallbacks"
    if grid_doc == plugin_doc
    else f"first difference: {next((f'{a!r} != {b!r}' for a, b in zip(grid_doc or [], plugin_doc or []) if a != b), 'length differs')}",
)
# MUTATION CHECK, twice — once for a changed heading, once for a DROPPED line. A comparison that
# only catches edits but not deletions would miss the likelier mistake.
r.check(
    "mutation check: a reworded heading IS detected",
    document_strings(grid.replace("## Outstanding work — do this", "## TODO", 1)) != plugin_doc,
)
r.check(
    "mutation check: a DROPPED line IS detected",
    document_strings(grid.replace('    "",\n    "## Outstanding work — do this",', '    "",', 1)) != plugin_doc,
)

# ---------------------------------------------------------------------------------------------
# 4. The load-bearing sentinel. `verify_handoff.py` asserts continuity by looking for the
#    predecessor's first message inside the "## Original instruction" section, and the demotion
#    line below it is what stops a successor obeying stale sequencing (TESTED: without it a
#    successor read "do only the first, leave the rest pending" and replied "No further work
#    performed"). Both are behaviour, not decoration.
# ---------------------------------------------------------------------------------------------
for phrase in (
    "## Original instruction, for context only",
    "## Outstanding work — do this",
    "outstanding list below wins.",
):
    r.check(
        f"both copies carry {phrase!r}",
        phrase in grid and phrase in plugin,
        f"grid={phrase in grid} plugin={phrase in plugin}",
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
    "the grid still owns MANUAL retirement",
    "healbot.retire" in grid and "const retire = async" in grid,
    "`x` is the operator's override and stays",
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
    "auto-retire.ts exports only functions",
    bool(exports) and set(exports) == fn_names,
    f"exports={exports} functions={sorted(fn_names)}",
)
r.check(
    "…and it is registered in the harness config",
    "./plugin/auto-retire.ts" in read(f"{rig.HEALBOT}/harness/config/opencode/opencode.jsonc"),
    "an unregistered plugin is a file, not a guard",
)

sys.exit(0 if r.summary() else 1)
