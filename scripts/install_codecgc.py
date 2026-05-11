import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from codecgc_console_io import render_summary_block
from codecgc_executor_registry import build_executor_registry
from codecgc_executor_registry import resolve_python_command
from codecgc_policy import load_policy
from codecgc_routing_template import sync_workspace_routing_file
from codecgc_runtime_paths import PACKAGE_ROOT
from codecgc_runtime_paths import resolve_workspace_root
from sync_codecgc_mcp_config import build_mcp_config
from sync_codecgc_mcp_config import write_mcp_config


WORKSPACE = PACKAGE_ROOT
CLAUDE_DIR = WORKSPACE / ".claude"
HOOKS_DIR = CLAUDE_DIR / "hooks"
SETTINGS_PATH = CLAUDE_DIR / "settings.json"
MCP_CONFIG_PATH = WORKSPACE / ".mcp.json"
PROJECT_HOOK_PATH = HOOKS_DIR / "route-edit.ps1"
PROJECT_ROUTING_PATH = WORKSPACE / "model-routing.yaml"
PROJECT_TEMPLATES_DIR = WORKSPACE / "codecgc" / "templates"
EDIT_GUARDRAIL_MATCHER = "Edit|Write|MultiEdit|Bash|PowerShell"
LEGACY_EDIT_GUARDRAIL_MATCHERS = {"Edit|Write", "Edit|Write|MultiEdit"}
PROJECT_ONBOARDING_RELATIVE_PATH = "codecgc/START_HERE.md"
PROJECT_ONBOARDING_MARKER = "<!-- codecgc:onboarding:v1 -->"
CLAUDE_SETTINGS_TEMPLATE = PROJECT_TEMPLATES_DIR / "claude" / "settings.local.json"
CODEX_POLICY_TEMPLATE = PROJECT_TEMPLATES_DIR / "codex" / "codecgcrc.json"
GEMINI_POLICY_TEMPLATE = PROJECT_TEMPLATES_DIR / "gemini" / "codecgc-policy.toml"


DEFAULT_HOOKS = {
    "PreToolUse": [
        {
            "matcher": EDIT_GUARDRAIL_MATCHER,
            "hooks": [
                {
                    "type": "command",
                    "command": "powershell -ExecutionPolicy Bypass -File .claude/hooks/route-edit.ps1",
                }
            ],
        }
    ]
}

SENSITIVE_KEYWORDS = ("token", "secret", "key", "password", "auth")
MCP_RUNTIME_REQUIREMENT = 'mcp[cli]>=1.21.2'
DEFAULT_ALLOWED_TOOLS = [
    "mcp__codecgc__*",
    "mcp__codex__*",
    "mcp__gemini__*",
]

PROJECT_WORKFLOW_DIRS = [
    "codecgc/features",
    "codecgc/issues",
    "codecgc/execution",
    "codecgc/requirements",
    "codecgc/architecture",
    "codecgc/roadmap",
    "codecgc/compound",
    "codecgc/docs",
    "codecgc/reference",
    "codecgc/fixtures/features",
    "codecgc/fixtures/issues",
    "codecgc/fixtures/execution",
    "codecgc/fixtures/roadmap",
]


def get_user_claude_root(override_root: str = "") -> Path:
    override = override_root.strip() or os.environ.get("CODECGC_USER_CLAUDE_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    if os.name == "nt":
        base = Path(os.environ.get("USERPROFILE", str(Path.home())))
    else:
        base = Path.home()
    return (base / ".claude").resolve()


def get_user_claude_paths(override_root: str = "") -> dict[str, Path]:
    root = get_user_claude_root(override_root)
    return {
        "root": root,
        "settings": root / "settings.json",
        "mcp": root / "mcp.json",
        "hooks_dir": root / "hooks",
        "hook_script": root / "hooks" / "route-edit.ps1",
        "commands_dir": root / "commands",
    }


def get_workspace_paths(override_workspace: str = "") -> dict[str, Path]:
    root = resolve_workspace_root(override_workspace)
    claude_dir = root / ".claude"
    hooks_dir = claude_dir / "hooks"
    codex_dir = root / ".codex"
    gemini_dir = root / ".gemini"
    return {
        "root": root,
        "claude_dir": claude_dir,
        "hooks_dir": hooks_dir,
        "settings": claude_dir / "settings.local.json",
        "legacy_settings": claude_dir / "settings.json",
        "mcp": root / ".mcp.json",
        "hook_script": hooks_dir / "route-edit.ps1",
        "commands_dir": claude_dir / "commands",
        "routing_file": root / "model-routing.yaml",
        "onboarding_file": root / PROJECT_ONBOARDING_RELATIVE_PATH,
        "codex_dir": codex_dir,
        "codex_policy": codex_dir / "codecgcrc.json",
        "gemini_dir": gemini_dir,
        "gemini_policies_dir": gemini_dir / "policies",
        "gemini_policy": gemini_dir / "policies" / "codecgc-policy.toml",
    }


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_text_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def copy_template_file(template_path: Path, target_path: Path) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template_path, target_path)
    return target_path


def ensure_workspace_workflow_dirs(workspace_root: Path) -> list[str]:
    created_or_existing: list[str] = []
    for relative_path in PROJECT_WORKFLOW_DIRS:
        directory = workspace_root / relative_path
        directory.mkdir(parents=True, exist_ok=True)
        created_or_existing.append(str(directory))
    return created_or_existing


def workspace_workflow_dirs_ready(workspace_root: Path) -> bool:
    return all((workspace_root / relative_path).is_dir() for relative_path in PROJECT_WORKFLOW_DIRS)


def build_project_onboarding_text() -> str:
    return f"""{PROJECT_ONBOARDING_MARKER}
# CodeCGC Start Here

This file is generated by `cgc-install` for this project. It is intentionally project-relative and should not contain machine-specific install paths.

## First Run

Inside Claude:

```text
/cgc-start
/cgc-status
/cgc-doctor
/cgc 新增一个登录页面，放在 src/components/LoginForm.tsx
```

Outside Claude:

```bash
cgc-start
cgc-status
cgc-doctor
cgc "新增一个登录页面，放在 src/components/LoginForm.tsx"
```

## What CodeCGC Owns

- Claude owns orchestration, requirements, design notes, docs, review, acceptance, and workflow state.
- Codex owns backend implementation and backend tests.
- Gemini owns frontend implementation and frontend tests.
- Mixed backend/frontend work should be split before execution.

## Installed Project Surface

```text
.mcp.json
model-routing.yaml
.claude/settings.local.json
.claude/hooks/route-edit.ps1
.claude/commands/cgc*.md
.codex/codecgcrc.json
.gemini/policies/codecgc-policy.toml
codecgc/features/
codecgc/issues/
codecgc/execution/
codecgc/requirements/
codecgc/architecture/
codecgc/roadmap/
codecgc/compound/
codecgc/docs/
codecgc/reference/
```

## Normal Loop

1. Start with `/cgc <your request>` or `cgc "<your request>"`.
2. Let CodeCGC decide whether the next step is planning, execution, review, or closure.
3. Review execution audits with `/cgc-review` or `cgc-review`.
4. Use `/cgc-history` or `cgc-history` when you need to find open work.

## Recovery

- If project integration looks wrong, run `cgc-install`, then `cgc-status`.
- If runtime or executor startup fails, run `cgc-doctor`.
- If a write is blocked, inspect `model-routing.yaml`; it is the project-local policy source of truth.
- If an execution was rejected, use `/cgc` or `cgc` to continue the same workflow rather than starting a new one.

## Stable References

- `codecgc/reference/quickstart.md`
- `codecgc/reference/onboarding.md`
- `codecgc/reference/operation-guide.md`
- `codecgc/reference/troubleshooting.md`
- `codecgc/reference/path-contract.md`
"""


def write_project_onboarding_file(workspace_root: Path) -> Path:
    path = workspace_root / PROJECT_ONBOARDING_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_project_onboarding_text(), encoding="utf-8")
    return path


def onboarding_file_is_valid(path: Path) -> bool:
    text = load_text_file(path)
    if not text:
        return False
    required_markers = [
        PROJECT_ONBOARDING_MARKER,
        "/cgc-start",
        "cgc-start",
        "/cgc-status",
        "cgc-status",
        "model-routing.yaml",
    ]
    return all(marker in text for marker in required_markers)


def build_hook_payload(command_text: str) -> dict[str, Any]:
    return {
        "PreToolUse": [
            {
                "matcher": EDIT_GUARDRAIL_MATCHER,
                "hooks": [
                    {
                        "type": "command",
                        "command": command_text,
                    }
                ],
            }
        ]
    }


