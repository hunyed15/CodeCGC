---
name: cgc-plan
description: 为 workflow 规划执行步骤
---

为指定 workflow 添加执行步骤。调用 MCP 工具 `codecgc.plan`。

用户输入格式：`/cgc-plan <kind> <slug>`

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
