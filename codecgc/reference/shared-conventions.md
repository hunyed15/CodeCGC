# CodeCGC 共享约定

## 1. 适用范围

这份文档定义 CodeCGC 的产品层通用约定。

当前固定角色分工是：

- Claude：规划、拆分、路由、审核、验收
- Gemini：前端实现
- Codex：后端实现

如果某项设计或实现与这套分工冲突，应优先怀疑该设计是否偏离了 CodeCGC 蓝图。

## 2. 目录模型

当前活跃运行时根目录是 `codecgc/`。

主要目录职责如下：

- `codecgc/reference/`：参考说明与契约
- `codecgc/cgc*`：技能定义
- `codecgc/features/`：功能开发工作流产物
- `codecgc/issues/`：问题修复工作流产物
- `codecgc/execution/`：执行审计产物
- `codecgc/requirements/`、`architecture/`、`roadmap/`、`compound/`：长期项目记忆
- `scripts/`：任务打包、运行时控制与 MCP 桥接

## 3. 产品级硬规则

所有代码改动步骤都必须遵守下面这些规则：

- 前端范围必须交给 Gemini
- 后端范围必须交给 Codex
- shared 范围必须先拆分
- Claude 不直接写受路由保护的业务代码

这套规则通过两层落地：

1. 工作流层：`cgc-build` 与 `cgc-fix`
2. guardrail 层：`.claude/hooks/route-edit.ps1`

## 4. 当前公开命令面

当前对外公开命令面是：

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

其中：

- `cgc` 是产品总入口
- 其他命令是在阶段已明确时使用

旧 `cs-*` 命令已经不属于 CodeCGC。

## 5. 产物归档规则

所有新的工作流产物都应归档到 `codecgc/` 下的正确目录。

推荐的长期归档家族包括：

- `codecgc/requirements/`
- `codecgc/architecture/`
- `codecgc/roadmap/`
- `codecgc/features/`
- `codecgc/issues/`
- `codecgc/compound/`

不要再把长期事实散落在旧命令体系或临时顶层文档中。

## 6. 实现步骤最低要求

任何会改代码的实现或修复步骤，都必须带有机器可执行的范围元数据。

至少应定义：

- 目标类型：frontend 或 backend
- `target_paths`
- `task_summary`
- 硬约束
- 当前步骤的验收标准

如果这些内容写不清楚，就说明步骤还没 ready，应该回到拆分或设计，而不是强行执行。
