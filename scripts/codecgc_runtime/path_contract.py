from __future__ import annotations

import re
from pathlib import Path

from .paths import PROJECT_ROOT


def normalize_path_text(path_text: str) -> str:
    return str(path_text or "").replace("\\", "/").strip()


def is_project_relative_path(path_text: str) -> bool:
    normalized = normalize_path_text(path_text)
    if not normalized:
        return False
    if normalized.startswith(("/", "~")):
        return False
    if re.match(r"^[A-Za-z]:/", normalized):
        return False
    return True


def _relative_to_project(path: Path, project_root: Path) -> str | None:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return None


def _legacy_project_suffix(path_text: str) -> str | None:
    normalized = normalize_path_text(path_text)
    if not normalized:
        return None

    for marker in ("/CodeCGC/release/", "/CodeCGC/", "/CodeCCG/release/", "/CodeCCG/"):
        if marker in normalized:
            return normalized.split(marker, 1)[1].lstrip("/")

    if normalized.endswith(("/CodeCGC/release", "/CodeCGC", "/CodeCCG/release", "/CodeCCG")):
        return "."

    basename = normalized.rsplit("/", 1)[-1]
    if basename == "model-routing.yaml":
        return "model-routing.yaml"
    return None


def to_project_relative_path(
    path_value: str | Path,
    project_root: Path = PROJECT_ROOT,
    *,
    allow_legacy_suffix: bool = True,
) -> str:
    path_text = normalize_path_text(str(path_value))
    if not path_text:
        return ""
    if path_text == ".":
        return "."

    path = Path(path_text)
    if path.is_absolute():
        relative = _relative_to_project(path, project_root)
        if relative is not None:
            return relative or "."

        if allow_legacy_suffix:
            legacy_suffix = _legacy_project_suffix(path_text)
            if legacy_suffix is not None:
                return legacy_suffix or "."

        return path_text

    normalized = path_text
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized or "."


def resolve_project_path(path_value: str | Path, project_root: Path = PROJECT_ROOT) -> Path:
    path_text = normalize_path_text(str(path_value))
    if not path_text or path_text == ".":
        return project_root.resolve()

    path = Path(path_text)
    if path.is_absolute():
        relative = _relative_to_project(path, project_root)
        if relative is not None:
            return (project_root / relative).resolve()

        legacy_suffix = _legacy_project_suffix(path_text)
        if legacy_suffix is not None:
            return (project_root / legacy_suffix).resolve()

        return path.resolve()

    return (project_root / path_text).resolve()


def normalize_persisted_project_path(path_value: str | Path, project_root: Path = PROJECT_ROOT) -> str:
    return to_project_relative_path(path_value, project_root)


def normalize_source_contract(source: object, project_root: Path = PROJECT_ROOT) -> object:
    if not isinstance(source, dict):
        return source
    normalized = dict(source)
    artifact_file = normalized.get("artifact_file")
    if isinstance(artifact_file, str) and artifact_file.strip():
        normalized["artifact_file"] = normalize_persisted_project_path(artifact_file, project_root)
    return normalized


def normalize_audit_path_fields(record: dict, project_root: Path = PROJECT_ROOT) -> dict:
    normalized = dict(record)
    for key in ("routing_file", "cd"):
        value = normalized.get(key)
        if isinstance(value, str) and value.strip():
            normalized[key] = normalize_persisted_project_path(value, project_root)

    source = normalized.get("source")
    normalized["source"] = normalize_source_contract(source, project_root)
    return normalized
