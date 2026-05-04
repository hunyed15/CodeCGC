import argparse
from pathlib import Path

from codecgc_artifact_roots import artifact_output_root
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_governance_dedupe import has_existing_governance_entry


def resolve_learning_path() -> Path:
    return artifact_output_root("product") / "compound" / "codecgc-learning-log.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把一条可复用经验写入 codecgc/compound/codecgc-learning-log.md。"
    )
    parser.add_argument("--summary", required=True, help="一行经验摘要。")
    parser.add_argument("--kind", choices=["pitfall", "practice"], default="practice")
    parser.add_argument("--instruction", default="", help="简短的可复用后续指引。")
    parser.add_argument("--source", default="", help="可选的来源产物、工作流或讨论引用。")
    return parser


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def ensure_document(path: Path) -> None:
    if path.exists():
        return
    ensure_parent(path)
    path.write_text(
        "# CodeCGC 经验沉淀\n\n"
        "该文件用于记录当前仓库可复用的经验、坑点和推荐做法。\n\n"
        "## 条目\n\n",
        encoding="utf-8",
    )


def has_existing_entry(existing: str, summary: str) -> bool:
    return has_existing_governance_entry(existing, summary, field_labels=["Summary", "摘要"])


def append_learning(path: Path, summary: str, kind: str, instruction: str, source: str) -> dict[str, str]:
    ensure_document(path)
    cleaned_summary = summary.strip()
    existing = path.read_text(encoding="utf-8")
    if has_existing_entry(existing, cleaned_summary):
        return {
            "path": str(path),
            "summary": cleaned_summary,
            "kind": kind.strip(),
            "instruction": instruction.strip(),
            "source": source.strip(),
            "created": "false",
        }

    kind_label = "坑点" if kind.strip() == "pitfall" else "实践"
    lines = [f"### {cleaned_summary}", "", f"- 类型: {kind_label}", f"- 摘要: {cleaned_summary}"]
    if instruction.strip():
        lines.append(f"- 后续指引: {instruction.strip()}")
    if source.strip():
        lines.append(f"- 来源: {source.strip()}")
    lines.append("")

    path.write_text(existing + "\n".join(lines), encoding="utf-8")
    return {
        "path": str(path),
        "summary": cleaned_summary,
        "kind": kind.strip(),
        "instruction": instruction.strip(),
        "source": source.strip(),
        "created": "true",
    }


def main() -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args()
    result = append_learning(resolve_learning_path(), args.summary, args.kind, args.instruction, args.source)
    print_json({"success": True, "learning": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
