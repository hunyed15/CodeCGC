import argparse
import json
from pathlib import Path
from typing import Any

from codecgc_console_io import render_summary_block
from codecgc_executor_registry import build_executor_registry
from codecgc_runtime_paths import resolve_workspace_root

WORKSPACE = Path(__file__).resolve().parents[1]
REGISTRY_PATH = WORKSPACE / "codecgc" / "reference" / "external-capability-registry.json"
STATUS_PANEL_CAPABILITY_ORDER = [
    "memos",
    "github-mcp",
    "linear-mcp",
    "sentry-mcp",
]
STATUS_PANEL_SUPPORT_CAPABILITY_ORDER = [
    "augment-search",
    "jira-mcp",
]


def load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def load_workspace_mcp_servers(workspace_override: str = "") -> tuple[dict[str, Any], Path]:
    workspace_root = resolve_workspace_root(workspace_override)
    mcp_path = workspace_root / ".mcp.json"
    if not mcp_path.exists():
        return {}, workspace_root
    try:
        payload = json.loads(mcp_path.read_text(encoding="utf-8"))
    except Exception:
        return {}, workspace_root
    servers = payload.get("mcpServers", {})
    return servers if isinstance(servers, dict) else {}, workspace_root


def probe_executor_capability(entry: dict[str, Any]) -> dict[str, Any]:
    target = str(entry.get("executor_target", "")).strip()
    server_names = [str(item).strip() for item in entry.get("mcp_server_names", []) if str(item).strip()]
    registry = build_executor_registry()
    config = registry.get(target, {})
    python_module = Path(str(config.get("pythonpath", ""))) / Path(str(config.get("python_module", "")).replace(".", "/")).with_suffix(".py")
    server_name = str(config.get("mcp_server_name", "")).strip()
    path_ready = python_module.exists()
    server_ready = server_name in server_names if server_name else False
    return {
        "local_ready": bool(config) and path_ready and server_ready,
        "observed_servers": [server_name] if server_name else [],
        "details": {
            "executor_target": target,
            "python_module_path": str(python_module),
            "path_ready": path_ready,
            "server_ready": server_ready,
        },
    }


def probe_workspace_mcp_capability(entry: dict[str, Any], workspace_servers: dict[str, Any]) -> dict[str, Any]:
    server_names = [str(item).strip() for item in entry.get("mcp_server_names", []) if str(item).strip()]
    observed = [name for name in server_names if name in workspace_servers]
    return {
        "local_ready": bool(observed),
        "observed_servers": observed,
        "details": {
            "declared_servers": server_names,
            "observed_servers": observed,
        },
    }


def normalize_capability_entry(entry: dict[str, Any], workspace_servers: dict[str, Any]) -> dict[str, Any]:
    capability_id = str(entry.get("id", "")).strip()
    name = str(entry.get("name", capability_id)).strip()
    status = str(entry.get("status", "")).strip()
    category = str(entry.get("category", "")).strip()
    integration_type = str(entry.get("integration_type", "")).strip()
    required = bool(entry.get("required", False))
    probe_kind = str(entry.get("probe_kind", "")).strip()

    if probe_kind == "executor":
        probe = probe_executor_capability(entry)
    else:
        probe = probe_workspace_mcp_capability(entry, workspace_servers)

    policy_ready = all(
        [
            capability_id,
            name,
            status,
            category,
            integration_type,
        ]
    )
    blocking = required and status == "integrated" and not probe["local_ready"]
    drift = status != "integrated" and bool(probe["observed_servers"])

    return {
        "id": capability_id,
        "name": name,
        "status": status,
        "category": category,
        "integration_type": integration_type,
        "required": required,
        "owner": str(entry.get("owner", "")).strip(),
        "description": str(entry.get("description", "")).strip(),
        "mcp_server_names": [str(item).strip() for item in entry.get("mcp_server_names", []) if str(item).strip()],
        "local_ready": probe["local_ready"],
        "observed_servers": probe["observed_servers"],
        "policy_ready": policy_ready,
        "blocking": blocking,
        "drift": drift,
        "details": probe["details"],
    }


