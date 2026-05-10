import argparse
import json
import re
from pathlib import Path
from typing import Any

from build_codecgc_task import build_split_required_payload
from build_codecgc_task import load_checklist_yaml
from build_codecgc_task import load_simple_routing_config
from codecgc_artifact_roots import discover_flow_directory
from codecgc_artifact_roots import execution_root
from codecgc_artifact_roots import normalize_artifact_class
from codecgc_command_surface import to_public_command
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_path_contract import normalize_persisted_project_path
from codecgc_routing_paths import resolve_active_routing_file
from codecgc_runtime_paths import PACKAGE_ROOT
from codecgc_step_control import is_test_codecgc_block
from codecgc_step_control import get_step_metadata
from codecgc_step_control import select_next_executable_step

WORKSPACE = PACKAGE_ROOT
ROUTING_FILE = resolve_active_routing_file()


def display_path(path: Path | None) -> str:
    return normalize_persisted_project_path(path) if path else ""


def attach_route_summary(result: dict[str, Any]) -> dict[str, Any]:
    review = result.get("review", {}) if isinstance(result.get("review"), dict) else {}
    current_step = result.get("current_step", {}) if isinstance(result.get("current_step"), dict) else {}
    recommended_command = str(result.get("recommended_command", "")).strip()
    next_text = str(result.get("next", "")).strip()
    human_summary = str(result.get("reason", "")).strip() or next_text
    workflow_state = "closed" if not recommended_command and result.get("success") else ""
    if recommended_command == "cgc-plan":
        workflow_state = "needs-planning"
    elif recommended_command == "cgc-build":
        workflow_state = "awaiting-build"
    elif recommended_command == "cgc-fix":
        workflow_state = "awaiting-fix"
    elif recommended_command == "cgc-review":
        workflow_state = "awaiting-review"
    elif current_step:
        workflow_state = "step-selected"

    result["summary"] = {
        "human_summary": human_summary,
        "recommended_command": recommended_command,
        "next": next_text,
        "workflow_state": workflow_state,
        "current_step_number": int(current_step.get("step_number", 0) or 0),
        "current_task_id": str(current_step.get("task_id", "")).strip(),
        "review_decision": str(review.get("decision", "")).strip(),
        "is_closed": workflow_state == "closed",
    }
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Route an existing CodeCGC feature or issue artifact directory to the recommended next command."
    )
    parser.add_argument("--flow", required=True, choices=["feature", "issue"])
    parser.add_argument("--slug", required=True)
    return parser


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def find_artifact_file(directory: Path, suffix: str) -> Path | None:
    matches = sorted(directory.glob(f"*{suffix}"))
    return matches[0] if matches else None


def checklist_has_codecgc_step(path: Path) -> bool:
    text = load_text(path)
    return "codecgc:" in text and "steps:" in text


def checklist_has_planning_step(path: Path) -> bool:
    text = load_text(path)
    return "planning_note:" in text or "owner_hint: Claude planning" in text


def extract_task_ids(path: Path) -> list[str]:
    task_ids: list[str] = []
    pattern = re.compile(r"^\s*task_id:\s*(.+?)\s*$")
    for line in load_text(path).splitlines():
        match = pattern.match(line)
        if not match:
            continue
        task_id = match.group(1).strip().strip("\"'")
        if task_id:
            task_ids.append(task_id)
    return task_ids


def first_pending_step_is_not_executable(path: Path) -> tuple[bool, dict[str, Any] | None]:
    data = load_text(path)
    if "steps:" not in data:
        return False, None

    try:
        checklist_data = load_checklist_yaml(path)
    except Exception:
        return False, None

    steps = checklist_data.get("steps", [])
    if not isinstance(steps, list) or not steps:
        return False, None

    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        status = str(step.get("status", "pending")).strip().lower()
        if status not in {"pending", ""}:
            continue
        try:
            metadata = get_step_metadata(path, index)
        except Exception:
            return False, None
        if metadata.get("executable"):
            return False, metadata
        return True, metadata

    return False, None


