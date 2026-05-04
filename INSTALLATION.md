# CodeCGC 安装与使用指南

## 目录

1. [系统要求](#系统要求)
2. [安装 CodeCGC](#安装-codecgc)
3. [安装 Python 依赖](#安装-python-依赖)
4. [安装 MCP 服务器](#安装-mcp-服务器)
5. [初始化项目](#初始化项目)
6. [验证安装](#验证安装)
7. [快速开始](#快速开始)
8. [常见问题](#常见问题)

---

## 系统要求

### 必需环境

- **Node.js**: >= 20.0.0
- **Python**: >= 3.10
- **npm**: >= 9.0.0 (随 Node.js 安装)
- **操作系统**: Windows 10+, macOS 10.15+, Linux (Ubuntu 20.04+)

### 检查当前环境

```bash
node --version    # 应显示 v20.x.x 或更高
python --version  # 应显示 Python 3.10.x 或更高
npm --version     # 应显示 9.x.x 或更高
```

---

## 安装 CodeCGC

### 方式 1：从 npm 全局安装（推荐）

```bash
# 使用 npm 官方源安装
npm install -g @hunyed15/codecgc --registry=https://registry.npmjs.org/
```

安装完成后，CodeCGC 会尝试自动执行一次用户级 Claude 集成，相当于：

```bash
cgc-install --mode user
```

这会写入：

- `~/.claude/mcp.json`
- `~/.claude/hooks/route-edit.ps1`
- `~/.claude/commands/cgc.md`
- `~/.claude/commands/cgc-install.md`
- `~/.claude/commands/cgc-status.md`
- `~/.claude/commands/cgc-doctor.md`

写入完成后，可以在 Claude 中直接输入：

```text
/cgc
/cgc-install
/cgc-status
/cgc-doctor
```

如果安装阶段因为 Python 未就绪而跳过了这一步，可以在装好 Python 后手动补执行该命令。

安装后，以下命令将全局可用：
- `cgc`
- `cgc-install`
- `cgc-status`
- `cgc-doctor`
- `cgc-plan`
- `cgc-build`
- `cgc-fix`
- `cgc-test`
- `cgc-review`
- `cgc-route`
- 等等...

### 方式 2：从源码本地安装

```bash
# 1. 进入您的项目目录
cd your-project

# 2. 安装 CodeCGC（指向 release 目录）
npm install /path/to/codecgc/release
```

使用时需要通过 `npx` 调用：
```bash
npx cgc --help
npx cgc-install
```

### 方式 3：直接使用（无需安装）

```bash
# 进入 release 目录
cd /path/to/codecgc/release

# 直接运行命令
node bin/cgc.js --help
node bin/cgc-install.js
```

### 验证安装

```bash
cgc --version
cgc --help
```

**注意**: 如果使用方式 2 或方式 3，需要将 `/path/to/codecgc/release` 替换为实际的 release 目录路径。

---

## 安装 Python 依赖

CodeCGC 的 Python 脚本需要以下依赖：

### 核心依赖

```bash
pip install pyyaml>=6.0
```

### 开发依赖（可选，用于运行测试）

```bash
pip install -r requirements-dev.txt
```

`requirements-dev.txt` 内容：
```
pytest>=8.0.0
pytest-cov>=4.1.0
pyyaml>=6.0
```

### 一键安装所有依赖

在 CodeCGC 项目根目录执行：

```bash
pip install -r requirements.txt
```

---

## 安装 MCP 服务器

CodeCGC 依赖两个 MCP 服务器来执行代码：

### 1. Codex MCP（后端执行器）

**位置**: `codexmcp/` 目录

**安装步骤**:

```bash
cd codexmcp
pip install -e .
```

**验证安装**:

```bash
python -m codexmcp.server --help
```

**功能**: 执行后端代码任务（Python, Go, Rust, Java 等）

---

### 2. Gemini MCP（前端执行器）

**位置**: `geminimcp/` 目录

**安装步骤**:

```bash
cd geminimcp
pip install -e .
```

**验证安装**:

```bash
python -m geminimcp.server --help
```

**功能**: 执行前端代码任务（TypeScript, React, Vue 等）

---

### MCP 服务器配置

CodeCGC 会自动在项目中生成 `.mcp.json` 配置文件：

```json
{
  "mcpServers": {
    "codexmcp": {
      "command": "python",
      "args": ["-m", "codexmcp.server"],
      "env": {}
    },
    "geminimcp": {
      "command": "python",
      "args": ["-m", "geminimcp.server"],
      "env": {}
    }
  }
}
```

**注意**: 如果 Python 命令在您的系统上是 `python3`，请手动修改 `command` 字段。

---

## 初始化项目

### 1. 进入您的项目目录

```bash
cd /path/to/your/project
```

### 2. 运行安装命令

```bash
cgc-install
```

这会创建以下文件和目录：

```
your-project/
├── .claude/
│   ├── hooks/
│   │   └── route-edit.ps1       # 路由钩子（阻止 Claude 直接编辑代码）
│   └── settings.json            # Claude 配置
├── .mcp.json                    # MCP 服务器注册
├── model-routing.yaml           # 路由规则配置
└── codecgc/                     # 工作流产物存储
    ├── product/
    │   ├── feature/             # 功能开发工作流
    │   ├── issue/               # Bug 修复工作流
    │   └── execution/           # 执行审计记录
    ├── architecture/            # 架构文档
    ├── requirements/            # 需求文档
    ├── decisions/               # 技术决策
    ├── learnings/               # 经验总结
    └── roadmap/                 # 路线图
```

### 3. 配置路由规则

编辑 `model-routing.yaml`，定义前端和后端的文件路径模式：

```yaml
# 前端文件路径模式
frontend_paths:
  - "src/components/**"
  - "src/pages/**"
  - "src/ui/**"
  - "*.tsx"
  - "*.jsx"
  - "*.vue"

# 后端文件路径模式
backend_paths:
  - "src/api/**"
  - "src/server/**"
  - "src/db/**"
  - "*.py"
  - "*.go"
  - "*.java"

# 共享路径（需要特殊处理）
shared_paths:
  - "src/types/**"
  - "src/utils/**"

# 路由规则
rules:
  frontend_executor: geminimcp    # 前端使用 Gemini
  backend_executor: codexmcp      # 后端使用 Codex
  shared_policy: split-first      # 共享文件优先拆分
  claude_role: plan-review-accept-only  # Claude 只规划和审查
```

---

## 验证安装

### 1. 检查环境

```bash
cgc-doctor
```

**预期输出**:
```
✓ Python 可用: python 3.10.x
✓ Codex MCP 可导入
✓ Gemini MCP 可导入
✓ 项目集成就绪
✓ .mcp.json 存在
✓ model-routing.yaml 存在
```

### 2. 检查项目状态

```bash
cgc-status
```

**预期输出**:
```
项目集成状态: 就绪
工作流目录: codecgc/
MCP 配置: .mcp.json
路由配置: model-routing.yaml
```

### 3. 运行测试（可选）

```bash
cd /path/to/codecgc
pytest tests/ -v
```

---

## 快速开始

### 示例 1：新增功能

```bash
# 1. 提交需求
cgc "新增用户登录页面，包含用户名密码输入框和登录按钮"

# 2. 系统自动生成规划
# 输出: 已创建 feature 工作流 2026-05-04-user-login-page

# 3. 查看生成的文件
ls codecgc/product/feature/2026-05-04-user-login-page/
# - 2026-05-04-user-login-page-design.md
# - 2026-05-04-user-login-page-checklist.yaml

# 4. 执行第一个步骤
cgc-build --slug 2026-05-04-user-login-page

# 5. 审查执行结果
cgc-review --audit-file codecgc/product/execution/.../xxx.json --decision accepted

# 6. 继续执行后续步骤
cgc-build --slug 2026-05-04-user-login-page

# 7. 查询下一步
cgc-route --slug 2026-05-04-user-login-page
```

### 示例 2：修复 Bug

```bash
# 1. 提交问题
cgc "用户列表页面加载很慢，需要优化"

# 2. 系统自动生成 issue 工作流
# 输出: 已创建 issue 工作流 2026-05-04-slow-user-list

# 3. 执行修复
cgc-fix --slug 2026-05-04-slow-user-list

# 4. 审查修复结果
cgc-review --audit-file ... --decision accepted
```

### 示例 3：查看历史

```bash
# 查看所有开放的功能工作流
cgc-history --flow feature --status open

# 查看最近 10 个工作流
cgc-history --last 10

# 查看项目生命周期
cgc-lifecycle
```

---

## 常见问题

### Q1: `cgc` 命令找不到

**原因**: 全局安装失败或 npm 全局路径未加入 PATH

**解决**:
```bash
# 检查全局安装路径
npm config get prefix

# 将该路径添加到系统 PATH
# Windows: 添加到环境变量
# macOS/Linux: 添加到 ~/.bashrc 或 ~/.zshrc
export PATH="$PATH:$(npm config get prefix)/bin"
```

### Q2: `ModuleNotFoundError: No module named 'yaml'`

**原因**: PyYAML 未安装

**解决**:
```bash
pip install pyyaml
```

### Q3: MCP 服务器无法启动

**原因**: MCP 服务器未正确安装

**解决**:
```bash
# 重新安装 Codex MCP
cd codexmcp
pip uninstall codexmcp -y
pip install -e .

# 重新安装 Gemini MCP
cd geminimcp
pip uninstall geminimcp -y
pip install -e .

# 验证
python -m codexmcp.server --help
python -m geminimcp.server --help
```

### Q4: `cgc-doctor` 报告 Python 不可用

**原因**: Python 命令名称不匹配

**解决**:
```bash
# 如果您的系统使用 python3
which python3

# 创建软链接或别名
# Linux/macOS:
sudo ln -s $(which python3) /usr/local/bin/python

# Windows: 在 .mcp.json 中修改 command 为 "python3"
```

### Q5: 执行步骤时超时

**原因**: 默认 120 秒超时不够

**解决**: 在 checklist.yaml 中为该步骤指定更长的超时
```yaml
steps:
  - action: "复杂重构任务"
    status: pending
    codecgc:
      kind: backend
      task_summary: "重构认证模块"
      target_paths: ["src/auth/"]
      timeout_seconds: 600  # 10 分钟
```

### Q6: 路由规则不生效

**原因**: `model-routing.yaml` 格式错误或路径模式不匹配

**解决**:
```bash
# 检查 YAML 语法
python -c "import yaml; yaml.safe_load(open('model-routing.yaml'))"

# 测试路径匹配
cgc-route --slug your-workflow-slug
```

### Q7: 如何卸载 CodeCGC

```bash
# 卸载全局包
npm uninstall -g codecgc

# 卸载 MCP 服务器
pip uninstall codexmcp geminimcp -y

# 删除项目集成文件（可选）
rm -rf .claude .mcp.json model-routing.yaml codecgc/
```

---

## 进阶配置

### 自定义执行器沙箱模式

在 checklist.yaml 中为每个步骤指定沙箱策略：

```yaml
steps:
  - action: "只读分析"
    codecgc:
      kind: backend
      codex_sandbox: read-only  # 只读模式

  - action: "工作区写入"
    codecgc:
      kind: backend
      codex_sandbox: workspace-write  # 可写工作区

  - action: "完全访问"
    codecgc:
      kind: backend
      codex_sandbox: danger-full-access  # 完全访问（危险）
```

### 保持执行器会话

通过 `session_id` 在多个步骤间保持上下文：

```yaml
steps:
  - action: "步骤 1"
    codecgc:
      kind: backend
      session_id: my-session-123

  - action: "步骤 2"
    codecgc:
      kind: backend
      session_id: my-session-123  # 复用同一会话
```

### 获取完整执行日志

```yaml
steps:
  - action: "调试任务"
    codecgc:
      kind: backend
      return_all_messages: true  # 返回完整消息历史
```

---

## 技术支持

- **GitHub Issues**: https://github.com/hunyed15/CodeCGC/issues
- **文档**: 查看 `codecgc/` 目录下的参考文档
- **审计报告**: `codecgc/architecture/code-audit-2026-05-04.md`

---

## 版本信息

- **CodeCGC 版本**: 0.1.0
- **最后更新**: 2026-05-04
- **Python 要求**: >= 3.10
- **Node.js 要求**: >= 20.0.0
