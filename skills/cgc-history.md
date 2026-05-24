---
name: cgc-history
description: 查询 workflow 历史和审计记录
---

查询历史 workflow 和 audit 记录。调用 MCP 工具 `codecgc.history`。

用户输入格式：`/cgc-history [kind] [slug] [step_id]`

```
codecgc.history({
  kind?: "feature" | "issue",
  slug?: string,
  step_id?: string,
  limit?: number
})
```

查询模式：
- 不传参数 → 列出所有 workflow
- 传 kind+slug → 查看该 workflow 的所有 audits
- 传 kind+slug+step_id → 查看该步骤的所有 audits
