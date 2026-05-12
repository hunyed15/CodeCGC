import argparse
import ast
import json
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from codecgc_console_io import render_summary_block

WORKSPACE = Path(__file__).resolve().parents[1]
PACKAGE_JSON_PATH = WORKSPACE / "package.json"
_PYTHON_CMD = sys.executable

RUNTIME_ENTRYPOINTS = [
    "bin/codecgc.js",
    "bin/cgc-start.js",
    "mcp/codecgcmcp/src/codecgcmcp/cli.py",
    "scripts/install_codecgc.py",
    "scripts/codecgc_cli.py",
    "scripts/codecgc_policy.py",
]

RUNTIME_STATIC_REQUIREMENTS = [
    ".claude/hooks/route-edit.ps1",
    "codecgc/templates/project/claude/settings.local.json",
    "codecgc/templates/project/codex/codecgcrc.json",
    "codecgc/templates/project/gemini/policies/codecgc-policy.toml",
    "model-routing.yaml",
    "requirements.txt",
    "scripts/codecgc_runtime/__init__.py",
    "scripts/audit_codecgc_external_capabilities.py",
    "scripts/audit_codecgc_lifecycle.py",
    "mcp/codexmcp/pyproject.toml",
    "mcp/codexmcp/src/codexmcp/__init__.py",
    "mcp/codexmcp/src/codexmcp/cli.py",
    "mcp/codexmcp/src/codexmcp/server.py",
    "mcp/geminimcp/pyproject.toml",
    "mcp/geminimcp/src/geminimcp/__init__.py",
    "mcp/geminimcp/src/geminimcp/cli.py",
    "mcp/geminimcp/src/geminimcp/server.py",
    "scripts/audit_codecgc_release_readiness.py",
    "scripts/write_codecgc_guide.py",
    "scripts/write_codecgc_libdoc.py",
    "scripts/write_codecgc_trick.py",
    "scripts/write_codecgc_explore.py",
]

DOC_RUNTIME_PATHS = [
    "codecgc/cgc/SKILL.md",
    "codecgc/cgc-build/SKILL.md",
    "codecgc/cgc-fix/SKILL.md",
    "codecgc/cgc-onboard/SKILL.md",
    "codecgc/cgc-plan/SKILL.md",
    "codecgc/cgc-review/SKILL.md",
    "codecgc/compound/codecgc-capability-matrix.md",
    "codecgc/reference/README.md",
    "codecgc/reference/external-capability-registry.json",
    "codecgc/reference/lifecycle-playbook.md",
    "codecgc/reference/maintainer-guide.md",
    "codecgc/reference/mcp-tool-surface.md",
    "codecgc/reference/operation-guide.md",
    "codecgc/reference/path-contract.md",
    "codecgc/reference/policy-routing.md",
    "codecgc/reference/project-structure.md",
    "codecgc/reference/quickstart.md",
    "codecgc/reference/onboarding.md",
    "codecgc/reference/recovery-loop.md",
    "codecgc/reference/real-workflow-loop.md",
    "codecgc/reference/release-maintenance-playbook.md",
    "codecgc/reference/troubleshooting.md",
    "codecgc/roadmap/codecgc-release-maintenance/delivery-plan.md",
    "codecgc/roadmap/codecgc-release-maintenance/overview.md",
    "codecgc/roadmap/codecgc-release-maintenance/phases.md",
]

PLACEHOLDER_METADATA_MARKERS = (
    "your-org",
    "example.com",
    "todo",
    "placeholder",
)


def normalize_path_text(path: str) -> str:
    return str(path).replace("\\", "/").strip()


def load_package_manifest() -> dict[str, Any]:
    return json.loads(PACKAGE_JSON_PATH.read_text(encoding="utf-8"))


def contains_placeholder_marker(value: str) -> bool:
    normalized = normalize_path_text(value).lower()
    return any(marker in normalized for marker in PLACEHOLDER_METADATA_MARKERS)


