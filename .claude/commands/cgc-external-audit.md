---
description: 审计外部 MCP 能力注册与接入状态
argument-hint: "[参数]"
---
优先使用 `codecgc.external_audit` MCP 工具作为主执行路径。
内部思考语言可自行选择，但面向用户的最终回复默认使用中文。

执行规则：
- 映射可选字段 `workspace` 和 `format`。
- 该命令用于外部能力策略与注册检查。

回退规则：
- 只有在 MCP 工具路径不可用，或用户明确要求走 CLI 时，才回退到 Bash + `cgc-external-audit`。
- 向用户用中文简要总结结果。
