# CodeCGC Lifecycle Playbook

## 1. 目的

这份文档定义 CodeCGC 在“从 0 到 1、从 1 到 2、长期维护”三种阶段下的统一使用方式。

它补的是 `lifecycle-map.md` 的操作层。

## 2. 三种阶段

### 2.1 从 0 到 1

适用场景：

- 还没有 workflow
- 还没有明确的 roadmap 或 feature / issue 资产

优先入口：

1. `cgc`
2. `cgc-entry`
3. `cgc-plan`

目标：

- 先把需求收敛成 feature / issue / roadmap 之一
- 再进入可执行步骤

### 2.2 从 1 到 2

适用场景：

- 已有 roadmap
- 已有多个 feature / issue workflow
- 已有 execution 审计沉淀

优先入口：

1. `cgc-lifecycle`
2. `cgc-route`
3. `cgc-build / cgc-fix / cgc-review`

目标：

- 判断当前是继续规划、继续执行、还是收尾审核
- 避免在多个 workflow 并行时丢失当前主线

### 2.3 长期维护

适用场景：

- 已经进入安装、发布、运维或生态接入阶段

优先入口：

1. `cgc-status`
2. `cgc-doctor`
3. `cgc-external-audit`
4. `cgc-release-readiness`
5. `cgc-lifecycle`

目标：

- 判断当前是环境问题、发布问题、外部接入问题，还是正常的交付推进

## 3. 生命周期总览入口

`cgc-lifecycle` 不负责直接执行 workflow。

它只负责回答：

- 当前仓库更像 setup-only、initiative-planning、planned-not-executed，还是 active-delivery
- 当前 product / fixture 的 roadmap、workflow、execution 分布是什么
- roadmap 是否已经继续拆成 child workflow，还是还停留在 initiative 层
- 下一步更适合回到 `cgc`、`cgc-plan`、`cgc-route`，还是进入维护总检查链

## 4. 使用规则

如果你不知道当前仓库处在哪个阶段，优先跑：

```bash
cgc-lifecycle
```

如果你已经知道自己要继续某个 workflow，优先回到：

```bash
cgc-route --flow feature --slug <slug>
```

或：

```bash
cgc-route --flow issue --slug <slug>
```

## 5. 边界

`cgc-lifecycle` 是总览，不是调度器。

真正的执行、审核、发布与维护，仍然分别归：

- `cgc-entry / cgc-plan / cgc-build / cgc-fix / cgc-review / cgc-route`
- `cgc-status / cgc-doctor / cgc-package-audit / cgc-external-audit / cgc-release-readiness`
