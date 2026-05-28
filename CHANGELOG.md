# Changelog

All notable changes to CodeCGC will be documented in this file.

## [1.0.14] - 2026-05-28

### 📝 Docs
- **更新**：README.md 架构图、工作模式、路由策略、环境要求
- **更新**：.gitignore 添加临时测试目录

### 🔧 Refactor
- **重构**：build.ts/fix.ts 提取共享逻辑到 step-executor.ts（-165 行）

---

## [1.0.13] - 2026-05-28

### ✨ Features

#### P0: Executor 配置基础设施
- **新增**：`src/shared/executor-config.ts` — executors.yaml 配置加载器
- **新增**：`src/shared/types.ts` — ExecutorConfig、ExecutorMode、ExecutorProvider 类型
- **新增**：`.codecgc/config/executors.yaml` 配置文件格式
- **功能**：loadExecutorConfig()、getLightweightModeConfig()、getFullModeConfig()

#### P0: Init 模式选择
- **新增**：`codecgc.init` 支持 `mode`、`backend`、`frontend` 参数
- **新增**：自动生成 executors.yaml 和按需生成 .mcp.json
- **新增**：智能推荐信息（包含安装提示）
- **模式**：轻量模式（只用 Claude）/ 完全模式（Codex + OpenCode/Gemini）

#### P1: 路由和执行配置感知
- **新增**：`route.ts` 读取 executors.yaml，轻量模式全部路由到 Claude
- **新增**：`executor.ts` callExecutor() 根据配置选择执行路径
- **新增**：callClaudeExecutor() 轻量执行器
- **新增**：callOpenCodeExecutor() OpenCode 执行器
- **改进**：route 返回 mode 和 actual_provider 字段

---

## [1.0.12] - 2026-05-27

### ✨ Features

#### OpenCode MCP 集成
- **新增**：`opencodemcp` MCP 服务器，支持 OpenCode CLI 作为前端执行器
- **新增**：`opencode` 通用会话执行器工具
- **新增**：`implement_frontend_task` 前端任务执行器（OpenCode 版本）
- **架构**：复用双路由策略（HTTP 优先 + Stdio fallback），与 Codex/Gemini 一致
- **配置**：`codecgc.init` 自动生成 `.mcp.json` 包含 `opencode` 服务器配置
- **CLI**：`cgc-mcp opencodemcp` 启动 OpenCode MCP 服务器
- **HTTP**：`cli-http-service.cjs` 已支持 `opencode` CLI 类型

### 🔧 Improvements
- **类型**：新增 `OpenCodeOptions` 接口到 `shared/types.ts`
- **路径解析**：`resolveCliCommand` 支持 `@opencode-ai/opencode` 包路径

---

## [1.0.2] - 2026-05-24

### 🐛 Fixes

#### 初始化诊断可见性
- **修复**：`codecgc.init` 返回项目级 skills 的源目录、目标目录、新增/跳过列表和 warnings，避免 `/cgc-init` 静默成功但无法判断 skills 是否释放
- **修复**：`codecgc.doctor` 检查 `cgc`、`cgc-init`、`cgc-mcp` 是否在 PATH 中，便于定位终端命令不可用问题

#### `.codecgc/` 命名一致性
- **修复**：README、skills、CLI 描述和 doctor 提示统一使用 `.codecgc/` 与 `.codecgc/config/routing.yaml`
- **修复**：用户可见提示不再误写为 `codecgc/` 或 `model-routing.yaml`

### 📝 Docs
- 新增 `cgc-init` 命令不可用、项目级 skills 未显示的排障说明

---

## [1.0.1] - 2026-05-24

### 🐛 Fixes

#### `/cgc-init` skill 不被 Claude Code 识别
- **问题**：postinstall 把 skill 释放为扁平 `.md` 文件，Claude Code 要求目录结构 `<name>/SKILL.md`
- **修复**：`scripts/postinstall.cjs` 全局只释放 `cgc` + `cgc-init` 到 `~/.claude/skills/<name>/SKILL.md`，并清理旧扁平文件

#### 终端 `cgc-init` 命令不存在
- **问题**：`package.json` bin 未注册 `cgc-init`
- **修复**：新增 `bin/cgc-init.js` 入口（代理到 `cgc init`），在 bin 字段声明

#### 项目级 skills 自动释放
- **新增**：`codecgc.init` 执行时把 `cgc-entry`、`cgc-plan` 等其余 skill 释放到项目 `.claude/skills/<name>/SKILL.md`
- **影响**：全局只放 2 个入口 skill，初始化后项目内才看到完整命令集

### 📝 Docs
- README、`skills/cgc.md`、`skills/cgc-init.md`、`skills/cgc-doctor.md` 中 `codecgc/` → `.codecgc/`，与代码实际行为对齐

---

## [0.4.5] - 2026-05-24

### 🔒 Hardening

#### #1 workflow.yaml 文件锁
- **问题**：并发 read-modify-write 可能丢失 session_id
- **修复**：writeWorkflow 使用 `.lock` 文件 + 重试机制，防止并发覆盖
- **机制**：`writeFile(lockFile, pid, { flag: "wx" })` 原子创建 + 10 次重试 + 死锁保护

#### #2 audit 文件名加随机后缀
- **问题**：同毫秒写入同 step 的 audit 会覆盖
- **修复**：文件名格式改为 `${stepId}-${timestamp}-${randomHex(6)}.json`
- **影响**：即使并发写入也不会碰撞

#### #3 continue session_id 验证增强
- **问题**：`step.session_id=""` 时允许任意 session_id 续接
- **修复**：
  - 显式检查 `!== undefined && !== ""`
  - 如果 step 从未执行过（无 session_id），拒绝 continue 并提示先 build/fix

