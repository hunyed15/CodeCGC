from __future__ import annotations

import difflib
import hashlib
import subprocess
from pathlib import Path
from typing import Any


WORKSPACE = Path(__file__).resolve().parents[1]

IGNORED_PREFIXES = (
    ".git/",
    ".ace-tool/",
    "__pycache__/",
    ".pytest_cache/",
    ".mypy_cache/",
    "node_modules/",
)


def normalize_path_text(path_text: str) -> str:
    normalized = path_text.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def should_ignore_path(relative_path: str) -> bool:
    normalized = normalize_path_text(relative_path)
    return any(
        normalized == prefix.rstrip("/") or normalized.startswith(prefix)
        for prefix in IGNORED_PREFIXES
    )


def iter_workspace_files(root: Path = WORKSPACE) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = normalize_path_text(str(path.relative_to(root)))
        if should_ignore_path(relative):
            continue
        files.append(path)
    return files


def fingerprint_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def read_text_preview(path: Path, max_chars: int = 240) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return "[non-text-or-unreadable]"
    compact = " ".join(text.split())
    return compact[:max_chars]


def read_full_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def extract_text(snapshot_value: Any) -> str | None:
    if isinstance(snapshot_value, dict):
        text = snapshot_value.get("text")
        return text if isinstance(text, str) else None
    return None


def build_unified_diff(
    relative_path: str,
    before_text: str | None,
    after_text: str | None,
    *,
    max_lines: int = 80,
) -> str:
    if before_text is None and after_text is None:
        return ""
    before_lines = [] if before_text is None else before_text.splitlines()
    after_lines = [] if after_text is None else after_text.splitlines()
    diff_lines = list(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"a/{relative_path}",
            tofile=f"b/{relative_path}",
            lineterm="",
            n=3,
        )
    )
    if not diff_lines:
        return ""
    truncated = diff_lines[:max_lines]
    if len(diff_lines) > max_lines:
        truncated.append("... [diff truncated]")
    return "\n".join(truncated)


def count_changed_diff_lines(diff_excerpt: str) -> int:
    count = 0
    for line in diff_excerpt.splitlines():
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith("+") or line.startswith("-"):
            count += 1
    return count


def snapshot_workspace(root: Path = WORKSPACE) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for path in iter_workspace_files(root):
        relative = normalize_path_text(str(path.relative_to(root)))
        fingerprint = fingerprint_file(path)
        full_text = read_full_text(path)
        snapshot[relative] = {
            "hash": fingerprint,
            "size": path.stat().st_size,
            "preview": read_text_preview(path),
            "text": full_text,
        }
    return snapshot


def extract_hash(snapshot_value: Any) -> str:
    if isinstance(snapshot_value, dict):
        return str(snapshot_value.get("hash", ""))
    return str(snapshot_value or "")


def extract_size(snapshot_value: Any) -> int:
    if isinstance(snapshot_value, dict):
        try:
            return int(snapshot_value.get("size", 0) or 0)
        except Exception:
            return 0
    return 0


def extract_preview(snapshot_value: Any) -> str:
    if isinstance(snapshot_value, dict):
        return str(snapshot_value.get("preview", ""))
    return ""


def classify_scope_match(relative_path: str, target_paths: list[str]) -> tuple[bool, str, str]:
    normalized_path = normalize_path_text(relative_path)
    normalized_targets = [normalize_path_text(path) for path in target_paths if str(path).strip()]

    for target in normalized_targets:
        if any(char in target for char in "*?[]"):
            if Path(normalized_path).match(target):
                return True, "glob", target
            continue
        if normalized_path == target:
            return True, "exact", target
        if normalized_path.startswith(target.rstrip("/") + "/"):
            return True, "child", target
    return False, "out-of-scope", ""


def path_matches_scope(relative_path: str, target_paths: list[str]) -> bool:
    matched, _, _ = classify_scope_match(relative_path, target_paths)
    return matched


def detect_git_root(root: Path = WORKSPACE) -> Path | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except FileNotFoundError:
        return None
    if completed.returncode != 0:
        return None
    candidate = completed.stdout.strip()
    return Path(candidate) if candidate else None


