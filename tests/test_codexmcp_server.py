import json

import pytest

from codexmcp import server


@pytest.mark.unit
def test_execute_codex_session_injects_project_policy_context(monkeypatch, tmp_path):
    captured = {}
    policy_path = tmp_path / ".codex" / "codecgcrc.json"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(
        json.dumps(
            {
                "role": "backend implementation and backend tests",
                "enforcement": {
                    "primary": "CodeCGC MCP backend path validation",
                    "codex_cli": "sandbox and approval flags supplied by codexmcp",
                    "routing_policy": "model-routing.yaml",
                },
                "allowed_path_kinds": ["backend"],
                "denied_path_kinds": ["frontend"],
                "notes": ["Do not edit frontend files."],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def fake_run_shell_command(cmd):
        captured["cmd"] = cmd
        yield json.dumps({"type": "thread.started", "thread_id": "codex-session"})
        yield json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "OK"}})

    monkeypatch.setattr(server, "run_shell_command", fake_run_shell_command)

    result = server._execute_codex_session(
        prompt="Implement API.",
        cd=tmp_path,
        sandbox="workspace-write",
        session_id="",
        skip_git_repo_check=True,
        return_all_messages=False,
        image=[],
        model="",
        yolo=False,
        profile="",
    )

    assert result["success"] is True
    prompt_arg = captured["cmd"][-1]
    assert "Project CodeCGC Codex policy contract:" in prompt_arg
    assert "Do not edit frontend files." in prompt_arg
    assert "User task:" in prompt_arg
    assert "Implement API." in prompt_arg
