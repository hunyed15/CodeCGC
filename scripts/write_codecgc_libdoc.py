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
    return normalized or "libdoc"


def resolve_reference_root() -> Path:
    return artifact_output_root("product") / "reference"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把一条 API/组件/命令参考文档请求写入 codecgc/reference/ 下的 libdoc 文档。"
    )
    parser.add_argument("--summary", required=True, help="一行 libdoc 摘要。")
    parser.add_argument("--surface", default="public-api", help="可选的公开表面类型说明。")
    parser.add_argument("--source", default="", help="可选的来源产物、工作流或讨论引用。")
    parser.add_argument("--artifact-path", default="", help="已有 libdoc 文件路径；传入时进入补充完善模式。")
    parser.add_argument("--entry", default="", help="补充入口说明。")
    parser.add_argument("--contract", default="", help="补充公开契约说明。")
    parser.add_argument("--example", default="", help="补充最小示例说明。")
    parser.add_argument("--boundary", default="", help="补充边界说明。")
    parser.add_argument("--append-note", default="", help="无法结构化时，附加到 libdoc 的补充说明。")
    return parser


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_libdoc(path: Path, summary: str, surface: str, source: str) -> dict[str, str]:
    ensure_parent(path)
    created = not path.exists()
    if created:
        title = summary.strip()
        lines = [
            f"# {title}",
            "",
            f"- 表面类型: {surface.strip() or 'public-api'}",
            f"- 摘要: {title}",
        ]
        if source.strip():
            lines.append(f"- 来源: {source.strip()}")
        lines.extend(
            [
                "",
                "## 1. 入口",
                "",
                "待补充。",
                "",
                "## 2. 公开契约",
                "",
                "待补充。",
                "",
            ]
        )
        path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "path": str(path),
        "summary": summary.strip(),
        "surface": surface.strip() or "public-api",
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


def update_libdoc(path: Path, entry: str, contract: str, example: str, boundary: str, append_note: str) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"Libdoc file not found: {path}")
    content = path.read_text(encoding="utf-8")
    if entry.strip():
        content = replace_section(content, "## 1. 入口", entry.strip())
    if contract.strip():
        content = replace_section(content, "## 2. 公开契约", contract.strip())
    combined = "\n\n".join(part for part in [example.strip(), boundary.strip()] if part)
    if combined:
        content = replace_section(content, "## 3. 示例与边界", combined)
    elif "## 3. 示例与边界" not in content and append_note.strip():
        content = replace_section(content, "## 3. 示例与边界", append_note.strip())
        append_note = ""
    if append_note.strip():
        if "## 4. 补充说明" in content:
            content = replace_section(content, "## 4. 补充说明", append_note.strip())
        else:
            content = content.rstrip() + f"\n\n## 4. 补充说明\n\n{append_note.strip()}\n"
    path.write_text(content, encoding="utf-8")
    return {
        "path": str(path),
        "updated": "true",
        "entry": entry.strip(),
        "contract": contract.strip(),
        "example": example.strip(),
        "boundary": boundary.strip(),
        "append_note": append_note.strip(),
    }


def main() -> int:
    configure_utf8_stdio()
    args = build_parser().parse_args()
    if args.artifact_path.strip():
        result = update_libdoc(
            Path(args.artifact_path),
            args.entry,
            args.contract,
            args.example,
            args.boundary,
            args.append_note,
        )
        print_json({"success": True, "libdoc": result})
        return 0
    filename = f"{slugify(args.summary)}-libdoc.md"
    result = write_libdoc(resolve_reference_root() / filename, args.summary, args.surface, args.source)
    print_json({"success": True, "libdoc": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
