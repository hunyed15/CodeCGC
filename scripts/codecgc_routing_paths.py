from __future__ import annotations

from pathlib import Path

from codecgc_runtime_paths import PACKAGE_ROOT
from codecgc_runtime_paths import PROJECT_ROOT


PACKAGE_ROUTING_FILE = PACKAGE_ROOT / "model-routing.yaml"
PROJECT_ROUTING_FILE = PROJECT_ROOT / "model-routing.yaml"


def resolve_active_routing_file() -> Path:
    if PROJECT_ROUTING_FILE.exists():
        return PROJECT_ROUTING_FILE
    return PACKAGE_ROUTING_FILE
