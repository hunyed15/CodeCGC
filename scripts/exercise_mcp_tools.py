import argparse
import asyncio
import datetime
import json
from pathlib import Path

from codecgc_executor_registry import build_executor_env
from codecgc_executor_registry import get_executor_config
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


WORKSPACE = Path(__file__).resolve().parents[1]


def build_server_params(target: str) -> StdioServerParameters:
    config = get_executor_config(target)
    return StdioServerParameters(
        command=str(config["python_command"]),
        args=["-m", str(config["python_module"])],
        env=build_executor_env(target),
    )


def build_tool_call(target: str) -> tuple[str, dict]:
    if target == "backend":
        return (
            "implement_backend_task",
            {
                "task_id": "exercise-backend-001",
                "task_summary": "Inspect the backend executor contract and return a constrained implementation summary only.",
                "target_paths": ["src/codexmcp/server.py"],
                "constraints": [
                    "Do not edit files outside target_paths.",
                    "Treat this as a dry-run style exercise response.",
                ],
                "acceptance_criteria": [
                    "Return a structured summary payload.",
                    "Do not touch frontend paths.",
                ],
                "cd": str(WORKSPACE / "mcp" / "codexmcp"),
                "sandbox": "read-only",
            },
        )

    if target == "frontend":
        return (
            "implement_frontend_task",
            {
                "task_id": "exercise-frontend-001",
                "task_summary": "Inspect the frontend executor contract and return a constrained implementation summary only.",
                "target_paths": ["images/title.png"],
                "constraints": [
                    "Do not edit files outside target_paths.",
                    "Treat this as a dry-run style exercise response.",
                ],
                "acceptance_criteria": [
                    "Return a structured summary payload.",
                    "Do not touch backend paths.",
                ],
                "cd": str(WORKSPACE / "mcp" / "geminimcp"),
                "sandbox": False,
            },
        )

    raise ValueError(f"Unsupported target: {target}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Exercise CodeCGC MCP tools over stdio.")
    parser.add_argument("target", choices=["backend", "frontend"])
    parser.add_argument("--list-tools", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()

    params = build_server_params(args.target)

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            if args.list_tools:
                result = await session.list_tools()
                print(
                    json.dumps(
                        result.model_dump(mode="json"),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
                return

            tool_name, tool_args = build_tool_call(args.target)
            result = await session.call_tool(
                tool_name,
                tool_args,
                read_timeout_seconds=datetime.timedelta(seconds=args.timeout_seconds),
            )

    print(
        json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
