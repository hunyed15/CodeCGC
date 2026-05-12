#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const { existsSync } = require("node:fs");
const { readFileSync } = require("node:fs");
const path = require("node:path");

const repoRoot = path.resolve(__dirname, "..");
const invocationCwd = process.cwd();
const args = process.argv.slice(2);
const invokedBinary = (process.env.CODECGC_BIN_NAME || path.basename(process.argv[1] || "cgc")).toLowerCase();
const packageJson = JSON.parse(readFileSync(path.join(repoRoot, "package.json"), "utf8"));
const productVersion = packageJson.version || "0.0.0";
const DIRECT_COMMANDS = new Set([
  "start",
  "install",
  "status",
  "doctor",
  "package-audit",
  "external-audit",
  "external-status",
  "release-readiness",
  "lifecycle",
  "history",
  "entry",
  "plan",
  "build",
  "fix",
  "test",
  "review",
  "route",
]);
const DASH_COMMANDS = new Set(Array.from(DIRECT_COMMANDS, (command) => `cgc-${command}`));

const helpText = `CodeCGC 命令入口

用法:
  cgc --help
  cgc --version
  cgc <自然语言需求>
  cgc --request <text>
  cgc --latest
  cgc --slug <workflow-slug>
  cgc-start [--format json|summary] [--workspace <dir>]
  cgc-init [--mode local|status|doctor|start] [--workspace <dir>]
  cgc-status [--format json|summary]
  cgc-doctor [--format json|summary]
  cgc-package-audit [--format json|summary]
  cgc-external-audit [--format json|summary] [--workspace <dir>]
  cgc-external-status [--format json|summary] [--workspace <dir>]
  cgc-release-readiness [--format json|summary] [--workspace <dir>]
  cgc-lifecycle [--format json|summary]
  cgc-history [--flow all|feature|issue] [--status all|open|closed] [--last <n>] [--format json|summary]
  cgc-entry [--request <text> | --payload-file <file> | --payload-base64 <b64>]
  cgc-plan ...
  cgc-build ...
  cgc-fix ...
  cgc-test ...
  cgc-review ...
  cgc-route ...

按目标选择:
  我只想直接说一句需求，让 CodeCGC 自己判断下一步
    cgc "新增一个登录页面，放在 src/components/LoginForm.tsx"
  我想继续刚刚的工作，不想先判断该用哪个子命令
    cgc "继续刚刚的工作"
  我只想对最近工作流说“直接做 / 通过 / 不通过 / 看下一步”
    cgc "直接做"
    cgc "通过"
    cgc "现在下一步该做什么"
  我想直接问当前工作流下一步做什么
    cgc --slug 2026-05-01-demo-login-ui
  我已经知道这是新需求或问题，但还想先补齐规划再执行
    cgc-plan ...
  我已经确认当前步骤可以开始执行
    cgc-build / cgc-fix
  我已经进入当前工作流的测试补充阶段
    cgc-test
  我已经有 audit，想回写审核结果
    cgc-review ...
  我只想让 CodeCGC 告诉我下一步该跑哪个命令
    cgc-route ...
  我想把 CodeCGC 安装或重新同步到当前项目
    cgc-init
  我刚装完，想看当前项目下一步怎么开始
    cgc-start
  我想知道集成面现在是否就绪
    cgc-status
  我想知道运行前置和执行器能不能真正启动
    cgc-doctor
  我想确认发布包没有漏掉运行时文件
    cgc-package-audit
  我想确认第三方能力接入策略和本地 MCP 注册状态
    cgc-external-audit
  我想快速查看第三方能力状态面板
    cgc-external-status
  我想在发布或长期维护前跑一次总检查
    cgc-release-readiness
  我想快速判断当前仓库处于哪个生命周期阶段
    cgc-lifecycle
  我想只读查看最近 workflow 历史
    cgc-history
  我只描述需求，让 CodeCGC 帮我判断下一步
    cgc-entry
  我已经知道当前阶段，想直接执行某个工作流命令
    cgc-plan / cgc-build / cgc-fix / cgc-review / cgc-route

命令职责:
  cgc-start          显示当前项目的首次使用入口和下一步动作
  cgc-init        同步项目级集成面
  cgc-status         检查集成是否就绪，并给出下一步
  cgc-doctor         检查运行前置、执行器导入与项目集成状态
  cgc-package-audit  检查发布包是否覆盖运行时依赖
  cgc-external-audit 检查外部能力白名单、接入声明与本地 MCP 观测一致性
  cgc-external-status 查看外部能力状态面板与本地 MCP 观测结果
  cgc-release-readiness 汇总安装、运行时、发布包、外部接入与生命周期就绪状态
  cgc-lifecycle      汇总 roadmap、workflow 与 execution 的生命周期阶段
  cgc-history        只读汇总最近 feature / issue workflow 历史
  cgc-entry          单入口路由：新需求、继续、解释下一步
  cgc-plan           澄清并整理需求，判断是否可执行
  cgc-build          执行一个功能开发步骤
  cgc-fix            执行一个问题修复步骤
  cgc-test           执行一个测试步骤
  cgc-review         审核一次执行结果并回写状态
  cgc-route          根据当前产物判断下一步命令
  version            输出当前产品壳版本

首次使用:
  1. 先在目标项目根目录执行 cgc-init
  2. 执行 cgc-start 查看项目本地入口说明
  3. 再执行 cgc-status，必要时补 cgc-doctor
  4. 然后直接使用 cgc "<自然语言需求>" 或 cgc-entry
  5. 只有当你已经明确知道当前阶段时，再改用 cgc-plan / cgc-build / cgc-fix / cgc-test / cgc-review / cgc-route

示例:
  cgc "新增一个登录页面，放在 src/components/LoginForm.tsx"
  cgc "继续刚刚的工作"
  cgc "直接做"
  cgc "通过"
  cgc --request "现在下一步该做什么"
  cgc --latest
  cgc --slug 2026-05-01-demo-login-ui
  cgc-start
  cgc-plan --flow feature --slug demo-login-ui --summary "Demo login UI feature" --target-path src/components/LoginForm.tsx --kind frontend
  cgc-build --slug 2026-05-01-demo-login-ui --step-number 1 --dry-run
  cgc-fix --slug 2026-05-01-demo-sync-bug --step-number 1 --dry-run
  cgc-test --flow feature --slug 2026-05-01-demo-login-ui --step-number 2 --dry-run
  cgc-review --audit-file codecgc/execution/demo-login-ui-step-1.json --decision accepted
  cgc-route --flow feature --slug 2026-05-01-demo-login-ui
  cgc-init
  cgc-status
  cgc-status --format summary
  cgc-doctor --format summary
  cgc-package-audit --format summary
  cgc-external-status --format summary
  cgc-external-audit --format summary
  cgc-release-readiness --format summary
  cgc-lifecycle --format summary
  cgc-history --status open --last 10
  cgc-init --workspace D:\\Projects\\MyApp
  cgc-entry --request "新增一个登录页面，放在 src/components/LoginForm.tsx"

环境变量:
  CODECGC_PYTHON_COMMAND  覆盖产品壳与生成的 MCP 配置所使用的 Python 命令
  CODECGC_WORKSPACE_ROOT  当当前 shell 目录不是目标项目根目录时，显式覆盖目标工作区
`;

