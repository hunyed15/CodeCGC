---
description: 运行 CodeCGC 发布就绪检查
argument-hint: "[参数]"
---
优先使用 `codecgc.release_readiness` MCP 工具作为主执行路径。
内部思考语言可自行选择，但面向用户的最终回复默认使用中文。

执行规则：
- 映射可选字段 `workspace` 和 `format`。
- 该命令用于联合检查发布、维护和运维就绪状态。

回退规则：
- 只有在 MCP 工具路径不可用，或用户明确要求走 CLI 时，才回退到 Bash + `cgc-release-readiness`。
- 向用户用中文简要总结结果。