def build_route_scope_split_payload(step: dict[str, Any]) -> dict[str, Any]:
    kind = str(step.get("kind", "")).strip().lower()
    target_paths = step.get("target_paths", [])
    if kind != "auto" or not isinstance(target_paths, list) or not target_paths:
        return {}

    normalized_paths = [str(path).strip().replace("\\", "/") for path in target_paths if str(path).strip()]
    if not normalized_paths:
        return {}

    routing = load_simple_routing_config(ROUTING_FILE)
    payload = build_split_required_payload(normalized_paths, routing)
    grouped_paths = payload.get("grouped_paths", {}) if isinstance(payload.get("grouped_paths"), dict) else {}
    has_shared = bool(grouped_paths.get("shared"))
    has_frontend = bool(grouped_paths.get("frontend"))
    has_backend = bool(grouped_paths.get("backend"))
    if not (has_shared or (has_frontend and has_backend)):
        return {}

    in_scope: list[str] = []
    for item in payload.get("suggested_split_steps", []):
        if not isinstance(item, dict):
            continue
        item_kind = str(item.get("kind", "")).strip()
        paths = [str(path).strip() for path in item.get("target_paths", []) if str(path).strip()]
        if not paths:
            continue
        if item_kind == "planning":
            in_scope.append(f"先拆分 shared 路径：{', '.join(paths)}。")
        else:
            in_scope.append(f"将 {item_kind} 范围拆成独立步骤：{', '.join(paths)}。")

    return {
        "split_suggestion": payload,
        "replan_payload": {
            "kind": "auto",
            "split_scope": True,
            "target_paths": normalized_paths,
            "path_classification": payload.get("path_classification", {}),
            "grouped_paths": grouped_paths,
            "suggested_split_steps": payload.get("suggested_split_steps", []),
            "in_scope": in_scope,
        },
    }


def find_audit_for_task_id(task_id: str, artifact_class: str) -> tuple[Path | None, dict[str, Any] | None]:
    if not task_id:
        return None, None
    audit_path = execution_root(artifact_class) / f"{task_id}.json"
    audit = load_json(audit_path)
    if not audit:
        return None, None
    return audit_path, audit


def parse_review_metadata(markdown: str) -> dict[str, Any]:
    text = str(markdown or "")
    decision_match = re.search(
        r"## [45]\. (?:Review Decision|审核结论)\s+[\r\n]+- (?:审核结果:\s*)?(accepted|changes-requested|通过|需修改)",
        text,
    )
    if not decision_match:
        decision_match = re.search(r"- (?:Final decision|最终决策): (accepted|changes-requested|通过|需修改)", text)
    if not decision_match:
        decision_match = re.search(
            r"-\s*(?:Review decision|审核决策|审核结果|ç€¹â„ƒç‰³éå´‡ç“¥):\s*(accepted|changes-requested|通过|需修改)",
            text,
            flags=re.IGNORECASE,
        )
    task_match = re.search(r"- (?:Reviewed task_id|审核 task_id): (.+)", text)
    step_match = re.search(r"- (?:Reviewed step_number|审核 step_number|审核步骤序号): (\d+)", text)
    if not step_match:
        step_match = re.search(
            r"-\s*(?:Reviewed step_number|审核 step_number|审核步骤序号|ç€¹â„ƒç‰³å§ãƒ©î€ƒæ´å¿“å½¿):\s*(\d+)",
            text,
            flags=re.IGNORECASE,
        )
    action_kind_match = re.search(r"- (?:Review action kind|审核动作类型): (.+)", text)
    fallback_stage_match = re.search(r"- (?:Review fallback stage|审核回退阶段): (.+)", text)
    policy_reason_match = re.search(r"- (?:Review policy reason|审核策略原因): (.+)", text)
    raw_decision = decision_match.group(1).strip() if decision_match else ""
    decision = {"通过": "accepted", "需修改": "changes-requested"}.get(raw_decision, raw_decision)
    return {
        "decision": decision,
        "task_id": task_match.group(1).strip() if task_match else "",
        "step_number": int(step_match.group(1)) if step_match else 0,
        "action_kind": action_kind_match.group(1).strip() if action_kind_match else "",
        "fallback_stage": fallback_stage_match.group(1).strip() if fallback_stage_match else "",
        "policy_reason": policy_reason_match.group(1).strip() if policy_reason_match else "",
    }


def extract_review_metadata(path: Path) -> dict[str, Any]:
    return parse_review_metadata(load_text(path))


def review_matches_step(review: dict[str, Any], step: dict[str, Any]) -> bool:
    return (
        str(review.get("task_id", "")) == str(step.get("task_id", ""))
        and int(review.get("step_number", 0) or 0) == int(step.get("step_number", 0) or 0)
    )


def audit_is_ready_for_review(audit: dict[str, Any], step: dict[str, Any]) -> bool:
    result = audit.get("result", {}) if isinstance(audit.get("result"), dict) else {}
    source = audit.get("source", {}) if isinstance(audit.get("source"), dict) else {}
    policy_checks = result.get("policy_checks", [])
    risks = result.get("risks", [])
    if not isinstance(policy_checks, list):
        policy_checks = []
    if not isinstance(risks, list):
        risks = []

    return (
        str(audit.get("task_id", "")) == str(step.get("task_id", ""))
        and int(source.get("step_number", 0) or 0) == int(step.get("step_number", 0) or 0)
        and str(audit.get("mode", "")) != "dry-run"
        and "dry_run_only" not in {str(item) for item in policy_checks}
        and "execution_not_performed" not in {str(item) for item in risks}
        and bool(result.get("success"))
        and str(result.get("outcome", "")) == "done"
    )