const startHelpText = `CodeCGC Start

用法:
  cgc-start [--format <summary|json>] [--workspace <dir>]

用途:
  显示当前项目的首次使用入口、项目本地 onboarding 文件，以及下一步动作。

默认行为:
  不传 --format 时默认输出 summary，更适合安装后直接阅读。
  该命令只读，不会修改项目文件。

主要参数:
  --workspace <dir>
    显式指定目标项目根目录。默认使用当前 shell 所在目录。
  --format <summary|json>
    summary 用于新手入口摘要，json 用于调试或自动化消费。

推荐用法:
  cgc-init
  cgc-start
  cgc-status
  cgc-doctor
  cgc "新增一个登录页面，放在 src/components/LoginForm.tsx"
`;

const installHelpText = `CodeCGC 安装与自检

用法:
  cgc-init [--mode <local|status|doctor|start>] [--workspace <dir>] [--format <json|summary>]

用途:
  准备、检查或修复 CodeCGC 在 Claude 与 MCP 启动链路上的集成面。

模式:
  local
    把项目级 .mcp.json、.claude/settings.json 与 route-edit.ps1 hook 同步到目标工作区。
  status
    检查项目级集成是否就绪。
  doctor
    检查运行前置、执行器可导入性，以及项目级集成是否就绪。
  start
    只读显示项目首次使用入口和下一步动作。

主要参数:
  --workspace <dir>
    local/status/doctor 模式下的目标项目根目录。默认使用当前 shell 所在目录。
  --format <json|summary>
    面向 Claude 或人工阅读时建议使用 summary；排查底层细节时用 json。

推荐用法:
  cgc-init
  cgc-start
  cgc-init --workspace D:\\Projects\\MyApp
  cgc-init --mode start --format summary
  cgc-init --mode status --format summary
  cgc-init --mode doctor --format summary

相关命令:
  cgc-start
    查看当前项目首次使用入口。
  cgc-status
    快速查看集成状态。
  cgc-doctor
    快速查看运行前置与集成前置是否齐全。
  cgc-package-audit
    检查 package.json files 是否覆盖安装运行所需文件。
  cgc-external-audit
    检查外部能力接入白名单、状态声明与本地注册观测。
  cgc-release-readiness
    汇总发布前与长期维护前的总检查结果。
  cgc-lifecycle
    汇总 roadmap、workflow 与 execution 的生命周期阶段。
`;

const statusHelpText = `CodeCGC 安装状态

用法:
  cgc-status [--format <summary|json>] [--workspace <dir>]

用途:
  检查当前项目工作区的 CodeCGC 集成是否就绪，并给出下一步建议。

默认行为:
  不传 --format 时默认输出 summary，更适合人和 Claude 直接阅读。
  只有在调试底层细节时才建议改用 --format json。

主要参数:
  --workspace <dir>
    显式指定目标项目根目录。默认使用当前 shell 所在目录。
  --format <summary|json>
    summary 用于产品化状态摘要，json 用于调试和自动化消费。

推荐用法:
  cgc-status
  cgc-status --workspace D:\\Projects\\MyApp
  cgc-status --format json

相关命令:
  cgc-start
    查看当前项目首次使用入口。
  cgc-init
    同步或修复当前项目集成面。
  cgc-doctor
    检查运行前置、执行器导入和项目集成状态。
`;

const doctorHelpText = `CodeCGC Doctor

用法:
  cgc-doctor [--format <summary|json>] [--workspace <dir>]

用途:
  检查运行前置、执行器可导入性，以及当前项目工作区的集成状态。

默认行为:
  不传 --format 时默认输出 summary，更适合直接判断环境是否可用。
  只有在需要查看完整检查细节时才建议改用 --format json。

主要参数:
  --workspace <dir>
    显式指定目标项目根目录。默认使用当前 shell 所在目录。
  --format <summary|json>
    summary 用于产品化自检摘要，json 用于底层排查。

推荐用法:
  cgc-doctor
  cgc-doctor --workspace D:\\Projects\\MyApp
  cgc-doctor --format json

相关命令:
  cgc-status
    快速查看项目集成是否就绪。
  cgc-init
    同步或修复集成文件。
  cgc-package-audit
    检查发布包运行面与发布就绪状态。
`;

const packageAuditHelpText = `CodeCGC 发布包审计

用法:
  cgc-package-audit [--format <summary|json>]

用途:
  检查发布包运行时覆盖、发布元数据，以及历史审计一致性是否就绪。

默认行为:
  不传 --format 时默认输出 summary，更适合发布前快速判断是否可继续。
  只有在需要保留结构化结果做调试或自动化时才建议改用 --format json。

主要参数:
  --format <summary|json>
    summary 用于发布前人工检查，json 用于底层调试或流水线消费。

推荐用法:
  cgc-package-audit
  cgc-package-audit --format json

相关命令:
  cgc-init
    检查并同步当前项目的 Claude/MCP 集成面。
  cgc-status
    查看当前项目集成状态。
  cgc-doctor
    检查运行前置与执行器导入状态。
`;

