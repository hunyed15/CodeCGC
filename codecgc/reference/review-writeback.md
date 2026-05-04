# CodeCGC 审核回写

## 1. 目的

这份文档说明 `cgc-review` 如何在委派执行完成后，把审核结果写回工作流产物。

当前主入口：

- `scripts/write_codecgc_review.py`

## 2. 输入

审核回写至少需要：

- `audit-file`
- `decision`

可选输入：

- `risk`
- `next-step`
- `force`

## 3. 回写目标

脚本会从 audit 的 `source` 区块解析回写目标。

当前映射规则：

- feature audit -> `{slug}-acceptance.md`
- issue audit -> `{slug}-fix-note.md`

## 4. 审核规则

审核不等于“执行成功”。

回写结果必须覆盖这些事实：

- 当前执行步骤是否通过审核
- 执行归属是否正确
- 实际发生了哪些变更
- 剩余风险是什么
- 下一步应该回到哪个阶段

当出现以下情况时，即使请求的是 `accepted`，审核也必须降级为 `changes-requested`：

- 本次只有 `dry-run`
- 执行器归属与路由目标不一致
- 变更文件超出 `target_paths`
- 真实执行后没有观察到已验证的范围内变更
- 执行器没有返回成功的 `done` 结果

## 5. 当前输出契约

高层审核入口当前会返回：

- `requested_decision`
- `final_decision`
- `review_state`
- `recommended_command`
- `recommended_action_kind`
- `fallback_stage`
- `policy_reason`
- `scope_check`
- `executor_check`
- `verification`
- `remaining_risk`
- `next_step`

这些字段属于长期稳定的审核结果契约，供：

- `cgc-review`
- `cgc-route`
- `cgc-entry`
- `operator_brief.machine_next_action`

共同消费。

## 6. 回写内容

审核回写除了更新 acceptance / fix-note 正文，还会同步：

- 当前被审核的 `task_id`
- 当前被审核的 `step_number`
- 当前步骤的 checklist / fix YAML 状态

状态推进规则：

- `accepted` -> `done`
- `changes-requested` -> `pending`

这样 `route / explain / continue` 才能在多步骤工作流中，把审核结论匹配回正确步骤。

## 7. 证据策略

只有真实执行结果才能成为“可通过审核”的证据。

`dry-run` audit 仍然可以写回供检查使用，但不能被视为可直接通过审核的证据。

当本地工作区证据存在时，审核优先使用本地证据，而不是只信执行器自报的 `changed_files`。

当前还会补充这些证据字段：

- `evidence_confidence`
- `risk_classes`
- `Observed file diffs`
- `Local evidence available`
- `Reported vs local evidence alignment`

如果执行器自报与本地证据不一致，审核必须降级。

## 8. 回退阶段

审核策略当前明确区分 4 类回退阶段：

- `closed`
- `planning`
- `execution`
- `review`

这层设计的目的是减少 Claude 在读完审核结果后再做二次自由解释的成本。

上层只要消费：

- `recommended_action_kind`
- `fallback_stage`
- `policy_reason`

就可以决定下一步是关闭、回规划、回执行，还是继续停留在审核阶段。

## 9. 当前限制

当前回写仍然属于“基于工作区快照 diff 的审核控制”。

它已经强于单纯依赖执行器自报，但还不是完整的、带历史感知的 git 级差异分析。

因此以下场景仍属于后续加固范围：

- 大量 rename
- 并发编辑
- 多轮交叉执行后的证据归属判定
