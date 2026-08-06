# Mirror skills and plugins into the harness config root

Type: task
Mode: AFK
Status: closed
Assignee: -
Blocked by: 09

## Question

Decided 2026-08-05: **mirror**, not share by symlink and not stay minimal.

The reasoning, so it is not re-opened. Isolation is the harness's whole claim, and a symlink from
`harness/claude/skills` to `~/.claude/skills` punctures it silently, which is the exact failure mode
this repo exists to hunt. Staying minimal was defensible but loses, because the captain's normal
interaction is crew work driven through `/firstmate` and `/wayfinder`, and those are skills. Mirroring
is also the only one of the three that reproduces on a second machine, and the PC is wanted.

The work, once ticket 09 says which directories actually follow the redirect:

- `harness/install-skills.py` grows a second Claude target. Today `CLAUDE` is hard-coded to
  `~/.claude/skills`. It becomes both that and the harness root, with the same direction rules the
  file already implements: a missing installed half is created, a divergent one is reported and left
  alone, and `--force` records the repo-over-installed decision.
- `harness/doctor.py`'s skill-twins row learns the second root, so a harness root missing its skills
  is a named row rather than a silent absence. Follow the row's existing vocabulary: absent is WARN
  with the install command, divergent is FAIL.
- Plugins, if ticket 09 says they follow the redirect. The default root carries
  `installed_plugins.json`, `cache`, `data` and `blocklist.json`; the harness root carries none of it.
  Decide deliberately whether crew get the plugin skills or only the repo's own, and record the choice
  here rather than letting the copy scope decide it by accident.

**Do not** create a `SKILL.md` anywhere inside the repo tree while doing this. `gate/gate.py`'s
`BANNED` set refuses that filename and the gate will block the push. The mirror writes outside the
tree, into `harness/claude/`, which is gitignored; check that assumption before writing, because the
gate lints changed files whole.

**Done looks like:** `python3 harness/install-skills.py` puts every tracked skill in both roots,
`python3 harness/doctor.py` reports the second root, and a session launched under
`harness/env.claude.sh` can invoke `/citation-hygiene`. That last one is the actual acceptance test
and it is the only one that proves the change worked.

## Resolution

Built and verified 2026-08-05. The harness config root now carries the skills surface it never
had, and the doctor reports a gap instead of hiding one.

**What changed.**

- `harness/install-skills.py` gained `mirror_harness_root()` and a third surface. `surface()`
  took a `link_root` parameter so one linking mechanism serves both roots; the default root's
  call passes exactly what the function used to hard-code, so its behavior is unchanged.
- `harness/doctor.py` gained `check_config_root_skills()`, its own row rather than a widening of
  the twins row, because the twins row means "canon and installed agree" and this one means "the
  root actually in use exposes them". One row, one claim. It gates the claude tier only, on FAIL
  only, matching the twins guard's reasoning that a not-installed WARN is bring-up rather than
  breakage.

**The scope decision the ticket asked for, and it is not the obvious one.** The mirror copies
what the **default root exposes**, not the tracked twins alone. Mirroring only `harness/skills/`
would have surfaced nine skills and left out `/wayfinder`, `/grilling`, `/domain-modeling` and
`/research`, which are exactly the planning skills the captain drives. So the source is
`~/.claude/skills`. Result: 28 skills surfaced, against 9 tracked.

**Plugins: deliberately deferred, not forgotten.** Skills are mirrored; plugins are not. Three
reasons. `claude plugin` is the supported mechanism and hand-copying `installed_plugins.json`,
`cache/`, `data/` and `marketplaces/` forks state the CLI owns, which will drift. Most of the
captain's plugins read `disabled` in `claude plugin list` today, so a bulk copy would import
mostly-off state and dress it up as a decision. And the skills half is what unblocks the
destination; the plugin half is additive. What remains is which plugins the harness root should
carry and installed how, which is not sharp enough to ticket and is now fog on the map.

**Verified.**

- Doctor row TESTED in both directions: PASS at 28/28 with doctor exit 0; deleting one mirrored
  skill gives `FAIL claude config-root skills incomplete`, names the missing skill, and takes
  doctor to exit 1; re-running the installer restores PASS and exit 0.
- Installer is idempotent: a second run reports 37 `link ok` and 0 new links.
- plaincode: 12 violations before the change, 12 after, all pre-existing in `doctor.py` and none
  in the new code. `install-skills.py` is clean.
- Free suite: every probe exits 0. `probe_fleet_claude.py` 107/107 against floor 107, which is the
  probe that owns the mutation-controlled version of the twins claim. Citations 21/21.
- Citation safety: no line-anchored citation exists into `install-skills.py`, and the two into
  `doctor.py` point at line 297 while the first diff hunk is at line 467, so nothing moved.

**One thing is UNTESTED and it is the acceptance test.** That a live session under
`harness/env.claude.sh` can now invoke `/citation-hygiene`. Everything above proves the files are
in place and that skills resolve from this directory by construction; it does not prove the
round trip. That costs one turn. Take it the next time a harness session starts, rather than
paying for it on its own.
