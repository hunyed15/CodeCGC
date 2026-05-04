from __future__ import annotations

from typing import Any

from codecgc_command_surface import to_public_command


def evaluate_plan_decision(
    *,
    flow: str,
    grouped_paths: dict[str, list[str]],
    target_paths: list[str],
    executable_steps: int,
    planning_only_steps: int,
    goal: str,
    user_story: str,
    symptom: str,
    expected: str,
    actual: str,
    in_scope: list[str],
    acceptance: list[str],
) -> dict[str, Any]:
    clarification_reasons: list[str] = []
    roadmap_reasons: list[str] = []
    missing_fields: list[str] = []

    if not target_paths:
        clarification_reasons.append("尚未提供目标路径。")
        missing_fields.append("target_paths")

    if grouped_paths.get("unknown"):
        clarification_reasons.append("部分目标路径尚未被 model-routing.yaml 覆盖。")
        missing_fields.append("routing_coverage")

    if planning_only_steps > 0:
        clarification_reasons.append("在执行开始前，仍有仅规划 step 需要先处理。")
        missing_fields.append("planning_blockers")

    if executable_steps < 1:
        clarification_reasons.append("当前还没有准备好可执行的单归属 step。")
        missing_fields.append("executable_step")

    if flow == "feature":
        if not goal.strip():
            clarification_reasons.append("功能目标仍未补齐。")
            missing_fields.append("goal")
        if not user_story.strip():
            clarification_reasons.append("用户故事仍未补齐。")
            missing_fields.append("user_story")
    else:
        if not symptom.strip():
            clarification_reasons.append("问题现象仍未补齐。")
            missing_fields.append("symptom")
        if not expected.strip():
            clarification_reasons.append("预期行为仍未补齐。")
            missing_fields.append("expected")
        if not actual.strip():
            clarification_reasons.append("实际行为仍未补齐。")
            missing_fields.append("actual")

    if not in_scope:
        clarification_reasons.append("范围内行为仍不明确。")
        missing_fields.append("in_scope")

    if not acceptance:
        clarification_reasons.append("验收条件仍未补齐。")
        missing_fields.append("acceptance")

    if executable_steps >= 3:
        roadmap_reasons.append("当前计划已经跨越 3 个或以上可执行 step。")

    if len(target_paths) >= 6:
        roadmap_reasons.append("当前计划涉及的目标路径过多，已经超出单个 feature 级流转的合理范围。")

    if grouped_paths.get("frontend") and grouped_paths.get("backend") and planning_only_steps > 0:
        roadmap_reasons.append("跨前后端边界的工作仍需要更高层级的拆分。")

    if roadmap_reasons:
        return {
            "planning_status": "needs-roadmap",
            "recommended_command": to_public_command("cgc-plan"),
            "next": "需要先在 roadmap 层完成拆分，再继续进入可执行的 feature 或 issue step。",
            "reasons": roadmap_reasons,
            "missing_fields": [],
        }

    if clarification_reasons:
        return {
            "planning_status": "needs-clarification",
            "recommended_command": to_public_command("cgc-plan"),
            "next": "需要先补齐缺失的规划信息，或先解决仅规划阻塞项，再进入执行。",
            "reasons": clarification_reasons,
            "missing_fields": missing_fields,
        }

    ready_command = "cgc-build" if flow == "feature" else "cgc-fix"
    return {
        "planning_status": "ready-for-build" if flow == "feature" else "ready-for-fix",
        "recommended_command": to_public_command(ready_command),
        "next": "当前待执行 step 已满足委派执行条件。",
        "reasons": ["当前规划信息与 step 归属已经足以进入执行。"],
        "missing_fields": [],
    }
