import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from codecgc_artifact_roots import discover_flow_directory
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_runtime_paths import PACKAGE_ROOT
from codecgc_runtime_paths import PROJECT_ROOT

WORKSPACE = PACKAGE_ROOT
PROJECT_WORKSPACE = PROJECT_ROOT


def resolve_checklist_path(flow: str, slug: str, checklist_file: str) -> Path:
    if checklist_file:
        path = Path(checklist_file)
        if not path.is_absolute():
            path = (PROJECT_WORKSPACE / path).resolve()
        return path

    discovered = discover_flow_directory(flow, slug, "auto")
    if not discovered:
        raise FileNotFoundError(f"Workflow directory not found for {flow}:{slug}. Create the artifacts first.")
    _, flow_root = discovered

    artifact_slug = slug
    if re.match(r"^\d{4}-\d{2}-\d{2}-", slug):
        artifact_slug = slug[11:]

    candidate_names = [
        f"{slug}-checklist.yaml",
        f"{artifact_slug}-checklist.yaml",
        "checklist.yaml",
        f"{slug}-fix.yaml",
        f"{artifact_slug}-fix.yaml",
        "fix-checklist.yaml",
    ]

    artifact_dir = flow_root
    for name in candidate_names:
        candidate = artifact_dir / name
        if candidate.exists():
            return candidate

    found = sorted(str(path.relative_to(PROJECT_WORKSPACE)) for path in artifact_dir.glob("*.yaml")) if artifact_dir.exists() else []
    raise FileNotFoundError(
        "No checklist-like YAML file found for "
        f"{flow}:{slug}. Looked for {candidate_names}. Found: {found or 'none'}."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one CodeCGC feature or issue step via the standard execution wrapper."
    )
    parser.add_argument(
        "--flow",
        required=True,
        choices=["feature", "issue"],
        help="Workflow type.",
    )
    parser.add_argument(
        "--slug",
        required=True,
        help="Feature or issue slug directory name.",
    )
    parser.add_argument(
        "--step-number",
        type=int,
        required=True,
        help="1-based step number inside the checklist-like YAML file.",
    )
    parser.add_argument(
        "--checklist-file",
        default="",
        help="Optional explicit checklist or fix YAML path.",
    )
    parser.add_argument(
        "--audit-root",
        default="",
        help="Optional explicit audit output directory.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
        help="Execution timeout in seconds.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the step payload and audit only.",
    )
    parser.add_argument(
        "--return-all-messages",
        action="store_true",
        help="Request full executor event logs.",
    )
    parser.add_argument(
        "--session-id",
        default="",
        help="Optional MCP session id used to resume a previous executor conversation.",
    )
    return parser


def main() -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()

    try:
        checklist_path = resolve_checklist_path(args.flow, args.slug, args.checklist_file)
    except Exception as error:
        print_json(
            {
                "success": False,
                "error": str(error),
            },
            file=sys.stderr,
        )
        return 1

    command = [
        sys.executable,
        str(WORKSPACE / "scripts" / "run_codecgc_task.py"),
        "--checklist-file",
        str(checklist_path),
        "--step-number",
        str(args.step_number),
        "--timeout-seconds",
        str(args.timeout_seconds),
    ]

    if args.audit_root:
        command.extend(["--audit-root", args.audit_root])
    if args.dry_run:
        command.append("--dry-run")
    if args.return_all_messages:
        command.append("--return-all-messages")
    if args.session_id.strip():
        command.extend(["--session-id", args.session_id.strip()])

    completed = subprocess.run(
        command,
        cwd=PROJECT_WORKSPACE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