const externalAuditHelpText = `CodeCGC 外部能力审计

用法:
  cgc-external-audit [--format <summary|json>] [--workspace <dir>]

用途:
  检查 CodeCGC 已批准的第三方能力清单、接入状态声明，以及当前项目工作区可观测到的 MCP 注册状态。

默认行为:
  不传 --format 时默认输出 summary，更适合维护者快速判断“哪些能力已正式接入、哪些只是预留位”。
  只有在需要查看完整结构化登记信息时才建议改用 --format json。

主要参数:
  --workspace <dir>
    显式指定目标项目根目录。默认使用当前 shell 所在目录。
  --format <summary|json>
    summary 用于维护检查，json 用于调试和自动化消费。

推荐用法:
  cgc-external-audit
  cgc-external-audit --workspace D:\\Projects\\MyApp
  cgc-external-audit --format json
`;

const externalStatusHelpText = `CodeCGC 外部能力状态面板

用法:
  cgc-external-status [--format <summary|json>] [--workspace <dir>]

用途:
  快速查看外部能力登记状态、规划项与本地 MCP 观测结果。

默认行为:
  不传 --format 时默认输出 summary，更适合日常维护检查。
  只有在需要查看完整结构化数据时才建议改用 --format json。

主要参数:
  --workspace <dir>
    显式指定目标项目根目录。默认使用当前 shell 所在目录。
  --format <summary|json>
    summary 用于快速查看面板，json 用于调试和自动化消费。

推荐用法:
  cgc-external-status
  cgc-external-status --workspace D:\\Projects\\MyApp
  cgc-external-status --format json
`;

const releaseReadinessHelpText = `CodeCGC Release Readiness

用法:
  cgc-release-readiness [--format <summary|json>] [--workspace <dir>]

用途:
  汇总安装集成、运行前置、发布包、外部能力接入与生命周期资产是否就绪，用于 release / maintenance / ops 前的总检查。

默认行为:
  不传 --format 时默认输出 summary，更适合发布前或长期维护前快速判断是否还存在阻塞。
  只有在需要查看所有底层检查细节时才建议改用 --format json。

主要参数:
  --workspace <dir>
    显式指定目标项目根目录。默认使用当前 shell 所在目录。
  --format <summary|json>
    summary 用于维护检查，json 用于调试和自动化消费。

推荐用法:
  cgc-release-readiness
  cgc-release-readiness --workspace D:\\Projects\\MyApp
  cgc-release-readiness --format json
`;

const lifecycleHelpText = `CodeCGC Lifecycle

用法:
  cgc-lifecycle [--format <summary|json>]

用途:
  汇总 roadmap、feature、issue 与 execution 审计的当前分布，帮助判断仓库处于 setup、规划、执行还是维护阶段。

默认行为:
  不传 --format 时默认输出 summary，更适合人和 Claude 直接阅读。
  只有在需要保留结构化统计时才建议改用 --format json。

推荐用法:
  cgc-lifecycle
  cgc-lifecycle --format json
`;

const historyHelpText = `CodeCGC Workflow History

用法:
  cgc-history [--flow <all|feature|issue>] [--status <all|open|closed|needs-planning|awaiting-build|awaiting-fix|awaiting-review>] [--last <n>] [--include-fixtures] [--format <summary|json>]

用途:
  只读汇总最近的 CodeCGC workflow 历史，帮助你快速知道哪些工作流还开着、下一步该跟进哪条。

默认行为:
  不传 --format 时默认输出 summary，更适合人和 Claude 直接阅读。
  默认只看 product 工作流；只有在维护样例或回归时，才建议加 --include-fixtures。

主要参数:
  --flow <all|feature|issue>
    过滤 feature、issue 或全部工作流。
  --status <...>
    过滤 open / closed / needs-planning / awaiting-build / awaiting-fix / awaiting-review 等状态。
  --last <n>
    限制返回最近 N 条记录。
  --include-fixtures
    把 fixture 工作流一并纳入结果。
  --format <summary|json>
    summary 用于产品化历史摘要，json 用于调试和自动化消费。

推荐用法:
  cgc-history
  cgc-history --status open --last 10
  cgc-history --flow feature --status awaiting-review
  cgc-history --include-fixtures --format json
`;

const entryHelpText = `CodeCGC Workflow Entry

用法:
  cgc-entry [--request <text> | --payload-file <file> | --payload-json <json> | --payload-base64 <b64>] [options]

用途:
  用一个单入口处理新需求、继续已有工作流，或解释当前下一步。

什么时候优先用它:
  - 你只想直接描述需求，不想先决定该用 plan、build、fix、review 还是 route
  - 你想继续刚刚的工作
  - 你只想问“现在下一步该做什么”

关键参数:
  --request <text>
    自然语言请求或操作指令。
  --mode <auto|new|continue|explain>
    让 CodeCGC 自动判断意图，或强制指定交互模式。
  --flow <feature|issue>
    在已知时显式指定工作流类型。
  --slug <slug>
    continue / explain 场景下的已有工作流标识。
  --payload-file / --payload-json / --payload-base64
    重新喂入上一轮结构化补全数据，避免手动重复拼长参数。

典型用法:
  cgc-entry --request "新增一个登录页面，放在 src/components/LoginForm.tsx"
  cgc-entry --request "继续刚刚的工作"
  cgc-entry --request "直接做"
  cgc-entry --request "通过"
  cgc-entry --request "现在下一步该做什么"

典型结果:
  返回澄清问题、推荐命令，或在条件具备时自动调度到 cgc-build / cgc-fix / cgc-review。
`;

