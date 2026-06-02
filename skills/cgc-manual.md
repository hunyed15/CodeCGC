---
name: cgc-manual
description: 手动标记 docs/orchestration 步骤完成
---

手动标记由 Claude 直接处理的 docs/orchestration 步骤完成。调用 MCP 工具 `codecgc.manual`。

用户输入格式：`/cgc-manual <kind> <slug> <step_id> --summary <text>`

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc-manual` 后必须实际写入完成记录：

1. 优先调用 MCP 工具：

```
codecgc.manual({ kind, slug, step_id, summary, changed_files?, notes? })
```

2. 如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用终端回退：

```bash
cgc manual <kind> <slug> <step_id> --summary "<text>"
```

3. 如果 `cgc manual` 不可用，再尝试兼容别名：

```bash
cgc-manual <kind> <slug> <step_id> --summary "<text>"
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在未拿到真实返回时声称步骤已完成。
