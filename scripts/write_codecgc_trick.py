import argparse
from pathlib import Path

from codecgc_artifact_roots import artifact_output_root
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_governance_dedupe import has_existing_governance_entry


def resolve_trick_path() -> Path:
    return artifact_output_root("product") / "compound" / "codecgc-tricks.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把一条可复用技巧或技术处方写入 codecgc/compound/codecgc-tricks.md。"
    )
    parser.add_argument("--summary", required=True, help="一行 trick 摘要。")
    parser.add_argument("--kind", choices=["pattern", "library", "technique"], default="technique")
    parser.add_argument("--instruction", default="", help="简短的默认做法或使用建议。")
    parser.add_argument("--source", default="", help="可选的来源产物、工作流或讨论引用。")
    parser.add_argument("--artifact-path", default="", help="已有 trick 文件路径；传入时进入补充完善模式。")
    parser.add_argument("--practice", default="", help="补充默认做法。")
    parser.add_argument("--scope", default="", help="补充适用范围。")
    parser.add_argument("--counterexample", default="", help="补充反例或误用。")
    parser.add_argument("--append-note", default="", help="无法结构化时，附加到 trick 条目的补充说明。")
    return parser


def ensure_document(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# CodeCGC Tricks\n\n"
        "该文件用于记录可复用的模式、库用法与技术技巧。\n\n"
        "## 条目\n\n",
        encoding="utf-8",
    )


def has_existing_entry(existing: str, summary: str) -> bool:
    return has_existing_governance_entry(existing, summary, field_labels=["摘要"])


def append_trick(path: Path, summary: str, kind: str, instruction: str, source: str) -> dict[str, str]:
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

    lines = [f"### {cleaned_summary}", "", f"- 类型: {kind.strip()}", f"- 摘要: {cleaned_summary}"]
    if instruction.strip():
        lines.append(f"- 默认做法: {instruction.strip()}")
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


def update_trick(path: Path, practice: str, scope: str, counterexample: str, append_note: str) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Trick file not found: {path}")
    content = path.read_text(encoding="utf-8")
    lines: list[str] = []
    if practice.strip():
        lines.append(f"- 默认做法补充: {practice.strip()}")
    if scope.strip():
        lines.append(f"- 适用范围: {scope.strip()}")
    if counterexample.strip():
        lines.append(f"- 反例或误用: {counterexample.strip()}")
    if append_note.strip():
        lines.append(f"- 补充说明: {append_note.strip()}")
    if lines:
        content = content.rstrip() + "\n" + "\n".join(lines) + "\n"
        path.write_text(content, encoding="utf-8")
    return {
        "path": str(path),
        "updated": "true",
        "practice": practice.strip(),
        "scope": scope.strip(),
        "counterexample": counterexample.strip(),
        "append_note": append_note.strip(),
    }


def main() -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args()
    if args.artifact_path.strip():
        result = update_trick(
            Path(args.artifact_path),
            args.practice,
            args.scope,
            args.counterexample,
            args.append_note,
        )
        print_json({"success": True, "trick": result})
        return 0
    result = append_trick(resolve_trick_path(), args.summary, args.kind, args.instruction, args.source)
    print_json({"success": True, "trick": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
