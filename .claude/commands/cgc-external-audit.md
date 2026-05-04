---
description: Audit external MCP capability registration and observation
argument-hint: "[flags]"
---
Prefer the `codecgc.external_audit` MCP tool as the primary execution path.

Execution rules:
- Map optional `workspace` and `format` fields.
- Use this command for external capability policy and registration checks.

Fallback rule:
- Only fall back to Bash + `cgc-external-audit` CLI when the MCP tool path is unavailable or the user explicitly wants CLI behavior.
- Summarize the result briefly for the user.
