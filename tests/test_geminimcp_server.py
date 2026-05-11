import json
from pathlib import Path

import pytest

from geminimcp import server


@pytest.mark.unit
def test_execute_gemini_session_uses_non_interactive_edit_mode(monkeypatch, tmp_path):
    captured = {}

    def fake_run_shell_command(cmd, cwd=None, timeout_seconds=0, env=None):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["timeout_seconds"] = timeout_seconds
        captured["env"] = env
        yield json.dumps({"type": "init", "session_id": "gemini-session"})
        yield json.dumps({"type": "message", "role": "assistant", "content": "OK"})
        yield json.dumps({"type": "result", "status": "success"})

    monkeypatch.setattr(server, "run_shell_command", fake_run_shell_command)

    result = server._execute_gemini_session(
        prompt="Write a file.",
        cd=tmp_path,
        sandbox=False,
        session_id="",
        return_all_messages=False,
        model="",
        timeout_seconds=123,
    )

    assert result["success"] is True
    assert result["SESSION_ID"] == "gemini-session"
    assert "--approval-mode" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--approval-mode") + 1] == "yolo"
    assert "--prompt" in captured["cmd"]
    assert captured["env"]["GEMINI_CLI_TRUST_WORKSPACE"] == "true"
    assert captured["timeout_seconds"] == 123
    assert captured["cwd"] == tmp_path.absolute().as_posix()
    assert "--policy" not in captured["cmd"]


@pytest.mark.unit
def test_execute_gemini_session_uses_project_policy_when_present(monkeypatch, tmp_path):
    captured = {}
    policy_path = tmp_path / ".gemini" / "policies" / "codecgc-policy.toml"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text('[[rule]]\ntoolName = "write_file"\ndecision = "allow"\n', encoding="utf-8")

    def fake_run_shell_command(cmd, cwd=None, timeout_seconds=0, env=None):
        captured["cmd"] = cmd
        yield json.dumps({"type": "init", "session_id": "gemini-session"})
        yield json.dumps({"type": "message", "role": "assistant", "content": "OK"})

    monkeypatch.setattr(server, "run_shell_command", fake_run_shell_command)

    result = server._execute_gemini_session(
        prompt="Write a file.",
        cd=tmp_path,
        sandbox=False,
        session_id="",
        return_all_messages=False,
        model="",
        timeout_seconds=123,
    )

    assert result["success"] is True
    assert "--policy" in captured["cmd"]
    assert captured["cmd"][captured["cmd"].index("--policy") + 1] == policy_path.absolute().as_posix()


@pytest.mark.unit
def test_execute_gemini_session_reports_process_timeout(monkeypatch, tmp_path):
    def fake_run_shell_command(cmd, cwd=None, timeout_seconds=0, env=None):
        raise TimeoutError(f"Gemini CLI timed out after {timeout_seconds} seconds.")
        yield

    monkeypatch.setattr(server, "run_shell_command", fake_run_shell_command)

    result = server._execute_gemini_session(
        prompt="Write a file.",
        cd=tmp_path,
        sandbox=False,
        session_id="",
        return_all_messages=True,
        model="",
        timeout_seconds=1,
    )

    assert result["success"] is False
    assert "[timeout]" in result["error"]
    assert "timed out after 1 seconds" in result["error"]
    assert result["all_messages"] == []
