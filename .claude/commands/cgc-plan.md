---
description: Plan or repair a CodeCGC workflow
argument-hint: "[structured planning flags]"
---
Prefer the `codecgc.plan` MCP tool as the primary execution path.

Execution rules:
- Extract `flow`, `slug`, and `summary` before calling the tool.
- Map any provided `target_paths`, `kind`, and planning fields such as `goal`, `acceptance`, `risk`, and issue-specific fields.

Missing parameter rules:
- If `flow` is missing, ask whether this is a `feature` or `issue` workflow.
- If `slug` is missing, ask for a stable workflow slug.
- If `summary` is missing, ask for a short planning summary.

Fallback rule:
- Only fall back to Bash + `cgc-plan` CLI when the MCP tool path is unavailable or the user explicitly wants CLI behavior.
- Summarize the result briefly for the user.
