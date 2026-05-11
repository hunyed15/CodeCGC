import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_path_contract import normalize_persisted_project_path
from codecgc_policy import classify_path
from codecgc_policy import load_policy
from codecgc_policy import validate_executor_target
from codecgc_routing_paths import resolve_active_routing_file
from codecgc_runtime_paths import PACKAGE_ROOT
from codecgc_runtime_paths import PROJECT_ROOT

WORKSPACE = PACKAGE_ROOT
PROJECT_WORKSPACE = PROJECT_ROOT
DEFAULT_ROUTING_FILE = resolve_active_routing_file()


def normalize_path_text(path_text: str) -> str:
    normalized = path_text.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def load_simple_routing_config(path: Path) -> dict[str, Any]:
    """Load routing configuration YAML file using standard yaml library."""
    return load_policy(path)


def load_checklist_yaml(path: Path) -> dict[str, Any]:
    """Load and parse a checklist YAML file using standard yaml library."""
    if not path.exists():
        raise FileNotFoundError(f"Checklist file not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict):
            raise ValueError(f"Checklist YAML must be a dictionary, got {type(data).__name__}")

        return data
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML file {path}: {e}") from e


def normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        normalized: list[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                normalized.append(text)
        return normalized
    text = str(value).strip()
    return [text] if text else []


def is_executable_codecgc_block(block: Any) -> bool:
    """Compatibility helper for older tests and scripts.

    Runtime step selection uses codecgc_step_control.is_executable_codecgc_block,
    which is intentionally stricter. This helper preserves the historical task
    builder contract: explicit frontend/backend kind plus at least one target.
    """
    if not isinstance(block, dict):
        return False

    kind = str(block.get("kind", "")).strip().lower()
    if not kind or kind == "auto":
        return False

    target_paths = block.get("target_paths", [])
    if not isinstance(target_paths, list):
        return False

    return any(str(path).strip() for path in target_paths)


def resolve_optional_value(cli_value: Any, spec_value: Any, default_value: Any) -> Any:
    if cli_value not in (None, "", []):
        return cli_value
    if spec_value not in (None, "", []):
        return spec_value
    return default_value


def resolve_cd_value(cd_value: str | None) -> str:
    if not cd_value:
        return str(PROJECT_WORKSPACE)

    path = Path(str(cd_value))
    if path.is_absolute():
        return str(path)

    return str((PROJECT_WORKSPACE / path).resolve())


def load_checklist_step_payload(args: argparse.Namespace) -> dict[str, Any]:
    checklist_path = Path(str(args.checklist_file))
    checklist = load_checklist_yaml(checklist_path)
    steps = checklist.get("steps", [])

    if not isinstance(steps, list) or not steps:
        raise ValueError("Checklist does not contain any steps.")

    step_number = args.step_number
    if step_number is None or step_number < 1 or step_number > len(steps):
        raise ValueError(f"Step number must be between 1 and {len(steps)}.")

    step = steps[step_number - 1]
    step_spec = step.get("codecgc")
    if not isinstance(step_spec, dict):
        raise ValueError(
            f"Checklist step {step_number} does not define a codecgc block."
        )

    feature_value = checklist.get("feature")
    issue_value = checklist.get("issue")
    artifact_class = str(checklist.get("artifact_class", "product") or "product")
    artifact_type = "feature" if feature_value else "issue" if issue_value else "checklist"
    fallback_slug = checklist_path.stem.replace("-checklist", "").replace("-fix", "")
    artifact_slug = str(feature_value or issue_value or fallback_slug)
    kind_from_spec = step_spec.get("kind", "auto")
    requested_kind = args.kind if args.kind != "auto" else str(kind_from_spec)
    task_summary = resolve_optional_value(args.task_summary, step_spec.get("task_summary"), step.get("action"))
    target_paths = normalize_string_list(
        resolve_optional_value(args.target_path, step_spec.get("target_paths"), None)
    )
    constraints = normalize_string_list(
        resolve_optional_value(args.constraint, step_spec.get("constraints"), [])
    )
    acceptance = normalize_string_list(
        resolve_optional_value(
            args.acceptance,
            step_spec.get("acceptance"),
            [step.get("exit_signal")] if step.get("exit_signal") else [],
        )
    )
    task_id = resolve_optional_value(
        args.task_id,
        step_spec.get("task_id"),
        f"{artifact_slug}-step-{step_number}",
    )

    return {
        "kind": requested_kind,
        "task_id": str(task_id),
        "task_summary": str(task_summary),
        "target_path": target_paths,
        "constraint": constraints,
        "acceptance": acceptance,
        "cd": resolve_cd_value(str(resolve_optional_value(args.cd, step_spec.get("cd"), None))),
        "routing_file": normalize_persisted_project_path(args.routing_file),
        "session_id": str(resolve_optional_value(args.session_id, step_spec.get("session_id"), "")),
        "model": str(resolve_optional_value(args.model, step_spec.get("model"), "")),
        "profile": str(resolve_optional_value(args.profile, step_spec.get("profile"), "")),
        "codex_sandbox": str(
            resolve_optional_value(args.codex_sandbox, step_spec.get("codex_sandbox"), "workspace-write")
        ),
        "gemini_sandbox": bool(
            resolve_optional_value(args.gemini_sandbox, step_spec.get("gemini_sandbox"), False)
        ),
        "return_all_messages": bool(
            resolve_optional_value(
                args.return_all_messages,
                step_spec.get("return_all_messages"),
                False,
            )
        ),
        "timeout_seconds": int(step_spec.get("timeout_seconds", 0)) or 0,
        "source": {
            "type": "workflow-step",
            "artifact_file": normalize_persisted_project_path(checklist_path),
            "artifact_type": artifact_type,
            "artifact_class": artifact_class,
            "artifact_slug": artifact_slug,
            "step_number": step_number,
            "step_action": str(step.get("action", "")),
        },
    }


def load_explicit_task_payload(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "kind": args.kind,
        "task_id": args.task_id,
        "task_summary": args.task_summary,
        "target_path": args.target_path,
        "constraint": args.constraint,
        "acceptance": args.acceptance,
        "cd": resolve_cd_value(args.cd),
        "routing_file": normalize_persisted_project_path(args.routing_file),
        "session_id": args.session_id or "",
        "model": args.model or "",
        "profile": args.profile or "",
        "codex_sandbox": args.codex_sandbox or "workspace-write",
        "gemini_sandbox": bool(args.gemini_sandbox),
        "return_all_messages": bool(args.return_all_messages),
        "timeout_seconds": int(getattr(args, "timeout_seconds", 0) or 0),
        "source": None,
    }


def classify_paths(paths: list[str], routing: dict[str, Any]) -> dict[str, str]:
    return {path: classify_path(path, routing) for path in paths}


def split_paths_by_category(classifications: dict[str, str]) -> dict[str, list[str]]:
    grouped = {
        "frontend": [],
        "backend": [],
        "frontend-test": [],
        "backend-test": [],
        "docs": [],
        "orchestration": [],
        "shared": [],
        "unknown": [],
    }
    for path, category in classifications.items():
        grouped.setdefault(category, []).append(path)
    return grouped


def build_split_required_payload(paths: list[str], routing: dict[str, Any]) -> dict[str, Any]:
    classifications = classify_paths(paths, routing)
    grouped = split_paths_by_category(classifications)
    suggestions: list[dict[str, Any]] = []

    if grouped.get("backend"):
        suggestions.append(
            {
                "step": f"step-{len(suggestions) + 1}",
                "kind": "backend",
                "executor": "Codex",
                "target_paths": grouped["backend"],
                "reason": "这些路径已明确属于后端范围，应拆成独立后端步骤。",
            }
        )

    if grouped.get("frontend"):
        suggestions.append(
            {
                "step": f"step-{len(suggestions) + 1}",
                "kind": "frontend",
                "executor": "Gemini",
                "target_paths": grouped["frontend"],
                "reason": "这些路径已明确属于前端范围，应拆成独立前端步骤。",
            }
        )

    if grouped.get("shared"):
        suggestions.append(
            {
                "step": f"step-{len(suggestions) + 1}",
                "kind": "planning",
                "executor": "Claude",
                "target_paths": grouped["shared"],
                "reason": "这些路径属于 shared 范围，必须先重新拆分到纯前端或纯后端步骤后才能执行。",
            }
        )

    return {
        "path_classification": classifications,
        "grouped_paths": grouped,
        "suggested_split_steps": suggestions,
    }


def detect_target_kind(paths: list[str], routing: dict[str, Any]) -> tuple[str, list[str]]:
    classifications = classify_paths(paths, routing)
    categories = set(classifications.values())

    if categories & {"shared", "docs", "orchestration"}:
        details = [
            f"{path} -> {category}"
            for path, category in classifications.items()
            if category in {"shared", "docs", "orchestration"}
        ]
        split_payload = build_split_required_payload(paths, routing)
        raise ValueError(
            "Detected non-executor-owned paths. Route them through Claude workflow first.\n"
            + "\n".join(details)
            + "\nSPLIT_PAYLOAD: "
            + json.dumps(split_payload, ensure_ascii=False)
        )

    if "unknown" in categories:
        details = [
            f"{path} -> unknown" for path, category in classifications.items() if category == "unknown"
        ]
        raise ValueError(
            "Some target paths are not covered by model-routing.yaml.\n" + "\n".join(details)
        )

    if categories <= {"frontend", "frontend-test"}:
        return "frontend", [f"{path} -> frontend" for path in paths]

    if categories <= {"backend", "backend-test"}:
        return "backend", [f"{path} -> backend" for path in paths]

    details = [f"{path} -> {classifications[path]}" for path in paths]
    split_payload = build_split_required_payload(paths, routing)
    raise ValueError(
        "Detected mixed frontend/backend paths. Split the task first.\n"
        + "\n".join(details)
        + "\nSPLIT_PAYLOAD: "
        + json.dumps(split_payload, ensure_ascii=False)
    )


def build_tool_call(args: argparse.Namespace, routing: dict[str, Any]) -> dict[str, Any]:
    payload_inputs = (
        load_checklist_step_payload(args)
        if args.checklist_file
        else load_explicit_task_payload(args)
    )
    target_paths = [normalize_path_text(path) for path in payload_inputs["target_path"]]

    if not target_paths:
        raise ValueError("At least one --target-path is required.")

    requested_kind = str(payload_inputs["kind"])
    if requested_kind == "auto":
        kind, route_notes = detect_target_kind(target_paths, routing)
    else:
        kind = requested_kind
        route_notes = [f"{path} -> forced:{kind}" for path in target_paths]

    policy_result = validate_executor_target(kind, target_paths, routing)
    if not policy_result.get("allowed"):
        raise ValueError(
            "Target paths violate CodeCGC routing policy.\n"
            + json.dumps(policy_result, ensure_ascii=False)
        )

    effective_timeout_seconds = int(payload_inputs.get("timeout_seconds", 0)) or int(
        getattr(args, "timeout_seconds", 0) or 0
    )

    if kind == "frontend":
        tool_name = "implement_frontend_task"
        tool_args: dict[str, Any] = {
            "task_id": payload_inputs["task_id"],
            "task_summary": payload_inputs["task_summary"],
            "target_paths": target_paths,
            "constraints": payload_inputs["constraint"],
            "acceptance_criteria": payload_inputs["acceptance"],
            "cd": payload_inputs["cd"],
            "SESSION_ID": payload_inputs["session_id"],
            "sandbox": payload_inputs["gemini_sandbox"],
            "return_all_messages": payload_inputs["return_all_messages"],
            "model": payload_inputs["model"],
            "timeout_seconds": effective_timeout_seconds,
        }
    elif kind == "backend":
        tool_name = "implement_backend_task"
        tool_args = {
            "task_id": payload_inputs["task_id"],
            "task_summary": payload_inputs["task_summary"],
            "target_paths": target_paths,
            "constraints": payload_inputs["constraint"],
            "acceptance_criteria": payload_inputs["acceptance"],
            "cd": payload_inputs["cd"],
            "SESSION_ID": payload_inputs["session_id"],
            "sandbox": payload_inputs["codex_sandbox"],
            "return_all_messages": payload_inputs["return_all_messages"],
            "model": payload_inputs["model"],
        }
        if payload_inputs["profile"]:
            tool_args["profile"] = payload_inputs["profile"]
    else:
        raise ValueError(f"Unsupported kind: {kind}")

    result = {
        "target": kind,
        "tool_name": tool_name,
        "tool_args": tool_args,
        "timeout_seconds": effective_timeout_seconds,
        "route_notes": route_notes,
        "policy": policy_result,
        "routing_file": payload_inputs["routing_file"],
    }
    if payload_inputs["source"] is not None:
        result["source"] = payload_inputs["source"]
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a standard CodeCGC MCP task payload."
    )
    parser.add_argument(
        "--kind",
        choices=["auto", "frontend", "backend"],
        default="auto",
        help="Task target kind. Use auto to classify from model-routing.yaml.",
    )
    parser.add_argument("--task-id", help="Stable task identifier.")
    parser.add_argument(
        "--task-summary",
        help="Current step or fix summary only.",
    )
    parser.add_argument(
        "--target-path",
        action="append",
        default=[],
        help="Allowed target path. Repeat for multiple files.",
    )
    parser.add_argument(
        "--constraint",
        action="append",
        default=[],
        help="Non-negotiable task constraint. Repeat for multiple lines.",
    )
    parser.add_argument(
        "--acceptance",
        action="append",
        default=[],
        help="Acceptance criterion. Repeat for multiple lines.",
    )
    parser.add_argument(
        "--cd",
        help="Workspace root that the executor should use.",
    )
    parser.add_argument(
        "--checklist-file",
        help="Optional checklist YAML file that contains a step-level codecgc block.",
    )
    parser.add_argument(
        "--step-number",
        type=int,
        help="1-based checklist step number. Requires --checklist-file.",
    )
    parser.add_argument(
        "--routing-file",
        default=str(DEFAULT_ROUTING_FILE),
        help="Path to model-routing.yaml.",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Optional MCP session id for resume.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional explicit model override.",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Optional Codex profile. Backend only.",
    )
    parser.add_argument(
        "--codex-sandbox",
        choices=["read-only", "workspace-write", "danger-full-access"],
        default=None,
        help="Backend sandbox value.",
    )
    parser.add_argument(
        "--gemini-sandbox",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Frontend sandbox flag.",
    )
    parser.add_argument(
        "--return-all-messages",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Request full event logs from the executor.",
    )
    return parser


def main() -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()

    try:
        routing = load_simple_routing_config(Path(args.routing_file))
        payload = build_tool_call(args, routing)
    except Exception as error:
        print_json(
            {
                "success": False,
                "error": str(error),
            },
            file=sys.stderr,
        )
        return 1

    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
