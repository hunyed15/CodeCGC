---
description: Execute a CodeCGC test step
argument-hint: "[flags]"
---
Prefer the `codecgc.test` MCP tool as the primary execution path.

Execution rules:
- Extract `flow` and `slug` before calling the tool.
- Map optional execution fields such as `step_number`, `checklist_file`, `audit_root`, `timeout_seconds`, `session_id`, and `dry_run`.

Missing parameter rules:
- If `flow` is missing, ask whether the test belongs to a `feature` or `issue` workflow.
- If `slug` is missing, ask for the target workflow slug.

Fallback rule:
- Only fall back to Bash + `cgc-test` CLI when the MCP tool path is unavailable or the user explicitly wants CLI behavior.
- Summarize the result briefly for the user.