def policy_file_is_valid(path: Path) -> bool:
    try:
        load_policy(path)
    except Exception:
        return False
    return True


def _normalize_command_path_for_markdown(path: Path) -> str:
    return str(path).replace("\\", "\\\\")


def build_mcp_first_command_template(
    *,
    filename: str,
    description: str,
    argument_hint: str,
    primary_tool: str,
    direct_rules: list[str],
    missing_rules: list[str] | None = None,
    fallback_command: str,
) -> tuple[str, str]:
    lines = [
        "---",
        f"description: {description}",
        f"argument-hint: \"{argument_hint}\"",
        "---",
        f"优先使用 `{primary_tool}` MCP 工具作为主执行路径。",
        "内部思考语言可自行选择，但面向用户的最终回复默认使用中文。",
        "",
        "执行规则：",
    ]
    lines.extend(f"- {item}" for item in direct_rules)
    if missing_rules:
        lines.append("")
        lines.append("缺少参数时：")
        lines.extend(f"- {item}" for item in missing_rules)
    lines.append("")
    lines.append("回退规则：")
    lines.append(f"- 只有在 MCP 工具路径不可用，或用户明确要求走 CLI 时，才回退到 Bash + `{fallback_command}`。")
    lines.append("- 向用户用中文简要总结结果。")
    return filename, "\n".join(lines) + "\n"


def build_custom_command_templates(bin_dir: Path) -> dict[str, str]:
    templates = dict(
        [
            build_mcp_first_command_template(
                filename="cgc.md",
                description="在当前项目中运行 CodeCGC",
                argument_hint="[需求或参数]",
                primary_tool="codecgc.entry",
                direct_rules=[
                    "如果用户提供的是自然语言需求，传给 `codecgc.entry`。",
                    "如果用户想继续最近的工作，使用 `codecgc.continue`。",
                    "如果用户想知道下一步做什么，使用 `codecgc.explain`。",
                ],
                fallback_command="cgc",
            ),
            build_mcp_first_command_template(
                filename="cgc-install.md",
                description="为当前项目或 Claude 用户目录安装/同步 CodeCGC 集成",
                argument_hint="[参数]",
                primary_tool="codecgc.install",
                direct_rules=[
                    "把安装参数映射到 `codecgc.install` 的 `mode`、`workspace`、`user_root` 等字段。",
                    "如果用户没有提供参数，就使用默认安装模式。",
                ],
                fallback_command="cgc-install",
            ),
            build_mcp_first_command_template(
                filename="cgc-status.md",
                description="检查 CodeCGC 集成状态",
                argument_hint="[参数]",
                primary_tool="codecgc.status",
                direct_rules=[
                    "使用 `codecgc.status` 检查安装与集成就绪状态。",
                    "如果用户明确给出目标项目目录，映射 `workspace`。",
                ],
                fallback_command="cgc-status",
            ),
            build_mcp_first_command_template(
                filename="cgc-doctor.md",
                description="运行 CodeCGC 自检",
                argument_hint="[参数]",
                primary_tool="codecgc.doctor",
                direct_rules=[
                    "使用 `codecgc.doctor` 检查运行时与集成健康状态。",
                    "如果用户明确给出目标项目目录，映射 `workspace`。",
                ],
                fallback_command="cgc-doctor",
            ),
            build_mcp_first_command_template(
                filename="cgc-plan.md",
                description="规划或修复一个 CodeCGC 工作流",
                argument_hint="[结构化规划参数]",
                primary_tool="codecgc.plan",
                direct_rules=[
                    "调用前提取 `flow`、`slug` 和 `summary`。",
                    "映射用户提供的 `target_paths`、`kind`，以及 `goal`、`acceptance`、`risk` 等规划字段和 issue 专属字段。",
                ],
                missing_rules=[
                    "如果缺少 `flow`，询问这是 `feature` 还是 `issue` 工作流。",
                    "如果缺少 `slug`，询问稳定的工作流 slug。",
                    "如果缺少 `summary`，询问一个简短规划摘要。",
                ],
                fallback_command="cgc-plan",
            ),
            build_mcp_first_command_template(
                filename="cgc-build.md",
                description="执行 CodeCGC 功能开发步骤",
                argument_hint="[参数]",
                primary_tool="codecgc.build",
                direct_rules=[
                    "调用前提取 `slug`。",
                    "映射可选执行字段，如 `step_number`、`checklist_file`、`audit_root`、`timeout_seconds`、`session_id`、`dry_run`。",
                ],
                missing_rules=[
                    "如果缺少 `slug`，询问目标功能工作流的 slug。",
                ],
                fallback_command="cgc-build",
            ),
            build_mcp_first_command_template(
                filename="cgc-fix.md",
                description="执行 CodeCGC 问题修复步骤",
                argument_hint="[参数]",
                primary_tool="codecgc.fix",
                direct_rules=[
                    "调用前提取 `slug`。",
                    "映射可选执行字段，如 `step_number`、`checklist_file`、`audit_root`、`timeout_seconds`、`session_id`、`dry_run`。",
                ],
                missing_rules=[
                    "如果缺少 `slug`，询问目标问题工作流的 slug。",
                ],
                fallback_command="cgc-fix",
            ),
            build_mcp_first_command_template(
                filename="cgc-test.md",
                description="执行 CodeCGC 测试步骤",
                argument_hint="[参数]",
                primary_tool="codecgc.test",
                direct_rules=[
                    "调用前提取 `flow` 和 `slug`。",
                    "映射可选执行字段，如 `step_number`、`checklist_file`、`audit_root`、`timeout_seconds`、`session_id`、`dry_run`。",
                ],
                missing_rules=[
                    "如果缺少 `flow`，询问该测试属于 `feature` 还是 `issue` 工作流。",
                    "如果缺少 `slug`，询问目标工作流 slug。",
                ],
                fallback_command="cgc-test",
            ),
            build_mcp_first_command_template(
                filename="cgc-review.md",
                description="审核一份 CodeCGC 执行审计结果",
                argument_hint="[参数]",
                primary_tool="codecgc.review",
                direct_rules=[
                    "调用前提取 `audit_file` 和 `decision`。",
                    "如果用户明确提供，映射可选字段 `risk`、`next_step`、`force`。",
                ],
                missing_rules=[
                    "如果缺少 `audit_file`，询问审计 JSON 路径。",
                    "如果缺少 `decision`，询问审核结论是 `accepted` 还是 `changes-requested`。",
                ],
                fallback_command="cgc-review",
            ),
            build_mcp_first_command_template(
                filename="cgc-route.md",
                description="为 CodeCGC 工作流推荐下一条命令",
                argument_hint="[参数]",
                primary_tool="codecgc.route",
                direct_rules=[
                    "调用前提取 `flow` 和 `slug`。",
                    "当用户已经知道目标工作流，只想得到下一步推荐动作时，使用这个命令。",
                ],
                missing_rules=[
                    "如果缺少 `flow`，询问工作流是 `feature` 还是 `issue`。",
                    "如果缺少 `slug`，询问工作流 slug。",
                ],
                fallback_command="cgc-route",
            ),
            build_mcp_first_command_template(
                filename="cgc-history.md",
                description="查看最近的 CodeCGC 工作流历史",
                argument_hint="[参数]",
                primary_tool="codecgc.history",
                direct_rules=[
                    "映射可选历史筛选字段，如 `flow`、`status`、`last`、`include_fixtures`。",
                    "如果没有提供筛选条件，就使用默认历史查询。",
                ],
                fallback_command="cgc-history",
            ),
            build_mcp_first_command_template(
                filename="cgc-package-audit.md",
                description="审计 CodeCGC 发布包运行时内容",
                argument_hint="[参数]",
                primary_tool="codecgc.package_audit",
                direct_rules=[
                    "当用户明确要求 `summary` 或 `json` 时，映射 `format`。",
                    "该命令用于发布包和运行时完整性检查。",
                ],
                fallback_command="cgc-package-audit",
            ),
            build_mcp_first_command_template(
                filename="cgc-external-audit.md",
                description="审计外部 MCP 能力注册与接入状态",
                argument_hint="[参数]",
                primary_tool="codecgc.external_audit",
                direct_rules=[
                    "映射可选字段 `workspace` 和 `format`。",
                    "该命令用于外部能力策略与注册检查。",
                ],
                fallback_command="cgc-external-audit",
            ),
            build_mcp_first_command_template(
                filename="cgc-external-status.md",
                description="查看外部 MCP 能力状态面板",
                argument_hint="[参数]",
                primary_tool="codecgc.external_status",
                direct_rules=[
                    "映射可选字段 `workspace` 和 `format`。",
                    "该命令用于日常快速查看外部能力登记状态与本地 MCP 观测结果。",
                ],
                fallback_command="cgc-external-status",
            ),
            build_mcp_first_command_template(
                filename="cgc-release-readiness.md",
                description="运行 CodeCGC 发布就绪检查",
                argument_hint="[参数]",
                primary_tool="codecgc.release_readiness",
                direct_rules=[
                    "映射可选字段 `workspace` 和 `format`。",
                    "该命令用于联合检查发布、维护和运维就绪状态。",
                ],
                fallback_command="cgc-release-readiness",
            ),
            build_mcp_first_command_template(
                filename="cgc-lifecycle.md",
                description="审计 CodeCGC 生命周期覆盖情况",
                argument_hint="[参数]",
                primary_tool="codecgc.lifecycle",
                direct_rules=[
                    "当用户明确要求 `summary` 或 `json` 时，映射 `format`。",
                    "该命令用于检查 roadmap、workflow、execution 的生命周期覆盖情况。",
                ],
                fallback_command="cgc-lifecycle",
            ),
        ]
    )
    templates["cgc-install.md"] = """---
description: Install or repair CodeCGC project-local integration
argument-hint: "[optional install arguments]"
---

Use the `codecgc.install` MCP tool as the primary path.

Default behavior:

- Run project-local install for the current workspace.
- Do not install user-level Claude files unless the user explicitly asks for `--mode user`.
- Treat `model-routing.yaml` as the single routing policy source.

Argument mapping:

- No arguments: call `codecgc.install` with `mode: "local"`.
- `status`: call `codecgc.install` with `mode: "status"`.
- `doctor`: call `codecgc.install` with `mode: "doctor"`.
- `--workspace <dir>`: pass the workspace through.
- `--mode user-dry-run`: preview user-level files only.
- `--mode user`: only run if the user explicitly asks to write user-level Claude integration.

Fallback:

- If the MCP tool is unavailable, run `cgc-install` with the same arguments from the target project root.
- After install, run or suggest `cgc-start`, `cgc-status`, and `cgc-doctor`.
"""
    templates["cgc-start.md"] = """---
description: Show the CodeCGC first-run entry guide for this project
argument-hint: "[optional workspace]"
---

Use `codecgc.start` as the primary path.

Default behavior:

- Treat this as a read-only onboarding/status entry.
- Summarize the project-local `codecgc/START_HERE.md` guide if present.
- If the guide is missing, tell the user to run `/cgc-install`.
- Keep the answer short and in Chinese.

Argument mapping:

- No arguments: call `codecgc.start`.
- `--workspace <dir>`: pass the workspace through.

Fallback:

- If the MCP tool is unavailable, run `cgc-start` from the target project root.
- If `cgc-start` reports missing onboarding, suggest `cgc-install`.
"""
    return templates


