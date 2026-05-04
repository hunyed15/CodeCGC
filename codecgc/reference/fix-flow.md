# CodeCGC 问题修复流程

## 1. 目的

这份文档定义 `cgc-fix` 的标准行为。

它是 CodeCGC 在问题修复场景下的受控执行流程。

## 2. 适用范围

`cgc-fix` 只处理范围已经足够收敛的问题修复工作。

它必须：

- 使用 `codecgc/issues/` 下的 issue 产物
- 遵守 CodeCGC 的执行归属规则
- 不绕过既有步骤契约直接自由执行

## 3. 标准流程阶段

`cgc-fix` 应按以下顺序推进：

1. 定位 issue 上下文
2. 检查修复范围与执行归属
3. 选出当前唯一可执行的问题修复步骤
4. 校验该步骤的 `codecgc` 契约
5. 通过 `scripts/run_codecgc_task.py` 发起委派执行
6. 收集结构化结果与 audit 路径
7. 把结果交给 `cgc-review`

## 4. 执行前检查

在真正执行之前，Claude 必须确认：

- 问题范围已经足够收敛
- 当前修复只属于一个执行器
- 当前步骤没有混合前端与后端工作
- 当前步骤具备本地验证目标

如果这些条件不满足，就必须回到规划或范围澄清，而不是继续执行。

## 5. 步骤契约检查

当前修复步骤必须包含合法的 `codecgc` 区块，至少包括：

- `kind`
- `task_id`
- `task_summary`
- `target_paths`
- `constraints`
- `acceptance`
- `cd`

只要步骤元数据缺失、混合或仍然模糊，就说明当前修复还不可执行。

## 6. 委派规则

执行必须通过：

- `scripts/run_codecgc_flow_step.py`
- `scripts/run_codecgc_task.py`

这样才能保证执行器选择与项目路由模型保持一致。

## 7. 结果采集规则

`cgc-fix` 必须收集：

- `success`
- `task_id`
- `SESSION_ID`
- `summary`
- `changed_files`
- `policy_checks`
- `risks`
- `audit.path`

audit 产物属于最小修复证据集的一部分。

如果执行失败，必须先分类，再决定如何继续，例如：

- 范围错误
- 缺少设计或修复澄清
- 环境或工具问题
- 执行器失败

## 8. 结束状态

`cgc-fix` 只能结束在以下几种状态之一：

- 已成功委派，等待 `cgc-review`
- 已退回范围澄清
- 被环境或工具问题阻塞
- 因步骤不可执行而拒绝继续
