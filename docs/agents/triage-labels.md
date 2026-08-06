# Triage labels

The skills speak in five canonical triage roles. This repo has no label system, because its
tracker is markdown files. Each role is the value of a `Status:` line in the ticket's header
block.

| Role in mattpocock/skills | `Status:` value here | Meaning |
|---|---|---|
| `needs-triage` | `needs-triage` | a human needs to evaluate this |
| `needs-info` | `needs-info` | waiting on the reporter |
| `ready-for-agent` | `ready-for-agent` | fully specified, an AFK agent can pick it up cold |
| `ready-for-human` | `ready-for-human` | needs human implementation |
| `wontfix` | `wontfix` | will not be actioned |

When a skill says "apply the AFK-ready triage label", set `Status: ready-for-agent`.

## Wayfinder tickets use a different `Status:` vocabulary

A `/wayfinder` ticket is `open` or `closed` and carries its own `Mode: HITL|AFK` line, because a
map's ticket is a decision to resolve rather than an issue to triage. The two vocabularies do not
mix and they never share a directory: triage issues live in `.scratch/<effort>/issues/`, wayfinder
tickets in `.scratch/<effort>/tickets/`. See `issue-tracker.md`.

## `ready-for-agent` has a specific meaning under `/firstmate`

An AFK crewmate sees none of the first mate's context, so the brief is its entire world. A ticket
marked `ready-for-agent` must therefore be self-contained: objective, constraints, what done looks
like, how to report. A ticket that only makes sense to someone who was in the conversation is not
`ready-for-agent` no matter how clear it reads to its author.
