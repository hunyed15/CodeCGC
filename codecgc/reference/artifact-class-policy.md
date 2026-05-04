# CodeCGC 产物类别策略

## 1. 目的

这份文档说明 CodeCGC 如何区分真实产品产物与本地验证 fixture。

## 2. 允许值

当前支持的 `artifact_class` 只有两种：

- `product`
- `fixture`

## 3. 默认规则

通过 `init` 或 `plan` 创建的新工作流产物，默认都属于：

- `artifact_class: product`

这代表正常的仓库交付意图。

## 4. Fixture 规则

只有当一个工作流的主要目的，是验证运行时行为而不是交付真实项目工作时，才应使用：

- `artifact_class: fixture`

## 5. 当前存储规则

`product` 产物当前放在：

- `codecgc/features/`
- `codecgc/issues/`

`fixture` 产物当前放在：

- `codecgc/fixtures/features/`
- `codecgc/fixtures/issues/`

因此 `artifact_class` 仍然是机器可读的意图标记，而 fixture 现在也有自己独立的目录根。

## 6. 审计传播规则

当 checklist 或 fix 产物里声明了 `artifact_class` 时，运行时会把它继续传播到 audit 的：

- `source.artifact_class`

当前规则是：

- `product` audit 默认写入 `codecgc/execution/`
- `fixture` audit 默认写入 `codecgc/fixtures/execution/`

这样后续工具就能区分：

- 真实产品执行证据
- fixture 验证执行证据

## 7. 操作规则

如果一个工作流只是为了验证：

- 路由
- 审核回写
- 状态推进
- 结构化规划

那么就应使用：

- `--artifact-class fixture`

否则保持默认的 `product`。

## 8. 历史修复规则

如果旧 audit 仍然保留在错误目录或仍含旧路径信息，可以使用：

- `python scripts/normalize_codecgc_audits.py`

如果旧 demo 工作流还停留在产品目录下，可以使用：

- `python scripts/migrate_demo_workflows_to_fixtures.py`
