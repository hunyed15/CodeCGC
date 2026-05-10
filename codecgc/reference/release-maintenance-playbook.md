# CodeCGC Release / Maintenance / Ops Playbook

## 1. 目的

这份文档定义 CodeCGC 在发布、长期维护、以及运维接入前的最小可执行闭环。

它不是 roadmap，也不是一次性 feature 设计稿。
它回答的是：

- 发布前要检查什么
- 长期维护时要怎么判断系统是否健康
- 运维与外部系统接入时，哪些检查必须先通过

## 2. 三条入口命令

维护者优先使用下面这组命令：

- `cgc-status`
- `cgc-doctor`
- `cgc-package-audit`
- `cgc-external-status`
- `cgc-external-audit`
- `cgc-release-readiness`

其中：

- `cgc-status` 看项目级集成是否已同步
- `cgc-doctor` 看 Python、MCP、执行器和项目级集成是否可运行
- `cgc-package-audit` 看发布包是否覆盖运行时依赖与发布元数据
- `cgc-external-status` 看第三方能力状态面板
- `cgc-external-audit` 看第三方能力白名单与本地 MCP 观测状态
- `cgc-release-readiness` 做总检查汇总，并补充仓库内 deploy / release 信号感知

## 3. 发布前顺序

建议固定按这个顺序执行：

1. `cgc-status`
2. `cgc-doctor`
3. `cgc-package-audit`
4. `cgc-external-audit`
5. `cgc-release-readiness`

只有当前一项没有阻塞时，才进入下一项。

## 4. 长期维护顺序

当你不是在发布，而是在维护已有安装面时，优先顺序改成：

1. `cgc-status`
2. `cgc-doctor`
3. `cgc-external-audit`
4. 必要时 `cgc-release-readiness`

原因是长期维护时，最常见的问题不是“包漏文件”，而是：

- 目标项目级集成漂移
- 本机 Python 或 MCP 运行时变化
- 新增了第三方 MCP，但没有登记到 CodeCGC 白名单

## 5. 运维接入规则

当需要接入 GitHub、Linear、Jira、Sentry、MemOS 或代码检索能力时，遵守下面规则。

当前项目已经明确：

- `Jira / Atlassian MCP` 不进入现阶段主线
- `Sentry MCP` 不进入现阶段主线

也就是说，下面规则目前主要作用于已经纳管的 `MemOS / ace-tool / GitHub / Linear`，以及未来如果你主动决定再启用 `Jira` 或 `Sentry` 的情况：

1. 先把接入意图写进 `codecgc/reference/external-capability-registry.json`
2. 再把项目级或用户级 `.mcp.json` 接入做好；对 `MemOS`，优先直接使用官方 `memos-mcp`
3. 日常用 `cgc-external-status` 快速看面板，必要时再用 `cgc-external-audit` 检查“登记状态”和“本地观测状态”是否一致

如果跳过第 1 步，CodeCGC 不把该接入视为正式产品能力。

`MemOS` 的特殊边界是：

- Claude 本身已经可以直接使用官方 `memos-mcp`
- CodeCGC 不再额外包一层记忆服务
- CodeCGC 只负责把它纳入正式白名单、状态审计与长期协作约束

`Augment` 的特殊边界是：

- Claude 本身已经可以直接使用 `ace-tool` 这一现成 MCP 接入面
- CodeCGC 不再额外包一层代码检索服务
- CodeCGC 只负责把它纳入正式白名单、状态审计与长期协作约束

`GitHub MCP` 的特殊边界是：

- Claude 本身已经可以直接使用 `github/github-mcp-server` 官方 MCP
- CodeCGC 不再额外包一层 GitHub 服务
- CodeCGC 只负责把它纳入正式白名单、状态审计与长期协作约束

`Linear MCP` 的特殊边界是：

- Claude 本身已经可以直接使用 Linear 官方 remote MCP
- CodeCGC 不再额外包一层 Linear 服务
- CodeCGC 只负责把它纳入正式白名单、状态审计与长期协作约束

`Jira / Atlassian MCP` 当前边界是：

- 当前不接入
- 不视为 CodeCGC 当前可用态的缺失
- 只有未来明确服务 Jira 体系团队时，才重新纳入评估

`Sentry MCP` 当前边界是：

- 当前不接入
- 它属于 post-release observability 能力
- 不视为 CodeCGC 当前可用态的缺失

## 6. 退出条件

只有同时满足下面条件，才算进入“可发布 / 可长期维护 / 可继续扩接”的状态：

- `cgc-status` 无阻塞
- `cgc-doctor` 无阻塞
- `cgc-package-audit` 无阻塞
- `cgc-external-status` 无阻塞
- `cgc-external-audit` 无阻塞
- `cgc-release-readiness` 总结论为通过

## 7. 边界

CodeCGC 自己只负责：

- 工作流控制
- 执行器分工
- 审计与 review
- 命令与安装壳
- 外部能力白名单与接入状态治理

CodeCGC 不负责自己重做：

- 记忆引擎
- 代码检索引擎
- GitHub / PM / 监控平台本体

这些能力都应优先复用成熟产品，并受 CodeCGC 的白名单与接入审计约束。

## 8. Deploy 信号感知

`cgc-release-readiness` 现在还会额外检查仓库内是否存在下面这类信号：

- GitHub Actions workflow
- Dockerfile
- docker compose / compose
- deploy / release 脚本
- `.env.example` 等运行时配置样例

这层当前只负责判断仓库有没有“已经开始考虑发布/部署”的迹象，不直接接通具体部署平台。