def audit_external_capabilities(workspace_override: str = "", view: str = "audit") -> dict[str, Any]:
    registry = load_registry()
    workspace_servers, workspace_root = load_workspace_mcp_servers(workspace_override)
    entries = registry.get("capabilities", [])
    normalized: list[dict[str, Any]] = []
    malformed_count = 0
    blocking_items: list[dict[str, Any]] = []
    drift_items: list[dict[str, Any]] = []

    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            malformed_count += 1
            continue
        item = normalize_capability_entry(raw_entry, workspace_servers)
        normalized.append(item)
        if not item["policy_ready"]:
            malformed_count += 1
        if item["blocking"]:
            blocking_items.append(item)
        if item["drift"]:
            drift_items.append(item)

    counts = {
        "integrated": sum(1 for item in normalized if item["status"] == "integrated"),
        "planned": sum(1 for item in normalized if item["status"] == "planned"),
        "optional": sum(1 for item in normalized if item["status"] == "optional"),
    }
    ready = malformed_count == 0 and not blocking_items
    human_summary = "外部能力接入清单已就绪。"
    if blocking_items:
        human_summary = "必需外部能力存在未接通或未观测到的阻塞项。"
    elif malformed_count > 0:
        human_summary = "外部能力登记表存在缺失字段或非法项。"
    elif drift_items:
        human_summary = "外部能力登记表已就绪，但发现本地额外接入漂移。"
    elif view == "status":
        human_summary = "外部能力状态面板已就绪。"

    recommended_next_action = ""
    if blocking_items:
        blocking_ids = {str(item["id"]) for item in blocking_items}
        if "codexmcp" in blocking_ids or "geminimcp" in blocking_ids:
            recommended_next_action = "先运行 cgc-install 或 cgc-doctor，修复必需执行器的项目级集成与运行前置。"
        else:
            recommended_next_action = "先补齐缺失的必需外部能力注册，再继续后续流程。"
    elif malformed_count > 0:
        recommended_next_action = "先修复 codecgc/reference/external-capability-registry.json 中缺失字段或非法项。"
    elif drift_items:
        recommended_next_action = "检查本地 .mcp.json 是否引入了登记表之外的额外接入，并决定是登记还是移除。"

    return {
        "success": ready,
        "mode": "external-capability-audit",
        "presentation_view": view,
        "workspace": str(workspace_root),
        "registry_path": str(REGISTRY_PATH),
        "summary": {
            "ready": ready,
            "scope": "外部能力白名单、接入状态声明与本地 MCP 观测状态",
            "human_summary": human_summary,
            "view": view,
            "capability_count": len(normalized),
            "integrated_count": counts["integrated"],
            "planned_count": counts["planned"],
            "optional_count": counts["optional"],
            "malformed_count": malformed_count,
            "blocking_count": len(blocking_items),
            "drift_count": len(drift_items),
            "recommended_next_action": recommended_next_action,
        },
        "capabilities": normalized,
        "workspace_mcp_servers": sorted(str(name) for name in workspace_servers.keys()),
    }


def _capability_by_id(result: dict[str, Any], capability_id: str) -> dict[str, Any] | None:
    for item in result.get("capabilities", []):
        if not isinstance(item, dict):
            continue
        if str(item.get("id", "")).strip() == capability_id:
            return item
    return None


def _format_capability_panel_line(item: dict[str, Any]) -> str:
    status = str(item.get("status", "")).strip()
    status_label = {
        "integrated": "已纳管",
        "planned": "规划中",
        "optional": "可选",
    }.get(status, status or "未知")
    local_label = "已观测" if item.get("local_ready") else "未观测"
    observed = ", ".join(str(value).strip() for value in item.get("observed_servers", []) if str(value).strip()) or "无"
    return (
        f"- {item.get('name', '')} [{item.get('id', '')}]: "
        f"{status_label} | 本地={local_label} | 服务器={observed}"
    )


