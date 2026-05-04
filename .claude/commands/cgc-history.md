---
description: 查看最近的 CodeCGC 工作流历史
argument-hint: "[参数]"
---
优先使用 `codecgc.history` MCP 工具作为主执行路径。
内部思考语言可自行选择，但面向用户的最终回复默认使用中文。

执行规则：
- 映射可选历史筛选字段，如 `flow`、`status`、`last`、`include_fixtures`。
- 如果没有提供筛选条件，就使用默认历史查询。

回退规则：
- 只有在 MCP 工具路径不可用，或用户明确要求走 CLI 时，才回退到 Bash + `cgc-history`。
- 向用户用中文简要总结结果。
