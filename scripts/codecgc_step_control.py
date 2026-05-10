from __future__ import annotations

from pathlib import Path
from typing import Any

from build_codecgc_task import load_checklist_yaml


def resolve_artifact_type(data: dict[str, Any]) -> str:
    if data.get("feature"):
        return "feature"
    if data.get("issue"):
        return "issue"
    return "checklist"


def is_placeholder_path(path_text: str) -> bool:
    normalized = str(path_text or "").strip().replace("\\", "/").lower()
    return not normalized or normalized == "todo/path" or normalized.startswith("todo/")


def is_executable_codecgc_block(codecgc: Any) -> bool:
    if not isinstance(codecgc, dict):
        return False

    kind = str(codecgc.get("kind", "")).strip().lower()
    if kind not in {"frontend", "backend"}:
        return False

    target_paths = codecgc.get("target_paths", [])
    if not isinstance(target_paths, list) or not target_paths:
        return False

    if any(is_placeholder_path(path) for path in target_paths):
        return False

    task_summary = str(codecgc.get("task_summary", "")).strip()
    return bool(task_summary)


def is_test_codecgc_block(codecgc: Any) -> bool:
    if not is_executable_codecgc_block(codecgc):
        return False
    return str(codecgc.get("step_type", "")).strip().lower() == "test"


def select_next_executable_step(checklist_path: Path) -> dict[str, Any]:
    data = load_checklist_yaml(checklist_path)
    steps = data.get("steps", [])
    if not isinstance(steps, list) or not steps:
        raise ValueError("Checklist does not contain any steps.")

    first_planning_index: int | None = None
    first_executable_index: int | None = None

    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        status = str(step.get("status", "pending")).strip().lower()
        if status not in {"pending", ""}:
            continue

        codecgc = step.get("codecgc")
        if is_executable_codecgc_block(codecgc):
            if first_executable_index is None:
                first_executable_index = index
            continue

        if first_planning_index is None:
            first_planning_index = index

    if first_planning_index is not None:
        step = steps[first_planning_index - 1]
        raise ValueError(
            f"Planning-only step {first_planning_index} must be resolved before execution: "
            f"{step.get('action', 'unknown action')}"
        )

    if first_executable_index is None:
        raise ValueError("No pending executable step remains in this checklist.")

    step = steps[first_executable_index - 1]
    codecgc = step.get("codecgc", {})
    return {
        "step_number": first_executable_index,
        "task_id": str(codecgc.get("task_id", "")),
        "action": str(step.get("action", "")),
        "kind": str(codecgc.get("kind", "")),
        "step_type": str(codecgc.get("step_type", "")),
        "target_paths": codecgc.get("target_paths", []),
        "task_summary": str(codecgc.get("task_summary", "")),
        "artifact_type": resolve_artifact_type(data),
        "timeout_seconds": int(codecgc.get("timeout_seconds", 0)) or 0,
    }


def get_step_metadata(checklist_path: Path, step_number: int) -> dict[str, Any]:
    data = load_checklist_yaml(checklist_path)
    steps = data.get("steps", [])
    if not isinstance(steps, list) or step_number < 1 or step_number > len(steps):
        raise ValueError(f"Step number must be between 1 and {len(steps)}.")
    step = steps[step_number - 1]
    codecgc = step.get("codecgc", {}) if isinstance(step, dict) else {}
    executable = is_executable_codecgc_block(codecgc)
    return {
        "step_number": step_number,
        "task_id": str(codecgc.get("task_id", "")),
        "action": str(step.get("action", "")) if isinstance(step, dict) else "",
        "kind": str(codecgc.get("kind", "")),
        "step_type": str(codecgc.get("step_type", "")),
        "target_paths": codecgc.get("target_paths", []),
        "task_summary": str(codecgc.get("task_summary", "")),
        "artifact_type": resolve_artifact_type(data),
        "executable": executable,
        "timeout_seconds": int(codecgc.get("timeout_seconds", 0)) or 0,
    }


def replace_step_status(text: str, step_number: int, new_status: str) -> str:
    lines = text.splitlines()
    current_step = 0
    inside_steps = False
    current_step_indent = ""

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "steps:":
            inside_steps = True
            continue

        if inside_steps and not line.startswith(" "):
            break

        if inside_steps and line.startswith("  - "):
            current_step += 1
            current_step_indent = line[: len(line) - len(line.lstrip(" "))]
            continue

        if (
            inside_steps
            and current_step == step_number
            and stripped.startswith("status:")
            and line.startswith(f"{current_step_indent}  ")
        ):
            indent = line[: len(line) - len(line.lstrip(" "))]
            lines[index] = f"{indent}status: {new_status}"
            return "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    raise ValueError(f"Could not find status field for step {step_number}.")


def update_step_status(checklist_path: Path, step_number: int, new_status: str) -> None:
    original = checklist_path.read_text(encoding="utf-8")
    updated = replace_step_status(original, step_number, new_status)
    checklist_path.write_text(updated, encoding="utf-8")
