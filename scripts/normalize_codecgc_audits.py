import json
from pathlib import Path
from typing import Any

from codecgc_artifact_roots import discover_flow_directory
from codecgc_artifact_roots import flow_root
from codecgc_artifact_roots import execution_root
from codecgc_artifact_roots import normalize_artifact_class
from codecgc_path_contract import normalize_audit_path_fields
from codecgc_path_contract import normalize_persisted_project_path


WORKSPACE = Path(__file__).resolve().parents[1]
CODECGC_ROOT = WORKSPACE / "codecgc"
PRODUCT_EXECUTION_ROOT = execution_root("product")
FIXTURE_EXECUTION_ROOT = execution_root("fixture")
OLD_REPO_NAME = "CodeCCG"
NEW_REPO_NAME = "CodeCGC"


def replace_repo_name(value: str) -> str:
    return value.replace(OLD_REPO_NAME, NEW_REPO_NAME)


def infer_artifact_class_from_source(source: dict[str, Any], fallback: str) -> str:
    artifact_type = str(source.get("artifact_type", "")).strip()
    artifact_slug = str(source.get("artifact_slug", "")).strip()
    if artifact_type in {"feature", "issue"} and artifact_slug:
        discovered = discover_flow_directory(artifact_type, artifact_slug, "auto")
        if discovered:
            return discovered[0]
    return fallback


def build_expected_artifact_file(source: dict[str, Any], artifact_class: str) -> str:
    artifact_type = str(source.get("artifact_type", "")).strip()
    artifact_slug = str(source.get("artifact_slug", "")).strip()
    if artifact_type not in {"feature", "issue"} or not artifact_slug:
        current = str(source.get("artifact_file", "")).strip()
        return normalize_persisted_project_path(replace_repo_name(current)) if current else current

    base_slug = artifact_slug[11:] if len(artifact_slug) > 11 and artifact_slug[4] == "-" else artifact_slug
    checklist_name = f"{base_slug}-checklist.yaml" if artifact_type == "feature" else f"{base_slug}-fix.yaml"
    return normalize_persisted_project_path(flow_root(artifact_type, artifact_class) / artifact_slug / checklist_name)


def normalize_audit_record(data: dict[str, Any]) -> tuple[dict[str, Any], str]:
    source = data.get("source", {}) if isinstance(data.get("source"), dict) else {}
    declared_artifact_class = normalize_artifact_class(str(source.get("artifact_class", "product")))
    artifact_class = infer_artifact_class_from_source(source, declared_artifact_class)

    for key in ("routing_file", "cd"):
        current = data.get(key)
        if isinstance(current, str):
            data[key] = replace_repo_name(current)

    source["artifact_file"] = build_expected_artifact_file(source, artifact_class)
    source["artifact_class"] = artifact_class
    data["source"] = source
    return normalize_audit_path_fields(data), artifact_class


def normalize_file(path: Path) -> tuple[Path, bool]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return path, False

    normalized, artifact_class = normalize_audit_record(raw)
    target_root = FIXTURE_EXECUTION_ROOT if artifact_class == "fixture" else PRODUCT_EXECUTION_ROOT
    target_root.mkdir(parents=True, exist_ok=True)
    target_path = target_root / path.name
    target_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    moved = target_path.resolve() != path.resolve()
    if moved and path.exists():
        path.unlink()
    return target_path, moved


def main() -> int:
    scanned = 0
    moved = 0
    updated = 0

    for root in [PRODUCT_EXECUTION_ROOT, FIXTURE_EXECUTION_ROOT]:
        if not root.exists():
            continue
        for path in sorted(root.glob("*.json")):
            scanned += 1
            before = path.read_text(encoding="utf-8")
            target_path, was_moved = normalize_file(path)
            after = target_path.read_text(encoding="utf-8")
            if before != after or was_moved:
                updated += 1
            if was_moved:
                moved += 1

    print(
        json.dumps(
            {
                "success": True,
                "scanned": scanned,
                "updated": updated,
                "moved": moved,
                "product_execution_root": str(PRODUCT_EXECUTION_ROOT),
                "fixture_execution_root": str(FIXTURE_EXECUTION_ROOT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
