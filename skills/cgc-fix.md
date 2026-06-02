---
name: cgc-fix
description: 执行 issue workflow 的下一个修复步骤
---

执行 issue workflow 的修复步骤。调用 MCP 工具 `codecgc.fix`。

用户输入格式：`/cgc-fix <slug> [step_id]`

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc-fix` 后必须实际执行修复步骤：

1. 优先调用 MCP 工具：

```
codecgc.fix({ kind: "issue", slug, step_id? })
```

2. 如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用终端回退：

```bash
cgc fix <slug> --step-id <step_id>
```

3. 如果 `cgc fix` 不可用，再尝试兼容别名：

```bash
cgc-fix <slug> --step-id <step_id>
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在未拿到真实返回时声称修复成功。

执行流程：
1. 调用 `codecgc.fix({ kind: "issue", slug, step_id? })`
2. 工具会自动选择正确的 executor（Codex 或 Gemini）
3. 执行成功后自动返回 `review_request`
4. 用 `review_request` 进行审核

修复策略：
- 如果是后端 bug，executor 应为 backend
- 如果是前端 bug，executor 应为 frontend
- 修复必须有明确的根因分析，不要做表面补丁
