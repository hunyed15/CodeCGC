---
description: 规划或修复一个 CodeCGC 工作流
argument-hint: "[结构化规划参数]"
---
优先使用 `codecgc.plan` MCP 工具作为主执行路径。
内部思考语言可自行选择，但面向用户的最终回复默认使用中文。

执行规则：
- 调用前提取 `flow`、`slug` 和 `summary`。
- 映射用户提供的 `target_paths`、`kind`，以及 `goal`、`acceptance`、`risk` 等规划字段和 issue 专属字段。

缺少参数时：
- 如果缺少 `flow`，询问这是 `feature` 还是 `issue` 工作流。
- 如果缺少 `slug`，询问稳定的工作流 slug。
- 如果缺少 `summary`，询问一个简短规划摘要。

回退规则：
- 只有在 MCP 工具路径不可用，或用户明确要求走 CLI 时，才回退到 Bash + `cgc-plan`。
- 向用户用中文简要总结结果。
