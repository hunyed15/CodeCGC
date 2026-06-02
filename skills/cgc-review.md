---
name: cgc-review
description: 审核 workflow 步骤的执行结果
---

审核步骤的执行结果。调用 MCP 工具 `codecgc.review`。

用户输入格式：`/cgc-review <kind> <slug> <step_id>`

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc-review` 后必须实际获取审核包或写入审核决定：

1. 优先调用 MCP 工具 `codecgc.review`。
2. 如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用终端回退：

```bash
cgc review <kind> <slug> <step_id>
```

写入决定时：

```bash
cgc review <kind> <slug> <step_id> <decision> --notes "<text>"
```

3. 如果 `cgc review` 不可用，再尝试兼容别名：

```bash
cgc-review <kind> <slug> <step_id>
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在未拿到真实返回时声称已审核。

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
- 变更路径必须符合 `.codecgc/config/routing.yaml`
- 路径越界必须驳回
- 验收标准未满足必须驳回

通过条件全部满足才能 approved，否则用 changes-requested 或 rejected。
