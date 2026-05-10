import argparse
import asyncio
import datetime
import json
import sys
from pathlib import Path
from typing import Any

from codecgc_artifact_roots import execution_root
from codecgc_artifact_roots import normalize_artifact_class
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_executor_registry import build_executor_env
from codecgc_executor_registry import get_executor_config
from codecgc_file_evidence import snapshot_workspace
from codecgc_file_evidence import verify_workspace_changes
from codecgc_path_contract import normalize_audit_path_fields
from codecgc_path_contract import normalize_persisted_project_path
from codecgc_runtime_paths import PACKAGE_ROOT
from codecgc_runtime_paths import PROJECT_ROOT
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from build_codecgc_task import build_parser as build_task_parser
from build_codecgc_task import build_tool_call, load_simple_routing_config


WORKSPACE = PACKAGE_ROOT
PROJECT_WORKSPACE = PROJECT_ROOT


def extract_split_payload(text: str) -> dict[str, Any]:
    marker = "SPLIT_PAYLOAD:"
    if marker not in text:
        return {}
    _, _, suffix = text.partition(marker)
    payload_text = suffix.strip()
    if not payload_text:
        return {}
    try:
        parsed = json.loads(payload_text)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def strip_split_payload_marker(text: str) -> str:
    marker = "SPLIT_PAYLOAD:"
    if marker not in text:
        return text.strip()
    prefix, _, _ = text.partition(marker)
    return prefix.strip()


def build_server_params(target: str) -> StdioServerParameters:
    config = get_executor_config(target)
    return StdioServerParameters(
        command=str(config["python_command"]),
        args=["-m", str(config["python_module"])],
        env=build_executor_env(target),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = build_task_parser()
    parser.description = "Build, execute, and audit a CodeCGC MCP task."
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="MCP call timeout in seconds.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print the built task payload without executing it.",
    )
    parser.add_argument(
        "--audit-root",
        default="",
        help="Optional directory used to store CodeCGC execution audit files. Defaults to the artifact-class-specific execution root.",
    )
    parser.add_argument(
        "--skip-audit-write",
        action="store_true",
        help="Do not write execution audit artifacts.",
    )
    return parser


def extract_text_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(part for part in parts if part).strip()
    return ""


def normalize_mcp_result(raw: dict[str, Any]) -> dict[str, Any]:
    structured_content = raw.get("structuredContent")
    if isinstance(structured_content, dict):
        return structured_content

    content = raw.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "text":
                continue
            text = item.get("text")
            if not isinstance(text, str):
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed

    return {
        "success": False,
        "error": "Unable to parse structured MCP tool result.",
        "raw_content": content,
    }


def sanitize_for_json(value: Any, seen: set[int] | None = None) -> Any:
    if seen is None:
        seen = set()

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    object_id = id(value)
    if object_id in seen:
        return "[circular]"

    if isinstance(value, dict):
        seen.add(object_id)
        sanitized = {str(key): sanitize_for_json(item, seen) for key, item in value.items()}
        seen.remove(object_id)
        return sanitized

    if isinstance(value, list):
        seen.add(object_id)
        sanitized = [sanitize_for_json(item, seen) for item in value]
        seen.remove(object_id)
        return sanitized

    if isinstance(value, tuple):
        seen.add(object_id)
        sanitized = [sanitize_for_json(item, seen) for item in value]
        seen.remove(object_id)
        return sanitized

    return str(value)


def classify_outcome(result: dict[str, Any]) -> str:
    if result.get("success"):
        return "done"

    error_text = str(result.get("error", "")).lower()
    summary_text = str(result.get("summary", "")).lower()
    combined = f"{error_text}\n{summary_text}"
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
    if "shared paths" in error_text or "mixed frontend/backend" in error_text:
        return "split-required"
    if "not covered by model-routing.yaml" in error_text or "unsupported kind" in error_text:
        return "design-gap"
    if any(marker in combined for marker in target_missing_markers):
        return "design-gap"
    if "does not exist" in error_text or "timeout" in error_text:
        return "blocked"
    if "unable to parse structured mcp tool result" in error_text:
        return "executor-failure"
    return "executor-failure"


