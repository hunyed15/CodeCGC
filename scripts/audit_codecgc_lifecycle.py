import argparse
import json
import re
from pathlib import Path
from typing import Any

from codecgc_artifact_roots import FIXTURE_ROOT
from codecgc_artifact_roots import PRODUCT_ROOT
from codecgc_console_io import render_summary_block

WORKSPACE = Path(__file__).resolve().parents[1]


def count_dirs(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.iterdir() if item.is_dir())


def count_files(path: Path, pattern: str) -> int:
    if not path.exists():
        return 0
    return sum(1 for _ in path.rglob(pattern))


def collect_root_stats(root: Path) -> dict[str, int]:
    return {
        "features": count_dirs(root / "features"),
        "issues": count_dirs(root / "issues"),
        "execution_audits": count_files(root / "execution", "*.json"),
        "roadmaps": count_dirs(root / "roadmap"),
        "requirements": count_files(root / "requirements", "*.md"),
        "architecture": count_files(root / "architecture", "*.md"),
    }


def count_child_workflow_lines(path: Path) -> int:
    if not path.exists():
        return 0
    content = path.read_text(encoding="utf-8")
    patterns = [
        r"(?m)^- (?:Frontend|Backend) 子工作流:",
        r"(?m)^- (?:Frontend|Backend) child:",
    ]
    total = 0
    for pattern in patterns:
        total += len(re.findall(pattern, content))
    return total


def collect_roadmap_tracking(root: Path) -> dict[str, Any]:
    roadmap_root = root / "roadmap"
    roadmaps: list[dict[str, Any]] = []
    if not roadmap_root.exists():
        return {
            "roadmap_count": 0,
            "tracked_roadmap_count": 0,
            "child_workflow_count": 0,
            "unexpanded_roadmaps": [],
            "roadmaps": [],
            "child_tracking_ready": True,
            "roadmap_coverage": "empty",
        }

    for item in sorted(path for path in roadmap_root.iterdir() if path.is_dir()):
        phases = item / "phases.md"
        delivery = item / "delivery-plan.md"
        child_count = count_child_workflow_lines(phases) + count_child_workflow_lines(delivery)
        tracked = child_count > 0
        roadmaps.append(
            {
                "initiative": item.name,
                "tracked": tracked,
                "child_workflow_count": child_count,
                "phases_exists": phases.exists(),
                "delivery_plan_exists": delivery.exists(),
            }
        )

    roadmap_count = len(roadmaps)
    tracked_roadmap_count = sum(1 for item in roadmaps if item["tracked"])
    child_workflow_count = sum(int(item["child_workflow_count"]) for item in roadmaps)
    unexpanded_roadmaps = [item["initiative"] for item in roadmaps if not item["tracked"]]
    child_tracking_ready = roadmap_count == 0 or tracked_roadmap_count == roadmap_count
    if roadmap_count == 0:
        roadmap_coverage = "empty"
    elif child_tracking_ready:
        roadmap_coverage = "tracked"
    elif tracked_roadmap_count == 0:
        roadmap_coverage = "unexpanded"
    else:
        roadmap_coverage = "partial"

    return {
        "roadmap_count": roadmap_count,
        "tracked_roadmap_count": tracked_roadmap_count,
        "child_workflow_count": child_workflow_count,
        "unexpanded_roadmaps": unexpanded_roadmaps,
        "roadmaps": roadmaps,
        "child_tracking_ready": child_tracking_ready,
        "roadmap_coverage": roadmap_coverage,
    }


def classify_maturity(product_stats: dict[str, int]) -> dict[str, str]:
    feature_count = int(product_stats.get("features", 0))
    issue_count = int(product_stats.get("issues", 0))
    roadmap_count = int(product_stats.get("roadmaps", 0))
    execution_count = int(product_stats.get("execution_audits", 0))

    if roadmap_count > 0 and feature_count == 0 and issue_count == 0:
        return {
            "stage": "initiative-planning",
            "human_summary": "当前仓库已经进入 roadmap 规划期，但还没有明显进入批量执行阶段。",
            "next_action": "优先检查 roadmap 子项是否已拆成具体 feature 或 issue workflow。",
        }
    if feature_count + issue_count == 0:
        return {
            "stage": "setup-only",
            "human_summary": "当前仓库已具备 CodeCGC 产品壳，但还没有明显的业务工作流沉淀。",
            "next_action": "优先从 cgc 开始一个新需求，或先用 cgc-plan 建立第一条 workflow。",
        }
    if execution_count == 0:
        return {
            "stage": "planned-not-executed",
            "human_summary": "当前仓库已有 feature / issue 规划，但执行审计还不多，主要处于规划后待执行阶段。",
            "next_action": "优先检查最近 workflow 是否已经进入 cgc-build / cgc-fix。",
        }
    return {
        "stage": "active-delivery",
        "human_summary": "当前仓库已经进入活跃交付阶段，roadmap、workflow 与 execution 审计都已有沉淀。",
        "next_action": "优先结合 cgc-route 与 cgc-release-readiness 判断当前是继续交付、收尾审核还是进入维护周期。",
    }


