import argparse
import datetime as dt
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from build_codecgc_task import classify_path
from codecgc_artifact_roots import flow_root
from codecgc_plan_decision import evaluate_plan_decision
from build_codecgc_task import load_simple_routing_config
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_routing_paths import resolve_active_routing_file
from codecgc_workflow_templates import build_acceptance_lines
from codecgc_workflow_templates import build_constraint_lines
from codecgc_workflow_templates import build_test_step
from codecgc_workflow_templates import render_feature_checklist_steps
from codecgc_workflow_templates import render_issue_fix_steps
from codecgc_workflow_runtime import run_json_script
from codecgc_runtime_paths import PACKAGE_ROOT


WORKSPACE = PACKAGE_ROOT
ROUTING_FILE = resolve_active_routing_file()


def slugify(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    if not normalized:
        raise ValueError("Slug cannot be empty after normalization.")
    return normalized


def resolve_slug_pair(raw_slug: str, default_date: str) -> tuple[str, str]:
    candidate = raw_slug.strip()
    dated_match = re.match(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<rest>.+)$", candidate)
    if dated_match:
        base_slug = slugify(dated_match.group("rest"))
        artifact_date = dated_match.group("date")
        return base_slug, f"{artifact_date}-{base_slug}"

    base_slug = slugify(candidate)
    return base_slug, f"{default_date}-{base_slug}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan a CodeCGC feature or issue workflow and create the scaffold when needed."
    )
    parser.add_argument("--flow", required=True, choices=["feature", "issue"])
    parser.add_argument("--slug", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--date", default=dt.date.today().isoformat())
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
    parser.add_argument("--force", action="store_true")
    return parser


def should_create_scaffold(route_result: dict[str, object]) -> bool:
    reason = str(route_result.get("reason", "")).lower()
    return "does not exist yet" in reason or "目录尚不存在" in str(route_result.get("reason", ""))


def scaffold_incomplete(route_result: dict[str, object]) -> bool:
    reason = str(route_result.get("reason", "")).lower()
    return "scaffold is incomplete" in reason or "骨架不完整" in str(route_result.get("reason", ""))


def owner_label(kind: str) -> str:
    if kind == "frontend":
        return "前端 / Gemini"
    if kind == "backend":
        return "后端 / Codex"
    return "待拆分"


def yaml_list(items: list[str], indent: int, fallback: str) -> str:
    values = [item.strip() for item in items if item.strip()]
    prefix = " " * indent
    if not values:
        return f"{prefix}- {fallback}"
    return "\n".join(f"{prefix}- {item}" for item in values)


def cleaned_items(items: list[str]) -> list[str]:
    return [item.strip() for item in items if item.strip()]


def build_path_groups(args: argparse.Namespace) -> tuple[dict[str, list[str]], list[str]]:
    if args.kind != "auto":
        return {args.kind: [path for path in args.target_path if path.strip()]}, []

    routing = load_simple_routing_config(ROUTING_FILE)
    grouped: dict[str, list[str]] = defaultdict(list)
    route_notes: list[str] = []
    for raw_path in args.target_path:
        path = raw_path.strip()
        if not path:
            continue
        category = classify_path(path, routing)
        grouped[category].append(path)
        route_notes.append(f"{path} -> {category}")
    return dict(grouped), route_notes


def summarize_paths(paths: list[str]) -> str:
    if not paths:
        return "当前批准范围"
    if len(paths) == 1:
        return paths[0]
    return f"{paths[0]} 等 {len(paths) - 1} 个路径"


def infer_step_acceptance(kind: str, flow: str, paths: list[str], acceptance: list[str]) -> list[str]:
    scoped: list[str] = []
    lower_kind = kind.lower()
    for item in acceptance:
        lowered = item.lower()
        if lower_kind in lowered:
            scoped.append(item)
            continue
        if kind == "frontend" and "backend" in lowered:
            continue
        if kind == "backend" and "frontend" in lowered:
            continue
        scoped.append(item)

    if scoped:
        return scoped

    if flow == "issue":
        if kind == "frontend":
            return [
                f"前端修复必须限定在 {summarize_paths(paths)} 内。",
                "浏览器侧修复行为只覆盖当前限定的缺陷范围。",
            ]
        if kind == "backend":
            return [
                f"后端修复必须限定在 {summarize_paths(paths)} 内。",
                "后端修复行为只覆盖当前限定的缺陷范围。",
            ]
    else:
        if kind == "frontend":
            return [
                f"前端实现必须限定在 {summarize_paths(paths)} 内。",
                "浏览器侧行为只覆盖当前限定的功能步骤。",
            ]
        if kind == "backend":
            return [
                f"后端实现必须限定在 {summarize_paths(paths)} 内。",
                "后端行为只覆盖当前限定的功能步骤。",
            ]

    return build_acceptance_lines(kind, paths)


def infer_task_summary(kind: str, flow: str, paths: list[str]) -> str:
    scope_text = summarize_paths(paths)
    if flow == "issue":
        if kind == "frontend":
            return f"只在 {scope_text} 内应用已批准的前端修复。"
        if kind == "backend":
            return f"只在 {scope_text} 内应用已批准的后端修复。"
        return f"只在 {scope_text} 内应用已批准的修复。"

    if kind == "frontend":
        return f"只在 {scope_text} 内实现已批准的前端步骤。"
    if kind == "backend":
        return f"只在 {scope_text} 内实现已批准的后端步骤。"
    return f"只在 {scope_text} 内实现已批准的步骤。"


def infer_action(kind: str, flow: str) -> str:
    if flow == "issue":
        return "执行一个前端修复步骤" if kind == "frontend" else "执行一个后端修复步骤" if kind == "backend" else "执行一个限定范围的修复步骤"
    return "执行一个前端功能步骤" if kind == "frontend" else "执行一个后端功能步骤" if kind == "backend" else "执行一个限定范围的功能步骤"


def build_execution_steps(slug: str, flow: str, grouped_paths: dict[str, list[str]], acceptance: list[str]) -> list[dict[str, object]]:
    steps: list[dict[str, object]] = []
    executable_index = 1

    for kind in ("frontend", "backend"):
        paths = grouped_paths.get(kind, [])
        if not paths:
            continue
        task_suffix = "fix-step" if flow == "issue" else "step"
        summary = infer_task_summary(kind, flow, paths)
        action = infer_action(kind, flow)
        exit_signal = "修复步骤已可进入委派执行" if flow == "issue" else "步骤契约已可进入委派执行"
        step_acceptance = infer_step_acceptance(kind, flow, paths, acceptance) or build_acceptance_lines(kind, paths)
        steps.append(
            {
                "action": action,
                "exit_signal": exit_signal,
                "status": "pending",
                "codecgc": {
                    "kind": kind,
                    "task_id": f"{slug}-{task_suffix}-{executable_index}",
                    "task_summary": summary,
                    "target_paths": paths,
                    "constraints": build_constraint_lines(kind),
                    "acceptance": step_acceptance,
                    "cd": ".",
                },
            }
        )
        executable_index += 1
        steps.append(
            build_test_step(
                slug=slug,
                flow=flow,
                kind=kind,
                target_paths=infer_test_target_paths(kind, paths),
                step_index=executable_index,
            )
        )
        executable_index += 1

    shared_paths = grouped_paths.get("shared", [])
    unknown_paths = grouped_paths.get("unknown", [])
    if shared_paths:
        steps.append(
            {
                "action": "在执行前先拆分共享范围工作",
                "exit_signal": "共享路径已经重新分配到纯前端或纯后端 steps",
                "status": "pending",
                "owner_hint": "Claude 规划",
                "planning_note": "共享路径不能在一个 CodeCGC 步骤中直接执行。",
            }
        )
    if unknown_paths:
        steps.append(
            {
                "action": "在执行前先确认未知路由路径",
                "exit_signal": "每个目标路径都已经被 model-routing.yaml 覆盖",
                "status": "pending",
                "owner_hint": "Claude 规划",
                "planning_note": "未知路径必须先分类或移除，才能进入执行。",
            }
        )

    if not steps:
        task_suffix = "fix-step" if flow == "issue" else "step"
        summary = "只执行当前已批准的修复步骤。" if flow == "issue" else "只执行当前已批准的步骤。"
        action = "执行一个限定范围的修复步骤" if flow == "issue" else "定义一个可执行步骤"
        exit_signal = "修复步骤已可进入委派执行" if flow == "issue" else "步骤契约已可进入委派执行"
        step_acceptance = acceptance or build_acceptance_lines("auto", [])
        steps.append(
            {
                "action": action,
                "exit_signal": exit_signal,
                "status": "pending",
                "codecgc": {
                    "kind": "auto",
                    "task_id": f"{slug}-{task_suffix}-1",
                    "task_summary": summary,
                    "target_paths": ["待补路径"],
                    "constraints": build_constraint_lines("auto"),
                    "acceptance": step_acceptance,
                    "cd": ".",
                },
            }
        )

    return steps


def infer_test_target_paths(kind: str, paths: list[str]) -> list[str]:
    inferred: list[str] = []
    for path in paths:
        normalized = str(path).replace("\\", "/").strip()
        if kind == "frontend":
            if normalized.endswith(".tsx"):
                inferred.append(normalized.replace(".tsx", ".test.tsx"))
            elif normalized.endswith(".ts"):
                inferred.append(normalized.replace(".ts", ".test.ts"))
            elif normalized.endswith(".jsx"):
                inferred.append(normalized.replace(".jsx", ".test.jsx"))
            elif normalized.endswith(".js"):
                inferred.append(normalized.replace(".js", ".test.js"))
            else:
                inferred.append(normalized)
        else:
            if normalized.endswith(".py"):
                inferred.append(normalized.replace(".py", "_test.py"))
            elif normalized.endswith(".go"):
                inferred.append(normalized.replace(".go", "_test.go"))
            elif normalized.endswith(".ts"):
                inferred.append(normalized.replace(".ts", ".spec.ts"))
            elif normalized.endswith(".js"):
                inferred.append(normalized.replace(".js", ".spec.js"))
            else:
                inferred.append(normalized)
    return inferred or paths


def downgrade_steps_to_planning_only(steps: list[dict[str, object]], reason: str) -> list[dict[str, object]]:
    downgraded: list[dict[str, object]] = []
    for step in steps:
        codecgc = step.get("codecgc")
        if not isinstance(codecgc, dict):
            downgraded.append(step)
            continue
        downgraded.append(
            {
                "action": str(step.get("action", "执行前先补齐规划信息")),
                "exit_signal": str(step.get("exit_signal", "执行前必须先完成规划")),
                "status": str(step.get("status", "pending")),
                "owner_hint": "Claude 规划",
                "planning_note": reason,
            }
        )
    return downgraded


def render_step_outline(steps: list[dict[str, object]]) -> str:
    lines: list[str] = []
    for index, step in enumerate(steps, start=1):
        codecgc = step.get("codecgc")
        if not isinstance(codecgc, dict):
            owner_hint = str(step.get("owner_hint", "Claude 规划")).strip()
            planning_note = str(step.get("planning_note", "")).strip() or "执行前需要先完成规划处理。"
            lines.extend(
                [
                    f"- 步骤 {index}: {step['action']}",
                    f"  归属: {owner_hint}",
                    f"  状态: 仅规划",
                    f"  说明: {planning_note}",
                ]
            )
            continue

        paths = codecgc.get("target_paths", [])
        acceptance = codecgc.get("acceptance", [])
        lines.extend(
            [
                f"- 步骤 {index}: {step['action']}",
                f"  归属: {owner_label(str(codecgc.get('kind', 'auto')))}",
                f"  路径: {', '.join(str(path) for path in paths) or '待补路径'}",
                f"  摘要: {codecgc.get('task_summary', '')}",
                f"  验收: {' | '.join(str(item) for item in acceptance) or '待补充'}",
            ]
        )
    return "\n".join(lines) if lines else "- 待补充"


def render_feature_design_document(directory_name: str, summary: str, args: argparse.Namespace, grouped_paths: dict[str, list[str]], route_notes: list[str], steps: list[dict[str, object]]) -> str:
    mixed_scope = len([kind for kind in ("frontend", "backend") if grouped_paths.get(kind)]) > 1
    planning_split_required = mixed_scope or bool(grouped_paths.get("shared")) or bool(grouped_paths.get("unknown"))
    executable_steps, planning_only_steps = summarize_step_counts(steps)
    plan_decision = evaluate_plan_decision(
        flow="feature",
        grouped_paths=grouped_paths,
        target_paths=cleaned_items(args.target_path),
        executable_steps=executable_steps,
        planning_only_steps=planning_only_steps,
        goal=args.goal,
        user_story=args.user_story,
        symptom="",
        expected="",
        actual="",
        in_scope=cleaned_items(args.in_scope),
        acceptance=cleaned_items(args.acceptance),
    )
    validation_lines = cleaned_items(args.validation) or [
        "对当前待执行步骤运行委派执行。",
        "在验收前先审核审计证据。",
    ]
    rollback_lines = cleaned_items(args.rollback) or [
        "如果审核或验证失败，只回退当前限定范围的步骤。",
        "如果归属或范围变化，回到规划阶段。",
    ]
    return f"""---
doc_type: feature-design
artifact_class: {args.artifact_class}
feature: {directory_name}
status: draft
summary: {summary}
tags: []
---

# {summary}

## 1. 目标

- 摘要: {summary}
- 用户目标: {args.goal.strip() if args.goal else '待补充'}
- 用户故事: {args.user_story.strip() if args.user_story else '待补充'}
- 计划执行归属: {"执行前由 Claude 先拆分" if mixed_scope or grouped_paths.get('shared') or grouped_paths.get('unknown') else owner_label(args.kind if args.kind != 'auto' else next(iter([k for k in ('frontend', 'backend') if grouped_paths.get(k)]), 'auto'))}
- 候选目标路径:
{yaml_list(args.target_path, 2, '待补路径')}

## 2. 背景

{yaml_list(cleaned_items(args.context), 0, '待补充')}

## 3. 范围内

{yaml_list(args.in_scope or [f"仅修改 `{path}`。" for path in args.target_path], 0, '待补充')}

## 4. 范围外

{yaml_list(args.out_of_scope or [item for item in build_constraint_lines(args.kind) if item != '不要修改 target_paths 之外的文件。'], 0, '待补充')}

## 5. 依赖与假设

依赖:
{yaml_list(cleaned_items(args.dependency), 2, '待补充')}

假设:
{yaml_list(cleaned_items(args.assumption), 2, '待补充')}

## 6. 执行说明

{yaml_list([
    "该产物在真正可执行前，还需要先通过多个受规划控制的 steps 完成拆分或补齐。" if planning_split_required else "该产物当前已经限定在单执行器可接管的 step 内。",
    f"规划状态: {plan_decision['planning_status']}",
    *([f"路由说明: {item}" for item in route_notes] or []),
    *([f"验收提示: {item}" for item in args.acceptance if item.strip()] or []),
    *([f"规划风险: {item}" for item in args.risk if item.strip()] or []),
    *([f"决策说明: {item}" for item in plan_decision.get("reasons", [])] or []),
], 0, '待补充')}

## 7. 验证计划

{yaml_list(validation_lines, 0, '待补充')}

## 8. 回退计划

{yaml_list(rollback_lines, 0, '待补充')}

## 9. 开放问题

{yaml_list(cleaned_items(args.open_question), 0, '当前无。')}

## 10. 计划步骤

{render_step_outline(steps)}
"""


def render_issue_report_document(directory_name: str, summary: str, args: argparse.Namespace, grouped_paths: dict[str, list[str]], route_notes: list[str], steps: list[dict[str, object]]) -> str:
    mixed_scope = len([kind for kind in ("frontend", "backend") if grouped_paths.get(kind)]) > 1
    return f"""---
doc_type: issue-report
artifact_class: {args.artifact_class}
issue: {directory_name}
status: draft
severity: P2
summary: {summary}
tags: []
---

# {summary} 问题报告

## 1. 现象

- 摘要: {summary}
- 现象: {args.symptom.strip() if args.symptom else '待补充'}
- 用户影响: {args.user_story.strip() if args.user_story else '待补充'}
- 预估执行归属: {"执行前由 Claude 先拆分" if mixed_scope or grouped_paths.get('shared') or grouped_paths.get('unknown') else owner_label(args.kind if args.kind != 'auto' else next(iter([k for k in ('frontend', 'backend') if grouped_paths.get(k)]), 'auto'))}
- 候选影响路径:
{yaml_list(args.target_path, 2, '待补路径')}

## 2. 复现方式

{yaml_list([args.reproduction.strip()] if args.reproduction else [], 0, '待补充')}

## 3. 预期与实际

{yaml_list([
    f'预期: {args.expected.strip()}' if args.expected else '预期: 待补充',
    f'实际: {args.actual.strip()}' if args.actual else '实际: 待补充',
    *([f'路由说明: {item}' for item in route_notes] or []),
], 0, '待补充')}

## 4. 背景

{yaml_list(cleaned_items(args.context), 0, '待补充')}

## 5. 计划步骤

{render_step_outline(steps)}
"""


def render_issue_analysis_document(directory_name: str, summary: str, args: argparse.Namespace, grouped_paths: dict[str, list[str]], steps: list[dict[str, object]]) -> str:
    mixed_scope = len([kind for kind in ("frontend", "backend") if grouped_paths.get(kind)]) > 1
    executable_steps, planning_only_steps = summarize_step_counts(steps)
    plan_decision = evaluate_plan_decision(
        flow="issue",
        grouped_paths=grouped_paths,
        target_paths=cleaned_items(args.target_path),
        executable_steps=executable_steps,
        planning_only_steps=planning_only_steps,
        goal="",
        user_story=args.user_story,
        symptom=args.symptom,
        expected=args.expected,
        actual=args.actual,
        in_scope=cleaned_items(args.in_scope),
        acceptance=cleaned_items(args.acceptance),
    )
    fix_lines = [
        f"首选定点修复: {args.preferred_fix.strip()}" if args.preferred_fix else "首选定点修复: 待补充",
        f"明确不采用的更大范围修复: {args.rejected_fix.strip()}" if args.rejected_fix else "明确不采用的更大范围修复: 待补充",
    ]
    fix_lines.extend(f"风险: {item}" for item in args.risk if item.strip())
    fix_lines.extend(f"决策说明: {item}" for item in plan_decision.get("reasons", []))
    return f"""---
doc_type: issue-analysis
artifact_class: {args.artifact_class}
issue: {directory_name}
status: draft
summary: {summary}
tags: []
---

# {summary} 分析

## 1. 根因

{yaml_list([
    f"当前假设归属: {'执行前由 Claude 先拆分' if mixed_scope or grouped_paths.get('shared') or grouped_paths.get('unknown') else owner_label(args.kind if args.kind != 'auto' else next(iter([k for k in ('frontend', 'backend') if grouped_paths.get(k)]), 'auto'))}",
    f'根因说明: {args.root_cause.strip()}' if args.root_cause else '根因说明: 待补充',
], 0, '待补充')}

## 2. 范围

{yaml_list(args.in_scope or [f"仅修改 `{path}`。" for path in args.target_path], 0, '待补充')}

## 3. 修复方案

{yaml_list(fix_lines, 0, '待补充')}

## 4. 依赖与假设

依赖:
{yaml_list(cleaned_items(args.dependency), 2, '待补充')}

假设:
{yaml_list(cleaned_items(args.assumption), 2, '待补充')}

## 5. 验证计划

{yaml_list(cleaned_items(args.validation), 0, '通过委派执行和 review 验证当前定点修复。')}

## 6. 回退计划

{yaml_list(cleaned_items(args.rollback), 0, '如果验证失败，只回退当前定点修复步骤。')}

## 7. 开放问题

{yaml_list(cleaned_items(args.open_question), 0, '当前无。')}

## 8. 计划步骤

{render_step_outline(steps)}
"""


def enrich_feature_artifacts(flow_dir: Path, slug: str, args: argparse.Namespace) -> list[str]:
    design_path = flow_dir / f"{slug}-design.md"
    checklist_path = flow_dir / f"{slug}-checklist.yaml"
    grouped_paths, route_notes = build_path_groups(args)
    acceptance = [item.strip() for item in args.acceptance if item.strip()]
    notes: list[str] = []
    steps = build_execution_steps(slug, "feature", grouped_paths, acceptance)
    executable_steps, planning_only_steps = summarize_step_counts(steps)
    plan_decision = evaluate_plan_decision(
        flow="feature",
        grouped_paths=grouped_paths,
        target_paths=cleaned_items(args.target_path),
        executable_steps=executable_steps,
        planning_only_steps=planning_only_steps,
        goal=args.goal,
        user_story=args.user_story,
        symptom="",
        expected="",
        actual="",
        in_scope=cleaned_items(args.in_scope),
        acceptance=cleaned_items(args.acceptance),
    )
    if plan_decision.get("planning_status") != "ready-for-build":
        steps = downgrade_steps_to_planning_only(
            steps,
            "当前规划输入仍不完整，在 CodeCGC 完成澄清前不要执行。",
        )

    if design_path.exists():
        design_path.write_text(
            render_feature_design_document(flow_dir.name, args.summary, args, grouped_paths, route_notes, steps),
            encoding="utf-8",
        )

    if checklist_path.exists():
        checklist_path.write_text(
            render_feature_checklist_steps(flow_dir.name, args.date, args.artifact_class, steps),
            encoding="utf-8",
        )
        executable_steps = sum(1 for step in steps if isinstance(step.get("codecgc"), dict))
        notes.append(f"已准备 {len(steps)} 个计划步骤，其中 {executable_steps} 个为可执行功能开发步骤。")
        if grouped_paths.get("shared"):
            notes.append("共享路径已保留为仅规划拆分步骤。")
        if grouped_paths.get("unknown"):
            notes.append("未知路由路径已保留为仅规划的路由确认步骤。")
    return notes


def summarize_step_counts(steps: list[dict[str, object]]) -> tuple[int, int]:
    executable_steps = sum(1 for step in steps if isinstance(step.get("codecgc"), dict))
    planning_only_steps = sum(1 for step in steps if not isinstance(step.get("codecgc"), dict))
    return executable_steps, planning_only_steps


def init_roadmap_from_plan(
    *,
    slug: str,
    summary: str,
    args: argparse.Namespace,
    grouped_paths: dict[str, list[str]],
    reasons: list[str],
) -> dict[str, Any]:
    command_args = [
        "--slug",
        slug,
        "--summary",
        summary,
        "--artifact-class",
        args.artifact_class,
        "--goal",
        args.goal or "TODO",
        "--user-story",
        args.user_story or "TODO",
    ]
    for item in cleaned_items(args.context):
        command_args.extend(["--context", item])
    for item in cleaned_items(args.in_scope):
        command_args.extend(["--in-scope", item])
    for item in cleaned_items(args.risk):
        command_args.extend(["--risk", item])
    for item in cleaned_items(args.dependency):
        command_args.extend(["--dependency", item])
    for item in cleaned_items(args.assumption):
        command_args.extend(["--assumption", item])
    for item in cleaned_items(args.validation):
        command_args.extend(["--validation", item])
    for item in cleaned_items(args.rollback):
        command_args.extend(["--rollback", item])
    for item in cleaned_items(args.open_question):
        command_args.extend(["--open-question", item])
    for item in reasons:
        command_args.extend(["--reason", item])
    for item in grouped_paths.get("frontend", []):
        command_args.extend(["--frontend-path", item])
    for item in grouped_paths.get("backend", []):
        command_args.extend(["--backend-path", item])
    for item in grouped_paths.get("shared", []):
        command_args.extend(["--shared-path", item])
    for item in grouped_paths.get("unknown", []):
        command_args.extend(["--unknown-path", item])
    if args.force:
        command_args.append("--force")
    return run_json_script("init_codecgc_roadmap.py", *command_args)


def expand_roadmap_children_from_plan(
    *,
    initiative: str,
    summary: str,
    args: argparse.Namespace,
    grouped_paths: dict[str, list[str]],
) -> dict[str, Any]:
    command_args = [
        "--initiative",
        initiative,
        "--summary",
        summary,
        "--artifact-class",
        args.artifact_class,
        "--source-flow",
        args.flow,
        "--goal",
        args.goal or "TODO",
        "--user-story",
        args.user_story or "TODO",
    ]
    if args.symptom:
        command_args.extend(["--symptom", args.symptom])
    if args.expected:
        command_args.extend(["--expected", args.expected])
    if args.actual:
        command_args.extend(["--actual", args.actual])
    if args.root_cause:
        command_args.extend(["--root-cause", args.root_cause])
    if args.preferred_fix:
        command_args.extend(["--preferred-fix", args.preferred_fix])
    if args.rejected_fix:
        command_args.extend(["--rejected-fix", args.rejected_fix])
    for item in cleaned_items(args.context):
        command_args.extend(["--context", item])
    for item in cleaned_items(args.in_scope):
        command_args.extend(["--in-scope", item])
    for item in cleaned_items(args.risk):
        command_args.extend(["--risk", item])
    for item in cleaned_items(args.dependency):
        command_args.extend(["--dependency", item])
    for item in cleaned_items(args.assumption):
        command_args.extend(["--assumption", item])
    for item in cleaned_items(args.validation):
        command_args.extend(["--validation", item])
    for item in cleaned_items(args.rollback):
        command_args.extend(["--rollback", item])
    for item in cleaned_items(args.open_question):
        command_args.extend(["--open-question", item])
    for item in cleaned_items(args.acceptance):
        command_args.extend(["--acceptance", item])
    for item in grouped_paths.get("frontend", []):
        command_args.extend(["--frontend-path", item])
    for item in grouped_paths.get("backend", []):
        command_args.extend(["--backend-path", item])
    if args.force:
        command_args.append("--force")
    return run_json_script("expand_codecgc_roadmap.py", *command_args)


def enrich_issue_artifacts(flow_dir: Path, slug: str, args: argparse.Namespace) -> list[str]:
    report_path = flow_dir / f"{slug}-report.md"
    analysis_path = flow_dir / f"{slug}-analysis.md"
    fix_path = flow_dir / f"{slug}-fix.yaml"
    grouped_paths, route_notes = build_path_groups(args)
    acceptance = [item.strip() for item in args.acceptance if item.strip()]
    notes: list[str] = []
    steps = build_execution_steps(slug, "issue", grouped_paths, acceptance)
    executable_steps, planning_only_steps = summarize_step_counts(steps)
    plan_decision = evaluate_plan_decision(
        flow="issue",
        grouped_paths=grouped_paths,
        target_paths=cleaned_items(args.target_path),
        executable_steps=executable_steps,
        planning_only_steps=planning_only_steps,
        goal="",
        user_story=args.user_story,
        symptom=args.symptom,
        expected=args.expected,
        actual=args.actual,
        in_scope=cleaned_items(args.in_scope),
        acceptance=cleaned_items(args.acceptance),
    )
    if plan_decision.get("planning_status") != "ready-for-fix":
        steps = downgrade_steps_to_planning_only(
            steps,
            "当前规划输入仍不完整，在 CodeCGC 完成澄清前不要执行。",
        )

    if report_path.exists():
        report_path.write_text(
            render_issue_report_document(flow_dir.name, args.summary, args, grouped_paths, route_notes, steps),
            encoding="utf-8",
        )

    if analysis_path.exists():
        analysis_path.write_text(
            render_issue_analysis_document(flow_dir.name, args.summary, args, grouped_paths, steps),
            encoding="utf-8",
        )

    if fix_path.exists():
        fix_path.write_text(
            render_issue_fix_steps(flow_dir.name, args.date, args.artifact_class, steps),
            encoding="utf-8",
        )
        executable_steps = sum(1 for step in steps if isinstance(step.get("codecgc"), dict))
        notes.append(f"已准备 {len(steps)} 个计划步骤，其中 {executable_steps} 个为可执行问题修复步骤。")
        if grouped_paths.get("shared"):
            notes.append("共享路径已保留为仅规划拆分步骤。")
        if grouped_paths.get("unknown"):
            notes.append("未知路由路径已保留为仅规划的路由确认步骤。")
    return notes


def main() -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()

    try:
        base_slug, artifact_slug = resolve_slug_pair(args.slug, args.date)

        route_before = run_json_script(
            "route_codecgc_workflow.py",
            "--flow",
            args.flow,
            "--slug",
            artifact_slug,
        )

        created = None
        notes: list[str] = []

        if should_create_scaffold(route_before):
            command_args = [
                "--flow",
                args.flow,
                "--slug",
                base_slug,
                "--summary",
                args.summary,
                "--date",
                args.date,
                "--kind",
                args.kind,
                "--artifact-class",
                args.artifact_class,
            ]
            for item in args.target_path:
                command_args.extend(["--target-path", item])
            if args.force:
                command_args.append("--force")

            created = run_json_script("init_codecgc_workflow.py", *command_args)
            if not created.get("success"):
                raise RuntimeError(str(created.get("error", "初始化工作流骨架失败。")))
            notes.append("已初始化最小工作流骨架。")
        elif scaffold_incomplete(route_before):
            if not args.force:
                result = {
                    "success": False,
                    "flow": args.flow,
                    "slug": artifact_slug,
                    "route": route_before,
                    "recommended_command": "cgc-plan",
                    "next": "请先修复现有工作流骨架，或使用 --force 重新覆盖缺失内容。",
                }
                print_json(result)
                return 1
            command_args = [
                "--flow",
                args.flow,
                "--slug",
                base_slug,
                "--summary",
                args.summary,
                "--date",
                args.date,
                "--kind",
                args.kind,
                "--artifact-class",
                args.artifact_class,
                "--force",
            ]
            for item in args.target_path:
                command_args.extend(["--target-path", item])
            created = run_json_script("init_codecgc_workflow.py", *command_args)
            if not created.get("success"):
                raise RuntimeError(str(created.get("error", "修复工作流骨架失败。")))
            notes.append("已通过强制覆盖修复工作流骨架。")

        flow_dir = (
            Path(created["directory"])
            if created and created.get("directory")
            else flow_root(args.flow, args.artifact_class) / artifact_slug
        )
        if args.flow == "feature":
            notes.extend(enrich_feature_artifacts(flow_dir, base_slug, args))
        else:
            notes.extend(enrich_issue_artifacts(flow_dir, base_slug, args))
        notes.append("已将结构化规划提示写入工作流产物。")

        grouped_paths, _ = build_path_groups(args)
        acceptance = cleaned_items(args.acceptance)
        in_scope = cleaned_items(args.in_scope)
        steps = build_execution_steps(base_slug, args.flow, grouped_paths, acceptance)
        executable_steps, planning_only_steps = summarize_step_counts(steps)
        plan_decision = evaluate_plan_decision(
            flow=args.flow,
            grouped_paths=grouped_paths,
            target_paths=cleaned_items(args.target_path),
            executable_steps=executable_steps,
            planning_only_steps=planning_only_steps,
            goal=args.goal,
            user_story=args.user_story,
            symptom=args.symptom,
            expected=args.expected,
            actual=args.actual,
            in_scope=in_scope,
            acceptance=acceptance,
        )
        roadmap_result = None
        roadmap_children = None
        if plan_decision.get("planning_status") == "needs-roadmap":
            roadmap_result = init_roadmap_from_plan(
                slug=artifact_slug,
                summary=args.summary,
                args=args,
                grouped_paths=grouped_paths,
                reasons=[str(item) for item in plan_decision.get("reasons", [])],
            )
            if roadmap_result.get("success"):
                notes.append("已为这条更大范围的请求初始化 roadmap 骨架。")
                roadmap_children = expand_roadmap_children_from_plan(
                    initiative=artifact_slug,
                    summary=args.summary,
                    args=args,
                    grouped_paths=grouped_paths,
                )
                if roadmap_children.get("success"):
                    notes.append("已根据 roadmap 分轨初始化子工作流骨架。")

        route_after = run_json_script(
            "route_codecgc_workflow.py",
            "--flow",
            args.flow,
            "--slug",
            artifact_slug,
        )

        result = {
            "success": True,
            "flow": args.flow,
            "slug": artifact_slug,
            "created": created is not None,
            "init": created,
            "planning_status": plan_decision.get("planning_status", ""),
            "planning_reasons": plan_decision.get("reasons", []),
            "planning_missing_fields": plan_decision.get("missing_fields", []),
            "roadmap": roadmap_result,
            "roadmap_children": roadmap_children,
            "route": route_after,
            "recommended_command": plan_decision.get("recommended_command") or route_after.get("recommended_command", ""),
            "next": plan_decision.get("next") or route_after.get("next", ""),
            "notes": notes,
        }
    except Exception as error:
        print_json({"success": False, "error": str(error)}, file=sys.stderr)
        return 1

    print_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
