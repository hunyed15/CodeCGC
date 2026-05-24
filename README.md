# @hunyed15/codecgc

多模型协作的代码工作流编排器。Claude 负责规划和审核，Codex 执行后端，Gemini 执行前端——CodeCGC 把它们串成可追踪、可审计的闭环。

## 为什么需要它

当你同时使用多个 AI 编码助手时，缺少一个统一的调度层：

- 谁改哪些文件？路径归属不清晰
- 执行结果在哪？没有审计记录
- 前后端改动如何协调？缺少拆分和闭环机制

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
│   ├── features/             # feature workflow 产物
│   ├── issues/               # issue workflow 产物
│   ├── execution/            # 执行审计记录
│   └── ...                   # 其他工作流产物
├── .codecgc/config/routing.yaml  # 路径归属策略
├── .claude/CLAUDE.md         # AI 提示词（Claude Code 读取）
└── .mcp.json                 # MCP 服务器配置
```

## 架构

```
┌─────────────────────────────────────────────────┐
│                   Claude Code                    │
│         （规划、审核、需求澄清、验收）            │
└────────────────────┬────────────────────────────┘
                     │ MCP
┌────────────────────▼────────────────────────────┐
│               codecgcmcp（主控）                  │
│  entry → plan → route → build/fix → review      │
└───────┬─────────────────────────────┬───────────┘
        │ MCP                         │ MCP
┌───────▼───────┐             ┌───────▼───────┐
│   codexmcp    │             │  geminimcp    │
│  （后端执行）  │             │ （前端执行）   │
│   Codex CLI   │             │  Gemini CLI   │
└───────────────┘             └───────────────┘
```

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
3. **route** — 根据 `.codecgc/config/routing.yaml` 验证路径归属
4. **build/fix** — 调用 Codex（后端）或 Gemini（前端）执行
5. **review** — Claude 审核执行结果，通过或打回
6. 打回后回到 build/fix 继续，通过则关闭

## 路由策略

`.codecgc/config/routing.yaml` 定义路径归属：

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

执行器只能修改归属范围内的文件，越界会被 review 驳回。

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
- Codex CLI（后端执行需要）
- Gemini CLI（前端执行需要）

## 发布

项目通过 GitHub Actions 自动发布。推送 tag 即触发：

```bash
npm version patch   # 或 minor / major
git push --tags
```

## License

MIT