def route_feature(slug: str) -> dict[str, Any]:
    discovered = discover_flow_directory("feature", slug, "auto")
    if not discovered:
        return {
            "success": False,
            "flow": "feature",
            "slug": slug,
            "recommended_command": "cgc-plan",
            "reason": "Feature 工作流目录尚不存在。",
            "next": "先初始化该 feature 的工作流骨架。",
        }
    artifact_class, directory = discovered

    design = find_artifact_file(directory, "-design.md")
    checklist = find_artifact_file(directory, "-checklist.yaml")
    acceptance = find_artifact_file(directory, "-acceptance.md")

    if not design or not checklist or not acceptance:
        return {
            "success": False,
            "flow": "feature",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "recommended_command": "cgc-plan",
            "reason": "当前功能开发工作流骨架不完整。",
            "next": "补齐或修复缺失的功能开发产物文件。",
        }

    if not checklist_has_codecgc_step(checklist):
        return {
            "success": False,
            "flow": "feature",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "recommended_command": "cgc-plan",
            "reason": "当前功能开发工作流已存在，但还不可执行。",
            "next": "继续细化设计，并补上有效的 CodeCGC 步骤契约。",
        }

    if checklist_has_planning_step(checklist):
        return {
            "success": False,
            "flow": "feature",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "recommended_command": "cgc-plan",
            "reason": "当前功能开发清单里仍然存在仅规划用途的拆分或路由确认步骤。",
            "next": "先完成必须的拆分或路由澄清，再执行剩余的限定范围步骤。",
        }

    blocked_first_step, first_step = first_pending_step_is_not_executable(checklist)
    if blocked_first_step:
        result = {
            "success": False,
            "flow": "feature",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "recommended_command": "cgc-plan",
            "reason": "当前功能开发清单仍以不可执行的占位步骤开头。",
            "next": "先澄清范围、归属和目标路径，再尝试执行该功能开发工作流。",
            "current_step": {
                "step_number": int(first_step.get("step_number", 0) or 0),
                "task_id": str(first_step.get("task_id", "")),
                "kind": str(first_step.get("kind", "")),
                "target_paths": first_step.get("target_paths", []),
                "task_summary": str(first_step.get("task_summary", "")),
            },
        }
        split_payload = build_route_scope_split_payload(first_step or {})
        if split_payload:
            result["reason"] = "当前功能开发步骤混合了前后端或 shared 范围，必须先拆分后才能执行。"
            result["next"] = "先回到 cgc-plan，按拆分建议把当前步骤改写成纯 frontend 或纯 backend 步骤，再继续执行。"
            result.update(split_payload)
        return result

    try:
        next_step = select_next_executable_step(checklist)
    except Exception:
        next_step = None

    review = extract_review_metadata(acceptance)

    if next_step is None:
        if review.get("decision") == "accepted":
            return {
                "success": True,
                "flow": "feature",
                "slug": slug,
                "artifact_class": artifact_class,
                "directory": display_path(directory),
                "review": review,
                "current_step": None,
                "audit_path": "",
                "recommended_command": "",
                "reason": "当前功能开发工作流已通过审核，且没有剩余待执行步骤。",
                "next": "当前功能开发工作流已关闭，除非后续新增新的跟进步骤。",
            }
        return {
            "success": True,
            "flow": "feature",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "review": review,
            "current_step": None,
            "audit_path": "",
            "recommended_command": "",
            "reason": "当前功能开发工作流已没有剩余待执行步骤。",
            "next": "请检查该工作流是否应关闭，或是否需要规划新的跟进步骤。",
        }

    audit_path, audit = find_audit_for_task_id(str(next_step.get("task_id", "")), artifact_class)
    review_for_current_step = review_matches_step(review, next_step)
    current_step = {
        "step_number": int(next_step.get("step_number", 0) or 0),
        "task_id": str(next_step.get("task_id", "")),
        "kind": str(next_step.get("kind", "")),
        "step_type": str(next_step.get("step_type", "")),
        "target_paths": next_step.get("target_paths", []),
        "task_summary": str(next_step.get("task_summary", "")),
    }
    if is_test_codecgc_block(
        {
            "kind": current_step["kind"],
            "task_id": current_step["task_id"],
            "task_summary": current_step["task_summary"],
            "target_paths": current_step["target_paths"],
            "step_type": current_step["step_type"] or ("test" if "-test-step-" in current_step["task_id"] else ""),
        }
    ):
        return {
            "success": True,
            "flow": "feature",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "review": review,
            "current_step": current_step,
            "audit_path": display_path(audit_path),
            "recommended_command": "cgc-test",
            "reason": "当前功能开发工作流正在等待测试步骤执行。",
            "next": "执行当前测试步骤。",
        }

    if (
        review_for_current_step
        and review.get("decision") == "changes-requested"
        and not (audit and audit_is_ready_for_review(audit, next_step))
    ):
        return {
            "success": True,
            "flow": "feature",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "review": review,
            "current_step": current_step,
            "audit_path": display_path(audit_path),
            "recommended_command": "cgc-build",
            "reason": "当前功能开发步骤在审核后仍需继续补充修改。",
            "next": "完成要求的后续修改后，重新执行当前功能开发步骤。",
        }

    if audit:
        if audit_is_ready_for_review(audit, next_step):
            return {
                "success": True,
                "flow": "feature",
                "slug": slug,
                "artifact_class": artifact_class,
                "directory": display_path(directory),
                "review": review,
                "current_step": current_step,
                "audit_path": display_path(audit_path),
                "recommended_command": "cgc-review",
                "reason": "当前功能开发步骤已有执行证据，但还没有对应的审核结论。",
                "next": f"审核最新审计产物 {audit_path}，并回写验收结论。",
            }
        return {
            "success": True,
            "flow": "feature",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "review": review,
            "current_step": current_step,
            "audit_path": display_path(audit_path),
            "recommended_command": "cgc-build",
            "reason": "当前功能开发步骤还没有“通过”审核结论。",
            "next": "执行或继续推进当前待执行的功能开发步骤。",
        }

    return {
        "success": True,
        "flow": "feature",
        "slug": slug,
        "artifact_class": artifact_class,
        "directory": display_path(directory),
        "review": review,
        "current_step": current_step,
        "audit_path": "",
        "recommended_command": "cgc-build",
        "reason": "当前功能开发清单已包含可执行步骤元数据，但还没有执行审计。",
        "next": "执行当前功能开发步骤。",
    }


