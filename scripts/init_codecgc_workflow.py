import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

from codecgc_artifact_roots import flow_root
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_workflow_templates import build_feature_paths
from codecgc_workflow_templates import build_issue_paths
from codecgc_workflow_templates import render_feature_acceptance
from codecgc_workflow_templates import render_feature_checklist
from codecgc_workflow_templates import render_feature_design
from codecgc_workflow_templates import render_issue_analysis
from codecgc_workflow_templates import render_issue_fix
from codecgc_workflow_templates import render_issue_fix_note
from codecgc_workflow_templates import render_issue_report


def slugify(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    if not normalized:
        raise ValueError("工作流 slug 归一化后不能为空。")
    return normalized


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="初始化最小可用的 CodeCGC 功能开发或问题修复工作流产物。"
    )
    parser.add_argument(
        "--flow",
        required=True,
        choices=["feature", "issue"],
        help="要初始化的工作流类型。",
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="新工作流目录使用的稳定 slug。",
    )
    parser.add_argument(
        "--summary",
        required=True,
        help="面向人的一句话摘要。",
    )
    parser.add_argument(
        "--date",
        default=dt.date.today().isoformat(),
        help="目录日期前缀，格式为 YYYY-MM-DD。",
    )
    parser.add_argument(
        "--target-path",
        action="append",
        default=[],
        help="可选：首个可执行步骤的初始目标路径。",
    )
    parser.add_argument(
        "--kind",
        choices=["auto", "frontend", "backend"],
        default="auto",
        help="可选：首个可执行步骤的初始归属类型。",
    )
    parser.add_argument(
        "--artifact-class",
        choices=["product", "fixture"],
        default="product",
        help="指定生成产物属于 product 还是 fixture。",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="如果目标文件已存在，则允许覆盖。",
    )
    return parser


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_file(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"文件已存在：{path}")
    ensure_parent(path)
    path.write_text(content, encoding="utf-8")


def init_feature(
    flow_dir: Path,
    slug: str,
    summary: str,
    created_date: str,
    kind: str,
    target_paths: list[str],
    artifact_class: str,
    force: bool,
) -> dict[str, str]:
    paths = build_feature_paths(flow_dir, slug)
    write_file(
        paths["design"],
        render_feature_design(flow_dir.name, summary, kind, target_paths, artifact_class=artifact_class),
        force,
    )
    write_file(
        paths["checklist"],
        render_feature_checklist(flow_dir.name, slug, created_date, kind, target_paths, artifact_class=artifact_class),
        force,
    )
    write_file(paths["acceptance"], render_feature_acceptance(summary, artifact_class=artifact_class), force)
    return {name: str(path) for name, path in paths.items()}


def init_issue(
    flow_dir: Path,
    slug: str,
    summary: str,
    created_date: str,
    kind: str,
    target_paths: list[str],
    artifact_class: str,
    force: bool,
) -> dict[str, str]:
    paths = build_issue_paths(flow_dir, slug)
    write_file(
        paths["report"],
        render_issue_report(flow_dir.name, summary, kind, target_paths, artifact_class=artifact_class),
        force,
    )
    write_file(
        paths["analysis"],
        render_issue_analysis(flow_dir.name, summary, kind, target_paths, artifact_class=artifact_class),
        force,
    )
    write_file(
        paths["fix"],
        render_issue_fix(flow_dir.name, slug, created_date, kind, target_paths, artifact_class=artifact_class),
        force,
    )
    write_file(
        paths["fix_note"],
        render_issue_fix_note(flow_dir.name, summary, created_date, artifact_class=artifact_class),
        force,
    )
    return {name: str(path) for name, path in paths.items()}


def main() -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()

    try:
        slug = slugify(args.slug)
        directory_name = f"{args.date}-{slug}"
        root = flow_root(args.flow, args.artifact_class)
        flow_dir = root / directory_name

        if args.flow == "feature":
            created = init_feature(
                flow_dir,
                slug,
                args.summary.strip(),
                args.date,
                args.kind,
                args.target_path,
                args.artifact_class,
                args.force,
            )
        else:
            created = init_issue(
                flow_dir,
                slug,
                args.summary.strip(),
                args.date,
                args.kind,
                args.target_path,
                args.artifact_class,
                args.force,
            )
    except Exception as error:
        print_json(
            {
                "success": False,
                "error": str(error),
            },
            file=sys.stderr,
        )
        return 1

    print_json(
        {
            "success": True,
            "flow": args.flow,
            "directory": str(flow_dir),
            "files": created,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
