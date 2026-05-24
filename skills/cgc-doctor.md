---
name: cgc-doctor
description: CodeCGC 环境健康检查
---

检查 CodeCGC 运行环境。调用 MCP 工具 `codecgc.doctor`。

```
codecgc.doctor({ cd: process.cwd() })
```

检查项：
- Node.js 版本（>= 20）
- Codex CLI 可用性
- Gemini CLI 可用性
- `.codecgc/` 目录结构
- `model-routing.yaml` 配置
- `.mcp.json` MCP 服务器配置

报告任何缺失或异常项，并给出修复建议。
