---
description: 检查 CodeCGC 集成状态
argument-hint: "[参数]"
---
优先使用 `codecgc.status` MCP 工具作为主执行路径。
内部思考语言可自行选择，但面向用户的最终回复默认使用中文。

执行规则：
- 使用 `codecgc.status` 检查安装与集成就绪状态。
- 如果用户明确给出目标项目目录，映射 `workspace`。

回退规则：
- 只有在 MCP 工具路径不可用，或用户明确要求走 CLI 时，才回退到 Bash + `cgc-status`。
- 向用户用中文简要总结结果。
