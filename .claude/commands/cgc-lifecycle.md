---
description: Audit CodeCGC lifecycle coverage
argument-hint: "[flags]"
---
Prefer the `codecgc.lifecycle` MCP tool as the primary execution path.

Execution rules:
- Map `format` when the user explicitly requests `summary` or `json`.
- Use this command to inspect roadmap/workflow/execution lifecycle coverage.

Fallback rule:
- Only fall back to Bash + `cgc-lifecycle` CLI when the MCP tool path is unavailable or the user explicitly wants CLI behavior.
- Summarize the result briefly for the user.
