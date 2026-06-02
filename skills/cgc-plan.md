---
name: cgc-plan
description: 为 workflow 规划执行步骤
---

为指定 workflow 添加执行步骤。调用 MCP 工具 `codecgc.plan`。

用户输入格式：`/cgc-plan <kind> <slug>`

## 必须执行

不要只解释本命令，也不要要求用户再去终端执行。收到 `/cgc-plan` 后必须实际规划并写入 steps：

1. 如果用户没有指定 kind 和 slug，先实际调用 `codecgc.status({ filter: "active" })` 查找需要规划的 workflow。
2. 读取 workflow 描述和相关文档后生成 steps。
3. 优先调用 MCP 工具 `codecgc.plan({ kind, slug, steps })` 写入。
4. 如果 MCP 工具不可用、没有返回内容，或当前环境无法直接调用 MCP，则立刻用终端回退：

```bash
cgc plan <kind> <slug> --steps '<json>'
```

5. 如果 `cgc plan` 不可用，再尝试兼容别名：

```bash
cgc-plan <kind> <slug> --steps '<json>'
```

只有在 MCP 和 CLI 都失败时，才把真实错误信息告诉用户。禁止在未写入 steps 时声称规划完成。

如果用户没有指定 kind 和 slug，先调用 `codecgc.status` 查找当前活跃的 workflow，选择最近一个处于 `needs-planning` 状态的。

规划流程：
1. 读取 workflow 的 description
2. 分析需求，拆分为多个步骤
3. 每个步骤指定 executor（backend/frontend/docs/orchestration）
4. 根据 `.codecgc/config/routing.yaml` 验证路径归属
5. 调用 `codecgc.plan` 写入步骤

步骤规划原则：
- 后端改动用 `executor: backend`
- 前端改动用 `executor: frontend`
- 文档改动用 `executor: docs`
- 编排/配置用 `executor: orchestration`
- shared 路径必须拆分为独立步骤

规划完成后，告知用户步骤列表和建议的执行顺序。