def write_custom_command_files(target_dir: Path, bin_dir: Path) -> list[str]:
    target_dir.mkdir(parents=True, exist_ok=True)
    templates = build_custom_command_templates(bin_dir)
    written: list[str] = []
    for filename, content in templates.items():
        path = target_dir / filename
        path.write_text(content, encoding="utf-8")
        written.append(str(path))
    return written


def is_codecgc_route_edit_hook(hook: Any) -> bool:
    if not isinstance(hook, dict):
        return False
    if hook.get("type") != "command":
        return False
    command = str(hook.get("command", "")).replace("\\", "/").lower()
    return "route-edit.ps1" in command


def merge_hook_settings(current: dict[str, Any], command_text: str) -> tuple[dict[str, Any], bool]:
    hooks = current.get("hooks")
    expected_hooks = build_hook_payload(command_text)
    if not isinstance(hooks, dict):
        current["hooks"] = expected_hooks
        return current, True

    pre_tool_use = hooks.get("PreToolUse")
    if not isinstance(pre_tool_use, list):
        hooks["PreToolUse"] = expected_hooks["PreToolUse"]
        return current, True

    changed = False
    for item in list(pre_tool_use):
        if not isinstance(item, dict):
            continue
        if item.get("matcher") not in LEGACY_EDIT_GUARDRAIL_MATCHERS | {EDIT_GUARDRAIL_MATCHER}:
            continue
        hook_list = item.get("hooks")
        if not isinstance(hook_list, list):
            continue
        filtered_hooks = [hook for hook in hook_list if not is_codecgc_route_edit_hook(hook)]
        if len(filtered_hooks) != len(hook_list):
            changed = True
            if filtered_hooks:
                item["hooks"] = filtered_hooks
            else:
                pre_tool_use.remove(item)

    expected = expected_hooks["PreToolUse"][0]
    for item in pre_tool_use:
        if not isinstance(item, dict):
            continue
        if item.get("matcher") != expected["matcher"]:
            continue
        hook_list = item.get("hooks")
        if not isinstance(hook_list, list):
            item["hooks"] = expected["hooks"]
            return current, True
        for hook in hook_list:
            if not isinstance(hook, dict):
                continue
            if hook.get("type") == "command" and hook.get("command") == expected["hooks"][0]["command"]:
                return current, changed
        hook_list.append(expected["hooks"][0])
        return current, True

    pre_tool_use.append(expected)
    return current, True


def merge_permission_settings(current: dict[str, Any], allow_rules: list[str]) -> tuple[dict[str, Any], bool]:
    permissions = current.get("permissions")
    changed = False

    if not isinstance(permissions, dict):
        permissions = {}
        current["permissions"] = permissions
        changed = True

    allow = permissions.get("allow")
    if not isinstance(allow, list):
        allow = []
        permissions["allow"] = allow
        changed = True

    existing = {str(item).strip() for item in allow if str(item).strip()}
    for rule in allow_rules:
        normalized = str(rule).strip()
        if not normalized or normalized in existing:
            continue
        allow.append(normalized)
        existing.add(normalized)
        changed = True

    return current, changed


