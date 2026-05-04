---
description: Run CodeCGC in the current project
argument-hint: "[request or flags]"
---
Prefer the `codecgc.entry` MCP tool as the primary execution path.

Execution rules:
- If the user supplied a natural-language request, pass it to `codecgc.entry`.
- If the user is asking to continue recent work, use `codecgc.continue`.
- If the user is asking what to do next, use `codecgc.explain`.

Fallback rule:
- Only fall back to Bash + `cgc` CLI when the MCP tool path is unavailable or the user explicitly wants CLI behavior.
- Summarize the result briefly for the user.
