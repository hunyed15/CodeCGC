# CodeCGC Release v0.1.2

## 📦 发布内容

本目录包含 CodeCGC 项目的完整发布版本，已修复所有 P0/P1 优先级 bug，并完成核心优化。

## 📋 版本信息

- **版本号**: 0.1.2
- **发布日期**: 2026-05-04
- **Python 要求**: >= 3.10
- **Node.js 要求**: >= 20.0.0

## 🎯 本版本修复内容

### P0 - 正确性修复 ✅
1. **路由逻辑错误** - `first_pending_step_is_not_executable` 硬编码检查 step 1
2. **路径提取误匹配** - `extract_target_paths_from_request` 误匹配日期/版本号

### P1 - 可用性改进 ✅
3. **步骤状态自动更新** - Review 后自动更新 checklist 步骤状态
4. **Per-step timeout** - 支持在 checklist 中为每个步骤指定超时时间

### P2 - 效率优化 ✅
5. **YAML 解析器替换** - 用 PyYAML 替换手写解析器，删除 ~180 行代码
6. **测试覆盖** - 添加 30+ 单元测试，覆盖核心逻辑

## 📚 文档

- **[QUICKSTART.md](QUICKSTART.md)** - 5 分钟快速上手指南
- **[INSTALLATION.md](INSTALLATION.md)** - 完整安装与配置文档
- **[codecgc/architecture/code-audit-2026-05-04.md](codecgc/architecture/code-audit-2026-05-04.md)** - 代码审计报告

## 🚀 快速开始

### 1. 安装

```bash
# 从 npm 安装 CodeCGC
npm install -g @hunyed15/codecgc --registry=https://registry.npmjs.org/

# 安装 Python 依赖
pip install pyyaml

# 如自动集成未生效，可手动补执行
cgc-install --mode user
```

全局安装完成后，CodeCGC 会尝试自动写入 Claude 用户级集成到 `~/.claude`，包括：

- `~/.claude/mcp.json`
- `~/.claude/hooks/route-edit.ps1`
- `~/.claude/commands/cgc*.md` 自定义 slash commands

当前安装链路还会注册 3 个 MCP server：

- `codecgc`：CodeCGC 编排器 MCP
- `codex`：后端执行器 MCP
- `gemini`：前端执行器 MCP

安装完成后，可以在 Claude 中直接使用：

- `/cgc`
- `/cgc-install`
- `/cgc-status`
- `/cgc-doctor`
- `/cgc-plan`
- `/cgc-build`
- `/cgc-fix`
- `/cgc-test`
- `/cgc-review`
- `/cgc-route`
- `/cgc-history`
- `/cgc-package-audit`
- `/cgc-external-audit`
- `/cgc-release-readiness`
- `/cgc-lifecycle`

当前这些 Claude commands 已调整为：

- 优先走 `codecgc` MCP orchestrator
- 只有在 MCP tool 路径不可用时，才回退到本地 CLI

如果安装时 Python 尚未就绪，自动集成会跳过，此时可在安装 Python 后手动执行 `cgc-install --mode user`。

### 2. 初始化项目

```bash
cd your-project
cgc-install
cgc-doctor
```

### 3. 开始使用

```bash
cgc "新增用户登录功能"
```

详细步骤请参考 [QUICKSTART.md](QUICKSTART.md)

## 📤 发布到 npm

### 手动发布

```bash
npm login --registry=https://registry.npmjs.org/
npm publish --access public --registry=https://registry.npmjs.org/
```

### GitHub 自动发布

本目录已包含 GitHub Actions 工作流：

`/.github/workflows/publish-npm.yml`

触发方式：

```bash
git tag v0.1.0
git push origin v0.1.0
```

自动发布前提：

- GitHub 仓库已启用 Actions
- 仓库 Secrets 中已设置 `NPM_TOKEN`
- tag 版本必须与 `package.json` 中的 `version` 完全一致

建议流程：

```bash
# 1. 更新 package.json version
# 2. 提交到 GitHub
# 3. 打版本 tag
git tag v0.1.0
git push origin main --tags
```

## 📁 目录结构

```
release/
├── README.md                    # 本文件
├── QUICKSTART.md               # 快速开始指南
├── INSTALLATION.md             # 完整安装文档
├── package.json                # Node.js 包配置
├── requirements.txt            # Python 核心依赖
├── requirements-dev.txt        # Python 开发依赖
├── pytest.ini                  # 测试配置
├── model-routing.yaml          # 路由规则模板
├── bin/                        # 命令行工具
├── scripts/                    # Python 工作流脚本
├── tests/                      # 单元测试
├── codecgc/                    # 工作流产物模板
├── codexmcp/                   # Codex MCP 服务器
└── geminimcp/                  # Gemini MCP 服务器
```

## 🔧 依赖清单

### Python 依赖

**核心依赖**:
- pyyaml>=6.0

**开发依赖**:
- pytest>=8.0.0
- pytest-cov>=4.1.0

### MCP 服务器

1. **Codex MCP** - 后端代码执行器
2. **Gemini MCP** - 前端代码执行器

## ✅ 验证安装

```bash
cgc-doctor
```

## 📝 更新日志

### v0.1.0 (2026-05-04)

**修复**:
- 修复路由逻辑错误
- 修复路径提取误匹配
- Review 后自动更新步骤状态

**新增**:
- Per-step timeout 支持
- 30+ 单元测试

**优化**:
- 用 PyYAML 替换手写解析器

## 📄 许可证

MIT License

---

**感谢使用 CodeCGC！**
