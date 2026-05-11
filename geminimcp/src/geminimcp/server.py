"""FastMCP server implementation for the Gemini MCP project."""

from __future__ import annotations

import asyncio
import functools
import json
import os
import queue
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Annotated, Any, Dict, Generator, List, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BeforeValidator, Field
import shutil

DEFAULT_GEMINI_APPROVAL_MODE = "yolo"
DEFAULT_GEMINI_TIMEOUT_SECONDS = 600
PROJECT_GEMINI_POLICY_RELATIVE_PATH = Path(".gemini") / "policies" / "codecgc-policy.toml"

mcp = FastMCP("Gemini MCP Server-from guda.studio")

# Mirror of model-routing.yaml backend_paths — keep these hints in sync with
# route-edit.ps1 and codexmcp/server.py FRONTEND_PATH_HINTS.
BACKEND_PATH_HINTS = (
    "apps/api/",
    "server/",
    "src/server/",
    "src/services/",
    "src/repositories/",
    "backend/",
)

BACKEND_FILE_HINTS = (
    ".py",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".cs",
    ".rb",
    ".php",
    ".sql",
)


def _normalize_path_text(path_value: Path | str) -> str:
    """Normalize a path-like value to a forward-slash string."""
    return str(path_value).replace("\\", "/").strip()


def _resolve_project_gemini_policy(cd: Path) -> Path | None:
    """Return the CodeCGC project-local Gemini policy if the workspace installed it."""
    policy_path = cd / PROJECT_GEMINI_POLICY_RELATIVE_PATH
    if policy_path.is_file():
        return policy_path
    return None


def _is_probably_backend_path(path_value: Path | str) -> bool:
    """Best-effort check to keep frontend-only Gemini tasks away from backend files."""
    normalized = _normalize_path_text(path_value).lower().lstrip("./")
    if any(hint in normalized for hint in BACKEND_PATH_HINTS):
        return True

    suffix = Path(normalized).suffix.lower()
    if suffix in BACKEND_FILE_HINTS:
        return True

    return False


def _build_frontend_task_prompt(
    task_summary: str,
    target_paths: List[Path],
    constraints: List[str],
    acceptance_criteria: List[str],
) -> str:
    """Build a constrained prompt for frontend implementation tasks."""
    lines = [
        "You are implementing a frontend-only coding task.",
        "Stay strictly within the provided target paths.",
        "Do not edit backend files, API layers, repositories, or server logic.",
        "Preserve the existing product structure unless the task explicitly requires otherwise.",
        "Return a concise implementation summary, followed by risks if any remain.",
        "",
        "Task summary:",
        task_summary.strip(),
        "",
        "Target paths:",
    ]

    lines.extend(f"- {_normalize_path_text(path)}" for path in target_paths)

    if constraints:
        lines.append("")
        lines.append("Constraints:")
        lines.extend(f"- {item.strip()}" for item in constraints if item.strip())

    if acceptance_criteria:
        lines.append("")
        lines.append("Acceptance criteria:")
        lines.extend(f"- {item.strip()}" for item in acceptance_criteria if item.strip())

    return "\n".join(lines).strip()


def _validate_frontend_target_paths(target_paths: List[Path]) -> tuple[bool, List[str], str]:
    """Validate frontend task target paths and return policy check notes."""
    if not target_paths:
        return False, [], "The `target_paths` field must contain at least one file or directory."

    normalized_paths = [_normalize_path_text(path) for path in target_paths]
    backend_hits = [
        path_text
        for path_text in normalized_paths
        if _is_probably_backend_path(path_text)
    ]

    policy_checks = [
        "target_paths_present",
        "frontend_scope_requested",
    ]

    if backend_hits:
        return (
            False,
            policy_checks,
            "The frontend executor refused backend-like paths: "
            + ", ".join(backend_hits),
        )

    policy_checks.append("backend_boundary_check_passed")
    return True, policy_checks, ""


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    """Terminate a process and its children best-effort."""
    if process.poll() is not None:
        return

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return

    process.kill()


