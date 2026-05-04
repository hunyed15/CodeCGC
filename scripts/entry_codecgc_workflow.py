import argparse
import base64
import hashlib
import json
import re
import sys
from typing import Any
from pathlib import Path

from build_codecgc_task import classify_path
from build_codecgc_task import load_checklist_yaml
from build_codecgc_task import load_simple_routing_config
from codecgc_artifact_roots import discover_flow_directory
from codecgc_artifact_roots import flow_root
from codecgc_command_surface import matches_command
from codecgc_command_surface import to_internal_command
from codecgc_command_surface import to_public_command
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_routing_paths import resolve_active_routing_file
from codecgc_runtime_paths import PACKAGE_ROOT
from codecgc_session_recovery import resolve_session_id_from_task
from codecgc_workflow_runtime import run_json_script

WORKSPACE = PACKAGE_ROOT
ROUTING_FILE = resolve_active_routing_file()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Single-entry orchestration layer for CodeCGC."
    )
    parser.add_argument("--payload-json", default="")
    parser.add_argument("--payload-base64", default="")
    parser.add_argument("--payload-file", default="")
    parser.add_argument("--mode", choices=["auto", "new", "continue", "explain"], default="auto")
    parser.add_argument("--flow", choices=["feature", "issue"], default="")
    parser.add_argument("--slug", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--request", default="")
    parser.add_argument("--date", default="")
    parser.add_argument("--target-path", action="append", default=[])
    parser.add_argument("--kind", choices=["auto", "frontend", "backend"], default="auto")
    parser.add_argument("--goal", default="")
    parser.add_argument("--context", action="append", default=[])
    parser.add_argument("--user-story", default="")
    parser.add_argument("--in-scope", action="append", default=[])
    parser.add_argument("--out-of-scope", action="append", default=[])
    parser.add_argument("--acceptance", action="append", default=[])
    parser.add_argument("--risk", action="append", default=[])
    parser.add_argument("--dependency", action="append", default=[])
    parser.add_argument("--assumption", action="append", default=[])
    parser.add_argument("--open-question", action="append", default=[])
    parser.add_argument("--validation", action="append", default=[])
    parser.add_argument("--rollback", action="append", default=[])
    parser.add_argument("--symptom", default="")
    parser.add_argument("--reproduction", default="")
    parser.add_argument("--expected", default="")
    parser.add_argument("--actual", default="")
    parser.add_argument("--root-cause", default="")
    parser.add_argument("--preferred-fix", default="")
    parser.add_argument("--rejected-fix", default="")
    parser.add_argument("--artifact-class", choices=["product", "fixture"], default="product")
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--include-fixtures", action="store_true")
    parser.add_argument("--step-number", type=int)
    parser.add_argument("--checklist-file", default="")
    parser.add_argument("--audit-root", default="")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--return-all-messages", action="store_true")
    parser.add_argument("--auto-dispatch", action="store_true")
    parser.add_argument("--decision", choices=["accepted", "changes-requested"], default="")
    parser.add_argument("--audit-file", default="")
    parser.add_argument("--next-step", default="")
    parser.add_argument("--force", action="store_true")
    return parser


def load_payload_input(args: argparse.Namespace) -> dict[str, Any]:
    if args.payload_json.strip():
        payload = json.loads(args.payload_json)
    elif args.payload_base64.strip():
        decoded = base64.b64decode(args.payload_base64).decode("utf-8")
        payload = json.loads(decoded)
    elif args.payload_file.strip():
        payload = json.loads(Path(args.payload_file).read_text(encoding="utf-8-sig"))
    else:
        return {}

    if not isinstance(payload, dict):
        raise ValueError("Entry payload must be a JSON object.")
    return payload


def merge_scalar_arg(args: argparse.Namespace, payload: dict[str, Any], field: str, default_value: str = "") -> None:
    current = getattr(args, field)
    if current != default_value:
        return
    value = payload.get(field)
    if isinstance(value, str) and value.strip():
        setattr(args, field, value.strip())


def merge_list_arg(args: argparse.Namespace, payload: dict[str, Any], field: str) -> None:
    current = getattr(args, field)
    if current:
        return
    value = payload.get(field)
    if isinstance(value, list):
        merged = [str(item).strip() for item in value if str(item).strip()]
        if merged:
            setattr(args, field, merged)
    elif isinstance(value, str) and value.strip():
        setattr(args, field, [value.strip()])


def merge_list_arg_alias(args: argparse.Namespace, payload: dict[str, Any], field: str, alias: str) -> None:
    current = getattr(args, field)
    if current:
        return
    value = payload.get(alias)
    if isinstance(value, list):
        merged = [str(item).strip() for item in value if str(item).strip()]
        if merged:
            setattr(args, field, merged)
    elif isinstance(value, str) and value.strip():
        setattr(args, field, [value.strip()])


def apply_entry_payload(args: argparse.Namespace) -> argparse.Namespace:
    payload = load_payload_input(args)
    if not payload:
        return args

    merge_scalar_arg(args, payload, "mode", "auto")
    merge_scalar_arg(args, payload, "flow", "")
    merge_scalar_arg(args, payload, "slug", "")
    merge_scalar_arg(args, payload, "summary", "")
    merge_scalar_arg(args, payload, "request", "")
    merge_scalar_arg(args, payload, "date", "")
    merge_scalar_arg(args, payload, "kind", "auto")
    merge_scalar_arg(args, payload, "goal", "")
    merge_scalar_arg(args, payload, "user_story", "")
    merge_scalar_arg(args, payload, "symptom", "")
    merge_scalar_arg(args, payload, "reproduction", "")
    merge_scalar_arg(args, payload, "expected", "")
    merge_scalar_arg(args, payload, "actual", "")
    merge_scalar_arg(args, payload, "root_cause", "")
    merge_scalar_arg(args, payload, "preferred_fix", "")
    merge_scalar_arg(args, payload, "rejected_fix", "")
    merge_scalar_arg(args, payload, "artifact_class", "product")
    merge_scalar_arg(args, payload, "audit_root", "")
    merge_scalar_arg(args, payload, "audit_file", "")
    merge_scalar_arg(args, payload, "next_step", "")
    merge_scalar_arg(args, payload, "decision", "")

    merge_list_arg(args, payload, "target_path")
    merge_list_arg_alias(args, payload, "target_path", "target_paths")
    merge_list_arg(args, payload, "context")
    merge_list_arg(args, payload, "in_scope")
    merge_list_arg(args, payload, "out_of_scope")
    merge_list_arg(args, payload, "acceptance")
    merge_list_arg(args, payload, "risk")
    merge_list_arg(args, payload, "dependency")
    merge_list_arg(args, payload, "assumption")
    merge_list_arg(args, payload, "open_question")
    merge_list_arg(args, payload, "validation")
    merge_list_arg(args, payload, "rollback")

    if not args.latest and bool(payload.get("latest")):
        args.latest = True
    if not args.include_fixtures and bool(payload.get("include_fixtures")):
        args.include_fixtures = True
    if args.step_number is None and payload.get("step_number") is not None:
        args.step_number = int(payload["step_number"])
    if args.timeout_seconds == 120 and payload.get("timeout_seconds") is not None:
        args.timeout_seconds = int(payload["timeout_seconds"])
    if not args.auto_dispatch and bool(payload.get("auto_dispatch")):
        args.auto_dispatch = True
    if not args.dry_run and bool(payload.get("dry_run")):
        args.dry_run = True
    if not args.return_all_messages and bool(payload.get("return_all_messages")):
        args.return_all_messages = True
    if not args.force and bool(payload.get("force")):
        args.force = True

    return args


def resolve_governance_followup(payload: dict[str, Any], request: str) -> dict[str, Any]:
    governance_type = str(payload.get("governance_type", "")).strip()
    artifact_path = str(payload.get("artifact_path", "")).strip()
    if not governance_type or not artifact_path:
        return {}

    request_text = request.strip()
    if not request_text:
        return {}

    lowered = request_text.lower()
    original_summary = str(payload.get("artifact_summary", "")).strip()

    def pick_clause(*patterns: str) -> str:
        return extract_clause(request_text, list(patterns))

    def split_labeled_fields(mapping: dict[str, list[str]]) -> dict[str, str]:
        labels: list[tuple[int, int, str]] = []
        for key, aliases in mapping.items():
            for alias in aliases:
                for match in re.finditer(rf"{re.escape(alias)}[:：]\s*", request_text, flags=re.IGNORECASE):
                    labels.append((match.start(), match.end(), key))
        labels.sort(key=lambda item: item[0])
        values: dict[str, str] = {key: "" for key in mapping}
        for index, (_, content_start, key) in enumerate(labels):
            next_start = labels[index + 1][0] if index + 1 < len(labels) else len(request_text)
            chunk = request_text[content_start:next_start].strip(" 。；;，,\n")
            if chunk and not values.get(key):
                values[key] = chunk
        return values

    def build_flag_args(pairs: list[tuple[str, str]], *, required_pairs: list[tuple[str, str]] | None = None) -> list[str]:
        args: list[str] = []
        for flag, value in required_pairs or []:
            args.extend([flag, value])
        for flag, value in pairs:
            if value.strip():
                args.extend([flag, value.strip()])
        return args

    if governance_type == "guide":
        details = split_labeled_fields(
            {
                "purpose": ["目的", "purpose"],
                "steps": ["步骤", "steps", "step"],
                "boundary": ["边界", "boundary"],
            }
        )
        details["append_note"] = request_text if not any(details.values()) else ""
        return {
            "governance_type": governance_type,
            "script": "write_codecgc_guide.py",
            "args": build_flag_args(
                [
                    ("--purpose", details["purpose"]),
                    ("--steps", details["steps"]),
                    ("--boundary", details["boundary"]),
                    ("--append-note", details["append_note"]),
                ],
                required_pairs=[
                    ("--summary", original_summary or request_text),
                    ("--artifact-path", artifact_path),
                ],
            ),
            "artifact_summary": original_summary or request_text,
            "artifact_path": artifact_path,
        }

    if governance_type == "libdoc":
        details = split_labeled_fields(
            {
                "entry": ["入口", "entry"],
                "contract": ["契约", "contract"],
                "example": ["示例", "example"],
                "boundary": ["边界", "boundary"],
            }
        )
        details["append_note"] = request_text if not any(details.values()) else ""
        return {
            "governance_type": governance_type,
            "script": "write_codecgc_libdoc.py",
            "args": build_flag_args(
                [
                    ("--entry", details["entry"]),
                    ("--contract", details["contract"]),
                    ("--example", details["example"]),
                    ("--boundary", details["boundary"]),
                    ("--append-note", details["append_note"]),
                ],
                required_pairs=[
                    ("--summary", original_summary or request_text),
                    ("--artifact-path", artifact_path),
                ],
            ),
            "artifact_summary": original_summary or request_text,
            "artifact_path": artifact_path,
        }

    if governance_type == "trick":
        details = split_labeled_fields(
            {
                "practice": ["做法", "practice"],
                "scope": ["范围", "scope"],
                "counterexample": ["反例", "误用", "counterexample"],
            }
        )
        details["append_note"] = request_text if not any(details.values()) else ""
        return {
            "governance_type": governance_type,
            "script": "write_codecgc_trick.py",
            "args": build_flag_args(
                [
                    ("--practice", details["practice"]),
                    ("--scope", details["scope"]),
                    ("--counterexample", details["counterexample"]),
                    ("--append-note", details["append_note"]),
                ],
                required_pairs=[
                    ("--summary", original_summary or request_text),
                    ("--artifact-path", artifact_path),
                ],
            ),
            "artifact_summary": original_summary or request_text,
            "artifact_path": artifact_path,
        }

    if governance_type == "explore":
        details = split_labeled_fields(
            {
                "question_detail": ["问题", "question"],
                "target_modules": ["模块", "目录", "文件", "module"],
                "expected_output": ["输出", "结论", "output"],
            }
        )
        details["append_note"] = request_text if not any(details.values()) else ""
        return {
            "governance_type": governance_type,
            "script": "write_codecgc_explore.py",
            "args": build_flag_args(
                [
                    ("--question-detail", details["question_detail"]),
                    ("--target-modules", details["target_modules"]),
                    ("--expected-output", details["expected_output"]),
                    ("--append-note", details["append_note"]),
                ],
                required_pairs=[
                    ("--summary", original_summary or request_text),
                    ("--artifact-path", artifact_path),
                ],
            ),
            "artifact_summary": original_summary or request_text,
            "artifact_path": artifact_path,
        }

    return {}


def summarize_new_work_seed(args: argparse.Namespace, flow: str) -> str:
    if args.summary.strip():
        return args.summary.strip()
    if args.request.strip():
        return args.request.strip()
    if flow == "feature":
        for value in (args.goal, args.user_story):
            if value.strip():
                return value.strip()
    else:
        for value in (args.symptom, args.expected, args.actual):
            if value.strip():
                return value.strip()
    target_paths = [item.strip() for item in args.target_path if item.strip()]
    if target_paths:
        return f"{flow} for {target_paths[0]}"
    return ""


def infer_flow_for_new_work(args: argparse.Namespace) -> str:
    if args.flow:
        return args.flow
    request = args.request.strip().lower()
    issue_signals = [
        args.symptom,
        args.reproduction,
        args.expected,
        args.actual,
        args.root_cause,
        args.preferred_fix,
        args.rejected_fix,
    ]
    issue_keywords = [
        "bug",
        "fix",
        "issue",
        "error",
        "failure",
        "broken",
        "problem",
        "修复",
        "问题",
        "报错",
        "异常",
        "故障",
    ]
    if any(keyword in request for keyword in issue_keywords):
        return "issue"
    return "issue" if any(value.strip() for value in issue_signals) else "feature"


def request_implies_continue(request: str) -> bool:
    lowered = request.lower()
    keywords = [
        "continue",
        "resume",
        "pick up",
        "go on",
        "继续",
        "接着",
        "继续做",
        "继续推进",
    ]
    return any(keyword in lowered for keyword in keywords)


def request_implies_explain(request: str) -> bool:
    lowered = request.lower()
    keywords = [
        "what next",
        "next step",
        "status",
        "explain",
        "why",
        "state",
        "下一步",
        "现在该做什么",
        "状态",
        "解释",
        "看看进度",
    ]
    return any(keyword in lowered for keyword in keywords)


def request_implies_execute(request: str) -> bool:
    lowered = request.lower()
    keywords = [
        "implement",
        "build it",
        "fix it",
        "execute",
        "run it",
        "go ahead",
        "start now",
        "处理掉",
        "解决掉",
        "直接做",
        "开始做",
        "开工",
        "执行",
        "继续处理",
        "继续执行",
        "直接修复",
        "马上修复",
        "立即修复",
        "直接实现",
        "马上实现",
        "立即实现",
        "直接开始",
        "马上开始",
        "立即开始",
        "测试",
        "补测试",
        "写测试",
        "加测试",
        "生成测试",
    ]
    return any(keyword in lowered for keyword in keywords)


def request_implies_review(request: str) -> bool:
    lowered = request.lower()
    keywords = [
        "review",
        "acceptance",
        "approve",
        "验收",
        "审核",
        "审查",
        "检查一下",
        "看下结果",
        "过一下",
        "通过",
        "不通过",
    ]
    return any(keyword in lowered for keyword in keywords)


def normalize_request_shortcut(request: str) -> str:
    normalized = request.strip().lower()
    normalized = re.sub(r"\s+", "", normalized)
    normalized = normalized.strip("`\"'，,。；;：:！？!?（）()[]{}")
    return normalized


def classify_existing_workflow_shortcut(request: str) -> str:
    normalized = normalize_request_shortcut(request)
    if not normalized:
        return ""

    explain_shortcuts = {
        "下一步",
        "现在下一步该做什么",
        "当前下一步",
        "看看进度",
        "当前状态",
        "解释一下当前状态",
        "解释当前状态",
        "看看状态",
    }
    continue_shortcuts = {
        "继续",
        "继续做",
        "继续处理",
        "继续推进",
        "继续执行",
        "继续刚刚的工作",
        "接着做",
        "接着处理",
        "直接做",
        "直接开始",
        "开始做",
        "开始吧",
        "开工",
        "马上开始",
        "立即开始",
        "处理掉",
        "解决掉",
        "审核",
        "审核一下",
        "审查",
        "审查一下",
        "验收",
        "验收一下",
        "看下结果",
        "看结果",
        "过一下",
        "通过",
        "不通过",
        "需修改",
        "需要修改",
        "测试",
        "补测试",
        "写测试",
        "加测试",
        "生成测试",
    }

    if normalized in explain_shortcuts:
        return "explain"
    if normalized in continue_shortcuts:
        return "continue"
    return ""


def classify_governance_request(request: str) -> dict[str, str]:
    lowered = request.lower().strip()
    if not lowered:
        return {}

    governance_patterns = [
        (
            "cgc-arch",
            "arch",
            [
                "架构文档",
                "更新架构",
                "架构图",
                "系统图",
                "architecture",
                "system map",
                "integration map",
            ],
            "当前请求更适合回写长期架构现状，而不是进入 feature/issue 执行流。",
            "下一步进入 cgc-arch，更新 codecgc/architecture/ 下的当前态文档。",
        ),
        (
            "cgc-req",
            "req",
            [
                "需求文档",
                "requirements",
                "回写需求",
                "补需求",
                "当前能力说明",
                "稳定需求",
                "需求边界",
                "稳定需求边界",
                "能力边界",
                "产品边界",
            ],
            "当前请求更适合回写稳定需求边界，而不是进入一次性执行流。",
            "下一步进入 cgc-req，更新 codecgc/requirements/ 下的稳定能力说明。",
        ),
        (
            "cgc-explore",
            "explore",
            [
                "explore",
                "探索一下",
                "快速熟悉",
                "这个仓库里",
                "怎么实现",
                "module overview",
                "spike",
            ],
            "当前请求更适合登记为定向代码探索，而不是直接进入执行流。",
            "下一步进入 cgc-explore，沉淀这条探索问题或模块概览请求。",
        ),
        (
            "cgc-roadmap",
            "roadmap",
            [
                "roadmap",
                "路线图",
                "分阶段",
                "阶段拆解",
                "大需求拆解",
                "长期规划",
                "生命周期蓝图",
                "发布规划",
                "运维规划",
                "maintenance",
                "release plan",
                "release roadmap",
                "maintenance roadmap",
                "ops roadmap",
                "lifecycle",
            ],
            "当前请求更像 roadmap 级分解，不适合直接落成单个 feature/issue step。",
            "下一步进入 cgc-roadmap，把需求拆成 phases、tracks 或 child workflows。",
        ),
        (
            "cgc-decide",
            "decide",
            [
                "记录决定",
                "记录这个决定",
                "决定记录下来",
                "把这条决定记录下来",
                "记成决定",
                "长期决定",
                "记录为约束",
                "作为长期约束",
                "技术选型",
                "架构决策",
                "adr",
                "decision",
                "约束",
                "编码规约",
            ],
            "当前请求是长期决策归档动作，不应误走 feature/issue 执行流。",
            "下一步进入 cgc-decide，记录已确认的约束、选型或长期规则。",
        ),
        (
            "cgc-learn",
            "learn",
            [
                "沉淀经验",
                "记录经验",
                "沉淀成经验",
                "值得沉淀",
                "值得记录",
                "踩坑",
                "教训",
                "pitfall",
                "learning",
                "最佳实践",
                "经验",
            ],
            "当前请求是经验沉淀动作，不应误走一次性执行流。",
            "下一步进入 cgc-learn，记录可复用的经验、坑点或默认做法。",
        ),
        (
            "cgc-refactor",
            "refactor",
            [
                "重构",
                "refactor",
                "代码优化",
                "结构优化",
                "可读性优化",
                "性能优化",
            ],
            "当前请求更像受控重构，而不是新 feature 或 issue 修复。",
            "下一步进入 cgc-refactor，先确认行为不变边界，再进入受控执行。",
        ),
        (
            "cgc-guide",
            "guide",
            [
                "用户指南",
                "开发者指南",
                "操作指南",
                "使用指南",
                "guide",
                "how to",
                "使用文档",
            ],
            "当前请求更适合沉淀为面向用户或开发者的任务导向指南。",
            "下一步进入 cgc-guide，把这条使用说明沉淀为长期 guide 资产。",
        ),
        (
            "cgc-libdoc",
            "libdoc",
            [
                "api 文档",
                "组件文档",
                "命令文档",
                "参考文档",
                "libdoc",
                "reference doc",
            ],
            "当前请求更适合沉淀为公开表面的参考文档，而不是执行流。",
            "下一步进入 cgc-libdoc，生成对应 API、组件或命令参考资产。",
        ),
        (
            "cgc-trick",
            "trick",
            [
                "技巧",
                "trick",
                "pattern",
                "技术技巧",
                "记录这个用法",
                "记录库用法",
                "最佳用法",
            ],
            "当前请求更适合沉淀为可复用的模式、库用法或技巧处方。",
            "下一步进入 cgc-trick，记录这条可复用技巧资产。",
        ),
    ]

    for skill, governance_type, keywords, summary, next_step in governance_patterns:
        if any(keyword in lowered for keyword in keywords):
            return {
                "skill": skill,
                "governance_type": governance_type,
                "human_summary": summary,
                "next": next_step,
            }
    return {}


def infer_review_decision_from_request(request: str) -> str:
    lowered = request.lower()
    accepted_keywords = [
        "accept",
        "approve",
        "passed",
        "通过",
        "通过验收",
        "没问题就通过",
        "可以通过",
    ]
    rejected_keywords = [
        "changes requested",
        "request changes",
        "reject",
        "不通过",
        "驳回",
        "需要修改",
        "有问题就退回",
    ]
    if any(keyword in lowered for keyword in rejected_keywords):
        return "changes-requested"
    if any(keyword in lowered for keyword in accepted_keywords):
        return "accepted"
    return ""


def build_request_slug(flow: str, request: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", request.lower()).strip("-")
    if not normalized:
        normalized = "request"
    normalized = re.sub(r"-{2,}", "-", normalized)
    normalized = "-".join(normalized.split("-")[:6]).strip("-") or "request"
    digest = hashlib.md5(request.encode("utf-8")).hexdigest()[:8]
    return f"{flow}-{normalized}-{digest}"


def resolve_new_slug(args: argparse.Namespace, flow: str) -> str:
    if args.slug.strip():
        return args.slug
    seed = summarize_new_work_seed(args, flow)
    if seed:
        return build_request_slug(flow, seed)
    raise ValueError("New work requires --slug, --request, or enough payload fields to infer a summary.")


def resolve_new_summary(args: argparse.Namespace) -> str:
    if args.summary.strip():
        return args.summary
    if args.request.strip():
        return args.request.strip()
    flow = infer_flow_for_new_work(args)
    seed = summarize_new_work_seed(args, flow)
    if seed:
        return seed
    raise ValueError("New work requires --summary, --request, or enough payload fields to infer a summary.")


def normalize_request_path(path_text: str) -> str:
    normalized = path_text.strip().strip("\"'`")
    normalized = normalized.replace("\\", "/")
    normalized = re.sub(r"/{2,}", "/", normalized)
    return normalized.rstrip(".,;:!?)]}")


def _is_likely_false_positive_path(normalized: str) -> bool:
    segments = normalized.split("/")
    if all(seg.isdigit() for seg in segments if seg):
        return True
    if re.match(r"^\d{4}/\d{2}(/\d{2})?$", normalized):
        return True
    if re.match(r"^v?\d+\.\d+", segments[0]):
        return True
    if normalized.count("/") == 1 and "." not in normalized:
        first, second = segments[0], segments[1] if len(segments) > 1 else ""
        if first.isdigit() or second.isdigit():
            return True
    return False


def extract_target_paths_from_request(request: str) -> list[str]:
    if not request.strip():
        return []

    matches = re.findall(r"(?:(?:[A-Za-z]:)?[\\/])?(?:[\w.\-]+[\\/])+[\w.\-]+", request)
    extracted: list[str] = []
    seen: set[str] = set()

    for raw in matches:
        normalized = normalize_request_path(raw)
        if "/" not in normalized:
            continue
        lowered = normalized.lower()
        if lowered.startswith("http/") or lowered.startswith("https/"):
            continue
        if _is_likely_false_positive_path(lowered):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        extracted.append(normalized)

    return extracted


def classify_request_paths(paths: list[str]) -> str:
    if not paths:
        return "auto"

    routing = load_simple_routing_config(ROUTING_FILE)
    categories = {classify_path(path, routing) for path in paths}

    if categories == {"frontend"}:
        return "frontend"
    if categories == {"backend"}:
        return "backend"
    return "auto"


def resolve_target_paths(args: argparse.Namespace) -> list[str]:
    explicit = [item.strip() for item in args.target_path if item.strip()]
    if explicit:
        return explicit
    return extract_target_paths_from_request(args.request)


def resolve_kind(args: argparse.Namespace, target_paths: list[str]) -> str:
    if args.kind != "auto":
        return args.kind
    return classify_request_paths(target_paths)


def cleaned_items(items: list[str]) -> list[str]:
    return [item.strip() for item in items if item.strip()]


def extract_clause(request: str, patterns: list[str]) -> str:
    if not request.strip():
        return ""
    for pattern in patterns:
        match = re.search(pattern, request, flags=re.IGNORECASE)
        if not match:
            continue
        value = str(match.group(1)).strip(" ，,；;。\"'")
        if value:
            return value
    return ""


def infer_feature_goal(args: argparse.Namespace) -> str:
    if args.goal.strip():
        return args.goal
    request = args.request.strip()
    if not request:
        return ""
    trimmed = re.split(r"[，,。；;]", request, maxsplit=1)[0].strip()
    return trimmed or request


def infer_feature_user_story(args: argparse.Namespace) -> str:
    if args.user_story.strip():
        return args.user_story
    return extract_clause(
        args.request,
        [
            r"(作为[^，,。；;]*?[我你他她它]?(?:想|希望|需要)[^，,。；;]*)",
            r"(As\s+an?[^,.;\n]*?(?:I want|I need)[^,.;\n]*)",
        ],
    )


def infer_in_scope(args: argparse.Namespace, flow: str, target_paths: list[str]) -> list[str]:
    explicit = [item.strip() for item in args.in_scope if item.strip()]
    if explicit:
        return explicit
    inferred = extract_clause(
        args.request,
        [
            r"范围(?:只)?包括(.+?)(?:[，,；;。]|$)",
            r"只包括(.+?)(?:[，,；;。]|$)",
            r"in scope(?: is|:)?\s*(.+?)(?:[,.;\n]|$)",
        ],
    )
    if inferred:
        return [inferred]

    if target_paths:
        if flow == "feature":
            return [f"Implement the requested feature only in {', '.join(target_paths)}."]
        if flow == "issue":
            return [f"Fix the reported issue only in {', '.join(target_paths)}."]
    return []


def infer_acceptance(args: argparse.Namespace, flow: str) -> list[str]:
    explicit = [item.strip() for item in args.acceptance if item.strip()]
    if explicit:
        return explicit

    inferred = extract_clause(
        args.request,
        [
            r"验收(?:标准)?(?:是|为|包括)?(.+?)(?:[，,；;。]|$)",
            r"acceptance(?: criteria)?(?: is| are|:)?\s*(.+?)(?:[,.;\n]|$)",
        ],
    )
    if inferred:
        return [inferred]

    if flow == "issue":
        expected = infer_issue_expected(args)
        if expected:
            return [expected]
    return []


def infer_issue_symptom(args: argparse.Namespace) -> str:
    if args.symptom.strip():
        return args.symptom
    request = args.request.strip()
    if not request:
        return ""
    before_expected = re.split(r"预期|expected", request, maxsplit=1, flags=re.IGNORECASE)[0].strip(" ，,；;。")
    return before_expected


def infer_issue_expected(args: argparse.Namespace) -> str:
    if args.expected.strip():
        return args.expected
    return extract_clause(
        args.request,
        [
            r"预期(?:是|为)?(.+?)(?:[，,；;。]|$)",
            r"expected(?: is|:)?\s*(.+?)(?:[,.;\n]|$)",
        ],
    )


def infer_issue_actual(args: argparse.Namespace) -> str:
    if args.actual.strip():
        return args.actual
    return extract_clause(
        args.request,
        [
            r"实际(?:是|为)?(.+?)(?:[，,；;。]|$)",
            r"actual(?: is|:)?\s*(.+?)(?:[,.;\n]|$)",
        ],
    )


def clean_placeholder_text(value: str) -> str:
    cleaned = value.strip()
    placeholders = {
        "",
        "TODO",
        "todo",
        "待补充",
        "当前无。",
        "当前无",
        "无",
    }
    return "" if cleaned in placeholders else cleaned


def read_text_if_exists(path: Path | None) -> str:
    if not path or not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig")


def find_first_artifact_file(directory: Path, pattern: str) -> Path | None:
    matches = sorted(directory.glob(pattern))
    return matches[0] if matches else None


def extract_frontmatter_value(text: str, key: str) -> str:
    if not text.strip():
        return ""
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+?)\s*$", text)
    if not match:
        return ""
    return clean_placeholder_text(str(match.group(1)).strip().strip("\"'"))


def extract_markdown_bullet_value(text: str, label: str) -> str:
    if not text.strip():
        return ""
    match = re.search(rf"(?m)^\s*-\s*{re.escape(label)}:\s*(.+?)\s*$", text)
    if not match:
        return ""
    return clean_placeholder_text(str(match.group(1)).strip())


def extract_markdown_section_bullets(text: str, heading: str) -> list[str]:
    if not text.strip():
        return []
    pattern = rf"{re.escape(heading)}\s*\n(?P<body>.*?)(?=\n##\s|\Z)"
    match = re.search(pattern, text, flags=re.DOTALL)
    if not match:
        return []

    bullets: list[str] = []
    for raw_line in str(match.group("body")).splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("- "):
            continue
        value = clean_placeholder_text(stripped[2:].strip())
        if value:
            bullets.append(value)
    return bullets


def unique_nonempty(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = clean_placeholder_text(str(item))
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def load_step_contract_context(checklist_path: Path | None) -> dict[str, Any]:
    if not checklist_path or not checklist_path.exists():
        return {}

    data = load_checklist_yaml(checklist_path)
    steps = data.get("steps", [])
    if not isinstance(steps, list):
        return {}

    target_paths: list[str] = []
    acceptance: list[str] = []
    kinds: list[str] = []

    for step in steps:
        if not isinstance(step, dict):
            continue
        codecgc = step.get("codecgc")
        if not isinstance(codecgc, dict):
            continue
        kinds.append(str(codecgc.get("kind", "")).strip())
        target_paths.extend(str(item).strip() for item in codecgc.get("target_paths", []) if str(item).strip())
        acceptance.extend(str(item).strip() for item in codecgc.get("acceptance", []) if str(item).strip())

    distinct_kinds = {kind for kind in kinds if kind}
    resolved_kind = ""
    if len(distinct_kinds) == 1:
        resolved_kind = next(iter(distinct_kinds))
    elif len(distinct_kinds) > 1:
        resolved_kind = "auto"

    return {
        "kind": resolved_kind,
        "target_paths": unique_nonempty(target_paths),
        "acceptance": unique_nonempty(acceptance),
    }


def build_existing_workflow_replan_payload(flow: str, slug: str) -> dict[str, Any]:
    discovered = discover_flow_directory(flow, slug, "auto")
    if not discovered:
        return {}

    _, directory = discovered
    payload: dict[str, Any] = {
        "flow": flow,
        "slug": slug,
    }

    if flow == "issue":
        report_text = read_text_if_exists(find_first_artifact_file(directory, "*-report.md"))
        analysis_text = read_text_if_exists(find_first_artifact_file(directory, "*-analysis.md"))
        step_context = load_step_contract_context(find_first_artifact_file(directory, "*-fix.yaml"))
        payload["summary"] = extract_frontmatter_value(report_text, "summary")
        payload["user_story"] = extract_markdown_bullet_value(report_text, "用户影响")
        payload["symptom"] = extract_markdown_bullet_value(report_text, "现象")
        payload["expected"] = extract_markdown_bullet_value(report_text, "预期")
        payload["actual"] = extract_markdown_bullet_value(report_text, "实际")
        payload["in_scope"] = extract_markdown_section_bullets(analysis_text, "## 2. 范围")
    else:
        design_text = read_text_if_exists(find_first_artifact_file(directory, "*-design.md"))
        step_context = load_step_contract_context(find_first_artifact_file(directory, "*-checklist.yaml"))
        payload["summary"] = extract_frontmatter_value(design_text, "summary")
        payload["goal"] = extract_markdown_bullet_value(design_text, "用户目标")
        payload["user_story"] = extract_markdown_bullet_value(design_text, "用户故事")
        payload["in_scope"] = extract_markdown_section_bullets(design_text, "## 3. 范围内")

    payload.update(step_context)
    task_id = str(step_context.get("task_id", "")).strip()
    reusable_session_id = resolve_session_id_from_task(task_id, discovered[0]) if task_id else ""
    if reusable_session_id:
        payload["session_id"] = reusable_session_id

    if not payload.get("summary"):
        payload["summary"] = slug

    return {
        key: value
        for key, value in payload.items()
        if has_planning_value(value) and not (key == "kind" and value == "auto")
    }


def has_planning_value(value: Any) -> bool:
    if isinstance(value, list):
        return any(str(item).strip() for item in value)
    return bool(str(value).strip()) if isinstance(value, str) else bool(value)


def build_planning_snapshot(flow: str, args: argparse.Namespace, target_paths: list[str], resolved_kind: str) -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "kind": resolved_kind,
        "target_paths": target_paths,
        "context": cleaned_items(args.context),
    }

    if flow == "feature":
        snapshot.update(
            {
                "goal": infer_feature_goal(args),
                "user_story": infer_feature_user_story(args),
                "in_scope": infer_in_scope(args, flow, target_paths),
                "acceptance": infer_acceptance(args, flow),
            }
        )
    else:
        snapshot.update(
            {
                "symptom": infer_issue_symptom(args),
                "expected": infer_issue_expected(args),
                "actual": infer_issue_actual(args),
                "in_scope": infer_in_scope(args, flow, target_paths),
                "acceptance": infer_acceptance(args, flow),
            }
        )
    return snapshot


def build_captured_fields(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in snapshot.items()
        if has_planning_value(value) and not (key == "kind" and value == "auto")
    }


def build_clarification_mode(flow: str, missing_fields: list[str], resolved_kind: str) -> str:
    missing = set(missing_fields)
    if not missing:
        return ""
    if missing == {"target_paths"}:
        return "path-discovery"
    if "routing_coverage" in missing or resolved_kind == "auto":
        return f"{flow}-routing-clarification"
    return f"{flow}-beginner"


def build_clarification_prompts(flow: str, missing_fields: list[str]) -> list[dict[str, str]]:
    prompts: list[dict[str, str]] = []
    mapping = {
        "target_paths": {
            "field": "target_paths",
            "question": "这次改动具体落在哪些文件或目录？",
            "example": "例如：src/components/LoginForm.tsx 或 backend/src/sync.py",
        },
        "user_story": {
            "field": "user_story",
            "question": "这个需求从用户视角想解决什么问题？",
            "example": "例如：作为用户，我想快速登录，以便进入系统。",
        },
        "goal": {
            "field": "goal",
            "question": "这次需求的目标是什么？",
            "example": "例如：提供一个独立登录入口页面。",
        },
        "in_scope": {
            "field": "in_scope",
            "question": "这次明确要做的范围是什么？",
            "example": "例如：只新增登录表单，不改后端接口。",
        },
        "acceptance": {
            "field": "acceptance",
            "question": "怎么才算完成？",
            "example": "例如：页面展示邮箱和密码输入框，并可提交。",
        },
        "symptom": {
            "field": "symptom",
            "question": "这个问题的现象是什么？",
            "example": "例如：批量同步时报错，中途停止。",
        },
        "expected": {
            "field": "expected",
            "question": "你预期正确行为应该是什么？",
            "example": "例如：坏记录被跳过，其余记录继续处理。",
        },
        "actual": {
            "field": "actual",
            "question": "现在实际发生了什么？",
            "example": "例如：遇到一条坏记录后整批停止。",
        },
        "routing_coverage": {
            "field": "routing_coverage",
            "question": "这些路径应该归前端、后端，还是需要先拆分？",
            "example": "例如：src/components/** 归前端，backend/** 归后端。",
        },
    }

    preferred_order = (
        ["target_paths", "goal", "user_story", "in_scope", "acceptance"]
        if flow == "feature"
        else ["target_paths", "symptom", "expected", "actual", "in_scope", "acceptance"]
    )
    ordered_fields = preferred_order + [field for field in missing_fields if field not in preferred_order]

    seen: set[str] = set()
    for field in ordered_fields:
        if field not in missing_fields or field in seen:
            continue
        seen.add(field)
        prompt = mapping.get(field)
        if prompt:
            prompts.append(prompt)
    return prompts


def build_suggested_reply_payload(flow: str, snapshot: dict[str, Any], missing_fields: list[str]) -> dict[str, Any]:
    field_order = (
        ["target_paths", "goal", "user_story", "in_scope", "acceptance"]
        if flow == "feature"
        else ["target_paths", "symptom", "expected", "actual", "in_scope", "acceptance"]
    )
    list_fields = {"target_paths", "in_scope", "acceptance"}
    payload: dict[str, Any] = {"flow": flow}

    kind = str(snapshot.get("kind", "")).strip()
    if kind and kind != "auto":
        payload["kind"] = kind

    missing = set(missing_fields)
    for field in field_order:
        value = snapshot.get(field)
        if field in missing:
            payload[field] = [] if field in list_fields else ""
        elif has_planning_value(value):
            payload[field] = value
    return payload


def build_suggested_reply_template(flow: str, prompts: list[dict[str, str]]) -> str:
    if not prompts:
        return ""

    lines: list[str] = []
    if flow == "feature":
        lines.append("请补充下面这些信息后我再继续推进：")
    else:
        lines.append("请补充下面这些问题信息后我再继续修复：")

    for prompt in prompts:
        question = str(prompt.get("question", "")).strip()
        example = str(prompt.get("example", "")).strip()
        if not question:
            continue
        lines.append(f"- {question}")
        if example:
            lines.append(f"  参考：{example}")
    return "\n".join(lines)


def resolve_effective_auto_dispatch(
    args: argparse.Namespace,
    recommended_command: str,
    explain_only: bool = False,
) -> tuple[bool, str]:
    if explain_only:
        return False, "explain-mode"
    if args.auto_dispatch:
        return True, "explicit-flag"

    request = args.request.strip()
    if not request:
        return False, ""

    if matches_command(recommended_command, "cgc-build", "cgc-fix") and (
        request_implies_execute(request) or request_implies_continue(request)
    ):
        return True, "request-implies-execution"

    if matches_command(recommended_command, "cgc-review") and request_implies_review(request):
        inferred_decision = infer_review_decision_from_request(request)
        if inferred_decision and not args.decision:
            args.decision = inferred_decision
        if args.decision:
            return True, "request-implies-review"
        return False, "review-decision-missing"

    return False, ""


def build_route_status_summary(route: dict[str, Any]) -> dict[str, Any]:
    review = route.get("review", {}) if isinstance(route.get("review"), dict) else {}
    current_step = route.get("current_step", {}) if isinstance(route.get("current_step"), dict) else {}
    recommended_command = str(route.get("recommended_command", "")).strip()
    audit_path = str(route.get("audit_path", "")).strip()
    task_id = str(current_step.get("task_id", "")).strip()
    artifact_class = str(route.get("artifact_class", "")).strip() or "product"
    reusable_session_id = resolve_session_id_from_task(task_id, artifact_class) if task_id else ""

    workflow_state = "closed"
    if matches_command(recommended_command, "cgc-plan"):
        workflow_state = "needs-planning"
    elif matches_command(recommended_command, "cgc-build"):
        workflow_state = "awaiting-build"
    elif matches_command(recommended_command, "cgc-fix"):
        workflow_state = "awaiting-fix"
    elif matches_command(recommended_command, "cgc-review"):
        workflow_state = "awaiting-review"
    elif current_step:
        workflow_state = "step-selected"

    flow_step_labels = {
        "cgc-build": "功能开发步骤",
        "cgc-fix": "问题修复步骤",
        "cgc-test": "测试步骤",
    }

    human_status_summary = "当前工作流已关闭。"
    operator_action_summary = "如需继续，先新增后续步骤，或回到规划阶段。"
    if matches_command(recommended_command, "cgc-plan"):
        human_status_summary = "当前工作流还需要回到规划阶段补齐可执行信息。"
        operator_action_summary = "进入规划阶段，补齐范围、归属或可执行步骤。"
    elif matches_command(recommended_command, "cgc-build"):
        human_status_summary = "当前工作流正在等待前端或功能实现执行。"
        operator_action_summary = f"执行当前{flow_step_labels['cgc-build']}。"
    elif matches_command(recommended_command, "cgc-fix"):
        human_status_summary = "当前工作流正在等待后端或问题修复执行。"
        operator_action_summary = f"执行当前{flow_step_labels['cgc-fix']}。"
    elif matches_command(recommended_command, "cgc-test"):
        human_status_summary = "当前工作流正在等待测试步骤执行。"
        operator_action_summary = f"执行当前{flow_step_labels['cgc-test']}。"
    elif matches_command(recommended_command, "cgc-review"):
        human_status_summary = "当前工作流已有执行证据，正在等待审核决策。"
        operator_action_summary = "基于最新审计产物执行审核，并写回“通过”或“需修改”。"
    elif current_step:
        human_status_summary = "当前工作流已选中步骤，但还没有明确的后续命令。"
        operator_action_summary = "检查 route 原因，并确认是否需要回到规划阶段。"

    review_fallback_stage = str(review.get("fallback_stage", "")).strip()
    review_action_kind = str(review.get("action_kind", "")).strip()
    review_policy_reason = str(review.get("policy_reason", "")).strip()
    if recommended_command == "" and review_fallback_stage == "closed":
        human_status_summary = "当前工作流已关闭，最近一次审核已确认该步骤可以结束。"
        operator_action_summary = "如需继续，新增后续步骤；否则当前结果已可视为通过。"

    return {
        "workflow_state": workflow_state,
        "recommended_command": recommended_command,
        "current_step_number": int(current_step.get("step_number", 0) or 0),
        "current_task_id": str(current_step.get("task_id", "")),
        "current_kind": str(current_step.get("kind", "")),
        "current_target_paths": current_step.get("target_paths", []),
        "review_decision": str(review.get("decision", "")),
        "review_step_number": int(review.get("step_number", 0) or 0),
        "review_fallback_stage": review_fallback_stage,
        "review_policy_reason": review_policy_reason,
        "review_action_kind": review_action_kind,
        "audit_path": audit_path,
        "reusable_session_id": reusable_session_id,
        "human_status_summary": human_status_summary,
        "operator_action_summary": operator_action_summary,
        "is_closed": recommended_command == "",
        "needs_review_decision": matches_command(recommended_command, "cgc-review"),
        "needs_execution": matches_command(recommended_command, "cgc-build", "cgc-fix", "cgc-test"),
    }


def build_review_policy_status(dispatch_result: dict[str, Any]) -> dict[str, str]:
    fallback_stage = str(dispatch_result.get("fallback_stage", "")).strip()
    action_kind = str(dispatch_result.get("recommended_action_kind", "")).strip()
    policy_reason = str(dispatch_result.get("policy_reason", "")).strip()
    action_kind_labels = {
        "execute-for-real": "执行一次真实运行",
    }

    human_status_summary = ""
    operator_action_summary = ""

    if fallback_stage == "closed":
        human_status_summary = "当前审核已完成，并确认该步骤可以关闭。"
        operator_action_summary = "结束当前步骤，或继续处理新的后续工作。"
    elif fallback_stage == "planning":
        human_status_summary = "当前审核已把工作退回规划阶段。"
        operator_action_summary = "回到 cgc-plan，修正范围、归属或拆分策略。"
    elif fallback_stage == "execution":
        human_status_summary = "当前审核认为还需要重新执行或补做实现。"
        if action_kind == "execute-for-real":
            operator_action_summary = "执行一次非 dry-run 的真实执行。"
        else:
            operator_action_summary = "修正实现后重新执行当前步骤。"
    elif fallback_stage == "review":
        human_status_summary = "当前审核结果仍需进一步确认。"
        operator_action_summary = "重新检查审核输入与决策依据。"

    return {
        "fallback_stage": fallback_stage,
        "recommended_action_kind": action_kind,
        "policy_reason": policy_reason,
        "human_status_summary": human_status_summary,
        "operator_action_summary": operator_action_summary,
    }


def infer_dispatch_recovery(command: str, failure_type: str, state: str, next_step: str) -> dict[str, str]:
    normalized_failure = failure_type.strip()
    normalized_state = state.strip()
    normalized_next = next_step.strip()
    public_command = to_public_command(command)

    if normalized_failure == "workflow-state":
        recovery_command = public_command or to_public_command("cgc-build")
        retry_kind = "rerun-without-dry-run" if normalized_state == "executed-dry-run" else "workflow-repair"
        retry_hint = normalized_next or "先修复当前工作流就绪状态，再重新执行同一个 step。"
        return {
            "recovery_command": recovery_command,
            "recovery_kind": retry_kind,
            "retry_hint": retry_hint,
        }

    if normalized_failure in {"scope-error", "design-gap"}:
        retry_hint = normalized_next or "先回到规划阶段，收窄范围，并重新生成可执行 step。"
        return {
            "recovery_command": to_public_command("cgc-plan"),
            "recovery_kind": "returned-to-planning",
            "retry_hint": retry_hint,
        }

    if normalized_failure == "environment-or-tooling":
        retry_hint = normalized_next or "先修复本地环境、缺失文件或超时条件，再重试当前 step。"
        return {
            "recovery_command": "",
            "recovery_kind": "repair-environment",
            "retry_hint": retry_hint,
        }

    if normalized_failure == "executor-failure":
        retry_hint = normalized_next or "先检查执行器输出和审计产物，修复执行器侧失败后再重试。"
        return {
            "recovery_command": public_command,
            "recovery_kind": "inspect-executor",
            "retry_hint": retry_hint,
        }

    return {
        "recovery_command": public_command,
        "recovery_kind": "",
        "retry_hint": normalized_next,
    }


def build_dispatch_failure_user_summary(dispatch_result: dict[str, Any], command: str) -> tuple[str, str]:
    failure_type = str(dispatch_result.get("failure_type", "")).strip()
    dispatch_state = str(dispatch_result.get("state", "")).strip()
    recovery = infer_dispatch_recovery(command, failure_type, dispatch_state, str(dispatch_result.get("next", "")).strip())
    recovery_command = str(recovery.get("recovery_command", "")).strip()
    split_suggestion = dispatch_result.get("split_suggestion", {}) if isinstance(dispatch_result.get("split_suggestion"), dict) else {}

    if failure_type == "workflow-state":
        if dispatch_state == "executed-dry-run":
            return "本次只完成了预演执行，尚未真正完成代码改动。", "去掉 dry-run 后重新执行当前步骤。"
        return "当前步骤还不满足执行条件，执行尚未完成。", f"先修复工作流状态，再通过 {recovery_command or '当前执行命令'} 重试。"

    if failure_type == "environment-or-tooling":
        return "当前卡在本地环境或工具前置条件，执行尚未完成。", "先修复缺失目录、依赖、权限或超时条件，再重试当前步骤。"

    if failure_type == "executor-failure":
        return "当前卡在执行器返回异常，需要检查执行日志与审计产物。", f"先检查执行器输出，修复后再通过 {recovery_command or '当前执行命令'} 重试。"

    if failure_type in {"scope-error", "design-gap"}:
        if failure_type == "scope-error" and split_suggestion:
            suggested_steps = split_suggestion.get("suggested_split_steps", [])
            if isinstance(suggested_steps, list):
                parts: list[str] = []
                for item in suggested_steps:
                    if not isinstance(item, dict):
                        continue
                    kind = str(item.get("kind", "")).strip()
                    executor = str(item.get("executor", "")).strip()
                    paths = [str(path).strip() for path in item.get("target_paths", []) if str(path).strip()]
                    if not paths:
                        continue
                    parts.append(f"{kind}->{executor}: {', '.join(paths)}")
                if parts:
                    return (
                        "当前步骤混合了前后端或 shared 范围，执行已返回规划阶段。",
                        "建议按以下方式拆分后回到 cgc-plan：" + "；".join(parts),
                    )
        return "当前步骤的规划、范围或目标路径还不够清晰，执行已返回规划阶段。", "先回到 cgc-plan 补齐规划、修正目标路径或重新拆分步骤，再继续执行。"

    fallback_summary = str(dispatch_result.get("summary", "")).strip()
    if fallback_summary:
        return "自动调度未完成，需要先处理当前阻塞。", fallback_summary
    return "自动调度未完成，需要先处理当前阻塞。", "先检查当前步骤状态和执行日志，再决定是否重试。"


def build_dispatch_recovery_user_hint(dispatch_result: dict[str, Any], command: str) -> str:
    _, next_step = build_dispatch_failure_user_summary(dispatch_result, command)
    return next_step


def build_command_user_next(command: str) -> str:
    if matches_command(command, "cgc-build"):
        return "执行当前功能开发步骤。"
    if matches_command(command, "cgc-fix"):
        return "执行当前问题修复步骤。"
    if matches_command(command, "cgc-plan"):
        return "回到规划阶段，补齐可执行信息。"
    if matches_command(command, "cgc-review"):
        return "基于最新审计产物完成审核，并写回“通过”或“需修改”。"
    return ""


def compose_user_reply(summary: str, next_text: str, prefix: str = "下一步：") -> str:
    normalized_summary = summary.strip()
    normalized_next = next_text.strip()
    if normalized_summary and normalized_next:
        if normalized_next in normalized_summary:
            return normalized_summary
        return f"{normalized_summary}\n\n{prefix}{normalized_next}"
    return normalized_summary or normalized_next


def apply_dispatch_failure_context(result: dict[str, Any], fallback_command: str) -> None:
    dispatch_result = result.get("dispatch_result", {}) if isinstance(result.get("dispatch_result"), dict) else {}
    if not dispatch_result or dispatch_result.get("success"):
        return

    failure_command = str(dispatch_result.get("recommended_command", "")).strip() or fallback_command
    recovery = infer_dispatch_recovery(
        failure_command,
        str(dispatch_result.get("failure_type", "")).strip(),
        str(dispatch_result.get("state", "")).strip(),
        str(dispatch_result.get("next", "")).strip(),
    )
    retry_hint = str(recovery.get("retry_hint", "")).strip()
    user_summary, user_next = build_dispatch_failure_user_summary(dispatch_result, failure_command)

    result["recommended_command"] = failure_command
    result["next"] = user_next or retry_hint or user_summary


def describe_missing_fields(missing_fields: list[str]) -> str:
    labels = {
        "target_paths": "目标文件或目录",
        "goal": "需求目标",
        "user_story": "用户故事",
        "in_scope": "本次范围",
        "acceptance": "验收标准",
        "symptom": "问题现象",
        "expected": "预期行为",
        "actual": "实际行为",
        "routing_coverage": "前后端归属",
        "planning_blockers": "规划阻塞项",
        "executable_step": "可执行步骤定义",
    }
    described = [labels.get(str(item), str(item)) for item in missing_fields]
    return "、".join(item for item in described if item)


def build_user_facing_next(result: dict[str, Any]) -> str:
    if str(result.get("entry_mode", "")).strip() == "governance":
        return str(result.get("next", "")).strip()

    entry_mode = str(result.get("entry_mode", "")).strip()
    if entry_mode == "new":
        planning_status = str(result.get("planning_status", "")).strip()
        recommended_command = str(result.get("recommended_command", "")).strip()
        if planning_status == "needs-clarification":
            return "请先补充缺失信息，我再继续完成规划和路由。"
        command_next = build_command_user_next(recommended_command)
        if command_next:
            return command_next
        return str(result.get("next", "")).strip()

    route_status = result.get("route_status", {}) if isinstance(result.get("route_status"), dict) else {}
    recommended_command = str(result.get("recommended_command", "")).strip()
    workflow_state = str(route_status.get("workflow_state", "")).strip()
    if workflow_state == "needs-new-workflow":
        return "先直接描述一个新需求，或显式提供已有工作流的 slug。"
    if workflow_state == "needs-review-target":
        return "先定位一个待审核工作流，或先完成执行步骤后再回来审核。"
    if bool(route_status.get("is_closed")):
        return str(route_status.get("operator_action_summary", "")).strip() or "如需继续，先新增后续步骤，或回到规划阶段。"
    if bool(route_status.get("needs_review_decision")):
        return "基于最新审计产物执行审核，并写回“通过”或“需修改”。"
    command_next = build_command_user_next(recommended_command)
    if command_next:
        return command_next
    return str(result.get("next", "")).strip()


def build_new_mode_human_summary(result: dict[str, Any]) -> str:
    flow = str(result.get("flow", "")).strip() or "workflow"
    status = str(result.get("planning_status", "")).strip()
    recommended_command = str(result.get("recommended_command", "")).strip()
    dispatched = bool(result.get("dispatched"))
    dispatch_result = result.get("dispatch_result", {}) if isinstance(result.get("dispatch_result"), dict) else {}
    missing_fields = result.get("planning_missing_fields", [])
    resolved_kind = str(result.get("resolved_kind", "")).strip() or "auto"
    flow_labels = {
        "feature": "功能开发",
        "issue": "问题修复",
        "workflow": "工作流",
    }
    kind_labels = {
        "frontend": "前端",
        "backend": "后端",
        "shared": "共享范围（需先拆分）",
        "auto": "待路由",
    }
    flow_label = flow_labels.get(flow, flow)
    kind_label = kind_labels.get(resolved_kind, resolved_kind)

    if status == "needs-clarification":
        if missing_fields:
            return f"已识别为{flow_label}请求，但信息还不完整，当前缺少：{describe_missing_fields(missing_fields)}。"
        return f"已识别为{flow_label}请求，但还需要进一步澄清。"
    if dispatched:
        if not dispatch_result.get("success"):
            failure_summary, next_step = build_dispatch_failure_user_summary(dispatch_result, recommended_command)
            if failure_summary and next_step:
                return f"已完成{flow_label}规划，并尝试自动调度，但当前未完成：{failure_summary} 下一步建议：{next_step}"
            if next_step:
                return f"已完成{flow_label}规划，并尝试自动调度，但当前未完成。下一步建议：{next_step}"
            return f"已完成{flow_label}规划，但自动调度尚未完成：{failure_summary}"
        command_next = build_command_user_next(recommended_command)
        if command_next and recommended_command:
            return f"已完成{flow_label}规划，并已自动调度到 {recommended_command}，当前应继续{command_next}"
        return f"已完成{flow_label}规划，并已自动调度到 {recommended_command or '后续执行阶段'}。"
    if recommended_command:
        command_next = build_command_user_next(recommended_command)
        if command_next:
            return f"已完成{flow_label}规划，当前归属为{kind_label}，下一步建议进入 {recommended_command}，继续{command_next}"
        return f"已完成{flow_label}规划，当前归属为{kind_label}，下一步建议进入 {recommended_command}。"
    return f"已完成{flow_label}规划，当前没有进一步命令需要执行。"


def build_existing_mode_human_summary(result: dict[str, Any]) -> str:
    route_status = result.get("route_status", {}) if isinstance(result.get("route_status"), dict) else {}
    summary = str(route_status.get("human_status_summary", "")).strip()
    action = str(route_status.get("operator_action_summary", "")).strip()
    recommended_command = str(result.get("recommended_command", "")).strip()
    dispatched = bool(result.get("dispatched"))
    dispatch_result = result.get("dispatch_result", {}) if isinstance(result.get("dispatch_result"), dict) else {}
    decision_labels = {
        "accepted": "通过",
        "changes-requested": "需修改",
    }
    fallback_stage_labels = {
        "closed": "关闭",
        "planning": "规划阶段",
        "execution": "执行阶段",
        "review": "审核阶段",
    }
    action_kind_labels = {
        "close-step": "关闭当前步骤",
        "repair-plan": "回到规划修正",
        "execute-for-real": "执行一次真实运行",
        "refine-and-rerun": "修正实现后重新执行",
        "re-evaluate": "重新评估当前步骤",
    }

    if dispatched and dispatch_result.get("success"):
        final_decision = str(dispatch_result.get("final_decision", "")).strip()
        fallback_stage = str(dispatch_result.get("fallback_stage", "")).strip()
        action_kind = str(dispatch_result.get("recommended_action_kind", "")).strip()
        if final_decision:
            policy_suffix = ""
            if fallback_stage:
                policy_suffix = f" 当前回退阶段为{fallback_stage_labels.get(fallback_stage, fallback_stage)}。"
            if action_kind:
                policy_suffix += f" 建议动作类型为{action_kind_labels.get(action_kind, action_kind)}。"
            return f"{summary} 已自动完成审核，最终决策为{decision_labels.get(final_decision, final_decision)}。{policy_suffix}".strip()
        if recommended_command:
            command_next = build_command_user_next(recommended_command)
            if command_next:
                return f"{summary} 已自动调度到 {recommended_command}，当前应继续{command_next}"
            return f"{summary} 已自动调度到 {recommended_command}。"
        return f"{summary} 已自动完成当前建议动作。"
    if dispatched and not dispatch_result.get("success"):
        failure_summary, next_step = build_dispatch_failure_user_summary(dispatch_result, recommended_command)
        dispatch_state = str(dispatch_result.get("state", "")).strip()
        dispatch_failure_type = str(dispatch_result.get("failure_type", "")).strip()
        if dispatch_failure_type in {"scope-error", "design-gap"} or dispatch_state == "returned-to-planning":
            if failure_summary and next_step:
                return f"{failure_summary} 下一步建议：{next_step}"
            return failure_summary or next_step or "当前步骤已返回规划阶段。"
        if dispatch_failure_type == "environment-or-tooling":
            if failure_summary and next_step:
                return f"{failure_summary} 下一步建议：{next_step}"
            return failure_summary or next_step or "当前执行被环境或工具前置条件阻塞。"
        if dispatch_failure_type == "executor-failure":
            if failure_summary and next_step:
                return f"{failure_summary} 下一步建议：{next_step}"
            return failure_summary or next_step or "当前执行器返回异常，需要先处理阻塞。"
        if summary and failure_summary and next_step:
            return f"{summary} 自动调度未完成：{failure_summary} 下一步建议：{next_step}"
        if summary and next_step:
            return f"{summary} 自动调度未完成。下一步建议：{next_step}"
        if summary and failure_summary:
            return f"{summary} 自动调度未完成：{failure_summary}"
        if failure_summary and next_step:
            return f"自动调度未完成：{failure_summary} 下一步建议：{next_step}"
        if next_step:
            return f"自动调度未完成。下一步建议：{next_step}"
        if failure_summary:
            return f"自动调度未完成：{failure_summary}"
    if summary and action:
        if action in summary:
            return summary
        return f"{summary} 下一步建议：{action}"
    if summary:
        return summary
    if action:
        return action
    return "当前已有工作流状态暂时无法判断，请检查输入的 slug 或最近工作流记录。"


def build_missing_existing_workflow_result(
    *,
    request: str,
    explain_only: bool,
    include_fixtures: bool,
    human_summary: str = "当前没有可继续的 CodeCGC 工作流。",
    next_text: str = "先直接描述一个新需求，或显式提供已有 workflow 的 slug。",
    action_reason: str = "当前仓库里还没有可用于 continue / explain 的最近工作流。",
    workflow_state: str = "needs-new-workflow",
    reply_kind: str = "start-new-workflow",
    action_type: str = "wait-new-request",
    dispatch_blocker: str = "missing-existing-workflow",
    recovery_hint: str = "直接描述一个新需求，或显式提供已有 workflow slug。",
    recommended_command: str = "",
    command_args: list[str] | None = None,
) -> dict[str, Any]:
    command_args = [str(item).strip() for item in (command_args or []) if str(item).strip()]
    result = {
        "success": True,
        "entry_mode": "explain" if explain_only else "continue",
        "flow": "",
        "slug": "",
        "latest": True,
        "request": request,
        "auto_dispatch": False,
        "auto_dispatch_reason": "missing-existing-workflow",
        "recommended_command": recommended_command,
        "next": next_text,
        "dispatched": False,
        "dispatch_result": None,
        "route": {},
        "route_status": {
            "workflow_state": workflow_state,
            "recommended_command": recommended_command,
            "current_step_number": 0,
            "current_task_id": "",
            "current_kind": "",
            "current_target_paths": [],
            "review_decision": "",
            "review_step_number": 0,
            "review_fallback_stage": "",
            "review_policy_reason": "",
            "review_action_kind": "",
            "audit_path": "",
            "human_status_summary": human_summary,
            "operator_action_summary": next_text,
            "is_closed": False,
            "needs_review_decision": False,
            "needs_execution": False,
            "include_fixtures": include_fixtures,
        },
        "human_summary": human_summary,
        "assistant_reply": compose_user_reply(human_summary, next_text, prefix=""),
    }
    result["operator_brief"] = {
        "entry_mode": result["entry_mode"],
        "flow": "",
        "slug": "",
        "recommended_command": recommended_command,
        "next": next_text,
        "human_summary": human_summary,
        "assistant_reply": result["assistant_reply"],
        "user_message": result["assistant_reply"],
        "dispatched": False,
        "needs_user_reply": True,
        "needs_execution": False,
        "needs_review": False,
        "is_closed": False,
        "reply_kind": reply_kind,
        "workflow_state": workflow_state,
        "current_step_number": 0,
        "current_task_id": "",
        "current_kind": "",
        "current_target_paths": [],
        "review_decision": "",
        "audit_path": "",
        "machine_next_action": {
            "type": action_type,
            "command": recommended_command,
            "reason": action_reason,
            "can_auto_dispatch": False,
            "auto_dispatch_reason": dispatch_blocker,
            "command_args": command_args,
            "requires_user_reply": True,
            "requires_decision": False,
            "requires_audit_file": False,
            "requires_slug": False,
            "requires_step_number": False,
            "missing_fields": [],
            "workflow_state": workflow_state,
            "current_step_number": 0,
            "current_task_id": "",
            "current_kind": "",
            "audit_path": "",
            "review_decision": "",
            "review_fallback_stage": "",
            "review_policy_reason": "",
            "review_action_kind": "",
            "dispatch_attempted": False,
            "dispatch_success": None,
            "dispatch_state": "",
            "dispatch_failure_type": "",
            "dispatch_error": "",
            "dispatch_next": "",
            "dispatch_summary": "",
            "recovery_command": "",
            "recovery_kind": "",
            "retry_hint": "",
            "followup_payload": {},
            "dispatch_blocker": dispatch_blocker,
            "user_action": {
                "summary": human_summary,
                "next_step": next_text,
                "recovery_hint": recovery_hint,
                "followup_payload": {},
            },
            "diagnostics": {
                "dispatch_attempted": False,
                "dispatch_success": None,
                "dispatch_state": "",
                "dispatch_failure_type": "",
                "dispatch_blocker": dispatch_blocker,
                "dispatch_error": "",
                "dispatch_next": "",
                "dispatch_summary": "",
                "recovery_command": "",
                "recovery_kind": "",
                "retry_hint": recovery_hint,
                "audit_path": "",
                "review_fallback_stage": "",
                "review_policy_reason": "",
                "review_action_kind": "",
            },
            "execution": {
                "command": recommended_command,
                "command_args": command_args,
                "can_auto_dispatch": False,
                "auto_dispatch_reason": dispatch_blocker,
                "requires_user_reply": True,
                "requires_decision": False,
                "requires_audit_file": False,
                "requires_slug": False,
                "requires_step_number": False,
                "missing_fields": [],
                "workflow_state": workflow_state,
                "current_step_number": 0,
                "current_task_id": "",
                "current_kind": "",
                "review_decision": "",
                "review_fallback_stage": "",
                "review_policy_reason": "",
                "review_action_kind": "",
            },
            "preferred_fields": {
                "user_message": "user_action.summary",
                "next_step": "user_action.next_step",
                "recovery_hint": "user_action.recovery_hint",
            },
            "compatibility_fields": {
                "reason": "请优先改用 user_action.summary。",
                "dispatch_blocker": "请优先改用 diagnostics.dispatch_blocker。",
            },
        },
        "reply_payload": {},
        "reply_prompts": [],
    }
    return attach_entry_summary(result)
    return "已读取当前工作流状态。"


def build_assistant_reply(result: dict[str, Any]) -> str:
    entry_mode = str(result.get("entry_mode", "")).strip()
    if entry_mode == "governance":
        summary = str(result.get("human_summary", "")).strip()
        next_text = str(result.get("next", "")).strip()
        return compose_user_reply(summary, next_text, prefix="")

    dispatched = bool(result.get("dispatched"))
    dispatch_result = result.get("dispatch_result", {}) if isinstance(result.get("dispatch_result"), dict) else {}
    user_next = build_user_facing_next(result)
    if entry_mode == "new":
        summary = build_new_mode_human_summary(result)
        suggested = str(result.get("suggested_reply_template", "")).strip()
        if dispatched and not dispatch_result.get("success"):
            return summary
        if suggested:
            return f"{summary}\n\n{suggested}"
        return compose_user_reply(summary, user_next)

    summary = build_existing_mode_human_summary(result)
    if dispatched and not dispatch_result.get("success"):
        return summary
    route_status = result.get("route_status", {}) if isinstance(result.get("route_status"), dict) else {}
    if str(route_status.get("operator_action_summary", "")).strip():
        return compose_user_reply(summary, user_next)
    return compose_user_reply(summary, user_next)


def build_beginner_action_pack(result: dict[str, Any]) -> list[str]:
    operator_brief = result.get("operator_brief", {}) if isinstance(result.get("operator_brief"), dict) else {}
    machine_next_action = operator_brief.get("machine_next_action", {}) if isinstance(operator_brief.get("machine_next_action"), dict) else {}
    execution = machine_next_action.get("execution", {}) if isinstance(machine_next_action.get("execution"), dict) else {}
    user_action = machine_next_action.get("user_action", {}) if isinstance(machine_next_action.get("user_action"), dict) else {}
    command = str(execution.get("command", "") or machine_next_action.get("command", "")).strip()
    command_args = execution.get("command_args", []) if isinstance(execution.get("command_args"), list) else []
    prompts = operator_brief.get("reply_prompts", []) if isinstance(operator_brief.get("reply_prompts"), list) else []
    next_step = str(user_action.get("next_step", "")).strip()

    actions: list[str] = []
    if command:
        rendered = " ".join([command, *[str(item).strip() for item in command_args if str(item).strip()]]).strip()
        if rendered:
            actions.append(f"直接执行：{rendered}")
    if next_step:
        actions.append(f"你现在要做：{next_step}")
    for item in prompts[:3]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        question = str(item.get("question", "")).strip()
        if label and question:
            actions.append(f"先补充 {label}：{question}")
    return actions[:3]


def attach_entry_summary(result: dict[str, Any]) -> dict[str, Any]:
    operator_brief = result.get("operator_brief", {}) if isinstance(result.get("operator_brief"), dict) else {}
    route_status = result.get("route_status", {}) if isinstance(result.get("route_status"), dict) else {}
    machine_next_action = operator_brief.get("machine_next_action", {}) if isinstance(operator_brief.get("machine_next_action"), dict) else {}
    execution = machine_next_action.get("execution", {}) if isinstance(machine_next_action.get("execution"), dict) else {}
    summary = {
        "human_summary": str(result.get("human_summary", "")).strip(),
        "assistant_reply": str(result.get("assistant_reply", "")).strip(),
        "recommended_command": str(result.get("recommended_command", "")).strip(),
        "next": str(result.get("next", "")).strip(),
        "beginner_actions": build_beginner_action_pack(result),
        "workflow_state": str(
            execution.get("workflow_state", "")
            or machine_next_action.get("workflow_state", "")
            or route_status.get("workflow_state", "")
        ).strip(),
        "reply_kind": str(operator_brief.get("reply_kind", "")).strip(),
        "action_type": str(machine_next_action.get("type", "")).strip(),
        "governance_type": str(operator_brief.get("governance_type", "")).strip(),
        "is_closed": bool(operator_brief.get("is_closed")),
    }
    result["summary"] = summary
    return result


def extract_governance_artifact_info(governance_type: str, dispatch_result: dict[str, Any]) -> dict[str, str]:
    key_map = {
        "decide": ("decision", "path"),
        "learn": ("learning", "path"),
        "arch": ("architecture", "path"),
        "req": ("requirement", "path"),
        "roadmap": ("roadmap", "directory"),
        "refactor": ("refactor", "path"),
        "guide": ("guide", "path"),
        "libdoc": ("libdoc", "path"),
        "trick": ("trick", "path"),
        "explore": ("explore", "path"),
    }
    result_key, path_key = key_map.get(governance_type, ("", "path"))
    artifact = dispatch_result.get(result_key, {}) if result_key and isinstance(dispatch_result.get(result_key), dict) else {}
    return {
        "result_key": result_key,
        "artifact_path": str(artifact.get(path_key, "")).strip(),
        "summary": str(artifact.get("summary", "")).strip(),
        "created": str(artifact.get("created", "")).strip(),
    }


def build_governance_followup_bundle(
    governance_type: str,
    request: str,
    dispatch_result: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, str]], bool]:
    artifact = extract_governance_artifact_info(governance_type, dispatch_result)
    payload = {
        "governance_type": governance_type,
        "source_request": request.strip(),
        "artifact_path": artifact["artifact_path"],
        "artifact_summary": artifact["summary"] or request.strip(),
        "created": artifact["created"] or "unknown",
    }

    prompts: list[dict[str, str]] = []
    needs_user_reply = False

    if governance_type == "guide":
        needs_user_reply = True
        payload["suggested_request"] = "继续完善刚刚生成的 guide，补全目的、步骤和使用边界。"
        prompts = [
            {"label": "目的", "question": "这份 guide 最终要帮谁完成什么任务？"},
            {"label": "步骤", "question": "最少需要哪些可执行步骤，用户才能照着完成？"},
            {"label": "边界", "question": "有哪些前置条件、非目标或常见误区需要提前说明？"},
        ]
    elif governance_type == "libdoc":
        needs_user_reply = True
        payload["suggested_request"] = "继续完善刚刚生成的 libdoc，补全公开契约、示例和边界说明。"
        prompts = [
            {"label": "契约", "question": "这个公开表面有哪些稳定输入、输出或字段约束？"},
            {"label": "示例", "question": "最小示例应该如何调用或使用它？"},
            {"label": "边界", "question": "有哪些限制、异常场景或版本边界需要写清楚？"},
        ]
    elif governance_type == "trick":
        needs_user_reply = True
        payload["suggested_request"] = "继续完善刚刚记录的 trick，补全默认做法、适用范围和反例。"
        prompts = [
            {"label": "做法", "question": "这条技巧最推荐的默认做法是什么？"},
            {"label": "范围", "question": "它适用于哪些场景，不适用于哪些场景？"},
            {"label": "反例", "question": "有没有常见误用或应该避免的写法？"},
        ]
    elif governance_type == "explore":
        needs_user_reply = True
        payload["suggested_request"] = "继续细化刚刚登记的 explore 请求，明确问题、目标模块和预期输出。"
        prompts = [
            {"label": "问题", "question": "这次 explore 最终想回答的核心问题是什么？"},
            {"label": "模块", "question": "优先应该读哪些目录、模块或文件？"},
            {"label": "输出", "question": "希望最后产出结论、模块总览，还是 spike 结论？"},
        ]

    return payload, prompts, needs_user_reply


