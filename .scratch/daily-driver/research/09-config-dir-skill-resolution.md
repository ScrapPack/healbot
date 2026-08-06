# Does CLAUDE_CONFIG_DIR redirect skill and plugin resolution

Research findings for ticket 09. Claude Code 2.1.220, native build, commit `4073f59596e2`,
resolved from `~/.local/share/claude/versions/2.1.220`. Investigated 2026-08-05. No API credits
spent: every check below is a documentation read, a binary read, or a local CLI call.

## Answer

**Yes for skills and plugins. A session under `harness/env.claude.sh` gets neither.**

| Subsystem | Follows `CLAUDE_CONFIG_DIR`? | Tier |
|---|---|---|
| skills | yes | VERIFIED at source |
| plugins | yes | TESTED, and it is the free empirical proof |
| agents | not settled | see limits |
| commands (user level) | not settled, moot here | see limits |
| commands (project level) | **no**, deliberately | TESTED |

## Evidence

### The config directory base is `CLAUDE_CONFIG_DIR ?? ~/.claude`

Two independent constructions in the binary, both reading the variable with the home directory as
fallback:

```js
let u = n?.CLAUDE_CONFIG_DIR ?? process.env.CLAUDE_CONFIG_DIR,
    d = u ?? aw.join(eSr.homedir(), ".claude")     // then reads .credentials.json from d
```

```js
aw.join(gt.CLAUDE_CONFIG_DIR ?? aw.join(eSr.homedir(), ".claude"), "projects")
```

A dedicated getter returns the raw variable, and the minified `fn()` is the resolved base used
across subsystems, for example `m_e.join(fn(), "teams")`:

```js
function vkl(){return process.env.CLAUDE_CONFIG_DIR}
function RAt(){return m_e.join(fn(),"teams")}
```

### Skills are built on that base, with no fallback to the default root

Ten call sites construct the user skills directory as `join(fn(), "skills")`. The only literal
`.claude/skills` string in the binary is the display form `~/.claude/skills`, not a path
construction.

The contrast that makes this conclusive: the `ide` subsystem searches the redirected directory
**and then adds the default root back**, explicitly and only when the variable is set.

```js
function _co(){
  let e=[q7r.join(fn(),"ide")];
  if(Z.CLAUDE_CONFIG_DIR) e.push(q7r.join(Ywu.homedir(),".claude","ide").normalize("NFC"));
  ...
```

Skills get no such second path. So the redirect is total for skills by construction, and the
codebase demonstrably knows how to write the dual-path form when it wants one.

### Plugins, tested directly and for free

`claude plugin list` is a local operation that reads the installed-plugin state and makes no model
call. Run under each root from the same shell:

```
$ claude plugin list
Installed plugins:
  ❯ clangd-lsp@claude-plugins-official ...
  ❯ claude-md-management@claude-plugins-official ...
  ❯ code-review@claude-plugins-official ...
  ❯ code-simplifier@claude-plugins-official ...
  (continues)

$ CLAUDE_CONFIG_DIR=<repo>/harness/claude claude plugin list
No plugins installed. Use `claude plugin install` to install a plugin.
```

That is the empirical half of the answer and it needed no spend. It also independently corroborates
the source reading, because plugins are how a large share of the skill surface arrives.

### The official documentation does not settle it, and says so by omission

Claude Code's skills documentation gives personal skills as `~/.claude/skills/<skill-name>/SKILL.md`
and never mentions the config directory or `CLAUDE_CONFIG_DIR`. The settings documentation does not
document `CLAUDE_CONFIG_DIR` at all. The variable is nonetheless real and load-bearing: it appears
throughout the binary, and the CLI's own error strings reference it, for example *"ensure the
subprocess CLAUDE_CONFIG_DIR matches the parent"*. Treat the docs' `~/.claude/skills` as the
default-case shorthand it is, not as a hard-coded path.

### Project scope is deliberately not redirected

`harness/env.claude.sh` states this as an intentional keep, and it is confirmed live: `/orient`,
which lives at `.claude/commands/orient.md` in this repo, registers as an available skill in a
session on this repo. Claude Code's own documentation states that custom commands have merged into
skills and that `.claude/commands/deploy.md` and `.claude/skills/deploy/SKILL.md` both produce
`/deploy`.

## Limits of this pass

**Agents and user-level commands are not settled.** Counting `join(fn(), "<name>")` sites returns
zero for `agents`, `commands` and `plugins`, yet plugins are empirically redirected, so those paths
are built through some other construction and the counting method cannot see them. Absence of the
pattern is therefore not evidence of absence of the redirect. Both are moot on this machine
regardless: `~/.claude/agents` is empty and there is no `~/.claude/commands` directory.

**The skills conclusion is VERIFIED at source, not TESTED live.** The remaining check is one
session under the harness env asked to invoke a skill that exists only in the default root. That
costs one turn. Given the plugin result and the source reading agree, it is confirmation rather
than discovery, and ticket 10's acceptance test covers it anyway.

## What this means

`harness/env.claude.sh` sets `CLAUDE_CONFIG_DIR` to `harness/claude`, which has no `skills/`
directory and a `plugins/` holding only `known_marketplaces.json` and an empty `marketplaces`. So
**every session the harness has ever launched, including every crewmate spawned through
`hb-fleet.sh`, has run with no skills and no plugins.**

That includes the four skills `NEXT.md`'s prompt block orders every session to invoke before the
matching work: `/rig-assertion-discipline`, `/citation-hygiene`, `/paid-run-protocol` and
`/healbot-traps`. A crewmate instructed to invoke them could not have, and would have had no way to
report that beyond the slash command not existing.

It also means `harness/install-skills.py` and `harness/doctor.py`'s skill-twins row have been
verifying skills at `~/.claude/skills`, a root the harness redirects away from. The installer and
the doctor were both correct about the default root and both blind to the one the harness uses.

This is a sufficient mechanical explanation for the captain's "I don't know how to operate within
the harness": the harness has been strictly less capable than stock Claude Code, and no amount of
learning would have closed that.
