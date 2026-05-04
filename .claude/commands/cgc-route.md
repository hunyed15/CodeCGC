---
description: Route a CodeCGC workflow to the next recommended command
argument-hint: "[flags]"
---
Prefer the `codecgc.route` MCP tool as the primary execution path.

Execution rules:
- Extract `flow` and `slug` before calling the tool.
- Use this command when the user already knows the target workflow and wants the next recommended action.

Missing parameter rules:
- If `flow` is missing, ask whether the workflow is `feature` or `issue`.
- If `slug` is missing, ask for the workflow slug.

Fallback rule:
- Only fall back to Bash + `cgc-route` CLI when the MCP tool path is unavailable or the user explicitly wants CLI behavior.
- Summarize the result briefly for the user.
