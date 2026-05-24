---
name: cgc-explain
description: 解释当前 workflow 状态和下一步建议
---

解释指定 workflow 的当前状态。调用 MCP 工具 `codecgc.explain`。

用户输入格式：`/cgc-explain <kind> <slug>`

```
codecgc.explain({ kind, slug })
```

返回内容包括：
- 当前状态（needs-planning / awaiting-build / awaiting-review 等）
- 已完成的步骤
- 待执行的步骤
- 推荐的下一步操作

用清晰的中文向用户说明当前情况和建议。
