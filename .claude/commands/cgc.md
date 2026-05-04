---
description: 在当前项目中运行 CodeCGC
argument-hint: "[需求或参数]"
---
优先使用 `codecgc.entry` MCP 工具作为主执行路径。
内部思考语言可自行选择，但面向用户的最终回复默认使用中文。

执行规则：
- 如果用户提供的是自然语言需求，传给 `codecgc.entry`。
- 如果用户想继续最近的工作，使用 `codecgc.continue`。
- 如果用户想知道下一步做什么，使用 `codecgc.explain`。

回退规则：
- 只有在 MCP 工具路径不可用，或用户明确要求走 CLI 时，才回退到 Bash + `cgc`。
- 向用户用中文简要总结结果。
