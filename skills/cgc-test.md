---
name: cgc-test
description: 执行测试步骤
---

执行测试步骤。调用 MCP 工具 `codecgc.test`。

用户输入格式：`/cgc-test <kind> <slug> <step_id>`

参数全部必填：
- kind: feature 或 issue
- slug: workflow 标识
- step_id: 测试步骤 ID

调用 `codecgc.test({ kind, slug, step_id })`。

注意：
- test 步骤必须显式指定 step_id，不能像 build/fix 那样自动选择
- 测试失败时不要用 build/fix 代替，必须修复后重新跑 test
