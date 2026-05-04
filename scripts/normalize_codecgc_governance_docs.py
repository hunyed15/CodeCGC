import json
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
CODECGC_ROOT = WORKSPACE / "codecgc"

TARGET_FILES = [
    CODECGC_ROOT / "compound" / "codecgc-decisions.md",
    CODECGC_ROOT / "compound" / "codecgc-learning-log.md",
    CODECGC_ROOT / "compound" / "codecgc-productization-gap.md",
    CODECGC_ROOT / "architecture" / "codecgc-system-map.md",
    CODECGC_ROOT / "requirements" / "codecgc-core-requirements.md",
]

REPLACEMENTS = [
    ("# CodeCGC Decisions", "# CodeCGC 长期决策"),
    ("This file stores durable accepted decisions for the current repository.", "该文件用于记录当前仓库的长期有效决定。"),
    ("## Entries", "## 条目"),
    ("- Decision:", "- 决定:"),
    ("- Constraint:", "- 约束:"),
    ("- Source:", "- 来源:"),
    ("# CodeCGC Learning Log", "# CodeCGC 经验沉淀"),
    ("This file stores reusable lessons, pitfalls, and preferred practices for the current repository.", "该文件用于记录当前仓库可复用的经验、坑点和推荐做法。"),
    ("- Type: practice", "- 类型: 实践"),
    ("- Type: pitfall", "- 类型: 坑点"),
    ("- Type:", "- 类型:"),
    ("- Summary:", "- 摘要:"),
    ("- Future Instruction:", "- 后续指引:"),
    ("- Current-State Note:", "- 当前状态说明:"),
    ("- Stable Requirement Note:", "- 稳定需求说明:"),
    ("- Behavior-Preserving Note:", "- 保持行为不变说明:"),
    ("## 7. Governance Source", "## 7. 治理来源"),
    ("cgc-entry governance routing", "cgc-entry 治理分诊"),
    ("Treat this as a durable accepted rule for future CodeCGC behavior.", "将其视为约束未来 CodeCGC 行为的长期有效规则。"),
    ("Treat this as a durable current-state architecture update for the repository.", "将其视为当前仓库架构现状的长期更新记录。"),
    ("Treat this as a durable stable requirement update for the product surface.", "将其视为产品面的长期稳定需求更新。"),
    ("Treat this as a behavior-preserving structural improvement candidate that still requires routed execution.", "将其视为保持行为不变、但仍需走受控执行流程的结构优化候选项。"),
]


def normalize_text(text: str) -> str:
    updated = text
    for old, new in REPLACEMENTS:
        updated = updated.replace(old, new)
    return updated


def normalize_file(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"path": str(path), "exists": False, "updated": False}
    original = path.read_text(encoding="utf-8")
    normalized = normalize_text(original)
    updated = normalized != original
    if updated:
        path.write_text(normalized, encoding="utf-8")
    return {"path": str(path), "exists": True, "updated": updated}


def main() -> int:
    results = [normalize_file(path) for path in TARGET_FILES]
    updated_count = sum(1 for item in results if item.get("updated"))
    print(
        json.dumps(
            {
                "success": True,
                "scanned": len(results),
                "updated": updated_count,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
