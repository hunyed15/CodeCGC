from __future__ import annotations

import os
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def resolve_workspace_root(override_workspace: str = "") -> Path:
    explicit = str(override_workspace or "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()

    configured = os.environ.get("CODECGC_WORKSPACE_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    return Path.cwd().resolve()


PROJECT_ROOT = resolve_workspace_root()
