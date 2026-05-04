import argparse
import json
from pathlib import Path
from typing import Any

from codecgc_artifact_roots import execution_root
from codecgc_artifact_roots import flow_root
from codecgc_artifact_roots import normalize_artifact_class
from route_codecgc_workflow import extract_review_metadata
from write_codecgc_review import load_json
from write_codecgc_review import resolve_artifact_path
from write_codecgc_review import write_review


WORKSPACE = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="为历史 acceptance/fix-note 产物补写缺失的 CodeCGC 审核策略字段。"
    )
    parser.add_argument(
        "--artifact-class",
        choices=["product", "fixture", "all"],
        default="all",
        help="要扫描的产物类别根目录。默认同时处理 product 和 fixture。",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="将刷新结果真正写回文件。默认仅输出预演摘要。",
    )
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="json",
        help="输出格式。summary 更适合维护与发布检查。",
    )
    return parser


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def has_review_policy_fields(path: Path) -> bool:
    text = read_text(path)
    return (
        ("Review action kind:" in text or "审核动作类型:" in text)
        and ("Review fallback stage:" in text or "审核回退阶段:" in text)
        and ("Review policy reason:" in text or "审核策略原因:" in text)
    )


def has_legacy_review_text(path: Path) -> bool:
    text = read_text(path)
    legacy_markers = [
        "## 5. Review Decision",
        "## 4. Review Decision",
        "Requested decision:",
        "Final decision:",
        "Outcome:",
        "Evidence source:",
        "Risk classes:",
        "Execution mode:",
        "Execution performed:",
        "Reviewed task_id:",
        "Reviewed step_number:",
        "Review action kind:",
        "Review fallback stage:",
        "Review policy reason:",
        "Next step:",
        "- accepted",
        "- changes-requested",
    ]
    return any(marker in text for marker in legacy_markers)


def find_audit_candidates(artifact_class: str) -> list[Path]:
    root = execution_root(artifact_class)
    if not root.exists():
        return []
    return sorted(root.glob("*.json"))


def should_scan_artifact_class(value: str, artifact_class: str) -> bool:
    if value == "all":
        return True
    return value == artifact_class


def collect_refresh_candidates(scan_target: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for artifact_class in ("product", "fixture"):
        if not should_scan_artifact_class(scan_target, artifact_class):
            continue

        for audit_path in find_audit_candidates(artifact_class):
            try:
                audit = load_json(audit_path)
                artifact_type, artifact_path = resolve_artifact_path(audit)
            except Exception:
                continue

            if not artifact_path.exists():
                continue

            review = extract_review_metadata(artifact_path)
            decision = str(review.get("decision", "")).strip()
            if decision not in {"accepted", "changes-requested"}:
                continue
            if has_review_policy_fields(artifact_path) and not has_legacy_review_text(artifact_path):
                continue

            candidates.append(
                {
                    "artifact_class": artifact_class,
                    "artifact_type": artifact_type,
                    "artifact_path": artifact_path,
                    "audit_path": audit_path,
                    "decision": decision,
                    "review": review,
                }
            )
    return candidates


def refresh_candidates(candidates: list[dict[str, Any]], write: bool) -> dict[str, Any]:
    refreshed: list[dict[str, str]] = []
    failed: list[dict[str, str]] = []

    for item in candidates:
        artifact_path = item["artifact_path"]
        audit_path = item["audit_path"]
        decision = item["decision"]
        try:
            if write:
                write_review(
                    audit_path=audit_path,
                    decision=decision,
                    risks=[],
                    next_step="",
                    force=True,
                )
            audit = load_json(audit_path)
            artifact_type, resolved_artifact_path = resolve_artifact_path(audit)
            review = extract_review_metadata(artifact_path)
            refreshed.append(
                {
                    "artifact_class": str(item["artifact_class"]),
                    "artifact_type": artifact_type,
                    "artifact_path": str(resolved_artifact_path),
                    "audit_path": str(audit_path),
                    "decision": decision,
                    "review_action_kind": str(review.get("action_kind", "")),
                    "review_fallback_stage": str(review.get("fallback_stage", "")),
                    "review_policy_reason": str(review.get("policy_reason", "")),
                    "written": "yes" if write else "no",
                }
            )
        except Exception as error:
            failed.append(
                {
                    "artifact_path": str(artifact_path),
                    "audit_path": str(audit_path),
                    "error": str(error),
                }
            )

    return {
        "refreshed": refreshed,
        "failed": failed,
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    scan_target = normalize_artifact_class(args.artifact_class) if args.artifact_class != "all" else "all"
    candidates = collect_refresh_candidates(scan_target)
    result = refresh_candidates(candidates, write=args.write)

    output = {
        "success": True,
        "scan_target": args.artifact_class,
        "write": bool(args.write),
        "candidate_count": len(candidates),
        "refreshed_count": len(result["refreshed"]),
        "failed_count": len(result["failed"]),
        "refreshed": result["refreshed"],
        "failed": result["failed"],
    }
    if args.format == "summary":
        lines = [
            "CodeCGC Review Policy Refresh Audit",
            f"- 范围: {args.artifact_class}",
            f"- 写入模式: {'是' if args.write else '否'}",
            f"- 候选数: {len(candidates)}",
            f"- 刷新成功数: {len(result['refreshed'])}",
            f"- 失败数: {len(result['failed'])}",
        ]
        if result["refreshed"]:
            for item in result["refreshed"]:
                lines.append(
                    "- 已识别: "
                    + f"{item.get('artifact_path', '')} "
                    + f"[{item.get('decision', '')} / {item.get('review_action_kind', '')} / {item.get('review_fallback_stage', '')}]"
                )
        if result["failed"]:
            for item in result["failed"]:
                lines.append(
                    "- 失败: "
                    + f"{item.get('artifact_path', '')} ({item.get('error', '')})"
                )
        print("\n".join(lines))
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
