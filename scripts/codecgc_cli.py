import argparse
import subprocess
import sys
from pathlib import Path

from codecgc_runtime_paths import PACKAGE_ROOT
from codecgc_runtime_paths import PROJECT_ROOT

WORKSPACE = PACKAGE_ROOT
PROJECT_WORKSPACE = PROJECT_ROOT

HELP_TEXT = """CodeCGC 底层工作流 CLI

用法:
  python scripts/codecgc_cli.py <command> [options]

说明:
  这是实现层调试入口。日常使用优先走 `cgc-*` 产品命令；
  只有在维护 CodeCGC 本身或排查运行时问题时，才直接调用这里。

 按目标选择:
  我要先创建最小工作流脚手架
    init
  我要澄清或修复规划
    plan
  我要用单入口接收新需求、继续任务或解释下一步
    entry
  我要执行一个功能开发步骤
    build
  我要执行一个问题修复步骤
    fix
  我要执行一个测试步骤
    test
  我已经知道 flow + slug + step number，要精确执行一个步骤
    exec
  我要审核一次执行结果并回写
    review
  我要让 CodeCGC 判断下一步命令
    route
  我要只读查看最近工作流历史
    history

命令职责:
  init    初始化 feature 或 issue 的最小产物
  plan    创建或修复规划产物，并整理下一步可执行内容
  entry   单入口调度：新需求、继续、解释下一步
  build   通过高层 feature 执行入口运行一个步骤
  fix     通过高层 issue 执行入口运行一个步骤
  test    通过高层测试执行入口运行一个测试步骤
  exec    精确执行一个指定步骤
  review  根据 audit 结果回写审核结论
  route   根据当前产物状态推荐下一步命令
  history 只读汇总最近 workflow 历史

示例:
  python scripts/codecgc_cli.py entry --request "新增一个登录页面，放在 src/components/LoginForm.tsx"
  python scripts/codecgc_cli.py entry --request "继续刚刚的工作"
  python scripts/codecgc_cli.py plan --flow feature --slug demo-login-ui --summary "Demo login UI feature" --target-path src/components/LoginForm.tsx --kind frontend
  python scripts/codecgc_cli.py build --slug 2026-05-01-demo-login-ui --step-number 1 --dry-run
  python scripts/codecgc_cli.py fix --slug 2026-05-01-demo-sync-bug --step-number 1 --dry-run
  python scripts/codecgc_cli.py test --flow feature --slug 2026-05-01-demo-login-ui --step-number 2 --dry-run
  python scripts/codecgc_cli.py review --audit-file codecgc/execution/demo-login-ui-step-1.json --decision accepted
  python scripts/codecgc_cli.py route --flow feature --slug 2026-05-01-demo-login-ui
  python scripts/codecgc_cli.py history --flow all --status open --last 10
"""

