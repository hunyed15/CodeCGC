---
name: cgc-build
description: 执行 feature workflow 的下一个步骤
---

执行 feature workflow 的下一个 pending 步骤。调用 MCP 工具 `codecgc.build`。

用户输入格式：`/cgc-build <slug> [step_id]`

执行流程：
1. 调用 `codecgc.build({ kind: "feature", slug, step_id? })`
2. 工具会自动选择正确的 executor（Codex 或 Gemini）
3. 执行成功后会自动返回 `review_request`，包含审核所需的全部上下文
4. 用 `review_request` 进行审核，调用 `codecgc.review` 写入决定

如果执行失败：
- 检查 audit 文件中的错误信息
- 不要假装成功
- 建议用户用 `/cgc-fix` 创建 issue workflow 修复
