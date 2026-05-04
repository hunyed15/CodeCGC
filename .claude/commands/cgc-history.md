---
description: Read recent CodeCGC workflow history
argument-hint: "[flags]"
---
Prefer the `codecgc.history` MCP tool as the primary execution path.

Execution rules:
- Map optional history filters such as `flow`, `status`, `last`, and `include_fixtures`.
- If no filters are provided, use the default history query.

Fallback rule:
- Only fall back to Bash + `cgc-history` CLI when the MCP tool path is unavailable or the user explicitly wants CLI behavior.
- Summarize the result briefly for the user.
