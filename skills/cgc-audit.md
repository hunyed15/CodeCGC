---
name: cgc-audit
description: 审计 CodeCGC workflow 完整性和陈旧状态
---

审计 workflow 闭环、半成品和长期阻塞项。调用 MCP 工具 `codecgc.audit`。

用户输入格式：`/cgc-audit [completeness|stale|all]`

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc-audit` 后必须实际审计：

1. 优先调用 MCP 工具：

```
codecgc.audit({ check: $ARGUMENTS || "all" })
```

2. 如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用终端回退：

```bash
cgc audit --check ${ARGUMENTS:-all}
```

3. 如果 `cgc audit` 不可用，再尝试兼容别名：

```bash
cgc-audit --check ${ARGUMENTS:-all}
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在未拿到真实返回时声称审计完成。
