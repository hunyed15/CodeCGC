import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from audit_codecgc_external_capabilities import audit_external_capabilities
from audit_codecgc_package_runtime import audit_package_runtime
from codecgc_console_io import render_summary_block
from install_codecgc import collect_doctor_status
from install_codecgc import collect_install_status
from install_codecgc import install_local_runtime

WORKSPACE = Path(__file__).resolve().parents[1]
RELEASE_PROBE_ROOT_ENV = "CODECGC_RELEASE_PROBE_ROOT"

LIFECYCLE_REQUIRED_PATHS = [
    "codecgc/reference/README.md",
    "codecgc/reference/lifecycle-map.md",
    "codecgc/reference/lifecycle-playbook.md",
    "codecgc/reference/maintainer-guide.md",
    "codecgc/reference/mcp-tool-surface.md",
    "codecgc/reference/operation-guide.md",
    "codecgc/reference/onboarding.md",
    "codecgc/reference/path-contract.md",
    "codecgc/reference/quickstart.md",
    "codecgc/reference/recovery-loop.md",
    "codecgc/reference/real-workflow-loop.md",
    "codecgc/reference/release-maintenance-playbook.md",
    "codecgc/reference/troubleshooting.md",
    "codecgc/reference/external-capability-registry.json",
    "codecgc/compound/codecgc-capability-matrix.md",
]

ROADMAP_REQUIRED_PATHS = [
    "codecgc/roadmap/codecgc-release-maintenance/overview.md",
    "codecgc/roadmap/codecgc-release-maintenance/phases.md",
    "codecgc/roadmap/codecgc-release-maintenance/delivery-plan.md",
]

DEPLOY_SIGNAL_GLOBS = {
    "github_actions": [".github/workflows/*.yml", ".github/workflows/*.yaml"],
    "dockerfile": ["Dockerfile", "**/Dockerfile"],
    "docker_compose": ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"],
    "deploy_scripts": ["deploy/*.sh", "deploy/*.ps1", "scripts/deploy*.sh", "scripts/deploy*.ps1", "scripts/release*.sh", "scripts/release*.ps1"],
    "runtime_env_examples": [".env.example", ".env.*.example", "**/.env.example"],
}


def audit_document_set(paths: list[str]) -> dict[str, Any]:
    existing: list[str] = []
    missing: list[str] = []
    for item in paths:
        if (WORKSPACE / item).exists():
            existing.append(item)
        else:
            missing.append(item)
    return {
        "required_count": len(paths),
        "existing": existing,
        "missing": missing,
        "ready": len(missing) == 0,
    }


def collect_deploy_signals() -> dict[str, Any]:
    signal_hits: dict[str, list[str]] = {}
    total_hits = 0
    for signal_name, patterns in DEPLOY_SIGNAL_GLOBS.items():
        matched: list[str] = []
        seen: set[str] = set()
        for pattern in patterns:
            for path in WORKSPACE.glob(pattern):
                if not path.is_file():
                    continue
                relative = path.relative_to(WORKSPACE).as_posix()
                if relative in seen:
                    continue
                seen.add(relative)
                matched.append(relative)
        signal_hits[signal_name] = sorted(matched)
        total_hits += len(matched)

    if total_hits == 0:
        stage = "none"
    elif signal_hits["github_actions"] or signal_hits["dockerfile"] or signal_hits["docker_compose"]:
        stage = "repo-release-ready"
    else:
        stage = "basic-signals"

    return {
        "deploy_signals_detected": signal_hits,
        "total_detected": total_hits,
        "deploy_readiness_stage": stage,
    }


def collect_install_probe(workspace_override: str = "") -> dict[str, Any]:
    if str(workspace_override or "").strip():
        install_status = collect_install_status(workspace_override)
        doctor_status = collect_doctor_status(workspace_override)
        return {
            "mode": "target-workspace",
            "workspace": str(install_status.get("workspace", "")),
            "install_result": {},
            "install_status": install_status,
            "doctor_status": doctor_status,
        }

    probe_root_value = os.environ.get(RELEASE_PROBE_ROOT_ENV, "").strip()
    probe_root = Path(probe_root_value).expanduser().resolve() if probe_root_value else None
    if probe_root is not None:
        probe_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="codecgc-release-check-",
        dir=str(probe_root) if probe_root is not None else None,
        ignore_cleanup_errors=True,
    ) as temp_dir:
        install_result = install_local_runtime(temp_dir)
        install_status = collect_install_status(temp_dir)
        doctor_status = collect_doctor_status(temp_dir)
        return {
            "mode": "temporary-project-install",
            "workspace": temp_dir,
            "install_result": install_result,
            "install_status": install_status,
            "doctor_status": doctor_status,
        }


