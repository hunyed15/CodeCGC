# CodeCGC 执行器契约

## 1. 目的

这份文档定义 CodeCGC 工作流运行时与执行器 MCP 适配层之间的标准执行契约。

## 2. 当前执行器

前端执行器工具：

- `implement_frontend_task`

后端执行器工具：

- `implement_backend_task`

## 3. 成功返回的必要字段

当执行成功时，两类执行器都必须返回：

- `success`
- `task_id`
- `SESSION_ID`
- `summary`
- `agent_messages`
- `changed_files`
- `policy_checks`
- `risks`

可选字段：

- `all_messages`

## 4. 失败返回的必要字段

当执行失败时，两类执行器至少必须返回：

- `success`
- `task_id`
- `policy_checks`
- `error`

## 5. 运行时归一化规则

工作流运行时允许在写入 audit 之前，对执行器输出做标准化整理。

当前归一化入口：

- `scripts/run_codecgc_task.py`

audit 层最终会稳定写入：

- `result.success`
- `result.outcome`
- `result.task_id`
- `result.session_id`
- `result.summary`
- `result.changed_files`
- `result.policy_checks`
- `result.risks`
- `result.error`

## 6. 当前语义规则

两个执行器目前在工作流层被视为共享同一套语义：

- `success` 表示执行器返回了结构化结果
- `changed_files` 是审核会消费的范围内文件证据
- `policy_checks` 是机器可读的策略轨迹
- `SESSION_ID` 是后续续跑所需的会话句柄

## 7. 可审核规则

执行器返回成功，并不等于已经可以直接通过审核。

要进入可通过审核状态，还必须额外满足：

- 不是 `dry-run`
- 执行归属正确
- 变更文件没有超出路由范围
- audit 最终结果为 `done`

## 8. 当前限制

执行器成功时返回的 `changed_files`，本质上仍然首先来自执行器自身报告，而不是完整独立的版本历史证明。

CodeCGC 已经在 audit 层补充了工作区快照证据，但它还不是完整的 git 级差异证明系统。
