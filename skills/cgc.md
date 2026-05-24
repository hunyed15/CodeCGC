---
name: cgc
description: CodeCGC 单入口 - 自然语言需求自动路由到合适的工作流
---

CodeCGC 单入口命令。根据用户的自然语言需求自动决定流程。

用户输入格式：`/cgc <自然语言需求>`

判断逻辑：

1. **如果项目未初始化**（无 `.codecgc/` 目录）→ 先 `/cgc-init`，然后继续
2. **如果是修复类需求**（包含"修复"、"bug"、"fix"、"错误"）→ 用 `codecgc.entry({ kind: "issue" })` 创建 issue workflow
3. **否则** → 用 `codecgc.entry({ kind: "feature" })` 创建 feature workflow
4. 创建后自动进入规划阶段（`/cgc-plan`），询问用户确认或调整步骤
5. 用户确认后自动执行 `/cgc-build` 或 `/cgc-fix`
6. 执行成功后自动进入审核

整个流程对用户透明，但每个关键决策点（规划完成、执行完成）需要确认。
