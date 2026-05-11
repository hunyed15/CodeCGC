from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import yaml

from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_path_contract import to_project_relative_path
from codecgc_routing_paths import resolve_active_routing_file


OWNERS = {"orchestration", "docs", "frontend", "backend", "frontend-test", "backend-test", "shared", "unknown"}
POLICY_PROJECT_ROOT_KEY = "_codecgc_project_root"


@dataclass(frozen=True)
class PathDecision:
    path: str
    owner: str
    allowed: bool
    reason: str
    recommended_action: str


@dataclass(frozen=True)
class HookRequest:
    tool_name: str
    file_path: str
    command: str


EDIT_TOOL_NAMES = {"Edit", "Write", "MultiEdit"}
SHELL_TOOL_NAMES = {"Bash", "PowerShell"}
SHELL_DENIED_COMMAND_PATTERNS = (
    r"\brm\s+-[^\n\r]*[rf]",
    r"\bdel\s+",
    r"\brmdir\s+",
    r"\bremove-item\b",
    r"\bset-content\b",
    r"\badd-content\b",
    r"\bout-file\b",
    r"\bnew-item\b",
    r"\bcopy-item\b",
    r"\bmove-item\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\b",
    r"\bpython\s+-c\b",
    r"\bnode\s+-e\b",
    r"\bpowershell(\.exe)?\s+-(command|encodedcommand)\b",
    r"\bcmd(\.exe)?\s+/c\b",
)
SHELL_ALLOWED_COMMAND_PREFIXES = (
    "git status",
    "git diff",
    "git log",
    "git show",
    "git branch",
    "git rev-parse",
    "git ls-files",
    "git remote",
    "rg",
    "ls",
    "dir",
    "pwd",
    "get-content",
    "get-childitem",
    "select-string",
    "test-path",
    "resolve-path",
    "pytest",
    "python -m pytest",
    "python -m compileall",
    "npm test",
    "npm run test",
    "npm run lint",
    "npm run typecheck",
    "npm run check",
    "pnpm test",
    "pnpm run test",
    "pnpm run lint",
    "pnpm run typecheck",
    "yarn test",
    "yarn lint",
    "codex --help",
    "gemini --help",
    "gemini --version",
)


def normalize_path_text(path_text: str) -> str:
    normalized = str(path_text or "").replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Routing policy file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Routing policy must be a mapping: {path}")
    return data


def load_policy(path: Path | None = None) -> dict[str, Any]:
    policy_path = path or resolve_active_routing_file()
    policy = _load_yaml(policy_path)
    if int(policy.get("version", 0) or 0) != 2:
        raise ValueError("model-routing.yaml must use version: 2.")
    validate_policy(policy)
    policy[POLICY_PROJECT_ROOT_KEY] = str(policy_path.parent.resolve())
    return policy


def validate_policy(policy: dict[str, Any]) -> None:
    required_lists = [
        "orchestration_paths",
        "docs_paths",
        "frontend_paths",
        "backend_paths",
        "shared_paths",
    ]
    missing = [name for name in required_lists if not isinstance(policy.get(name), list)]
    test_paths = policy.get("test_paths")
    rules = policy.get("rules")
    if not isinstance(test_paths, dict):
        missing.append("test_paths")
    if not isinstance(rules, dict):
        missing.append("rules")
    if missing:
        raise ValueError(f"model-routing.yaml is missing required policy sections: {', '.join(missing)}")

    for name in ("frontend", "backend"):
        if not isinstance(test_paths.get(name), list):
            raise ValueError(f"model-routing.yaml test_paths.{name} must be a list.")

    allowed = set(_as_string_list(rules.get("claude_allowed_owners")))
    invalid_allowed = sorted(allowed - OWNERS)
    if invalid_allowed:
        raise ValueError(f"Invalid claude_allowed_owners entries: {', '.join(invalid_allowed)}")

    if str(rules.get("shared_policy", "")).strip() != "split-first":
        raise ValueError("Only shared_policy: split-first is supported.")


def _matches_any(path_text: str, patterns: list[str]) -> bool:
    return any(fnmatch(path_text, pattern) for pattern in patterns)


def normalize_policy_path(path_text: str, policy: dict[str, Any]) -> str:
    project_root = str(policy.get(POLICY_PROJECT_ROOT_KEY, "")).strip()
    if project_root:
        return normalize_path_text(
            to_project_relative_path(path_text, Path(project_root), allow_legacy_suffix=False)
        )
    return normalize_path_text(path_text)


