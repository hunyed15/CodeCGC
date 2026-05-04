# CodeCGC 运行时边界

## 1. 目的

这份文档用来区分“真实运行时产物”和“示例 / 校验用 fixture”。

这个边界很重要，因为 `route / build / fix / review` 会把 `codecgc/` 下的文件当成真实工作流状态来消费。

## 2. 真实运行时目录

下面这些目录属于当前活跃产品状态：

- `codecgc/features/`
- `codecgc/issues/`
- `codecgc/execution/`

下面这些目录属于 fixture 校验根：

- `codecgc/fixtures/features/`
- `codecgc/fixtures/issues/`
- `codecgc/fixtures/execution/`

fixture 不只是“示例文本”，它们同样会参与本地回归与行为验证，因此不能随便混放。

## 3. fixture 风险

在本地开发阶段，一些 demo 或校验文件可能长期存在。

这可以接受，但必须遵守一条规则：

- 校验必须是串行且显式的

不要假设 `codecgc/execution/` 里最新的 audit 一定对应当前工作流。
所有控制逻辑都必须按精确步骤身份匹配。

## 4. 当前控制规则

当前运行时遵守下面这些规则：

- `route` 只检查当前 `pending` 的可执行步骤
- audit 必须按精确 `task_id` 匹配
- review 必须按精确 `task_id` 与 `step_number` 匹配
- `artifact_class` 会从工作流产物继续传递到 audit 元数据
- `dry-run` audit 只是预演证据
- 只有非 `dry-run` 且成功 `done` 的执行结果，才算 review-ready

## 5. 操作建议

当你在校验一个 fixture 工作流时，建议顺序是：

1. 先看 checklist 或 fix 文件
2. 确认当前哪一步是 `pending`
3. 只检查与该步骤匹配的 audit
4. 再运行 `route`
5. 然后运行 `build` 或 `fix`
6. 真实执行完成后再写 review

## 6. 持续清理方向

当前 fixtures 已经有目录级隔离，但后续仍应继续收口：

- 让长期产品示例与临时校验文件分得更清楚
- 保持 `artifact_class` 作为机器意图标记
- 继续规范历史 audit 路径

如果历史 audit 里还保留旧仓库名或旧执行根，可使用：

- `python scripts/normalize_codecgc_audits.py`

如果历史 demo 工作流还混在活跃目录里，可使用：

- `python scripts/migrate_demo_workflows_to_fixtures.py`
