# CodeCGC 功能设计文档

> 版本：2026-05-11  
> 面向：产品理解、接入评估、协作分工设计

---

## 一、产品定位

CodeCGC 是一个**以 Claude 为主控入口的多模型开发编排层**。

它解决的核心问题是：在 AI 辅助编程场景中，单一模型既要做规划又要写代码，边界模糊、过程不可追踪、结果难以验收。

CodeCGC 的解法是：**把软件交付流程显式拆开**，让每个阶段都有明确负责人、可审计的产物和机器可验证的退出条件。

```
用户需求 → Claude 规划 → CodeCGC 路由 → Codex/Gemini 执行 → audit 证据 → Claude 审核 → 工作流关闭
```

它不是一个代码生成工具，而是一个**受控的多模型协作流水线**。

---

## 二、角色分工

CodeCGC 把参与方固定为四个角色，分工不重叠：

| 角色 | 职责边界 |
|------|---------|
| **Claude** | 需求澄清、规划设计、路由决策、审核验收、文档回写、工作流状态管理 |
| **Codex**（OpenAI） | 后端代码实现、后端测试，通过 CodexMCP 桥接调用 |
| **Gemini**（Google） | 前端代码实现、前端测试，通过 GeminiMCP 桥接调用 |
| **CodeCGC** | 路由策略执行、执行审计产物管理、工作流状态闭环、write 拦截 guardrail |

**硬规则**：Claude 不直接修改受路由保护的业务代码。产品源码的写入权限只属于 Codex（后端）或 Gemini（前端）。这条规则通过两层机制强制落地：

1. **工作流层**：`cgc-build` / `cgc-fix` 打包步骤时强制路由到正确执行器
2. **Guardrail 层**：`.claude/hooks/route-edit.ps1` 拦截 Claude 的 `Edit`、`Write`、`MultiEdit`、`Bash`、`PowerShell`，阻止直接写入绕过路由

---

## 三、路由策略

路由规则的唯一来源是项目根目录的 `model-routing.yaml`。

```yaml
orchestration_paths:   # Claude 可写：codecgc/**、.claude/**、.mcp.json 等
docs_paths:            # Claude 可写：README.md、docs/** 等
frontend_paths:        # Gemini 专属：src/components/**、apps/web/** 等
backend_paths:         # Codex 专属：server/**、src/services/** 等
shared_paths:          # 必须拆分后再执行：packages/shared/**、src/types/** 等
```

路径分类决定了执行器归属：

- `frontend` → `geminimcp`（GeminiMCP）
- `backend` → `codexmcp`（CodexMCP）
- `shared` → 强制拆分，`split-first` 策略
- `unknown` → 默认拒绝，必须先加入路由表

路由策略在三个位置同时生效：
1. `scripts/codecgc_policy.py`：任务打包时的策略检查
2. `.claude/hooks/route-edit.ps1`：Claude 写入时的实时拦截
3. 审核阶段：`cgc-review` 验证执行器归属是否符合路由

---

## 四、完整业务流程

### 4.1 生命周期总览

CodeCGC 把软件交付显式分为六个阶段：

```
Define → Plan → Build → Verify → Review → Ship
```

每个阶段都有明确的退出条件，不满足条件不得进入下一阶段。

---

### 4.2 Define（需求定义）

**负责人**：Claude

**触发方式**：

```text
# Claude 内
/cgc 在 src/components/LoginForm.tsx 中新增登录页

# 命令行
cgc "在 src/components/LoginForm.tsx 中新增登录页"
```

`/cgc` 是总入口，它不执行工作流本身，只做路由判断，根据当前项目状态推荐下一步命令。

**Claude 在此阶段的输出**：
- 问题定义
- 用户可见范围与非目标
- 初步分类：`feature`（新功能）/ `issue`（问题修复）/ `refactor`（重构）/ `roadmap`（大型规划）

**退出条件**：需求清晰到可以进入规划。

---

### 4.3 Plan（规划与步骤拆分）

**负责人**：Claude（通过 `cgc-plan`）

**核心任务**：把需求拆成每个步骤只属于一个执行器的可执行单元。

**触发**：

```bash
cgc-plan --flow feature --slug demo-login-ui \
  --summary "Demo login UI feature" \
  --target-path src/components/LoginForm.tsx \
  --kind frontend
```

**规划产物骨架**（自动创建）：

