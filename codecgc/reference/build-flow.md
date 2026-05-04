# CodeCGC 功能开发流程

## 1. 目的

这份文档定义 `cgc-build` 的标准行为。

它是 CodeCGC 在功能开发场景下的受控执行流程。

## 2. 适用范围

`cgc-build` 只处理“需求已经足够清晰、可以进入执行”的新能力开发工作。

它必须：

- 使用 `codecgc/features/` 下的 feature 产物
- 遵守 CodeCGC 的执行归属规则
- 不绕过既有步骤契约直接自由执行

## 3. 标准流程阶段

`cgc-build` 应按以下顺序推进：

1. 定位或初始化 feature 上下文
2. 检查设计是否已具备执行条件
3. 选出当前唯一可执行的功能开发步骤
4. 校验该步骤的 `codecgc` 契约
5. 通过 `scripts/run_codecgc_task.py` 发起委派执行
6. 收集结构化结果与 audit 路径
7. 把结果交给 `cgc-review`

## 4. 执行前检查

在真正执行之前，Claude 必须确认：

- 功能目标已经清楚
- 当前步骤只属于一个执行器
- 当前步骤具备本地验收条件
- 当前步骤没有混入未来工作

只要这些条件不满足，就必须回到规划或设计阶段，而不是继续执行。

## 5. 步骤契约检查

当前步骤必须包含合法的 `codecgc` 区块，至少包括：

- `kind`
- `task_id`
- `task_summary`
- `target_paths`
- `constraints`
- `acceptance`
- `cd`

如果这个区块缺失、混合或仍然模糊，那么该步骤不可执行。

## 6. 委派规则

执行必须通过：

- `scripts/run_codecgc_flow_step.py`
- `scripts/run_codecgc_task.py`

不要在已有合法步骤契约的情况下，手工重拼执行器 prompt 直接发起执行。

## 7. 结果采集规则

`cgc-build` 必须收集：

- `success`
- `task_id`
- `SESSION_ID`
- `summary`
- `changed_files`
- `policy_checks`
- `risks`
- `audit.path`

audit 产物属于执行证据的一部分。
后续审核不能只依赖自由文本聊天结果。

如果执行失败，`cgc-build` 不能静默继续，而必须分类失败原因，例如：

- 范围错误
- 设计缺口
- 环境或工具问题
- 执行器失败

## 8. 结束状态

`cgc-build` 只能结束在以下几种状态之一：

- 已成功委派，等待 `cgc-review`
- 已退回规划或设计
- 被环境或工具问题阻塞
- 因步骤不可执行而拒绝继续
