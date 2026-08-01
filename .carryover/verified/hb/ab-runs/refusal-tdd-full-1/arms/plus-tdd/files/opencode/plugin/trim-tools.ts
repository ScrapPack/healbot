/**
 * Trims generic prose out of tool descriptions via the `tool.definition` hook.
 *
 * Why this exists: tool definitions are the single largest block of standing context.
 * Measured under openai/gpt-5.6-sol in a neutral directory: 11 tools, 19,898 B (~4,975 tok)
 * — larger than the base prompt, instructions and skills combined.
 *
 * Why it is OFF by default: a tool description is not pure overhead. Much of it encodes
 * harness-specific constraints the model cannot infer (apply_patch vs cat, timeout
 * semantics, path rules). Cutting too much degrades tool use in ways that are expensive to
 * notice. This ships as a measurable, reversible lever — not a default.
 *
 *   HARNESS_TRIM_TOOLS=1   enable
 *   HARNESS_TRIM_TOOLS=""  (default) no-op, descriptions untouched
 *
 * Scope note: the `task` tool's subagent roster is appended AFTER this hook runs
 * (tool/registry.ts:313-326), so trimming here cannot remove it. Cut subagents instead.
 */

type ToolDefInput = { toolID: string }
type ToolDefOutput = { description: string; parameters: unknown }

/**
 * Drop whole sections whose headings match. Conservative by design: only sections that are
 * generic engineering or style advice, never sections carrying a hard constraint.
 */
const DROP_SECTIONS: Record<string, RegExp[]> = {
  // Few-shot examples of when to keep a todo list. A capable model does not need them.
  // MEASURED: 2,548 -> 2,042 B.
  todowrite: [/^#{1,4}\s*Examples?( of when to use the todo list)?\s*$/i],

  // bash is deliberately ABSENT despite being the largest tool (5,164 B, 26% of the block).
  // Its text was inspected line by line: the bulk is harness-specific semantics (workdir vs
  // `cd`, timeout, output truncation, the good/bad examples) and hard safety constraints
  // ("only commit, amend, push, or create PRs when explicitly requested" -- a real
  // behavioral rule, not something the model does by default). Only ~807 B is the
  // "# Git and GitHub" tail, and most of that is constraint rather than filler.
  // Cutting it would trade correctness for ~200 tokens. Not worth it.
}

/** Collapse 3+ blank lines left behind by section removal. */
const squeeze = (s: string) => s.replace(/\n{3,}/g, "\n\n").trim()

/**
 * Remove a markdown section: the matching heading through the line before the next heading
 * at the same-or-shallower depth. Returns the input unchanged if no heading matches.
 */
function dropSection(text: string, heading: RegExp): string {
  const lines = text.split("\n")
  let start = -1
  let depth = 0
  for (let i = 0; i < lines.length; i++) {
    if (heading.test(lines[i])) {
      start = i
      depth = (lines[i].match(/^#+/) ?? ["#"])[0].length
      break
    }
  }
  if (start === -1) return text

  let end = lines.length
  for (let i = start + 1; i < lines.length; i++) {
    const m = lines[i].match(/^(#+)\s/)
    if (m && m[1].length <= depth) {
      end = i
      break
    }
  }
  return [...lines.slice(0, start), ...lines.slice(end)].join("\n")
}

export const TrimTools = async () => {
  if (process.env["HARNESS_TRIM_TOOLS"] !== "1") return {}

  return {
    "tool.definition": async (input: ToolDefInput, output: ToolDefOutput) => {
      const patterns = DROP_SECTIONS[input.toolID]
      if (!patterns) return

      const before = output.description
      let text = before
      for (const p of patterns) text = dropSection(text, p)
      text = squeeze(text)

      // Refuse a suspicious cut rather than silently gutting a tool.
      if (text.length < before.length * 0.35) return

      output.description = text
    },
  }
}
