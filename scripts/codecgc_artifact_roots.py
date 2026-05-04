from __future__ import annotations

from codecgc_runtime_paths import PROJECT_ROOT


CODECGC_ROOT = PROJECT_ROOT / "codecgc"
PRODUCT_ROOT = CODECGC_ROOT
FIXTURE_ROOT = CODECGC_ROOT / "fixtures"


def normalize_artifact_class(value: str | None) -> str:
    cleaned = str(value or "product").strip().lower()
    return "fixture" if cleaned == "fixture" else "product"


def flow_root(flow: str, artifact_class: str) -> Path:
    base = FIXTURE_ROOT if normalize_artifact_class(artifact_class) == "fixture" else PRODUCT_ROOT
    return base / ("features" if flow == "feature" else "issues")


def execution_root(artifact_class: str) -> Path:
    base = FIXTURE_ROOT if normalize_artifact_class(artifact_class) == "fixture" else PRODUCT_ROOT
    return base / "execution"


def discover_flow_directory(flow: str, slug: str, artifact_class: str = "auto") -> tuple[str, Path] | None:
    classes = (
        [normalize_artifact_class(artifact_class)]
        if artifact_class in {"product", "fixture"}
        else ["product", "fixture"]
    )
    for candidate_class in classes:
        directory = flow_root(flow, candidate_class) / slug
        if directory.exists():
            return candidate_class, directory
    return None


def artifact_output_root(artifact_class: str) -> Path:
    return FIXTURE_ROOT if normalize_artifact_class(artifact_class) == "fixture" else PRODUCT_ROOT
