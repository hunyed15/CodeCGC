---
name: cgc-init
description: 初始化当前项目的 CodeCGC 工作流环境
---

在当前项目中初始化 CodeCGC。调用 MCP 工具 `codecgc.init` 完成以下操作：

1. 创建 `.codecgc/` 目录结构（features、issues、execution 等）
2. 生成 `.codecgc/config/routing.yaml`（路径归属策略）
3. 生成 `.codecgc/config/executors.yaml`（执行器配置）
4. 生成 `.claude/CLAUDE.md`（AI 提示词，根据模式自适应）
5. 生成 `.mcp.json`（MCP 服务器配置，按需生成）
6. 释放项目级 skills 和 Claude Code memory

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc-init` 后必须实际初始化或刷新项目：

1. 优先调用 MCP 工具 `codecgc.init`。
2. 如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用终端回退：

```bash
cgc init
```

3. 如果 `cgc init` 不可用，再尝试兼容别名：

```bash
cgc-init
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在未拿到真实返回时声称初始化完成。

## 模式选择

初始化前需要确定工作模式：

### 轻量模式（推荐新手/小项目）
所有代码任务由 Claude 直接处理，无需额外工具。

```
codecgc.init({ cd: $ARGUMENTS || process.cwd() })
```

### 完全模式（推荐团队/大项目）
Claude 规划 + 专业工具执行代码。

```
codecgc.init({ 
  cd: $ARGUMENTS || process.cwd(),
  mode: "full",
  backend: "codex",     // 后端执行器：codex（推荐）或 claude
  frontend: "opencode"  // 前端执行器：opencode（推荐）、gemini 或 claude
})
```

**推荐组合**：
- 后端：`codex`（OpenAI 官方，稳定可靠）
- 前端：`opencode`（开源免费，社区活跃）或 `gemini`（Google 官方）

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| cd | string | "." | 项目根目录 |
| force | boolean | false | 强制覆盖已有文件 |
| refresh_skills | boolean | false | 只刷新项目级 skills，不覆盖 `.codecgc` 配置 |
| mode | "lightweight" \| "full" | "lightweight" | 工作模式 |
| backend | "claude" \| "codex" | "claude" | 后端执行器（仅 full 模式） |
| frontend | "claude" \| "gemini" \| "opencode" | "claude" | 前端执行器（仅 full 模式） |

## 升级已有项目的 skills

如果升级 CodeCGC 后，旧项目里的 `/cgc-status`、`/cgc-history` 等仍然只输出说明，没有实际调用工具，请刷新项目级 skills：

```
codecgc.init({ cd: process.cwd(), refresh_skills: true })
```

CLI 等价命令：

```bash
cgc init --refresh-skills
```

## 初始化完成后

告知用户：
- 已创建的文件列表
- 当前工作模式（轻量/完全）
- 选择的执行器（完全模式时）
- 如需安装外部工具（Codex/Gemini/OpenCode），提供安装命令
- 项目级 skills 的释放情况
- 如有 `warnings`，必须明确提示
- 下一步可以用 `/cgc` 创建第一个 workflow