SUBCOMMAND_HELP_TEXT: dict[str, str] = {
    "init": """CodeCGC Workflow Init

用法:
  python scripts/codecgc_cli.py init --flow <feature|issue> --slug <slug> --summary <text> [options]

用途:
  为 feature 或 issue 创建第一份最小工作流脚手架。

适用场景:
  - 这是一个全新的工作流，还没有任何产物。
  - 你已经知道基本的 slug、summary 和大致目标范围。
  - 你想先把最小文件结构建出来，再进入 plan 或 entry。

关键参数:
  --flow <feature|issue>
    指定是 feature 流还是 issue 流。
  --slug <slug>
    用于存储产物的稳定工作流标识。
  --summary <text>
    写入产物中的简短说明。
  --target-path <path>
    可选的初始范围提示。多个路径可重复传入。
  --kind <auto|frontend|backend>
    让 CodeCGC 自动判断路由，或在已知时直接指定前后端。

典型结果:
  生成最小工作流产物，后续可继续走 plan 或 entry。
""",
    "plan": """CodeCGC Workflow Plan

用法:
  python scripts/codecgc_cli.py plan --flow <feature|issue> --slug <slug> --summary <text> [options]

用途:
  在真正委派执行前，澄清或修复一份工作流规划。

适用场景:
  - 需求还不完整，需要补 design 或 checklist。
  - 当前产物里还有只用于规划的 step，或缺少 acceptance。
  - 你希望 CodeCGC 判断下一步是否已经可以进入 build 或 fix。

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

高价值规划字段:
  --goal / --user-story / --in-scope / --acceptance
    更适合 feature 规划。
  --symptom / --expected / --actual / --preferred-fix
    更适合 issue 规划。

典型结果:
  更新规划产物，并告诉你是继续 build、fix，还是先继续澄清。
""",
    "build": """CodeCGC Workflow Build

用法:
  python scripts/codecgc_cli.py build --slug <slug> [--step-number <n>] [options]

用途:
  通过高层 feature 执行入口，运行一个功能开发步骤。

适用场景:
  - feature 规划已经确认。
  - checklist 已存在，并且某个前端或后端步骤已可执行。
  - 你希望 CodeCGC 在写代码前先强制检查路由归属。

关键参数:
  --slug <slug>
    feature 工作流标识。
  --step-number <n>
    可选的精确步骤；不传时，CodeCGC 会自动选择当前 pending step。
  --checklist-file <path>
    可选的显式 checklist 路径。
  --dry-run
    只生成执行意图，不真正委派代码执行。

典型结果:
  运行一个功能开发步骤，写出 execution audit，并进入 review。
""",
    "fix": """CodeCGC Workflow Fix

用法:
  python scripts/codecgc_cli.py fix --slug <slug> [--step-number <n>] [options]

用途:
  通过高层 issue 执行入口，运行一个问题修复步骤。

适用场景:
  - issue 规划或分析已经收敛出一个可执行修复步骤。
  - 下一步是路由后的代码修改，而不是继续诊断。
  - 你希望沿用与 feature 相同的 audit 与 review 约束。

关键参数:
  --slug <slug>
    issue 工作流标识。
  --step-number <n>
    可选的精确步骤；不传时，CodeCGC 会自动选择当前 pending step。
  --checklist-file <path>
    可选的显式修复清单路径。
  --dry-run
    只生成执行意图，不真正委派代码执行。

典型结果:
  运行一个问题修复步骤，写出 execution audit，并进入 review。
""",
    "test": """CodeCGC Workflow Test

用法:
  python scripts/codecgc_cli.py test --flow <feature|issue> --slug <slug> [--step-number <n>] [options]

用途:
  通过高层测试执行入口，运行一个测试步骤。

适用场景:
  - 主代码步骤已经规划完成，下一步是补充或更新对应测试。
  - 你希望测试也进入与 build/fix 一致的 audit 与 review 主流程。
  - 你不希望测试仍然停留在主流程之外的手工动作。

关键参数:
  --flow <feature|issue>
    指定该测试步骤属于 feature 还是 issue 工作流。
  --slug <slug>
    稳定工作流标识。
  --step-number <n>
    可选的精确步骤；不传时，CodeCGC 会自动选择当前 pending 测试步骤。
  --dry-run
    只生成执行意图，不真正委派代码执行。

典型结果:
  运行一个测试步骤，写出 execution audit，并进入 review。
""",
    "review": """CodeCGC Workflow Review

用法:
  python scripts/codecgc_cli.py review --audit-file <path> --decision <accepted|changes-requested> [options]

用途:
  审核一次 execution audit，并把结果回写到工作流产物中。

适用场景:
  - build 或 fix 已执行完成，并产出了 audit 文件。
  - 你要判断这个步骤是“通过”，还是应该退回修改。
  - 你希望把 review 状态写回去，供 route 判断下一步命令。

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
  回写 review 结果，并告诉你当前工作流是关闭、继续执行，还是退回规划。
""",
    "route": """CodeCGC Workflow Route

用法:
  python scripts/codecgc_cli.py route --flow <feature|issue> --slug <slug>

用途:
  根据当前工作流产物状态，让 CodeCGC 判断下一步应该运行哪个命令。

适用场景:
  - 你已经有 workflow slug，但不想手动读产物判断状态。
  - 你需要知道现在该回到 plan、进入 build/fix、进入 review，还是已经结束。
  - Claude 在回复用户前，希望先拿到稳定、确定的下一步命令摘要。

关键参数:
  --flow <feature|issue>
    工作流类型。
  --slug <slug>
    稳定工作流标识。

典型结果:
  返回推荐命令、当前 route 状态，以及为什么做出这个判断。
""",
    "entry": """CodeCGC Workflow Entry

用法:
  python scripts/codecgc_cli.py entry [--request <text> | --payload-file <file> | --payload-json <json>] [options]

用途:
  通过一个单入口处理新需求、继续已有工作流，或解释下一步。

适用场景:
  - 你希望以 Claude 面向用户的方式工作，而不是手动选择 plan/build/fix/review。
  - 你只有自然语言需求，希望 CodeCGC 自动抽取规划信息。
  - 你想继续已有 slug，或直接问 CodeCGC 现在下一步是什么。

关键参数:
  --request <text>
    自然语言请求或操作指令。
  --mode <auto|new|continue|explain>
    让 CodeCGC 自动判断意图，或强制指定交互模式。
  --flow <feature|issue>
    在已知时，可显式指定工作流类型。
  --slug <slug>
    continue / explain 场景下的已有工作流标识。
  --payload-file / --payload-json / --payload-base64
    重新喂入上一轮结构化规划数据，避免重复拼接长参数。

典型结果:
  CodeCGC 会根据当前状态选择继续追问、更新规划，或在准备好后直接调度到 build、fix、review。
""",
    "exec": """CodeCGC Workflow Exec

用法:
  python scripts/codecgc_cli.py exec --flow <feature|issue> --slug <slug> --step-number <n> [options]

用途:
  在你已经明确知道 flow、slug 和 step 编号时，精确执行一个 step。

适用场景:
  - 你需要一个比 build/fix 更底层的执行入口。
  - 你已经知道具体 step，不需要 route 再帮你选择。
  - 你在调试执行行为，或重放某一个特定 step。

关键参数:
  --flow <feature|issue>
    工作流类型。
  --slug <slug>
    稳定工作流标识。
  --step-number <n>
    要执行的精确 step 编号。
  --checklist-file <path>
    可选的显式 checklist 路径。
  --dry-run
    只生成执行意图，不真正委派代码执行。

典型结果:
  执行一个精确 step，写出 execution audit，并把结果留给 review 处理。
""",
    "history": """CodeCGC Workflow History

用法:
  python scripts/codecgc_cli.py history [--flow <all|feature|issue>] [--status <all|open|closed|needs-planning|awaiting-build|awaiting-fix|awaiting-review>] [--last <n>] [options]

用途:
  只读查看最近的 CodeCGC workflow 历史，不改任何状态。

适用场景:
  - 你想知道最近哪些 feature / issue 还没关闭
  - 你不想手工翻 codecgc/features 和 codecgc/issues 目录
  - Claude 想快速拿到“最近应该继续哪条 workflow”

关键参数:
  --flow <all|feature|issue>
    过滤 feature、issue 或全部工作流。
  --status <...>
    过滤 open / closed / needs-planning / awaiting-build / awaiting-fix / awaiting-review 等状态。
  --last <n>
    限制返回最近 N 条记录。
  --include-fixtures
    默认只看 product 工作流；传入后把 fixture 也一起纳入。
  --format <summary|json>
    summary 适合人和 Claude 直接阅读，json 适合自动化。

典型结果:
  返回最近工作流的关闭状态、下一条推荐命令，以及可继续跟进的 slug 列表。
""",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Unified local CLI wrapper for CodeCGC workflow initialization, execution, and review."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize feature or issue workflow artifacts.")
    init_parser.add_argument("--flow", required=True, choices=["feature", "issue"])
    init_parser.add_argument("--slug", required=True)
    init_parser.add_argument("--summary", required=True)
    init_parser.add_argument("--date", default="")
    init_parser.add_argument("--target-path", action="append", default=[])
    init_parser.add_argument("--kind", choices=["auto", "frontend", "backend"], default="auto")
    init_parser.add_argument("--artifact-class", choices=["product", "fixture"], default="product")
    init_parser.add_argument("--force", action="store_true")

    plan_parser = subparsers.add_parser("plan", help="Create or repair a workflow scaffold and route the next step.")
    plan_parser.add_argument("--flow", required=True, choices=["feature", "issue"])
    plan_parser.add_argument("--slug", required=True)
    plan_parser.add_argument("--summary", required=True)
    plan_parser.add_argument("--date", default="")
    plan_parser.add_argument("--target-path", action="append", default=[])
    plan_parser.add_argument("--kind", choices=["auto", "frontend", "backend"], default="auto")
    plan_parser.add_argument("--goal", default="")
    plan_parser.add_argument("--context", action="append", default=[])
    plan_parser.add_argument("--user-story", default="")
    plan_parser.add_argument("--in-scope", action="append", default=[])
    plan_parser.add_argument("--out-of-scope", action="append", default=[])
    plan_parser.add_argument("--acceptance", action="append", default=[])
    plan_parser.add_argument("--risk", action="append", default=[])
    plan_parser.add_argument("--dependency", action="append", default=[])
    plan_parser.add_argument("--assumption", action="append", default=[])
    plan_parser.add_argument("--open-question", action="append", default=[])
    plan_parser.add_argument("--validation", action="append", default=[])
    plan_parser.add_argument("--rollback", action="append", default=[])
    plan_parser.add_argument("--symptom", default="")
    plan_parser.add_argument("--reproduction", default="")
    plan_parser.add_argument("--expected", default="")
    plan_parser.add_argument("--actual", default="")
    plan_parser.add_argument("--root-cause", default="")
    plan_parser.add_argument("--preferred-fix", default="")
    plan_parser.add_argument("--rejected-fix", default="")
    plan_parser.add_argument("--artifact-class", choices=["product", "fixture"], default="product")
    plan_parser.add_argument("--force", action="store_true")

    entry_parser = subparsers.add_parser("entry", help="Single-entry orchestration for new work, continue flow, or explain-next-step.")
    entry_parser.add_argument("--payload-json", default="")
    entry_parser.add_argument("--payload-base64", default="")
    entry_parser.add_argument("--payload-file", default="")
    entry_parser.add_argument("--mode", choices=["auto", "new", "continue", "explain"], default="auto")
    entry_parser.add_argument("--flow", choices=["feature", "issue"], default="")
    entry_parser.add_argument("--slug", default="")
    entry_parser.add_argument("--summary", default="")
    entry_parser.add_argument("--request", default="")
    entry_parser.add_argument("--date", default="")
    entry_parser.add_argument("--target-path", action="append", default=[])
    entry_parser.add_argument("--kind", choices=["auto", "frontend", "backend"], default="auto")
    entry_parser.add_argument("--goal", default="")
    entry_parser.add_argument("--context", action="append", default=[])
    entry_parser.add_argument("--user-story", default="")
    entry_parser.add_argument("--in-scope", action="append", default=[])
    entry_parser.add_argument("--out-of-scope", action="append", default=[])
    entry_parser.add_argument("--acceptance", action="append", default=[])
    entry_parser.add_argument("--risk", action="append", default=[])
    entry_parser.add_argument("--dependency", action="append", default=[])
    entry_parser.add_argument("--assumption", action="append", default=[])
    entry_parser.add_argument("--open-question", action="append", default=[])
    entry_parser.add_argument("--validation", action="append", default=[])
    entry_parser.add_argument("--rollback", action="append", default=[])
    entry_parser.add_argument("--symptom", default="")
    entry_parser.add_argument("--reproduction", default="")
    entry_parser.add_argument("--expected", default="")
    entry_parser.add_argument("--actual", default="")
    entry_parser.add_argument("--root-cause", default="")
    entry_parser.add_argument("--preferred-fix", default="")
    entry_parser.add_argument("--rejected-fix", default="")
    entry_parser.add_argument("--artifact-class", choices=["product", "fixture"], default="product")
    entry_parser.add_argument("--latest", action="store_true")
    entry_parser.add_argument("--include-fixtures", action="store_true")
    entry_parser.add_argument("--step-number", type=int)
    entry_parser.add_argument("--checklist-file", default="")
    entry_parser.add_argument("--audit-root", default="")
    entry_parser.add_argument("--timeout-seconds", type=int, default=120)
    entry_parser.add_argument("--dry-run", action="store_true")
    entry_parser.add_argument("--return-all-messages", action="store_true")
    entry_parser.add_argument("--auto-dispatch", action="store_true")
    entry_parser.add_argument("--decision", choices=["accepted", "changes-requested"], default="")
    entry_parser.add_argument("--audit-file", default="")
    entry_parser.add_argument("--next-step", default="")
    entry_parser.add_argument("--force", action="store_true")

    build_parser = subparsers.add_parser("build", help="Run one feature step through the high-level feature workflow entry.")
    build_parser.add_argument("--slug", required=True)
    build_parser.add_argument("--step-number", type=int)
    build_parser.add_argument("--checklist-file", default="")
    build_parser.add_argument("--audit-root", default="")
    build_parser.add_argument("--timeout-seconds", type=int, default=120)
    build_parser.add_argument("--session-id", default="")
    build_parser.add_argument("--dry-run", action="store_true")
    build_parser.add_argument("--return-all-messages", action="store_true")

    fix_parser = subparsers.add_parser("fix", help="Run one issue-fix step through the high-level fix workflow entry.")
    fix_parser.add_argument("--slug", required=True)
    fix_parser.add_argument("--step-number", type=int)
    fix_parser.add_argument("--checklist-file", default="")
    fix_parser.add_argument("--audit-root", default="")
    fix_parser.add_argument("--timeout-seconds", type=int, default=120)
    fix_parser.add_argument("--session-id", default="")
    fix_parser.add_argument("--dry-run", action="store_true")
    fix_parser.add_argument("--return-all-messages", action="store_true")

    test_parser = subparsers.add_parser("test", help="Run one test step through the high-level test workflow entry.")
    test_parser.add_argument("--flow", required=True, choices=["feature", "issue"])
    test_parser.add_argument("--slug", required=True)
    test_parser.add_argument("--step-number", type=int)
    test_parser.add_argument("--checklist-file", default="")
    test_parser.add_argument("--audit-root", default="")
    test_parser.add_argument("--timeout-seconds", type=int, default=120)
    test_parser.add_argument("--session-id", default="")
    test_parser.add_argument("--dry-run", action="store_true")
    test_parser.add_argument("--return-all-messages", action="store_true")

    exec_parser = subparsers.add_parser("exec", help="Execute one feature or issue step.")
    exec_parser.add_argument("--flow", required=True, choices=["feature", "issue"])
    exec_parser.add_argument("--slug", required=True)
    exec_parser.add_argument("--step-number", required=True, type=int)
    exec_parser.add_argument("--checklist-file", default="")
    exec_parser.add_argument("--audit-root", default="")
    exec_parser.add_argument("--timeout-seconds", type=int, default=120)
    exec_parser.add_argument("--session-id", default="")
    exec_parser.add_argument("--dry-run", action="store_true")
    exec_parser.add_argument("--return-all-messages", action="store_true")

    review_parser = subparsers.add_parser("review", help="Write review results back from an audit artifact.")
    review_parser.add_argument("--audit-file", required=True)
    review_parser.add_argument("--decision", required=True, choices=["accepted", "changes-requested"])
    review_parser.add_argument("--risk", action="append", default=[])
    review_parser.add_argument("--next-step", default="")
    review_parser.add_argument("--force", action="store_true")

    route_parser = subparsers.add_parser("route", help="Recommend the next CodeCGC command from current artifact state.")
    route_parser.add_argument("--flow", required=True, choices=["feature", "issue"])
    route_parser.add_argument("--slug", required=True)

    history_parser = subparsers.add_parser("history", help="Read-only query of recent CodeCGC workflow history.")
    history_parser.add_argument("--flow", choices=["all", "feature", "issue"], default="all")
    history_parser.add_argument("--status", default="all")
    history_parser.add_argument("--last", type=int, default=10)
    history_parser.add_argument("--include-fixtures", action="store_true")
    history_parser.add_argument("--format", choices=["summary", "json"], default="summary")

    return parser


