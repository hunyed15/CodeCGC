import argparse
import sys

from codecgc_command_surface import matches_command
from codecgc_command_surface import to_public_command
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_flow_control import build_execution_result
from codecgc_flow_control import build_not_ready_result
from codecgc_policy import load_policy
from codecgc_policy import validate_executor_target
from codecgc_routing_paths import resolve_active_routing_file
from codecgc_session_recovery import resolve_session_id_from_task
from codecgc_step_control import get_step_metadata
from codecgc_step_control import select_next_executable_step
from run_codecgc_flow_step import resolve_checklist_path
from codecgc_workflow_runtime import run_json_script


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CodeCGC 的高层问题修复入口：校验路由与步骤状态，并执行一个问题修复步骤。"
    )
    parser.add_argument("--slug", required=True)
    parser.add_argument("--step-number", type=int)
    parser.add_argument("--checklist-file", default="")
    parser.add_argument("--audit-root", default="")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--session-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--return-all-messages", action="store_true")
    return parser


def main() -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()

    route = run_json_script("route_codecgc_workflow.py", "--flow", "issue", "--slug", args.slug)
    if not matches_command(str(route.get("recommended_command", "")).strip(), "cgc-fix"):
        result = build_not_ready_result("issue", args.slug, route, "cgc-fix")
        print_json(result)
        return 1

    try:
        checklist_path = resolve_checklist_path("issue", args.slug, args.checklist_file)
        selected = (
            get_step_metadata(checklist_path, args.step_number)
            if args.step_number
            else select_next_executable_step(checklist_path)
        )
    except Exception as error:
        result = {
            "success": False,
            "flow": "issue",
            "slug": args.slug,
            "state": "not-ready",
            "failure_type": "workflow-state",
            "route": route,
            "error": str(error),
            "recommended_command": to_public_command("cgc-plan"),
            "next": "先处理仅规划步骤，或补齐缺失的可执行步骤，再进入 fix 执行。",
        }
        print_json(result)
        return 1

    try:
        policy_result = validate_executor_target(
            str(selected.get("kind", "")),
            [str(path) for path in selected.get("target_paths", [])],
            load_policy(resolve_active_routing_file()),
        )
        if not policy_result.get("allowed"):
            result = {
                "success": False,
                "flow": "issue",
                "slug": args.slug,
                "state": "not-ready",
                "failure_type": "policy",
                "route": route,
                "selected_step": selected,
                "policy": policy_result,
                "recommended_command": to_public_command("cgc-plan"),
                "next": "Adjust target_paths or split the task before fix execution.",
            }
            print_json(result)
            return 1
    except Exception as error:
        print_json({"success": False, "error": str(error), "failure_type": "policy"}, file=sys.stderr)
        return 1

    effective_session_id = args.session_id.strip()
    if not effective_session_id:
        effective_session_id = resolve_session_id_from_task(
            str(selected.get("task_id", "")).strip(),
            str(route.get("artifact_class", "")).strip() or "product",
        )

    command_args = [
        "--flow",
        "issue",
        "--slug",
        args.slug,
        "--step-number",
        str(selected["step_number"]),
        "--timeout-seconds",
        str(args.timeout_seconds),
    ]
    if args.checklist_file:
        command_args.extend(["--checklist-file", args.checklist_file])
    if args.audit_root:
        command_args.extend(["--audit-root", args.audit_root])
    if effective_session_id:
        command_args.extend(["--session-id", effective_session_id])
    if args.dry_run:
        command_args.append("--dry-run")
    if args.return_all_messages:
        command_args.append("--return-all-messages")

    execution = run_json_script("run_codecgc_flow_step.py", *command_args)
    result = build_execution_result(flow="issue", slug=args.slug, route=route, execution=execution)
    result["selected_step"] = selected
    result["reused_session_id"] = effective_session_id
    print_json(result)
    if result.get("success") or str(result.get("state", "")).strip() == "executed-dry-run":
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
