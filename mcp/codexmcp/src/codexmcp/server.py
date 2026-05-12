"""FastMCP server implementation for the Codex MCP project."""

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
from typing import Annotated, Any, Dict, Generator, List, Literal, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BeforeValidator, Field
import shutil

mcp = FastMCP("Codex MCP Server-from guda.studio")

# Mirror of model-routing.yaml frontend_paths — keep these hints in sync with
# route-edit.ps1 and geminimcp/server.py BACKEND_PATH_HINTS.
FRONTEND_PATH_HINTS = (
    "apps/web/",
    "src/components/",
    "src/pages/",
    "src/app/",
    "src/styles/",
    "src/ui/",
    "components/",
    "pages/",
    "app/",
    "styles/",
    "ui/",
    "web/",
    "frontend/",
)

FRONTEND_FILE_SUFFIXES = (
    ".tsx",
    ".jsx",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".styl",
    ".html",
    ".vue",
    ".svelte",
)

PROJECT_CODEX_POLICY_RELATIVE_PATH = Path(".codex") / "codecgcrc.json"


def _empty_str_to_none(value: str | None) -> str | None:
    """Convert empty strings to None for optional UUID parameters."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _normalize_path_text(path_value: Path | str) -> str:
    """Normalize a path-like value to a forward-slash string."""
    return str(path_value).replace("\\", "/").strip()


def _load_project_codex_policy_context(cd: Path) -> str:
    """Load the CodeCGC project-local Codex policy contract as prompt context."""
    policy_path = cd / PROJECT_CODEX_POLICY_RELATIVE_PATH
    if not policy_path.is_file():
        return ""

    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except Exception:
        return ""

    if not isinstance(payload, dict):
        return ""

    enforcement = payload.get("enforcement")
    if not isinstance(enforcement, dict):
        enforcement = {}

    allowed_path_kinds = payload.get("allowed_path_kinds")
    denied_path_kinds = payload.get("denied_path_kinds")
    notes = payload.get("notes")

    lines = [
        "Project CodeCGC Codex policy contract:",
        f"- Role: {payload.get('role', 'backend implementation and backend tests')}",
        f"- Routing policy: {enforcement.get('routing_policy', 'model-routing.yaml')}",
        f"- Primary enforcement: {enforcement.get('primary', 'CodeCGC MCP backend path validation')}",
        f"- Codex CLI guardrail: {enforcement.get('codex_cli', 'sandbox and approval flags supplied by codexmcp')}",
    ]
    if isinstance(allowed_path_kinds, list):
        lines.append("- Allowed path kinds: " + ", ".join(str(item) for item in allowed_path_kinds))
    if isinstance(denied_path_kinds, list):
        lines.append("- Denied path kinds: " + ", ".join(str(item) for item in denied_path_kinds))
    if isinstance(notes, list):
        lines.extend(f"- {str(item)}" for item in notes if str(item).strip())
    lines.append("Follow this project policy before making any code change.")
    return "\n".join(lines).strip()


def _is_probably_frontend_path(path_value: Path | str) -> bool:
    """Best-effort check to keep backend-only Codex tasks away from frontend files."""
    normalized = _normalize_path_text(path_value).lower().lstrip("./")
    if any(hint in normalized for hint in FRONTEND_PATH_HINTS):
        return True
    suffix = Path(normalized).suffix.lower()
    return suffix in FRONTEND_FILE_SUFFIXES


def _build_backend_task_prompt(
    task_summary: str,
    target_paths: List[Path],
    constraints: List[str],
    acceptance_criteria: List[str],
) -> str:
    """Build a constrained prompt for backend implementation tasks."""
    lines = [
        "You are implementing a backend-only coding task.",
        "Stay strictly within the provided target paths.",
        "Do not edit frontend files, styling files, or UI components.",
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


def _validate_backend_target_paths(target_paths: List[Path]) -> tuple[bool, List[str], str]:
    """Validate backend task target paths and return policy check notes."""
    if not target_paths:
        return False, [], "The `target_paths` field must contain at least one file or directory."

    normalized_paths = [_normalize_path_text(path) for path in target_paths]
    frontend_hits = [
        path_text
        for path_text in normalized_paths
        if _is_probably_frontend_path(path_text)
    ]

    policy_checks = [
        "target_paths_present",
        "backend_scope_requested",
    ]

    if frontend_hits:
        return (
            False,
            policy_checks,
            "The backend executor refused frontend-like paths: "
            + ", ".join(frontend_hits),
        )

    policy_checks.append("frontend_boundary_check_passed")
    return True, policy_checks, ""


def run_shell_command(cmd: list[str]) -> Generator[str, None, None]:
    """Execute a command and stream its output line-by-line.

    Args:
        cmd: Command and arguments as a list (e.g., ["codex", "exec", "prompt"])

    Yields:
        Output lines from the command
    """
    # On Windows, codex is exposed via a *.cmd shim. Use cmd.exe with /s so
    # user prompts containing quotes/newlines aren't reinterpreted as shell syntax.
    popen_cmd = cmd.copy()
    codex_path = shutil.which('codex') or cmd[0]
    popen_cmd[0] = codex_path

    process = subprocess.Popen(
        popen_cmd,
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        encoding='utf-8',
    )

    output_queue: queue.Queue[str | None] = queue.Queue()
    GRACEFUL_SHUTDOWN_DELAY = 0.3

    def is_turn_completed(line: str) -> bool:
        """Check if the line indicates turn completion via JSON parsing."""
        try:
            data = json.loads(line)
            return data.get("type") == "turn.completed"
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
        process.kill()
        process.wait()
    thread.join(timeout=5)

    while not output_queue.empty():
        try:
            line = output_queue.get_nowait()
            if line is not None:
                yield line
        except queue.Empty:
            break


def _execute_codex_session(
    *,
    prompt: str,
    cd: Path,
    sandbox: Literal["read-only", "workspace-write", "danger-full-access"],
    session_id: str,
    skip_git_repo_check: bool,
    return_all_messages: bool,
    image: List[Path],
    model: str,
    yolo: bool,
    profile: str,
) -> Dict[str, Any]:
    """Execute Codex CLI and return the parsed MCP response payload."""
    if not cd.exists():
        return {
            "success": False,
            "error": f"The workspace root directory `{cd.absolute().as_posix()}` does not exist.",
        }

    cmd = ["codex", "exec", "--sandbox", sandbox, "--cd", str(cd), "--json"]

    if len(image):
        cmd.extend(["--image", ",".join(image)])

    if model:
        cmd.extend(["--model", model])

    if profile:
        cmd.extend(["--profile", profile])

    if yolo:
        cmd.append("--yolo")

    if skip_git_repo_check:
        cmd.append("--skip-git-repo-check")

    if session_id:
        cmd.extend(["resume", str(session_id)])

    policy_context = _load_project_codex_policy_context(cd)
    if policy_context:
        prompt = f"{policy_context}\n\nUser task:\n{prompt}"

    if os.name == "nt":
        prompt = windows_escape(prompt)
    cmd += ["--", prompt]

    all_messages: list[Dict[str, Any]] = []
    agent_messages = ""
    success = True
    err_message = ""
    thread_id: Optional[str] = None

    for line in run_shell_command(cmd):
        try:
            line_dict = json.loads(line.strip())
            all_messages.append(line_dict)
            item = line_dict.get("item", {})
            item_type = item.get("type", "")
            if item_type == "agent_message":
                agent_messages = agent_messages + item.get("text", "")
            if line_dict.get("thread_id") is not None:
                thread_id = line_dict.get("thread_id")
            if "fail" in line_dict.get("type", ""):
                success = False if len(agent_messages) == 0 else success
                err_message += "\n\n[codex error] " + line_dict.get("error", {}).get("message", "")
            if "error" in line_dict.get("type", ""):
                error_msg = line_dict.get("message", "")
                import re

                is_reconnecting = bool(re.match(r"^Reconnecting\.\.\.\s+\d+/\d+", error_msg))
                if not is_reconnecting:
                    success = False if len(agent_messages) == 0 else success
                    err_message += "\n\n[codex error] " + error_msg

        except json.JSONDecodeError:
            err_message += "\n\n[json decode error] " + line
            continue
        except Exception as error:
            err_message += "\n\n[unexpected error] " + f"Unexpected error: {error}. Line: {line!r}"
            success = False
            break

    if thread_id is None:
        success = False
        err_message = "Failed to get `SESSION_ID` from the codex session. \n\n" + err_message

    if len(agent_messages) == 0:
        success = False
        err_message = (
            "Failed to get `agent_messages` from the codex session. "
            "\n\n You can try to set `return_all_messages` to `True` to get the full reasoning information. "
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
    result = prompt.replace('\\', '\\\\')
    # 双引号，转义成 \"，防止字符串边界乱套
    result = result.replace('"', '\\"')
    # 换行符，Windows 常用 \r\n，但我们分开转义
    result = result.replace('\n', '\\n')
    result = result.replace('\r', '\\r')
    # 制表符，空格的“超级版”
    result = result.replace('\t', '\\t')
    # 其他常见：退格符（像按了后退键）、换页符（打印机跳页用）
    result = result.replace('\b', '\\b')
    result = result.replace('\f', '\\f')
    # 如果有单引号，也转义下（不过 Windows 命令行不那么严格，但保险起见）
    result = result.replace("'", "\\'")
    
    return result

@mcp.tool(
    name="codex",
    description="""
    Executes a non-interactive Codex session via CLI to perform AI-assisted coding tasks in a secure workspace.
    This tool wraps the `codex exec` command, enabling model-driven code generation, debugging, or automation based on natural language prompts.
    It supports resuming ongoing sessions for continuity and enforces sandbox policies to prevent unsafe operations. Ideal for integrating Codex into MCP servers for agentic workflows, such as code reviews or repo modifications.

    **Key Features:**
        - **Prompt-Driven Execution:** Send task instructions to Codex for step-by-step code handling.
        - **Workspace Isolation:** Operate within a specified directory, with optional Git repo skipping.
        - **Security Controls:** Three sandbox levels balance functionality and safety.
        - **Session Persistence:** Resume prior conversations via `SESSION_ID` for iterative tasks.

    **Edge Cases & Best Practices:**
        - Ensure `cd` exists and is accessible; tool fails silently on invalid paths.
        - For most repos, prefer "read-only" to avoid accidental changes.
        - If needed, set `return_all_messages` to `True` to parse "all_messages" for detailed tracing (e.g., reasoning, tool calls, etc.).
    """,
    meta={"version": "0.0.0", "author": "guda.studio"},
)
async def codex(
    PROMPT: Annotated[str, "Instruction for the task to send to codex."],
    cd: Annotated[Path, "Set the workspace root for codex before executing the task."],
    sandbox: Annotated[
        Literal["read-only", "workspace-write", "danger-full-access"],
        Field(
            description="Sandbox policy for model-generated commands. Defaults to `read-only`."
        ),
    ] = "read-only",
    SESSION_ID: Annotated[
        str,
        "Resume the specified session of the codex. Defaults to `None`, start a new session.",
    ] = "",
    skip_git_repo_check: Annotated[
        bool,
        "Allow codex running outside a Git repository (useful for one-off directories).",
    ] = True,
    return_all_messages: Annotated[
        bool,
        "Return all messages (e.g. reasoning, tool calls, etc.) from the codex session. Set to `False` by default, only the agent's final reply message is returned.",
    ] = False,
    image: Annotated[
        List[Path],
        Field(
            description="Attach one or more image files to the initial prompt. Separate multiple paths with commas or repeat the flag.",
        ),
    ] = [],
    model: Annotated[
        str,
        Field(
            description="The model to use for the codex session. This parameter is strictly prohibited unless explicitly specified by the user.",
        ),
    ] = "",
    yolo: Annotated[
        bool,
        Field(
            description="Run every command without approvals or sandboxing. Only use when `sandbox` couldn't be applied.",
        ),
    ] = False,
    profile: Annotated[
        str,
        "Configuration profile name to load from `~/.codex/config.toml`. This parameter is strictly prohibited unless explicitly specified by the user.",
    ] = "",
) -> Dict[str, Any]:
    """Execute a Codex CLI session and return the results."""
    return await asyncio.to_thread(
        functools.partial(
            _execute_codex_session,
            prompt=PROMPT,
            cd=cd,
            sandbox=sandbox,
            session_id=SESSION_ID,
            skip_git_repo_check=skip_git_repo_check,
            return_all_messages=return_all_messages,
            image=image,
            model=model,
            yolo=yolo,
            profile=profile,
        )
    )


@mcp.tool(
    name="implement_backend_task",
    description="""
    Executes a backend-only implementation task via Codex with extra policy checks.
    Use this tool when Claude has already completed planning/design and needs Codex to
    perform the actual backend code changes inside a constrained path set.
    """,
    meta={"version": "0.1.0", "author": "CodeCGC"},
)
async def implement_backend_task(
    task_id: Annotated[str, "Stable task identifier for audit and review."],
    task_summary: Annotated[str, "Backend implementation summary prepared by the orchestrator."],
    target_paths: Annotated[
        List[Path],
        Field(
            description="Backend paths Codex is allowed to touch for this task.",
        ),
    ],
    constraints: Annotated[
        List[str],
        Field(
            description="Non-negotiable implementation constraints for this backend task.",
        ),
    ] = [],
    acceptance_criteria: Annotated[
        List[str],
        Field(
            description="Acceptance criteria the implementation should satisfy.",
        ),
    ] = [],
    cd: Annotated[Path, "Workspace root for the backend task." ] = Path("."),
    SESSION_ID: Annotated[
        str,
        "Resume the specified Codex session. Empty string starts a new session.",
    ] = "",
    sandbox: Annotated[
        Literal["read-only", "workspace-write", "danger-full-access"],
        Field(
            description="Sandbox policy for the backend task. Defaults to `workspace-write`."
        ),
    ] = "workspace-write",
    return_all_messages: Annotated[
        bool,
        "Return full Codex event logs for debugging. Defaults to `False`.",
    ] = False,
    model: Annotated[
        str,
        Field(
            description="Optional model override. Only use when explicitly requested by the user.",
        ),
    ] = "",
    profile: Annotated[
        str,
        "Optional Codex profile from `~/.codex/config.toml`.",
    ] = "",
) -> Dict[str, Any]:
    """Execute a backend-only Codex task with CodeCGC policy checks."""
    valid, policy_checks, validation_error = _validate_backend_target_paths(target_paths)
    if not valid:
        return {
            "success": False,
            "task_id": task_id,
            "policy_checks": policy_checks,
            "error": validation_error,
        }

    prompt = _build_backend_task_prompt(
        task_summary=task_summary,
        target_paths=target_paths,
        constraints=constraints,
        acceptance_criteria=acceptance_criteria,
    )
    result = await asyncio.to_thread(
        functools.partial(
            _execute_codex_session,
            prompt=prompt,
            cd=cd,
            sandbox=sandbox,
            session_id=SESSION_ID,
            skip_git_repo_check=True,
            return_all_messages=return_all_messages,
            image=[],
            model=model,
            yolo=False,
            profile=profile,
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
        "policy_checks": policy_checks + ["backend_executor_completed"],
        "risks": [],
        **({"all_messages": result["all_messages"]} if return_all_messages and "all_messages" in result else {}),
    }


def run() -> None:
    """Start the MCP server over stdio transport."""
    mcp.run(transport="stdio")