def build_operator_brief(result: dict[str, Any]) -> dict[str, Any]:
    entry_mode = str(result.get("entry_mode", "")).strip()
    flow = str(result.get("flow", "")).strip()
    slug = str(result.get("slug", "")).strip()
    recommended_command = str(result.get("recommended_command", "")).strip()
    next_text = str(result.get("next", "")).strip()
    human_summary = str(result.get("human_summary", "")).strip()
    assistant_reply = str(result.get("assistant_reply", "")).strip()
    dispatched = bool(result.get("dispatched"))
    auto_dispatch = bool(result.get("auto_dispatch"))
    auto_dispatch_reason = str(result.get("auto_dispatch_reason", "")).strip()
    dispatch_result = result.get("dispatch_result", {}) if isinstance(result.get("dispatch_result"), dict) else {}
    replan_payload = (
        result.get("replan_payload", {})
        if isinstance(result.get("replan_payload"), dict)
        else {}
    )
    if dispatched and isinstance(dispatch_result.get("replan_payload"), dict) and dispatch_result.get("replan_payload"):
        merged_replan_payload = dict(replan_payload)
        merged_replan_payload.update(dispatch_result.get("replan_payload", {}))
        replan_payload = merged_replan_payload

    def build_command_args(command: str, route_status: dict[str, Any] | None = None) -> list[str]:
        if not command:
            return []
        args: list[str] = []
        if matches_command(command, "cgc-plan"):
            if flow:
                args.extend(["--flow", flow])
            if slug:
                args.extend(["--slug", slug])
            summary = str(replan_payload.get("summary", "")).strip()
            if summary:
                args.extend(["--summary", summary])
            kind = str(replan_payload.get("kind", "")).strip()
            if kind:
                args.extend(["--kind", kind])
            for item in replan_payload.get("target_paths", []):
                if str(item).strip():
                    args.extend(["--target-path", str(item).strip()])
            if flow == "feature":
                for key, flag in (
                    ("goal", "--goal"),
                    ("user_story", "--user-story"),
                ):
                    value = str(replan_payload.get(key, "")).strip()
                    if value:
                        args.extend([flag, value])
            else:
                for key, flag in (
                    ("symptom", "--symptom"),
                    ("expected", "--expected"),
                    ("actual", "--actual"),
                    ("user_story", "--user-story"),
                ):
                    value = str(replan_payload.get(key, "")).strip()
                    if value:
                        args.extend([flag, value])
            for item in replan_payload.get("in_scope", []):
                if str(item).strip():
                    args.extend(["--in-scope", str(item).strip()])
            for item in replan_payload.get("acceptance", []):
                if str(item).strip():
                    args.extend(["--acceptance", str(item).strip()])
            return args
        if slug and matches_command(command, "cgc-build", "cgc-fix", "cgc-test"):
            args.extend(["--slug", slug])
        if matches_command(command, "cgc-build", "cgc-fix", "cgc-test"):
            current_step_number = int((route_status or {}).get("current_step_number", 0) or 0)
            if current_step_number:
                args.extend(["--step-number", str(current_step_number)])
            reusable_session_id = str((route_status or {}).get("reusable_session_id", "")).strip()
            if reusable_session_id:
                args.extend(["--session-id", reusable_session_id])
        if matches_command(command, "cgc-review"):
            audit_path = str((route_status or {}).get("audit_path", "")).strip()
            review_decision = str((route_status or {}).get("review_decision", "")).strip()
            if audit_path:
                args.extend(["--audit-file", audit_path])
            if review_decision in {"accepted", "changes-requested"}:
                args.extend(["--decision", review_decision])
        return args

    def build_machine_next_action(
        *,
        action_type: str,
        command: str,
        reason: str,
        route_status: dict[str, Any] | None = None,
        missing_fields: list[str] | None = None,
        reply_payload: dict[str, Any] | None = None,
        reply_prompts: list[dict[str, str]] | None = None,
        force_can_auto_dispatch: bool | None = None,
    ) -> dict[str, Any]:
        route_status = route_status or {}
        missing_fields = missing_fields or []
        reply_payload = reply_payload or {}
        reply_prompts = reply_prompts or []
        current_step_number = int(route_status.get("current_step_number", 0) or 0)
        audit_path = str(route_status.get("audit_path", "")).strip()
        review_decision = str(route_status.get("review_decision", "")).strip()
        review_fallback_stage = str(route_status.get("review_fallback_stage", "")).strip()
        review_policy_reason = str(route_status.get("review_policy_reason", "")).strip()
        review_action_kind = str(route_status.get("review_action_kind", "")).strip()
        dispatch_state = str(dispatch_result.get("state", "")).strip() if dispatched else ""
        dispatch_failure_type = str(dispatch_result.get("failure_type", "")).strip() if dispatched else ""
        dispatch_error = str(dispatch_result.get("error", "")).strip() if dispatched else ""
        dispatch_next = str(dispatch_result.get("next", "")).strip() if dispatched else ""
        dispatch_summary = str(dispatch_result.get("summary", "")).strip() if dispatched else ""
        dispatch_audit_path = str(dispatch_result.get("audit_path", "")).strip() if dispatched else ""
        dispatch_review_fallback_stage = str(dispatch_result.get("fallback_stage", "")).strip() if dispatched else ""
        dispatch_review_policy_reason = str(dispatch_result.get("policy_reason", "")).strip() if dispatched else ""
        dispatch_review_action_kind = str(dispatch_result.get("recommended_action_kind", "")).strip() if dispatched else ""
        dispatch_user_hint = build_dispatch_recovery_user_hint(dispatch_result, command) if dispatched else ""
        dispatch_recovery = infer_dispatch_recovery(command, dispatch_failure_type, dispatch_state, dispatch_next) if dispatched else {
            "recovery_command": "",
            "recovery_kind": "",
            "retry_hint": "",
        }
        followup_payload: dict[str, Any] = {}
        if reply_payload:
            followup_payload = {
                "payload": reply_payload,
                "prompts": reply_prompts,
            }
        if matches_command(command, "cgc-plan") and replan_payload:
            existing_payload = (
                followup_payload.get("payload", {})
                if isinstance(followup_payload.get("payload"), dict)
                else {}
            )
            merged_payload = dict(replan_payload)
            merged_payload.update(existing_payload)
            followup_payload = {
                "payload": merged_payload,
                "prompts": reply_prompts,
            }
        can_auto_dispatch = bool(auto_dispatch and command)
        if force_can_auto_dispatch is not None:
            can_auto_dispatch = force_can_auto_dispatch
        dispatch_blocker = ""
        if action_type == "wait-review-decision" and review_decision not in {"accepted", "changes-requested"}:
            dispatch_blocker = "review-decision-missing"
        elif dispatched and not dispatch_result.get("success"):
            dispatch_blocker = dispatch_failure_type or dispatch_error or dispatch_state or auto_dispatch_reason
        elif not can_auto_dispatch and auto_dispatch_reason:
            dispatch_blocker = auto_dispatch_reason
        command_args = build_command_args(command, route_status)
        user_action = {
            "summary": reason,
            "next_step": reason,
            "recovery_hint": dispatch_user_hint or str(dispatch_recovery.get("retry_hint", "")).strip(),
            "followup_payload": followup_payload,
        }
        diagnostics = {
            "dispatch_attempted": dispatched,
            "dispatch_success": bool(dispatch_result.get("success")) if dispatched else None,
            "dispatch_state": dispatch_state,
            "dispatch_failure_type": dispatch_failure_type,
            "dispatch_blocker": dispatch_blocker,
            "dispatch_error": dispatch_error,
            "dispatch_next": dispatch_next,
            "dispatch_summary": dispatch_summary,
            "recovery_command": str(dispatch_recovery.get("recovery_command", "")).strip(),
            "recovery_kind": str(dispatch_recovery.get("recovery_kind", "")).strip(),
            "retry_hint": dispatch_user_hint or str(dispatch_recovery.get("retry_hint", "")).strip(),
            "audit_path": dispatch_audit_path or audit_path,
            "review_fallback_stage": dispatch_review_fallback_stage or review_fallback_stage,
            "review_policy_reason": dispatch_review_policy_reason or review_policy_reason,
            "review_action_kind": dispatch_review_action_kind or review_action_kind,
        }
        execution = {
            "command": command,
            "command_args": command_args,
            "can_auto_dispatch": can_auto_dispatch,
            "auto_dispatch_reason": auto_dispatch_reason,
            "requires_user_reply": action_type == "wait-user-reply",
            "requires_decision": action_type in {"review", "wait-review-decision"} and review_decision not in {"accepted", "changes-requested"},
            "requires_audit_file": action_type == "review" and not audit_path,
            "requires_slug": not bool(slug) and action_type in {"dispatch", "review"},
            "requires_step_number": action_type == "dispatch" and matches_command(command, "cgc-build", "cgc-fix") and current_step_number <= 0,
            "missing_fields": missing_fields,
            "workflow_state": str(route_status.get("workflow_state", "")).strip(),
            "current_step_number": current_step_number,
            "current_task_id": str(route_status.get("current_task_id", "")).strip(),
            "current_kind": str(route_status.get("current_kind", "")).strip(),
            "review_decision": review_decision,
            "review_fallback_stage": dispatch_review_fallback_stage or review_fallback_stage,
            "review_policy_reason": dispatch_review_policy_reason or review_policy_reason,
            "review_action_kind": dispatch_review_action_kind or review_action_kind,
        }
        preferred_fields = {
            "user_message": "user_action.summary",
            "next_step": "user_action.next_step",
            "recovery_hint": "user_action.recovery_hint",
            "execution_command": "execution.command",
            "execution_args": "execution.command_args",
            "diagnostic_blocker": "diagnostics.dispatch_blocker",
            "diagnostic_error": "diagnostics.dispatch_error",
            "diagnostic_next": "diagnostics.dispatch_next",
        }
        compatibility_fields = {
            "reason": "请优先改用 user_action.summary。",
            "command": "请优先改用 execution.command。",
            "command_args": "请优先改用 execution.command_args。",
            "retry_hint": "请优先改用 user_action.recovery_hint 或 diagnostics.retry_hint。",
            "dispatch_blocker": "请优先改用 diagnostics.dispatch_blocker。",
            "dispatch_error": "请优先改用 diagnostics.dispatch_error。",
            "dispatch_next": "请优先改用 diagnostics.dispatch_next。",
        }
        return {
            "type": action_type,
            "command": command,
            "reason": reason,
            "can_auto_dispatch": can_auto_dispatch,
            "auto_dispatch_reason": auto_dispatch_reason,
            "command_args": command_args,
            "requires_user_reply": action_type == "wait-user-reply",
            "requires_decision": action_type in {"review", "wait-review-decision"} and review_decision not in {"accepted", "changes-requested"},
            "requires_audit_file": action_type == "review" and not audit_path,
            "requires_slug": not bool(slug) and action_type in {"dispatch", "review"},
            "requires_step_number": action_type == "dispatch" and matches_command(command, "cgc-build", "cgc-fix") and current_step_number <= 0,
            "missing_fields": missing_fields,
            "workflow_state": str(route_status.get("workflow_state", "")).strip(),
            "current_step_number": current_step_number,
            "current_task_id": str(route_status.get("current_task_id", "")).strip(),
            "current_kind": str(route_status.get("current_kind", "")).strip(),
            "audit_path": dispatch_audit_path or audit_path,
            "review_decision": review_decision,
            "review_fallback_stage": dispatch_review_fallback_stage or review_fallback_stage,
            "review_policy_reason": dispatch_review_policy_reason or review_policy_reason,
            "review_action_kind": dispatch_review_action_kind or review_action_kind,
            "dispatch_attempted": dispatched,
            "dispatch_success": bool(dispatch_result.get("success")) if dispatched else None,
            "dispatch_state": dispatch_state,
            "dispatch_failure_type": dispatch_failure_type,
            "dispatch_error": dispatch_error,
            "dispatch_next": dispatch_next,
            "dispatch_summary": dispatch_summary,
            "recovery_command": str(dispatch_recovery.get("recovery_command", "")).strip(),
            "recovery_kind": str(dispatch_recovery.get("recovery_kind", "")).strip(),
            "retry_hint": dispatch_user_hint or str(dispatch_recovery.get("retry_hint", "")).strip(),
            "followup_payload": followup_payload,
            "dispatch_blocker": dispatch_blocker,
            "user_action": user_action,
            "diagnostics": diagnostics,
            "execution": execution,
            "preferred_fields": preferred_fields,
            "compatibility_fields": compatibility_fields,
        }

    brief: dict[str, Any] = {
        "entry_mode": entry_mode,
        "flow": flow,
        "slug": slug,
        "recommended_command": recommended_command,
        "next": next_text,
        "human_summary": human_summary,
        "assistant_reply": assistant_reply,
        "user_message": assistant_reply,
        "dispatched": dispatched,
        "needs_user_reply": False,
        "needs_execution": False,
        "needs_review": False,
        "is_closed": False,
        "reply_kind": "status",
        "machine_next_action": build_machine_next_action(
            action_type="idle",
            command=recommended_command,
            reason=next_text,
        ),
        "reply_payload": {},
        "reply_prompts": [],
    }

    if entry_mode == "governance":
        governance_skill = str(result.get("recommended_skill", "")).strip()
        governance_type = str(result.get("governance_type", "")).strip()
        governance_dispatch_result = result.get("dispatch_result", {}) if isinstance(result.get("dispatch_result"), dict) else {}
        governance_reply_payload, governance_reply_prompts, governance_needs_user_reply = build_governance_followup_bundle(
            governance_type,
            str(result.get("request", "")),
            governance_dispatch_result,
        )
        brief["reply_kind"] = "governance"
        brief["governance_type"] = governance_type
        brief["recommended_skill"] = governance_skill
        brief["needs_user_reply"] = governance_needs_user_reply
        brief["reply_payload"] = governance_reply_payload
        brief["reply_prompts"] = governance_reply_prompts
        brief["machine_next_action"] = {
            "type": "wait-governance-followup" if governance_needs_user_reply else "governance",
            "command": "",
            "reason": next_text,
            "recommended_skill": governance_skill,
            "governance_type": governance_type,
            "can_auto_dispatch": False,
            "requires_user_reply": governance_needs_user_reply,
            "workflow_state": "governance-routing",
            "user_action": {
                "summary": human_summary,
                "next_step": next_text,
                "recovery_hint": "",
                "followup_payload": {
                    "payload": governance_reply_payload,
                    "prompts": governance_reply_prompts,
                },
            },
            "diagnostics": {
                "dispatch_attempted": False,
                "dispatch_success": None,
                "dispatch_state": "",
                "dispatch_failure_type": "",
                "dispatch_blocker": "",
                "dispatch_error": "",
                "dispatch_next": "",
                "dispatch_summary": "",
                "recovery_command": "",
                "recovery_kind": "",
                "retry_hint": "",
                "audit_path": "",
            },
            "execution": {
                "command": "",
                "command_args": [],
                "can_auto_dispatch": False,
                "auto_dispatch_reason": "governance-skill-routing",
                "requires_user_reply": governance_needs_user_reply,
                "requires_decision": False,
                "requires_audit_file": False,
                "requires_slug": False,
                "requires_step_number": False,
                "missing_fields": [],
                "workflow_state": "governance-routing",
                "current_step_number": 0,
                "current_task_id": "",
                "current_kind": "",
                "review_decision": "",
            },
            "preferred_fields": {
                "user_message": "user_action.summary",
                "next_step": "user_action.next_step",
                "governance_skill": "recommended_skill",
                "followup_payload": "user_action.followup_payload.payload",
            },
            "compatibility_fields": {
                "reason": "请优先改用 user_action.summary。",
            },
        }
        return brief

    if entry_mode == "new":
        planning_missing_fields = result.get("planning_missing_fields", [])
        clarification_prompts = result.get("clarification_prompts", [])
        brief["planning_status"] = str(result.get("planning_status", "")).strip()
        brief["planning_missing_fields"] = planning_missing_fields
        brief["resolved_kind"] = str(result.get("resolved_kind", "")).strip()
        brief["resolved_target_paths"] = result.get("resolved_target_paths", [])
        brief["needs_user_reply"] = bool(planning_missing_fields)
        brief["needs_execution"] = matches_command(recommended_command, "cgc-build", "cgc-fix")
        brief["reply_kind"] = "clarification" if planning_missing_fields else ("execution" if brief["needs_execution"] else "status")
        brief["reply_payload"] = result.get("suggested_reply_payload", {})
        brief["reply_prompts"] = clarification_prompts
        route_status = result.get("route_status", {}) if isinstance(result.get("route_status"), dict) else {}
        brief["workflow_state"] = str(route_status.get("workflow_state", "")).strip()
        brief["current_step_number"] = int(route_status.get("current_step_number", 0) or 0)
        brief["current_task_id"] = str(route_status.get("current_task_id", "")).strip()
        brief["current_kind"] = str(route_status.get("current_kind", "")).strip()
        brief["current_target_paths"] = route_status.get("current_target_paths", [])
        brief["review_decision"] = str(route_status.get("review_decision", "")).strip()
        brief["audit_path"] = str(route_status.get("audit_path", "")).strip()
        brief["machine_next_action"] = build_machine_next_action(
            action_type="wait-user-reply" if planning_missing_fields else ("dispatch" if brief["needs_execution"] else "idle"),
            command=recommended_command,
            reason=next_text,
            route_status=route_status,
            missing_fields=[str(item) for item in planning_missing_fields],
            reply_payload=brief["reply_payload"] if isinstance(brief["reply_payload"], dict) else {},
            reply_prompts=clarification_prompts if isinstance(clarification_prompts, list) else [],
        )
        return brief

    route_status = result.get("route_status", {}) if isinstance(result.get("route_status"), dict) else {}
    brief["workflow_state"] = str(route_status.get("workflow_state", "")).strip()
    brief["needs_execution"] = bool(route_status.get("needs_execution"))
    brief["needs_review"] = bool(route_status.get("needs_review_decision"))
    brief["is_closed"] = bool(route_status.get("is_closed"))
    brief["current_step_number"] = int(route_status.get("current_step_number", 0) or 0)
    brief["current_task_id"] = str(route_status.get("current_task_id", "")).strip()
    brief["current_kind"] = str(route_status.get("current_kind", "")).strip()
    brief["current_target_paths"] = route_status.get("current_target_paths", [])
    brief["review_decision"] = str(route_status.get("review_decision", "")).strip()
    brief["audit_path"] = str(route_status.get("audit_path", "")).strip()
    brief["review_fallback_stage"] = str(route_status.get("review_fallback_stage", "")).strip()
    brief["review_policy_reason"] = str(route_status.get("review_policy_reason", "")).strip()
    brief["review_action_kind"] = str(route_status.get("review_action_kind", "")).strip()
    if dispatched:
        brief["dispatch_success"] = bool(dispatch_result.get("success"))
        brief["dispatch_error"] = str(dispatch_result.get("error", "")).strip()
    if dispatched and not dispatch_result.get("success"):
        failed_command = str(dispatch_result.get("recommended_command", "")).strip() or recommended_command
        failed_reason = build_dispatch_recovery_user_hint(dispatch_result, failed_command) or next_text
        brief["reply_kind"] = "blocked"
        brief["machine_next_action"] = build_machine_next_action(
            action_type="dispatch-failed",
            command=failed_command,
            reason=failed_reason,
            route_status=route_status,
            force_can_auto_dispatch=False,
        )
    elif brief["needs_review"]:
        brief["reply_kind"] = "review"
        brief["machine_next_action"] = build_machine_next_action(
            action_type="wait-review-decision" if not brief["review_decision"] else "review",
            command=recommended_command,
            reason=next_text,
            route_status=route_status,
        )
    elif brief["needs_execution"]:
        brief["reply_kind"] = "execution"
        brief["machine_next_action"] = build_machine_next_action(
            action_type="dispatch",
            command=recommended_command,
            reason=next_text,
            route_status=route_status,
        )
    elif brief["is_closed"]:
        brief["reply_kind"] = "closed"
        brief["machine_next_action"] = build_machine_next_action(
            action_type="closed",
            command="",
            reason=next_text,
            route_status=route_status,
        )
    else:
        brief["machine_next_action"] = build_machine_next_action(
            action_type="idle",
            command=recommended_command,
            reason=next_text,
            route_status=route_status,
        )
    return brief


