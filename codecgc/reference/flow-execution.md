# CodeCGC 流程执行入口

## 1. 目的

这份文档定义 `cgc-build` 与 `cgc-fix` 共享的步骤执行入口。

两条流程都会通过：

- `scripts/run_codecgc_flow_step.py`

把当前可执行步骤交给运行时执行。

## 2. 输入

这个共享执行入口至少需要：

- `flow`
- `slug`
- `step-number`

可选输入：

- `checklist-file`
- `audit-root`
- `timeout-seconds`
- `dry-run`

## 3. 解析规则

如果没有显式传入 `checklist-file`，执行入口会自动从以下目录解析工作流文件：

- `codecgc/features/{slug}/`
- `codecgc/issues/{slug}/`

当前查找顺序包括：

- `{slug}-checklist.yaml`
- `checklist.yaml`
- `{slug}-fix.yaml`
- `fix-checklist.yaml`

## 4. 共享契约

被解析出来的 YAML 文件，必须包含带有合法 `codecgc` 区块的步骤条目。

这意味着 feature 与 issue 当前共享同一套机器可执行契约：

- 面向人的步骤元信息
- 面向运行时的 `codecgc` 执行元信息

## 5. 产品规则

当步骤契约已经存在时，`cgc-build` 与 `cgc-fix` 不应再手工重构执行器 prompt。

它们应统一调用这个共享入口，然后读取：

- 结构化执行结果
- audit 产物

## 6. 当前限制

这个共享执行入口不负责创建 feature 或 issue 产物。

它只负责执行一个已经准备好的步骤契约。
产物创建、规划补全、审核回写仍然属于更上层工作流逻辑。