Feature 类型：
```
codecgc/features/YYYY-MM-DD-{slug}/
  {slug}-design.md        # 功能设计说明
  {slug}-checklist.yaml   # 步骤契约列表
  {slug}-acceptance.md    # 验收记录（Review 阶段回写）
```

Issue 类型：
```
codecgc/issues/YYYY-MM-DD-{slug}/
  {slug}-report.md        # 问题描述
  {slug}-analysis.md      # 根因分析
  {slug}-fix.yaml         # 修复步骤契约
  {slug}-fix-note.md      # 修复记录（Review 阶段回写）
```

**步骤契约最低要求**：每个可执行步骤必须明确：
- `target_paths`：目标文件路径
- `kind`：`frontend` 或 `backend`
- `task_summary`：任务摘要
- 当前步骤的验收标准

**拆分规则**：
- 前后端混合路径 → 拆成多个单归属步骤
- `shared` 路径 → 转为规划澄清步骤，必须先解决再执行
- `unknown` 路径 → 必须先加入路由表或澄清归属

**Plan 输出状态**（`planning_status`）：
- `ready-for-build`：功能步骤可执行
- `ready-for-fix`：修复步骤可执行
- `needs-clarification`：还需要更多信息
- `needs-roadmap`：需求规模超出单一工作流，需进入 `cgc-roadmap`

**退出条件**：每个步骤都满足"一个 owner、一个 scope、一个 acceptance target"。

---

### 4.4 Build / Fix（执行）

**负责人**：Gemini（前端）/ Codex（后端）；Claude 负责打包和调度

**触发**：

```bash
# 功能开发
cgc-build --slug 2026-05-01-demo-login-ui --step-number 1

# 问题修复
cgc-fix --slug 2026-05-01-demo-sync-bug --step-number 1

# 不指定步骤时，自动选下一个 pending 步骤
cgc-build --slug 2026-05-01-demo-login-ui
```

**执行链路**：

```
cgc-build
  → scripts/build_codecgc_task.py    # 读取 checklist，打包步骤契约
  → scripts/codecgc_policy.py        # 路由策略检查
  → scripts/run_codecgc_flow_step.py # 调用 MCP 执行器
      → geminimcp（前端）或 codexmcp（后端）
  → scripts/run_codecgc_task.py      # 写入 audit 文件
```

**执行器调用**（通过 MCP 协议）：
- 前端：`implement_frontend_task`（Gemini CLI 封装）
- 后端：`implement_backend_task`（Codex CLI 封装）

两者都支持会话管理（`SESSION_ID`），可跨轮次保持上下文连续。

**执行步骤状态**：
- `ready`：单模型范围明确，可立即执行
- `split-required`：前后端混合，必须先拆分
- `design-gap`：步骤描述不足，需补设计
- `blocked`：环境或权限阻塞
- `done`：执行器已返回完整结果

**dry-run 模式**：

```bash
cgc-build --slug 2026-05-01-demo-login-ui --step-number 1 --dry-run
```

dry-run 会写入 audit 文件但不是真实执行证据。审核时若发现只有 dry-run，`cgc-review` 会强制将结果降级为 `changes-requested`。

---

### 4.5 Verify（证据收集）

**负责人**：Gemini / Codex 提供证据，Claude 判断证据是否充分

每次执行完成后，自动在 `codecgc/execution/` 生成 audit JSON 文件：

```
codecgc/execution/{task_id}.json
```

Audit 文件包含：

| 字段组 | 内容 |
|--------|------|
| `source` | 来源：flow、slug、step_number、artifact_class |
| `target` | 路由目标：tool_name、target_paths |
| `result` | 执行结果：success、outcome、changed_files、policy_checks、risks |
| `file_evidence` | 本地证据：workspace_changed_files、verified_changed_files、file_diffs |

本地证据（`file_evidence`）优先于执行器自报（`result.changed_files`）。若两者不一致，审核必须降级。

**Outcome 值**：
- `done`：执行成功
- `split-required`：需要拆分
- `design-gap`：设计缺口
- `blocked`：执行阻塞
- `executor-failure`：执行器失败

---

### 4.6 Review（审核验收）

**负责人**：Claude（通过 `cgc-review`）

这是整个流水线的**控制点**，不是简单的"写一句通过"。

**触发**：

```bash
cgc-review --audit-file codecgc/execution/demo-login-ui-step-1.json --decision accepted
```

