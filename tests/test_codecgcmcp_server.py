import asyncio
import json
from pathlib import Path

import pytest

from codecgcmcp import server


def _json_content(result):
    assert result.content
    return json.loads(result.content[0].text)


def _run(coro):
    return asyncio.run(coro)


async def _capture_tool_call(monkeypatch, tool_func, *args, **kwargs):
    captured = {}

    def fake_call_runtime_tool(tool_name, script_name, *runtime_args, requested_format=""):
        captured["tool_name"] = tool_name
        captured["script_name"] = script_name
        captured["args"] = list(runtime_args)
        captured["requested_format"] = requested_format
        return server._as_tool_result(
            tool_name,
            {
                "success": True,
                "script_name": script_name,
                "args": list(runtime_args),
                "requested_format": requested_format,
            },
        )

    monkeypatch.setattr(server, "_call_runtime_tool", fake_call_runtime_tool)
    result = await tool_func(*args, **kwargs)
    return captured, _json_content(result)


@pytest.mark.unit
def test_tool_result_uses_stable_envelope_for_success():
    result = server._as_tool_result("codecgc.status", {"success": True, "mode": "status"})
    payload = _json_content(result)

    assert result.isError is False
    assert payload["success"] is True
    assert payload["tool"] == "codecgc.status"
    assert payload["payload"] == {"success": True, "mode": "status"}
    assert payload["error"] is None
    assert payload["meta"]["contract_version"] == server.MCP_CONTRACT_VERSION
    assert payload["meta"]["response_shape"] == "codecgc.mcp.tool_result"


@pytest.mark.unit
def test_tool_result_normalizes_runtime_failure():
    runtime_payload = {"success": False, "error": "boom", "returncode": 7}
    error = server._payload_error("codecgc.status", "install_codecgc.py", ("--mode", "status"), runtime_payload)

    result = server._as_tool_result("codecgc.status", runtime_payload, error)
    payload = _json_content(result)

    assert result.isError is True
    assert payload["success"] is False
    assert payload["payload"] == runtime_payload
    assert payload["error"]["type"] == "RuntimeScriptError"
    assert payload["error"]["category"] == "runtime-script-failed"
    assert payload["error"]["message"] == "boom"
    assert payload["error"]["tool"] == "codecgc.status"
    assert payload["error"]["script"] == "install_codecgc.py"
    assert payload["error"]["args"] == ["--mode", "status"]
    assert payload["error"]["returncode"] == 7


@pytest.mark.unit
def test_call_runtime_tool_adds_requested_format(monkeypatch):
    def fake_run_json_script(script_name, *args):
        return {"success": True, "script_name": script_name, "args": list(args)}

    monkeypatch.setattr(server, "run_json_script", fake_run_json_script)

    result = server._call_runtime_tool(
        "codecgc.install",
        "install_codecgc.py",
        "--mode",
        "status",
        requested_format="summary",
    )
    payload = _json_content(result)

    assert result.isError is False
    assert payload["success"] is True
    assert payload["payload"]["requested_format"] == "summary"
    assert payload["payload"]["script_name"] == "install_codecgc.py"
    assert payload["payload"]["args"] == ["--mode", "status"]


@pytest.mark.unit
def test_call_runtime_tool_wraps_exceptions(monkeypatch):
    def fake_run_json_script(script_name, *args):
        raise ValueError("invalid runtime json")

    monkeypatch.setattr(server, "run_json_script", fake_run_json_script)

    result = server._call_runtime_tool("codecgc.status", "install_codecgc.py", "--mode", "status")
    payload = _json_content(result)

    assert result.isError is True
    assert payload["success"] is False
    assert payload["tool"] == "codecgc.status"
    assert payload["payload"]["success"] is False
    assert payload["error"]["type"] == "ValueError"
    assert payload["error"]["category"] == "runtime-json-invalid"
    assert payload["error"]["message"] == "invalid runtime json"
    assert payload["error"]["script"] == "install_codecgc.py"
    assert payload["error"]["args"] == ["--mode", "status"]


@pytest.mark.unit
def test_payload_error_uses_runtime_payload_category():
    runtime_payload = {"success": False, "error": "blocked", "error_category": "policy-blocked"}

    error = server._payload_error("codecgc.review", "review_codecgc_workflow.py", (), runtime_payload)

    assert error["category"] == "policy-blocked"


