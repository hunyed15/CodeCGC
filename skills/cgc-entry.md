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

```
codecgc.entry({ description: $ARGUMENTS, kind: <auto-detect> })
```

创建成功后，告知用户：
- workflow slug
- 当前状态（needs-planning）
- 建议下一步：用 `/cgc-plan` 规划步骤
