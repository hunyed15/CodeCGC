from __future__ import annotations

from typing import Any

from codecgc_command_surface import matches_command
from codecgc_command_surface import to_public_command


def extract_execution_result(execution: dict[str, Any]) -> dict[str, Any]:
    result = execution.get("result", {}) if isinstance(execution, dict) else {}
    if not isinstance(result, dict):
        return {}
    nested = result.get("result")
    if isinstance(nested, dict):
        return nested
    return result


def execution_is_ready_for_review(execution: dict[str, Any]) -> bool:
    if not bool(execution.get("success")):
        return False

    mode = str(execution.get("mode", "")).strip().lower()
    result = extract_execution_result(execution)
    policy_checks = result.get("policy_checks", [])
    risks = result.get("risks", [])
    if not isinstance(policy_checks, list):
        policy_checks = []
    if not isinstance(risks, list):
        risks = []

    return (
        mode != "dry-run"
        and "dry_run_only" not in {str(item) for item in policy_checks}
        and "execution_not_performed" not in {str(item) for item in risks}
        and bool(result.get("success"))
        and str(result.get("outcome", "")).strip().lower() == "done"
    )


def build_not_ready_result(flow: str, slug: str, route: dict[str, Any], expected_command: str) -> dict[str, Any]:
    public_expected_command = to_public_command(expected_command)
    flow_label = "测试执行" if expected_command == "cgc-test" else "功能开发" if flow == "feature" else "问题修复" if flow == "issue" else "当前"
    result = {
        "success": False,
        "flow": flow,
        "slug": slug,
        "state": "not-ready",
        "failure_type": "workflow-state",
        "route": route,
        "error": f"{flow_label}工作流当前还未满足 {public_expected_command} 的执行条件。",
        "recommended_command": to_public_command(route.get("recommended_command", "cgc-plan")),
        "next": route.get("next", "请先修复当前工作流产物与状态，再继续执行。"),
    }
    split_suggestion = route.get("split_suggestion", {}) if isinstance(route.get("split_suggestion"), dict) else {}
    replan_payload = route.get("replan_payload", {}) if isinstance(route.get("replan_payload"), dict) else {}
    if split_suggestion:
        result["split_suggestion"] = split_suggestion
    if replan_payload:
        result["replan_payload"] = replan_payload
    return result


def classify_execution_failure(execution: dict[str, Any]) -> tuple[str, str, str, str]:
    result = extract_execution_result(execution)
    outcome = str(result.get("outcome", "")).strip().lower()
    error_text = str(result.get("error", "") or execution.get("error", "")).strip()
    summary_text = str(result.get("summary", "")).strip()
    combined = f"{outcome}\n{error_text}\n{summary_text}".lower()
    target_missing_markers = [
        "target file path does not exist",
        "target directory path does not exist",
        "does not exist in the current workspace",
        "current workspace",
        "当前工作区中不存在目标文件",
        "目标文件路径在当前工作区下不存在",
        "在当前工作区里不存在",
        "工作区里没有",
        "目标文件路径在当前工作区里对不上",
        "目标文件缺失",
        "没有可实施对象",
        "目标文件本身缺失",
        "提供正确文件路径",
        "恢复到工作区",
    ]

    if outcome == "split-required" or "split the task first" in combined:
        return (
            "returned-to-planning",
            "scope-error",
            "cgc-plan",
            "请先按执行器归属或路径范围拆分当前步骤，再重新生成更窄的可执行契约。",
        )

    if outcome == "design-gap" or "not covered by model-routing.yaml" in combined:
        return (
            "returned-to-planning",
            "design-gap",
            "cgc-plan",
            "请先修正路由规则、目标路径或步骤契约，再重新尝试执行。",
        )

    if any(marker in combined for marker in target_missing_markers):
        return (
            "returned-to-planning",
            "design-gap",
            "cgc-plan",
            "当前步骤引用的目标路径在工作区中不存在，请先回到 cgc-plan 修正目标路径或步骤契约。",
        )

    if outcome == "blocked" or "timeout" in combined or "does not exist" in combined:
        return (
            "blocked",
            "environment-or-tooling",
            "",
            "请先修复缺失产物、执行器环境或超时条件，再重试当前步骤。",
        )

    return (
        "blocked",
        "executor-failure",
        "",
        "请先检查审计产物和执行器输出，修复执行器侧失败后再重试。",
    )