def discover_existing_flow(slug: str) -> tuple[str, str] | None:
    feature = discover_flow_directory("feature", slug, "auto")
    issue = discover_flow_directory("issue", slug, "auto")
    if feature and issue:
        raise ValueError(f"Slug '{slug}' exists as both feature and issue. Specify --flow explicitly.")
    if feature:
        return "feature", feature[0]
    if issue:
        return "issue", issue[0]
    return None


def workflow_activity_timestamp(directory: Path) -> float:
    timestamps = [directory.stat().st_mtime]
    for path in directory.rglob("*"):
        try:
            timestamps.append(path.stat().st_mtime)
        except OSError:
            continue
    return max(timestamps) if timestamps else 0.0


def build_latest_workflow_state_priority(request: str, explain_only: bool = False) -> dict[str, int]:
    if explain_only or request_implies_explain(request):
        return {
            "awaiting-review": 4,
            "awaiting-build": 3,
            "awaiting-fix": 3,
            "needs-planning": 2,
            "step-selected": 1,
            "closed": 0,
        }

    if request_implies_review(request):
        return {
            "awaiting-review": 5,
            "awaiting-build": 3,
            "awaiting-fix": 3,
            "needs-planning": 2,
            "step-selected": 1,
            "closed": 0,
        }

    if request_implies_execute(request) or request_implies_continue(request):
        return {
            "awaiting-build": 5,
            "awaiting-fix": 5,
            "awaiting-review": 4,
            "needs-planning": 3,
            "step-selected": 2,
            "closed": 0,
        }

    return {
        "awaiting-review": 4,
        "awaiting-build": 3,
        "awaiting-fix": 3,
        "needs-planning": 2,
        "step-selected": 1,
        "closed": 0,
    }


