---
name: cgc-init
description: 初始化当前项目的 CodeCGC 工作流环境
---

在当前项目中初始化 CodeCGC。调用 MCP 工具 `codecgc.init` 完成以下操作：

1. 创建 `.codecgc/` 目录结构（features、issues、execution 等）
2. 生成 `model-routing.yaml`（路径归属策略）
3. 生成 `.claude/CLAUDE.md`（AI 提示词）
4. 生成 `.mcp.json`（MCP 服务器配置）

执行：

```
codecgc.init({ cd: $ARGUMENTS || process.cwd() })
```

如果用户传了参数，作为项目路径；否则使用当前工作目录。

初始化完成后，告知用户：
- 已创建的文件列表
- 下一步可以用 `/cgc-entry` 创建第一个 workflow
