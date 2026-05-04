---
description: 执行 CodeCGC 测试步骤
argument-hint: "[参数]"
---
优先使用 `codecgc.test` MCP 工具作为主执行路径。
内部思考语言可自行选择，但面向用户的最终回复默认使用中文。

执行规则：
- 调用前提取 `flow` 和 `slug`。
- 映射可选执行字段，如 `step_number`、`checklist_file`、`audit_root`、`timeout_seconds`、`session_id`、`dry_run`。

缺少参数时：
- 如果缺少 `flow`，询问该测试属于 `feature` 还是 `issue` 工作流。
- 如果缺少 `slug`，询问目标工作流 slug。

回退规则：
- 只有在 MCP 工具路径不可用，或用户明确要求走 CLI 时，才回退到 Bash + `cgc-test`。
- 向用户用中文简要总结结果。