def build_split_scope_replan_payload(flow: str, slug: str, execution: dict[str, Any]) -> dict[str, Any]:
    result = extract_execution_result(execution)
    split_suggestion = result.get("split_suggestion", {}) if isinstance(result.get("split_suggestion"), dict) else {}
    if not split_suggestion:
        return {}

    grouped_paths = split_suggestion.get("grouped_paths", {}) if isinstance(split_suggestion.get("grouped_paths"), dict) else {}
    path_classification = split_suggestion.get("path_classification", {}) if isinstance(split_suggestion.get("path_classification"), dict) else {}
    suggested_steps = split_suggestion.get("suggested_split_steps", []) if isinstance(split_suggestion.get("suggested_split_steps"), list) else []

    payload: dict[str, Any] = {
        "flow": flow,
        "slug": slug,
        "kind": "auto",
        "split_scope": True,
        "path_classification": path_classification,
        "grouped_paths": grouped_paths,
        "suggested_split_steps": suggested_steps,
    }

    combined_paths: list[str] = []
    for key in ("frontend", "backend", "shared"):
        value = grouped_paths.get(key, [])
        if isinstance(value, list):
            combined_paths.extend(str(item).strip() for item in value if str(item).strip())
    if combined_paths:
        payload["target_paths"] = combined_paths

    in_scope: list[str] = []
    for item in suggested_steps:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind", "")).strip()
        paths = [str(path).strip() for path in item.get("target_paths", []) if str(path).strip()]
        if not paths:
            continue
        if kind == "planning":
            in_scope.append(f"先拆分 shared 路径：{', '.join(paths)}。")
        else:
            in_scope.append(f"将 {kind} 范围拆成独立步骤：{', '.join(paths)}。")
    if in_scope:
        payload["in_scope"] = in_scope

    return payload


def build_execution_result(
    *,
    flow: str,
    slug: str,
    route: dict[str, Any],
    execution: dict[str, Any],
) -> dict[str, Any]:
    success = bool(execution.get("success"))
    audit = execution.get("audit", {}) if isinstance(execution, dict) else {}
    audit_path = audit.get("path", "") if isinstance(audit, dict) else ""
    result = extract_execution_result(execution)

    if execution_is_ready_for_review(execution):
        return {
            "success": True,
            "flow": flow,
            "slug": slug,
            "state": "ready-for-review",
            "failure_type": "",
            "route": route,
            "execution": execution,
            "audit_path": audit_path,
            "recommended_command": to_public_command("cgc-review"),
            "next": "请检查执行审计结果，并写回通过或修复决策。",
            "summary": result.get("summary", ""),
        }

    if success:
        retry_command = "cgc-test" if matches_command(str(route.get("recommended_command", "")).strip(), "cgc-test") else f"cgc-{'build' if flow == 'feature' else 'fix'}"
        return {
            "success": False,
            "flow": flow,
            "slug": slug,
            "state": "executed-dry-run",
            "failure_type": "workflow-state",
            "route": route,
            "execution": execution,
            "audit_path": audit_path,
            "recommended_command": to_public_command(retry_command),
            "next": "请去掉 --dry-run 后重新执行同一步骤，再发起审核。",
            "summary": result.get("summary", ""),
            "error": "",
        }

    state, failure_type, recommended_command, next_step = classify_execution_failure(execution)
    return {
        "success": False,
        "flow": flow,
        "slug": slug,
        "state": state,
        "failure_type": failure_type,
        "route": route,
        "execution": execution,
        "audit_path": audit_path,
        "recommended_command": to_public_command(recommended_command),
        "next": next_step,
        "summary": result.get("summary", ""),
        "error": result.get("error", "") or execution.get("error", ""),
        "split_suggestion": result.get("split_suggestion", {}),
        "replan_payload": build_split_scope_replan_payload(flow, slug, execution) if failure_type == "scope-error" else {},
    }