**审核必须确认的事项**：

| 检查项 | 说明 |
|--------|------|
| 执行器归属 | 是否调用了正确的执行器（前端 → Gemini，后端 → Codex）|
| 路径边界 | 变更文件是否在 `target_paths` 范围内 |
| 证据真实性 | 是否是真实执行（非 dry-run）|
| 验收达成 | 是否满足当前步骤的 acceptance target |
| 夹带检查 | 是否混入了无关改动 |

**强制降级场景**（即使请求 `accepted` 也会变成 `changes-requested`）：
- 只有 dry-run
- 执行器归属与路由目标不一致
- 变更文件超出 target_paths
- 执行器未返回成功的 `done` 结果
- 本地证据与执行器自报不一致

**审核结果回写**：

```
accepted        → checklist 步骤状态 → done   → 写入 *-acceptance.md 或 *-fix-note.md
changes-requested → checklist 步骤状态 → pending → 工作流等待重新执行
```

**审核输出契约**（供后续路由消费）：
- `final_decision`：最终决定
- `fallback_stage`：回退阶段（`closed` / `planning` / `execution` / `review`）
- `recommended_command`：推荐的下一步命令
- `remaining_risk`：残余风险

---

### 4.7 Ship（闭环）

**负责人**：Claude

当所有步骤的 checklist 状态均为 `done` 时，工作流状态变为 `closed`。

`cgc-route` 在此时不再推荐任何命令，表示当前工作流已结束。

**Claude 输出**：
- 验收结论汇总
- 工作流产物最终回写（acceptance / fix-note）
- 变更摘要
- 残余风险说明
- 后续建议（是否需要触发 `cgc-arch`、`cgc-req`、`cgc-decide` 等长期知识沉淀）

---

## 五、工作流状态机

工作流在任意时刻处于以下五个稳定状态之一：

```
needs-planning    → 需要规划或补充设计，等待 cgc-plan
awaiting-build    → feature 步骤可执行，等待 cgc-build
awaiting-fix      → issue 修复步骤可执行，等待 cgc-fix
awaiting-review   → audit 存在，等待 cgc-review
closed            → 所有步骤完成，工作流结束
```

状态推进由 `cgc-route` 综合三层证据判断：
1. 工作流产物完整性（checklist / fix YAML 步骤状态）
2. 最近一次执行 audit
3. acceptance / fix-note 中最近一次审核结论

---

## 六、失败恢复机制

失败恢复是 CodeCGC 的**正常行为**，不是异常路径。

### 执行器失败

```
executor failure
  → state: blocked
  → failure_type: executor-failure
  → 检查 audit 和执行器输出后再重试
```

### 审核驳回（changes-requested）

```
changes-requested
  → checklist 步骤保持 pending
  → route 推荐重新执行 cgc-build / cgc-fix / cgc-test
  → 若存在可复用 session_id，下次执行带 --session-id 保持会话连续
```

### 混合路径

```
混合路径检测
  → route 推荐回到 cgc-plan
  → 返回结构化拆分建议（grouped_paths / suggested_split_steps）
  → Claude 依据拆分建议重写 checklist
```

### 测试步骤

步骤标记 `step_type: test` 时，路由到 `cgc-test`，不走 `cgc-build` 或 `cgc-fix`。

### 会话续接

同一 task_id 的多次执行可复用 session_id：

```
audit.result.session_id → 下次执行 --session-id <id>
```

session_id 不跨 task_id 或 artifact_class 复用。

---

## 七、命令面总览

### 日常入口（用户优先使用）

| 命令 | 用途 |
|------|------|
| `/cgc <需求>` | 总入口，自动路由到下一步 |
| `/cgc-plan` | 规划或补充设计 |
| `/cgc-build` | 执行功能开发步骤 |
| `/cgc-fix` | 执行问题修复步骤 |
| `/cgc-review` | 审核验收 |
| `/cgc-route` | 查看当前推荐的下一步命令 |
| `/cgc-history` | 查看最近的工作流历史 |

### 安装与健康检查

| 命令 | 用途 |
|------|------|
| `cgc-init` | 项目级安装（写入 .mcp.json、model-routing.yaml、hooks 等） |
| `cgc-start` | 查看项目首次使用入口 |
| `cgc-status` | 查看当前集成状态 |
| `cgc-doctor` | 诊断安装问题 |