def build_latest_workflow_required_states(request: str, explain_only: bool = False) -> set[str]:
    if explain_only or request_implies_explain(request):
        return set()
    if request_implies_review(request):
        return {"awaiting-review"}
    return set()


def score_latest_workflow_candidate(
    flow: str,
    slug: str,
    state_priority: dict[str, int] | None = None,
) -> tuple[int, int, str]:
    try:
        route = run_json_script("route_codecgc_workflow.py", "--flow", flow, "--slug", slug)
    except Exception:
        return (0, 0, "")

    summary = route.get("summary", {}) if isinstance(route.get("summary"), dict) else {}
    workflow_state = str(summary.get("workflow_state", "")).strip()
    is_closed = bool(summary.get("is_closed"))
    recommended_command = str(route.get("recommended_command", "")).strip()
    priorities = state_priority or build_latest_workflow_state_priority("")

    if not is_closed and workflow_state:
        return (int(priorities.get(workflow_state, 1)), 1, workflow_state)
    if not is_closed and recommended_command:
        return (1, 1, workflow_state)
    return (0, 0, workflow_state)


def discover_latest_flow(
    include_fixtures: bool,
    *,
    request: str = "",
    explain_only: bool = False,
) -> tuple[str, str] | None:
    candidates: list[tuple[int, int, float, str, str]] = []
    state_priority = build_latest_workflow_state_priority(request, explain_only=explain_only)
    required_states = build_latest_workflow_required_states(request, explain_only=explain_only)
    artifact_classes = ["product", "fixture"] if include_fixtures else ["product"]
    for artifact_class in artifact_classes:
        for flow in ("feature", "issue"):
            root = flow_root(flow, artifact_class)
            if not root.exists():
                continue
            for child in root.iterdir():
                if not child.is_dir():
                    continue
                lifecycle_priority, active_priority, workflow_state = score_latest_workflow_candidate(
                    flow,
                    child.name,
                    state_priority=state_priority,
                )
                if required_states and workflow_state not in required_states:
                    continue
                candidates.append(
                    (
                        active_priority,
                        lifecycle_priority,
                        workflow_activity_timestamp(child),
                        flow,
                        child.name,
                    )
                )
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    _, _, _, flow, slug = candidates[0]
    return flow, slug