def classify_path(path_text: str, policy: dict[str, Any]) -> str:
    normalized = normalize_policy_path(path_text, policy)
    test_paths = policy.get("test_paths", {})

    ordered_groups: list[tuple[str, list[str]]] = [
        ("shared", _as_string_list(policy.get("shared_paths"))),
        ("orchestration", _as_string_list(policy.get("orchestration_paths"))),
        ("docs", _as_string_list(policy.get("docs_paths"))),
        ("frontend-test", _as_string_list(test_paths.get("frontend"))),
        ("backend-test", _as_string_list(test_paths.get("backend"))),
        ("frontend", _as_string_list(policy.get("frontend_paths"))),
        ("backend", _as_string_list(policy.get("backend_paths"))),
    ]
    for owner, patterns in ordered_groups:
        if _matches_any(normalized, patterns):
            return owner
    return "unknown"


def allowed_owners_for_actor(actor: str, policy: dict[str, Any]) -> set[str]:
    normalized_actor = str(actor or "").strip().lower()
    rules = policy.get("rules", {})
    if normalized_actor == "claude":
        return set(_as_string_list(rules.get("claude_allowed_owners")))
    if normalized_actor in {"codex", "codexmcp", "backend"}:
        return {"backend", "backend-test"}
    if normalized_actor in {"gemini", "geminimcp", "frontend"}:
        return {"frontend", "frontend-test"}
    return set()


def recommended_action_for(owner: str, actor: str) -> str:
    if owner == "backend":
        return "route through cgc-build or cgc-fix with a backend step"
    if owner == "backend-test":
        return "route through cgc-test with a backend test step"
    if owner == "frontend":
        return "route through cgc-build or cgc-fix with a frontend step"
    if owner == "frontend-test":
        return "route through cgc-test with a frontend test step"
    if owner == "shared":
        return "split the shared change before execution"
    if owner == "unknown":
        return "add the path to model-routing.yaml or narrow the target path"
    return f"request a policy route for actor {actor}"


def decide_path(path_text: str, actor: str, operation: str, policy: dict[str, Any]) -> PathDecision:
    owner = classify_path(path_text, policy)
    allowed_owners = allowed_owners_for_actor(actor, policy)
    normalized_actor = str(actor or "").strip().lower()
    normalized_operation = str(operation or "").strip().lower() or "write"

    allowed = normalized_operation in {"read", "inspect"} or owner in allowed_owners
    if owner == "unknown":
        allowed = False
    if owner == "shared" and normalized_operation not in {"read", "inspect"}:
        allowed = False

    if allowed:
        reason = f"{normalized_actor} may {normalized_operation} {owner} paths"
        recommended = ""
    elif owner == "shared":
        reason = "shared paths require split-first routing"
        recommended = recommended_action_for(owner, normalized_actor)
    elif owner == "unknown":
        reason = "path is not covered by model-routing.yaml"
        recommended = recommended_action_for(owner, normalized_actor)
    else:
        reason = f"{owner} paths are not owned by {normalized_actor}"
        recommended = recommended_action_for(owner, normalized_actor)

    return PathDecision(
        path=normalize_policy_path(path_text, policy),
        owner=owner,
        allowed=allowed,
        reason=reason,
        recommended_action=recommended,
    )


def evaluate_paths(paths: list[str], actor: str, operation: str, policy: dict[str, Any]) -> dict[str, Any]:
    decisions = [decide_path(path, actor, operation, policy) for path in paths]
    return {
        "success": all(decision.allowed for decision in decisions),
        "allowed": all(decision.allowed for decision in decisions),
        "actor": str(actor or "").strip().lower(),
        "operation": str(operation or "").strip().lower() or "write",
        "decisions": [decision.__dict__ for decision in decisions],
        "owners": sorted({decision.owner for decision in decisions}),
    }


def validate_executor_target(kind: str, target_paths: list[str], policy: dict[str, Any]) -> dict[str, Any]:
    actor = "codex" if str(kind).strip().lower() == "backend" else "gemini" if str(kind).strip().lower() == "frontend" else str(kind)
    result = evaluate_paths(target_paths, actor=actor, operation="write", policy=policy)
    result["kind"] = str(kind).strip().lower()
    return result


def parse_hook_request(text: str) -> HookRequest:
    if not text.strip():
        return HookRequest(tool_name="", file_path="", command="")
    payload = json.loads(text)
    if not isinstance(payload, dict):
        return HookRequest(tool_name="", file_path="", command="")
    tool_name = str(payload.get("tool_name", "")).strip()
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return HookRequest(tool_name=tool_name, file_path="", command="")
    file_path = str(tool_input.get("file_path") or tool_input.get("path") or "").strip()
    command = str(tool_input.get("command") or tool_input.get("script") or "").strip()
    return HookRequest(tool_name=tool_name, file_path=file_path, command=command)


def parse_hook_payload(text: str) -> tuple[str, str]:
    request = parse_hook_request(text)
    return request.tool_name, request.file_path


def has_unquoted_shell_control_operator(command: str) -> bool:
    in_single = False
    in_double = False
    escaped = False
    for index, char in enumerate(command):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if in_single or in_double:
            continue
        if char in {"|", ";", ">", "<", "`", "&"}:
            return True
        if char == "$" and index + 1 < len(command) and command[index + 1] == "(":
            return True
    return False


