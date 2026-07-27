# Carryover — NOT verified work, pending redo

These came out of a session rooted in the WRONG project (the-union). They are kept only so
the rig does not have to be rebuilt from scratch. Two things must change before any result
from them counts:

1. **Model.** They ran `ollama/gemma4-agentic:q6` through `@ai-sdk/openai-compatible`. The
   harness pins `openai/gpt-5.6-sol`, and every load-bearing figure in this project
   (concurrency, the 350K retirement threshold, compaction-off) was measured on it. Re-run
   under `harness/env.sh`.
2. **The question path was FORCED.** `tools: {"*": false, "question": true}` was needed
   because the 12B would not call `question` on instruction. The path that matters is the
   model *choosing* to ask. Drop the forcing and let it happen.

Also: local inference serializes on one GPU, so "four concurrent sessions" was not
concurrent in the sense the exit gate means.

**Redo done.** See [`verified/`](verified/README.md) for the rig that counts and
[`../docs/VERIFY.md`](../docs/VERIFY.md) for the report. The implementation landed at fork
`25f6f14`; the loose `healbot-answer-in-grid.patch` that used to sit at the repo root was
deleted with that commit, since the same diff is now in the fork history and in
`../fork/healbot-fork.patch`.