def resolve_existing_flow(args: argparse.Namespace) -> str:
    if args.flow:
        return args.flow
    use_latest = args.latest or (args.request.strip() and not args.slug.strip())
    if use_latest and not args.slug:
        discovered = discover_latest_flow(args.include_fixtures, request=args.request)
        if not discovered:
            raise ValueError("No existing workflow was found for the requested continue/explain operation.")
        return discovered[0]
    if not args.slug:
        raise ValueError("Existing workflow operations require --slug.")
    discovered = discover_existing_flow(args.slug)
    if not discovered:
        raise ValueError(f"No existing feature or issue workflow was found for slug '{args.slug}'.")
    return discovered[0]


def infer_mode(args: argparse.Namespace) -> str:
    if args.mode != "auto":
        return args.mode
    request = args.request.strip()
    shortcut_mode = classify_existing_workflow_shortcut(request)
    if shortcut_mode:
        return shortcut_mode
    if request and request_implies_explain(request):
        return "explain" if not args.summary.strip() else "new"
    if request and request_implies_continue(request):
        return "continue"
    if args.latest and not args.slug:
        return "continue"
    if args.slug:
        discovered = discover_existing_flow(args.slug)
        if discovered:
            return "continue"
        if args.summary.strip():
            return "new"
    if args.summary.strip() or request or any(item.strip() for item in args.target_path):
        return "new"
    if args.slug:
        return "explain"
    raise ValueError("Auto mode could not infer intent. Provide --request, --summary, --slug, or --latest.")


