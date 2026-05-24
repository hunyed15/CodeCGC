---
name: cgc-review
description: 审核 workflow 步骤的执行结果
---

审核步骤的执行结果。调用 MCP 工具 `codecgc.review`。

用户输入格式：`/cgc-review <kind> <slug> <step_id>`

两种模式：

**1. Prepare 模式（不传 decision）**
返回审核请求包，包含代码、验收标准、历史记录。用于分析。

```
codecgc.review({ kind, slug, step_id })
```

**2. Decision 模式（传 decision）**
写入审核决定，可选值：approved、changes-requested、rejected、reopen。

```
codecgc.review({
  kind, slug, step_id,
  decision: "approved" | "changes-requested" | "rejected",
  notes: "...",
  issues: [...],
  suggestions: [...],
  acceptance_check: [...]
})
```

审核硬规则：
- audit 必须是真实执行，不能是 dry-run
- executor 归属必须正确（前端用 Gemini，后端用 Codex）
- 变更路径必须符合 routing.yaml
- 路径越界必须驳回
- 验收标准未满足必须驳回

通过条件全部满足才能 approved，否则用 changes-requested 或 rejected。
