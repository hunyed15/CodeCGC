# CodeCGC Fixture 治理

## 1. 目的

这份文档说明 CodeCGC 如何管理历史 demo、验证样例和行为检查工作流。

## 2. 治理规则

如果一个工作流存在的主要目的，是验证以下能力，而不是交付真实项目工作：

- 路由
- 状态推进
- 审核回写
- 结构化规划
- 会话续跑
- mixed-scope 阻断

那么它就应归入 fixture 根目录，而不是 product 根目录。

## 3. 目录规则

验证样例及其 audit 应放在：

- `codecgc/fixtures/features/`
- `codecgc/fixtures/issues/`
- `codecgc/fixtures/execution/`

真实交付工作流应保留在：

- `codecgc/features/`
- `codecgc/issues/`
- `codecgc/execution/`

## 4. 历史迁移

仓库当前已经提供历史 demo 迁移脚本：

- `python scripts/migrate_demo_workflows_to_fixtures.py`

这个脚本会把已知 demo 与验证工作流从 product 根目录迁入 fixture 根目录，并把它们的 `artifact_class` 改成 `fixture`。

## 5. 当前仓库状态

主要历史 demo 工作流已经迁入 fixture 根目录。

这意味着：

- fixture 根目录是当前运行时验证样例的规范位置

## 6. 操作规则

在创建新的样例工作流前，先判断：

- 这是实际产品工作，还是运行时验证样例

如果只是样例，应从一开始就使用：

- `--artifact-class fixture`

并直接把产物放进 fixture 根目录。
