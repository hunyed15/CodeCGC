---
name: cgc
description: CodeCGC 单入口 - 自然语言需求自动路由到合适的工作流
---

CodeCGC 单入口命令。根据用户的自然语言需求自动决定流程。

用户输入格式：`/cgc <自然语言需求>`

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc` 后必须根据需求类型实际调用对应的 MCP 工具；如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用 `cgc` CLI 回退。

判断逻辑：

1. **如果是只读检阅/状态类请求**（包含"检阅"、"查看进度"、"当前进度"、"状态"、"历史"、"体检"、"doctor"、"status"、"history"）→ 不创建 workflow，直接执行只读检阅流程
2. **如果项目未初始化**（无 `.codecgc/` 目录）→ 先 `/cgc-init`，然后继续
3. **如果是修复类需求**（包含"修复"、"bug"、"fix"、"错误"）→ 用 `codecgc.entry({ kind: "issue" })` 创建 issue workflow
4. **否则** → 用 `codecgc.entry({ kind: "feature" })` 创建 feature workflow
5. 创建后自动进入规划阶段（`/cgc-plan`），询问用户确认或调整步骤
6. 用户确认后自动执行 `/cgc-build` 或 `/cgc-fix`
7. 执行成功后自动进入审核

## 只读检阅流程

当用户要求“检阅当前项目文档和进度”、“看一下现在做到哪了”、“查看 CodeCGC 状态/历史/环境”时，禁止新建 workflow，必须实际读取状态：

1. 调用 `codecgc.status({ filter: "all" })`
2. 调用 `codecgc.history({ limit: 20 })`
3. 调用 `codecgc.doctor({ cd: process.cwd() })`
4. 读取项目中的关键文档（如 `README.md`、`docs/**`、`.codecgc/config/**`）并与 workflow 状态对照
5. 输出“当前进度、活跃 workflow、已关闭 workflow、环境问题、文档与实现不一致、下一步建议”

如果 MCP 工具不可用或没有返回内容，立刻用终端回退：

```bash
cgc status all
cgc history --limit 20
cgc doctor
```

如果 `cgc status/history/doctor` 不可用，再尝试兼容别名：

```bash
cgc-status all
cgc-history --limit 20
cgc-doctor
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在没有真实返回的情况下要求用户自行执行命令并贴输出。

## 模式感知

读取 `.codecgc/config/executors.yaml` 判断当前模式：

### 轻量模式（mode: lightweight）
- `codecgc.route` 会返回 `mode: "lightweight"`，所有路径由 Claude 处理
- `codecgc.build/fix` 会返回任务描述，Claude 应直接用 Edit/Write 工具执行代码
- 流程更轻快：需求 → 规划 → Claude 执行 → 审核

### 完全模式（mode: full）
- `codecgc.route` 返回具体的 executor 和 actual_provider
- `codecgc.build/fix` 通过 Codex/Gemini/OpenCode 执行代码
- Claude 负责规划、审核、验收，不直接编写代码

## 执行器说明

完全模式下，根据 `actual_provider` 字段判断使用哪个执行器：
- `codex` → Codex CLI（后端代码，HTTP 优先 + worker fallback）
- `gemini` → Gemini CLI（前端代码，HTTP 优先 + worker fallback）
- `opencode` → OpenCode CLI（前端代码，HTTP 优先 + worker fallback）
- `claude` → Claude 直接处理（无需外部工具）

整个流程对用户透明，但每个关键决策点（规划完成、执行完成）需要确认。
