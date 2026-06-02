---
name: cgc-entry
description: 创建或恢复一个 CodeCGC workflow（feature/issue）
---

创建一个新的 workflow。调用 MCP 工具 `codecgc.entry`。

用户输入格式：`/cgc-entry <需求描述>`

参数解析：
- `$ARGUMENTS` 整体作为 `description`
- 默认 `kind: "feature"`，如果描述中包含"修复"、"bug"、"fix"则用 `kind: "issue"`

执行：

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc-entry` 后必须实际创建或恢复 workflow：

1. 优先调用 MCP 工具：

```
codecgc.entry({ description: $ARGUMENTS, kind: <auto-detect> })
```

2. 如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用终端回退：

```bash
cgc entry $ARGUMENTS
```

3. 如果 `cgc entry` 不可用，再尝试兼容别名：

```bash
cgc-entry $ARGUMENTS
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在未拿到真实返回时声称 workflow 已创建。

创建成功后，告知用户：
- workflow slug
- 当前状态（needs-planning）
- 建议下一步：用 `/cgc-plan` 规划步骤
