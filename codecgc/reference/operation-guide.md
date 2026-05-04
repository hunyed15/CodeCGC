# CodeCGC 操作指南

## 1. 目的

这份文档是 CodeCGC 的本地使用实操指南。

统一产品命令面是：

- `cgc`
- `cgc-install`
- `cgc-entry`
- `cgc-plan`
- `cgc-build`
- `cgc-fix`
- `cgc-review`
- `cgc-route`
- `cgc-status`
- `cgc-doctor`
- `cgc-package-audit`
- `cgc-external-audit`
- `cgc-release-readiness`
- `cgc-lifecycle`

底层实现入口如 `scripts/codecgc_cli.py`、`scripts/route_codecgc_workflow.py` 只属于维护者调试层。

默认原则：

- 日常使用优先走 `cgc-*`
- 调试运行时本身时再看 Python 脚本入口

## 2. 首次接入顺序

如果你是第一次把 CodeCGC 接入某个项目，建议顺序是：

1. 在目标项目根目录运行 `cgc-install`
2. 运行 `cgc-status`，必要时再运行 `cgc-doctor`
3. 用 `cgc "<自然语言需求>"` 或 `cgc-entry` 开始

最小示例：

```bash
cgc-install
cgc-status
cgc "新增一个登录页面，放在 src/components/LoginForm.tsx"
```

如果当前 shell 目录不是目标项目根目录：

```bash
cgc-install --workspace D:\Projects\MyApp
cgc-status --workspace D:\Projects\MyApp
```

## 3. 什么时候切到明确子命令

只有在阶段已经明确时，才切到工作流子命令：

- `cgc-plan`：还需要规划或澄清
- `cgc-build` / `cgc-fix`：当前步骤已具备执行条件
- `cgc-review`：已经存在 audit，等待审核决策
- `cgc-route`：只想知道下一步推荐命令
- `cgc-external-audit`：只想看外部能力接入状态
- `cgc-release-readiness`：发布或长期维护前做总检查
- `cgc-lifecycle`：快速判断仓库现在处于哪个生命周期阶段

## 4. 主命令用法

### 4.1 单入口

```bash
cgc "新增一个登录页面，放在 src/components/LoginForm.tsx"
cgc "继续刚刚的工作"
cgc --request "现在下一步该做什么"
cgc --latest
```

`cgc` 是意图优先入口，默认输出更适合人直接阅读的摘要。

如果需要完整结构化结果，使用：

```bash
cgc-entry --request "新增一个登录页面，放在 src/components/LoginForm.tsx"
```

### 4.2 规划

```bash
cgc-plan --flow feature --slug demo-login-ui --summary "Demo login UI feature" --target-path src/components/LoginForm.tsx --kind frontend
cgc-plan --flow issue --slug demo-sync-bug --summary "Demo sync bug fix" --target-path backend/src/sync.py --kind backend
```

当结构化信息已知时，优先显式传入目标、范围、验收和风险，而不是只给最短摘要。

## 5. `plan` 的当前行为

`cgc-plan` 当前不仅会建骨架，还会做步骤塑形：

- 前后端混合目标路径会拆成多个可执行步骤
- 共享或未知路径会转成仅规划步骤
- 只要仍存在仅规划步骤，`route` 就会继续把流程留在 `cgc-plan`
- 每个可执行步骤都可以拥有自己的 action、task summary 与 acceptance

`plan` 还会返回 `planning_status`，当前常见值包括：

- `ready-for-build`
- `ready-for-fix`
- `needs-clarification`
- `needs-roadmap`

## 6. 执行步骤

```bash
cgc-build --slug 2026-05-01-demo-login-ui --step-number 1 --dry-run
cgc-fix --slug 2026-05-01-demo-sync-bug --step-number 1 --dry-run
```

`build` 与 `fix` 当前不会只返回简单成功/失败，而会补充：

- `state`
- `failure_type`
- `recommended_command`
- `next`
- `audit_path`

当未显式传入 `--step-number` 时，运行时会自动选择下一个可执行的 `pending` 步骤。