def run_shell_command(
    cmd: list[str],
    cwd: str | None = None,
    timeout_seconds: int = DEFAULT_GEMINI_TIMEOUT_SECONDS,
    env: dict[str, str] | None = None,
) -> Generator[str, None, None]:
    """Execute a command and stream its output line-by-line.

    Args:
        cmd: Command and arguments as a list (e.g., ["gemini", "-o", "stream-json", "--", "prompt"])
        cwd: Working directory for the command

    Yields:
        Output lines from the command
    """
    popen_cmd = cmd

    gemini_path = shutil.which("gemini") or cmd[0]
    popen_cmd[0] = gemini_path

    # if os.name == "nt" and gemini_path.lower().endswith((".cmd", ".bat")):
    #     from subprocess import list2cmdline
    #     popen_cmd = ["cmd.exe", "/s", "/c", list2cmdline(cmd)]

    process = subprocess.Popen(
        popen_cmd,
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding='utf-8',
        cwd=cwd,
        env=env,
    )

    output_queue: queue.Queue[str | None] = queue.Queue()
    GRACEFUL_SHUTDOWN_DELAY = 0.3
    started_at = time.monotonic()
    timed_out = False

    def is_turn_completed(line: str) -> bool:
        """Check if the line indicates turn completion via JSON parsing."""
        try:
            data = json.loads(line)
            return data.get("type") in {"turn.completed", "result"}
        except (json.JSONDecodeError, AttributeError, TypeError):
            return False

    def read_output() -> None:
        """Read process output in a separate thread."""
        if process.stdout:
            for line in iter(process.stdout.readline, ""):
                stripped = line.strip()
                output_queue.put(stripped)
                if is_turn_completed(stripped):
                    time.sleep(GRACEFUL_SHUTDOWN_DELAY)
                    process.terminate()
                    break
            process.stdout.close()
        output_queue.put(None)

    thread = threading.Thread(target=read_output)
    thread.start()

    # Yield lines while process is running
    while True:
        if timeout_seconds > 0 and time.monotonic() - started_at > timeout_seconds:
            timed_out = True
            _terminate_process_tree(process)
            break

        try:
            line = output_queue.get(timeout=0.5)
            if line is None:
                break
            yield line
        except queue.Empty:
            if process.poll() is not None and not thread.is_alive():
                break

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(process)
        process.wait()
    thread.join(timeout=5)

    while not output_queue.empty():
        try:
            line = output_queue.get_nowait()
            if line is not None:
                yield line
        except queue.Empty:
            break

    if timed_out:
        raise TimeoutError(
            f"Gemini CLI timed out after {timeout_seconds} seconds. "
            "This usually means the CLI was waiting for interactive approval, "
            "network/authentication, or a long-running tool call."
        )


