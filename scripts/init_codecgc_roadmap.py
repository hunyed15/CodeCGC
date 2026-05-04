import argparse
import json
import re
import sys
from pathlib import Path

from codecgc_roadmap_templates import render_delivery_plan
from codecgc_roadmap_templates import render_overview
from codecgc_roadmap_templates import render_phases


WORKSPACE = Path(__file__).resolve().parents[1]
ROADMAP_ROOT = WORKSPACE / "codecgc" / "roadmap"


def slugify(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    if not normalized:
        raise ValueError("Roadmap slug cannot be empty after normalization.")
    return normalized


def write_file(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"File already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Initialize a CodeCGC roadmap scaffold.")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--artifact-class", choices=["product", "fixture"], default="product")
    parser.add_argument("--goal", default="")
    parser.add_argument("--user-story", default="")
    parser.add_argument("--context", action="append", default=[])
    parser.add_argument("--in-scope", action="append", default=[])
    parser.add_argument("--risk", action="append", default=[])
    parser.add_argument("--dependency", action="append", default=[])
    parser.add_argument("--assumption", action="append", default=[])
    parser.add_argument("--validation", action="append", default=[])
    parser.add_argument("--rollback", action="append", default=[])
    parser.add_argument("--open-question", action="append", default=[])
    parser.add_argument("--reason", action="append", default=[])
    parser.add_argument("--frontend-path", action="append", default=[])
    parser.add_argument("--backend-path", action="append", default=[])
    parser.add_argument("--shared-path", action="append", default=[])
    parser.add_argument("--unknown-path", action="append", default=[])
    parser.add_argument("--force", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        slug = slugify(args.slug)
        directory = ROADMAP_ROOT / slug
        grouped_paths = {
            "frontend": args.frontend_path,
            "backend": args.backend_path,
            "shared": args.shared_path,
            "unknown": args.unknown_path,
        }

        overview_path = directory / "overview.md"
        phases_path = directory / "phases.md"
        delivery_plan_path = directory / "delivery-plan.md"

        write_file(
            overview_path,
            render_overview(
                initiative=slug,
                summary=args.summary,
                user_story=args.user_story,
                goal=args.goal,
                context=args.context,
                scope=args.in_scope,
                risks=args.risk,
                reasons=args.reason,
                artifact_class=args.artifact_class,
            ),
            args.force,
        )
        write_file(
            phases_path,
            render_phases(
                initiative=slug,
                grouped_paths=grouped_paths,
                artifact_class=args.artifact_class,
            ),
            args.force,
        )
        write_file(
            delivery_plan_path,
            render_delivery_plan(
                initiative=slug,
                dependencies=args.dependency,
                assumptions=args.assumption,
                validation=args.validation,
                rollback=args.rollback,
                open_questions=args.open_question,
                artifact_class=args.artifact_class,
            ),
            args.force,
        )
    except Exception as error:
        print(json.dumps({"success": False, "error": str(error)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "success": True,
                "directory": str(directory),
                "files": {
                    "overview": str(overview_path),
                    "phases": str(phases_path),
                    "delivery_plan": str(delivery_plan_path),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
