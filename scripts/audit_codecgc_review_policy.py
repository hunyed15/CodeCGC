import argparse
import json
from pathlib import Path
from typing import Any

from refresh_codecgc_review_policy import collect_refresh_candidates
from refresh_codecgc_review_policy import normalize_artifact_class


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="检查历史 CodeCGC 审核产物是否缺少已持久化的策略字段。"
    )
    parser.add_argument(
        "--artifact-class",
        choices=["product", "fixture", "all"],
        default="all",
        help="要扫描的产物类别根目录。默认同时检查 product 和 fixture。",
    )
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="json",
        help="输出格式。summary 更适合维护与发布检查。",
    )
    return parser


def build_result(scan_target: str) -> dict[str, Any]:
    normalized_target = normalize_artifact_class(scan_target) if scan_target != "all" else "all"
    candidates = collect_refresh_candidates(normalized_target)
    missing_items: list[dict[str, str]] = []
    for item in candidates:
        missing_items.append(
            {
                "artifact_class": str(item.get("artifact_class", "")),
                "artifact_type": str(item.get("artifact_type", "")),
                "artifact_path": str(item.get("artifact_path", "")),
                "audit_path": str(item.get("audit_path", "")),
                "decision": str(item.get("decision", "")),
            }
        )
    return {
        "success": len(missing_items) == 0,
        "scan_target": scan_target,
        "missing_count": len(missing_items),
        "missing": missing_items,
    }


def build_summary(result: dict[str, Any]) -> str:
    lines = [
        "CodeCGC 审核策略一致性检查",
        f"- 范围: {result.get('scan_target', '')}",
        f"- 缺失项数: {result.get('missing_count', 0)}",
        f"- 就绪: {'是' if result.get('success') else '否'}",
    ]
    for item in result.get("missing", []):
        if not isinstance(item, dict):
            continue
        lines.append(
            "- 缺失: "
            + f"{item.get('artifact_path', '')} "
            + f"[{item.get('artifact_class', '')}/{item.get('decision', '')}]"
        )
    return "\n".join(lines)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = build_result(args.artifact_class)

    if args.format == "summary":
        print(build_summary(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
