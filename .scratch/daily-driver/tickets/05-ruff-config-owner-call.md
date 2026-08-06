# The ruff config owner call

Type: grilling
Mode: HITL
Status: open
Assignee: -
Blocked by: -

## Question

The repo pins no ruff configuration anywhere, so the gate's lint verdict is whatever the installed
ruff version defaults to and differs by machine. Recorded in `NEXT.md`'s open-items section from the
Windows bring-up, 2026-08-05.

Why it belongs on this map rather than in the build backlog: a daily driver hits the gate on every
push. A lint verdict that differs by machine is a gate that blocks work for a reason the captain
cannot reproduce, and the Windows bring-up already had to push with `--no-verify` partly because of
it. That is a direct tax on using this as the daily workflow.

The measured conflict, and it is not hypothetical: under the config-less invocation ruff calls the
`# noqa: E402` in `probe_citations.py` unused and offers to delete it, but under the ruleset
`docs/PLAINCODE.md` documents, E402 fires on that exact line. Running `ruff --fix` there would strip
a directive the documented standard needs.

The decision, which is the owner's:

- Pin a root `ruff.toml` matching `docs/PLAINCODE.md`. This makes the gate reproducible across
  machines, and it silently arms plaincode gate enforcement, which has deliberately not been flipped.
  Those two consequences arrive together and that is the whole difficulty.
- Pin a root `ruff.toml` that is deliberately narrower than the plaincode ruleset, so reproducibility
  arrives without enforcement.
- Pin nothing, and record that the gate's lint row is machine-dependent by design.

Do not resolve this by running `ruff --fix` anywhere. That is the one move already known to be wrong.
