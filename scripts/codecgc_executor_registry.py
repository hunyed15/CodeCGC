from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1]


def resolve_python_command() -> str:
    override = os.environ.get("CODECGC_PYTHON_COMMAND", "").strip()
    if override:
        return override
    return sys.executable


def build_executor_registry() -> dict[str, dict[str, Any]]:
    python_command = resolve_python_command()
    return {
        "backend": {
            "target": "backend",
            "mcp_server_name": "codex",
            "routing_executor": "codexmcp",
            "tool_name": "implement_backend_task",
            "python_module": "codexmcp.cli",
            "pythonpath": str(WORKSPACE / "codexmcp" / "src"),
            "python_command": python_command,
        },
        "frontend": {
            "target": "frontend",
            "mcp_server_name": "gemini",
            "routing_executor": "geminimcp",
            "tool_name": "implement_frontend_task",
            "python_module": "geminimcp.cli",
            "pythonpath": str(WORKSPACE / "geminimcp" / "src"),
            "python_command": python_command,
        },
    }


def get_executor_config(target: str) -> dict[str, Any]:
    registry = build_executor_registry()
    if target not in registry:
        raise ValueError(f"Unsupported target: {target}")
    return registry[target]


def build_executor_env(target: str) -> dict[str, str]:
    env = dict(os.environ)
    config = get_executor_config(target)
    env["PYTHONPATH"] = str(config["pythonpath"])
    return env
