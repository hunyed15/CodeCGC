---
description: Audit the CodeCGC package runtime contents
argument-hint: "[flags]"
---
Prefer the `codecgc.package_audit` MCP tool as the primary execution path.

Execution rules:
- Map `format` when the user explicitly requests `summary` or `json`.
- Use this command for publish/runtime completeness checks.

Fallback rule:
- Only fall back to Bash + `cgc-package-audit` CLI when the MCP tool path is unavailable or the user explicitly wants CLI behavior.
- Summarize the result briefly for the user.
