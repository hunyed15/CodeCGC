import argparse
from pathlib import Path

from codecgc_artifact_roots import artifact_output_root
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_governance_dedupe import has_existing_governance_entry


SECTION_HEADING = "## 7. Governance Updates"


def resolve_requirement_path() -> Path:
    return artifact_output_root("product") / "requirements" / "codecgc-core-requirements.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把一条长期有效的需求治理更新写入 codecgc/requirements/codecgc-core-requirements.md。"
    )
    parser.add_argument("--summary", required=True, help="一行需求更新摘要。")
    parser.add_argument("--note", default="", help="可选的稳定需求说明。")
    parser.add_argument("--source", default="", help="可选的来源产物、工作流或讨论引用。")
    return parser


def ensure_governance_section(text: str) -> str:
    if SECTION_HEADING in text:
        return text
    stripped = text.rstrip()
    suffix = "\n\n" if stripped else ""
    return f"{stripped}{suffix}{SECTION_HEADING}\n\n"


def has_existing_entry(existing: str, summary: str) -> bool:
    return has_existing_governance_entry(existing, summary, field_labels=["Summary", "摘要"])


def append_requirement_update(path: Path, summary: str, note: str, source: str) -> dict[str, str]:
    existing = path.read_text(encoding="utf-8")
    ensured = ensure_governance_section(existing)
    cleaned_summary = summary.strip()
    if has_existing_entry(ensured, cleaned_summary):
        return {
            "path": str(path),
            "summary": cleaned_summary,
            "note": note.strip(),
            "source": source.strip(),
            "created": "false",
        }

    lines = [f"### {cleaned_summary}", "", f"- 摘要: {cleaned_summary}"]
    if note.strip():
        lines.append(f"- 稳定需求说明: {note.strip()}")
    if source.strip():
        lines.append(f"- 来源: {source.strip()}")
    lines.append("")

    path.write_text(ensured + "\n".join(lines), encoding="utf-8")
    return {
        "path": str(path),
        "summary": cleaned_summary,
        "note": note.strip(),
        "source": source.strip(),
        "created": "true",
    }


def main() -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args()
    result = append_requirement_update(resolve_requirement_path(), args.summary, args.note, args.source)
    print_json({"success": True, "requirement": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
