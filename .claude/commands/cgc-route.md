---
description: 为 CodeCGC 工作流推荐下一条命令
argument-hint: "[参数]"
---
优先使用 `codecgc.route` MCP 工具作为主执行路径。
内部思考语言可自行选择，但面向用户的最终回复默认使用中文。

执行规则：
- 调用前提取 `flow` 和 `slug`。
- 当用户已经知道目标工作流，只想得到下一步推荐动作时，使用这个命令。

缺少参数时：
- 如果缺少 `flow`，询问工作流是 `feature` 还是 `issue`。
- 如果缺少 `slug`，询问工作流 slug。

回退规则：
- 只有在 MCP 工具路径不可用，或用户明确要求走 CLI 时，才回退到 Bash + `cgc-route`。
- 向用户用中文简要总结结果。