def build_audit_summary(result: dict[str, Any]) -> str:
    summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
    lines = [
        f"- 工作区: {result.get('workspace', '')}",
        f"- 登记表: {result.get('registry_path', '')}",
        f"- 范围: {summary.get('scope', '')}",
        f"- 就绪: {'是' if summary.get('ready') else '否'}",
        f"- 摘要: {summary.get('human_summary', '')}",
        f"- 能力总数: {summary.get('capability_count', 0)}",
        f"- 已集成: {summary.get('integrated_count', 0)}",
        f"- 规划中: {summary.get('planned_count', 0)}",
        f"- 可选项: {summary.get('optional_count', 0)}",
        f"- 阻塞项: {summary.get('blocking_count', 0)}",
        f"- 漂移项: {summary.get('drift_count', 0)}",
    ]
    for item in result.get("capabilities", []):
        if not isinstance(item, dict):
            continue
        optional_text = "可选" if not item.get("required") else "必需"
        lines.append(
            "- 能力: "
            + f"{item.get('id', '')} "
            + f"[{item.get('status', '')}/{item.get('category', '')}/{optional_text}] "
            + f"本地={'已观测' if item.get('local_ready') else '未观测'} "
            + f"服务器={', '.join(item.get('observed_servers', [])) or '无'}"
        )
    next_action = str(summary.get("recommended_next_action", "")).strip()
    next_actions = [next_action] if next_action else []
    memos_item = next(
        (
            item
            for item in result.get("capabilities", [])
            if isinstance(item, dict) and str(item.get("id", "")).strip() == "memos"
        ),
        None,
    )
    if isinstance(memos_item, dict) and not memos_item.get("local_ready"):
        next_actions.append("如需跨会话记忆，可先在 Claude 中配置官方 memos-mcp，再重新执行 cgc-external-audit")
    augment_item = next(
        (
            item
            for item in result.get("capabilities", [])
            if isinstance(item, dict) and str(item.get("id", "")).strip() == "augment-search"
        ),
        None,
    )
    if isinstance(augment_item, dict) and not augment_item.get("local_ready"):
        next_actions.append("如需代码检索增强，可先在 Claude 中配置 ace-tool MCP，再重新执行 cgc-external-audit")
    github_item = next(
        (
            item
            for item in result.get("capabilities", [])
            if isinstance(item, dict) and str(item.get("id", "")).strip() == "github-mcp"
        ),
        None,
    )
    if isinstance(github_item, dict) and not github_item.get("local_ready"):
        next_actions.append("如需 GitHub 仓库、PR 与 issue 协作，可先在 Claude 中配置官方 github MCP，再重新执行 cgc-external-audit")
    linear_item = next(
        (
            item
            for item in result.get("capabilities", [])
            if isinstance(item, dict) and str(item.get("id", "")).strip() == "linear-mcp"
        ),
        None,
    )
    if isinstance(linear_item, dict) and not linear_item.get("local_ready"):
        next_actions.append("如需任务与项目节奏协作，可先在 Claude 中配置官方 Linear MCP，再重新执行 cgc-external-audit")
    return render_summary_block("CodeCGC 外部能力审计", lines, next_actions)


def build_status_panel(result: dict[str, Any]) -> str:
    summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
    lines = [
        f"- 工作区: {result.get('workspace', '')}",
        f"- 登记表: {result.get('registry_path', '')}",
        f"- 范围: {summary.get('scope', '')}",
        f"- 摘要: {summary.get('human_summary', '')}",
        f"- 就绪: {'是' if summary.get('ready') else '否'}",
        f"- 正式接入: {summary.get('integrated_count', 0)}",
        f"- 规划中: {summary.get('planned_count', 0)}",
        f"- 可选项: {summary.get('optional_count', 0)}",
        f"- 阻塞项: {summary.get('blocking_count', 0)}",
        f"- 漂移项: {summary.get('drift_count', 0)}",
        "- 正式能力面板:",
    ]
    for capability_id in STATUS_PANEL_CAPABILITY_ORDER:
        item = _capability_by_id(result, capability_id)
        if isinstance(item, dict):
            lines.append(_format_capability_panel_line(item))
    lines.append("- 其他受管能力:")
    for capability_id in STATUS_PANEL_SUPPORT_CAPABILITY_ORDER:
        item = _capability_by_id(result, capability_id)
        if isinstance(item, dict):
            lines.append(_format_capability_panel_line(item))
    next_actions = []
    next_action = str(summary.get("recommended_next_action", "")).strip()
    if next_action:
        next_actions.append(next_action)
    next_actions.append("需要更细的登记一致性检查时，再跑 cgc-external-audit")
    return render_summary_block("CodeCGC 外部能力状态面板", lines, next_actions)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit CodeCGC external capability registry and local MCP observations.")
    parser.add_argument(
        "--view",
        choices=["audit", "status"],
        default="audit",
        help="Rendered summary view. Audit is detailed; status is the concise panel view.",
    )
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="summary",
        help="Output format. Summary is the default product-facing mode; use json for debugging or automation.",
    )
    parser.add_argument(
        "--workspace",
        default="",
        help="Optional target workspace root. Defaults to the current shell workspace.",
    )
    args = parser.parse_args()

    result = audit_external_capabilities(args.workspace, view=args.view)
    if args.format == "summary":
        if args.view == "status":
            print(build_status_panel(result))
        else:
            print(build_audit_summary(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