const planHelpText = `CodeCGC Workflow Plan

用法:
  cgc-plan --flow <feature|issue> --slug <slug> --summary <text> [options]

用途:
  在真正委派执行前，澄清或修复一份工作流规划。

什么时候优先用它:
  - 需求还不完整，需要补 design、checklist 或 acceptance
  - route 结果仍显示“需要回到规划阶段”
  - 你已经知道这就是一个 feature 或 issue，只想直接补齐规划

关键参数:
  --flow <feature|issue>
    指定是 feature 规划还是 issue 规划。
  --slug <slug>
    用于存储产物的稳定工作流标识。
  --summary <text>
    写入产物中的简短说明。
  --target-path <path>
    定义执行范围的文件或目录，可重复传入。
  --kind <auto|frontend|backend>
    让 CodeCGC 自动判断归属，或在已知时直接指定前后端。

高价值字段:
  --goal / --user-story / --in-scope / --acceptance
    更适合 feature 规划。
  --symptom / --expected / --actual / --preferred-fix
    更适合 issue 规划。

典型结果:
  更新规划产物，并明确告诉你下一步是继续澄清，还是进入 cgc-build / cgc-fix。
`;

const buildHelpText = `CodeCGC Workflow Build

用法:
  cgc-build --slug <slug> [--step-number <n>] [options]

用途:
  执行一个功能开发步骤，并沿用 CodeCGC 的强制路由、审计和 review 约束。

什么时候优先用它:
  - feature checklist 已准备好
  - route 已推荐你进入 cgc-build
  - 你需要真的开始执行当前功能开发步骤

关键参数:
  --slug <slug>
    feature 工作流标识。
  --step-number <n>
    可选的精确步骤；不传时会自动选择当前 pending step。
  --checklist-file <path>
    可选的显式 checklist 路径。
  --dry-run
    只生成执行意图，不真正委派执行器写代码。

典型结果:
  生成 execution audit；成功后通常进入 cgc-review。
`;

const fixHelpText = `CodeCGC Workflow Fix

用法:
  cgc-fix --slug <slug> [--step-number <n>] [options]

用途:
  执行一个问题修复步骤，并沿用与 feature 相同的审计和 review 约束。

什么时候优先用它:
  - issue 分析已经收敛到可执行修复步骤
  - route 已推荐你进入 cgc-fix
  - 你现在要做的是修复，不是继续诊断或补规划

关键参数:
  --slug <slug>
    issue 工作流标识。
  --step-number <n>
    可选的精确步骤；不传时会自动选择当前 pending step。
  --checklist-file <path>
    可选的显式修复清单路径。
  --dry-run
    只生成执行意图，不真正委派执行器写代码。

典型结果:
  生成 execution audit；成功后通常进入 cgc-review。
`;

const testHelpText = `CodeCGC Workflow Test

用法:
  cgc-test --flow <feature|issue> --slug <slug> [--step-number <n>] [options]

用途:
  执行一个测试步骤，并沿用与 build/fix 相同的审计和 review 约束。

什么时候优先用它:
  - 当前主代码步骤已经完成，下一步是补充或更新对应测试
  - route 已推荐你进入 cgc-test
  - 你希望测试也纳入现有主工作流，而不是停留在手工动作

关键参数:
  --flow <feature|issue>
    测试步骤所属的工作流类型。
  --slug <slug>
    稳定工作流标识。
  --step-number <n>
    可选的精确步骤；不传时会自动选择当前 pending 测试步骤。
  --dry-run
    只生成执行意图，不真正委派执行器写代码。

典型结果:
  生成 execution audit；成功后通常进入 cgc-review。
`;

const reviewHelpText = `CodeCGC Workflow Review

用法:
  cgc-review --audit-file <path> --decision <accepted|changes-requested> [options]

用途:
  审核一次 execution audit，并把结果回写到 acceptance 或 fix-note 中。

什么时候优先用它:
  - build 或 fix 已执行完成，并产出了 audit 文件
  - route 已推荐你进入 cgc-review
  - 你要明确当前步骤是“通过”，还是退回继续修改

关键参数:
  --audit-file <path>
    build、fix 或 exec 生成的 execution audit 文件。
  --decision <accepted|changes-requested>
    希望写回的审核结论。
  --risk <text>
    可选的额外风险说明，可重复传入。
  --next-step <text>
    可选的下一步动作说明。

典型结果:
  回写 review 结论，并明确后续是关闭、继续执行，还是回到规划。
`;

const routeHelpText = `CodeCGC Workflow Route

用法:
  cgc-route --flow <feature|issue> --slug <slug>

用途:
  根据当前工作流产物状态，判断下一步最合适的命令。

什么时候优先用它:
  - 你已经有 slug，但不想手工判断该走 plan、build、fix 还是 review
  - 你希望 Claude 在回复人前，先拿到稳定、确定的下一步命令
  - 你想确认当前工作流是待规划、待执行、待审核，还是已经关闭

关键参数:
  --flow <feature|issue>
    工作流类型。
  --slug <slug>
    稳定工作流标识。

典型结果:
  返回推荐命令、当前 route 状态，以及为什么做出这个判断。
`;

function findPython() {
  const override = (process.env.CODECGC_PYTHON_COMMAND || "").trim();
  const generatedMcpCommand = readGeneratedMcpPythonCommand();
  for (const configured of [override, generatedMcpCommand]) {
    if (configured) {
      return configured;
    }
  }
  const candidates = [
    ...(process.platform === "win32" ? ["python", "py"] : ["python3", "python"]),
  ];
  const seen = new Set();

  for (const command of candidates) {
    if (seen.has(command)) {
      continue;
    }
    seen.add(command);
    const probe = spawnSync(command, ["--version"], {
      cwd: repoRoot,
      encoding: "utf8",
      shell: false,
    });
    if (probe.status === 0) {
      return command;
    }
  }
  return null;
}

