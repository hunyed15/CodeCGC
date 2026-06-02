---
name: cgc-route
description: 根据路径判断 CodeCGC executor 归属
---

根据路径判断归属（backend/frontend/docs/orchestration/shared）并推荐 executor。调用 MCP 工具 `codecgc.route`。

用户输入格式：`/cgc-route <paths...>`

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc-route` 后必须实际路由：

1. 优先调用 MCP 工具：

```
codecgc.route({ paths: [...], executor_hint? })
```

2. 如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用终端回退：

```bash
cgc route <paths...>
```

3. 如果 `cgc route` 不可用，再尝试兼容别名：

```bash
cgc-route <paths...>
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在未拿到真实返回时声称已经完成路由。
