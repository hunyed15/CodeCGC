import argparse
import json
from pathlib import Path
from typing import Any

from codecgc_artifact_roots import discover_flow_directory
from codecgc_artifact_roots import execution_root
from codecgc_artifact_roots import normalize_artifact_class
from codecgc_path_contract import is_project_relative_path
from codecgc_path_contract import resolve_project_path


WORKSPACE = Path(__file__).resolve().parents[1]
PRODUCT_EXECUTION_ROOT = execution_root("product")
FIXTURE_EXECUTION_ROOT = execution_root("fixture")
OLD_REPO_NAME = "CodeCCG"
LEGACY_DEMO_TASK_IDS = {"audit-dry-run-001", "audit-dry-run-002"}


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def detect_root_class(path: Path) -> str:
    if path.parent.resolve() == FIXTURE_EXECUTION_ROOT.resolve():
        return "fixture"
    return "product"


def contains_old_repo_name(value: Any) -> bool:
    return isinstance(value, str) and OLD_REPO_NAME in value


def contains_persisted_absolute_project_path(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    if is_project_relative_path(value):
        return False
    resolved = resolve_project_path(value)
    try:
        resolved.relative_to(WORKSPACE.resolve())
        return True
    except ValueError:
        return False


def expected_artifact_filename(artifact_type: str, artifact_slug: str) -> str:
    base_slug = artifact_slug[11:] if len(artifact_slug) > 11 and artifact_slug[4] == "-" else artifact_slug
    if artifact_type == "feature":
        return f"{base_slug}-acceptance.md"
    if artifact_type == "issue":
        return f"{base_slug}-fix-note.md"
    return ""


def validate_source_contract(source: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    artifact_type = str(source.get("artifact_type", "")).strip()
    artifact_slug = str(source.get("artifact_slug", "")).strip()
    artifact_class = normalize_artifact_class(str(source.get("artifact_class", "product")))
    artifact_file = str(source.get("artifact_file", "")).strip()

    if not artifact_type or not artifact_slug:
        issues.append(
            {
                "problem": "source-missing-artifact-identity",
                "detail": "artifact_type or artifact_slug is missing.",
            }
        )
        return issues

    if artifact_type not in {"feature", "issue"}:
        issues.append(
            {
                "problem": "source-unsupported-artifact-type",
                "detail": f"artifact_type={artifact_type}",
            }
        )
        return issues

    discovered = discover_flow_directory(artifact_type, artifact_slug, artifact_class)
    if not discovered:
        issues.append(
            {
                "problem": "source-artifact-directory-missing",
                "detail": f"artifact_type={artifact_type}, artifact_slug={artifact_slug}, artifact_class={artifact_class}",
            }
        )
        return issues

    discovered_class, directory = discovered
    if discovered_class != artifact_class:
        issues.append(
            {
                "problem": "artifact-class-directory-mismatch",
                "detail": f"artifact_class={artifact_class}, actual_directory_class={discovered_class}",
            }
        )

    expected_name = expected_artifact_filename(artifact_type, artifact_slug)
    expected_artifact_path = directory / expected_name if expected_name else None
    if expected_artifact_path and not expected_artifact_path.exists():
        issues.append(
            {
                "problem": "artifact-target-missing",
                "detail": str(expected_artifact_path),
            }
        )

    if artifact_file:
        artifact_file_path = resolve_project_path(artifact_file)
        if not artifact_file_path.exists():
            issues.append(
                {
                    "problem": "source-artifact-file-missing",
                    "detail": artifact_file,
                }
            )
        elif directory.resolve() not in artifact_file_path.resolve().parents:
            issues.append(
                {
                    "problem": "source-artifact-file-directory-mismatch",
                    "detail": f"artifact_file={artifact_file}, expected_directory={directory}",
                }
            )

    return issues


def inspect_audit(path: Path) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    data = load_json(path)
    if not data:
        return [
            {
                "path": str(path),
                "problem": "invalid-json",
                "detail": "Audit file is not a valid JSON object.",
            }
        ]

    source = data.get("source", {}) if isinstance(data.get("source"), dict) else {}
    task_id = str(data.get("task_id", "")).strip()
    if task_id in LEGACY_DEMO_TASK_IDS:
        return [
            {
                "path": str(path),
                "problem": "legacy-demo-audit",
                "detail": "历史演示用审计样本缺少工作流产物身份信息，应归档或从发布就绪的执行历史中排除。",
            }
        ]
    artifact_class = normalize_artifact_class(str(source.get("artifact_class", "product")))
    root_class = detect_root_class(path)
    if artifact_class != root_class:
        issues.append(
            {
                "path": str(path),
                "problem": "artifact-class-root-mismatch",
                "detail": f"artifact_class={artifact_class}, execution_root={root_class}",
            }
        )

    if contains_old_repo_name(data.get("routing_file")):
        issues.append(
            {
                "path": str(path),
                "problem": "old-repo-name-routing-file",
                "detail": str(data.get("routing_file", "")),
            }
        )
    if contains_old_repo_name(data.get("cd")):
        issues.append(
            {
                "path": str(path),
                "problem": "old-repo-name-cd",
                "detail": str(data.get("cd", "")),
            }
        )
    if contains_old_repo_name(source.get("artifact_file")):
        issues.append(
            {
                "path": str(path),
                "problem": "old-repo-name-artifact-file",
                "detail": str(source.get("artifact_file", "")),
            }
        )

    if contains_persisted_absolute_project_path(data.get("routing_file")):
        issues.append(
            {
                "path": str(path),
                "problem": "absolute-project-routing-file",
                "detail": str(data.get("routing_file", "")),
            }
        )
    if contains_persisted_absolute_project_path(data.get("cd")):
        issues.append(
            {
                "path": str(path),
                "problem": "absolute-project-cd",
                "detail": str(data.get("cd", "")),
            }
        )
    if contains_persisted_absolute_project_path(source.get("artifact_file")):
        issues.append(
            {
                "path": str(path),
                "problem": "absolute-project-artifact-file",
                "detail": str(source.get("artifact_file", "")),
            }
        )

    for item in validate_source_contract(source):
        issues.append(
            {
                "path": str(path),
                "problem": str(item.get("problem", "")),
                "detail": str(item.get("detail", "")),
            }
        )

    return issues


def collect_issues() -> dict[str, Any]:
    scanned = 0
    issues: list[dict[str, str]] = []
    for root in (PRODUCT_EXECUTION_ROOT, FIXTURE_EXECUTION_ROOT):
        if not root.exists():
            continue
        for path in sorted(root.glob("*.json")):
            scanned += 1
            issues.extend(inspect_audit(path))
    return {
        "success": len(issues) == 0,
        "scanned": scanned,
        "issue_count": len(issues),
        "issues": issues,
        "product_execution_root": str(PRODUCT_EXECUTION_ROOT),
        "fixture_execution_root": str(FIXTURE_EXECUTION_ROOT),
    }


def build_summary(result: dict[str, Any]) -> str:
    lines = [
        "CodeCGC 历史执行审计一致性检查",
        f"- 扫描文件数: {result.get('scanned', 0)}",
        f"- 问题数: {result.get('issue_count', 0)}",
        f"- 就绪: {'是' if result.get('success') else '否'}",
    ]
    for item in result.get("issues", []):
        if not isinstance(item, dict):
            continue
        lines.append(
            "- 问题: "
            + f"{item.get('path', '')} "
            + f"[{item.get('problem', '')}] {item.get('detail', '')}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查历史 CodeCGC 执行审计中是否存在放置错误、旧仓库名残留或来源契约不一致问题。"
    )
    parser.add_argument("--format", choices=["json", "summary"], default="json")
    args = parser.parse_args()

    result = collect_issues()
    if args.format == "summary":
        print(build_summary(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
