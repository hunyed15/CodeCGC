from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from codecgc_artifact_roots import FIXTURE_ROOT
from codecgc_artifact_roots import PRODUCT_ROOT
from codecgc_console_io import render_summary_block
from codecgc_path_contract import normalize_persisted_project_path
from codecgc_path_contract import resolve_project_path
from codecgc_runtime_paths import PROJECT_ROOT
from route_codecgc_workflow import attach_route_summary
from route_codecgc_workflow import route_feature
from route_codecgc_workflow import route_issue


WORKSPACE = PROJECT_ROOT


FLOW_CONFIG: dict[str, dict[str, str]] = {
    "feature": {
        "plural": "features",
        "summary_suffix": "-acceptance.md",
    },
    "issue": {
        "plural": "issues",
        "summary_suffix": "-fix-note.md",
    },
}


STATE_LABELS = {
    "needs-planning": "待规划",
    "awaiting-build": "待功能执行",
    "awaiting-fix": "待问题修复",
    "awaiting-review": "待审核",
    "closed": "已关闭",
    "step-selected": "已选步骤",
    "unknown": "未知",
}


def parse_iso_like_timestamp(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except Exception:
        return None


def extract_created_from_slug(slug: str) -> str:
    text = str(slug or "").strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return ""


def artifact_root(artifact_class: str) -> Path:
    return FIXTURE_ROOT if artifact_class == "fixture" else PRODUCT_ROOT


def collect_flow_directories(flow: str, include_fixtures: bool) -> list[tuple[str, Path]]:
    config = FLOW_CONFIG[flow]
    roots: list[tuple[str, Path]] = [("product", PRODUCT_ROOT / config["plural"])]
    if include_fixtures:
        roots.append(("fixture", FIXTURE_ROOT / config["plural"]))

    discovered: list[tuple[str, Path]] = []
    for artifact_class, root in roots:
        if not root.exists():
            continue
        for item in sorted(root.iterdir()):
            if item.is_dir():
                discovered.append((artifact_class, item))
    return discovered


def locate_summary_file(flow: str, directory: Path) -> str:
    suffix = FLOW_CONFIG[flow]["summary_suffix"]
    matches = sorted(directory.glob(f"*{suffix}"))
    if not matches:
        return ""
    return normalize_persisted_project_path(matches[0])


def collect_history_record(flow: str, artifact_class: str, directory: Path) -> dict[str, Any]:
    slug = directory.name
    raw_route = route_feature(slug) if flow == "feature" else route_issue(slug)
    route = attach_route_summary(raw_route)
    summary = route.get("summary", {}) if isinstance(route.get("summary"), dict) else {}
    workflow_state = str(summary.get("workflow_state", "")).strip() or "unknown"
    current_step = route.get("current_step", {}) if isinstance(route.get("current_step"), dict) else {}
    audit_path = str(route.get("audit_path", "")).strip()
    audit_timestamp = ""
    if audit_path:
        resolved_audit_path = resolve_project_path(audit_path)
        audit_time = parse_iso_like_timestamp(resolved_audit_path.stat().st_mtime_ns and datetime.fromtimestamp(resolved_audit_path.stat().st_mtime).isoformat())
        if audit_time:
            audit_timestamp = audit_time.isoformat()

    record: dict[str, Any] = {
        "flow": flow,
        "artifact_class": artifact_class,
        "slug": slug,
        "created": extract_created_from_slug(slug),
        "directory": normalize_persisted_project_path(directory),
        "workflow_state": workflow_state,
        "state_label": STATE_LABELS.get(workflow_state, workflow_state or "未知"),
        "recommended_command": str(route.get("recommended_command", "")).strip(),
        "human_summary": str(summary.get("human_summary", "")).strip() or str(route.get("reason", "")).strip(),
        "next": str(route.get("next", "")).strip(),
        "current_step_number": int(summary.get("current_step_number", 0) or 0),
        "current_task_id": str(summary.get("current_task_id", "")).strip(),
        "review_decision": str(summary.get("review_decision", "")).strip(),
        "is_closed": bool(summary.get("is_closed")),
        "audit_path": normalize_persisted_project_path(audit_path) if audit_path else "",
        "audit_timestamp": audit_timestamp,
        "summary_file": locate_summary_file(flow, directory),
        "root": normalize_persisted_project_path(artifact_root(artifact_class)),
    }
    if current_step:
        record["current_step"] = {
            "step_number": int(current_step.get("step_number", 0) or 0),
            "task_id": str(current_step.get("task_id", "")).strip(),
            "kind": str(current_step.get("kind", "")).strip(),
            "target_paths": current_step.get("target_paths", []),
            "task_summary": str(current_step.get("task_summary", "")).strip(),
        }
    return record


def build_sort_key(record: dict[str, Any]) -> tuple[datetime, str]:
    audit_dt = parse_iso_like_timestamp(str(record.get("audit_timestamp", "")).strip())
    if audit_dt is not None:
        return audit_dt, str(record.get("slug", ""))

    created_text = str(record.get("created", "")).strip()
    created_dt = parse_iso_like_timestamp(f"{created_text}T00:00:00") if created_text else None
    if created_dt is not None:
        return created_dt, str(record.get("slug", ""))

    directory = Path(str(record.get("directory", "")).strip())
    try:
        fallback = datetime.fromtimestamp(directory.stat().st_mtime)
    except Exception:
        fallback = datetime.fromtimestamp(0)
    return fallback, str(record.get("slug", ""))


def normalize_status_filter(value: str) -> str:
    text = str(value or "all").strip().lower()
    aliases = {
        "all": "all",
        "open": "open",
        "closed": "closed",
        "planning": "needs-planning",
        "needs-planning": "needs-planning",
        "build": "awaiting-build",
        "awaiting-build": "awaiting-build",
        "fix": "awaiting-fix",
        "awaiting-fix": "awaiting-fix",
        "review": "awaiting-review",
        "awaiting-review": "awaiting-review",
        "selected": "step-selected",
        "step-selected": "step-selected",
        "unknown": "unknown",
    }
    return aliases.get(text, text)


def status_matches(record: dict[str, Any], status_filter: str) -> bool:
    normalized = normalize_status_filter(status_filter)
    state = str(record.get("workflow_state", "")).strip()
    if normalized == "all":
        return True
    if normalized == "open":
        return not bool(record.get("is_closed"))
    if normalized == "closed":
        return bool(record.get("is_closed"))
    return state == normalized


def collect_history(flow: str, status_filter: str, last: int, include_fixtures: bool) -> dict[str, Any]:
    flows = ["feature", "issue"] if flow == "all" else [flow]
    records: list[dict[str, Any]] = []
    scanned = 0
    for current_flow in flows:
        for artifact_class, directory in collect_flow_directories(current_flow, include_fixtures):
            scanned += 1
            record = collect_history_record(current_flow, artifact_class, directory)
            if status_matches(record, status_filter):
                records.append(record)

    records.sort(key=build_sort_key, reverse=True)
    limited_records = records[:last] if last > 0 else records

    open_count = sum(1 for item in limited_records if not item.get("is_closed"))
    closed_count = sum(1 for item in limited_records if item.get("is_closed"))
    state_breakdown: dict[str, int] = {}
    for item in limited_records:
        state = str(item.get("workflow_state", "unknown")).strip() or "unknown"
        state_breakdown[state] = state_breakdown.get(state, 0) + 1

    flow_label = "全部工作流" if flow == "all" else flow
    summary_filter = normalize_status_filter(status_filter)
    human_summary = f"已汇总最近 {len(limited_records)} 条 {flow_label} 历史。"
    if summary_filter != "all":
        human_summary = f"已汇总最近 {len(limited_records)} 条 {flow_label} 历史，过滤条件为 {summary_filter}。"

    recommended_command = ""
    next_action = "继续使用 cgc-route / cgc-entry / cgc-plan 进入你要跟进的那条工作流。"
    if limited_records:
        first = limited_records[0]
        recommended_command = str(first.get("recommended_command", "")).strip()
        slug = str(first.get("slug", "")).strip()
        first_flow = str(first.get("flow", "")).strip()
        if recommended_command and slug and first_flow:
            if recommended_command == "cgc-route":
                next_action = f"如需继续最近一条工作流，先运行 cgc-route --flow {first_flow} --slug {slug}。"
            elif recommended_command in {"cgc-build", "cgc-fix"}:
                next_action = f"如需继续最近一条工作流，可直接运行 {recommended_command} --slug {slug}。"
            else:
                next_action = f"如需继续最近一条工作流，可先运行 {recommended_command} 并带上 slug {slug}。"

    return {
        "success": True,
        "mode": "workflow-history",
        "workspace": str(WORKSPACE),
        "filters": {
            "flow": flow,
            "status": summary_filter,
            "last": last,
            "include_fixtures": include_fixtures,
        },
        "summary": {
            "human_summary": human_summary,
            "recommended_command": recommended_command,
            "next_action": next_action,
            "matched_count": len(records),
            "returned_count": len(limited_records),
            "open_count": open_count,
            "closed_count": closed_count,
            "state_breakdown": state_breakdown,
        },
        "scanned_workflows": scanned,
        "records": limited_records,
    }


def build_summary(result: dict[str, Any]) -> str:
    summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
    filters = result.get("filters", {}) if isinstance(result.get("filters"), dict) else {}
    lines = [
        f"- 工作区: {result.get('workspace', '')}",
        f"- Flow 过滤: {filters.get('flow', '')}",
        f"- 状态过滤: {filters.get('status', '')}",
        f"- 返回条数: {summary.get('returned_count', 0)} / 匹配条数: {summary.get('matched_count', 0)}",
        f"- 已关闭: {summary.get('closed_count', 0)}",
        f"- 未关闭: {summary.get('open_count', 0)}",
        f"- 摘要: {summary.get('human_summary', '')}",
    ]
    breakdown = summary.get("state_breakdown", {}) if isinstance(summary.get("state_breakdown"), dict) else {}
    for state, count in breakdown.items():
        lines.append(f"- 状态分布: {state} = {count}")

    for item in result.get("records", []):
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug", "")).strip()
        flow = str(item.get("flow", "")).strip()
        artifact_class = str(item.get("artifact_class", "")).strip()
        state_label = str(item.get("state_label", "")).strip()
        command = str(item.get("recommended_command", "")).strip() or "无"
        created = str(item.get("created", "")).strip() or "unknown"
        lines.append(
            f"- 历史: [{flow}/{artifact_class}] {slug} | {state_label} | created={created} | next={command}"
        )

    next_action = str(summary.get("next_action", "")).strip()
    next_actions = [next_action] if next_action else []
    return render_summary_block("CodeCGC Workflow History", lines, next_actions)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only CodeCGC workflow history query across feature and issue artifacts."
    )
    parser.add_argument("--flow", choices=["all", "feature", "issue"], default="all")
    parser.add_argument("--status", default="all")
    parser.add_argument("--last", type=int, default=10)
    parser.add_argument("--include-fixtures", action="store_true")
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="summary",
        help="Output format. Summary is the default product-facing mode; use json for debugging or automation.",
    )
    args = parser.parse_args()

    result = collect_history(
        flow=args.flow,
        status_filter=args.status,
        last=max(args.last, 0),
        include_fixtures=args.include_fixtures,
    )
    if args.format == "summary":
        print(build_summary(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
