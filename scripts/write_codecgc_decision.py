import argparse
from pathlib import Path

from codecgc_artifact_roots import artifact_output_root
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_governance_dedupe import has_existing_governance_entry


def resolve_decision_path() -> Path:
    return artifact_output_root("product") / "compound" / "codecgc-decisions.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把一条长期有效的已确认决定写入 codecgc/compound/codecgc-decisions.md。"
    )
    parser.add_argument("--summary", required=True, help="一行决定摘要。")
    parser.add_argument("--constraint", default="", help="这条决定会约束哪些后续行为。")
    parser.add_argument("--source", default="", help="可选的来源产物、工作流或讨论引用。")
    return parser


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def ensure_document(path: Path) -> None:
    if path.exists():
        return
    ensure_parent(path)
    path.write_text(
        "# CodeCGC 长期决策\n\n"
        "该文件用于记录当前仓库的长期有效决定。\n\n"
        "## 条目\n\n",
        encoding="utf-8",
    )


def has_existing_entry(existing: str, summary: str) -> bool:
    return has_existing_governance_entry(existing, summary, field_labels=["Decision", "决定"])


def append_decision(path: Path, summary: str, constraint: str, source: str) -> dict[str, str]:
    ensure_document(path)
    cleaned_summary = summary.strip()
    existing = path.read_text(encoding="utf-8")
    if has_existing_entry(existing, cleaned_summary):
        return {
            "path": str(path),
            "summary": cleaned_summary,
            "constraint": constraint.strip(),
            "source": source.strip(),
            "created": "false",
        }

    lines = [f"### {cleaned_summary}", "", f"- 决定: {cleaned_summary}"]
    if constraint.strip():
        lines.append(f"- 约束: {constraint.strip()}")
    if source.strip():
        lines.append(f"- 来源: {source.strip()}")
    lines.append("")

    path.write_text(existing + "\n".join(lines), encoding="utf-8")
    return {
        "path": str(path),
        "summary": cleaned_summary,
        "constraint": constraint.strip(),
        "source": source.strip(),
        "created": "true",
    }


def main() -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args()
    result = append_decision(resolve_decision_path(), args.summary, args.constraint, args.source)
    print_json({"success": True, "decision": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
