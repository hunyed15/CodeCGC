import argparse
import re
from pathlib import Path

from codecgc_artifact_roots import artifact_output_root
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json


def slugify(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "guide"


def resolve_docs_root() -> Path:
    return artifact_output_root("product") / "docs"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把一条面向用户或开发者的指南请求写入 codecgc/docs/ 下的 guide 文档。"
    )
    parser.add_argument("--summary", required=True, help="一行 guide 摘要。")
    parser.add_argument("--audience", choices=["user", "developer"], default="developer")
    parser.add_argument("--note", default="", help="可选的指南用途说明。")
    parser.add_argument("--source", default="", help="可选的来源产物、工作流或讨论引用。")
    parser.add_argument("--artifact-path", default="", help="已有 guide 文件路径；传入时进入补充完善模式。")
    parser.add_argument("--purpose", default="", help="补充 guide 的目的说明。")
    parser.add_argument("--steps", default="", help="补充 guide 的使用步骤。")
    parser.add_argument("--boundary", default="", help="补充 guide 的边界或前置条件。")
    parser.add_argument("--append-note", default="", help="无法结构化时，附加到 guide 的补充说明。")
    return parser


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_guide(path: Path, summary: str, audience: str, note: str, source: str) -> dict[str, str]:
    ensure_parent(path)
    created = not path.exists()
    if created:
        title = summary.strip()
        lines = [
            f"# {title}",
            "",
            f"- Audience: {'开发者' if audience == 'developer' else '用户'}",
            f"- 摘要: {title}",
        ]
        if note.strip():
            lines.append(f"- 用途: {note.strip()}")
        if source.strip():
            lines.append(f"- 来源: {source.strip()}")
        lines.extend(
            [
                "",
                "## 1. 目的",
                "",
                "待补充。",
                "",
                "## 2. 使用步骤",
                "",
                "待补充。",
                "",
            ]
        )
        path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "path": str(path),
        "summary": summary.strip(),
        "audience": audience,
        "note": note.strip(),
        "source": source.strip(),
        "created": "true" if created else "false",
    }


def replace_section(text: str, heading: str, body: str) -> str:
    pattern = rf"({re.escape(heading)}\n\n)(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, flags=re.DOTALL)
    if match:
        return text[:match.start()] + f"{heading}\n\n{body.strip()}\n" + text[match.end():]
    stripped = text.rstrip()
    suffix = "\n\n" if stripped else ""
    return f"{stripped}{suffix}{heading}\n\n{body.strip()}\n"


def update_guide(path: Path, purpose: str, steps: str, boundary: str, append_note: str) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Guide file not found: {path}")
    content = path.read_text(encoding="utf-8")
    if purpose.strip():
        content = replace_section(content, "## 1. 目的", purpose.strip())
    if steps.strip():
        content = replace_section(content, "## 2. 使用步骤", steps.strip())
    if boundary.strip():
        content = replace_section(content, "## 3. 使用边界", boundary.strip())
    elif "## 3. 使用边界" not in content and append_note.strip():
        content = replace_section(content, "## 3. 使用边界", append_note.strip())
        append_note = ""
    if append_note.strip():
        note_block = f"## 4. 补充说明\n\n{append_note.strip()}\n"
        if "## 4. 补充说明" in content:
            content = replace_section(content, "## 4. 补充说明", append_note.strip())
        else:
            content = content.rstrip() + "\n\n" + note_block
    path.write_text(content, encoding="utf-8")
    return {
        "path": str(path),
        "updated": "true",
        "purpose": purpose.strip(),
        "steps": steps.strip(),
        "boundary": boundary.strip(),
        "append_note": append_note.strip(),
    }


def main() -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args()
    if args.artifact_path.strip():
        result = update_guide(
            Path(args.artifact_path),
            args.purpose,
            args.steps,
            args.boundary,
            args.append_note,
        )
        print_json({"success": True, "guide": result})
        return 0
    filename = f"{slugify(args.summary)}-guide.md"
    result = write_guide(resolve_docs_root() / filename, args.summary, args.audience, args.note, args.source)
    print_json({"success": True, "guide": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
