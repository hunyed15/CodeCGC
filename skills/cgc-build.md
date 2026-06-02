---
name: cgc-build
description: 执行 feature workflow 的下一个步骤
---

执行 feature workflow 的下一个 pending 步骤。调用 MCP 工具 `codecgc.build`。

用户输入格式：`/cgc-build <slug> [step_id]`

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc-build` 后必须实际执行步骤：

1. 优先调用 MCP 工具：

```
codecgc.build({ kind: "feature", slug, step_id? })
```

2. 如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用终端回退：

```bash
cgc build <slug> --step-id <step_id>
```

3. 如果 `cgc build` 不可用，再尝试兼容别名：

```bash
cgc-build <slug> --step-id <step_id>
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在未拿到真实返回时声称执行成功。

执行流程：
1. 调用 `codecgc.build({ kind: "feature", slug, step_id? })`
2. 工具会自动选择正确的 executor（Codex 或 Gemini）
3. 执行成功后会自动返回 `review_request`，包含审核所需的全部上下文
4. 用 `review_request` 进行审核，调用 `codecgc.review` 写入决定

如果执行失败：
- 检查 audit 文件中的错误信息
- 不要假装成功
- 建议用户用 `/cgc-fix` 创建 issue workflow 修复
