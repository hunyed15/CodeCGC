# CodeCGC 执行审计

## 1. 目的

这份文档定义委派执行后生成的 audit 产物。

当前写入入口：

- `scripts/run_codecgc_task.py`

每一次委派的 `build` 或 `fix` 执行，都应生成一个 audit 文件。

## 2. 当前存放位置

审计文件默认存放在：

- `codecgc/execution/`

如果工作流属于 fixture，则会写入：

- `codecgc/fixtures/execution/`

## 3. 文件规则

每次执行写入一个 JSON 文件：

- `{task_id}.json`

当同一个 `task_id` 被再次执行时，应覆盖旧文件，而不是无限追加。

## 4. 顶层必要字段

每个 audit 文件至少必须包含：

- `product`
- `version`
- `mode`
- `timestamp`
- `task_id`
- `target`
- `tool_name`
- `target_paths`
- `route_notes`
- `routing_file`
- `source`
- `task_summary`
- `constraints`
- `acceptance_criteria`
- `cd`
- `requested_session_id`
- `result`

## 5. `result` 区块

`result` 区块至少必须包含：

- `success`
- `outcome`
- `task_id`
- `session_id`
- `summary`
- `changed_files`
- `policy_checks`
- `risks`
- `error`

`source` 区块当前也可能携带：

- `artifact_class`

## 6. `file_evidence` 区块

`file_evidence` 当前用于补充本地证据，应尽量包含：

- `evidence_source`
- `workspace_changed_files`
- `verified_changed_files`
- `out_of_scope_changed_files`
- `file_diffs`
- `evidence_confidence`

当可用时，`file_diffs` 还会总结本地观察到的文件变化，例如：

- `path`
- `change_type`
- `before_hash`
- `after_hash`
- `before_size`
- `after_size`
- `before_preview`
- `after_preview`
- `in_scope`

## 7. 允许的结果值

当前常见 `outcome` 包括：

- `done`
- `split-required`
- `design-gap`
- `blocked`
- `executor-failure`

## 8. 审核契约

`cgc-review` 在验收前必须读取 audit 文件。

audit 是最小机器可读执行证据，至少回答这些问题：

- 哪个执行器执行了当前步骤
- 路由到的是哪些路径
- 执行返回了什么结果
- 哪些策略检查通过或失败了
- 当前步骤是否具备进入审核的证据基础

## 9. 非目标

audit 不是最终验收报告。

它只负责执行证据层。
最终验收、回写和发布判断仍然属于 Claude。