def audit_release_readiness(workspace_override: str = "") -> dict[str, Any]:
    install_probe = collect_install_probe(workspace_override)
    install_status = install_probe["install_status"]
    doctor_status = install_probe["doctor_status"]
    package_audit = audit_package_runtime()
    external_audit = audit_external_capabilities(workspace_override)
    lifecycle_docs = audit_document_set(LIFECYCLE_REQUIRED_PATHS)
    roadmap_assets = audit_document_set(ROADMAP_REQUIRED_PATHS)
    deploy_signals = collect_deploy_signals()

    install_ready = bool(install_status.get("summary", {}).get("project_ready"))
    doctor_ready = bool(doctor_status.get("summary", {}).get("ready"))
    package_ready = bool(package_audit.get("summary", {}).get("ready"))
    external_ready = bool(external_audit.get("summary", {}).get("ready"))
    lifecycle_ready = bool(lifecycle_docs.get("ready"))
    roadmap_ready = bool(roadmap_assets.get("ready"))

    ready = all([install_ready, doctor_ready, package_ready, external_ready, lifecycle_ready, roadmap_ready])
    human_summary = "release / maintenance / ops 总检查通过。"
    if not ready:
        human_summary = "release / maintenance / ops 总检查仍有阻塞项。"

    recommended_next_action = ""
    if not install_ready:
        recommended_next_action = str(install_status.get("summary", {}).get("recommended_project_command", "")).strip() or "cgc-install"
    elif not doctor_ready:
        recommended_next_action = "cgc-doctor"
    elif not external_ready:
        recommended_next_action = "cgc-external-audit"
    elif not package_ready:
        recommended_next_action = "cgc-package-audit"
    elif not lifecycle_ready or not roadmap_ready:
        recommended_next_action = "检查 codecgc/reference/release-maintenance-playbook.md 与 codecgc/roadmap/codecgc-release-maintenance/ 下的生命周期资产。"

    return {
        "success": ready,
        "mode": "release-readiness-audit",
        "workspace": str(WORKSPACE),
        "summary": {
            "ready": ready,
            "scope": "release / maintenance / ops 就绪状态",
            "human_summary": human_summary,
            "recommended_next_action": recommended_next_action,
            "install_probe_mode": install_probe["mode"],
            "install_probe_workspace": install_probe["workspace"],
            "install_ready": install_ready,
            "doctor_ready": doctor_ready,
            "package_ready": package_ready,
            "external_ready": external_ready,
            "lifecycle_ready": lifecycle_ready,
            "roadmap_ready": roadmap_ready,
            "deploy_signals_detected": deploy_signals["deploy_signals_detected"],
            "deploy_readiness_stage": deploy_signals["deploy_readiness_stage"],
        },
        "install_probe": install_probe,
        "install_status": install_status,
        "doctor_status": doctor_status,
        "package_audit": package_audit,
        "external_audit": external_audit,
        "lifecycle_docs": lifecycle_docs,
        "roadmap_assets": roadmap_assets,
        "deploy_signals": deploy_signals,
    }


def build_summary(result: dict[str, Any]) -> str:
    summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
    lifecycle_docs = result.get("lifecycle_docs", {}) if isinstance(result.get("lifecycle_docs"), dict) else {}
    roadmap_assets = result.get("roadmap_assets", {}) if isinstance(result.get("roadmap_assets"), dict) else {}
    deploy_signals = result.get("deploy_signals", {}) if isinstance(result.get("deploy_signals"), dict) else {}
    lines = [
        f"- 工作区: {result.get('workspace', '')}",
        f"- 范围: {summary.get('scope', '')}",
        f"- 安装探针: {summary.get('install_probe_mode', '')} ({summary.get('install_probe_workspace', '')})",
        f"- 就绪: {'是' if summary.get('ready') else '否'}",
        f"- 摘要: {summary.get('human_summary', '')}",
        f"- 项目级集成: {'就绪' if summary.get('install_ready') else '未就绪'}",
        f"- 运行时自检: {'通过' if summary.get('doctor_ready') else '未通过'}",
        f"- 发布包检查: {'通过' if summary.get('package_ready') else '未通过'}",
        f"- 外部能力检查: {'通过' if summary.get('external_ready') else '未通过'}",
        f"- 生命周期资产: {'齐全' if summary.get('lifecycle_ready') else '缺失'}",
        f"- roadmap 资产: {'齐全' if summary.get('roadmap_ready') else '缺失'}",
        f"- Deploy readiness stage: {summary.get('deploy_readiness_stage', '')}",
    ]
    for signal_name, items in deploy_signals.get("deploy_signals_detected", {}).items():
        if not isinstance(items, list):
            continue
        lines.append(f"- Deploy signal {signal_name}: {', '.join(str(item) for item in items) or '无'}")
    for item in lifecycle_docs.get("missing", []):
        lines.append(f"- 缺少生命周期资产: {item}")
    for item in roadmap_assets.get("missing", []):
        lines.append(f"- 缺少 roadmap 资产: {item}")
    next_action = str(summary.get("recommended_next_action", "")).strip()
    next_actions = [next_action] if next_action else []
    return render_summary_block("CodeCGC Release Readiness", lines, next_actions)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the combined CodeCGC release, maintenance, and ops readiness audit.")
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="summary",
        help="Output format. Summary is the default product-facing mode; use json for debugging or automation.",
    )
    parser.add_argument(
        "--workspace",
        default="",
        help="Optional target workspace root. Defaults to the current shell workspace.",
    )
    args = parser.parse_args()

    result = audit_release_readiness(args.workspace)
    if args.format == "summary":
        print(build_summary(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