function readGeneratedMcpPythonCommand() {
  for (const mcpPath of [path.join(invocationCwd, ".mcp.json"), path.join(repoRoot, ".mcp.json")]) {
    if (!existsSync(mcpPath)) {
      continue;
    }
    try {
      const payload = JSON.parse(readFileSync(mcpPath, "utf8"));
      const servers = payload && payload.mcpServers;
      if (servers && servers.codecgc && typeof servers.codecgc.command === "string") {
        const command = servers.codecgc.command.trim();
        if (command) {
          return command;
        }
      }
    } catch (_error) {
      // Ignore malformed generated config and continue with normal Python discovery.
    }
  }
  return "";
}

function run(command, commandArgs) {
  const commandEnv = {
    ...process.env,
    CODECGC_WORKSPACE_ROOT: process.env.CODECGC_WORKSPACE_ROOT || invocationCwd,
    PYTHONIOENCODING: process.env.PYTHONIOENCODING || "utf-8",
    PYTHONUTF8: process.env.PYTHONUTF8 || "1",
  };
  const result = spawnSync(command, commandArgs, {
    cwd: repoRoot,
    env: commandEnv,
    stdio: "inherit",
    shell: false,
  });

  if (typeof result.status === "number") {
    process.exit(result.status);
  }

  process.exit(1);
}

function runCapture(command, commandArgs) {
  const commandEnv = {
    ...process.env,
    CODECGC_WORKSPACE_ROOT: process.env.CODECGC_WORKSPACE_ROOT || invocationCwd,
    PYTHONIOENCODING: process.env.PYTHONIOENCODING || "utf-8",
    PYTHONUTF8: process.env.PYTHONUTF8 || "1",
  };
  return spawnSync(command, commandArgs, {
    cwd: repoRoot,
    env: commandEnv,
    encoding: "utf8",
    shell: false,
  });
}

