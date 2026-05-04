# CodeCGC 长期产物说明

## 1. 目的

这份文档说明 `codecgc/` 里哪些目录属于“长期项目记忆”，哪些只是交付过程产物。

简单说：

- `feature / issue / execution` 更像交付过程状态
- `requirements / architecture / roadmap / compound` 更像长期产品记忆

## 2. 四类长期产物

### Requirements

路径：

- `codecgc/requirements/`

用途：

- 保存当前已经生效的稳定需求
- 记录产品或模块当前边界

### Architecture

路径：

- `codecgc/architecture/`

用途：

- 保存系统地图
- 记录当前真实架构状态

### Roadmap

路径：

- `codecgc/roadmap/`

用途：

- 保存超出单个 feature 范围的阶段性规划
- 记录后续要继续拆分的 initiative 级设计

### Compound

路径：

- `codecgc/compound/`

用途：

- 保存跨多个视角的组合型长期产物
- 例如 operating model、capability matrix、productization gap

## 3. 写文档前先问一个问题

先判断这份内容到底是在描述什么：

- 如果描述的是“某一步怎么交付”，它应该留在交付流里
- 如果描述的是“这个项目当前长期成立的事实”，它应该进入长期产物目录

交付流目录包括：

- `codecgc/features/`
- `codecgc/issues/`
- `codecgc/execution/`

fixture 目录包括：

- `codecgc/fixtures/features/`
- `codecgc/fixtures/issues/`
- `codecgc/fixtures/execution/`

参见：

- `codecgc/reference/fixture-governance.md`

## 4. 回写原则

正常顺序应当是：

1. 先在 feature / issue 中完成规划、执行、审核
2. 再从交付结果里提炼稳定知识
3. 最后把稳定知识回写到长期产物目录

不要在交付范围还不清楚时，先写一堆长期文档抢占真相。

## 5. 当前使用规则

如果同一份信息同时满足下面两个条件，就应该优先考虑写入长期目录：

- 它会在后续多个会话中被反复引用
- 它已经不再依赖某个单独步骤是否完成

这类文档的价值不是“记录一次过程”，而是“降低未来恢复上下文的成本”。
