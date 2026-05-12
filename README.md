# CodeCGC

CodeCGC 是一个以 Claude 为主控入口的多模型开发编排层，用于把需求、规划、执行、审查和验收拆成可控的协作流程。

它的核心分工是：Claude 负责需求、规划、设计、文档、审查、验收和工作流状态；Codex 负责后端实现和后端测试；Gemini 负责前端实现和前端测试。CodeCGC 通过项目级路由策略和 Claude 写入拦截 hook 来约束这些边界。

## 工作模型

推荐主路径：

```text
Claude /cgc -> CodeCGC MCP -> CodeCGC runtime -> Codex 或 Gemini 执行器
```

CLI 仍然保留，用于本地调试、CI 检查和 MCP 不可用时的回退执行。普通用户优先使用 Claude 内的 `/cgc`，或在命令行使用 `cgc`，不需要记住所有内部子命令。

安全边界：Claude 可以维护需求、规划、文档、审查和工作流状态；产品代码实现必须经由 CodeCGC 路由到 Codex 或 Gemini。项目 hook 会拦截 `Edit`、`Write`、`MultiEdit`、`Bash` 和 `PowerShell`，防止 Claude 用直接编辑或 shell 写入绕过路由。

## 环境要求

- Node.js >= 20
- npm >= 9
- Python >= 3.10
- 可选：Claude Code、Codex CLI、Gemini CLI

## 安装

全局安装 CLI：

```bash
npm install -g @hunyed15/codecgc --registry=https://registry.npmjs.org/
```

全局安装只提供 `cgc*` 命令，不会默认写入用户级 Claude 配置。

然后在每个目标项目根目录执行项目级安装：

```bash
cd your-project
cgc-init
cgc-start
cgc-status
cgc-doctor
```

在 Claude 中可以使用对应 slash command：

```text
/cgc-init
/cgc-start
/cgc-status
/cgc-doctor
```

`/cgc-init` 和 `cgc-init` 默认都是项目级安装。它们会把集成文件写入当前项目，不会写入 `~/.claude` 等全局目录。

## 安装后生成的项目文件

`cgc-init` 会在目标项目中创建或同步：

```text
.mcp.json
model-routing.yaml
.claude/
  settings.local.json
  hooks/
    route-edit.ps1
  commands/
    cgc*.md
.codex/
  codecgcrc.json
.gemini/
  policies/
    codecgc-policy.toml
codecgc/
  START_HERE.md
  features/
  issues/
  execution/
  requirements/
  architecture/
  roadmap/
  compound/
  docs/
  reference/
  fixtures/
```

在 CodeCGC 源码仓库中，`.mcp.json`、`.claude/settings.local.json`、`.claude/commands/`、`.codex/`、`.gemini/`、`codecgc/START_HERE.md` 以及实时 workflow 输出目录会被忽略，因为它们是机器相关或项目安装生成的内容。

源码仓库会保留可发布运行时、参考文档、命令模板、测试 fixtures，以及 `.claude/hooks/route-edit.ps1` 这个 hook 模板。

## 角色与路由策略

`model-routing.yaml` 是文件归属和写入权限的唯一策略来源：

- Claude 可以写 orchestration 和 docs 路径。
- Codex 可以写 backend 源码和 backend 测试。
- Gemini 可以写 frontend 源码和 frontend 测试。
- shared 路径使用 `split-first` 策略，必须先拆分再执行。
- unknown 路径默认拒绝，直到它被明确加入 `model-routing.yaml`。

Claude hook 本身不承载业务逻辑。它只把 `Edit`、`Write`、`MultiEdit` 请求转发给 `scripts/codecgc_policy.py`，从而保证 hook 检查、任务构建和执行器派发使用同一套路由策略。

## 文档放置规则

普通项目文档放在 `docs/`，例如用户手册、API 文档、部署说明和 changelog。

CodeCGC 工作流和治理产物放在 `codecgc/`：

- `codecgc/docs/`：CodeCGC 生成的指南类文档。
- `codecgc/reference/`：稳定契约、参考说明和工具文档。
- `codecgc/requirements/`：长期需求沉淀。
- `codecgc/architecture/`：架构说明和系统图谱。
- `codecgc/roadmap/`：路线图和阶段计划。
- `codecgc/features/`：功能计划、checklist 和验收记录。
- `codecgc/issues/`：问题报告、分析和修复计划。
- `codecgc/execution/`：执行器审计记录。

## 日常使用

在 Claude 中：

```text
/cgc 在 src/components/LoginForm.tsx 中新增登录页
```

在命令行中：

```bash
cgc "在 src/components/LoginForm.tsx 中新增登录页"
```

CodeCGC 会判断下一步应该是规划、执行、审查、继续还是关闭。只有当你已经明确知道当前阶段时，才需要直接使用子命令：

```bash
cgc-plan ...
cgc-build ...
cgc-fix ...
cgc-test ...
cgc-review ...
cgc-route ...
```

## 健康检查

对已经安装 CodeCGC 的目标项目：

```bash
cgc-status
cgc-doctor
cgc-external-status
cgc-external-audit
```

维护或发布 CodeCGC 包时：

```bash
python -m pytest tests --basetemp D:\tmp\codecgc-pytest
python -m compileall -q scripts mcp\codecgcmcp\src mcp\codexmcp\src mcp\geminimcp\src
python scripts\audit_codecgc_package_runtime.py --format json
python scripts\audit_codecgc_release_readiness.py --format json
npm pack --dry-run --json
```

`cgc-release-readiness` 会通过临时项目安装探针验证发布包可用性。源码仓库本身不需要提交项目级 `.mcp.json`、`.claude/settings.local.json`、`.codex/` 或 `.gemini/`。

如果运行环境限制默认临时目录写入，可以显式指定探针目录：

```bash
set CODECGC_RELEASE_PROBE_ROOT=D:\tmp
python scripts\audit_codecgc_release_readiness.py --format json
```

## 常见问题

### `cgc` 命令找不到

确认 npm 全局 bin 目录已加入 `PATH`：

```bash
npm config get prefix
```

然后检查对应系统的全局 bin 路径是否在环境变量中。

### `cgc-doctor` 提示 Python 或 MCP 依赖缺失

先确认 Python 可用：

```bash
python --version
```

再安装核心依赖：

```bash
python -m pip install -r requirements.txt
```

如果是在源码开发环境中，可以按 `cgc-doctor` 输出的建议执行 editable install。

### 项目级集成缺失或过期

在目标项目根目录重新执行：

```bash
cgc-init
cgc-status
```

### 写入被 hook 拦截

检查 `model-routing.yaml`。如果目标路径属于 unknown 或 shared，应该先明确文件归属或拆分任务，而不是绕过 hook。

## 参考文档

- [快速开始](codecgc/reference/quickstart.md)
- [新手入口](codecgc/reference/onboarding.md)
- [操作指南](codecgc/reference/operation-guide.md)
- [真实工作流闭环](codecgc/reference/real-workflow-loop.md)
- [失败恢复闭环](codecgc/reference/recovery-loop.md)
- [故障排查](codecgc/reference/troubleshooting.md)
- [路径契约](codecgc/reference/path-contract.md)
- [路由策略](codecgc/reference/policy-routing.md)
- [项目结构](codecgc/reference/project-structure.md)
- [维护者指南](codecgc/reference/maintainer-guide.md)
