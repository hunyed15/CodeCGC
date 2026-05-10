from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .executor_registry import build_executor_registry
from .paths import PACKAGE_ROOT


WORKSPACE = PACKAGE_ROOT
MCP_CONFIG_PATH = WORKSPACE / ".mcp.json"


def build_runtime_pythonpath(*extra_paths: Path) -> str:
    paths = [str(WORKSPACE / "scripts"), *(str(path) for path in extra_paths)]
    return os.pathsep.join(paths)


def _with_workspace_env(env: dict[str, str], workspace_root: Path | None) -> dict[str, str]:
    if workspace_root is None:
        return env
    enriched = dict(env)
    enriched["CODECGC_WORKSPACE_ROOT"] = str(workspace_root.expanduser().resolve())
    return enriched


def build_mcp_config(workspace_root: Path | None = None) -> dict[str, Any]:
    registry = build_executor_registry()
    servers: dict[str, dict[str, Any]] = {}

    servers["codecgc"] = {
        "command": str(next(iter(registry.values()))["python_command"]),
        "args": ["-m", "codecgcmcp.cli"],
        "env": _with_workspace_env(
            {
                "PYTHONPATH": build_runtime_pythonpath(WORKSPACE / "codecgcmcp" / "src"),
            },
            workspace_root,
        ),
    }

    for config in registry.values():
        servers[str(config["mcp_server_name"])] = {
            "command": str(config["python_command"]),
            "args": ["-m", str(config["python_module"])],
            "env": _with_workspace_env(
                {
                    "PYTHONPATH": build_runtime_pythonpath(
                        WORKSPACE / "codecgcmcp" / "src",
                        Path(str(config["pythonpath"])),
                    ),
                },
                workspace_root,
            ),
        }

    return {"mcpServers": servers}


def write_mcp_config(target_path: Path, workspace_root: Path | None = None) -> Path:
    config = build_mcp_config(workspace_root)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target_path


def main() -> int:
    write_mcp_config(MCP_CONFIG_PATH, WORKSPACE)
    print(json.dumps({"success": True, "path": str(MCP_CONFIG_PATH)}, ensure_ascii=False, indent=2))
    return 0
