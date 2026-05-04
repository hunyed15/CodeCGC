---
description: Run CodeCGC release readiness checks
argument-hint: "[flags]"
---
Prefer the `codecgc.release_readiness` MCP tool as the primary execution path.

Execution rules:
- Map optional `workspace` and `format` fields.
- Use this command for combined release, maintenance, and ops checks.

Fallback rule:
- Only fall back to Bash + `cgc-release-readiness` CLI when the MCP tool path is unavailable or the user explicitly wants CLI behavior.
- Summarize the result briefly for the user.
