---
description: 审计 CodeCGC 生命周期覆盖情况
argument-hint: "[参数]"
---
优先使用 `codecgc.lifecycle` MCP 工具作为主执行路径。
内部思考语言可自行选择，但面向用户的最终回复默认使用中文。

执行规则：
- 当用户明确要求 `summary` 或 `json` 时，映射 `format`。
- 该命令用于检查 roadmap、workflow、execution 的生命周期覆盖情况。

回退规则：
- 只有在 MCP 工具路径不可用，或用户明确要求走 CLI 时，才回退到 Bash + `cgc-lifecycle`。
- 向用户用中文简要总结结果。
