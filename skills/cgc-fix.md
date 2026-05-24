---
name: cgc-fix
description: 执行 issue workflow 的下一个修复步骤
---

执行 issue workflow 的修复步骤。调用 MCP 工具 `codecgc.fix`。

用户输入格式：`/cgc-fix <slug> [step_id]`

执行流程：
1. 调用 `codecgc.fix({ kind: "issue", slug, step_id? })`
2. 工具会自动选择正确的 executor（Codex 或 Gemini）
3. 执行成功后自动返回 `review_request`
4. 用 `review_request` 进行审核

修复策略：
- 如果是后端 bug，executor 应为 backend
- 如果是前端 bug，executor 应为 frontend
- 修复必须有明确的根因分析，不要做表面补丁