@pytest.mark.unit
def test_install_maps_to_json_runtime_args(monkeypatch):
    workspace = "workspace-example"

    captured, payload = _run(_capture_tool_call(
        monkeypatch,
        server.codecgc_install,
        mode="user-dry-run",
        format="summary",
        workspace=workspace,
        user_root="C:\\Users\\Example\\.claude",
    ))

    assert captured["tool_name"] == "codecgc.install"
    assert captured["script_name"] == "install_codecgc.py"
    assert captured["requested_format"] == "summary"
    assert captured["args"] == [
        "--mode",
        "user-dry-run",
        "--format",
        "json",
        "--workspace",
        str(Path(workspace).resolve()),
        "--user-root",
        "C:\\Users\\Example\\.claude",
    ]
    assert payload["success"] is True


@pytest.mark.unit
def test_entry_maps_all_optional_flags(monkeypatch):
    captured, _payload = _run(_capture_tool_call(
        monkeypatch,
        server.codecgc_entry,
        request="继续登录功能",
        mode="continue",
        flow="feature",
        slug="login-ui",
        latest=True,
        include_fixtures=True,
        auto_dispatch=True,
        dry_run=True,
        audit_file="codecgc/execution/login-ui-step-1.json",
        decision="accepted",
    ))

    assert captured["tool_name"] == "codecgc.entry"
    assert captured["script_name"] == "entry_codecgc_workflow.py"
    assert captured["args"] == [
        "--mode",
        "continue",
        "--request",
        "继续登录功能",
        "--flow",
        "feature",
        "--slug",
        "login-ui",
        "--latest",
        "--include-fixtures",
        "--auto-dispatch",
        "--dry-run",
        "--audit-file",
        "codecgc/execution/login-ui-step-1.json",
        "--decision",
        "accepted",
    ]


@pytest.mark.unit
def test_continue_and_explain_use_defaults(monkeypatch):
    continue_call, _ = _run(_capture_tool_call(monkeypatch, server.codecgc_continue, request=""))
    explain_call, _ = _run(_capture_tool_call(monkeypatch, server.codecgc_explain, request=""))

    assert continue_call["args"] == ["--mode", "continue", "--request", "继续刚刚的工作", "--latest"]
    assert explain_call["args"] == ["--mode", "explain", "--request", "现在下一步该做什么", "--latest"]


@pytest.mark.unit
def test_review_maps_repeated_risks_and_force(monkeypatch):
    captured, _payload = _run(_capture_tool_call(
        monkeypatch,
        server.codecgc_review,
        audit_file="codecgc/execution/login-ui-step-1.json",
        decision="changes-requested",
        risk=["missing test", "scope risk"],
        next_step="补测试",
        force=True,
    ))

    assert captured["tool_name"] == "codecgc.review"
    assert captured["script_name"] == "review_codecgc_workflow.py"
    assert captured["args"] == [
        "--audit-file",
        "codecgc/execution/login-ui-step-1.json",
        "--decision",
        "changes-requested",
        "--risk",
        "missing test",
        "--risk",
        "scope risk",
        "--next-step",
        "补测试",
        "--force",
    ]


@pytest.mark.unit
def test_build_fix_and_test_map_execution_args(monkeypatch):
    build_call, _ = _run(_capture_tool_call(
        monkeypatch,
        server.codecgc_build,
        slug="login-ui",
        step_number=2,
        checklist_file="codecgc/features/login/checklist.yaml",
        audit_root="codecgc/execution",
        timeout_seconds=300,
        session_id="session-1",
        dry_run=True,
        return_all_messages=True,
    ))
    fix_call, _ = _run(_capture_tool_call(monkeypatch, server.codecgc_fix, slug="bug", timeout_seconds=60))
    test_call, _ = _run(_capture_tool_call(
        monkeypatch,
        server.codecgc_test,
        flow="issue",
        slug="bug",
        step_number=3,
        timeout_seconds=90,
        dry_run=True,
    ))

    assert build_call["script_name"] == "run_codecgc_build.py"
    assert build_call["args"] == [
        "--slug",
        "login-ui",
        "--timeout-seconds",
        "300",
        "--step-number",
        "2",
        "--checklist-file",
        "codecgc/features/login/checklist.yaml",
        "--audit-root",
        "codecgc/execution",
        "--session-id",
        "session-1",
        "--dry-run",
        "--return-all-messages",
    ]
    assert fix_call["script_name"] == "run_codecgc_fix.py"
    assert fix_call["args"] == ["--slug", "bug", "--timeout-seconds", "60"]
    assert test_call["script_name"] == "run_codecgc_test.py"
    assert test_call["args"] == [
        "--flow",
        "issue",
        "--slug",
        "bug",
        "--timeout-seconds",
        "90",
        "--step-number",
        "3",
        "--dry-run",
    ]


