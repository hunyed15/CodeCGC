import json
import os

import pytest

from install_codecgc import DEFAULT_ALLOWED_TOOLS
from install_codecgc import EDIT_GUARDRAIL_MATCHER
from install_codecgc import PROJECT_HOOK_PATH
from install_codecgc import PROJECT_ONBOARDING_MARKER
from install_codecgc import PROJECT_WORKFLOW_DIRS
from install_codecgc import build_workspace_hook_command
from install_codecgc import build_user_hook_command
from install_codecgc import collect_project_status
from install_codecgc import collect_start_status
from install_codecgc import collect_user_status
from install_codecgc import ensure_workspace_workflow_dirs
from install_codecgc import get_user_claude_paths
from install_codecgc import get_workspace_paths
from install_codecgc import install_local_runtime
from install_codecgc import merge_hook_settings
from install_codecgc import onboarding_file_is_valid
from install_codecgc import workspace_workflow_dirs_ready


def _write_user_surface(root, mcp_payload):
    paths = get_user_claude_paths(str(root))
    paths["root"].mkdir(parents=True, exist_ok=True)
    paths["hooks_dir"].mkdir(parents=True, exist_ok=True)

    settings_payload = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": EDIT_GUARDRAIL_MATCHER,
                    "hooks": [
                        {
                            "type": "command",
                            "command": build_user_hook_command(paths),
                        }
                    ],
                }
            ]
        },
        "permissions": {
            "allow": list(DEFAULT_ALLOWED_TOOLS),
        },
    }
    paths["settings"].write_text(json.dumps(settings_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["mcp"].write_text(json.dumps(mcp_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["hook_script"].write_text(PROJECT_HOOK_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    return paths


def _server_env(pythonpath, workspace_root):
    return {
        "PYTHONPATH": pythonpath,
        "CODECGC_WORKSPACE_ROOT": str(workspace_root),
    }


@pytest.mark.unit
def test_collect_user_status_accepts_runtime_equivalent_mcp(tmp_path):
    runtime_root = tmp_path / "external-codecgc"
    pythonpath = os.pathsep.join(
        [
            str(runtime_root / "scripts"),
            str(runtime_root / "codecgcmcp" / "src"),
        ]
    )
    codex_pythonpath = os.pathsep.join(
        [
            str(runtime_root / "scripts"),
            str(runtime_root / "codecgcmcp" / "src"),
            str(runtime_root / "codexmcp" / "src"),
        ]
    )
    gemini_pythonpath = os.pathsep.join(
        [
            str(runtime_root / "scripts"),
            str(runtime_root / "codecgcmcp" / "src"),
            str(runtime_root / "geminimcp" / "src"),
        ]
    )
    payload = {
        "mcpServers": {
            "codecgc": {
                "command": "C:\\Python314\\python.exe",
                "args": ["-m", "codecgcmcp.cli"],
                "env": _server_env(pythonpath, runtime_root),
            },
            "codex": {
                "command": "C:\\Python314\\python.exe",
                "args": ["-m", "codexmcp.cli"],
                "env": _server_env(codex_pythonpath, runtime_root),
            },
            "gemini": {
                "command": "C:\\Python314\\python.exe",
                "args": ["-m", "geminimcp.cli"],
                "env": _server_env(gemini_pythonpath, runtime_root),
            },
        }
    }

    status = collect_user_status(_write_user_surface(tmp_path / "user-home", payload))

    assert status["ready"] is True
    assert status["mcp_matches_expected"] is True
    assert status["mcp_matches_expected_exact"] is False
    assert status["mcp_matches_runtime_shape"] is True
    assert status["missing_or_outdated"] == []


@pytest.mark.unit
def test_collect_user_status_rejects_invalid_runtime_shape(tmp_path):
    runtime_root = tmp_path / "external-codecgc"
    payload = {
        "mcpServers": {
            "codecgc": {
                "command": "C:\\Python314\\python.exe",
                "args": ["-m", "codecgcmcp.cli"],
                "env": _server_env(os.pathsep.join([str(runtime_root / "scripts")]), runtime_root),
            },
            "codex": {
                "command": "C:\\Python314\\python.exe",
                "args": ["-m", "codexmcp.cli"],
                "env": _server_env(os.pathsep.join([str(runtime_root / "scripts")]), runtime_root),
            },
            "gemini": {
                "command": "C:\\Python314\\python.exe",
                "args": ["-m", "geminimcp.cli"],
                "env": _server_env(os.pathsep.join([str(runtime_root / "scripts")]), runtime_root),
            },
        }
    }

    status = collect_user_status(_write_user_surface(tmp_path / "user-home", payload))

    assert status["ready"] is False
    assert status["mcp_matches_expected"] is False
    assert status["mcp_matches_runtime_shape"] is False
    assert "mcp_json" in status["missing_or_outdated"]


@pytest.mark.unit
def test_ensure_workspace_workflow_dirs_creates_expected_project_surface(tmp_path):
    created = ensure_workspace_workflow_dirs(tmp_path)

    assert len(created) == len(PROJECT_WORKFLOW_DIRS)
    assert workspace_workflow_dirs_ready(tmp_path) is True
    for relative_path in PROJECT_WORKFLOW_DIRS:
        assert (tmp_path / relative_path).is_dir()


@pytest.mark.unit
def test_local_install_writes_project_onboarding_and_start_command(tmp_path):
    result = install_local_runtime(str(tmp_path))

    onboarding_path = tmp_path / "codecgc" / "START_HERE.md"
    start_command_path = tmp_path / ".claude" / "commands" / "cgc-start.md"
    external_status_command_path = tmp_path / ".claude" / "commands" / "cgc-external-status.md"

    assert result["summary"]["recommended_next_action"] == "cgc-start"
    assert result["onboarding_file"] == str(onboarding_path)
    assert onboarding_path.exists()
    assert start_command_path.exists()
    assert external_status_command_path.exists()
    assert onboarding_file_is_valid(onboarding_path) is True
    assert PROJECT_ONBOARDING_MARKER in onboarding_path.read_text(encoding="utf-8")
    assert "codecgc.start" in start_command_path.read_text(encoding="utf-8")
    assert "codecgc.external_status" in external_status_command_path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_project_status_requires_project_onboarding(tmp_path):
    install_local_runtime(str(tmp_path))
    paths = get_workspace_paths(str(tmp_path))

    ready_status = collect_project_status(paths)
    assert ready_status["ready"] is True
    assert ready_status["onboarding_ready"] is True

    paths["onboarding_file"].unlink()
    missing_status = collect_project_status(paths)

    assert missing_status["ready"] is False
    assert missing_status["onboarding_ready"] is False
    assert "onboarding_file" in missing_status["missing_or_outdated"]


@pytest.mark.unit
def test_start_status_reports_first_run_actions(tmp_path):
    missing = collect_start_status(str(tmp_path))
    assert missing["summary"]["ready"] is False
    assert "cgc-install --mode local" in missing["summary"]["recommended_next_action"]

    install_local_runtime(str(tmp_path))
    ready = collect_start_status(str(tmp_path))

    assert ready["summary"]["ready"] is True
    assert ready["summary"]["recommended_next_action"] == "cgc-status"
    assert "/cgc <你的需求>" in ready["summary"]["quick_actions"]
    assert ready["onboarding"]["relative_path"] == "codecgc/START_HERE.md"


@pytest.mark.unit
def test_merge_hook_settings_migrates_legacy_edit_write_matcher():
    command = (
        "powershell -ExecutionPolicy Bypass -Command "
        "\"$env:CODECGC_PACKAGE_ROOT='C:\\CodeCGC'; "
        "$env:CODECGC_WORKSPACE_ROOT='D:\\App'; "
        "& .claude/hooks/route-edit.ps1\""
    )
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Edit|Write",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "powershell -ExecutionPolicy Bypass -File .claude/hooks/route-edit.ps1",
                        }
                    ],
                }
            ]
        }
    }

    merged, changed = merge_hook_settings(settings, command)

    assert changed is True
    pre_tool_use = merged["hooks"]["PreToolUse"]
    assert len(pre_tool_use) == 1
    assert pre_tool_use[0]["matcher"] == EDIT_GUARDRAIL_MATCHER
    assert pre_tool_use[0]["hooks"] == [{"type": "command", "command": command}]


@pytest.mark.unit
def test_workspace_hook_command_pins_package_and_workspace_roots(tmp_path):
    workspace_paths = {"root": tmp_path}

    command = build_workspace_hook_command(workspace_paths)

    assert "CODECGC_PACKAGE_ROOT" in command
    assert "CODECGC_WORKSPACE_ROOT" in command
    assert str(tmp_path) in command
    assert ".claude/hooks/route-edit.ps1" in command


@pytest.mark.unit
def test_hook_script_uses_project_mcp_python_command():
    hook_text = PROJECT_HOOK_PATH.read_text(encoding="utf-8")

    assert "CODECGC_PYTHON_COMMAND" in hook_text
    assert ".mcp.json" in hook_text
    assert "mcpServers.codecgc.command" in hook_text
