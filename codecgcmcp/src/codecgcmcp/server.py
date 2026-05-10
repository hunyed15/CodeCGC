"""FastMCP server implementation for the CodeCGC orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult
from mcp.types import TextContent
from pydantic import Field

from codecgc_workflow_runtime import run_json_script

mcp = FastMCP("CodeCGC MCP Server")

MCP_CONTRACT_VERSION = "1.0"

EXCEPTION_ERROR_CATEGORIES = {
    "JSONDecodeError": "runtime-json-invalid",
    "ValueError": "runtime-json-invalid",
    "TimeoutExpired": "runtime-timeout",
    "FileNotFoundError": "runtime-script-missing",
    "PermissionError": "runtime-permission-denied",
}


def _append_repeated_flag(args: list[str], flag: str, values: list[str]) -> None:
    for value in values:
        text = str(value).strip()
        if text:
            args.extend([flag, text])


def _normalize_workspace(workspace: str) -> str:
    return str(Path(workspace).expanduser().resolve()) if str(workspace).strip() else ""


def _payload_success(payload: dict[str, Any]) -> bool:
    return bool(payload.get("success", True))


def _runtime_error_category(payload: dict[str, Any]) -> str:
    raw_category = str(payload.get("error_category") or payload.get("failure_category") or "").strip()
    if raw_category:
        return raw_category
    returncode = payload.get("returncode")
    if returncode is not None:
        return "runtime-script-failed"
    return "runtime-payload-failed"


def _payload_error(tool_name: str, script_name: str, args: tuple[str, ...], payload: dict[str, Any]) -> dict[str, Any] | None:
    if _payload_success(payload):
        return None
    summary = payload.get("summary", {}) if isinstance(payload.get("summary"), dict) else {}
    message = str(
        payload.get("error")
        or summary.get("human_summary")
        or summary.get("recommended_next_action")
        or "Runtime script reported failure."
    )
    return {
        "type": str(payload.get("error_type") or "RuntimeScriptError"),
        "category": _runtime_error_category(payload),
        "message": message,
        "tool": tool_name,
        "script": script_name,
        "args": list(args),
        "returncode": payload.get("returncode"),
    }


def _exception_category(error: Exception) -> str:
    return EXCEPTION_ERROR_CATEGORIES.get(error.__class__.__name__, "mcp-wrapper-exception")


def _exception_payload(tool_name: str, script_name: str, args: tuple[str, ...], error: Exception) -> tuple[dict[str, Any], dict[str, Any]]:
    normalized_error = {
        "type": error.__class__.__name__,
        "category": _exception_category(error),
        "message": str(error),
        "tool": tool_name,
        "script": script_name,
        "args": list(args),
        "returncode": None,
    }
    payload = {
        "success": False,
        "mode": "mcp-runtime-call",
        "summary": {
            "ready": False,
            "human_summary": "CodeCGC MCP tool failed before a runtime JSON payload was produced.",
            "recommended_next_action": "Check the runtime script output and MCP server logs.",
        },
    }
    return payload, normalized_error


def _build_tool_envelope(tool_name: str, payload: dict[str, Any], error: dict[str, Any] | None = None) -> dict[str, Any]:
    success = _payload_success(payload) and error is None
    return {
        "success": success,
        "tool": tool_name,
        "payload": payload,
        "error": error,
        "meta": {
            "contract_version": MCP_CONTRACT_VERSION,
            "payload_success": _payload_success(payload),
            "response_shape": "codecgc.mcp.tool_result",
        },
    }


def _as_tool_result(tool_name: str, payload: dict[str, Any], error: dict[str, Any] | None = None) -> CallToolResult:
    envelope = _build_tool_envelope(tool_name, payload, error)
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(envelope, ensure_ascii=False, indent=2),
            )
        ],
        isError=not bool(envelope.get("success", True)),
    )


def _call_runtime_tool(tool_name: str, script_name: str, *args: str, requested_format: str = "") -> CallToolResult:
    try:
        payload = run_json_script(script_name, *args)
        if requested_format:
            payload.setdefault("requested_format", requested_format)
        return _as_tool_result(tool_name, payload, _payload_error(tool_name, script_name, args, payload))
    except Exception as error:
        payload, normalized_error = _exception_payload(tool_name, script_name, args, error)
        return _as_tool_result(tool_name, payload, normalized_error)


@mcp.tool(
    name="codecgc.install",
    description="Install or sync CodeCGC integration for the current project or Claude user profile.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_install(
    mode: Annotated[
        Literal["local", "user-dry-run", "user", "status", "doctor"],
        Field(description="Install mode for CodeCGC integration."),
    ] = "local",
    format: Annotated[
        Literal["summary", "json"],
        Field(description="Presentation hint. MCP responses are always returned as JSON payloads."),
    ] = "summary",
    workspace: Annotated[
        str,
        Field(description="Optional target workspace root for local/status/doctor modes."),
    ] = "",
    user_root: Annotated[
        str,
        Field(description="Optional explicit Claude user root for user/user-dry-run modes."),
    ] = "",
) -> CallToolResult:
    # The MCP surface must always receive machine-readable JSON from the script.
    args = ["--mode", mode, "--format", "json"]
    normalized_workspace = _normalize_workspace(workspace)
    if normalized_workspace:
        args.extend(["--workspace", normalized_workspace])
    if str(user_root).strip():
        args.extend(["--user-root", str(user_root).strip()])
    return _call_runtime_tool("codecgc.install", "install_codecgc.py", *args, requested_format=format)


@mcp.tool(
    name="codecgc.status",
    description="Check CodeCGC integration readiness for the current or specified workspace.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_status(
    workspace: Annotated[
        str,
        Field(description="Optional target workspace root."),
    ] = "",
) -> CallToolResult:
    args = ["--mode", "status", "--format", "json"]
    normalized_workspace = _normalize_workspace(workspace)
    if normalized_workspace:
        args.extend(["--workspace", normalized_workspace])
    return _call_runtime_tool("codecgc.status", "install_codecgc.py", *args)


@mcp.tool(
    name="codecgc.start",
    description="Show the project-local CodeCGC first-run guide and recommended next actions.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_start(
    workspace: Annotated[
        str,
        Field(description="Optional target workspace root."),
    ] = "",
) -> CallToolResult:
    args = ["--mode", "start", "--format", "json"]
    normalized_workspace = _normalize_workspace(workspace)
    if normalized_workspace:
        args.extend(["--workspace", normalized_workspace])
    return _call_runtime_tool("codecgc.start", "install_codecgc.py", *args)


@mcp.tool(
    name="codecgc.doctor",
    description="Run CodeCGC runtime and integration health checks.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_doctor(
    workspace: Annotated[
        str,
        Field(description="Optional target workspace root."),
    ] = "",
) -> CallToolResult:
    args = ["--mode", "doctor", "--format", "json"]
    normalized_workspace = _normalize_workspace(workspace)
    if normalized_workspace:
        args.extend(["--workspace", normalized_workspace])
    return _call_runtime_tool("codecgc.doctor", "install_codecgc.py", *args)


@mcp.tool(
    name="codecgc.entry",
    description="Primary CodeCGC orchestration entry for new requests, continue, explain, and auto-dispatch decisions.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_entry(
    request: Annotated[str, "Natural-language request for CodeCGC."] = "",
    mode: Annotated[
        Literal["auto", "new", "continue", "explain"],
        Field(description="Entry mode."),
    ] = "auto",
    flow: Annotated[
        Literal["", "feature", "issue"],
        Field(description="Optional explicit workflow flow."),
    ] = "",
    slug: Annotated[str, "Optional workflow slug."] = "",
    latest: Annotated[bool, "Use the latest matching workflow."] = False,
    include_fixtures: Annotated[bool, "Allow fixture workflows to be considered."] = False,
    auto_dispatch: Annotated[bool, "Allow entry to dispatch when the route permits it."] = False,
    dry_run: Annotated[bool, "Avoid real executor dispatch."] = False,
    audit_file: Annotated[str, "Optional audit file for review dispatch."] = "",
    decision: Annotated[
        Literal["", "accepted", "changes-requested"],
        Field(description="Optional review decision when the request is review-like."),
    ] = "",
) -> CallToolResult:
    args = ["--mode", mode]
    if str(request).strip():
        args.extend(["--request", str(request).strip()])
    if flow:
        args.extend(["--flow", flow])
    if str(slug).strip():
        args.extend(["--slug", str(slug).strip()])
    if latest:
        args.append("--latest")
    if include_fixtures:
        args.append("--include-fixtures")
    if auto_dispatch:
        args.append("--auto-dispatch")
    if dry_run:
        args.append("--dry-run")
    if str(audit_file).strip():
        args.extend(["--audit-file", str(audit_file).strip()])
    if decision:
        args.extend(["--decision", decision])
    return _call_runtime_tool("codecgc.entry", "entry_codecgc_workflow.py", *args)


@mcp.tool(
    name="codecgc.continue",
    description="Continue the current or latest CodeCGC workflow using the existing runtime state.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_continue(
    request: Annotated[str, "Optional continue request text. Defaults to continuing the current work."] = "继续刚刚的工作",
    flow: Annotated[
        Literal["", "feature", "issue"],
        Field(description="Optional explicit workflow flow."),
    ] = "",
    slug: Annotated[str, "Optional workflow slug."] = "",
    latest: Annotated[bool, "Use the latest matching workflow."] = True,
    include_fixtures: Annotated[bool, "Allow fixture workflows to be considered."] = False,
    auto_dispatch: Annotated[bool, "Allow continue to dispatch when the route permits it."] = False,
    dry_run: Annotated[bool, "Avoid real executor dispatch."] = False,
) -> CallToolResult:
    args = ["--mode", "continue", "--request", str(request).strip() or "继续刚刚的工作"]
    if flow:
        args.extend(["--flow", flow])
    if str(slug).strip():
        args.extend(["--slug", str(slug).strip()])
    if latest:
        args.append("--latest")
    if include_fixtures:
        args.append("--include-fixtures")
    if auto_dispatch:
        args.append("--auto-dispatch")
    if dry_run:
        args.append("--dry-run")
    return _call_runtime_tool("codecgc.continue", "entry_codecgc_workflow.py", *args)


@mcp.tool(
    name="codecgc.explain",
    description="Explain the current or latest CodeCGC workflow state and recommended next action.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_explain(
    request: Annotated[str, "Optional explain request text."] = "现在下一步该做什么",
    flow: Annotated[
        Literal["", "feature", "issue"],
        Field(description="Optional explicit workflow flow."),
    ] = "",
    slug: Annotated[str, "Optional workflow slug."] = "",
    latest: Annotated[bool, "Use the latest matching workflow."] = True,
    include_fixtures: Annotated[bool, "Allow fixture workflows to be considered."] = False,
) -> CallToolResult:
    args = ["--mode", "explain", "--request", str(request).strip() or "现在下一步该做什么"]
    if flow:
        args.extend(["--flow", flow])
    if str(slug).strip():
        args.extend(["--slug", str(slug).strip()])
    if latest:
        args.append("--latest")
    if include_fixtures:
        args.append("--include-fixtures")
    return _call_runtime_tool("codecgc.explain", "entry_codecgc_workflow.py", *args)


@mcp.tool(
    name="codecgc.review",
    description="Review a CodeCGC execution audit and write the decision back to workflow artifacts.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_review(
    audit_file: Annotated[str, "Execution audit JSON file path."],
    decision: Annotated[
        Literal["accepted", "changes-requested"],
        Field(description="Requested review decision."),
    ],
    risk: Annotated[list[str], Field(description="Optional remaining risks to record.")] = [],
    next_step: Annotated[str, "Optional next-step text to record."] = "",
    force: Annotated[bool, "Allow overwriting an existing review writeback."] = False,
) -> CallToolResult:
    args = ["--audit-file", str(audit_file).strip(), "--decision", decision]
    _append_repeated_flag(args, "--risk", risk)
    if str(next_step).strip():
        args.extend(["--next-step", str(next_step).strip()])
    if force:
        args.append("--force")
    return _call_runtime_tool("codecgc.review", "review_codecgc_workflow.py", *args)


@mcp.tool(
    name="codecgc.history",
    description="Read recent CodeCGC workflow history across feature and issue flows.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_history(
    flow: Annotated[
        Literal["all", "feature", "issue"],
        Field(description="Workflow flow filter."),
    ] = "all",
    status: Annotated[str, "Workflow status filter."] = "all",
    last: Annotated[int, "Maximum number of records to return."] = 10,
    include_fixtures: Annotated[bool, "Include fixture workflows."] = False,
) -> CallToolResult:
    args = ["--flow", flow, "--status", str(status).strip() or "all", "--last", str(int(last)), "--format", "json"]
    if include_fixtures:
        args.append("--include-fixtures")
    return _call_runtime_tool("codecgc.history", "audit_codecgc_workflow_history.py", *args)


@mcp.tool(
    name="codecgc.route",
    description="Route an existing CodeCGC workflow to the recommended next command.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_route(
    flow: Annotated[
        Literal["feature", "issue"],
        Field(description="Workflow flow."),
    ],
    slug: Annotated[str, "Workflow slug."],
) -> CallToolResult:
    return _call_runtime_tool("codecgc.route", "route_codecgc_workflow.py", "--flow", flow, "--slug", str(slug).strip())


@mcp.tool(
    name="codecgc.plan",
    description="Plan or repair a CodeCGC feature or issue workflow scaffold.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_plan(
    flow: Annotated[
        Literal["feature", "issue"],
        Field(description="Workflow flow."),
    ],
    slug: Annotated[str, "Workflow slug."],
    summary: Annotated[str, "Planning summary."],
    date: Annotated[str, "Optional workflow date, defaults to current date in runtime."] = "",
    target_paths: Annotated[list[str], Field(description="Target paths for this workflow.")] = [],
    kind: Annotated[
        Literal["auto", "frontend", "backend"],
        Field(description="Routing kind."),
    ] = "auto",
    goal: Annotated[str, "Optional goal text."] = "",
    context: Annotated[list[str], Field(description="Optional context notes.")] = [],
    user_story: Annotated[str, "Optional user story."] = "",
    in_scope: Annotated[list[str], Field(description="In-scope items.")] = [],
    out_of_scope: Annotated[list[str], Field(description="Out-of-scope items.")] = [],
    acceptance: Annotated[list[str], Field(description="Acceptance criteria.")] = [],
    risk: Annotated[list[str], Field(description="Risk items.")] = [],
    dependency: Annotated[list[str], Field(description="Dependencies.")] = [],
    assumption: Annotated[list[str], Field(description="Assumptions.")] = [],
    open_question: Annotated[list[str], Field(description="Open questions.")] = [],
    validation: Annotated[list[str], Field(description="Validation steps.")] = [],
    rollback: Annotated[list[str], Field(description="Rollback notes.")] = [],
    symptom: Annotated[str, "Issue symptom."] = "",
    reproduction: Annotated[str, "Issue reproduction."] = "",
    expected: Annotated[str, "Expected behavior."] = "",
    actual: Annotated[str, "Actual behavior."] = "",
    root_cause: Annotated[str, "Root cause note."] = "",
    preferred_fix: Annotated[str, "Preferred fix note."] = "",
    rejected_fix: Annotated[str, "Rejected fix note."] = "",
    artifact_class: Annotated[
        Literal["product", "fixture"],
        Field(description="Artifact class."),
    ] = "product",
    force: Annotated[bool, "Allow overwriting scaffold state when needed."] = False,
) -> CallToolResult:
    args = ["--flow", flow, "--slug", str(slug).strip(), "--summary", str(summary).strip()]
    if str(date).strip():
        args.extend(["--date", str(date).strip()])
    _append_repeated_flag(args, "--target-path", target_paths)
    if kind:
        args.extend(["--kind", kind])
    if str(goal).strip():
        args.extend(["--goal", str(goal).strip()])
    _append_repeated_flag(args, "--context", context)
    if str(user_story).strip():
        args.extend(["--user-story", str(user_story).strip()])
    _append_repeated_flag(args, "--in-scope", in_scope)
    _append_repeated_flag(args, "--out-of-scope", out_of_scope)
    _append_repeated_flag(args, "--acceptance", acceptance)
    _append_repeated_flag(args, "--risk", risk)
    _append_repeated_flag(args, "--dependency", dependency)
    _append_repeated_flag(args, "--assumption", assumption)
    _append_repeated_flag(args, "--open-question", open_question)
    _append_repeated_flag(args, "--validation", validation)
    _append_repeated_flag(args, "--rollback", rollback)
    if str(symptom).strip():
        args.extend(["--symptom", str(symptom).strip()])
    if str(reproduction).strip():
        args.extend(["--reproduction", str(reproduction).strip()])
    if str(expected).strip():
        args.extend(["--expected", str(expected).strip()])
    if str(actual).strip():
        args.extend(["--actual", str(actual).strip()])
    if str(root_cause).strip():
        args.extend(["--root-cause", str(root_cause).strip()])
    if str(preferred_fix).strip():
        args.extend(["--preferred-fix", str(preferred_fix).strip()])
    if str(rejected_fix).strip():
        args.extend(["--rejected-fix", str(rejected_fix).strip()])
    args.extend(["--artifact-class", artifact_class])
    if force:
        args.append("--force")
    return _call_runtime_tool("codecgc.plan", "plan_codecgc_workflow.py", *args)


@mcp.tool(
    name="codecgc.build",
    description="Execute a CodeCGC feature step through the existing runtime.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_build(
    slug: Annotated[str, "Feature workflow slug."],
    step_number: Annotated[int | None, "Optional explicit step number."] = None,
    checklist_file: Annotated[str, "Optional checklist file path."] = "",
    audit_root: Annotated[str, "Optional audit root path."] = "",
    timeout_seconds: Annotated[int, "Execution timeout in seconds."] = 120,
    session_id: Annotated[str, "Optional reusable executor session id."] = "",
    dry_run: Annotated[bool, "Avoid real executor dispatch."] = False,
    return_all_messages: Annotated[bool, "Return executor event logs when available."] = False,
) -> CallToolResult:
    args = ["--slug", str(slug).strip(), "--timeout-seconds", str(int(timeout_seconds))]
    if step_number is not None:
        args.extend(["--step-number", str(int(step_number))])
    if str(checklist_file).strip():
        args.extend(["--checklist-file", str(checklist_file).strip()])
    if str(audit_root).strip():
        args.extend(["--audit-root", str(audit_root).strip()])
    if str(session_id).strip():
        args.extend(["--session-id", str(session_id).strip()])
    if dry_run:
        args.append("--dry-run")
    if return_all_messages:
        args.append("--return-all-messages")
    return _call_runtime_tool("codecgc.build", "run_codecgc_build.py", *args)


@mcp.tool(
    name="codecgc.fix",
    description="Execute a CodeCGC issue fix step through the existing runtime.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_fix(
    slug: Annotated[str, "Issue workflow slug."],
    step_number: Annotated[int | None, "Optional explicit step number."] = None,
    checklist_file: Annotated[str, "Optional checklist file path."] = "",
    audit_root: Annotated[str, "Optional audit root path."] = "",
    timeout_seconds: Annotated[int, "Execution timeout in seconds."] = 120,
    session_id: Annotated[str, "Optional reusable executor session id."] = "",
    dry_run: Annotated[bool, "Avoid real executor dispatch."] = False,
    return_all_messages: Annotated[bool, "Return executor event logs when available."] = False,
) -> CallToolResult:
    args = ["--slug", str(slug).strip(), "--timeout-seconds", str(int(timeout_seconds))]
    if step_number is not None:
        args.extend(["--step-number", str(int(step_number))])
    if str(checklist_file).strip():
        args.extend(["--checklist-file", str(checklist_file).strip()])
    if str(audit_root).strip():
        args.extend(["--audit-root", str(audit_root).strip()])
    if str(session_id).strip():
        args.extend(["--session-id", str(session_id).strip()])
    if dry_run:
        args.append("--dry-run")
    if return_all_messages:
        args.append("--return-all-messages")
    return _call_runtime_tool("codecgc.fix", "run_codecgc_fix.py", *args)


@mcp.tool(
    name="codecgc.test",
    description="Execute a CodeCGC test step through the existing runtime.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_test(
    flow: Annotated[
        Literal["feature", "issue"],
        Field(description="Workflow flow."),
    ],
    slug: Annotated[str, "Workflow slug."],
    step_number: Annotated[int | None, "Optional explicit step number."] = None,
    checklist_file: Annotated[str, "Optional checklist file path."] = "",
    audit_root: Annotated[str, "Optional audit root path."] = "",
    timeout_seconds: Annotated[int, "Execution timeout in seconds."] = 120,
    session_id: Annotated[str, "Optional reusable executor session id."] = "",
    dry_run: Annotated[bool, "Avoid real executor dispatch."] = False,
    return_all_messages: Annotated[bool, "Return executor event logs when available."] = False,
) -> CallToolResult:
    args = ["--flow", flow, "--slug", str(slug).strip(), "--timeout-seconds", str(int(timeout_seconds))]
    if step_number is not None:
        args.extend(["--step-number", str(int(step_number))])
    if str(checklist_file).strip():
        args.extend(["--checklist-file", str(checklist_file).strip()])
    if str(audit_root).strip():
        args.extend(["--audit-root", str(audit_root).strip()])
    if str(session_id).strip():
        args.extend(["--session-id", str(session_id).strip()])
    if dry_run:
        args.append("--dry-run")
    if return_all_messages:
        args.append("--return-all-messages")
    return _call_runtime_tool("codecgc.test", "run_codecgc_test.py", *args)


@mcp.tool(
    name="codecgc.package_audit",
    description="Audit whether the published CodeCGC package contains all required runtime files.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_package_audit(
    format: Annotated[
        Literal["summary", "json"],
        Field(description="Output format."),
    ] = "json",
) -> CallToolResult:
    return _call_runtime_tool("codecgc.package_audit", "audit_codecgc_package_runtime.py", "--format", format)


def _external_capability_runtime_args(view: str, workspace: str, format: str) -> list[str]:
    args = ["--view", view, "--format", format]
    normalized_workspace = _normalize_workspace(workspace)
    if normalized_workspace:
        args.extend(["--workspace", normalized_workspace])
    return args


@mcp.tool(
    name="codecgc.external_audit",
    description="Audit external capability registration policy and locally observed MCP servers.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_external_audit(
    workspace: Annotated[str, "Optional target workspace root."] = "",
    format: Annotated[
        Literal["summary", "json"],
        Field(description="Output format."),
    ] = "json",
) -> CallToolResult:
    args = _external_capability_runtime_args("audit", workspace, format)
    return _call_runtime_tool("codecgc.external_audit", "audit_codecgc_external_capabilities.py", *args)


@mcp.tool(
    name="codecgc.external_status",
    description="Render the concise external capability status panel for day-to-day checks.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_external_status(
    workspace: Annotated[str, "Optional target workspace root."] = "",
    format: Annotated[
        Literal["summary", "json"],
        Field(description="Output format."),
    ] = "summary",
) -> CallToolResult:
    args = _external_capability_runtime_args("status", workspace, format)
    return _call_runtime_tool("codecgc.external_status", "audit_codecgc_external_capabilities.py", *args)


@mcp.tool(
    name="codecgc.release_readiness",
    description="Run the combined CodeCGC release, maintenance, and ops readiness audit.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_release_readiness(
    workspace: Annotated[str, "Optional target workspace root."] = "",
    format: Annotated[
        Literal["summary", "json"],
        Field(description="Output format."),
    ] = "json",
) -> CallToolResult:
    args = ["--format", format]
    normalized_workspace = _normalize_workspace(workspace)
    if normalized_workspace:
        args.extend(["--workspace", normalized_workspace])
    return _call_runtime_tool("codecgc.release_readiness", "audit_codecgc_release_readiness.py", *args)


@mcp.tool(
    name="codecgc.lifecycle",
    description="Audit CodeCGC lifecycle coverage across roadmap, workflows, and execution artifacts.",
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def codecgc_lifecycle(
    format: Annotated[
        Literal["summary", "json"],
        Field(description="Output format."),
    ] = "json",
) -> CallToolResult:
    return _call_runtime_tool("codecgc.lifecycle", "audit_codecgc_lifecycle.py", "--format", format)


def run() -> None:
    """Start the MCP server over stdio transport."""
    mcp.run(transport="stdio")
