---
name: cgc-status
description: 查看所有 workflow 的状态摘要
---

显示项目内所有 workflow 状态。调用 MCP 工具 `codecgc.status`。

用户输入格式：`/cgc-status [active|closed|all]`

默认显示 active workflow。

```
codecgc.status({ filter: $ARGUMENTS || "active" })
```

返回结果包含：
- 每个 workflow 的 kind、slug、状态
- 当前步骤进度
- 最后更新时间

根据状态给用户建议：
- needs-planning → 用 /cgc-plan
- awaiting-build → 用 /cgc-build
- awaiting-fix → 用 /cgc-fix
- awaiting-review → 用 /cgc-review
