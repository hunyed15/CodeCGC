import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from codecgc_runtime_paths import PACKAGE_ROOT
from codecgc_runtime_paths import PROJECT_ROOT

WORKSPACE = PACKAGE_ROOT
PROJECT_WORKSPACE = PROJECT_ROOT
SCRIPTS_DIR = WORKSPACE / "scripts"


def build_script_command(script_name: str, *args: str) -> list[str]:
    return [sys.executable, str(SCRIPTS_DIR / script_name), *args]


def parse_json_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Command produced no JSON output.")
    return json.loads(stripped)


def run_json_script(script_name: str, *args: str) -> dict[str, Any]:
    command = build_script_command(script_name, *args)
    completed = subprocess.run(
        command,
        cwd=PROJECT_WORKSPACE,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()

    if completed.returncode == 0:
        if not stdout:
            return {"success": True}
        return parse_json_text(stdout)

    for candidate in (stdout, stderr):
        if not candidate:
            continue
        try:
            parsed = parse_json_text(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            parsed.setdefault("success", False)
            parsed.setdefault("returncode", completed.returncode)
            return parsed

    return {
        "success": False,
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "error": f"{script_name} failed with exit code {completed.returncode}.",
    }
