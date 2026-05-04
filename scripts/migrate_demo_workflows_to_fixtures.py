import json
import shutil
from pathlib import Path

from codecgc_artifact_roots import FIXTURE_ROOT
from codecgc_artifact_roots import PRODUCT_ROOT


WORKSPACE = Path(__file__).resolve().parents[1]
CODECGC_ROOT = WORKSPACE / "codecgc"
FEATURES_ROOT = PRODUCT_ROOT / "features"
ISSUES_ROOT = PRODUCT_ROOT / "issues"
FIXTURE_FEATURES_ROOT = FIXTURE_ROOT / "features"
FIXTURE_ISSUES_ROOT = FIXTURE_ROOT / "issues"

FEATURE_FIXTURE_NAMES = {
    "2026-05-01-artifact-class-demo",
    "2026-05-01-artifact-class-ui-demo",
    "2026-05-01-cli-demo-ui",
    "2026-05-01-closed-route-demo",
    "2026-05-01-demo-login-ui",
    "2026-05-01-direct-goal-check",
    "2026-05-01-final-check-ui",
    "2026-05-01-migration-check-ui",
    "2026-05-01-mixed-plan-ui-api",
    "2026-05-01-mixed-scope-demo",
    "2026-05-01-progression-demo",
    "2026-05-01-review-status-demo",
    "2026-05-01-richer-plan-ui",
    "2026-05-01-session-continue-ui",
    "2026-05-01-shared-plan-demo",
    "2026-05-01-structured-plan-ui",
    "2026-05-01-structured-plan-ui-v2",
}

ISSUE_FIXTURE_NAMES = {
    "2026-05-01-demo-sync-bug",
    "2026-05-01-mixed-fix-ui-api",
    "2026-05-01-richer-plan-bug",
    "2026-05-01-session-continue-bug",
    "2026-05-01-structured-plan-bug",
    "2026-05-01-structured-plan-bug-v2",
}


def ensure_artifact_class(text: str) -> str:
    if "artifact_class:" in text:
        lines = text.splitlines()
        updated = []
        for line in lines:
            if line.startswith("artifact_class:"):
                updated.append("artifact_class: fixture")
            else:
                updated.append(line)
        return "\n".join(updated) + ("\n" if text.endswith("\n") else "")

    if text.startswith("---\n"):
        insert_at = text.find("\n", 4)
        if insert_at != -1:
            return text[: insert_at + 1] + "artifact_class: fixture\n" + text[insert_at + 1 :]

    if text.startswith("feature: ") or text.startswith("issue: "):
        first_newline = text.find("\n")
        if first_newline != -1:
            return text[: first_newline + 1] + "artifact_class: fixture\n" + text[first_newline + 1 :]

    return text


def rewrite_directory_files(directory: Path) -> int:
    updated = 0
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".yaml"}:
            continue
        original = path.read_text(encoding="utf-8")
        rewritten = ensure_artifact_class(original)
        if rewritten != original:
            path.write_text(rewritten, encoding="utf-8")
            updated += 1
    return updated


def move_directory(src: Path, dst: Path) -> int:
    if not src.exists():
        return 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.move(str(src), str(dst))
    return rewrite_directory_files(dst)


def main() -> int:
    moved_features = 0
    moved_issues = 0
    updated_files = 0

    for name in sorted(FEATURE_FIXTURE_NAMES):
        updated_files += move_directory(FEATURES_ROOT / name, FIXTURE_FEATURES_ROOT / name)
        if (FIXTURE_FEATURES_ROOT / name).exists():
            moved_features += 1

    for name in sorted(ISSUE_FIXTURE_NAMES):
        updated_files += move_directory(ISSUES_ROOT / name, FIXTURE_ISSUES_ROOT / name)
        if (FIXTURE_ISSUES_ROOT / name).exists():
            moved_issues += 1

    print(
        json.dumps(
            {
                "success": True,
                "moved_features": moved_features,
                "moved_issues": moved_issues,
                "updated_files": updated_files,
                "fixture_features_root": str(FIXTURE_FEATURES_ROOT),
                "fixture_issues_root": str(FIXTURE_ISSUES_ROOT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