function tryParseJsonObject(rawText) {
  const text = String(rawText || "").trim();
  if (!text) {
    return null;
  }
  try {
    const parsed = JSON.parse(text);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

function buildRootEntryText(result) {
  if (!result || typeof result !== "object") {
    return "";
  }
  function quoteShellArg(value) {
    const text = String(value || "");
    if (!text) {
      return '""';
    }
    if (!/[\s"`]/.test(text)) {
      return text;
    }
    return `"${text.replace(/(["`])/g, "\\$1")}"`;
  }
  function splitSummaryAndNext(summaryText) {
    const text = String(summaryText || "").trim();
    if (!text) {
      return { summary: "", inlineNext: "" };
    }
    const markerPattern = /\s+下一步建议[:：]\s*/;
    const match = markerPattern.exec(text);
    if (!match || match.index < 0) {
      return { summary: text, inlineNext: "" };
    }
    const summaryPart = text.slice(0, match.index).trim();
    const nextPart = text.slice(match.index + match[0].length).trim();
    return {
      summary: summaryPart || text,
      inlineNext: nextPart,
    };
  }
  const operatorBrief = result.operator_brief && typeof result.operator_brief === "object"
    ? result.operator_brief
    : {};
  const routeStatus = result.route_status && typeof result.route_status === "object"
    ? result.route_status
    : {};
  const machineNextAction = operatorBrief.machine_next_action && typeof operatorBrief.machine_next_action === "object"
    ? operatorBrief.machine_next_action
    : {};
  const execution = machineNextAction.execution && typeof machineNextAction.execution === "object"
    ? machineNextAction.execution
    : {};
  const replyKind = String(operatorBrief.reply_kind || "").trim();
  const actionType = String(machineNextAction.type || "").trim();
  const governanceType = String(operatorBrief.governance_type || machineNextAction.governance_type || "").trim();
  const conciseSummary = String(
    operatorBrief.human_summary
    || result.human_summary
    || ""
  ).trim();
  const detailedSummary = String(
    operatorBrief.user_message
    || result.assistant_reply
    || conciseSummary
    || result.next
    || ""
  ).trim();
  const summary = String(
    replyKind === "clarification"
      ? detailedSummary
      : (conciseSummary || detailedSummary)
  ).trim();
  if (!summary) {
    return "";
  }
  const splitDisplay = replyKind === "clarification"
    ? { summary, inlineNext: "" }
    : splitSummaryAndNext(summary);
  const displaySummary = splitDisplay.summary || summary;

  const lines = [displaySummary];
  const workflowState = String(
    execution.workflow_state
    || machineNextAction.workflow_state
    || routeStatus.workflow_state
    || ""
  ).trim();
  const workflowStateLabels = {
    "needs-new-workflow": "需要先开始新的工作流",
    "needs-review-target": "需要先定位待审核工作流",
    "needs-planning": "需要回到规划阶段",
    "awaiting-build": "等待功能开发执行",
    "awaiting-fix": "等待问题修复执行",
    "awaiting-review": "等待审核决策",
    "step-selected": "已选中当前步骤",
    "closed": "已关闭",
    "governance-routing": "治理动作路由中",
  };
  const command = String(
    execution.command
    || machineNextAction.command
    || operatorBrief.recommended_command
    || result.recommended_command
    || ""
  ).trim();
  const commandArgs = Array.isArray(execution.command_args)
    ? execution.command_args.map((item) => String(item).trim()).filter(Boolean)
    : Array.isArray(machineNextAction.command_args)
      ? machineNextAction.command_args.map((item) => String(item).trim()).filter(Boolean)
      : [];
  function buildShortCommandHintParts(baseCommand, argsList) {
    const normalizedCommand = String(baseCommand || "").trim();
    if (!normalizedCommand) {
      return [];
    }
    const normalizedArgs = Array.isArray(argsList) ? argsList : [];
    if (normalizedCommand === "cgc-plan") {
      const flowIndex = normalizedArgs.indexOf("--flow");
      const slugIndex = normalizedArgs.indexOf("--slug");
      const parts = [normalizedCommand];
      if (flowIndex >= 0 && normalizedArgs[flowIndex + 1]) {
        parts.push("--flow", normalizedArgs[flowIndex + 1]);
      }
      if (slugIndex >= 0 && normalizedArgs[slugIndex + 1]) {
        parts.push("--slug", normalizedArgs[slugIndex + 1]);
      }
      return parts;
    }
    if (normalizedCommand === "cgc-build" || normalizedCommand === "cgc-fix" || normalizedCommand === "cgc-test") {
      const flowIndex = normalizedArgs.indexOf("--flow");
      const slugIndex = normalizedArgs.indexOf("--slug");
      const stepIndex = normalizedArgs.indexOf("--step-number");
      const parts = [normalizedCommand];
      if (flowIndex >= 0 && normalizedArgs[flowIndex + 1]) {
        parts.push("--flow", normalizedArgs[flowIndex + 1]);
      }
      if (slugIndex >= 0 && normalizedArgs[slugIndex + 1]) {
        parts.push("--slug", normalizedArgs[slugIndex + 1]);
      }
      if (stepIndex >= 0 && normalizedArgs[stepIndex + 1]) {
        parts.push("--step-number", normalizedArgs[stepIndex + 1]);
      }
      return parts;
    }
    if (normalizedCommand === "cgc-review") {
      const auditIndex = normalizedArgs.indexOf("--audit-file");
      const decisionIndex = normalizedArgs.indexOf("--decision");
      const parts = [normalizedCommand];
      if (auditIndex >= 0 && normalizedArgs[auditIndex + 1]) {
        parts.push("--audit-file", normalizedArgs[auditIndex + 1]);
      }
      if (decisionIndex >= 0 && normalizedArgs[decisionIndex + 1]) {
        parts.push("--decision", normalizedArgs[decisionIndex + 1]);
      }
      return parts;
    }
    return [normalizedCommand];
  }
  const nextStep = String(
    machineNextAction.user_action && machineNextAction.user_action.next_step
      ? machineNextAction.user_action.next_step
      : result.next || ""
  ).trim();
  const normalizedNextStep = nextStep.replace(/^下一步[:：]?\s*/, "").trim();
  const normalizedSummary = displaySummary.replace(/\s+/g, " ").trim();
  const compactSummary = normalizedSummary.replace(/\n+/g, " ").trim();
  const recoveryHint = String(
    machineNextAction.user_action && machineNextAction.user_action.recovery_hint
      ? machineNextAction.user_action.recovery_hint
      : ""
  ).trim();
  const dispatchFailureType = String(
    machineNextAction.diagnostics && machineNextAction.diagnostics.dispatch_failure_type
      ? machineNextAction.diagnostics.dispatch_failure_type
      : machineNextAction.dispatch_failure_type || ""
  ).trim();
  const dispatchState = String(
    machineNextAction.diagnostics && machineNextAction.diagnostics.dispatch_state
      ? machineNextAction.diagnostics.dispatch_state
      : machineNextAction.dispatch_state || ""
  ).trim();
  let displayWorkflowState = workflowState;
  if (replyKind === "clarification" || actionType === "wait-user-reply") {
    displayWorkflowState = "needs-clarification";
  }
  if (replyKind === "blocked" || actionType === "dispatch-failed") {
    if (dispatchFailureType === "executor-failure") {
      displayWorkflowState = "blocked-executor";
    } else if (dispatchFailureType === "environment-or-tooling") {
      displayWorkflowState = "blocked-environment";
    } else if (dispatchFailureType === "workflow-state") {
      displayWorkflowState = "blocked-workflow-state";
    } else if (
      dispatchState === "returned-to-planning"
      || dispatchFailureType === "design-gap"
      || dispatchFailureType === "scope-error"
    ) {
      displayWorkflowState = "needs-planning";
    } else if (command) {
      if (command.startsWith("cgc-plan")) {
        displayWorkflowState = "needs-planning";
      } else if (command.startsWith("cgc-build")) {
        displayWorkflowState = "awaiting-build";
      } else if (command.startsWith("cgc-fix")) {
        displayWorkflowState = "awaiting-fix";
      } else if (command.startsWith("cgc-review")) {
        displayWorkflowState = "awaiting-review";
      }
    } else {
      displayWorkflowState = "blocked";
    }
  }
  const mergedNextStep = (
    splitDisplay.inlineNext
    && normalizedNextStep
    && normalizedNextStep !== splitDisplay.inlineNext
  )
    ? splitDisplay.inlineNext
    : (normalizedNextStep || splitDisplay.inlineNext);
  const shouldShowNextStep = (
    mergedNextStep
    && normalizedNextStep !== summary
    && normalizedNextStep !== compactSummary
    && !compactSummary.includes(mergedNextStep)
  );
  const resultLabels = {
    "review-target-missing": "当前还不能直接审核，需要先找到待审核工作流。",
    "start-new-workflow": "当前还没有可继续的工作流，可以直接开始一个新需求。",
    "clarification": "当前还需要先补齐信息，再进入后续步骤。",
    "review": "当前已进入待审核状态。",
    "execution": "当前工作流已具备进入执行阶段的条件。",
    "closed": "当前工作流已收口。",
    "governance": "当前请求已按治理动作处理。",
  };
  const resultLabel = resultLabels[replyKind] || "";
  const fullCommandParts = [command, ...commandArgs].filter(Boolean);
  const shortCommandParts = buildShortCommandHintParts(command, commandArgs);
  const fullCommandText = fullCommandParts.join(" ").trim();
  const shortCommandHint = shortCommandParts.join(" ").trim();
  const renderedFullCommandText = [command, ...commandArgs].map(quoteShellArg).join(" ").trim();
  const renderedShortCommandHint = shortCommandParts.length
    ? shortCommandParts.map(quoteShellArg).join(" ").trim()
    : "";
  const shouldShowShortCommand = Boolean(
    fullCommandText
    && shortCommandHint
    && shortCommandHint !== fullCommandText
  );

  const displayStateLabel = displayWorkflowState === "needs-clarification"
    ? "需要补充规划信息"
    : displayWorkflowState === "blocked-executor"
      ? "执行器返回异常"
      : displayWorkflowState === "blocked-environment"
        ? "本地环境或工具阻塞"
        : displayWorkflowState === "blocked-workflow-state"
          ? "工作流状态未就绪"
          : displayWorkflowState === "blocked"
            ? "当前工作流存在阻塞"
    : (workflowStateLabels[displayWorkflowState] || displayWorkflowState);
  if (displayWorkflowState) {
    lines.push(`状态: ${displayStateLabel}`);
  }
  if (governanceType) {
    lines.push(`治理类型: ${governanceType}`);
  }
  if (command && actionType !== "closed") {
    if (shouldShowShortCommand) {
      lines.push(`建议命令: ${renderedShortCommandHint}`);
      lines.push(`完整命令: ${renderedFullCommandText}`);
    } else {
      lines.push(`建议命令: ${renderedFullCommandText}`);
    }
  }
  if (shouldShowNextStep) {
    lines.push(`下一步: ${mergedNextStep}`);
  }
  if (replyKind === "blocked" && recoveryHint) {
    if (recoveryHint !== mergedNextStep) {
      lines.push(`恢复建议: ${recoveryHint}`);
    }
  }
  if (replyKind === "closed" || actionType === "closed") {
    lines.push("结果: 当前工作流已收口。");
  } else if (replyKind === "review" || actionType === "wait-review-decision") {
    lines.push("结果: 当前已进入待审核状态。");
  } else if (replyKind === "execution" || actionType === "dispatch") {
    lines.push("结果: 当前工作流已具备进入执行阶段的条件。");
  } else if (replyKind === "blocked") {
    const blockedResultLabel = displayWorkflowState === "needs-planning"
      ? "当前工作流已返回规划阶段，需先补齐规划后再继续。"
      : displayWorkflowState === "blocked-executor"
        ? "当前执行器返回异常，需先检查执行日志与审计产物。"
        : displayWorkflowState === "blocked-environment"
          ? "当前被本地环境或工具问题阻塞，需先修复环境后再继续。"
          : displayWorkflowState === "blocked-workflow-state"
            ? "当前工作流状态未就绪，需先修复状态后再继续。"
            : "当前工作流有阻塞，需先按恢复建议处理。";
    lines.push(`结果: ${blockedResultLabel}`);
  } else if (replyKind === "governance" || actionType === "governance") {
    lines.push("结果: 当前请求已按治理动作处理。");
  } else if (resultLabel) {
    lines.push(`结果: ${resultLabel}`);
  }
  return lines.join("\n");
}

