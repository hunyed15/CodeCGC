# CodeCGC 工作流骨架

## 1. 目的

这份文档定义 CodeCGC 在新工作开始时的最小产物骨架。

当前创建入口：

- `scripts/init_codecgc_workflow.py`

## 2. Feature 骨架

初始化 feature 时会创建：

- `codecgc/features/YYYY-MM-DD-{slug}/{slug}-design.md`
- `codecgc/features/YYYY-MM-DD-{slug}/{slug}-checklist.yaml`
- `codecgc/features/YYYY-MM-DD-{slug}/{slug}-acceptance.md`

默认情况下，checklist 会包含第一个 `codecgc` 步骤契约占位。

如果规划阶段识别到前后端混合目标路径，checklist 可以扩展成多个可执行步骤，而不只保留单一占位步骤。

如果规划阶段识别到共享路径或未知路径，也可以加入只用于规划澄清的步骤，这些步骤必须先被解决，后续才能执行。

每个拆分后的可执行步骤，也可以拥有自己的：

- action label
- task summary
- acceptance lines

这样执行器契约始终保持局部化，而不是依赖上层自由解释。

## 3. Issue 骨架

初始化 issue 时会创建：

- `codecgc/issues/YYYY-MM-DD-{slug}/{slug}-report.md`
- `codecgc/issues/YYYY-MM-DD-{slug}/{slug}-analysis.md`
- `codecgc/issues/YYYY-MM-DD-{slug}/{slug}-fix.yaml`
- `codecgc/issues/YYYY-MM-DD-{slug}/{slug}-fix-note.md`

默认情况下，fix YAML 会包含第一个 `codecgc` 修复步骤契约占位。

如果问题范围是混合的，也可以扩展成多个可执行修复步骤，并在必要时插入只用于规划澄清的步骤。

## 4. 产品规则

feature 与 issue 产物都直接落在 `codecgc/` 运行时根目录下：

- feature 产物在 `codecgc/features/`
- issue 产物在 `codecgc/issues/`

## 5. 规划规则

`cgc-plan` 应先创建工作流骨架，再由 `cgc-build` 或 `cgc-fix` 执行。

执行层默认假设目录、步骤契约和基本骨架已经存在。