## 7. 审核回写

```bash
cgc-review --audit-file codecgc/execution/demo-login-ui-step-1.json --decision accepted
```

`review` 现在是审核控制点，而不是单纯回写助手。

它会在以下场景把请求的 `accepted` 降级为 `changes-requested`：

- 只有 `dry-run`
- 执行器归属不匹配
- 变更文件越界
- 执行器没有成功返回 `done`
- 本地证据与执行器自报不一致

审核回写后，匹配步骤的状态也会同步更新：

- `accepted` -> `done`
- `changes-requested` -> `pending`

## 8. 路由判断

```bash
cgc-route --flow feature --slug 2026-05-01-demo-login-ui
```

`route` 当前会综合三层证据：

- 工作流产物完整性
- 当前步骤最近一次执行 audit
- acceptance / fix-note 中最近一次审核结论

常见结果包括：

- 推荐 `cgc-build` 或 `cgc-fix`
- 推荐 `cgc-review`
- 不再推荐任何命令，表示当前流程已关闭

对于多步骤工作流，`route` 现在会优先跟随“当前 pending 步骤”，而不是简单相信历史上最后一次审核结果。

## 9. 推荐操作闭环

推荐顺序始终是：

1. `cgc-plan`
2. 必要时补全或细化产物
3. `cgc-build` 或 `cgc-fix`
4. 检查 audit
5. `cgc-review`

## 10. 维护与发布检查

如果你当前不是在推进某个 feature / issue，而是在维护 CodeCGC 本身，建议改用下面这条链路：

1. `cgc-status`
2. `cgc-doctor`
3. `cgc-package-audit`
4. `cgc-external-audit`
5. `cgc-release-readiness`
6. `cgc-lifecycle`

其中：

- `cgc-external-audit` 用来判断第三方能力是否处于“正式接入 / 规划中 / 本地漂移”哪一种状态
- `cgc-release-readiness` 用来把安装、运行时、发布包、外部接入与生命周期资产汇总成一个结论
- `cgc-lifecycle` 用来把 roadmap、workflow 与 execution 当前分布汇总成生命周期阶段

## 11. Fixture 与历史修复

如果只是创建验证样例工作流，应使用：

```bash
python scripts/codecgc_cli.py init --flow feature --slug fixture-demo --summary "Fixture demo" --artifact-class fixture
```

如果历史 audit 仍在错误目录或保留旧路径，可运行：

```bash
python scripts/normalize_codecgc_audits.py
```

如果历史 demo 工作流仍在 product 目录，可运行：

```bash
python scripts/migrate_demo_workflows_to_fixtures.py
```

如果历史 acceptance / fix-note 缺少或保留旧审核策略字段，可运行：

```bash
python scripts/refresh_codecgc_review_policy.py --write
```

这属于维护修复命令，不是普通用户日常主流程。

## 12. 产品规则

`cgc-plan`、`cgc-build`、`cgc-fix`、`cgc-review`、`cgc-route` 必须共同遵守同一套运行时时序。

技能层定义工作流规则。
CLI 层提供本地执行便利。

## 13. 底层调试入口

以下入口只在维护 CodeCGC 自身、调试产品壳、或直接验证运行时层时使用：

```bash
python scripts/codecgc_cli.py entry --request "新增一个登录页面，放在 src/components/LoginForm.tsx"
python scripts/codecgc_cli.py plan --flow feature --slug demo-login-ui --summary "Demo login UI feature" --target-path src/components/LoginForm.tsx --kind frontend
python scripts/codecgc_cli.py build --slug 2026-05-01-demo-login-ui --step-number 1 --dry-run
python scripts/codecgc_cli.py fix --slug 2026-05-01-demo-sync-bug --step-number 1 --dry-run
python scripts/codecgc_cli.py review --audit-file codecgc/execution/demo-login-ui-step-1.json --decision accepted
python scripts/codecgc_cli.py route --flow feature --slug 2026-05-01-demo-login-ui
python scripts/route_codecgc_workflow.py --flow feature --slug 2026-05-01-demo-login-ui
```
