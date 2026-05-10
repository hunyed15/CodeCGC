# CodeCGC 安装指南

本文说明如何从 npm 安装 CodeCGC，并把它接入到具体项目中。

## 环境要求

- Node.js >= 20
- npm >= 9
- Python >= 3.10
- 可选：Claude Code、Codex CLI、Gemini CLI

CodeCGC 的 npm 包提供 `cgc*` 命令；Python 运行时负责 MCP 编排器、执行器桥接、路由策略检查和工作流脚本。

## 1. 全局安装 CLI

```bash
npm install -g @hunyed15/codecgc --registry=https://registry.npmjs.org/
```

全局安装只注册命令，不会默认写入 `~/.claude`。这是当前主线设计：每个业务项目通过项目级安装生成自己的 `.mcp.json`、`.claude/` 和 `model-routing.yaml`。

验证命令：

```bash
cgc --help
cgc-install --help
cgc-doctor --help
```

## 2. 在目标项目执行项目级安装

进入你要使用 CodeCGC 的项目根目录：

```bash
cd your-project
cgc-install
```

默认安装模式是项目级安装，等价于：

```bash
cgc-install --mode local --workspace .
```

安装会创建或同步：

```text
.mcp.json
model-routing.yaml
.claude/
  settings.json
  hooks/
    route-edit.ps1
  commands/
    cgc*.md
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

这些文件属于目标项目的 CodeCGC 集成面。不同电脑、不同项目的安装路径可能不同，因此应由 `cgc-install` 在本机生成，不应从 CodeCGC 源码仓库复制固定路径。

## 3. 首次启动和自检

安装后执行：

```bash
cgc-start
cgc-status
cgc-doctor
```

在 Claude 中也可以使用：

```text
/cgc-start
/cgc-status
/cgc-doctor
```

`cgc-start` 是只读的新手入口，会提示当前项目的最短使用路径。`cgc-status` 检查项目级集成文件是否齐全。`cgc-doctor` 检查 Python、MCP 运行时、执行器导入和项目集成状态。

## 4. 日常使用

推荐从一个入口开始：

```text
/cgc 新增一个登录页，放在 src/components/LoginForm.tsx
```

命令行回退路径：

```bash
cgc "新增一个登录页，放在 src/components/LoginForm.tsx"
```

CodeCGC 会根据工作流状态决定下一步是规划、执行、审核、继续还是收尾。只有在你明确知道当前阶段时，才需要直接使用子命令：

```bash
cgc-plan ...
cgc-build ...
cgc-fix ...
cgc-test ...
cgc-review ...
cgc-route ...
cgc-history ...
```

## 5. 角色与写入边界

CodeCGC 的默认协作边界是：

- Claude：需求、规划、设计、文档、审核、验收和工作流状态。
- Codex：后端代码和后端测试。
- Gemini：前端代码和前端测试。

`model-routing.yaml` 是项目内路由策略的唯一来源。Claude 的 hook 不承载业务规则，只把 `Edit`、`Write`、`MultiEdit` 写入请求交给同一套策略检查器，从而避免 Claude 绕过路由边界直接修改代码。

## 6. 用户级安装

用户级安装不是默认路径。只有在你明确希望同步 `~/.claude` 时才使用：

```bash
cgc-install --mode user-dry-run
cgc-install --mode user
```

建议先使用 `user-dry-run` 预览变更。普通项目接入场景应使用默认项目级安装。

## 7. 发布包维护者检查

维护 CodeCGC 包时，建议在源码仓库运行：

```bash
python -m pytest tests --basetemp D:\tmp\codecgc-pytest
python -m compileall -q scripts codecgcmcp\src codexmcp\src geminimcp\src
python scripts\audit_codecgc_package_runtime.py --format json
python scripts\audit_codecgc_release_readiness.py --format json
npm pack --dry-run --json
```

如果默认临时目录受限，可以指定发布探针目录：

```bash
set CODECGC_RELEASE_PROBE_ROOT=D:\tmp
python scripts\audit_codecgc_release_readiness.py --format json
```

## 8. 常见问题

### `cgc` 命令找不到

确认 npm 全局 bin 目录已经加入 `PATH`：

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
cgc-install
cgc-status
```

### 写入被 hook 拦截

检查 `model-routing.yaml`。如果目标路径属于 unknown 或 shared，应该先明确文件归属或拆分任务，而不是绕过 hook。

## 参考

- `README.md`
- `codecgc/reference/quickstart.md`
- `codecgc/reference/onboarding.md`
- `codecgc/reference/project-structure.md`
- `codecgc/reference/policy-routing.md`
- `codecgc/reference/troubleshooting.md`
