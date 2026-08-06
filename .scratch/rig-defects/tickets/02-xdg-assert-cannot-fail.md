# The XDG_DATA_HOME assert in arms.py cannot fail

Type: task
Mode: AFK
Status: open
Assignee: -
Blocked by: -

## Question

[arms.py:255](../../../.carryover/verified/arms.py) asserts:

```
assert "XDG_DATA_HOME" not in env or env["XDG_DATA_HOME"] == os.environ.get("XDG_DATA_HOME"), \
    "this function must never introduce XDG_DATA_HOME (auth.json lives there)"
```

Both disjuncts derive from the same source, so the assert cannot fail. `env` is a plain
`dict(os.environ)` copy, and nothing between the copy and the assert sets or pops `XDG_DATA_HOME`.
The function does mutate `env` first, and this ticket originally described that wrongly: it claimed
the only keys touched were `OPENCODE_DB` and `OPENCODE_CLIENT`. In fact the lines above the assert
pop `XDG_CONFIG_HOME`, `OPENCODE_DISABLE_EXTERNAL_SKILLS` and `OPENCODE_DISABLE_CLAUDE_CODE` and
then set all three, before setting `OPENCODE_DB` and defaulting `OPENCODE_CLIENT`. **None of the
five is `XDG_DATA_HOME`, so the conclusion is unchanged**, but the supporting claim was written
after reading only the five lines above the assert rather than the whole function, and was labelled
VERIFIED on that basis. Corrected 2026-08-05 from a review finding on the push that shipped it.

Given that: if `XDG_DATA_HOME` is absent from `os.environ` it is absent from `env` and the first
disjunct holds; if it is present it is present with the same value and the second holds.
`git log -S'XDG_DATA_HOME' -- arms.py` returns only the commit that introduced it.

The rule it guards is real and worth guarding. `/paid-run-protocol` states it plainly: never set
`XDG_DATA_HOME`, because `auth.json` lives there and OpenAI is on oauth, so isolate the DB only.
The assert simply cannot notice a violation of it.

This is the class `/rig-assertion-discipline` exists for, and it is roughly the eighth found in this
repo. It was raised as an `error` review finding on 2026-07-31 and never acted on.

## Constraints

- **Invoke `/rig-assertion-discipline` before touching this.** It is the skill written from the
  previous seven.
- Do not delete the assert and call it done. The rule is real; an unguarded real rule is a
  regression, not a cleanup.
- The repair must be TESTED in both directions: red when the rule is violated, green when it is not.
  An assertion that cannot fail is exactly what a green run does not distinguish from a correct one.

## The shape of the repair

The assert needs a reference that is independent of the thing it checks. Capture the value from
`os.environ` BEFORE the copy is built and mutated, then assert the copy against that captured value
rather than against a live re-read of the same source. The mutation test is then trivial: insert an
`env["XDG_DATA_HOME"] = "/tmp/x"` before the assert and confirm it fires.

**Done looks like:** the assert can fail, demonstrated by a deliberate violation that trips it, and
passes on the real path. Recorded wherever this repo records the previous seven.
