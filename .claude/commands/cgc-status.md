---
description: Check CodeCGC integration status
argument-hint: "[flags]"
---
Prefer the `codecgc.status` MCP tool as the primary execution path.

Execution rules:
- Use `codecgc.status` for installation readiness checks.
- Map `workspace` when the user explicitly provides a target project directory.

Fallback rule:
- Only fall back to Bash + `cgc-status` CLI when the MCP tool path is unavailable or the user explicitly wants CLI behavior.
- Summarize the result briefly for the user.
