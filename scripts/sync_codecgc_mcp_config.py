import os
import json
from pathlib import Path

from codecgc_executor_registry import build_executor_registry


WORKSPACE = Path(__file__).resolve().parents[1]
MCP_CONFIG_PATH = WORKSPACE / ".mcp.json"


def build_runtime_pythonpath(*extra_paths: Path) -> str:
    paths = [str(WORKSPACE / "scripts"), *(str(path) for path in extra_paths)]
    return os.pathsep.join(paths)


def build_mcp_config() -> dict:
    registry = build_executor_registry()
    servers: dict[str, dict] = {}

    servers["codecgc"] = {
        "command": str(next(iter(registry.values()))["python_command"]),
        "args": ["-m", "codecgcmcp.cli"],
        "env": {
            "PYTHONPATH": build_runtime_pythonpath(WORKSPACE / "codecgcmcp" / "src"),
        },
    }

    for config in registry.values():
        servers[str(config["mcp_server_name"])] = {
            "command": str(config["python_command"]),
            "args": ["-m", str(config["python_module"])],
            "env": {
                "PYTHONPATH": build_runtime_pythonpath(
                    WORKSPACE / "codecgcmcp" / "src",
                    Path(str(config["pythonpath"])),
                ),
            },
        }

    return {"mcpServers": servers}


def write_mcp_config(target_path: Path) -> Path:
    config = build_mcp_config()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target_path


def main() -> int:
    write_mcp_config(MCP_CONFIG_PATH)
    print(json.dumps({"success": True, "path": str(MCP_CONFIG_PATH)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
