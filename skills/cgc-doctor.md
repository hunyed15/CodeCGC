---
name: cgc-doctor
description: CodeCGC 环境健康检查
---

检查 CodeCGC 运行环境。调用 MCP 工具 `codecgc.doctor`。

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc-doctor` 后必须实际运行诊断：

1. 优先调用 MCP 工具：

```
codecgc.doctor({ cd: process.cwd() })
```

2. 如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用终端回退：

```bash
cgc doctor
```

3. 如果 `cgc doctor` 不可用，再尝试兼容别名：

```bash
cgc-doctor
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在未拿到真实返回时声称已经完成诊断。

如果 MCP 工具没有出现在当前工具列表里，不要停下来解释工具不可用；必须继续尝试 `Bash` 执行 CLI。只有实际调用 MCP/CLI 失败后才能报告失败，且禁止要求用户粘贴命令输出。

检查项：
- Node.js 版本（>= 20）
- CodeCGC CLI 可用性（`cgc` / `cgc-init` / `cgc-mcp`）
- Codex CLI 可用性
- Gemini CLI 可用性
- `.codecgc/` 目录结构
- `.codecgc/config/routing.yaml` 配置
- `.mcp.json` MCP 服务器配置

报告任何缺失或异常项，并给出修复建议。