def build_plan_args(args: argparse.Namespace, flow: str) -> list[str]:
    slug = resolve_new_slug(args, flow)
    summary = resolve_new_summary(args)
    target_paths = resolve_target_paths(args)
    kind = resolve_kind(args, target_paths)
    goal = infer_feature_goal(args) if flow == "feature" else args.goal
    user_story = infer_feature_user_story(args) if flow == "feature" else args.user_story
    in_scope = infer_in_scope(args, flow, target_paths)
    acceptance = infer_acceptance(args, flow)
    symptom = infer_issue_symptom(args) if flow == "issue" else args.symptom
    expected = infer_issue_expected(args) if flow == "issue" else args.expected
    actual = infer_issue_actual(args) if flow == "issue" else args.actual

    command = [
        "--flow",
        flow,
        "--slug",
        slug,
        "--summary",
        summary,
        "--kind",
        kind,
        "--artifact-class",
        args.artifact_class,
    ]
    if args.date:
        command.extend(["--date", args.date])
    for item in target_paths:
        command.extend(["--target-path", item])
    if goal:
        command.extend(["--goal", goal])
    if user_story:
        command.extend(["--user-story", user_story])
    for item in args.context:
        command.extend(["--context", item])
    for item in in_scope:
        command.extend(["--in-scope", item])
    for item in args.out_of_scope:
        command.extend(["--out-of-scope", item])
    for item in acceptance:
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
    if symptom:
        command.extend(["--symptom", symptom])
    if args.reproduction:
        command.extend(["--reproduction", args.reproduction])
    if expected:
        command.extend(["--expected", expected])
    if actual:
        command.extend(["--actual", actual])
    if args.root_cause:
        command.extend(["--root-cause", args.root_cause])
    if args.preferred_fix:
        command.extend(["--preferred-fix", args.preferred_fix])
    if args.rejected_fix:
        command.extend(["--rejected-fix", args.rejected_fix])
    if args.force:
        command.append("--force")
    return command


