---
name: cgc-continue
description: 在同一 session_id 内继续执行 CodeCGC 步骤
---

在同一 session_id 内继续执行，用于跨 turn 续接 Codex/Gemini/OpenCode 执行。调用 MCP 工具 `codecgc.continue`。

用户输入格式：`/cgc-continue <kind> <slug> <step_id> <session_id>`

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc-continue` 后必须实际续接：

1. 优先调用 MCP 工具：

```
codecgc.continue({ kind, slug, step_id, session_id })
```

2. 如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用终端回退：

```bash
cgc continue <kind> <slug> <step_id> <session_id>
```

3. 如果 `cgc continue` 不可用，再尝试兼容别名：

```bash
cgc-continue <kind> <slug> <step_id> <session_id>
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在未拿到真实返回时声称续接完成。
