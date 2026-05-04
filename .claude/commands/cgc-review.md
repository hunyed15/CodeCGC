---
description: 审核一份 CodeCGC 执行审计结果
argument-hint: "[参数]"
---
优先使用 `codecgc.review` MCP 工具作为主执行路径。
内部思考语言可自行选择，但面向用户的最终回复默认使用中文。

执行规则：
- 调用前提取 `audit_file` 和 `decision`。
- 如果用户明确提供，映射可选字段 `risk`、`next_step`、`force`。

缺少参数时：
- 如果缺少 `audit_file`，询问审计 JSON 路径。
- 如果缺少 `decision`，询问审核结论是 `accepted` 还是 `changes-requested`。

回退规则：
- 只有在 MCP 工具路径不可用，或用户明确要求走 CLI 时，才回退到 Bash + `cgc-review`。
- 向用户用中文简要总结结果。
