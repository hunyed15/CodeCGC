# CodeCGC 执行模型

## 1. 目的

CodeCGC 把“工作流控制”和“代码执行”明确分层。

工作流层决定：

- 当前在做哪一步
- 这一步是否已经可执行
- 这一步应该交给哪个模型

执行层负责：

- 通过 MCP 调用正确执行器
- 落地代码改动
- 产出可审核的结构化证据

## 2. 当前运行链路

当前标准链路如下：

1. 用户通过 `cgc` 或 `cgc-entry` 进入工作流
2. Claude 读取现有工作流产物
3. Claude 识别当前唯一可推进的执行步骤
4. Claude 将步骤打包为机器可执行任务
5. 运行时调用对应的执行入口
6. 执行入口再桥接到底层任务执行脚本
7. MCP 将任务委托给 Gemini 或 Codex
8. 执行结果被写入 audit 产物
9. Claude 基于 audit、步骤契约和工作流状态继续审核与回写

简化理解：

- Claude 决定“做什么、何时做、交给谁”
- Gemini / Codex 负责“按边界把代码做出来”

## 3. 路由输入

路由规则主要声明在：

- `model-routing.yaml`

运行时 guardrail 主要声明在：

- `.mcp.json`
- `.claude/settings.local.json`
- `.codex/codecgcrc.json`
- `.gemini/policies/codecgc-policy.toml`
- `.claude/hooks/route-edit.ps1`

这些文件一起负责“不能越界”。

## 4. 允许的执行结果

一个代码步骤最终只允许落在下面这些状态之一：

- `ready`：单模型范围明确，可以立即执行
- `split-required`：前后端混合或 shared 范围，必须先拆分
- `design-gap`：步骤描述不足，仍需补设计
- `blocked`：环境、权限或工具阻塞
- `done`：执行器已经返回完整结果

这些状态不是面向用户的产品口语，而是运行时判断的机器语义。

从 `P6-1` 开始，`split-required` 不再只是一个阻断码。
当运行时能明确看出哪些路径属于前端、后端或 shared 时，还会额外返回结构化拆分建议，供单入口恢复链和 `cgc-plan` 继续复用。

## 5. 什么叫“可执行步骤”

只有同时满足下面条件，步骤才算真正 ready：

- 只属于一个执行器
- 不包含 shared 或 mixed 范围
- `target_paths` 足够小且明确
- 有当前步骤自己的验收标准
- 没有把未来工作偷偷塞进当前执行

如果做不到这一点，就不该执行，而应该回到拆分或设计。

## 6. 执行器契约

当前前端执行器是：

- `implement_frontend_task`

当前后端执行器是：

- `implement_backend_task`

执行器返回结果时，至少应包含：

- `success`
- `task_id`
- `SESSION_ID`
- `summary`
- `changed_files`
- `policy_checks`
- `risks`

运行时必须把这些字段持久化到 audit 中，供后续审核使用。

参见：

- `codecgc/reference/execution-audit.md`
- `codecgc/reference/executor-contract.md`

## 7. 产品原则

CodeCGC 不相信“提示词里说了不要越界”就足够。

正确顺序必须是：

1. 先定义流程
2. 再生成机器可读步骤契约
3. 再触发 MCP 执行
4. 再用 hook 和审核控制做兜底

文档负责解释系统。
流程控制负责真正约束系统。
