from __future__ import annotations

from pathlib import Path

import yaml


DEFAULT_FRONTEND_PATHS = [
    "apps/web/**",
    "src/components/**",
    "src/pages/**",
    "src/app/**",
    "src/styles/**",
    "web/**",
    "frontend/**",
]

DEFAULT_BACKEND_PATHS = [
    "apps/api/**",
    "server/**",
    "src/server/**",
    "src/services/**",
    "src/repositories/**",
    "backend/**",
]

DEFAULT_SHARED_PATHS = [
    "packages/shared/**",
    "src/shared/**",
    "src/lib/**",
    "src/types/**",
]

DEFAULT_ORCHESTRATION_PATHS = [
    "codecgc/**",
    ".claude/commands/**",
    ".claude/settings.json",
    ".mcp.json",
    "model-routing.yaml",
]

DEFAULT_DOCS_PATHS = [
    "README.md",
    "INSTALLATION.md",
    "docs/**",
    "CHANGELOG.md",
]

DEFAULT_BACKEND_TEST_PATHS = [
    "apps/api/*.test.*",
    "apps/api/*.spec.*",
    "apps/api/**/*.test.*",
    "apps/api/**/*.spec.*",
    "tests/backend/**",
]

DEFAULT_FRONTEND_TEST_PATHS = [
    "apps/web/*.test.*",
    "apps/web/*.spec.*",
    "apps/web/**/*.test.*",
    "apps/web/**/*.spec.*",
    "tests/frontend/**",
]

DEFAULT_RULES = {
    "claude_allowed_owners": ["orchestration", "docs"],
    "backend_executor": "codexmcp",
    "frontend_executor": "geminimcp",
    "shared_policy": "split-first",
}


def _render_list_block(name: str, items: list[str]) -> list[str]:
    lines = [f"{name}:"]
    for item in items:
        lines.append(f'  - "{item}"')
    return lines


def _render_nested_list_block(name: str, groups: dict[str, list[str]]) -> list[str]:
    lines = [f"{name}:"]
    for group_name, items in groups.items():
        lines.append(f"  {group_name}:")
        for item in items:
            lines.append(f'    - "{item}"')
    return lines


def _render_rules_block() -> list[str]:
    lines = ["rules:"]
    for key, value in DEFAULT_RULES.items():
        if isinstance(value, list):
            lines.append(f"  {key}:")
            lines.extend(f'    - "{item}"' for item in value)
        else:
            lines.append(f'  {key}: "{value}"')
    return lines


def render_default_routing_yaml() -> str:
    lines: list[str] = [
        "version: 2",
        "",
        *_render_list_block("orchestration_paths", DEFAULT_ORCHESTRATION_PATHS),
        "",
        *_render_list_block("docs_paths", DEFAULT_DOCS_PATHS),
        "",
        *_render_list_block("frontend_paths", DEFAULT_FRONTEND_PATHS),
        "",
        *_render_list_block("backend_paths", DEFAULT_BACKEND_PATHS),
        "",
        *_render_nested_list_block(
            "test_paths",
            {
                "frontend": DEFAULT_FRONTEND_TEST_PATHS,
                "backend": DEFAULT_BACKEND_TEST_PATHS,
            },
        ),
        "",
        *_render_list_block("shared_paths", DEFAULT_SHARED_PATHS),
        "",
        *_render_rules_block(),
        "",
    ]
    return "\n".join(lines)


def _normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _extract_list_block(lines: list[str], block_name: str) -> list[str]:
    items: list[str] = []
    inside = False
    for line in lines:
        stripped = line.strip()
        if not inside:
            if stripped == f"{block_name}:":
                inside = True
            continue

        if line and not line.startswith(" "):
            break
        if stripped.startswith("- "):
            value = stripped[2:].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            if value:
                items.append(value)
    return items


def merge_routing_template(existing_text: str) -> str:
    if existing_text.strip():
        try:
            data = yaml.safe_load(existing_text)
        except yaml.YAMLError:
            data = None
        if isinstance(data, dict) and int(data.get("version", 0) or 0) == 2:
            return _normalize_line_endings(existing_text).rstrip() + "\n"
    return render_default_routing_yaml()


def sync_workspace_routing_file(target_path: Path) -> Path:
    existing_text = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
    merged_text = merge_routing_template(existing_text)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(merged_text, encoding="utf-8")
    return target_path