def write_json_file(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def build_project_claude_settings(workspace_paths: dict[str, Path]) -> dict[str, Any]:
    settings = load_json_file(CLAUDE_SETTINGS_TEMPLATE)
    merged_settings, _ = merge_hook_settings(
        settings,
        build_workspace_hook_command(workspace_paths),
    )
    merged_settings, _ = merge_permission_settings(merged_settings, DEFAULT_ALLOWED_TOOLS)
    return merged_settings


def shell_quote(value: str) -> str:
    text = str(value)
    if not text:
        return '""'
    if any(char.isspace() for char in text) or any(char in text for char in '"&()[]{}^=;!+,`~'):
        escaped = text.replace('"', '\\"')
        return f'"{escaped}"'
    return text


def is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(keyword in lowered for keyword in SENSITIVE_KEYWORDS)


def sanitize_for_preview(value: Any, key_hint: str = "") -> Any:
    if isinstance(value, dict):
        return {
            str(key): ("***REDACTED***" if is_sensitive_key(str(key)) else sanitize_for_preview(item, str(key)))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize_for_preview(item, key_hint) for item in value]
    if is_sensitive_key(key_hint):
        return "***REDACTED***"
    return value


def settings_have_hook_command(settings: dict[str, Any], command_text: str) -> bool:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return False
    pre_tool_use = hooks.get("PreToolUse")
    if not isinstance(pre_tool_use, list):
        return False
    for item in pre_tool_use:
        if not isinstance(item, dict):
            continue
        if item.get("matcher") != EDIT_GUARDRAIL_MATCHER:
            continue
        hook_list = item.get("hooks")
        if not isinstance(hook_list, list):
            continue
        for hook in hook_list:
            if not isinstance(hook, dict):
                continue
            if hook.get("type") == "command" and hook.get("command") == command_text:
                return True
    return False


def settings_have_allowed_tools(settings: dict[str, Any], allow_rules: list[str]) -> bool:
    permissions = settings.get("permissions")
    if not isinstance(permissions, dict):
        return False
    allow = permissions.get("allow")
    if not isinstance(allow, list):
        return False
    existing = {str(item).strip() for item in allow if str(item).strip()}
    return all(str(rule).strip() in existing for rule in allow_rules)


RUNTIME_MCP_SERVER_SPECS: dict[str, dict[str, Any]] = {
    "codecgc": {
        "module": "codecgcmcp.cli",
        "pythonpath_suffixes": ["scripts", "codecgcmcp/src"],
    },
    "codex": {
        "module": "codexmcp.cli",
        "pythonpath_suffixes": ["scripts", "codecgcmcp/src", "codexmcp/src"],
    },
    "gemini": {
        "module": "geminimcp.cli",
        "pythonpath_suffixes": ["scripts", "codecgcmcp/src", "geminimcp/src"],
    },
}


def _normalize_path_parts(path_text: str) -> tuple[str, ...]:
    text = str(path_text).replace("\\", "/").strip().rstrip("/")
    if not text:
        return ()
    return tuple(part.lower() for part in text.split("/") if part)


def _match_runtime_root(path_text: str, suffix: str) -> tuple[str, ...] | None:
    parts = _normalize_path_parts(path_text)
    suffix_parts = _normalize_path_parts(suffix)
    if not parts or not suffix_parts or len(parts) < len(suffix_parts):
        return None
    if parts[-len(suffix_parts) :] != suffix_parts:
        return None
    return parts[: -len(suffix_parts)]


def _collect_runtime_roots(entries: list[str], suffix: str) -> set[tuple[str, ...]]:
    roots: set[tuple[str, ...]] = set()
    for entry in entries:
        root = _match_runtime_root(entry, suffix)
        if root is not None:
            roots.add(root)
    return roots


def mcp_server_matches_runtime_shape(server_payload: dict[str, Any], spec: dict[str, Any]) -> bool:
    command_text = str(server_payload.get("command", "")).strip()
    if not command_text:
        return False

    args = server_payload.get("args")
    if args != ["-m", spec["module"]]:
        return False

    env = server_payload.get("env")
    if not isinstance(env, dict):
        return False

    workspace_text = str(env.get("CODECGC_WORKSPACE_ROOT", "")).strip()
    if not workspace_text:
        return False

    pythonpath_text = str(env.get("PYTHONPATH", "")).strip()
    if not pythonpath_text:
        return False

    entries = [item.strip() for item in pythonpath_text.split(os.pathsep) if item.strip()]
    if not entries:
        return False

    candidate_roots: set[tuple[str, ...]] | None = None
    for suffix in spec["pythonpath_suffixes"]:
        matching_roots = _collect_runtime_roots(entries, str(suffix))
        if not matching_roots:
            return False
        candidate_roots = matching_roots if candidate_roots is None else candidate_roots & matching_roots
        if not candidate_roots:
            return False
    return True


def mcp_config_matches_runtime_shape(payload: dict[str, Any]) -> bool:
    servers = payload.get("mcpServers")
    if not isinstance(servers, dict):
        return False

    for server_name, spec in RUNTIME_MCP_SERVER_SPECS.items():
        server_payload = servers.get(server_name)
        if not isinstance(server_payload, dict):
            return False
        if not mcp_server_matches_runtime_shape(server_payload, spec):
            return False
    return True


def build_workspace_hook_command(workspace_paths: dict[str, Path]) -> str:
    package_root = str(WORKSPACE).replace("'", "''")
    workspace_root_path = Path(workspace_paths["root"])
    hook_script_path = workspace_paths.get("hook_script", workspace_root_path / ".claude" / "hooks" / "route-edit.ps1")
    workspace_root = str(workspace_root_path).replace("'", "''")
    hook_script = str(hook_script_path).replace("\\", "/").replace("'", "''")
    return (
        "powershell -ExecutionPolicy Bypass -Command "
        f"\"$env:CODECGC_PACKAGE_ROOT='{package_root}'; "
        f"$env:CODECGC_WORKSPACE_ROOT='{workspace_root}'; "
        f"& '{hook_script}'\""
    )


def build_mode_summary_payload(
    *,
    scope: str,
    human_summary: str,
    recommended_next_action: str = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = {
        "scope": scope,
        "human_summary": human_summary,
        "recommended_next_action": recommended_next_action,
    }
    if extra:
        summary.update(extra)
    return summary


def install_local_runtime(override_workspace: str = "") -> dict[str, Any]:
    workspace_paths = get_workspace_paths(override_workspace)
    mcp_path = write_mcp_config(workspace_paths["mcp"], workspace_paths["root"])
    routing_path = sync_workspace_routing_file(workspace_paths["routing_file"])

    workspace_paths["claude_dir"].mkdir(parents=True, exist_ok=True)
    workspace_paths["hooks_dir"].mkdir(parents=True, exist_ok=True)
    workflow_dirs = ensure_workspace_workflow_dirs(workspace_paths["root"])

    write_json_file(
        workspace_paths["settings"],
        build_project_claude_settings(workspace_paths),
    )
    codex_policy_path = copy_template_file(CODEX_POLICY_TEMPLATE, workspace_paths["codex_policy"])
    gemini_policy_path = copy_template_file(GEMINI_POLICY_TEMPLATE, workspace_paths["gemini_policy"])

    if PROJECT_HOOK_PATH.resolve() != workspace_paths["hook_script"].resolve():
        shutil.copyfile(PROJECT_HOOK_PATH, workspace_paths["hook_script"])
    written_commands = write_custom_command_files(workspace_paths["commands_dir"], WORKSPACE / "bin")
    onboarding_file = write_project_onboarding_file(workspace_paths["root"])

    summary = build_mode_summary_payload(
        scope="项目级 Claude 与 MCP 集成面",
        human_summary="项目级 CodeCGC 集成文件已同步。",
        recommended_next_action="cgc-start",
    )

    return {
        "success": True,
        "mode": "local",
        "workspace": str(workspace_paths["root"]),
        "mcp_config": str(mcp_path),
        "routing_file": str(routing_path),
        "claude_settings": str(workspace_paths["settings"]),
        "codex_policy": str(codex_policy_path),
        "gemini_policy": str(gemini_policy_path),
        "hook_script": str(workspace_paths["hook_script"]),
        "commands_dir": str(workspace_paths["commands_dir"]),
        "onboarding_file": str(onboarding_file),
        "workflow_dirs": workflow_dirs,
        "command_files": written_commands,
        "notes": [
            "Repository-local MCP config was synced from the executor registry.",
            "Project-local model-routing.yaml was synchronized as the policy source of truth.",
            "Project-local codecgc workflow directories were initialized.",
            "Claude pre-edit guardrail hook was synchronized into the target workspace.",
            "Claude project permissions were rendered from codecgc/templates/claude/settings.local.json.",
            "Project-local Codex policy contract was synchronized into .codex/codecgcrc.json.",
            "Project-local Gemini policy was synchronized into .gemini/policies/codecgc-policy.toml.",
            "Project-local Claude slash commands were synchronized into .claude/commands.",
            "Project-local codecgc/START_HERE.md was written as the first-run entry guide.",
            "This mode prepares project-level integration surfaces for the selected workspace.",
        ],
        "summary": summary,
    }


def build_user_hook_command(user_paths: dict[str, Path]) -> str:
    package_root = str(WORKSPACE).replace("'", "''")
    workspace_root = str(WORKSPACE).replace("'", "''")
    hook_script = str(user_paths["hook_script"]).replace("'", "''")
    return (
        "powershell -ExecutionPolicy Bypass -Command "
        f"\"$env:CODECGC_PACKAGE_ROOT='{package_root}'; "
        f"$env:CODECGC_WORKSPACE_ROOT='{workspace_root}'; "
        f"& '{hook_script}'\""
    )


def preview_user_install(override_root: str = "") -> dict[str, Any]:
    user_paths = get_user_claude_paths(override_root)
    user_settings = load_json_file(user_paths["settings"])
    merged_settings, settings_changed = merge_hook_settings(user_settings, build_user_hook_command(user_paths))
    merged_settings, permissions_changed = merge_permission_settings(merged_settings, DEFAULT_ALLOWED_TOOLS)
    mcp_config = build_mcp_config(WORKSPACE)
    recommended_next_action = "cgc-install"
    summary = build_mode_summary_payload(
        scope="用户级 Claude 集成预演",
        human_summary="已完成用户级 Claude 集成预演，未写入任何文件。",
        recommended_next_action=recommended_next_action,
    )

    return {
        "success": True,
        "mode": "user-dry-run",
        "workspace": str(WORKSPACE),
        "user_claude_root": str(user_paths["root"]),
        "planned_files": {
            "settings_json": str(user_paths["settings"]),
            "mcp_json": str(user_paths["mcp"]),
            "hook_script": str(user_paths["hook_script"]),
            "commands_dir": str(user_paths["commands_dir"]),
        },
        "would_write": {
            "settings_changed": settings_changed or permissions_changed or not user_paths["settings"].exists(),
            "mcp_changed": True,
            "hook_changed": True,
            "commands_changed": True,
        },
        "preview": {
            "settings": sanitize_for_preview(merged_settings),
            "mcp": mcp_config,
        },
        "notes": [
            "This mode does not modify user-level Claude files.",
            "Use this preview only when intentionally inspecting a user-level integration surface.",
            "The preview includes MCP tool allow rules for codecgc, codex, and gemini servers.",
            "Current CodeCGC product policy still defaults to project-local installation.",
        ],
        "summary": summary,
    }


def install_user_runtime(override_root: str = "") -> dict[str, Any]:
    user_paths = get_user_claude_paths(override_root)
    user_paths["root"].mkdir(parents=True, exist_ok=True)
    user_paths["hooks_dir"].mkdir(parents=True, exist_ok=True)
    user_paths["commands_dir"].mkdir(parents=True, exist_ok=True)

    settings = load_json_file(user_paths["settings"])
    merged_settings, settings_changed = merge_hook_settings(settings, build_user_hook_command(user_paths))
    merged_settings, permissions_changed = merge_permission_settings(merged_settings, DEFAULT_ALLOWED_TOOLS)
    write_json_file(user_paths["settings"], merged_settings)
    write_json_file(user_paths["mcp"], build_mcp_config(WORKSPACE))
    shutil.copyfile(PROJECT_HOOK_PATH, user_paths["hook_script"])
    written_commands = write_custom_command_files(user_paths["commands_dir"], WORKSPACE / "bin")
    summary = build_mode_summary_payload(
        scope="用户级 Claude 集成面",
        human_summary="用户级 Claude 集成文件已写入。",
        recommended_next_action="cgc-install --mode status",
    )

    return {
        "success": True,
        "mode": "user",
        "workspace": str(WORKSPACE),
        "user_claude_root": str(user_paths["root"]),
        "written_files": {
            "settings_json": str(user_paths["settings"]),
            "mcp_json": str(user_paths["mcp"]),
            "hook_script": str(user_paths["hook_script"]),
            "commands_dir": str(user_paths["commands_dir"]),
        },
        "changes": {
            "settings_changed": settings_changed or permissions_changed or not user_paths["settings"].exists(),
            "mcp_changed": True,
            "hook_changed": True,
            "commands_changed": True,
        },
        "command_files": written_commands,
        "notes": [
            "User-level Claude integration files were written to the selected root.",
            "The user-level hook script was copied from the project hook source.",
            "MCP tool allow rules were merged into ~/.claude/settings.json.",
            "User-level Claude slash commands were written to ~/.claude/commands.",
            "This mode is explicit and should be used only when a broader Claude integration surface is intended.",
        ],
        "summary": summary,
    }


def build_workspace_install_command(workspace_root: Path) -> str:
    return f"cgc-install --mode local --workspace {shell_quote(str(workspace_root))}"


def build_user_preview_command(user_root: Path) -> str:
    return f"cgc-install --mode user-dry-run --user-root {shell_quote(str(user_root))}"


def build_doctor_fix_command(workspace_root: Path) -> str:
    return f"cgc-install --workspace {shell_quote(str(workspace_root))}"


def build_install_mode_summary(result: dict[str, Any]) -> str:
    mode = str(result.get("mode", "")).strip()

    if mode == "local":
        lines = [
            f"- 工作区: {result.get('workspace', '')}",
            "- 范围: 项目级 Claude 与 MCP 集成面",
            "- 摘要: 项目级 CodeCGC 集成文件已同步。",
            f"- MCP 配置: {result.get('mcp_config', '')}",
            f"- Routing 文件: {result.get('routing_file', '')}",
            f"- Claude 设置: {result.get('claude_settings', '')}",
            f"- Codex 策略: {result.get('codex_policy', '')}",
            f"- Gemini 策略: {result.get('gemini_policy', '')}",
            f"- Hook 脚本: {result.get('hook_script', '')}",
            f"- Slash Commands: {result.get('commands_dir', '')}",
            f"- 新手入口: {result.get('onboarding_file', '')}",
            "- 说明: 可选外部能力如 MemOS 不由 cgc-install 自动写入；如需启用，请在 Claude 中单独配置官方 MCP。",
        ]
        next_actions = [
            "cgc-start",
            "cgc-status",
            "cgc-doctor",
        ]
        return render_summary_block("CodeCGC 安装", lines, next_actions)

    if mode == "user-dry-run":
        planned = result.get("planned_files", {}) if isinstance(result.get("planned_files"), dict) else {}
        lines = [
            f"- 工作区: {result.get('workspace', '')}",
            f"- 用户 Claude 根目录: {result.get('user_claude_root', '')}",
            "- 范围: 用户级 Claude 集成预演",
            "- 摘要: 已完成用户级 Claude 集成预演，未写入任何文件。",
            f"- 预演 Settings: {planned.get('settings_json', '')}",
            f"- 预演 MCP: {planned.get('mcp_json', '')}",
            f"- 预演 Hook: {planned.get('hook_script', '')}",
            f"- 预演 Slash Commands: {planned.get('commands_dir', '')}",
            "- 说明: 该预演只覆盖 CodeCGC 必需执行器；MemOS 等可选外部能力仍建议在 Claude 中独立配置。",
        ]
        next_actions = []
        user_root = str(result.get("user_claude_root", "")).strip()
        if user_root:
            next_actions.append("cgc-install")
        next_actions.append("cgc-install --mode status")
        return render_summary_block("CodeCGC 用户级预演", lines, next_actions)

    if mode == "user":
        written = result.get("written_files", {}) if isinstance(result.get("written_files"), dict) else {}
        lines = [
            f"- 工作区: {result.get('workspace', '')}",
            f"- 用户 Claude 根目录: {result.get('user_claude_root', '')}",
            "- 范围: 用户级 Claude 集成面",
            "- 摘要: 用户级 Claude 集成文件已写入。",
            f"- Settings: {written.get('settings_json', '')}",
            f"- MCP: {written.get('mcp_json', '')}",
            f"- Hook 脚本: {written.get('hook_script', '')}",
            f"- Slash Commands: {written.get('commands_dir', '')}",
            "- 说明: 该安装只写入 CodeCGC 必需执行器；MemOS 等可选外部能力仍需在 Claude 中单独配置。",
        ]
        next_actions = [
            "cgc-install --mode status",
            "cgc-doctor",
        ]
        return render_summary_block("CodeCGC 用户级安装", lines, next_actions)

    return ""


def collect_project_status(workspace_paths: dict[str, Path]) -> dict[str, Any]:
    expected_mcp = build_mcp_config(workspace_paths["root"])
    expected_hook_command = build_workspace_hook_command(workspace_paths)
    expected_hook_text = load_text_file(PROJECT_HOOK_PATH)
    expected_settings = build_project_claude_settings(workspace_paths)
    expected_codex_policy = load_text_file(CODEX_POLICY_TEMPLATE)
    expected_gemini_policy = load_text_file(GEMINI_POLICY_TEMPLATE)
    current_settings = load_json_file(workspace_paths["settings"])
    current_mcp = load_json_file(workspace_paths["mcp"])
    current_hook_text = load_text_file(workspace_paths["hook_script"])
    current_codex_policy = load_text_file(workspace_paths["codex_policy"])
    current_gemini_policy = load_text_file(workspace_paths["gemini_policy"])
    routing_exists = workspace_paths["routing_file"].exists()
    policy_valid = policy_file_is_valid(workspace_paths["routing_file"]) if routing_exists else False
    workflow_dirs_ready = workspace_workflow_dirs_ready(workspace_paths["root"])
    onboarding_ready = onboarding_file_is_valid(workspace_paths["onboarding_file"])

    hook_registered = settings_have_hook_command(current_settings, expected_hook_command)
    permissions_registered = settings_have_allowed_tools(current_settings, DEFAULT_ALLOWED_TOOLS)
    settings_matches = current_settings == expected_settings if workspace_paths["settings"].exists() else False
    mcp_matches = current_mcp == expected_mcp if workspace_paths["mcp"].exists() else False
    hook_file_matches = current_hook_text == expected_hook_text if workspace_paths["hook_script"].exists() else False
    codex_policy_matches = (
        current_codex_policy == expected_codex_policy if workspace_paths["codex_policy"].exists() else False
    )
    gemini_policy_matches = (
        current_gemini_policy == expected_gemini_policy if workspace_paths["gemini_policy"].exists() else False
    )

    missing = []
    if not routing_exists:
        missing.append("routing_file")
    if routing_exists and not policy_valid:
        missing.append("routing_policy")
    if not workflow_dirs_ready:
        missing.append("workflow_dirs")
    if not mcp_matches:
        missing.append("mcp_json")
    if not settings_matches:
        missing.append("claude_settings_local")
    if not hook_registered:
        missing.append("claude_settings_hook")
    if not permissions_registered:
        missing.append("claude_settings_permissions")
    if not hook_file_matches:
        missing.append("hook_script")
    if not onboarding_ready:
        missing.append("onboarding_file")
    if not codex_policy_matches:
        missing.append("codex_policy")
    if not gemini_policy_matches:
        missing.append("gemini_policy")

    ready = not missing
    return {
        "mcp_json_path": str(workspace_paths["mcp"]),
        "routing_file_path": str(workspace_paths["routing_file"]),
        "claude_settings_path": str(workspace_paths["settings"]),
        "legacy_claude_settings_path": str(workspace_paths["legacy_settings"]),
        "codex_policy_path": str(workspace_paths["codex_policy"]),
        "gemini_policy_path": str(workspace_paths["gemini_policy"]),
        "hook_script_path": str(workspace_paths["hook_script"]),
        "onboarding_file_path": str(workspace_paths["onboarding_file"]),
        "mcp_json_exists": workspace_paths["mcp"].exists(),
        "routing_file_exists": routing_exists,
        "routing_policy_valid": policy_valid,
        "workflow_dirs_ready": workflow_dirs_ready,
        "onboarding_ready": onboarding_ready,
        "workflow_dirs_expected": [str(workspace_paths["root"] / item) for item in PROJECT_WORKFLOW_DIRS],
        "claude_settings_exists": workspace_paths["settings"].exists(),
        "legacy_claude_settings_exists": workspace_paths["legacy_settings"].exists(),
        "codex_policy_exists": workspace_paths["codex_policy"].exists(),
        "gemini_policy_exists": workspace_paths["gemini_policy"].exists(),
        "hook_exists": workspace_paths["hook_script"].exists(),
        "onboarding_exists": workspace_paths["onboarding_file"].exists(),
        "mcp_matches_expected": mcp_matches,
        "claude_settings_matches_expected": settings_matches,
        "hook_registered": hook_registered,
        "permissions_registered": permissions_registered,
        "hook_file_matches_expected": hook_file_matches,
        "codex_policy_matches_expected": codex_policy_matches,
        "gemini_policy_matches_expected": gemini_policy_matches,
        "ready": ready,
        "missing_or_outdated": missing,
        "recommended_command": "" if ready else build_workspace_install_command(workspace_paths["root"]),
        "hook_expected": {"hooks": build_hook_payload(expected_hook_command)},
        "permissions_expected": {"permissions": {"allow": DEFAULT_ALLOWED_TOOLS}},
    }


def collect_user_status(user_paths: dict[str, Path]) -> dict[str, Any]:
    expected_mcp = build_mcp_config(WORKSPACE)
    expected_hook_command = build_user_hook_command(user_paths)
    expected_hook_text = load_text_file(PROJECT_HOOK_PATH)
    current_settings = load_json_file(user_paths["settings"])
    current_mcp = load_json_file(user_paths["mcp"])
    current_hook_text = load_text_file(user_paths["hook_script"])

    hook_registered = settings_have_hook_command(current_settings, expected_hook_command)
    permissions_registered = settings_have_allowed_tools(current_settings, DEFAULT_ALLOWED_TOOLS)
    mcp_matches_exact = current_mcp == expected_mcp if user_paths["mcp"].exists() else False
    mcp_matches_runtime = mcp_config_matches_runtime_shape(current_mcp) if user_paths["mcp"].exists() else False
    mcp_matches = mcp_matches_exact or mcp_matches_runtime
    hook_file_matches = current_hook_text == expected_hook_text if user_paths["hook_script"].exists() else False

    missing = []
    if not mcp_matches:
        missing.append("mcp_json")
    if not hook_registered:
        missing.append("claude_settings_hook")
    if not permissions_registered:
        missing.append("claude_settings_permissions")
    if not hook_file_matches:
        missing.append("hook_script")

    ready = not missing
    return {
        "root": str(user_paths["root"]),
        "settings_json": str(user_paths["settings"]),
        "mcp_json": str(user_paths["mcp"]),
        "hook_script": str(user_paths["hook_script"]),
        "settings_exists": user_paths["settings"].exists(),
        "mcp_exists": user_paths["mcp"].exists(),
        "hook_exists": user_paths["hook_script"].exists(),
        "mcp_matches_expected": mcp_matches,
        "mcp_matches_expected_exact": mcp_matches_exact,
        "mcp_matches_runtime_shape": mcp_matches_runtime,
        "hook_registered": hook_registered,
        "permissions_registered": permissions_registered,
        "hook_file_matches_expected": hook_file_matches,
        "ready": ready,
        "missing_or_outdated": missing,
        "recommended_command": "" if ready else build_user_preview_command(user_paths["root"]),
    }


def collect_install_status(override_workspace: str = "") -> dict[str, Any]:
    workspace_paths = get_workspace_paths(override_workspace)
    user_paths = get_user_claude_paths()
    project_status = collect_project_status(workspace_paths)
    user_status = collect_user_status(user_paths)
    recommended_next_command = project_status["recommended_command"] or user_status["recommended_command"]
    human_summary = "项目级 CodeCGC 集成已就绪。"
    if not project_status["ready"]:
        human_summary = "项目级 CodeCGC 集成尚未就绪。"
    elif not user_status["ready"]:
        human_summary = "项目级集成已就绪；用户级 Claude 集成仍是可选项，当前尚未就绪。"
    status_summary = {
        "project_ready": project_status["ready"],
        "user_ready": user_status["ready"],
        "default_policy": "project-local-first",
        "recommended_next_command": recommended_next_command,
        "recommended_project_command": project_status["recommended_command"],
        "recommended_user_command": user_status["recommended_command"],
        "human_summary": human_summary,
        "scope": "项目级集成就绪状态，以及用户级 Claude 集成预演状态",
    }

    status_summary.update(
        {
            "default_policy": "project-local-first",
            "recommended_next_command": project_status["recommended_command"],
            "recommended_user_command": "",
            "human_summary": (
                "Project-local CodeCGC integration is ready."
                if project_status["ready"]
                else "Project-local CodeCGC integration is missing or outdated."
            ),
            "scope": "project-local integration status; user-level config is optional preview only",
        }
    )

    return {
        "success": True,
        "mode": "status",
        "workspace": str(workspace_paths["root"]),
        "summary": status_summary,
        "status_summary": status_summary,
        "project": project_status,
        "user_preview_targets": user_status,
    }


def collect_start_status(override_workspace: str = "") -> dict[str, Any]:
    workspace_paths = get_workspace_paths(override_workspace)
    project_status = collect_project_status(workspace_paths)
    onboarding_path = workspace_paths["onboarding_file"]
    onboarding_ready = onboarding_file_is_valid(onboarding_path)
    guide_text = load_text_file(onboarding_path) if onboarding_ready else ""
    recommended_next_action = "cgc-status" if onboarding_ready else build_workspace_install_command(workspace_paths["root"])
    human_summary = (
        "CodeCGC first-run guide is ready. Start with /cgc or cgc after status/doctor are green."
        if onboarding_ready
        else "CodeCGC first-run guide is missing or outdated. Run project-local install first."
    )
    quick_actions = [
        "/cgc-status",
        "/cgc-doctor",
        "/cgc <你的需求>",
        "cgc-status",
        "cgc-doctor",
        "cgc \"你的需求\"",
    ]
    if not onboarding_ready:
        quick_actions = ["/cgc-install", build_workspace_install_command(workspace_paths["root"])]

    return {
        "success": True,
        "mode": "start",
        "workspace": str(workspace_paths["root"]),
        "summary": {
            "ready": onboarding_ready,
            "human_summary": human_summary,
            "scope": "project-local first-run guide and next actions",
            "recommended_next_action": recommended_next_action,
            "quick_actions": quick_actions,
        },
        "onboarding": {
            "path": str(onboarding_path),
            "exists": onboarding_path.exists(),
            "ready": onboarding_ready,
            "relative_path": PROJECT_ONBOARDING_RELATIVE_PATH,
            "guide_excerpt": guide_text[:1200],
        },
        "project": project_status,
    }


def find_python_command() -> str:
    candidates = ["python", "py"] if os.name == "nt" else ["python3", "python"]
    for candidate in candidates:
        if shutil.which(candidate):
            return candidate
    return ""


def probe_python_import(runtime_command: str, module_name: str, runtime_env: dict[str, str]) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [runtime_command, "-c", f"import {module_name}; print('ok')"],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=runtime_env,
        )
    except Exception as error:
        return {
            "ok": False,
            "detail": str(error),
            "error_type": type(error).__name__,
            "stdout": "",
            "stderr": "",
            "returncode": None,
        }

    stdout_text = (result.stdout or "").strip()
    stderr_text = (result.stderr or "").strip()
    return {
        "ok": result.returncode == 0 and stdout_text == "ok",
        "detail": stdout_text if result.returncode == 0 and stdout_text == "ok" else stderr_text or stdout_text or f"returncode={result.returncode}",
        "error_type": "",
        "stdout": stdout_text,
        "stderr": stderr_text,
        "returncode": result.returncode,
    }


def build_pip_install_command(python_command: str, requirement: str) -> str:
    runtime_command = python_command.strip() or sys.executable
    return f"{shell_quote(runtime_command)} -m pip install {shell_quote(requirement)}"


def build_local_editable_install_command(python_command: str) -> str:
    runtime_command = python_command.strip() or sys.executable
    codecgcmcp_path = WORKSPACE / "codecgcmcp"
    codexmcp_path = WORKSPACE / "codexmcp"
    geminimcp_path = WORKSPACE / "geminimcp"
    if not (codecgcmcp_path / "pyproject.toml").exists():
        return ""
    if not (codexmcp_path / "pyproject.toml").exists():
        return ""
    if not (geminimcp_path / "pyproject.toml").exists():
        return ""
    return (
        f"{shell_quote(runtime_command)} -m pip install -e {shell_quote(str(codecgcmcp_path))} "
        f"-e {shell_quote(str(codexmcp_path))} "
        f"-e {shell_quote(str(geminimcp_path))}"
    )


def format_bool_zh(value: Any) -> str:
    return "是" if bool(value) else "否"


def format_list_zh(items: Any, empty_text: str = "无") -> str:
    if not isinstance(items, list):
        return empty_text
    values = [str(item).strip() for item in items if str(item).strip()]
    return "、".join(values) if values else empty_text


def classify_doctor_failures(
    checks: list[dict[str, Any]],
    configured_python_command: str,
    workspace_root: Path,
) -> tuple[list[dict[str, str]], list[str]]:
    failure_categories: list[dict[str, str]] = []
    recommended_commands: list[str] = []
    seen_codes: set[str] = set()
    seen_commands: set[str] = set()

    def add_failure(code: str, summary: str, suggestion: str, command: str = "") -> None:
        if code in seen_codes:
            return
        seen_codes.add(code)
        failure_categories.append(
            {
                "code": code,
                "summary": summary,
                "suggestion": suggestion,
            }
        )
        if command and command not in seen_commands:
            seen_commands.add(command)
            recommended_commands.append(command)

    runtime_command = configured_python_command.strip() or sys.executable
    install_command = build_doctor_fix_command(workspace_root)
    editable_install_command = build_local_editable_install_command(runtime_command)
    failed_names = {
        str(item.get("name", "")).strip()
        for item in checks
        if isinstance(item, dict) and not item.get("ok")
    }
    configured_python_missing = "configured_python_command_exists" in failed_names

    for item in checks:
        if not isinstance(item, dict) or item.get("ok"):
            continue
        name = str(item.get("name", "")).strip()
        detail = str(item.get("detail", "")).strip()

        if name == "python_available":
            add_failure(
                "python-unavailable",
                "系统 PATH 中没有找到可用 Python 命令。",
                "先安装 Python 3.12+，并确保 `python` 或 `py` 可在命令行直接调用。",
            )
            continue

        if name == "configured_python_command_exists":
            add_failure(
                "configured-python-missing",
                "配置的 Python 解释器不存在或不可执行。",
                "检查 `CODECGC_PYTHON_COMMAND` 是否指向正确解释器，或者移除该变量后重试。",
            )
            continue

        if name == "python_runtime_import_probe_mcp":
            if configured_python_missing:
                continue
            add_failure(
                "mcp-runtime-missing",
                "当前 Python 环境缺少 `mcp` 运行时依赖。",
                "在当前解释器下安装 MCP CLI 依赖后重新执行 doctor。",
                build_pip_install_command(runtime_command, MCP_RUNTIME_REQUIREMENT),
            )
            continue

        if name == "python_runtime_import_probe_codecgcmcp":
            if configured_python_missing:
                continue
            if "No module named 'codecgcmcp'" in detail or 'No module named "codecgcmcp"' in detail:
                add_failure(
                    "codecgcmcp-package-missing",
                    "当前解释器无法导入本地 `codecgcmcp` 包。",
                    "确认当前安装包已包含 `codecgcmcp/src`；仓库开发环境可执行本地 editable install，安装产物则应重新安装 CodeCGC 包。",
                    editable_install_command,
                )
            else:
                add_failure(
                    "codecgcmcp-runtime-broken",
                    "`codecgcmcp` 启动入口存在，但当前运行时仍无法导入。",
                    "仓库开发环境可先重装本地编排器包；若你使用的是已安装产物，则优先重新安装 CodeCGC，再检查编排器源码是否缺失或损坏。",
                    editable_install_command,
                )
            continue

        if name == "python_runtime_import_probe_codexmcp":
            if configured_python_missing:
                continue
            if "No module named 'codexmcp'" in detail or 'No module named "codexmcp"' in detail:
                add_failure(
                    "codexmcp-package-missing",
                    "当前解释器无法导入本地 `codexmcp` 包。",
                    "确认当前安装包已包含 `codexmcp/src`；仓库开发环境可执行本地 editable install，安装产物则应重新安装 CodeCGC 包。",
                    editable_install_command,
                )
            else:
                add_failure(
                    "codexmcp-runtime-broken",
                    "`codexmcp` 启动入口存在，但当前运行时仍无法导入。",
                    "仓库开发环境可先重装本地执行器包；若你使用的是已安装产物，则优先重新安装 CodeCGC，再检查执行器源码是否缺失或损坏。",
                    editable_install_command,
                )
            continue

        if name == "python_runtime_import_probe_geminimcp":
            if configured_python_missing:
                continue
            if "No module named 'geminimcp'" in detail or 'No module named "geminimcp"' in detail:
                add_failure(
                    "geminimcp-package-missing",
                    "当前解释器无法导入本地 `geminimcp` 包。",
                    "确认当前安装包已包含 `geminimcp/src`；仓库开发环境可执行本地 editable install，安装产物则应重新安装 CodeCGC 包。",
                    editable_install_command,
                )
            else:
                add_failure(
                    "geminimcp-runtime-broken",
                    "`geminimcp` 启动入口存在，但当前运行时仍无法导入。",
                    "仓库开发环境可先重装本地执行器包；若你使用的是已安装产物，则优先重新安装 CodeCGC，再检查执行器源码是否缺失或损坏。",
                    editable_install_command,
                )
            continue

        if name == "project_integration_ready":
            add_failure(
                "project-integration-missing",
                "项目级 Claude 集成面未就绪。",
                "重新执行项目级安装以同步 `.mcp.json`、hook 与 Claude settings。",
                install_command,
            )
            continue

        if name == "onboarding_file_ready":
            add_failure(
                "onboarding-guide-missing",
                "项目级新手入口文件缺失或已过期。",
                "重新执行项目级安装以同步 `codecgc/START_HERE.md` 与 `/cgc-start` 入口。",
                install_command,
            )
            continue

        if name in {"routing_file_exists", "routing_policy_valid", "project_hook_source_exists"}:
            add_failure(
                "packaged-runtime-missing-files",
                "运行时所需的 policy、路由文件或 hook 源文件缺失/无效。",
                "重新执行项目级安装以同步 model-routing.yaml、policy-backed hook 与 Claude settings。",
            )
            continue

    return failure_categories, recommended_commands


def collect_doctor_status(override_workspace: str = "") -> dict[str, Any]:
    workspace_paths = get_workspace_paths(override_workspace)
    project_status = collect_project_status(workspace_paths)
    registry = build_executor_registry()
    python_command = find_python_command()
    configured_python_command = resolve_python_command()

    checks: list[dict[str, Any]] = [
        {
            "name": "workspace_root_exists",
            "ok": workspace_paths["root"].exists(),
            "detail": str(workspace_paths["root"]),
        },
        {
            "name": "python_available",
            "ok": bool(python_command),
            "detail": python_command or "python-not-found",
        },
        {
            "name": "configured_python_command_exists",
            "ok": Path(configured_python_command).exists() if Path(configured_python_command).is_absolute() else bool(shutil.which(configured_python_command)),
            "detail": configured_python_command,
        },
        {
            "name": "routing_file_exists",
            "ok": workspace_paths["routing_file"].exists(),
            "detail": str(workspace_paths["routing_file"]),
        },
        {
            "name": "routing_policy_valid",
            "ok": policy_file_is_valid(workspace_paths["routing_file"]) if workspace_paths["routing_file"].exists() else False,
            "detail": str(workspace_paths["routing_file"]),
        },
        {
            "name": "workflow_dirs_ready",
            "ok": workspace_workflow_dirs_ready(workspace_paths["root"]),
            "detail": str(workspace_paths["root"] / "codecgc"),
        },
        {
            "name": "onboarding_file_ready",
            "ok": onboarding_file_is_valid(workspace_paths["onboarding_file"]),
            "detail": str(workspace_paths["onboarding_file"]),
        },
        {
            "name": "project_hook_source_exists",
            "ok": PROJECT_HOOK_PATH.exists(),
            "detail": str(PROJECT_HOOK_PATH),
        },
    ]

    for target, config in registry.items():
        pythonpath = Path(str(config["pythonpath"]))
        module_path = pythonpath / Path(str(config["python_module"]).replace(".", "/")).with_suffix(".py")
        checks.append(
            {
                "name": f"{target}_pythonpath_exists",
                "ok": pythonpath.exists(),
                "detail": str(pythonpath),
            }
        )
        checks.append(
            {
                "name": f"{target}_entry_module_exists",
                "ok": module_path.exists(),
                "detail": str(module_path),
            }
        )

    runtime_probe_command = configured_python_command if configured_python_command else (python_command or sys.executable)
    runtime_env = dict(os.environ)
    combined_pythonpath = os.pathsep.join(
        [
            str(WORKSPACE / "scripts"),
            str(WORKSPACE / "codecgcmcp" / "src"),
            str(WORKSPACE / "codexmcp" / "src"),
            str(WORKSPACE / "geminimcp" / "src"),
        ]
    )
    existing_pythonpath = runtime_env.get("PYTHONPATH", "").strip()
    runtime_env["PYTHONPATH"] = f"{combined_pythonpath}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else combined_pythonpath

    for module_name in ("mcp", "codecgcmcp.cli", "codexmcp.cli", "geminimcp.cli"):
        probe = probe_python_import(runtime_probe_command, module_name, runtime_env)
        checks.append(
            {
                "name": f"python_runtime_import_probe_{module_name.split('.')[0]}",
                "ok": probe["ok"],
                "detail": probe["detail"],
                "module": module_name,
                "returncode": probe["returncode"],
                "stderr": probe["stderr"],
                "stdout": probe["stdout"],
                "error_type": probe["error_type"],
            }
        )

    checks.append(
        {
            "name": "project_integration_ready",
            "ok": bool(project_status["ready"]),
            "detail": ", ".join(project_status["missing_or_outdated"]) or "ready",
        }
    )

    failed = [item["name"] for item in checks if not item["ok"]]
    ready = not failed
    failure_categories, recommended_runtime_fix_commands = classify_doctor_failures(
        checks,
        configured_python_command,
        workspace_paths["root"],
    )
    human_summary = "CodeCGC 自检通过。"
    if not ready:
        human_summary = "CodeCGC 自检发现运行前置或集成面存在缺失。"
    doctor_summary = {
        "ready": ready,
        "failed_checks": failed,
        "human_summary": human_summary,
        "scope": "运行前置、执行器可导入性，以及项目级集成就绪状态",
        "recommended_fix_command": "" if ready else build_doctor_fix_command(workspace_paths["root"]),
        "recommended_runtime_fix_command": "" if not recommended_runtime_fix_commands else recommended_runtime_fix_commands[0],
        "recommended_runtime_fix_commands": recommended_runtime_fix_commands,
        "failure_categories": failure_categories,
    }

    return {
        "success": True,
        "mode": "doctor",
        "workspace": str(workspace_paths["root"]),
        "summary": doctor_summary,
        "doctor_summary": doctor_summary,
        "checks": checks,
        "project": project_status,
        "python": {
            "current_executable": sys.executable,
            "discovered_command": python_command,
            "configured_command": configured_python_command,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install or inspect CodeCGC integration surfaces.")
    parser.add_argument("--mode", choices=["local", "user-dry-run", "user", "status", "doctor", "start"], default="local")
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="summary",
        help="Output format. Summary is the default product-facing mode; use json for debugging or automation.",
    )
    parser.add_argument(
        "--workspace",
        default="",
        help="Optional target workspace root for local/status modes. Defaults to the current CodeCGC repository root.",
    )
    parser.add_argument("--user-root", default="", help="Optional explicit Claude user root for user/user-dry-run modes.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "local":
        result = install_local_runtime(args.workspace)
    elif args.mode == "user-dry-run":
        result = preview_user_install(args.user_root)
    elif args.mode == "user":
        result = install_user_runtime(args.user_root)
    elif args.mode == "status":
        result = collect_install_status(args.workspace)
    elif args.mode == "doctor":
        result = collect_doctor_status(args.workspace)
    elif args.mode == "start":
        result = collect_start_status(args.workspace)
    else:
        raise ValueError(f"Unsupported install mode: {args.mode}")

    if args.mode == "start" and args.format == "summary":
        summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
        onboarding = result.get("onboarding", {}) if isinstance(result.get("onboarding"), dict) else {}
        quick_actions = summary.get("quick_actions", []) if isinstance(summary.get("quick_actions"), list) else []
        lines = [
            f"- 工作区: {result.get('workspace', '')}",
            f"- 范围: {summary.get('scope', '')}",
            f"- 新手入口就绪: {format_bool_zh(summary.get('ready'))}",
            f"- 入口文件: {onboarding.get('path', '')}",
            f"- 摘要: {summary.get('human_summary', '')}",
            f"- 快速动作: {format_list_zh(quick_actions)}",
        ]
        next_action = str(summary.get("recommended_next_action", "")).strip()
        next_actions = [next_action] if next_action else []
        print(render_summary_block("CodeCGC Start", lines, next_actions))
        return 0 if result.get("success") else 1

    if args.mode == "status" and args.format == "summary":
        summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
        project = result.get("project", {}) if isinstance(result.get("project"), dict) else {}
        user = result.get("user_preview_targets", {}) if isinstance(result.get("user_preview_targets"), dict) else {}
        lines = [
            f"- 工作区: {result.get('workspace', '')}",
            f"- 范围: {summary.get('scope', '')}",
            f"- 项目级就绪: {format_bool_zh(summary.get('project_ready'))}",
            f"- 用户级就绪: {format_bool_zh(summary.get('user_ready'))}",
            f"- 策略: {summary.get('default_policy', '')}",
            f"- 摘要: {summary.get('human_summary', '')}",
            f"- 项目级缺失项: {format_list_zh(project.get('missing_or_outdated', []))}",
            f"- 新手入口: {project.get('onboarding_file_path', '')}",
            f"- 用户级缺失项: {format_list_zh(user.get('missing_or_outdated', []))}",
        ]
        recommended_project = str(summary.get("recommended_project_command", "")).strip()
        recommended_user = str(summary.get("recommended_user_command", "")).strip()
        recommended_next = str(summary.get("recommended_next_command", "")).strip()
        next_actions = [item for item in [recommended_next, recommended_project, recommended_user] if item]
        print(render_summary_block("CodeCGC 安装状态", lines, next_actions))
        return 0 if result.get("success") else 1

    if args.mode == "doctor" and args.format == "summary":
        summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
        checks = result.get("checks", []) if isinstance(result.get("checks"), list) else []
        lines = [
            f"- 工作区: {result.get('workspace', '')}",
            f"- 范围: {summary.get('scope', '')}",
            f"- 就绪: {format_bool_zh(summary.get('ready'))}",
            f"- 摘要: {summary.get('human_summary', '')}",
        ]
        failed_checks = summary.get("failed_checks", [])
        lines.append(f"- 失败检查项: {format_list_zh(failed_checks)}")
        failure_categories = summary.get("failure_categories", [])
        for item in failure_categories:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- 失败分类 {item.get('code', '')}: {item.get('summary', '')} | {item.get('suggestion', '')}"
            )
        for item in checks:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- 检查 {item.get('name', '')}: {'通过' if item.get('ok') else '失败'} ({item.get('detail', '')})"
            )
        fix_command = str(summary.get("recommended_fix_command", "")).strip()
        runtime_fix_command = str(summary.get("recommended_runtime_fix_command", "")).strip()
        next_actions = [item for item in [runtime_fix_command, fix_command] if item]
        print(render_summary_block("CodeCGC 自检", lines, next_actions))
        return 0 if result.get("success") else 1

    if args.format == "summary" and args.mode in {"local", "user-dry-run", "user"}:
        print(build_install_mode_summary(result))
        return 0 if result.get("success") else 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
