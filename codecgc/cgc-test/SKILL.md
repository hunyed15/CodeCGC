# CodeCGC `cgc-test`

`cgc-test` 用于执行已经进入主工作流的测试步骤。

它不是独立于 `feature / issue` 之外的新体系，而是：

- 读取当前 workflow 中的测试 step
- 按前端测试 / 后端测试继续走 Gemini / Codex
- 复用现有 `execution audit -> review` 闭环

默认入口：

```bash
cgc-test --flow <feature|issue> --slug <slug>
```

如果已经知道准确 step，也可以：

```bash
cgc-test --flow <feature|issue> --slug <slug> --step-number <n>
```