@pytest.mark.unit
def test_readonly_tools_map_expected_scripts(monkeypatch):
    workspace = "workspace-example"

    start_call, _ = _run(_capture_tool_call(monkeypatch, server.codecgc_start, workspace=workspace))
    status_call, _ = _run(_capture_tool_call(monkeypatch, server.codecgc_status, workspace=workspace))
    doctor_call, _ = _run(_capture_tool_call(monkeypatch, server.codecgc_doctor))
    external_audit_call, _ = _run(_capture_tool_call(monkeypatch, server.codecgc_external_audit, workspace=workspace, format="summary"))
    external_status_call, _ = _run(_capture_tool_call(monkeypatch, server.codecgc_external_status, workspace=workspace))
    history_call, _ = _run(_capture_tool_call(
        monkeypatch,
        server.codecgc_history,
        flow="feature",
        status="open",
        last=5,
        include_fixtures=True,
    ))
    route_call, _ = _run(_capture_tool_call(monkeypatch, server.codecgc_route, flow="issue", slug="bug"))
    release_call, _ = _run(_capture_tool_call(
        monkeypatch,
        server.codecgc_release_readiness,
        workspace=workspace,
        format="summary",
    ))

    assert start_call["script_name"] == "install_codecgc.py"
    assert start_call["args"] == ["--mode", "start", "--format", "json", "--workspace", str(Path(workspace).resolve())]
    assert status_call["script_name"] == "install_codecgc.py"
    assert status_call["args"] == ["--mode", "status", "--format", "json", "--workspace", str(Path(workspace).resolve())]
    assert doctor_call["args"] == ["--mode", "doctor", "--format", "json"]
    assert external_audit_call["script_name"] == "audit_codecgc_external_capabilities.py"
    assert external_audit_call["args"] == [
        "--view",
        "audit",
        "--format",
        "summary",
        "--workspace",
        str(Path(workspace).resolve()),
    ]
    assert external_status_call["script_name"] == "audit_codecgc_external_capabilities.py"
    assert external_status_call["args"] == [
        "--view",
        "status",
        "--format",
        "summary",
        "--workspace",
        str(Path(workspace).resolve()),
    ]
    assert history_call["script_name"] == "audit_codecgc_workflow_history.py"
    assert history_call["args"] == [
        "--flow",
        "feature",
        "--status",
        "open",
        "--last",
        "5",
        "--format",
        "json",
        "--include-fixtures",
    ]
    assert route_call["script_name"] == "route_codecgc_workflow.py"
    assert route_call["args"] == ["--flow", "issue", "--slug", "bug"]
    assert release_call["script_name"] == "audit_codecgc_release_readiness.py"
    assert release_call["args"] == ["--format", "summary", "--workspace", str(Path(workspace).resolve())]


@pytest.mark.unit
def test_plan_maps_structured_fields(monkeypatch):
    captured, _payload = _run(_capture_tool_call(
        monkeypatch,
        server.codecgc_plan,
        flow="feature",
        slug="login-ui",
        summary="Login UI",
        date="2026-05-09",
        target_paths=["src/Login.tsx", "src/Login.css"],
        kind="frontend",
        goal="build login",
        context=["ctx"],
        user_story="As a user",
        in_scope=["form"],
        out_of_scope=["auth backend"],
        acceptance=["renders"],
        risk=["css risk"],
        dependency=["design"],
        assumption=["React"],
        open_question=["copy"],
        validation=["npm test"],
        rollback=["revert"],
        artifact_class="fixture",
        force=True,
    ))

    assert captured["script_name"] == "plan_codecgc_workflow.py"
    assert captured["args"] == [
        "--flow",
        "feature",
        "--slug",
        "login-ui",
        "--summary",
        "Login UI",
        "--date",
        "2026-05-09",
        "--target-path",
        "src/Login.tsx",
        "--target-path",
        "src/Login.css",
        "--kind",
        "frontend",
        "--goal",
        "build login",
        "--context",
        "ctx",
        "--user-story",
        "As a user",
        "--in-scope",
        "form",
        "--out-of-scope",
        "auth backend",
        "--acceptance",
        "renders",
        "--risk",
        "css risk",
        "--dependency",
        "design",
        "--assumption",
        "React",
        "--open-question",
        "copy",
        "--validation",
        "npm test",
        "--rollback",
        "revert",
        "--artifact-class",
        "fixture",
        "--force",
    ]
