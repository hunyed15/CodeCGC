# CodeCGC Checklist Contract

## 1. 目的

design 文档首先是给人看的。
checklist contract 首先是给执行系统看的。

因此，一个真正会改代码的 CodeCGC 步骤，应该带有一个 `codecgc` 块，明确声明这一步的机器执行边界。

## 2. 必填字段

`codecgc` 块至少要定义：

- `kind`
- `task_id`
- `task_summary`
- `target_paths`
- `constraints`
- `acceptance`
- `cd`

可选字段包括：

- `codex_sandbox`
- `gemini_sandbox`
- `model`
- `profile`
- `SESSION_ID`

## 3. 字段规则

### `kind`

只能是：

- `frontend`
- `backend`
- `auto`

其中 `auto` 只表示“运行时可进一步判定”，不表示可以放弃边界控制。

### `target_paths`

必须是当前步骤允许修改的最小文件范围。

不要写成整个模块、整个应用或宽泛目录，除非该步骤本身确实只允许那样的范围。

### `task_summary`

只能描述当前这一步，不要把后续步骤一起塞进去。

### `constraints`

这里写的是硬约束，不是愿景描述。

好的约束应接近：

- 不能修改哪些文件
- 不能跨到哪个层
- 不能顺手做什么额外重构

### `acceptance`

验收条件必须能在当前步骤内被检查，而不是依赖未来步骤。

## 4. 何时拒绝生成 contract

遇到下面这些情况，不应该勉强附一个宽泛 `codecgc` 块：

- 当前步骤混合了前端和后端范围
- 当前步骤包含 shared 路径
- 仍然存在未拍板设计选择
- 无法明确给出 `target_paths`

这种情况下，正确做法不是“先执行再说”，而是先拆分或回到设计。

## 5. 示例

```yaml
steps:
  - action: "仅实现登录页 UI"
    exit_signal: "前端执行器返回结构化摘要"
    status: pending
    codecgc:
      kind: frontend
      task_id: login-ui-step-1
      task_summary: "仅实现已确认范围内的登录页 UI。"
      target_paths:
        - frontend/login-page.tsx
      constraints:
        - 不要修改 target_paths 之外的文件。
        - 不要改动后端 API。
      acceptance:
        - 登录页 UI 满足当前步骤已确认的范围。
      cd: .
      gemini_sandbox: false
```

## 6. 使用原则

可以把 checklist contract 理解成“Claude 发给执行器的最小合法任务包”。

如果这个任务包写不清楚，说明步骤本身还没准备好，不应该把问题转嫁给执行器。
