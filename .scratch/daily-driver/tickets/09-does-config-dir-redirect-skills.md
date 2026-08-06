# Does CLAUDE_CONFIG_DIR redirect skill resolution

Type: research
Mode: AFK
Status: closed
Assignee: claude-research
Blocked by: -

## Question

Settle one link, because ticket 10 and a large part of the daily-driver story rest on it.

**The question:** when `CLAUDE_CONFIG_DIR` points somewhere other than `~/.claude`, does Claude Code
resolve user skills, agents, commands and plugins from `$CLAUDE_CONFIG_DIR/`, or does it always read
`~/.claude/` for those?

**What is already VERIFIED, so do not re-derive it:**

- `harness/env.claude.sh` sets `CLAUDE_CONFIG_DIR` to `harness/claude`, and its own comment asserts
  the redirect covers "settings, CLAUDE.md, skills, agents, hooks, AND auth/state".
- `harness/claude/` has no `skills/`, no `agents/`, no `commands/`. Its `plugins/` holds only
  `known_marketplaces.json` and an empty `marketplaces`.
- `harness/install-skills.py` hard-codes `~/.claude/skills` with no `CLAUDE_CONFIG_DIR` awareness,
  and `harness/doctor.py`'s skill-twins row names that same default root as the claude surface.
- Nothing anywhere wires skills into the redirected root.

**What is INFERRED and needs settling:** the assertion in that comment. The measurement it cites
covered auth and state, not skills. So the harness may be stripping every skill from every session it
launches, including the four the repo's own `NEXT.md` orders each session to invoke, or it may not.

**Method, primary sources first.** Claude Code's own documentation on `CLAUDE_CONFIG_DIR` and on
skill and plugin resolution order. Follow each claim to the doc that owns it rather than to a
write-up about it.

If the docs do not settle it, one empirical turn does: source `harness/env.claude.sh`, run a headless
`claude` asking it to list its available skills, and compare against the same question asked outside
the harness. That spends, so `/paid-run-protocol` first and the captain authorizes. It is one turn,
inside `NEXT.md`'s few-turns allowance.

**Resolved when** the answer is stated with its evidence tier and its source, and it says which of
`skills`, `agents`, `commands` and `plugins` follow the redirect and which do not. Write the findings
to a markdown file and link it from this ticket rather than pasting it in.

## Resolution

**Yes. Skills and plugins both follow `CLAUDE_CONFIG_DIR`, so a harness session gets neither.**
No API credits spent: documentation reads, binary reads, and one local CLI call.

Findings, with every citation:
[research/09-config-dir-skill-resolution.md](../research/09-config-dir-skill-resolution.md).

The short form:

- **Skills: VERIFIED at source.** The config base is `CLAUDE_CONFIG_DIR ?? join(homedir(),".claude")`,
  and ten call sites build the user skills directory as `join(fn(),"skills")` off that base with no
  fallback to the default root. The `ide` subsystem does add the default root back when the variable
  is set, so the binary demonstrably knows how to write a dual path and does not do it for skills.
- **Plugins: TESTED, free.** `claude plugin list` lists the installed set under the default root and
  prints "No plugins installed" under `harness/claude`.
- **Project scope is not redirected**, deliberately, which is why `/orient` works.
- **Agents and user-level commands: not settled**, and moot on this machine. The counting method that
  settled skills returns zero for them, but it also returns zero for plugins, which are empirically
  redirected, so absence of the pattern proves nothing. `~/.claude/agents` is empty and there is no
  `~/.claude/commands`.

**The consequence is larger than this ticket asked for.** Every session the harness has ever
launched, including every crewmate spawned through `hb-fleet.sh`, has run with no skills and no
plugins. That includes the four `NEXT.md` orders every session to invoke before the matching work.
`install-skills.py` and `doctor.py`'s skill-twins row have been verifying the default root the
harness redirects away from: both correct about that root, both blind to the one in use.

Ticket 10 is unblocked and its scope is confirmed rather than speculative.