def _execute_gemini_session(
    *,
    prompt: str,
    cd: Path,
    sandbox: bool,
    session_id: str,
    return_all_messages: bool,
    model: str,
    timeout_seconds: int = DEFAULT_GEMINI_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Execute Gemini CLI and return the parsed MCP response payload."""
    if not cd.exists():
        return {
            "success": False,
            "error": f"The workspace root directory `{cd.absolute().as_posix()}` does not exist. Please check the path and try again.",
        }

    if os.name == "nt":
        prompt = windows_escape(prompt)

    effective_timeout_seconds = int(timeout_seconds or 0) or DEFAULT_GEMINI_TIMEOUT_SECONDS
    cmd = [
        "gemini",
        "--skip-trust",
        "--approval-mode",
        DEFAULT_GEMINI_APPROVAL_MODE,
        "-o",
        "stream-json",
    ]

    project_policy = _resolve_project_gemini_policy(cd)
    if project_policy is not None:
        cmd.extend(["--policy", project_policy.absolute().as_posix()])

    if sandbox:
        cmd.extend(["--sandbox"])

    if model:
        cmd.extend(["--model", model])

    if session_id:
        cmd.extend(["--resume", session_id])

    cmd.append(prompt)

    gemini_env = {**os.environ, "GEMINI_CLI_TRUST_WORKSPACE": "true"}

    all_messages = []
    agent_messages = ""
    success = True
    err_message = ""
    thread_id: Optional[str] = None

    try:
        for line in run_shell_command(
            cmd,
            cwd=cd.absolute().as_posix(),
            timeout_seconds=effective_timeout_seconds,
            env=gemini_env,
        ):
            try:
                line_dict = json.loads(line.strip())
                all_messages.append(line_dict)
                item_type = line_dict.get("type", "")
                item_role = line_dict.get("role", "")
                if item_type == "message" and item_role == "assistant":
                    agent_messages = agent_messages + line_dict.get("content", "")
                if line_dict.get("session_id") is not None:
                    thread_id = line_dict.get("session_id")
            except json.JSONDecodeError:
                err_message += "\n\n[json decode error] " + line
                continue
            except Exception as error:
                err_message += "\n\n[unexpected error] " + f"Unexpected error: {error}. Line: {line!r}"
                success = False
                break
    except TimeoutError as error:
        success = False
        err_message += "\n\n[timeout] " + str(error)

    if thread_id is None:
        success = False
        err_message = (
            "Failed to get `SESSION_ID` from the gemini session. \n\n" + err_message
        )

    if success and len(agent_messages) == 0:
        success = False
        err_message = (
            "Failed to retrieve `agent_messages` data from the Gemini session. This might be due to Gemini performing a tool call. You can continue using the `SESSION_ID` to proceed with the conversation. \n\n "
            + err_message
        )

    if success:
        result: Dict[str, Any] = {
            "success": True,
            "SESSION_ID": thread_id,
            "agent_messages": agent_messages,
        }
    else:
        result = {"success": False, "error": err_message}

    if return_all_messages:
        result["all_messages"] = all_messages

    return result


def windows_escape(prompt):
    """
    Windows 风格的字符串转义函数。
    把常见特殊字符转义成 \\ 形式，适合命令行、JSON 或路径使用。
    比如：\n 变成 \\n，" 变成 \\"。
    """
    # 先处理反斜杠，避免它干扰其他替换
    result = prompt.replace("\\", "\\\\")
    # 双引号，转义成 \"，防止字符串边界乱套
    result = result.replace('"', '\\"')
    # 换行符，Windows 常用 \r\n，但我们分开转义
    result = result.replace("\n", "\\n")
    result = result.replace("\r", "\\r")
    # 制表符，空格的“超级版”
    result = result.replace("\t", "\\t")
    # 其他常见：退格符（像按了后退键）、换页符（打印机跳页用）
    result = result.replace("\b", "\\b")
    result = result.replace("\f", "\\f")
    # 如果有单引号，也转义下（不过 Windows 命令行不那么严格，但保险起见）
    result = result.replace("'", "\\'")

    return result


@mcp.tool(
    name="gemini",
    description="""
    Invokes the Gemini CLI to execute AI-driven tasks, returning structured JSON events and a session identifier for conversation continuity. 
    
    **Return structure:**
        - `success`: boolean indicating execution status
        - `SESSION_ID`: unique identifier for resuming this conversation in future calls
        - `agent_messages`: concatenated assistant response text
        - `all_messages`: (optional) complete array of JSON events when `return_all_messages=True`
        - `error`: error description when `success=False`

    **Best practices:**
        - Always capture and reuse `SESSION_ID` for multi-turn interactions
        - Enable `sandbox` mode when file modifications should be isolated
        - Use `return_all_messages` only when detailed execution traces are necessary (increases payload size)
        - Only pass `model` when the user has explicitly requested a specific model
    """,
    meta={"version": "0.0.0", "author": "guda.studio"},
)
async def gemini(
    PROMPT: Annotated[str, "Instruction for the task to send to gemini."],
    cd: Annotated[Path, "Set the workspace root for gemini before executing the task."],
    sandbox: Annotated[
        bool,
        Field(description="Run in sandbox mode. Defaults to `False`."),
    ] = False,
    SESSION_ID: Annotated[
        str,
        "Resume the specified session of the gemini. Defaults to empty string, start a new session.",
    ] = "",
    return_all_messages: Annotated[
        bool,
        "Return all messages (e.g. reasoning, tool calls, etc.) from the gemini session. Set to `False` by default, only the agent's final reply message is returned.",
    ] = False,
    model: Annotated[
        str,
        "The model to use for the gemini session. This parameter is strictly prohibited unless explicitly specified by the user.",
    ] = "",
    timeout_seconds: Annotated[
        int,
        Field(description="Maximum Gemini CLI process runtime in seconds. Defaults to 600."),
    ] = DEFAULT_GEMINI_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Execute a gemini CLI session and return the results."""
    return await asyncio.to_thread(
        functools.partial(
            _execute_gemini_session,
            prompt=PROMPT,
            cd=cd,
            sandbox=sandbox,
            session_id=SESSION_ID,
            return_all_messages=return_all_messages,
            model=model,
            timeout_seconds=timeout_seconds,
        )
    )


@mcp.tool(
    name="implement_frontend_task",
    description="""
    Executes a frontend-only implementation task via Gemini with extra policy checks.
    Use this tool when Claude has already completed planning/design and needs Gemini to
    perform the actual frontend code changes inside a constrained path set.
    """,
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def implement_frontend_task(
    task_id: Annotated[str, "Stable task identifier for audit and review."],
    task_summary: Annotated[str, "Frontend implementation summary prepared by the orchestrator."],
    target_paths: Annotated[
        List[Path],
        Field(
            description="Frontend paths Gemini is allowed to touch for this task.",
        ),
    ],
    constraints: Annotated[
        List[str],
        Field(
            description="Non-negotiable implementation constraints for this frontend task.",
        ),
    ] = [],
    acceptance_criteria: Annotated[
        List[str],
        Field(
            description="Acceptance criteria the implementation should satisfy.",
        ),
    ] = [],
    cd: Annotated[Path, "Workspace root for the frontend task."] = Path("."),
    SESSION_ID: Annotated[
        str,
        "Resume the specified Gemini session. Empty string starts a new session.",
    ] = "",
    sandbox: Annotated[
        bool,
        Field(description="Run Gemini in sandbox mode. Defaults to `False`."),
    ] = False,
    return_all_messages: Annotated[
        bool,
        "Return full Gemini event logs for debugging. Defaults to `False`.",
    ] = False,
    model: Annotated[
        str,
        "Optional model override. Only use when explicitly requested by the user.",
    ] = "",
    timeout_seconds: Annotated[
        int,
        Field(description="Maximum Gemini CLI process runtime in seconds. Defaults to 600."),
    ] = DEFAULT_GEMINI_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Execute a frontend-only Gemini task with CodeCGC policy checks."""
    valid, policy_checks, validation_error = _validate_frontend_target_paths(target_paths)
    if not valid:
        return {
            "success": False,
            "task_id": task_id,
            "policy_checks": policy_checks,
            "error": validation_error,
        }

    prompt = _build_frontend_task_prompt(
        task_summary=task_summary,
        target_paths=target_paths,
        constraints=constraints,
        acceptance_criteria=acceptance_criteria,
    )
    result = await asyncio.to_thread(
        functools.partial(
            _execute_gemini_session,
            prompt=prompt,
            cd=cd,
            sandbox=sandbox,
            session_id=SESSION_ID,
            return_all_messages=return_all_messages,
            model=model,
            timeout_seconds=timeout_seconds,
        )
    )

    if not result.get("success"):
        result["task_id"] = task_id
        result["policy_checks"] = policy_checks
        return result

    return {
        "success": True,
        "task_id": task_id,
        "SESSION_ID": result["SESSION_ID"],
        "summary": result["agent_messages"],
        "agent_messages": result["agent_messages"],
        "changed_files": [_normalize_path_text(path) for path in target_paths],
        "policy_checks": policy_checks + ["frontend_executor_completed"],
        "risks": [],
        **({"all_messages": result["all_messages"]} if return_all_messages and "all_messages" in result else {}),
    }


def run() -> None:
    """Start the MCP server over stdio transport."""
    mcp.run(transport="stdio")
