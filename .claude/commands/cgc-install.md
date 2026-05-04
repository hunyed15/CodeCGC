---
description: Install or sync CodeCGC integration for the current project or user Claude profile
argument-hint: "[flags]"
---
Prefer the `codecgc.install` MCP tool as the primary execution path.

Execution rules:
- Map install flags to `codecgc.install` fields such as `mode`, `workspace`, and `user_root`.
- If the user did not supply flags, use the default install mode.

Fallback rule:
- Only fall back to Bash + `cgc-install` CLI when the MCP tool path is unavailable or the user explicitly wants CLI behavior.
- Summarize the result briefly for the user.
