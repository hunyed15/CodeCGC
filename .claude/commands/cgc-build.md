---
description: Execute a CodeCGC feature build step
argument-hint: "[flags]"
---
Prefer the `codecgc.build` MCP tool as the primary execution path.

Execution rules:
- Extract `slug` before calling the tool.
- Map optional execution fields such as `step_number`, `checklist_file`, `audit_root`, `timeout_seconds`, `session_id`, and `dry_run`.

Missing parameter rules:
- If `slug` is missing, ask for the target feature workflow slug.

Fallback rule:
- Only fall back to Bash + `cgc-build` CLI when the MCP tool path is unavailable or the user explicitly wants CLI behavior.
- Summarize the result briefly for the user.