def normalize_shell_command_for_prefix(command: str) -> str:
    try:
        parts = shlex.split(command, posix=False)
    except ValueError:
        parts = command.split()
    if not parts:
        return ""

    first = parts[0].strip().strip("'\"")
    first_name = Path(first.replace("\\", "/")).name.lower()
    for suffix in (".cmd", ".ps1", ".exe", ".bat"):
        if first_name.endswith(suffix):
            first_name = first_name[: -len(suffix)]
            break
    rest = " ".join(str(item).strip().strip("'\"").lower() for item in parts[1:])
    return f"{first_name} {rest}".strip()


def shell_prefix_matches(command: str, prefix: str) -> bool:
    return command == prefix or command.startswith(f"{prefix} ")


def is_codecgc_cli_shell_command(normalized_command: str) -> bool:
    first = normalized_command.split(" ", 1)[0]
    return first == "cgc" or first == "codecgc" or first.startswith("cgc-")


def evaluate_shell_command(command: str, tool_name: str = "Bash") -> dict[str, Any]:
    normalized_tool_name = str(tool_name or "").strip()
    if not str(command or "").strip():
        return {"allowed": True, "reason": "", "recommended_action": ""}

    if has_unquoted_shell_control_operator(command):
        return {
            "allowed": False,
            "reason": f"{normalized_tool_name} commands with shell control operators are not allowed for Claude",
            "recommended_action": "route write work through /cgc or run a single read-only check",
        }

    lowered = command.lower()
    if any(re.search(pattern, lowered) for pattern in SHELL_DENIED_COMMAND_PATTERNS):
        return {
            "allowed": False,
            "reason": f"{normalized_tool_name} command looks like a direct write or destructive shell operation",
            "recommended_action": "route implementation through /cgc so CodeCGC can dispatch Codex or Gemini",
        }

    normalized_command = normalize_shell_command_for_prefix(command)
    if is_codecgc_cli_shell_command(normalized_command):
        return {"allowed": True, "reason": "", "recommended_action": ""}

    if any(shell_prefix_matches(normalized_command, prefix) for prefix in SHELL_ALLOWED_COMMAND_PREFIXES):
        return {"allowed": True, "reason": "", "recommended_action": ""}

    return {
        "allowed": False,
        "reason": f"{normalized_tool_name} command is outside the CodeCGC Claude shell allowlist",
        "recommended_action": "use /cgc for write work, or use an allowed read-only/test command",
    }


def build_hook_response(allowed: bool, reason: str) -> dict[str, Any]:
    if allowed:
        return {"decision": "approve"}
    return {"decision": "deny", "reason": reason}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate CodeCGC routing policy decisions.")
    parser.add_argument("--routing-file", default="", help="Optional explicit model-routing.yaml path.")
    parser.add_argument("--actor", default="claude", help="Actor requesting the operation.")
    parser.add_argument("--operation", default="write", help="Operation to evaluate.")
    parser.add_argument("--path", action="append", default=[], help="Path to evaluate. Repeatable.")
    parser.add_argument("--hook-check", action="store_true", help="Read Claude hook JSON from stdin and return hook JSON.")
    return parser


def main() -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()

    try:
        policy_path = Path(args.routing_file).resolve() if args.routing_file else resolve_active_routing_file()
        policy = load_policy(policy_path)

        if args.hook_check:
            request = parse_hook_request(sys.stdin.read())
            if request.tool_name in SHELL_TOOL_NAMES:
                result = evaluate_shell_command(request.command, request.tool_name)
                if result["allowed"]:
                    print_json(build_hook_response(True, ""))
                    return 0
                hook_reason = f"CodeCGC: {result['reason']}."
                recommended = str(result.get("recommended_action", "")).strip()
                if recommended:
                    hook_reason += f" {recommended}."
                print_json(build_hook_response(False, hook_reason))
                return 0

            if request.tool_name not in EDIT_TOOL_NAMES or not request.file_path:
                print_json(build_hook_response(True, ""))
                return 0
            result = evaluate_paths([request.file_path], actor=args.actor, operation=args.operation, policy=policy)
            decision = result["decisions"][0]
            reason = decision.get("reason", "")
            recommended = decision.get("recommended_action", "")
            hook_reason = f"CodeCGC: {reason}."
            if recommended:
                hook_reason += f" {recommended}."
            print_json(build_hook_response(bool(result["allowed"]), hook_reason))
            return 0

        if not args.path:
            raise ValueError("At least one --path is required unless --hook-check is used.")

        print_json(evaluate_paths(args.path, actor=args.actor, operation=args.operation, policy=policy))
        return 0
    except Exception as error:
        print_json({"success": False, "allowed": False, "error": str(error)}, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