#### #9 MCP 参数大小限制（DoS 防护）
- **问题**：超长 description/paths 可能导致 CPU/内存耗尽
- **修复**：server.ts 入口添加 `validateInputSize()`
  - 字符串字段：最大 5000 字符
  - 数组字段：最大 100 元素
- **验证**：6000 字符 description → `"参数 description 超过最大长度 5000 字符"`

#### #11 YAML 显式安全 schema
- **问题**：依赖 js-yaml 4.x 默认行为，未来升级可能引入风险
- **修复**：所有 `yaml.load/dump` 显式传入 `{ schema: yaml.JSON_SCHEMA }`
- **影响**：即使库行为变更也不会引入反序列化攻击

---

## [0.4.4] - 2026-05-24

### 🔒 Security Fixes

#### slug 路径穿越防护（Critical）
- **问题**：slug 参数直接拼接到路径，攻击者传 `../../../../tmp/evil` 可逃逸项目目录
- **修复**：paths.ts 新增 `validateSlug()` + `assertWithinRoot()`，拒绝含 `..`、`/`、`\` 的 slug
- **影响**：所有使用 slug 的工具（entry/build/fix/test/review/manual/continue）

#### step.paths 路径穿越防护（High）
- **问题**：step.paths 可包含 `../../../etc/passwd`，传递给执行器
- **修复**：paths.ts 新增 `validateStepPaths()`，拒绝绝对路径和 `..` 开头的路径。plan/build/fix/test/continue 均调用
- **影响**：阻止执行器操作项目根之外的文件

#### codexmcp sandbox 提权防护（Medium）
- **问题**：implement_backend_task 允许调用者传 `danger-full-access` 提权
- **修复**：移除 sandbox 参数，硬编码为 `workspace-write`
- **影响**：Codex 执行器始终在安全沙箱内运行

### 🔥 Critical Fixes

#### inferWorkflowState 判断 result.success
- **问题**：build 失败也写 audit，状态被误判为 awaiting-review
- **修复**：检查最新 audit 的 `result.success`，失败时返回 awaiting-build/fix
- **影响**：build 失败后正确引导用户重试而非 review

#### rejected → skipped 死锁修复
- **问题**：review rejected 后 step.status="skipped"，无法恢复
- **修复**：新增 `reopen` 决策，允许将 skipped 步骤恢复为 pending
- **影响**：误操作 rejected 后可通过 `review reopen` 恢复

### ✅ Bug Fixes

#### review.ts 过滤 review audit
- **问题**：sort().pop() 可能取到 review audit 而非执行 audit
- **修复**：从最新往前遍历，找第一个非 review 的 audit 进行检查

#### audit.ts 过滤 review audit
- **问题**：sort().reverse()[0] 同样可能取到 review audit
- **修复**：遍历过滤出执行类 audit 再取最新

#### manual audit dry-run 误报
- **问题**：manual audit 的 sessionId="" 触发 "可能是 dry-run" 警告
- **修复**：检查 audit.kind !== "manual" 后才检查 sessionId

#### nextPendingStep 跳过 docs/orchestration
- **问题**：build/fix 自动选步骤时可能选到 docs 步骤导致抛错
- **修复**：nextPendingStep 新增 skipManual 参数，build/fix 传 true

#### CLI parseInt NaN 处理
- **问题**：--timeout 传非数字时 parseInt 返回 NaN
- **修复**：新增 parseTimeout() 函数，NaN 时回退到 600

#### CLI JSON.parse 友好错误
- **问题**：MCP 返回非 JSON 时显示 "Unexpected token" 错误
- **修复**：JSON.parse 加 try/catch，显示前 200 字符内容

### 📊 工具集（15 个）

| 类别 | 工具 |
|------|------|
| 核心工作流（7） | entry, plan, build, fix, test, review, manual |
| 决策辅助（3） | explain, route, history |
| 项目治理（4） | init, status, doctor, continue |
| 工作流审计（1） | audit |

---

## [0.4.2] - 2026-05-23

### ✅ Fixes (P1 + P2)

#### #2 修复 continue 工具缺失 audit 记录（P1）
- **问题**：`continue.ts` 调用执行器后不写 audit，导致审计链断裂
- **修复**：调用执行器后立即写入 `kind: "continue"` 的 audit 记录

#### #7 修复路径检查时机（P2）
- **问题**：原 `review.ts` 在审核时才检查路径越界，但代码可能已被执行器修改
- **修复**：在 `build/fix/test/continue` 调用执行器**之前**添加路径归属验证

---

## [0.4.1] - 2026-05-23

### 🔥 Critical Fixes (P0)

#### #1 修复 build/fix/test 与 review 的状态管理冲突
- **修复**：执行成功后保持 pending 状态，approved 时才标记 done

#### #4 修复 inferWorkflowState 的 "awaiting-review" 状态永不触发
- **修复**：重新设计状态推断逻辑，根据最新 audit 类型判断状态

#### #5 review 工具补充 audit 记录

#### #3 review 工具前置检查增强

---

## [0.4.0] - 2026-05-23

### Features
- ✅ 完整 14 个工具实现
- ✅ 核心工作流（6）：entry / plan / build / fix / test / review
- ✅ 决策辅助（3）：explain / route / history
- ✅ 项目治理（4）：init / status / doctor / continue
- ✅ 工作流审计（1）：audit

### Initial Release
- 纯 TypeScript 重写 CodeCGC
- 消除 Python 依赖
- 新 workflow.yaml 格式
- MCP 架构（codecgcmcp + codexmcp + geminimcp）
