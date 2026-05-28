# @hunyed15/codecgc

多模型协作的代码工作流编排器。支持两种工作模式：**轻量模式**（Claude 处理所有任务）和**完全模式**（Claude 规划 + 专业工具执行代码）。

## 为什么需要它

当你使用 AI 编码助手时，缺少一个统一的调度层：

- 谁改哪些文件？路径归属不清晰
- 执行结果在哪？没有审计记录
- 前后端改动如何协调？缺少拆分和闭环机制
- 小改动也要走完整流程？缺少轻量模式

CodeCGC 解决这些问题：**一个需求进来，自动拆分、路由、执行、审核、关闭**。

## 安装

```bash
npm install -g @hunyed15/codecgc
```

全局安装后，postinstall 自动释放 Skill 文件到 `~/.claude/skills/`。
你可以直接在任何项目的 Claude Code 中使用 `/cgc-init`、`/cgc-entry` 等命令，无需额外配置。

## 快速开始

```bash
# 1. 在 Claude Code 中初始化项目
/cgc-init

# 2. 创建工作流
/cgc 实现用户登录功能

# 3. 或使用具体命令
/cgc-entry    → 创建 workflow
/cgc-plan     → 规划步骤
/cgc-build    → 执行 feature
/cgc-review   → 审核结果
```

也可以在终端中使用 CLI：

```bash
cd your-project
cgc-init
cgc "实现用户登录功能"
```

初始化后项目结构：

```
your-project/
├── .codecgc/
│   ├── features/                # feature workflow 产物
│   ├── issues/                  # issue workflow 产物
│   ├── execution/               # 执行审计记录
│   └── config/
│       ├── routing.yaml         # 路径归属策略
│       └── executors.yaml       # 执行器配置（模式+provider）
├── .claude/CLAUDE.md            # AI 提示词（根据模式自适应）
└── .mcp.json                    # MCP 服务器配置（按需生成）
```

## 工作模式

### 轻量模式（推荐新手/小项目）

所有代码任务由 Claude 直接处理，无需额外工具。

```
┌─────────────────────────────────────────────────┐
│                   Claude Code                    │
│    规划 + 编码 + 审核 + 验收（全部由 Claude 处理）│
└────────────────────┬────────────────────────────┘
                     │ MCP
┌────────────────────▼────────────────────────────┐
│               codecgcmcp（主控）                  │
│  entry → plan → route → build/fix → review      │
│  路由结果: orchestration → Claude 直接执行       │
└─────────────────────────────────────────────────┘
```

### 完全模式（推荐团队/大项目）

Claude 负责规划和审核，专业工具执行代码。

```
┌─────────────────────────────────────────────────┐
│                   Claude Code                    │
│         （规划、审核、需求澄清、验收）            │
└────────────────────┬────────────────────────────┘
                     │ MCP
┌────────────────────▼────────────────────────────┐
│               codecgcmcp（主控）                  │
│  entry → plan → route → build/fix → review      │
└───────┬──────────────────┬──────────────────┬───┘
        │ MCP              │ MCP              │ MCP
┌───────▼───────┐  ┌───────▼───────┐  ┌───────▼───────┐
│   codexmcp    │  │  geminimcp    │  │ opencodemcp   │
│  （后端执行）  │  │ （前端执行）   │  │ （前端执行）   │
│   Codex CLI   │  │  Gemini CLI   │  │  OpenCode CLI │
└───────────────┘  └───────────────┘  └───────────────┘
```

后端可选：Codex（推荐）或 Claude。
前端可选：OpenCode（推荐）、Gemini 或 Claude。

## MCP 工具

| 工具 | 用途 |
|------|------|
| `codecgc.init` | 初始化项目 |
| `codecgc.entry` | 创建/恢复 workflow |
| `codecgc.plan` | 添加执行步骤 |
| `codecgc.build` | 执行 feature 步骤 |
| `codecgc.fix` | 执行 issue 修复 |
| `codecgc.test` | 执行测试步骤 |
| `codecgc.review` | 审核执行结果 |
| `codecgc.continue` | 续接执行 session |
| `codecgc.explain` | 解释 workflow 状态 |
| `codecgc.route` | 路径归属判断 |
| `codecgc.history` | 查询历史记录 |
| `codecgc.status` | 全局状态摘要 |
| `codecgc.doctor` | 环境健康检查 |
| `codecgc.audit` | 工作流完整性审计 |
| `codecgc.manual` | 手动标记步骤完成 |

## 工作流程

```
需求 → entry → plan → route → build/fix → review → 关闭
                                   ↑                  │
                                   └── changes-requested
```

1. **entry** — 创建 workflow（feature 或 issue）
2. **plan** — Claude 规划步骤，指定每步的 executor 和路径
3. **route** — 根据配置验证路径归属，返回实际 provider
4. **build/fix** — 轻量模式由 Claude 直接执行；完全模式调用 Codex/Gemini/OpenCode
5. **review** — Claude 审核执行结果，通过或打回
6. 打回后回到 build/fix 继续，通过则关闭

## 路由策略

两层配置协同工作：

### executors.yaml（执行器配置）

```yaml
version: 1
mode: lightweight  # lightweight | full
executors:
  backend:
    provider: claude     # claude | codex
  frontend:
    provider: claude     # claude | gemini | opencode
```

轻量模式下所有路径由 Claude 处理；完全模式下根据 provider 路由到对应 CLI。

### routing.yaml（路径归属）

```yaml
version: 1
rules:
  - patterns: ["**/*.py", "**/api/**", "**/backend/**"]
    ownership: backend
  - patterns: ["**/*.tsx", "**/components/**", "**/pages/**"]
    ownership: frontend
  - patterns: ["**/*.md", "**/docs/**"]
    ownership: docs
  - patterns: ["**/shared/**", "**/utils/**"]
    ownership: shared
```

完全模式下，执行器只能修改归属范围内的文件，越界会被拒绝执行。

## CLI 命令

| 命令 | 用途 |
|------|------|
| `cgc-init` | 初始化项目 |
| `cgc-mcp` | 启动 MCP 服务器 |

## 常见问题

### 终端提示 `cgc-init` 命令不存在

确认安装的是包含 `cgc-init` 的新版包，并检查 npm 全局 bin 目录是否在 `PATH` 中：

```bash
npm install -g @hunyed15/codecgc@latest
npm config get prefix
```

Windows 下可进一步确认：

```powershell
where cgc
where cgc-init
where cgc-mcp
```

macOS / Linux 下可进一步确认：

```bash
which cgc
which cgc-init
which cgc-mcp
```

如果 `cgc` 可用但 `cgc-init` 不可用，也可以先使用等价命令：

```bash
cgc init
```

### `/cgc-init` 成功但项目里没有其它 skills

查看初始化结果里的 `project_root` 和 `project_skills.target_dir`。项目级 skills 应释放到：

```text
<project>/.claude/skills/<skill-name>/SKILL.md
```

如果 `warnings` 提示未找到包内 skills 源目录，请重新全局安装包后再次运行 `/cgc-init`。

## 环境要求

- Node.js >= 20
- Codex CLI（完全模式后端需要，`npm install -g @openai/codex`）
- OpenCode CLI（完全模式前端推荐，`npm install -g @opencode-ai/opencode`）
- Gemini CLI（完全模式前端可选，`npm install -g @google/gemini-cli`）

轻量模式只需要 Node.js，无需安装额外 CLI。

## 发布

项目通过 GitHub Actions 自动发布。推送 tag 即触发：

```bash
npm version patch   # 或 minor / major
git push --tags
```

## License

MIT
