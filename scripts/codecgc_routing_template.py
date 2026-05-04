from __future__ import annotations

from pathlib import Path


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

DEFAULT_RULES = {
    "frontend_executor": "geminimcp",
    "backend_executor": "codexmcp",
    "shared_policy": "split-first",
    "claude_role": "plan-review-accept-only",
}


def _render_list_block(name: str, items: list[str]) -> list[str]:
    lines = [f"{name}:"]
    for item in items:
        lines.append(f'  - "{item}"')
    return lines


def _render_rules_block() -> list[str]:
    lines = ["rules:"]
    for key, value in DEFAULT_RULES.items():
        lines.append(f'  {key}: "{value}"')
    return lines


def render_default_routing_yaml() -> str:
    lines: list[str] = [
        "version: 1",
        "",
        *_render_list_block("frontend_paths", DEFAULT_FRONTEND_PATHS),
        "",
        *_render_list_block("custom_frontend_paths", []),
        "",
        *_render_list_block("backend_paths", DEFAULT_BACKEND_PATHS),
        "",
        *_render_list_block("custom_backend_paths", []),
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
    if not existing_text.strip():
        return render_default_routing_yaml()

    lines = _normalize_line_endings(existing_text).split("\n")
    custom_frontend = _extract_list_block(lines, "custom_frontend_paths")
    custom_backend = _extract_list_block(lines, "custom_backend_paths")

    merged = render_default_routing_yaml().split("\n")
    output: list[str] = []
    current_block = ""

    for line in merged:
        stripped = line.strip()
        output.append(line)
        if stripped == "custom_frontend_paths:":
            current_block = "custom_frontend_paths"
            for item in custom_frontend:
                output.append(f'  - "{item}"')
            continue
        if stripped == "custom_backend_paths:":
            current_block = "custom_backend_paths"
            for item in custom_backend:
                output.append(f'  - "{item}"')
            continue
        if stripped.endswith(":") and stripped not in {"custom_frontend_paths:", "custom_backend_paths:"}:
            current_block = stripped[:-1]

    return "\n".join(output).rstrip() + "\n"


def sync_workspace_routing_file(target_path: Path) -> Path:
    existing_text = target_path.read_text(encoding="utf-8") if target_path.exists() else ""
    merged_text = merge_routing_template(existing_text)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(merged_text, encoding="utf-8")
    return target_path