def build_audit_record(
    *,
    payload: dict[str, Any],
    args: argparse.Namespace,
    result: dict[str, Any],
    mode: str,
    file_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    tool_args = payload.get("tool_args", {})
    target_paths = tool_args.get("target_paths", [])
    task_id = str(tool_args.get("task_id", "unknown-task"))
    reported_changed_files = result.get("changed_files", [])
    if not isinstance(reported_changed_files, list):
        reported_changed_files = []

    record = {
        "product": "CodeCGC",
        "version": 1,
        "mode": mode,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "task_id": task_id,
        "target": payload.get("target"),
        "tool_name": payload.get("tool_name"),
        "target_paths": target_paths,
        "route_notes": payload.get("route_notes", []),
        "routing_file": payload.get("routing_file"),
        "source": payload.get("source"),
        "task_summary": tool_args.get("task_summary", ""),
        "constraints": tool_args.get("constraints", []),
        "acceptance_criteria": tool_args.get("acceptance_criteria", []),
        "cd": tool_args.get("cd", ""),
        "requested_session_id": tool_args.get("SESSION_ID", ""),
        "result": {
            "success": bool(result.get("success")),
            "outcome": classify_outcome(result),
            "task_id": result.get("task_id", task_id),
            "session_id": result.get("SESSION_ID", ""),
            "summary": result.get("summary", ""),
            "changed_files": reported_changed_files,
            "policy_checks": result.get("policy_checks", []),
            "risks": result.get("risks", []),
            "error": result.get("error", ""),
            "split_suggestion": result.get("split_suggestion", {}),
        },
        "file_evidence": file_evidence or {
            "evidence_source": "not-collected",
            "workspace_changed_files": [],
            "verified_changed_files": [],
            "out_of_scope_changed_files": [],
            "file_diffs": [],
            "evidence_confidence": "unknown",
            "git_evidence": {
                "git_repository_detected": False,
                "git_root": "",
                "history_available": False,
                "status": "not-collected",
                "tracked_changed_files": [],
                "untracked_changed_files": [],
                "git_changed_files": [],
            },
        },
    }
    return normalize_audit_path_fields(record, PROJECT_WORKSPACE)


def write_audit_file(audit_root: Path, audit_record: dict[str, Any]) -> Path:
    audit_root.mkdir(parents=True, exist_ok=True)

    task_id = str(audit_record.get("task_id", "unknown-task"))
    safe_task_id = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in task_id)
    filename = f"{safe_task_id}.json"
    audit_path = audit_root / filename
    audit_path.write_text(json.dumps(audit_record, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit_path


async def execute_payload(payload: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    params = build_server_params(payload["target"])

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            raw_result = await session.call_tool(
                payload["tool_name"],
                payload["tool_args"],
                read_timeout_seconds=datetime.timedelta(seconds=timeout_seconds),
            )

    dumped = raw_result.model_dump(mode="json")
    normalized = normalize_mcp_result(dumped)
    normalized["raw_mcp_result"] = dumped
    return normalized


async def run_task(args: argparse.Namespace) -> dict[str, Any]:
    routing = load_simple_routing_config(Path(args.routing_file))
    try:
        payload = build_tool_call(args, routing)
    except Exception as error:
        message = str(error)
        lowered = message.lower()
        outcome = "executor-failure"
        split_payload: dict[str, Any] = {}
        if "not covered by model-routing.yaml" in lowered or "unsupported kind" in lowered:
            outcome = "design-gap"
        elif "shared paths" in lowered or "mixed frontend/backend" in lowered:
            outcome = "split-required"
            split_payload = extract_split_payload(message)
        elif "does not exist" in lowered or "timeout" in lowered:
            outcome = "blocked"
        cleaned_message = strip_split_payload_marker(message)
        return {
            "success": False,
            "mode": "build-failed",
            "payload": {},
            "result": {
                "success": False,
                "outcome": outcome,
                "task_id": "",
                "session_id": "",
                "summary": cleaned_message,
                "changed_files": [],
                "policy_checks": [],
                "risks": [],
                "error": cleaned_message,
                "split_suggestion": split_payload,
            },
            "audit": {
                "written": False,
                "path": "",
            },
        }
    source = payload.get("source", {})
    artifact_class = normalize_artifact_class(source.get("artifact_class", "product") if isinstance(source, dict) else "product")
    file_evidence: dict[str, Any] | None = None

    if args.dry_run:
        task_result = {
            "success": True,
            "task_id": payload["tool_args"].get("task_id", ""),
            "summary": "Dry run only. Task payload built but not executed.",
            "changed_files": payload["tool_args"].get("target_paths", []),
            "policy_checks": ["dry_run_only"],
            "risks": ["execution_not_performed"],
            "SESSION_ID": payload["tool_args"].get("SESSION_ID", ""),
        }
        mode = "dry-run"
    else:
        step_timeout = int(payload.get("timeout_seconds", 0)) or 0
        effective_timeout = step_timeout if step_timeout > 0 else args.timeout_seconds
        before_snapshot = snapshot_workspace(PROJECT_WORKSPACE)
        task_result = await execute_payload(payload, effective_timeout)
        after_snapshot = snapshot_workspace(PROJECT_WORKSPACE)
        file_evidence = verify_workspace_changes(
            before_snapshot,
            after_snapshot,
            list(payload["tool_args"].get("target_paths", [])),
        )
        mode = "execute"

    audit_record = build_audit_record(
        payload=payload,
        args=args,
        result=task_result,
        mode=mode,
        file_evidence=file_evidence,
    )

    audit_path = None
    if not args.skip_audit_write:
        audit_root = Path(args.audit_root) if args.audit_root else execution_root(artifact_class)
        audit_path = write_audit_file(audit_root, audit_record)

    output = {
        "success": bool(task_result.get("success")),
        "mode": mode,
        "payload": payload,
        "result": task_result,
        "audit": {
            "written": not args.skip_audit_write,
            "path": normalize_persisted_project_path(audit_path) if audit_path else "",
        },
    }
    return sanitize_for_json(output)


def main() -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()

    try:
        result = asyncio.run(run_task(args))
    except Exception as error:
        print_json(
            {
                "success": False,
                "error": str(error),
            },
            file=sys.stderr,
        )
        return 1

    print_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
