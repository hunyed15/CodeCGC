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

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc-test` 后必须实际执行测试步骤：

1. 优先调用 MCP 工具：

调用 `codecgc.test({ kind, slug, step_id })`。

2. 如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用终端回退：

```bash
cgc test <kind> <slug> <step_id>
```

3. 如果 `cgc test` 不可用，再尝试兼容别名：

```bash
cgc-test <kind> <slug> <step_id>
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在未拿到真实返回时声称测试已执行。

注意：
- test 步骤必须显式指定 step_id，不能像 build/fix 那样自动选择
- 测试失败时不要用 build/fix 代替，必须修复后重新跑 test
