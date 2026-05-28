---
name: cgc
description: CodeCGC 单入口 - 自然语言需求自动路由到合适的工作流
---

CodeCGC 单入口命令。根据用户的自然语言需求自动决定流程。

用户输入格式：`/cgc <自然语言需求>`

判断逻辑：

1. **如果项目未初始化**（无 `.codecgc/` 目录）→ 先 `/cgc-init`，然后继续
2. **如果是修复类需求**（包含"修复"、"bug"、"fix"、"错误"）→ 用 `codecgc.entry({ kind: "issue" })` 创建 issue workflow
3. **否则** → 用 `codecgc.entry({ kind: "feature" })` 创建 feature workflow
4. 创建后自动进入规划阶段（`/cgc-plan`），询问用户确认或调整步骤
5. 用户确认后自动执行 `/cgc-build` 或 `/cgc-fix`
6. 执行成功后自动进入审核

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