def build_command(args: argparse.Namespace) -> list[str]:
    if args.command == "init":
        command = [
            sys.executable,
            str(WORKSPACE / "scripts" / "init_codecgc_workflow.py"),
            "--flow",
            args.flow,
            "--slug",
            args.slug,
            "--summary",
            args.summary,
            "--kind",
            args.kind,
            "--artifact-class",
            args.artifact_class,
        ]
        if args.date:
            command.extend(["--date", args.date])
        for item in args.target_path:
            command.extend(["--target-path", item])
        if args.force:
            command.append("--force")
        return command

    if args.command == "plan":
        command = [
            sys.executable,
            str(WORKSPACE / "scripts" / "plan_codecgc_workflow.py"),
            "--flow",
            args.flow,
            "--slug",
            args.slug,
            "--summary",
            args.summary,
            "--kind",
            args.kind,
            "--artifact-class",
            args.artifact_class,
        ]
        if args.date:
            command.extend(["--date", args.date])
        for item in args.target_path:
            command.extend(["--target-path", item])
        if args.goal:
            command.extend(["--goal", args.goal])
        if args.user_story:
            command.extend(["--user-story", args.user_story])
        for item in args.context:
            command.extend(["--context", item])
        for item in args.in_scope:
            command.extend(["--in-scope", item])
        for item in args.out_of_scope:
            command.extend(["--out-of-scope", item])
        for item in args.acceptance:
            command.extend(["--acceptance", item])
        for item in args.risk:
            command.extend(["--risk", item])
        for item in args.dependency:
            command.extend(["--dependency", item])
        for item in args.assumption:
            command.extend(["--assumption", item])
        for item in args.open_question:
            command.extend(["--open-question", item])
        for item in args.validation:
            command.extend(["--validation", item])
        for item in args.rollback:
            command.extend(["--rollback", item])
        if args.symptom:
            command.extend(["--symptom", args.symptom])
        if args.reproduction:
            command.extend(["--reproduction", args.reproduction])
        if args.expected:
            command.extend(["--expected", args.expected])
        if args.actual:
            command.extend(["--actual", args.actual])
        if args.root_cause:
            command.extend(["--root-cause", args.root_cause])
        if args.preferred_fix:
            command.extend(["--preferred-fix", args.preferred_fix])
        if args.rejected_fix:
            command.extend(["--rejected-fix", args.rejected_fix])
        if args.force:
            command.append("--force")
        return command

    if args.command == "entry":
        command = [
            sys.executable,
            str(WORKSPACE / "scripts" / "entry_codecgc_workflow.py"),
        ]
        if args.payload_json:
            command.extend(["--payload-json", args.payload_json])
        if args.payload_base64:
            command.extend(["--payload-base64", args.payload_base64])
        if args.payload_file:
            command.extend(["--payload-file", args.payload_file])
        command.extend([
            "--mode",
            args.mode,
            "--kind",
            args.kind,
            "--artifact-class",
            args.artifact_class,
            "--timeout-seconds",
            str(args.timeout_seconds),
        ])
        if args.flow:
            command.extend(["--flow", args.flow])
        if args.slug:
            command.extend(["--slug", args.slug])
        if args.summary:
            command.extend(["--summary", args.summary])
        if args.request:
            command.extend(["--request", args.request])
        if args.date:
            command.extend(["--date", args.date])
        for item in args.target_path:
            command.extend(["--target-path", item])
        if args.goal:
            command.extend(["--goal", args.goal])
        if args.user_story:
            command.extend(["--user-story", args.user_story])
        for item in args.context:
            command.extend(["--context", item])
        for item in args.in_scope:
            command.extend(["--in-scope", item])
        for item in args.out_of_scope:
            command.extend(["--out-of-scope", item])
        for item in args.acceptance:
            command.extend(["--acceptance", item])
        for item in args.risk:
            command.extend(["--risk", item])
        for item in args.dependency:
            command.extend(["--dependency", item])
        for item in args.assumption:
            command.extend(["--assumption", item])
        for item in args.open_question:
            command.extend(["--open-question", item])
        for item in args.validation:
            command.extend(["--validation", item])
        for item in args.rollback:
            command.extend(["--rollback", item])
        if args.symptom:
            command.extend(["--symptom", args.symptom])
        if args.reproduction:
            command.extend(["--reproduction", args.reproduction])
        if args.expected:
            command.extend(["--expected", args.expected])
        if args.actual:
            command.extend(["--actual", args.actual])
        if args.root_cause:
            command.extend(["--root-cause", args.root_cause])
        if args.preferred_fix:
            command.extend(["--preferred-fix", args.preferred_fix])
        if args.rejected_fix:
            command.extend(["--rejected-fix", args.rejected_fix])
        if args.latest:
            command.append("--latest")
        if args.include_fixtures:
            command.append("--include-fixtures")
        if args.step_number is not None:
            command.extend(["--step-number", str(args.step_number)])
        if args.checklist_file:
            command.extend(["--checklist-file", args.checklist_file])
        if args.audit_root:
            command.extend(["--audit-root", args.audit_root])
        if args.session_id:
            command.extend(["--session-id", args.session_id])
        if args.dry_run:
            command.append("--dry-run")
        if args.return_all_messages:
            command.append("--return-all-messages")
        if args.auto_dispatch:
            command.append("--auto-dispatch")
        if args.decision:
            command.extend(["--decision", args.decision])
        if args.audit_file:
            command.extend(["--audit-file", args.audit_file])
        if args.next_step:
            command.extend(["--next-step", args.next_step])
        if args.force:
            command.append("--force")
        return command

    if args.command == "build":
        command = [
            sys.executable,
            str(WORKSPACE / "scripts" / "run_codecgc_build.py"),
            "--slug",
            args.slug,
            "--timeout-seconds",
            str(args.timeout_seconds),
        ]
        if args.step_number is not None:
            command.extend(["--step-number", str(args.step_number)])
        if args.checklist_file:
            command.extend(["--checklist-file", args.checklist_file])
        if args.audit_root:
            command.extend(["--audit-root", args.audit_root])
        if args.session_id:
            command.extend(["--session-id", args.session_id])
        if args.dry_run:
            command.append("--dry-run")
        if args.return_all_messages:
            command.append("--return-all-messages")
        return command

    if args.command == "fix":
        command = [
            sys.executable,
            str(WORKSPACE / "scripts" / "run_codecgc_fix.py"),
            "--slug",
            args.slug,
            "--timeout-seconds",
            str(args.timeout_seconds),
        ]
        if args.step_number is not None:
            command.extend(["--step-number", str(args.step_number)])
        if args.checklist_file:
            command.extend(["--checklist-file", args.checklist_file])
        if args.audit_root:
            command.extend(["--audit-root", args.audit_root])
        if args.session_id:
            command.extend(["--session-id", args.session_id])
        if args.dry_run:
            command.append("--dry-run")
        if args.return_all_messages:
            command.append("--return-all-messages")
        return command

    if args.command == "test":
        command = [
            sys.executable,
            str(WORKSPACE / "scripts" / "run_codecgc_test.py"),
            "--flow",
            args.flow,
            "--slug",
            args.slug,
            "--timeout-seconds",
            str(args.timeout_seconds),
        ]
        if args.step_number is not None:
            command.extend(["--step-number", str(args.step_number)])
        if args.checklist_file:
            command.extend(["--checklist-file", args.checklist_file])
        if args.audit_root:
            command.extend(["--audit-root", args.audit_root])
        if args.session_id:
            command.extend(["--session-id", args.session_id])
        if args.dry_run:
            command.append("--dry-run")
        if args.return_all_messages:
            command.append("--return-all-messages")
        return command

    if args.command == "exec":
        command = [
            sys.executable,
            str(WORKSPACE / "scripts" / "run_codecgc_flow_step.py"),
            "--flow",
            args.flow,
            "--slug",
            args.slug,
            "--step-number",
            str(args.step_number),
            "--timeout-seconds",
            str(args.timeout_seconds),
        ]
        if args.checklist_file:
            command.extend(["--checklist-file", args.checklist_file])
        if args.audit_root:
            command.extend(["--audit-root", args.audit_root])
        if args.dry_run:
            command.append("--dry-run")
        if args.return_all_messages:
            command.append("--return-all-messages")
        return command

    if args.command == "review":
        command = [
            sys.executable,
            str(WORKSPACE / "scripts" / "review_codecgc_workflow.py"),
            "--audit-file",
            args.audit_file,
            "--decision",
            args.decision,
        ]
        for item in args.risk:
            command.extend(["--risk", item])
        if args.next_step:
            command.extend(["--next-step", args.next_step])
        if args.force:
            command.append("--force")
        return command

    if args.command == "route":
        return [
            sys.executable,
            str(WORKSPACE / "scripts" / "route_codecgc_workflow.py"),
            "--flow",
            args.flow,
            "--slug",
            args.slug,
        ]

    if args.command == "history":
        command = [
            sys.executable,
            str(WORKSPACE / "scripts" / "audit_codecgc_workflow_history.py"),
            "--flow",
            args.flow,
            "--status",
            args.status,
            "--last",
            str(args.last),
            "--format",
            args.format,
        ]
        if args.include_fixtures:
            command.append("--include-fixtures")
        return command

    raise ValueError(f"Unsupported command: {args.command}")


def main() -> int:
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] in {"--help", "-h"}):
        print(HELP_TEXT)
        return 0

    if len(sys.argv) == 3 and sys.argv[2] in {"--help", "-h"}:
        subcommand = sys.argv[1]
        help_text = SUBCOMMAND_HELP_TEXT.get(subcommand, "")
        if help_text:
            print(help_text)
            return 0

    parser = build_parser()
    args = parser.parse_args()
    command = build_command(args)

    completed = subprocess.run(command, cwd=PROJECT_WORKSPACE)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
