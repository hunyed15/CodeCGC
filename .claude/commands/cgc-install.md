---
description: 为当前项目或 Claude 用户目录安装/同步 CodeCGC 集成
argument-hint: "[参数]"
---
优先使用 `codecgc.install` MCP 工具作为主执行路径。
内部思考语言可自行选择，但面向用户的最终回复默认使用中文。

执行规则：
- 把安装参数映射到 `codecgc.install` 的 `mode`、`workspace`、`user_root` 等字段。
- 如果用户没有提供参数，就使用默认安装模式。

回退规则：
- 只有在 MCP 工具路径不可用，或用户明确要求走 CLI 时，才回退到 Bash + `cgc-install`。
- 向用户用中文简要总结结果。
