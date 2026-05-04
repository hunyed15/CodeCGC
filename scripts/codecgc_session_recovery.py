from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codecgc_artifact_roots import execution_root


def load_audit_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def extract_reusable_session_id(audit: dict[str, Any] | None) -> str:
    if not isinstance(audit, dict):
        return ""

    result = audit.get("result", {})
    if isinstance(result, dict):
        session_id = str(result.get("session_id", "")).strip()
        if session_id:
            return session_id

    return str(audit.get("requested_session_id", "")).strip()


def resolve_task_audit_path(task_id: str, artifact_class: str) -> Path | None:
    cleaned_task_id = str(task_id).strip()
    if not cleaned_task_id:
        return None
    return execution_root(artifact_class) / f"{cleaned_task_id}.json"


def resolve_session_id_from_task(task_id: str, artifact_class: str) -> str:
    audit_path = resolve_task_audit_path(task_id, artifact_class)
    if audit_path is None:
        return ""
    return extract_reusable_session_id(load_audit_json(audit_path))