def audit_lifecycle() -> dict[str, Any]:
    product_stats = collect_root_stats(PRODUCT_ROOT)
    fixture_stats = collect_root_stats(FIXTURE_ROOT)
    product_roadmap_tracking = collect_roadmap_tracking(PRODUCT_ROOT)
    fixture_roadmap_tracking = collect_roadmap_tracking(FIXTURE_ROOT)
    maturity = classify_maturity(product_stats)
    lifecycle_assets = [
        "codecgc/reference/lifecycle-map.md",
        "codecgc/reference/lifecycle-playbook.md",
        "codecgc/reference/release-maintenance-playbook.md",
        "codecgc/compound/codecgc-operating-model.md",
        "codecgc/compound/codecgc-capability-matrix.md",
        "codecgc/roadmap/README.md",
    ]
    missing_assets = [item for item in lifecycle_assets if not (WORKSPACE / item).exists()]

    ready = len(missing_assets) == 0
    human_summary = maturity["human_summary"]
    if not ready:
        human_summary = "生命周期资产还不完整，当前还不适合把 lifecycle 作为稳定操作面。"

    recommended_next_action = maturity["next_action"]
    if missing_assets:
        recommended_next_action = "先补齐生命周期参考资产，再继续使用 lifecycle 总览作为稳定入口。"
    elif product_roadmap_tracking["roadmap_count"] > 0 and not product_roadmap_tracking["child_tracking_ready"]:
        recommended_next_action = "优先把还未扩成 child workflow 的 roadmap initiative 继续拆解，再进入批量执行。"

    return {
        "success": ready,
        "mode": "lifecycle-audit",
        "workspace": str(WORKSPACE),
        "summary": {
            "ready": ready,
            "scope": "roadmap / feature / issue / execution 的生命周期总览",
            "human_summary": human_summary,
            "stage": maturity["stage"],
            "recommended_next_action": recommended_next_action,
            "roadmap_coverage": product_roadmap_tracking["roadmap_coverage"],
            "child_tracking_ready": product_roadmap_tracking["child_tracking_ready"],
        },
        "product_stats": product_stats,
        "fixture_stats": fixture_stats,
        "product_roadmap_tracking": product_roadmap_tracking,
        "fixture_roadmap_tracking": fixture_roadmap_tracking,
        "missing_assets": missing_assets,
    }


def build_summary(result: dict[str, Any]) -> str:
    summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
    product_stats = result.get("product_stats", {}) if isinstance(result.get("product_stats"), dict) else {}
    fixture_stats = result.get("fixture_stats", {}) if isinstance(result.get("fixture_stats"), dict) else {}
    product_roadmap_tracking = result.get("product_roadmap_tracking", {}) if isinstance(result.get("product_roadmap_tracking"), dict) else {}
    fixture_roadmap_tracking = result.get("fixture_roadmap_tracking", {}) if isinstance(result.get("fixture_roadmap_tracking"), dict) else {}
    lines = [
        f"- 工作区: {result.get('workspace', '')}",
        f"- 范围: {summary.get('scope', '')}",
        f"- 就绪: {'是' if summary.get('ready') else '否'}",
        f"- 生命周期阶段: {summary.get('stage', '')}",
        f"- 摘要: {summary.get('human_summary', '')}",
        f"- Product features: {product_stats.get('features', 0)}",
        f"- Product issues: {product_stats.get('issues', 0)}",
        f"- Product audits: {product_stats.get('execution_audits', 0)}",
        f"- Product roadmaps: {product_stats.get('roadmaps', 0)}",
        f"- Product roadmap coverage: {summary.get('roadmap_coverage', '')}",
        f"- Product child tracking ready: {'是' if summary.get('child_tracking_ready') else '否'}",
        f"- Product tracked roadmaps: {product_roadmap_tracking.get('tracked_roadmap_count', 0)}",
        f"- Product child workflows: {product_roadmap_tracking.get('child_workflow_count', 0)}",
        f"- Fixture features: {fixture_stats.get('features', 0)}",
        f"- Fixture issues: {fixture_stats.get('issues', 0)}",
        f"- Fixture audits: {fixture_stats.get('execution_audits', 0)}",
        f"- Fixture roadmaps: {fixture_stats.get('roadmaps', 0)}",
        f"- Fixture tracked roadmaps: {fixture_roadmap_tracking.get('tracked_roadmap_count', 0)}",
        f"- Fixture child workflows: {fixture_roadmap_tracking.get('child_workflow_count', 0)}",
    ]
    for item in product_roadmap_tracking.get("unexpanded_roadmaps", []):
        lines.append(f"- 未扩出的 product roadmap: {item}")
    for item in fixture_roadmap_tracking.get("unexpanded_roadmaps", []):
        lines.append(f"- 未扩出的 fixture roadmap: {item}")
    for item in result.get("missing_assets", []):
        lines.append(f"- 缺少生命周期资产: {item}")
    next_action = str(summary.get("recommended_next_action", "")).strip()
    next_actions = [next_action] if next_action else []
    return render_summary_block("CodeCGC Lifecycle", lines, next_actions)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit CodeCGC lifecycle coverage across roadmap, workflows, and execution artifacts.")
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="summary",
        help="Output format. Summary is the default product-facing mode; use json for debugging or automation.",
    )
    args = parser.parse_args()

    result = audit_lifecycle()
    if args.format == "summary":
        print(build_summary(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
