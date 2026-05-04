import argparse
from pathlib import Path

from codecgc_artifact_roots import artifact_output_root
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_governance_dedupe import has_existing_governance_entry


def resolve_explore_path() -> Path:
    return artifact_output_root("product") / "compound" / "codecgc-explorations.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把一条定向代码探索请求写入 codecgc/compound/codecgc-explorations.md。"
    )
    parser.add_argument("--summary", required=True, help="一行 explore 摘要。")
    parser.add_argument("--kind", choices=["question", "module-overview", "spike"], default="question")
    parser.add_argument("--source", default="", help="可选的来源产物、工作流或讨论引用。")
    parser.add_argument("--artifact-path", default="", help="已有 explore 文件路径；传入时进入补充完善模式。")
    parser.add_argument("--question-detail", default="", help="补充核心问题。")
    parser.add_argument("--target-modules", default="", help="补充目标模块、目录或文件。")
    parser.add_argument("--expected-output", default="", help="补充预期输出形式。")
    parser.add_argument("--append-note", default="", help="无法结构化时，附加到 explore 条目的补充说明。")
    return parser


def ensure_document(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# CodeCGC Explorations\n\n"
        "该文件用于记录待做或已登记的定向代码探索请求。\n\n"
        "## 条目\n\n",
        encoding="utf-8",
    )


def has_existing_entry(existing: str, summary: str) -> bool:
    return has_existing_governance_entry(existing, summary, field_labels=["摘要"])


def append_exploration(path: Path, summary: str, kind: str, source: str) -> dict[str, str]:
    ensure_document(path)
    cleaned_summary = summary.strip()
    existing = path.read_text(encoding="utf-8")
    if has_existing_entry(existing, cleaned_summary):
        return {
            "path": str(path),
            "summary": cleaned_summary,
            "kind": kind.strip(),
            "source": source.strip(),
            "created": "false",
        }

    lines = [f"### {cleaned_summary}", "", f"- 类型: {kind.strip()}", f"- 摘要: {cleaned_summary}"]
    if source.strip():
        lines.append(f"- 来源: {source.strip()}")
    lines.append("")

    path.write_text(existing + "\n".join(lines), encoding="utf-8")
    return {
        "path": str(path),
        "summary": cleaned_summary,
        "kind": kind.strip(),
        "source": source.strip(),
        "created": "true",
    }


def update_exploration(path: Path, question_detail: str, target_modules: str, expected_output: str, append_note: str) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Explore file not found: {path}")
    content = path.read_text(encoding="utf-8")
    lines: list[str] = []
    if question_detail.strip():
        lines.append(f"- 核心问题: {question_detail.strip()}")
    if target_modules.strip():
        lines.append(f"- 目标模块: {target_modules.strip()}")
    if expected_output.strip():
        lines.append(f"- 预期输出: {expected_output.strip()}")
    if append_note.strip():
        lines.append(f"- 补充说明: {append_note.strip()}")
    if lines:
        content = content.rstrip() + "\n" + "\n".join(lines) + "\n"
        path.write_text(content, encoding="utf-8")
    return {
        "path": str(path),
        "updated": "true",
        "question_detail": question_detail.strip(),
        "target_modules": target_modules.strip(),
        "expected_output": expected_output.strip(),
        "append_note": append_note.strip(),
    }


def main() -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args()
    if args.artifact_path.strip():
        result = update_exploration(
            Path(args.artifact_path),
            args.question_detail,
            args.target_modules,
            args.expected_output,
            args.append_note,
        )
        print_json({"success": True, "explore": result})
        return 0
    result = append_exploration(resolve_explore_path(), args.summary, args.kind, args.source)
    print_json({"success": True, "explore": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
