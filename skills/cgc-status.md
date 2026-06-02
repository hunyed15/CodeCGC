---
name: cgc-status
description: 查看所有 workflow 的状态摘要
---

显示项目内所有 workflow 状态。调用 MCP 工具 `codecgc.status`。

用户输入格式：`/cgc-status [active|closed|all]`

默认显示 active workflow。

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc-status` 后必须实际获取状态：

1. 优先调用 MCP 工具：

```
codecgc.status({ filter: $ARGUMENTS || "active" })
```

2. 如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用终端回退：

```bash
cgc status ${ARGUMENTS:-active}
```

3. 如果 `cgc status` 不可用，再尝试兼容别名：

```bash
cgc-status ${ARGUMENTS:-active}
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在未拿到真实返回时声称已经检阅状态。

如果 MCP 工具没有出现在当前工具列表里，不要停下来解释工具不可用；必须继续尝试 `Bash` 执行 CLI。只有实际调用 MCP/CLI 失败后才能报告失败，且禁止要求用户粘贴命令输出。

返回结果包含：
- 每个 workflow 的 kind、slug、状态
- 当前步骤进度
- 最后更新时间

根据状态给用户建议：
- needs-planning → 用 /cgc-plan
- awaiting-build → 用 /cgc-build
- awaiting-fix → 用 /cgc-fix
- awaiting-review → 用 /cgc-review