def run_git_text_command(git_root: Path, args: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["git", "-C", str(git_root), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except FileNotFoundError:
        return False, ""
    if completed.returncode != 0:
        return False, completed.stderr.strip() or completed.stdout.strip()
    return True, completed.stdout.strip()


def collect_git_evidence(changed_paths: list[str], root: Path = WORKSPACE) -> dict[str, Any]:
    git_root = detect_git_root(root)
    if git_root is None:
        return {
            "git_repository_detected": False,
            "git_root": "",
            "history_available": False,
            "status": "not-a-git-worktree",
            "tracked_changed_files": [],
            "untracked_changed_files": [],
            "git_changed_files": [],
        }

    git_changed_files: list[dict[str, Any]] = []
    tracked_changed_files: list[str] = []
    untracked_changed_files: list[str] = []
    history_available = False

    for relative_path in changed_paths:
        tracked_ok, _ = run_git_text_command(
            git_root,
            ["ls-files", "--error-unmatch", "--", relative_path],
        )
        last_commit_hash = ""
        last_commit_subject = ""
        if tracked_ok:
            tracked_changed_files.append(relative_path)
            log_ok, log_output = run_git_text_command(
                git_root,
                ["log", "-n", "1", "--format=%H%x1f%s", "--", relative_path],
            )
            if log_ok and log_output:
                parts = log_output.split("\x1f", 1)
                last_commit_hash = parts[0].strip()
                last_commit_subject = parts[1].strip() if len(parts) > 1 else ""
                history_available = history_available or bool(last_commit_hash)
        else:
            untracked_changed_files.append(relative_path)

        git_changed_files.append(
            {
                "path": relative_path,
                "tracked": tracked_ok,
                "last_commit_hash": last_commit_hash,
                "last_commit_subject": last_commit_subject,
            }
        )

    status = "git-history-available" if history_available else "git-repository-without-history-proof"
    return {
        "git_repository_detected": True,
        "git_root": str(git_root),
        "history_available": history_available,
        "status": status,
        "tracked_changed_files": tracked_changed_files,
        "untracked_changed_files": untracked_changed_files,
        "git_changed_files": git_changed_files,
    }


def verify_workspace_changes(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    target_paths: list[str],
) -> dict[str, Any]:
    changed_paths: list[str] = []
    all_paths = sorted(set(before) | set(after))
    file_diffs: list[dict[str, Any]] = []

    for relative_path in all_paths:
        before_item = before.get(relative_path)
        after_item = after.get(relative_path)
        if extract_hash(before_item) != extract_hash(after_item):
            in_scope, scope_match_kind, matched_target = classify_scope_match(relative_path, target_paths)
            changed_paths.append(relative_path)
            before_text = extract_text(before_item)
            after_text = extract_text(after_item)
            diff_excerpt = build_unified_diff(
                relative_path,
                before_text,
                after_text,
            )
            diff_kind = (
                "unified-text-diff"
                if diff_excerpt
                else "binary-or-unreadable"
                if before_text is None and after_text is None
                else "hash-only-diff"
            )
            file_diffs.append(
                {
                    "path": relative_path,
                    "change_type": (
                        "added"
                        if before_item is None
                        else "deleted"
                        if after_item is None
                        else "modified"
                    ),
                    "before_hash": extract_hash(before_item),
                    "after_hash": extract_hash(after_item),
                    "before_size": extract_size(before_item),
                    "after_size": extract_size(after_item),
                    "before_preview": extract_preview(before_item),
                    "after_preview": extract_preview(after_item),
                    "diff_excerpt": diff_excerpt,
                    "diff_kind": diff_kind,
                    "changed_line_count": count_changed_diff_lines(diff_excerpt),
                    "in_scope": in_scope,
                    "scope_match_kind": scope_match_kind,
                    "matched_target": matched_target,
                }
            )

    verified_changed_files = [
        path for path in changed_paths if path_matches_scope(path, target_paths)
    ]
    out_of_scope_changed_files = [
        path for path in changed_paths if not path_matches_scope(path, target_paths)
    ]
    git_evidence = collect_git_evidence(changed_paths)
    history_available = bool(git_evidence.get("history_available"))

    return {
        "evidence_source": "workspace-unified-diff-snapshot",
        "workspace_changed_files": changed_paths,
        "verified_changed_files": verified_changed_files,
        "out_of_scope_changed_files": out_of_scope_changed_files,
        "file_diffs": file_diffs,
        "evidence_confidence": (
            "stronger-than-self-report-with-git-history"
            if file_diffs and history_available
            else "stronger-than-self-report"
            if file_diffs
            else "no-observed-diff"
        ),
        "git_evidence": git_evidence,
    }