def route_issue(slug: str) -> dict[str, Any]:
    discovered = discover_flow_directory("issue", slug, "auto")
    if not discovered:
        return {
            "success": False,
            "flow": "issue",
            "slug": slug,
            "recommended_command": "cgc-plan",
            "reason": "Issue 工作流目录尚不存在。",
            "next": "先初始化该 issue 的工作流骨架。",
        }
    artifact_class, directory = discovered

    report = find_artifact_file(directory, "-report.md")
    analysis = find_artifact_file(directory, "-analysis.md")
    fix = find_artifact_file(directory, "-fix.yaml")
    fix_note = find_artifact_file(directory, "-fix-note.md")

    if not report or not analysis or not fix or not fix_note:
        return {
            "success": False,
            "flow": "issue",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "recommended_command": "cgc-plan",
            "reason": "Issue 工作流骨架不完整。",
            "next": "补齐或修复缺失的 issue 产物文件。",
        }

    if not checklist_has_codecgc_step(fix):
        return {
            "success": False,
            "flow": "issue",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "recommended_command": "cgc-plan",
            "reason": "当前问题修复工作流已存在，但还不可执行。",
            "next": "继续细化修复范围，并补上有效的 CodeCGC 步骤契约。",
        }

    if checklist_has_planning_step(fix):
        return {
            "success": False,
            "flow": "issue",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "recommended_command": "cgc-plan",
            "reason": "当前问题修复清单里仍然存在仅规划用途的拆分或路由确认步骤。",
            "next": "先完成必须的拆分或路由澄清，再执行剩余的限定范围修复步骤。",
        }

    blocked_first_step, first_step = first_pending_step_is_not_executable(fix)
    if blocked_first_step:
        result = {
            "success": False,
            "flow": "issue",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "recommended_command": "cgc-plan",
            "reason": "当前问题修复清单仍以不可执行的占位步骤开头。",
            "next": "先澄清修复范围、归属和目标路径，再尝试执行该问题修复工作流。",
            "current_step": {
                "step_number": int(first_step.get("step_number", 0) or 0),
                "task_id": str(first_step.get("task_id", "")),
                "kind": str(first_step.get("kind", "")),
                "target_paths": first_step.get("target_paths", []),
                "task_summary": str(first_step.get("task_summary", "")),
            },
        }
        split_payload = build_route_scope_split_payload(first_step or {})
        if split_payload:
            result["reason"] = "当前问题修复步骤混合了前后端或 shared 范围，必须先拆分后才能执行。"
            result["next"] = "先回到 cgc-plan，按拆分建议把当前修复步骤改写成纯 frontend 或纯 backend 步骤，再继续执行。"
            result.update(split_payload)
        return result

    try:
        next_step = select_next_executable_step(fix)
    except Exception:
        next_step = None

    review = extract_review_metadata(fix_note)

    if next_step is None:
        if review.get("decision") == "accepted":
            return {
                "success": True,
                "flow": "issue",
                "slug": slug,
                "artifact_class": artifact_class,
                "directory": display_path(directory),
                "review": review,
                "current_step": None,
                "audit_path": "",
                "recommended_command": "",
                "reason": "当前问题修复工作流已通过审核，且没有剩余待执行步骤。",
                "next": "当前问题修复工作流已关闭，除非后续新增新的跟进修复步骤。",
            }
        return {
            "success": True,
            "flow": "issue",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "review": review,
            "current_step": None,
            "audit_path": "",
            "recommended_command": "",
            "reason": "当前问题修复工作流已没有剩余待执行步骤。",
            "next": "请检查该工作流是否应关闭，或是否需要规划新的跟进修复步骤。",
        }

    audit_path, audit = find_audit_for_task_id(str(next_step.get("task_id", "")), artifact_class)
    review_for_current_step = review_matches_step(review, next_step)
    current_step = {
        "step_number": int(next_step.get("step_number", 0) or 0),
        "task_id": str(next_step.get("task_id", "")),
        "kind": str(next_step.get("kind", "")),
        "step_type": str(next_step.get("step_type", "")),
        "target_paths": next_step.get("target_paths", []),
        "task_summary": str(next_step.get("task_summary", "")),
    }
    if is_test_codecgc_block(
        {
            "kind": current_step["kind"],
            "task_id": current_step["task_id"],
            "task_summary": current_step["task_summary"],
            "target_paths": current_step["target_paths"],
            "step_type": current_step["step_type"] or ("test" if "-test-step-" in current_step["task_id"] else ""),
        }
    ):
        return {
            "success": True,
            "flow": "issue",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "review": review,
            "current_step": current_step,
            "audit_path": display_path(audit_path),
            "recommended_command": "cgc-test",
            "reason": "当前问题修复工作流正在等待测试步骤执行。",
            "next": "执行当前测试步骤。",
        }

    if (
        review_for_current_step
        and review.get("decision") == "changes-requested"
        and not (audit and audit_is_ready_for_review(audit, next_step))
    ):
        return {
            "success": True,
            "flow": "issue",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "review": review,
            "current_step": current_step,
            "audit_path": display_path(audit_path),
            "recommended_command": "cgc-fix",
            "reason": "当前问题修复步骤在审核后仍需继续补充修改。",
            "next": "完成要求的后续修复后，重新执行当前问题修复步骤。",
        }

    if audit:
        if audit_is_ready_for_review(audit, next_step):
            return {
                "success": True,
                "flow": "issue",
                "slug": slug,
                "artifact_class": artifact_class,
                "directory": display_path(directory),
                "review": review,
                "current_step": current_step,
                "audit_path": display_path(audit_path),
                "recommended_command": "cgc-review",
                "reason": "当前问题修复步骤已有执行证据，但还没有对应的审核结论。",
                "next": f"审核最新审计产物 {audit_path}，并回写修复结论。",
            }
        return {
            "success": True,
            "flow": "issue",
            "slug": slug,
            "artifact_class": artifact_class,
            "directory": display_path(directory),
            "review": review,
            "current_step": current_step,
            "audit_path": display_path(audit_path),
            "recommended_command": "cgc-fix",
            "reason": "当前问题修复步骤还没有“通过”审核结论。",
            "next": "执行或继续推进当前待执行的问题修复步骤。",
        }

    return {
        "success": True,
        "flow": "issue",
        "slug": slug,
        "artifact_class": artifact_class,
        "directory": display_path(directory),
        "review": review,
        "current_step": current_step,
        "audit_path": "",
        "recommended_command": "cgc-fix",
        "reason": "当前问题修复产物已包含可执行步骤元数据，但还没有执行审计。",
        "next": "执行当前问题修复步骤。",
    }


def main() -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()

    result = route_feature(args.slug) if args.flow == "feature" else route_issue(args.slug)
    result["recommended_command"] = to_public_command(result.get("recommended_command", ""))
    result = attach_route_summary(result)
    print_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
