---
description: Review a CodeCGC execution audit
argument-hint: "[flags]"
---
Prefer the `codecgc.review` MCP tool as the primary execution path.

Execution rules:
- Extract `audit_file` and `decision` before calling the tool.
- Map optional `risk`, `next_step`, and `force` fields when they are explicitly provided.

Missing parameter rules:
- If `audit_file` is missing, ask for the audit JSON path.
- If `decision` is missing, ask whether the review is `accepted` or `changes-requested`.

Fallback rule:
- Only fall back to Bash + `cgc-review` CLI when the MCP tool path is unavailable or the user explicitly wants CLI behavior.
- Summarize the result briefly for the user.
