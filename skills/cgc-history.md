---
name: cgc-history
description: 查询 workflow 历史和审计记录
---

查询历史 workflow 和 audit 记录。调用 MCP 工具 `codecgc.history`。

用户输入格式：`/cgc-history [kind] [slug] [step_id]`

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc-history` 后必须实际获取历史：

1. 优先调用 MCP 工具：

```
codecgc.history({
  kind?: "feature" | "issue",
  slug?: string,
  step_id?: string,
  limit?: number
})
```

2. 如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用终端回退：

```bash
cgc history $ARGUMENTS
```

3. 如果 `cgc history` 不可用，再尝试兼容别名：

```bash
cgc-history $ARGUMENTS
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在未拿到真实返回时声称已经查询历史。

查询模式：
- 不传参数 → 列出所有 workflow
- 传 kind+slug → 查看该 workflow 的所有 audits
- 传 kind+slug+step_id → 查看该步骤的所有 audits