def audit_manifest_metadata(manifest: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []

    homepage = str(manifest.get("homepage", "")).strip()
    if not homepage:
        issues.append(
            {
                "field": "homepage",
                "problem": "missing",
                "detail": "Package homepage is missing.",
            }
        )
    elif contains_placeholder_marker(homepage):
        issues.append(
            {
                "field": "homepage",
                "problem": "placeholder",
                "detail": homepage,
            }
        )

    bugs = manifest.get("bugs", {})
    bugs_url = str(bugs.get("url", "")).strip() if isinstance(bugs, dict) else ""
    if not bugs_url:
        issues.append(
            {
                "field": "bugs.url",
                "problem": "missing",
                "detail": "Package bugs.url is missing.",
            }
        )
    elif contains_placeholder_marker(bugs_url):
        issues.append(
            {
                "field": "bugs.url",
                "problem": "placeholder",
                "detail": bugs_url,
            }
        )

    repository = manifest.get("repository", {})
    repository_url = str(repository.get("url", "")).strip() if isinstance(repository, dict) else ""
    if not repository_url:
        issues.append(
            {
                "field": "repository.url",
                "problem": "missing",
                "detail": "Package repository.url is missing.",
            }
        )
    elif contains_placeholder_marker(repository_url):
        issues.append(
            {
                "field": "repository.url",
                "problem": "placeholder",
                "detail": repository_url,
            }
        )

    return issues


def path_matches_package_files(path_text: str, file_rules: list[str]) -> bool:
    normalized = normalize_path_text(path_text)
    for rule in file_rules:
        normalized_rule = normalize_path_text(rule)
        if normalized_rule.endswith("/"):
            if normalized.startswith(normalized_rule):
                return True
            continue
        if "*" in normalized_rule or "?" in normalized_rule:
            if fnmatch(normalized, normalized_rule):
                return True
            continue
        if normalized == normalized_rule:
            return True
        if (WORKSPACE / normalized_rule).is_dir() and normalized.startswith(f"{normalized_rule}/"):
            return True
    return False


def resolve_local_python_module(module_name: str) -> str:
    relative = normalize_path_text(module_name.replace(".", "/") + ".py")
    package_candidates = [
        f"mcp/{package}/src/{relative}"
        for package in ("codecgcmcp", "codexmcp", "geminimcp")
        if module_name == package or module_name.startswith(f"{package}.")
    ]
    candidates = [
        *package_candidates,
        f"scripts/{relative}",
        f"scripts/{relative.split('/')[-1]}",
        relative,
    ]
    for candidate in candidates:
        if (WORKSPACE / candidate).exists():
            return candidate
    package_init = f"scripts/{normalize_path_text(module_name.replace('.', '/'))}/__init__.py"
    if (WORKSPACE / package_init).exists():
        return package_init
    for package in ("codecgcmcp", "codexmcp", "geminimcp"):
        if module_name == package or module_name.startswith(f"{package}."):
            package_init = f"mcp/{package}/src/{normalize_path_text(module_name.replace('.', '/'))}/__init__.py"
            if (WORKSPACE / package_init).exists():
                return package_init
    root_package_init = f"{normalize_path_text(module_name.replace('.', '/'))}/__init__.py"
    if (WORKSPACE / root_package_init).exists():
        return root_package_init
    if (WORKSPACE / relative).exists():
        return relative
    return ""


def resolve_relative_python_module(current_path: str, level: int, module_name: str | None) -> str:
    current = Path(normalize_path_text(current_path))
    package_dir = current.parent
    for _ in range(max(level - 1, 0)):
        package_dir = package_dir.parent

    if module_name:
        candidate = package_dir / normalize_path_text(module_name.replace(".", "/") + ".py")
        if (WORKSPACE / candidate).exists():
            return normalize_path_text(str(candidate))

        package_init = package_dir / normalize_path_text(module_name.replace(".", "/")) / "__init__.py"
        if (WORKSPACE / package_init).exists():
            return normalize_path_text(str(package_init))

    init_candidate = package_dir / "__init__.py"
    if (WORKSPACE / init_candidate).exists():
        return normalize_path_text(str(init_candidate))
    return ""


def parse_local_python_dependencies(relative_path: str) -> tuple[list[str], list[str]]:
    path = WORKSPACE / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    missing_modules: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolved = resolve_local_python_module(alias.name)
                if resolved:
                    imports.append(resolved)
        elif isinstance(node, ast.ImportFrom):
            if node.level != 0:
                resolved_relative = resolve_relative_python_module(relative_path, node.level, node.module)
                if resolved_relative:
                    imports.append(resolved_relative)
                continue
            if not node.module:
                continue
            resolved = resolve_local_python_module(node.module)
            if resolved:
                imports.append(resolved)
                continue
            if node.module.startswith("codexmcp.") or node.module.startswith("geminimcp."):
                resolved_package = normalize_path_text(node.module.replace(".", "/") + ".py")
                if (WORKSPACE / resolved_package).exists():
                    imports.append(resolved_package)
                else:
                    missing_modules.append(node.module)

    unique_imports = sorted(set(imports))
    unique_missing = sorted(set(missing_modules))
    return unique_imports, unique_missing


def collect_python_runtime_graph(entrypoints: list[str]) -> dict[str, Any]:
    queue = list(entrypoints)
    visited: set[str] = set()
    graph: dict[str, list[str]] = {}
    missing_modules: dict[str, list[str]] = {}

    while queue:
        current = normalize_path_text(queue.pop(0))
        if current in visited:
            continue
        visited.add(current)

        if not (WORKSPACE / current).exists():
            graph[current] = []
            continue

        if not current.endswith(".py"):
            graph[current] = []
            continue

        imports, unresolved = parse_local_python_dependencies(current)
        graph[current] = imports
        if unresolved:
            missing_modules[current] = unresolved
        for item in imports:
            if item not in visited:
                queue.append(item)

    return {
        "required_python_files": sorted(path for path in visited if path.endswith(".py")),
        "import_graph": graph,
        "unresolved_local_modules": missing_modules,
    }


def build_runtime_requirement_set() -> dict[str, list[str]]:
    python_graph = collect_python_runtime_graph([item for item in RUNTIME_ENTRYPOINTS if item.endswith(".py")])
    required = sorted(
        set(RUNTIME_ENTRYPOINTS)
        | set(RUNTIME_STATIC_REQUIREMENTS)
        | set(DOC_RUNTIME_PATHS)
        | set(python_graph["required_python_files"])
    )
    return {
        "required_paths": required,
        "required_python_files": python_graph["required_python_files"],
        "import_graph": python_graph["import_graph"],
        "unresolved_local_modules": python_graph["unresolved_local_modules"],
    }


def audit_package_runtime() -> dict[str, Any]:
    manifest = load_package_manifest()
    file_rules = [str(item) for item in manifest.get("files", []) if isinstance(item, str)]
    runtime = build_runtime_requirement_set()
    metadata_issues = audit_manifest_metadata(manifest)
    review_policy_refresh_audit = run_review_policy_refresh_audit()
    historical_audit = run_historical_audit()

    missing_from_package = [
        path for path in runtime["required_paths"]
        if not path_matches_package_files(path, file_rules)
    ]

    refresh_candidates = int(review_policy_refresh_audit.get("missing_count", 0) or 0)
    refresh_failed = int(review_policy_refresh_audit.get("failed_count", 0) or 0)
    historical_issue_count = int(historical_audit.get("issue_count", 0) or 0)

    ready = (
        not missing_from_package
        and not runtime["unresolved_local_modules"]
        and not metadata_issues
        and refresh_candidates == 0
        and refresh_failed == 0
        and historical_issue_count == 0
    )
    human_summary = "发布包运行时覆盖检查通过。"
    if not ready:
        if metadata_issues and not missing_from_package and not runtime["unresolved_local_modules"] and refresh_candidates == 0:
            human_summary = "发布元数据检查发现占位值或缺失项。"
        elif historical_issue_count > 0:
            human_summary = "历史执行审计一致性检查未通过。"
        elif refresh_candidates > 0 or refresh_failed > 0:
            human_summary = "历史审核策略一致性检查未通过。"
        else:
            human_summary = "发布包运行时覆盖检查发现缺失依赖或发布元数据问题。"

    recommended_next_action = ""
    if missing_from_package:
        recommended_next_action = "更新 package.json 的 files，覆盖缺失的运行时路径。"
    elif runtime["unresolved_local_modules"]:
        recommended_next_action = "先修复未解析的本地 Python 模块，再进行发布。"
    elif metadata_issues:
        recommended_next_action = "先替换 homepage/bugs/repository 的占位元数据，再进行发布。"
    elif historical_issue_count > 0:
        recommended_next_action = "先运行 npm run cgc:audit-historical-audits，定位历史执行审计放置错误或旧仓库名残留问题。"
    elif refresh_candidates > 0:
        recommended_next_action = "先运行 npm run cgc:refresh-review-policy，刷新历史审核策略字段。"
    elif refresh_failed > 0:
        recommended_next_action = "先检查 refresh_codecgc_review_policy.py 的失败项，再进行发布。"

    return {
        "success": ready,
        "mode": "package-runtime-audit",
        "workspace": str(WORKSPACE),
        "summary": {
            "ready": ready,
            "human_summary": human_summary,
            "scope": "package.json 运行时覆盖与发布元数据就绪状态",
            "missing_from_package_files": missing_from_package,
            "unresolved_local_modules": runtime["unresolved_local_modules"],
            "manifest_metadata_issues": metadata_issues,
            "required_path_count": len(runtime["required_paths"]),
            "recommended_next_action": recommended_next_action,
            "review_policy_refresh_audit": review_policy_refresh_audit,
            "historical_audit": historical_audit,
        },
        "package_files_rules": file_rules,
        "manifest_metadata_issues": metadata_issues,
        "required_runtime_paths": runtime["required_paths"],
        "required_python_files": runtime["required_python_files"],
        "import_graph": runtime["import_graph"],
        "unresolved_local_modules": runtime["unresolved_local_modules"],
        "review_policy_refresh_audit": review_policy_refresh_audit,
        "historical_audit": historical_audit,
    }


def run_review_policy_refresh_audit() -> dict[str, Any]:
    command = [
        _PYTHON_CMD,
        str(WORKSPACE / "scripts" / "audit_codecgc_review_policy.py"),
        "--artifact-class",
        "all",
        "--format",
        "json",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        parsed = json.loads(completed.stdout)
        if not isinstance(parsed, dict):
            raise ValueError("Refresh audit did not return a JSON object.")
        return parsed
    except Exception as error:
        return {
            "success": False,
            "scan_target": "all",
            "candidate_count": -1,
            "failed_count": 1,
            "missing_count": -1,
            "missing": [{"artifact_path": "", "audit_path": "", "error": str(error)}],
        }


def run_historical_audit() -> dict[str, Any]:
    command = [
        _PYTHON_CMD,
        str(WORKSPACE / "scripts" / "audit_codecgc_historical_audits.py"),
        "--format",
        "json",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        parsed = json.loads(completed.stdout)
        if not isinstance(parsed, dict):
            raise ValueError("Historical audit did not return a JSON object.")
        return parsed
    except Exception as error:
        return {
            "success": False,
            "scanned": -1,
            "issue_count": 1,
            "issues": [{"path": "", "problem": "audit-execution-failed", "detail": str(error)}],
        }


def build_summary_lines(result: dict[str, Any]) -> str:
    summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
    missing = summary.get("missing_from_package_files", [])
    unresolved = summary.get("unresolved_local_modules", {})
    metadata_issues = summary.get("manifest_metadata_issues", [])
    refresh_audit = summary.get("review_policy_refresh_audit", {}) if isinstance(summary.get("review_policy_refresh_audit"), dict) else {}
    historical_audit = summary.get("historical_audit", {}) if isinstance(summary.get("historical_audit"), dict) else {}
    lines = [
        "CodeCGC 发布包审计",
        f"- 工作区: {result.get('workspace', '')}",
        f"- 范围: {summary.get('scope', '')}",
        f"- 就绪: {'是' if summary.get('ready') else '否'}",
        f"- 摘要: {summary.get('human_summary', '')}",
        f"- 必需路径数: {summary.get('required_path_count', 0)}",
        f"- package.json files 缺失项: {', '.join(str(item) for item in missing) or '无'}",
        f"- 历史执行审计问题数: {historical_audit.get('issue_count', 0)}",
        f"- 审核策略待刷新项: {refresh_audit.get('missing_count', 0)}",
        f"- 审核策略刷新失败项: {refresh_audit.get('failed_count', 0)}",
    ]
    if isinstance(historical_audit.get("issues"), list):
        for item in historical_audit["issues"]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- 历史执行审计问题 {item.get('problem', '')}: {item.get('path', '')} ({item.get('detail', '')})"
            )
    if unresolved:
        for source, modules in unresolved.items():
            if not isinstance(modules, list):
                continue
            lines.append(f"- 未解析本地模块 {source}: {', '.join(str(item) for item in modules) or '无'}")
    if isinstance(metadata_issues, list) and metadata_issues:
        for item in metadata_issues:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- 元数据 {item.get('field', '')}: {item.get('problem', '')} ({item.get('detail', '')})"
            )
    next_action = str(summary.get("recommended_next_action", "")).strip()
    next_actions = [next_action] if next_action else []
    return render_summary_block("CodeCGC 发布包审计", lines[1:], next_actions)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit whether package.json files cover CodeCGC runtime dependencies.")
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="summary",
        help="Output format. Summary is the default product-facing mode; use json for debugging or automation.",
    )
    args = parser.parse_args()

    result = audit_package_runtime()
    if args.format == "summary":
        print(build_summary_lines(result))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
