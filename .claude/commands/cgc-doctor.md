---
description: Run CodeCGC doctor checks
argument-hint: "[flags]"
---
Prefer the `codecgc.doctor` MCP tool as the primary execution path.

Execution rules:
- Use `codecgc.doctor` for runtime and integration health checks.
- Map `workspace` when the user explicitly provides a target project directory.

Fallback rule:
- Only fall back to Bash + `cgc-doctor` CLI when the MCP tool path is unavailable or the user explicitly wants CLI behavior.
- Summarize the result briefly for the user.