### 大型规划与知识沉淀

| 命令 | 用途 |
|------|------|
| `/cgc-roadmap` | 路线图级规划（需求过大时拆成多个子工作流） |
| `/cgc-arch` | 更新架构文档（已接受的变更才写入） |
| `/cgc-req` | 更新需求文档（稳定的功能边界才写入） |
| `/cgc-decide` | 记录已接受的技术或产品决策 |
| `/cgc-learn` | 记录可复用的经验教训和常见陷阱 |
| `/cgc-refactor` | 行为保持性重构（走完整路由流程） |

### 维护与发布

| 命令 | 用途 |
|------|------|
| `cgc-package-audit` | 审计发布包运行时内容 |
| `cgc-external-audit` | 审计外部 MCP 能力注册状态 |
| `cgc-release-readiness` | 发布前总检查 |
| `cgc-lifecycle` | 判断仓库当前生命周期阶段 |

---

## 八、产物目录结构

项目安装后，CodeCGC 在目标项目中生成以下目录结构：

```
{project-root}/
├── model-routing.yaml              # 路由策略（唯一权威来源）
├── .mcp.json                       # MCP 服务注册（CodexMCP / GeminiMCP）
├── .claude/
│   ├── settings.local.json         # 权限配置
│   ├── hooks/
│   │   └── route-edit.ps1          # Write 拦截 guardrail
│   └── commands/
│       └── cgc*.md                 # slash command 定义
├── .codex/
│   └── codecgcrc.json              # Codex 执行约束
├── .gemini/
│   └── policies/
│       └── codecgc-policy.toml     # Gemini 执行约束
└── codecgc/
    ├── features/                   # 功能工作流产物
    │   └── YYYY-MM-DD-{slug}/
    │       ├── {slug}-design.md
    │       ├── {slug}-checklist.yaml
    │       └── {slug}-acceptance.md
    ├── issues/                     # 问题修复工作流产物
    │   └── YYYY-MM-DD-{slug}/
    │       ├── {slug}-report.md
    │       ├── {slug}-analysis.md
    │       ├── {slug}-fix.yaml
    │       └── {slug}-fix-note.md
    ├── execution/                  # 执行审计文件（每次执行生成一个 JSON）
    ├── roadmap/                    # 路线图规划
    ├── requirements/               # 长期需求沉淀
    ├── architecture/               # 架构文档
    ├── compound/                   # 决策与经验记录
    ├── reference/                  # 稳定契约与参考说明
    └── docs/                       # CodeCGC 生成的指南文档
```

---

## 九、安装方式

### 全局安装 CLI

```bash
npm install -g @hunyed15/codecgc --registry=https://registry.npmjs.org/
```

全局安装只提供 `cgc*` 命令，不写入 `~/.claude`。

### 项目级接入（默认方式）

```bash
cd your-project
cgc-init      # 写入项目集成文件
cgc-start        # 查看首次使用入口
cgc-status       # 确认集成状态
cgc-doctor       # 诊断问题（可选）
```

### 配套 MCP 服务安装

CodexMCP（后端执行器）：

```bash
claude mcp add codex -s user --transport stdio -- uvx --from git+https://github.com/GuDaStudio/codexmcp.git codexmcp
```

GeminiMCP（前端执行器）：

```bash
claude mcp add gemini -s user --transport stdio -- uvx --from git+https://github.com/GuDaStudio/geminimcp.git geminimcp
```

---

## 十、设计原则

**1. 流程先于信任**

CodeCGC 不依赖"提示词里说不要越界"来保证安全。正确顺序是：先定义流程 → 生成机器可读步骤契约 → 触发 MCP 执行 → hook 和审核做兜底。

**2. 证据驱动审核**

审核不等于执行成功。dry-run 不是完成证据。没有 audit 不得宣称任务完成。本地文件证据优先于执行器自报。

**3. 单一归属原则**

每个可执行步骤只能有一个 owner（Gemini 或 Codex）。混合归属必须先拆分，不得强行执行。

**4. 路径即策略**

`model-routing.yaml` 是唯一的写入权限来源。所有路由判断、guardrail 拦截、任务打包、audit 审核都消费同一套路由表，不存在多套规则。

**5. 产物即状态**

工作流状态不在内存中，而在 `codecgc/` 目录的产物文件里。`cgc-route` 通过读产物文件判断状态，会话重启不丢失进度。
