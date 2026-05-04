import argparse
import re
from pathlib import Path

from codecgc_artifact_roots import artifact_output_root
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_workflow_runtime import run_json_script


def normalize_slug(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "roadmap-item"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="根据治理请求在 codecgc/roadmap/ 下初始化长期 roadmap 产物。"
    )
    parser.add_argument("--summary", required=True, help="一行 roadmap 摘要。")
    parser.add_argument("--goal", default="", help="可选的 roadmap 目标。")
    parser.add_argument("--source", default="", help="可选的来源产物、工作流或讨论引用。")
    parser.add_argument("--force", action="store_true")
    return parser


def resolve_roadmap_directory(slug: str) -> Path:
    return artifact_output_root("product") / "roadmap" / slug


def append_source_note(path: Path, source: str) -> None:
    if not source.strip() or not path.exists():
        return
    content = path.read_text(encoding="utf-8")
    note = f"\n## 7. 治理来源\n\n- 来源: {source.strip()}\n"
    if "## 7. Governance Source" in content or "## 7. 治理来源" in content or f"- Source: {source.strip()}" in content or f"- 来源: {source.strip()}" in content:
        return
    path.write_text(content.rstrip() + note, encoding="utf-8")


def init_roadmap(summary: str, goal: str, source: str, force: bool) -> dict[str, object]:
    slug = normalize_slug(summary)
    roadmap_dir = resolve_roadmap_directory(slug)
    result = run_json_script(
        "init_codecgc_roadmap.py",
        "--slug",
        slug,
        "--summary",
        summary.strip(),
        "--goal",
        goal.strip() or summary.strip(),
        *([] if not force else ["--force"]),
    )
    if not result.get("success") and roadmap_dir.exists() and not force:
        overview_path = roadmap_dir / "overview.md"
        append_source_note(overview_path, source)
        return {
            "success": True,
            "roadmap": {
                "slug": slug,
                "directory": str(roadmap_dir),
                "files": {
                    "overview": str(roadmap_dir / "overview.md"),
                    "phases": str(roadmap_dir / "phases.md"),
                    "delivery_plan": str(roadmap_dir / "delivery-plan.md"),
                },
                "source": source.strip(),
                "created": "false",
            },
        }
    if not result.get("success"):
        return result

    files = result.get("files", {}) if isinstance(result.get("files"), dict) else {}
    overview_path = Path(str(files.get("overview", ""))) if files.get("overview") else roadmap_dir / "overview.md"
    append_source_note(overview_path, source)
    return {
        "success": True,
        "roadmap": {
            "slug": slug,
            "directory": result.get("directory", str(roadmap_dir)),
            "files": files,
            "source": source.strip(),
            "created": "true",
        },
    }


def main() -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args()
    slug = normalize_slug(args.summary)
    roadmap_dir = resolve_roadmap_directory(slug)
    if roadmap_dir.exists() and not args.force:
        append_source_note(roadmap_dir / "overview.md", args.source)
        print_json(
            {
                "success": True,
                "roadmap": {
                    "slug": slug,
                    "directory": str(roadmap_dir),
                    "files": {
                        "overview": str(roadmap_dir / "overview.md"),
                        "phases": str(roadmap_dir / "phases.md"),
                        "delivery_plan": str(roadmap_dir / "delivery-plan.md"),
                    },
                    "source": args.source.strip(),
                    "created": "false",
                },
            }
        )
        return 0

    result = init_roadmap(args.summary, args.goal, args.source, args.force)
    print_json(result)
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
