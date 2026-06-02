---
name: cgc-explain
description: 解释当前 workflow 状态和下一步建议
---

解释指定 workflow 的当前状态。调用 MCP 工具 `codecgc.explain`。

用户输入格式：`/cgc-explain <kind> <slug>`

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc-explain` 后必须实际读取 workflow 状态：

1. 优先调用 MCP 工具：

```
codecgc.explain({ kind, slug })
```

2. 如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用终端回退：

```bash
cgc explain <kind> <slug>
```

3. 如果 `cgc explain` 不可用，再尝试兼容别名：

```bash
cgc-explain <kind> <slug>
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在未拿到真实返回时声称已经解释状态。

返回内容包括：
- 当前状态（needs-planning / awaiting-build / awaiting-review 等）
- 已完成的步骤
- 待执行的步骤
- 推荐的下一步操作

用清晰的中文向用户说明当前情况和建议。