def dispatch_from_route(flow: str, slug: str, route: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    command = to_internal_command(str(route.get("recommended_command", "")).strip())
    route_status = build_route_status_summary(route) if isinstance(route, dict) else {}
    reusable_session_id = str(route_status.get("reusable_session_id", "")).strip()

    if command == "cgc-build":
        command_args = ["--slug", slug, "--timeout-seconds", str(args.timeout_seconds)]
        if args.step_number is not None:
            command_args.extend(["--step-number", str(args.step_number)])
        if args.checklist_file:
            command_args.extend(["--checklist-file", args.checklist_file])
        if args.audit_root:
            command_args.extend(["--audit-root", args.audit_root])
        if args.dry_run:
            command_args.append("--dry-run")
        if args.return_all_messages:
            command_args.append("--return-all-messages")
        if reusable_session_id:
            command_args.extend(["--session-id", reusable_session_id])
        return run_json_script("run_codecgc_build.py", *command_args)

    if command == "cgc-fix":
        command_args = ["--slug", slug, "--timeout-seconds", str(args.timeout_seconds)]
        if args.step_number is not None:
            command_args.extend(["--step-number", str(args.step_number)])
        if args.checklist_file:
            command_args.extend(["--checklist-file", args.checklist_file])
        if args.audit_root:
            command_args.extend(["--audit-root", args.audit_root])
        if args.dry_run:
            command_args.append("--dry-run")
        if args.return_all_messages:
            command_args.append("--return-all-messages")
        if reusable_session_id:
            command_args.extend(["--session-id", reusable_session_id])
        return run_json_script("run_codecgc_fix.py", *command_args)

    if command == "cgc-test":
        command_args = ["--flow", flow, "--slug", slug, "--timeout-seconds", str(args.timeout_seconds)]
        if args.step_number is not None:
            command_args.extend(["--step-number", str(args.step_number)])
        if args.checklist_file:
            command_args.extend(["--checklist-file", args.checklist_file])
        if args.audit_root:
            command_args.extend(["--audit-root", args.audit_root])
        if args.dry_run:
            command_args.append("--dry-run")
        if args.return_all_messages:
            command_args.append("--return-all-messages")
        if reusable_session_id:
            command_args.extend(["--session-id", reusable_session_id])
        return run_json_script("run_codecgc_test.py", *command_args)

    if command == "cgc-review":
        audit_file = args.audit_file or str(route.get("audit_path", "")).strip()
        if not audit_file:
            return {
                "success": False,
                "error": "Review 调度需要先提供 audit 文件。",
                "recommended_command": to_public_command("cgc-review"),
                "next": route.get("next", "先提供 audit 文件，再执行 review 调度。"),
            }
        if not args.decision:
            return {
                "success": False,
                "error": "Review 调度需要先提供 --decision accepted|changes-requested。",
                "recommended_command": to_public_command("cgc-review"),
                "next": route.get("next", "先提供 review 决策，再执行 review 调度。"),
            }
        command_args = ["--audit-file", audit_file, "--decision", args.decision]
        for item in args.risk:
            command_args.extend(["--risk", item])
        if args.next_step:
            command_args.extend(["--next-step", args.next_step])
        if args.force:
            command_args.append("--force")
        return run_json_script("review_codecgc_workflow.py", *command_args)

    return {
        "success": False,
        "error": f"当前状态 '{command or 'closed'}' 不支持自动调度。",
        "recommended_command": to_public_command(command),
        "next": route.get("next", "请手动执行推荐命令。"),
    }


def refresh_route_after_dispatch(flow: str, slug: str, result: dict[str, Any]) -> None:
    dispatch_result = result.get("dispatch_result", {}) if isinstance(result.get("dispatch_result"), dict) else {}
    if not dispatch_result.get("success"):
        return
    if result.get("entry_mode") == "new":
        return

    refreshed_route = run_json_script("route_codecgc_workflow.py", "--flow", flow, "--slug", slug)
    result["route"] = refreshed_route
    result["route_status"] = build_route_status_summary(refreshed_route)
    result["recommended_command"] = to_public_command(str(refreshed_route.get("recommended_command", "")).strip())
    result["next"] = str(refreshed_route.get("next", "")).strip()

    if str(dispatch_result.get("review_state", "")).strip():
        policy_status = build_review_policy_status(dispatch_result)
        route_status = result.get("route_status", {}) if isinstance(result.get("route_status"), dict) else {}
        route_status["review_fallback_stage"] = policy_status["fallback_stage"]
        route_status["review_policy_reason"] = policy_status["policy_reason"]
        route_status["review_action_kind"] = policy_status["recommended_action_kind"]
        if policy_status["human_status_summary"]:
            route_status["human_status_summary"] = policy_status["human_status_summary"]
        if policy_status["operator_action_summary"]:
            route_status["operator_action_summary"] = policy_status["operator_action_summary"]
        result["route_status"] = route_status


def run_new_mode(args: argparse.Namespace) -> dict[str, Any]:
    flow = infer_flow_for_new_work(args)
    resolved_target_paths = resolve_target_paths(args)
    resolved_kind = resolve_kind(args, resolved_target_paths)
    planning_snapshot = build_planning_snapshot(flow, args, resolved_target_paths, resolved_kind)
    plan = run_json_script("plan_codecgc_workflow.py", *build_plan_args(args, flow))
    planning_missing_fields = list(plan.get("planning_missing_fields", []))
    clarification_prompts = build_clarification_prompts(flow, planning_missing_fields)
    recommended_command = to_public_command(str(plan.get("recommended_command", "")).strip())
    effective_auto_dispatch, auto_dispatch_reason = resolve_effective_auto_dispatch(args, recommended_command)
    result = {
        "success": bool(plan.get("success")),
        "entry_mode": "new",
        "flow": flow,
        "slug": plan.get("slug", args.slug),
        "request": args.request,
        "resolved_kind": resolved_kind,
        "resolved_target_paths": resolved_target_paths,
        "planning_snapshot": planning_snapshot,
        "captured_fields": build_captured_fields(planning_snapshot),
        "auto_dispatch": effective_auto_dispatch,
        "auto_dispatch_reason": auto_dispatch_reason,
        "plan": plan,
        "planning_status": plan.get("planning_status", ""),
        "planning_reasons": plan.get("planning_reasons", []),
        "planning_missing_fields": planning_missing_fields,
        "clarification_mode": build_clarification_mode(flow, planning_missing_fields, resolved_kind),
        "clarification_prompts": clarification_prompts,
        "route": plan.get("route", {}),
        "recommended_command": recommended_command,
        "next": plan.get("next", ""),
        "dispatched": False,
        "dispatch_result": None,
    }
    result["suggested_reply_template"] = build_suggested_reply_template(flow, result["clarification_prompts"])
    result["suggested_reply_payload"] = build_suggested_reply_payload(flow, planning_snapshot, planning_missing_fields)
    if isinstance(plan.get("route"), dict):
        result["route_status"] = build_route_status_summary(plan.get("route", {}))
    if not effective_auto_dispatch or not plan.get("success"):
        result["next"] = build_user_facing_next(result)
        result["human_summary"] = build_new_mode_human_summary(result)
        result["assistant_reply"] = build_assistant_reply(result)
        result["operator_brief"] = build_operator_brief(result)
        return attach_entry_summary(result)

    if recommended_command not in {"cgc-build", "cgc-fix"}:
        result["next"] = build_user_facing_next(result)
        result["human_summary"] = build_new_mode_human_summary(result)
        result["assistant_reply"] = build_assistant_reply(result)
        result["operator_brief"] = build_operator_brief(result)
        return attach_entry_summary(result)

    dispatch_result = dispatch_from_route(flow, str(plan.get("slug", args.slug)), plan.get("route", {}), args)
    result["dispatched"] = True
    result["dispatch_result"] = dispatch_result
    if dispatch_result.get("success"):
        result["recommended_command"] = to_public_command(dispatch_result.get("recommended_command", ""))
        result["next"] = dispatch_result.get("next", "")
    else:
        apply_dispatch_failure_context(result, recommended_command)
    result["human_summary"] = build_new_mode_human_summary(result)
    result["assistant_reply"] = build_assistant_reply(result)
    result["operator_brief"] = build_operator_brief(result)
    return attach_entry_summary(result)


def run_existing_mode(args: argparse.Namespace, explain_only: bool) -> dict[str, Any]:
    if not args.slug.strip() and not args.latest and not args.request.strip():
        raise ValueError("Continue or explain mode requires --slug, --latest, or a continue/explain request.")
    slug = args.slug
    use_latest = args.latest or (args.request.strip() and not args.slug.strip())
    latest_discovered: tuple[str, str] | None = None
    if not slug and use_latest:
        latest_discovered = discover_latest_flow(
            args.include_fixtures,
            request=args.request,
            explain_only=explain_only,
        )
        if not latest_discovered:
            if request_implies_review(args.request):
                return build_missing_existing_workflow_result(
                    request=args.request,
                    explain_only=explain_only,
                    include_fixtures=args.include_fixtures,
                    human_summary="当前没有待审核的 CodeCGC 工作流。",
                    next_text="先用“现在下一步该做什么”查看最近工作流，或先完成执行步骤后再回来审核。",
                    action_reason="当前仓库里没有处于 awaiting-review 的最近工作流，无法直接处理“通过/不通过/审核”这类请求。",
                    workflow_state="needs-review-target",
                    reply_kind="review-target-missing",
                    action_type="wait-review-target",
                    dispatch_blocker="missing-review-workflow",
                    recovery_hint="先定位一个待审核 workflow，或先完成 build/fix 再回来审核。",
                    recommended_command="cgc",
                    command_args=["--request", "现在下一步该做什么"],
                )
            return build_missing_existing_workflow_result(
                request=args.request,
                explain_only=explain_only,
                include_fixtures=args.include_fixtures,
                recommended_command="cgc",
                command_args=["--request", "<描述你的新需求>"],
            )
        slug = latest_discovered[1]
    flow = args.flow or (latest_discovered[0] if latest_discovered else resolve_existing_flow(args))
    route = run_json_script("route_codecgc_workflow.py", "--flow", flow, "--slug", slug)
    recommended_command = to_public_command(str(route.get("recommended_command", "")).strip())
    replan_payload = build_existing_workflow_replan_payload(flow, slug)
    effective_auto_dispatch, auto_dispatch_reason = resolve_effective_auto_dispatch(
        args,
        recommended_command,
        explain_only=explain_only,
    )
    result = {
        "success": bool(route.get("success", True)),
        "entry_mode": "explain" if explain_only else "continue",
        "flow": flow,
        "slug": slug,
        "auto_dispatch": effective_auto_dispatch,
        "auto_dispatch_reason": auto_dispatch_reason,
        "latest": use_latest,
        "request": args.request,
        "route": route,
        "route_status": build_route_status_summary(route),
        "replan_payload": replan_payload,
        "recommended_command": recommended_command,
        "next": route.get("next", ""),
        "dispatched": False,
        "dispatch_result": None,
    }
    if explain_only or not effective_auto_dispatch:
        result["next"] = build_user_facing_next(result)
        result["human_summary"] = build_existing_mode_human_summary(result)
        result["assistant_reply"] = build_assistant_reply(result)
        result["operator_brief"] = build_operator_brief(result)
        return attach_entry_summary(result)

    if recommended_command not in {"cgc-build", "cgc-fix", "cgc-review"}:
        result["next"] = build_user_facing_next(result)
        result["human_summary"] = build_existing_mode_human_summary(result)
        result["assistant_reply"] = build_assistant_reply(result)
        result["operator_brief"] = build_operator_brief(result)
        return attach_entry_summary(result)

    dispatch_result = dispatch_from_route(flow, slug, route, args)
    result["dispatched"] = True
    result["dispatch_result"] = dispatch_result
    if dispatch_result.get("success"):
        result["recommended_command"] = to_public_command(dispatch_result.get("recommended_command", ""))
        result["next"] = dispatch_result.get("next", "")
        refresh_route_after_dispatch(flow, slug, result)
        result["next"] = build_user_facing_next(result)
    else:
        apply_dispatch_failure_context(result, recommended_command)
    result["human_summary"] = build_existing_mode_human_summary(result)
    result["assistant_reply"] = build_assistant_reply(result)
    result["operator_brief"] = build_operator_brief(result)
    return attach_entry_summary(result)


def run_governance_mode(args: argparse.Namespace, governance: dict[str, str]) -> dict[str, Any]:
    request = args.request.strip()
    slug = args.slug.strip()
    flow = args.flow.strip()
    human_summary = str(governance.get("human_summary", "")).strip()
    next_text = str(governance.get("next", "")).strip()
    skill = str(governance.get("skill", "")).strip()
    governance_type = str(governance.get("governance_type", "")).strip()
    dispatch_result: dict[str, Any] | None = None
    auto_dispatch = False
    auto_dispatch_reason = "governance-skill-routing"

    if governance_type == "decide":
        auto_dispatch = True
        auto_dispatch_reason = "governance-auto-write"
        dispatch_result = run_json_script(
            "write_codecgc_decision.py",
            "--summary",
            request,
            "--constraint",
            "将其视为约束未来 CodeCGC 行为的长期有效规则。",
            "--source",
            "cgc-entry 治理分诊",
        )
        if dispatch_result.get("success"):
            decision = dispatch_result.get("decision", {}) if isinstance(dispatch_result.get("decision"), dict) else {}
            decision_path = str(decision.get("path", "")).strip()
            human_summary = "已将这条长期决定写入 CodeCGC 的长期决策资产。"
            next_text = f"下一步检查 {decision_path or 'codecgc/compound/codecgc-decisions.md'}，确认表述是否还需要补充。"

    elif governance_type == "learn":
        auto_dispatch = True
        auto_dispatch_reason = "governance-auto-write"
        dispatch_result = run_json_script(
            "write_codecgc_learning.py",
            "--summary",
            request,
            "--kind",
            "practice",
            "--instruction",
            "遇到同类问题时，优先把可复用经验沉淀到长期资产，而不是只停留在会话里。",
            "--source",
            "cgc-entry 治理分诊",
        )
        if dispatch_result.get("success"):
            learning = dispatch_result.get("learning", {}) if isinstance(dispatch_result.get("learning"), dict) else {}
            learning_path = str(learning.get("path", "")).strip()
            human_summary = "已将这条可复用经验写入 CodeCGC 的经验资产。"
            next_text = f"下一步检查 {learning_path or 'codecgc/compound/codecgc-learning-log.md'}，确认是否需要补充更具体的后续指引。"

    elif governance_type == "arch":
        auto_dispatch = True
        auto_dispatch_reason = "governance-auto-write"
        dispatch_result = run_json_script(
            "write_codecgc_architecture.py",
            "--summary",
            request,
            "--note",
            "将其视为当前仓库架构现状的长期更新记录。",
            "--source",
            "cgc-entry 治理分诊",
        )
        if dispatch_result.get("success"):
            architecture = (
                dispatch_result.get("architecture", {})
                if isinstance(dispatch_result.get("architecture"), dict)
                else {}
            )
            architecture_path = str(architecture.get("path", "")).strip()
            human_summary = "已将这条当前态架构更新写入 CodeCGC 的架构资产。"
            next_text = (
                f"下一步检查 {architecture_path or 'codecgc/architecture/codecgc-system-map.md'}，"
                "确认是否需要补充更细的模块边界或集成说明。"
            )

    elif governance_type == "req":
        auto_dispatch = True
        auto_dispatch_reason = "governance-auto-write"
        dispatch_result = run_json_script(
            "write_codecgc_requirement.py",
            "--summary",
            request,
            "--note",
            "将其视为产品面的长期稳定需求更新。",
            "--source",
            "cgc-entry 治理分诊",
        )
        if dispatch_result.get("success"):
            requirement = (
                dispatch_result.get("requirement", {})
                if isinstance(dispatch_result.get("requirement"), dict)
                else {}
            )
            requirement_path = str(requirement.get("path", "")).strip()
            human_summary = "已将这条稳定需求更新写入 CodeCGC 的需求资产。"
            next_text = (
                f"下一步检查 {requirement_path or 'codecgc/requirements/codecgc-core-requirements.md'}，"
                "确认是否需要补充更明确的能力边界或非目标说明。"
            )

    elif governance_type == "roadmap":
        auto_dispatch = True
        auto_dispatch_reason = "governance-auto-write"
        dispatch_result = run_json_script(
            "write_codecgc_roadmap.py",
            "--summary",
            request,
            "--goal",
            request,
            "--source",
            "cgc-entry 治理分诊",
        )
        if dispatch_result.get("success"):
            roadmap = dispatch_result.get("roadmap", {}) if isinstance(dispatch_result.get("roadmap"), dict) else {}
            roadmap_directory = str(roadmap.get("directory", "")).strip()
            human_summary = "已将这条大规模规划请求初始化为 CodeCGC 的 roadmap 资产。"
            next_text = (
                f"下一步检查 {roadmap_directory or 'codecgc/roadmap/'}，"
                "确认 phases、delivery plan 和后续 child workflow 拆分是否足够清晰。"
            )

    elif governance_type == "refactor":
        auto_dispatch = True
        auto_dispatch_reason = "governance-auto-write"
        dispatch_result = run_json_script(
            "write_codecgc_refactor.py",
            "--summary",
            request,
            "--note",
            "将其视为保持行为不变、但仍需走受控执行流程的结构优化候选项。",
            "--source",
            "cgc-entry 治理分诊",
        )
        if dispatch_result.get("success"):
            refactor = dispatch_result.get("refactor", {}) if isinstance(dispatch_result.get("refactor"), dict) else {}
            refactor_path = str(refactor.get("path", "")).strip()
            human_summary = "已将这条受控重构请求写入 CodeCGC 的重构队列资产。"
            next_text = (
                f"下一步检查 {refactor_path or 'codecgc/compound/codecgc-productization-gap.md'}，"
                "确认这条重构是否需要转成更具体的可执行 workflow。"
            )

    elif governance_type == "guide":
        auto_dispatch = True
        auto_dispatch_reason = "governance-auto-write"
        dispatch_result = run_json_script(
            "write_codecgc_guide.py",
            "--summary",
            request,
            "--audience",
            "developer",
            "--note",
            "将其视为需要长期维护的任务导向指南入口。",
            "--source",
            "cgc-entry 治理分诊",
        )
        if dispatch_result.get("success"):
            guide = dispatch_result.get("guide", {}) if isinstance(dispatch_result.get("guide"), dict) else {}
            guide_path = str(guide.get("path", "")).strip()
            human_summary = "已将这条指南请求写入 CodeCGC 的 docs guide 资产。"
            next_text = (
                f"下一步检查 {guide_path or 'codecgc/docs/'}，"
                "补全目的、步骤和使用边界。"
            )

    elif governance_type == "libdoc":
        auto_dispatch = True
        auto_dispatch_reason = "governance-auto-write"
        dispatch_result = run_json_script(
            "write_codecgc_libdoc.py",
            "--summary",
            request,
            "--surface",
            "public-api",
            "--source",
            "cgc-entry 治理分诊",
        )
        if dispatch_result.get("success"):
            libdoc = dispatch_result.get("libdoc", {}) if isinstance(dispatch_result.get("libdoc"), dict) else {}
            libdoc_path = str(libdoc.get("path", "")).strip()
            human_summary = "已将这条参考文档请求写入 CodeCGC 的 libdoc 资产。"
            next_text = (
                f"下一步检查 {libdoc_path or 'codecgc/reference/'}，"
                "补全公开契约、示例与边界说明。"
            )

    elif governance_type == "trick":
        auto_dispatch = True
        auto_dispatch_reason = "governance-auto-write"
        dispatch_result = run_json_script(
            "write_codecgc_trick.py",
            "--summary",
            request,
            "--kind",
            "technique",
            "--instruction",
            "将其视为可复用默认做法，后续可继续补充示例与适用边界。",
            "--source",
            "cgc-entry 治理分诊",
        )
        if dispatch_result.get("success"):
            trick = dispatch_result.get("trick", {}) if isinstance(dispatch_result.get("trick"), dict) else {}
            trick_path = str(trick.get("path", "")).strip()
            human_summary = "已将这条技巧请求写入 CodeCGC 的 trick 资产。"
            next_text = (
                f"下一步检查 {trick_path or 'codecgc/compound/codecgc-tricks.md'}，"
                "确认是否需要补更多默认做法与适用范围。"
            )

    elif governance_type == "explore":
        auto_dispatch = True
        auto_dispatch_reason = "governance-auto-write"
        dispatch_result = run_json_script(
            "write_codecgc_explore.py",
            "--summary",
            request,
            "--kind",
            "question",
            "--source",
            "cgc-entry 治理分诊",
        )
        if dispatch_result.get("success"):
            explore = dispatch_result.get("explore", {}) if isinstance(dispatch_result.get("explore"), dict) else {}
            explore_path = str(explore.get("path", "")).strip()
            human_summary = "已将这条探索请求写入 CodeCGC 的 exploration 资产。"
            next_text = (
                f"下一步检查 {explore_path or 'codecgc/compound/codecgc-explorations.md'}，"
                "再决定是否要继续做真实代码探索与证据回填。"
            )

    result = {
        "success": True,
        "entry_mode": "governance",
        "flow": flow,
        "slug": slug,
        "request": request,
        "governance_type": governance_type,
        "recommended_skill": skill,
        "recommended_command": "",
        "next": next_text,
        "human_summary": human_summary,
        "assistant_reply": "",
        "dispatched": bool(dispatch_result),
        "dispatch_result": dispatch_result,
        "auto_dispatch": auto_dispatch,
        "auto_dispatch_reason": auto_dispatch_reason,
        "route_status": {
            "workflow_state": "governance-routing",
            "recommended_command": "",
            "current_step_number": 0,
            "current_task_id": "",
            "current_kind": "",
            "current_target_paths": [],
            "review_decision": "",
            "review_step_number": 0,
            "audit_path": "",
            "human_status_summary": human_summary,
            "operator_action_summary": next_text,
            "is_closed": False,
            "needs_review_decision": False,
            "needs_execution": False,
        },
    }
    result["assistant_reply"] = build_assistant_reply(result)
    result["operator_brief"] = build_operator_brief(result)
    return attach_entry_summary(result)


def main() -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()
    args = apply_entry_payload(args)

    try:
        followup_payload = load_payload_input(args)
        nested_payload = followup_payload.get("payload", {}) if isinstance(followup_payload.get("payload"), dict) else {}
        governance_followup = resolve_governance_followup(nested_payload, args.request)
        if governance_followup:
            dispatch_result = run_json_script(
                str(governance_followup.get("script", "")).strip(),
                *[str(item) for item in governance_followup.get("args", []) if str(item).strip()],
            )
            artifact_path = str(governance_followup.get("artifact_path", "")).strip() or str(nested_payload.get("artifact_path", "")).strip()
            governance_type = str(governance_followup.get("governance_type", "")).strip()
            result = {
                "success": bool(dispatch_result.get("success")),
                "entry_mode": "governance",
                "flow": "",
                "slug": "",
                "request": args.request.strip(),
                "governance_type": governance_type,
                "recommended_skill": f"cgc-{governance_type}",
                "recommended_command": "",
                "next": f"已把补充内容回写到 {artifact_path or '对应长期资产'}，如还有缺口可继续补充。",
                "human_summary": "已将这轮补充内容回写到同一个治理资产中。",
                "assistant_reply": "",
                "dispatched": True,
                "dispatch_result": dispatch_result,
                "auto_dispatch": True,
                "auto_dispatch_reason": "governance-followup-write",
                "route_status": {
                    "workflow_state": "governance-routing",
                    "recommended_command": "",
                    "current_step_number": 0,
                    "current_task_id": "",
                    "current_kind": "",
                    "current_target_paths": [],
                    "review_decision": "",
                    "review_step_number": 0,
                    "audit_path": "",
                    "human_status_summary": "已将这轮补充内容回写到同一个治理资产中。",
                    "operator_action_summary": f"继续检查 {artifact_path or '对应长期资产'}，必要时补充下一轮内容。",
                    "is_closed": False,
                    "needs_review_decision": False,
                    "needs_execution": False,
                },
            }
            result["assistant_reply"] = build_assistant_reply(result)
            result["operator_brief"] = build_operator_brief(result)
            result = attach_entry_summary(result)
            result["inferred_mode"] = "governance-followup"
            print_json(result)
            return 0 if result.get("success") else 1

        governance = classify_governance_request(args.request)
        if governance:
            result = run_governance_mode(args, governance)
            result["inferred_mode"] = "governance"
            print_json(result)
            return 0
        inferred_mode = infer_mode(args)
        if inferred_mode == "new":
            result = run_new_mode(args)
        elif inferred_mode == "continue":
            result = run_existing_mode(args, explain_only=False)
        else:
            result = run_existing_mode(args, explain_only=True)
        result["inferred_mode"] = inferred_mode
    except Exception as error:
        print_json({"success": False, "error": str(error)}, file=sys.stderr)
        return 1

    print_json(result)
    operator_brief = result.get("operator_brief", {}) if isinstance(result.get("operator_brief"), dict) else {}
    is_closed = bool(operator_brief.get("is_closed"))
    workflow_state = str(operator_brief.get("workflow_state", "")).strip()
    if result.get("success") or workflow_state in {"needs-planning", "awaiting-build", "awaiting-fix", "awaiting-review"} or not is_closed:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