function buildRootEntryErrorText(parsedStdout, parsedStderr, rawStdout, rawStderr) {
  const candidates = [
    parsedStderr && parsedStderr.error,
    parsedStdout && parsedStdout.error,
    rawStderr,
    rawStdout,
  ];
  for (const item of candidates) {
    const text = String(item || "").trim();
    if (text) {
      return text;
    }
  }
  return "CodeCGC entry request failed.";
}

function runRootEntry(command, commandArgs) {
  const result = runCapture(command, commandArgs);
  const parsedStdout = tryParseJsonObject(result.stdout);
  const parsedStderr = tryParseJsonObject(result.stderr);

  if ((result.status || 0) === 0) {
    const text = buildRootEntryText(parsedStdout);
    if (text) {
      process.stdout.write(`${text}\n`);
    } else if (typeof result.stdout === "string" && result.stdout.trim()) {
      process.stdout.write(result.stdout);
      if (!result.stdout.endsWith("\n")) {
        process.stdout.write("\n");
      }
    }
    process.exit(0);
  }

  const errorText = buildRootEntryErrorText(parsedStdout, parsedStderr, result.stdout, result.stderr);
  process.stderr.write(`${errorText}\n`);
  process.exit(typeof result.status === "number" ? result.status : 1);
}

function normalizeWorkflowHelpText(rawText, subcommand) {
  const directHelp = `python scripts/codecgc_cli.py ${subcommand}`;
  return String(rawText || "")
    .replaceAll(directHelp, `cgc-${subcommand}`)
    .replaceAll(`python  scripts/codecgc_cli.py ${subcommand}`, `cgc-${subcommand}`)
    .replaceAll("python scripts/codecgc_cli.py", "cgc")
    .replaceAll("python  scripts/codecgc_cli.py", "cgc");
}

const BINARY_ALIASES = { "cgc-init": "cgc-install" };

function resolveCommandInvocation(invokedName, rawArgs) {
  const resolvedName = BINARY_ALIASES[invokedName] || invokedName;
    if (DASH_COMMANDS.has(resolvedName)) {
      return {
        subcommand: resolvedName.slice(4),
        rest: rawArgs,
        invokedAsRoot: false,
      };
    }

  if (rawArgs.length > 0 && DASH_COMMANDS.has(rawArgs[0])) {
    return {
      subcommand: rawArgs[0].slice(4),
      rest: rawArgs.slice(1),
      invokedAsRoot: invokedName === "cgc",
    };
  }

  if (rawArgs.length > 0 && DIRECT_COMMANDS.has(rawArgs[0])) {
    return {
      subcommand: rawArgs[0],
      rest: rawArgs.slice(1),
      invokedAsRoot: invokedName === "cgc",
    };
  }

  return {
    subcommand: "",
    rest: rawArgs,
    invokedAsRoot: invokedName === "cgc",
  };
}

function looksLikeEntryFlag(flag) {
  return new Set([
    "--payload-json",
    "--payload-base64",
    "--payload-file",
    "--mode",
    "--flow",
    "--slug",
    "--summary",
    "--request",
    "--date",
    "--target-path",
    "--kind",
    "--goal",
    "--context",
    "--user-story",
    "--in-scope",
    "--out-of-scope",
    "--acceptance",
    "--risk",
    "--dependency",
    "--assumption",
    "--open-question",
    "--symptom",
    "--reproduction",
    "--expected",
    "--actual",
    "--root-cause",
    "--preferred-fix",
    "--rejected-fix",
    "--decision",
    "--audit-file",
    "--next-step",
    "--artifact-class",
    "--latest",
    "--include-fixtures",
    "--step-number",
    "--checklist-file",
    "--audit-root",
    "--timeout-seconds",
    "--dry-run",
    "--return-all-messages",
    "--auto-dispatch",
    "--force",
  ]).has(flag);
}

function hasOption(argsList, optionName) {
  return argsList.some((item) => item === optionName || item.startsWith(`${optionName}=`));
}

function shouldRouteRootInvocationToEntry(rawArgs) {
  if (rawArgs.length === 0) {
    return false;
  }
  const first = String(rawArgs[0] || "");
  if (!first.startsWith("-")) {
    return true;
  }
  return looksLikeEntryFlag(first);
}

function main() {
  const python = findPython();
  if (!python) {
    console.error("CodeCGC requires Python in PATH.");
    process.exit(1);
  }

  const { subcommand, rest, invokedAsRoot } = resolveCommandInvocation(invokedBinary, args);

  if (!subcommand && (args.length === 0 || (args.length === 1 && (args[0] === "--help" || args[0] === "-h")))) {
    console.log(helpText);
    return;
  }

  if (args.length === 1 && (args[0] === "--version" || args[0] === "-v" || args[0] === "version")) {
    console.log(productVersion);
    return;
  }

  if (invokedAsRoot && subcommand && DIRECT_COMMANDS.has(subcommand)) {
    console.error(`Use cgc-${subcommand} instead of cgc ${subcommand}.`);
    process.exit(1);
  }

  if (rest.length === 1 && (rest[0] === "--help" || rest[0] === "-h")) {
    if (subcommand === "start") {
      console.log(startHelpText);
      return;
    }
    if (subcommand === "install") {
      console.log(installHelpText);
      return;
    }
    if (subcommand === "status") {
      console.log(statusHelpText);
      return;
    }
    if (subcommand === "doctor") {
      console.log(doctorHelpText);
      return;
    }
    if (subcommand === "package-audit") {
      console.log(packageAuditHelpText);
      return;
    }
    if (subcommand === "external-audit") {
      console.log(externalAuditHelpText);
      return;
    }
    if (subcommand === "external-status") {
      console.log(externalStatusHelpText);
      return;
    }
    if (subcommand === "release-readiness") {
      console.log(releaseReadinessHelpText);
      return;
    }
    if (subcommand === "lifecycle") {
      console.log(lifecycleHelpText);
      return;
    }
    if (subcommand === "history") {
      console.log(historyHelpText);
      return;
    }
    if (subcommand === "entry") {
      console.log(entryHelpText);
      return;
    }
    if (subcommand === "plan") {
      console.log(planHelpText);
      return;
    }
    if (subcommand === "build") {
      console.log(buildHelpText);
      return;
    }
    if (subcommand === "fix") {
      console.log(fixHelpText);
      return;
    }
    if (subcommand === "test") {
      console.log(testHelpText);
      return;
    }
    if (subcommand === "review") {
      console.log(reviewHelpText);
      return;
    }
    if (subcommand === "route") {
      console.log(routeHelpText);
      return;
    }
    const helpResult = runCapture(python, [path.join(repoRoot, "scripts", "codecgc_cli.py"), subcommand, "--help"]);
    if (typeof helpResult.stdout === "string" && helpResult.stdout.trim()) {
      process.stdout.write(normalizeWorkflowHelpText(helpResult.stdout, subcommand));
    }
    if (typeof helpResult.stderr === "string" && helpResult.stderr.trim()) {
      process.stderr.write(helpResult.stderr);
    }
    if (typeof helpResult.status === "number") {
      process.exit(helpResult.status);
    }
    process.exit(1);
  }

  if (!subcommand) {
    if (invokedAsRoot && shouldRouteRootInvocationToEntry(args)) {
      if (args[0].startsWith("-")) {
        runRootEntry(python, [path.join(repoRoot, "scripts", "codecgc_cli.py"), "entry", ...args]);
      }
      runRootEntry(python, [path.join(repoRoot, "scripts", "codecgc_cli.py"), "entry", "--request", args.join(" ")]);
    }
    console.log(helpText);
    return;
  }

  if (subcommand === "start") {
    run(
      python,
      [
        path.join(repoRoot, "scripts", "install_codecgc.py"),
        "--mode",
        "start",
        ...rest,
      ],
    );
  }

  if (subcommand === "install") {
    run(python, [path.join(repoRoot, "scripts", "install_codecgc.py"), ...rest]);
  }

  if (subcommand === "status" || subcommand === "doctor") {
    run(
      python,
      [
        path.join(repoRoot, "scripts", "install_codecgc.py"),
        "--mode",
        subcommand === "doctor" ? "doctor" : "status",
        ...rest,
      ],
    );
  }

  if (subcommand === "package-audit") {
    run(
      python,
      [
        path.join(repoRoot, "scripts", "audit_codecgc_package_runtime.py"),
        ...rest,
      ],
    );
  }

  if (subcommand === "external-audit" || subcommand === "external-status") {
    const view = subcommand === "external-status" ? "status" : "audit";
    const commandArgs = [...rest];
    if (!hasOption(commandArgs, "--view")) {
      commandArgs.push("--view", view);
    }
    run(
      python,
      [
        path.join(repoRoot, "scripts", "audit_codecgc_external_capabilities.py"),
        ...commandArgs,
      ],
    );
  }

  if (subcommand === "release-readiness") {
    run(
      python,
      [
        path.join(repoRoot, "scripts", "audit_codecgc_release_readiness.py"),
        ...rest,
      ],
    );
  }

  if (subcommand === "lifecycle") {
    run(
      python,
      [
        path.join(repoRoot, "scripts", "audit_codecgc_lifecycle.py"),
        ...rest,
      ],
    );
  }

  const cliPath = path.join(repoRoot, "scripts", "codecgc_cli.py");
  if (!existsSync(cliPath)) {
    console.error(`CodeCGC CLI not found: ${cliPath}`);
    process.exit(1);
  }

  run(python, [cliPath, subcommand, ...rest]);
}

main();
