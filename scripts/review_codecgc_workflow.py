import argparse
import sys
from pathlib import Path

from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_path_contract import normalize_persisted_project_path
from codecgc_path_contract import resolve_project_path
from codecgc_review_control import evaluate_review
from write_codecgc_review import load_json
from write_codecgc_review import render_review_decision
from write_codecgc_review import write_review


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CodeCGC 的高层审核入口：读取 audit、生成审核结论并回写到工作流产物。"
    )
    parser.add_argument("--audit-file", required=True, help="执行审计 JSON 文件路径。")
    parser.add_argument(
        "--decision",
        required=True,
        choices=["accepted", "changes-requested"],
        help="请求的审核决策：accepted 表示希望通过，changes-requested 表示要求修改。",
    )
    parser.add_argument("--risk", action="append", default=[], help="可选：补充剩余风险说明。")
    parser.add_argument("--next-step", default="", help="可选：补充建议的下一步说明。")
    parser.add_argument("--force", action="store_true", help="允许覆盖已有审核内容。")
    return parser


def main() -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()

    try:
        audit_file = resolve_project_path(args.audit_file)
        audit = load_json(audit_file)
        values = evaluate_review(audit, args.decision, args.risk, args.next_step)
        writeback = write_review(
            audit_path=audit_file,
            decision=args.decision,
            risks=args.risk,
            next_step=args.next_step,
            force=args.force,
        )
        result = {
            "success": True,
            "audit_file": normalize_persisted_project_path(audit_file),
            "requested_decision": args.decision,
            "final_decision": values["final_decision"],
            "accepted": values["accepted"],
            "review_state": values["review_state"],
            "recommended_command": values["recommended_command"],
            "recommended_action_kind": values.get("recommended_action_kind", ""),
            "fallback_stage": values.get("fallback_stage", ""),
            "policy_reason": values.get("policy_reason", ""),
            "risk_classes": values.get("risk_classes", []),
            "evidence_confidence": values.get("evidence_confidence", ""),
            "scope_check": values["scope_check"],
            "executor_check": values["executor_check"],
            "verification": values["verification"],
            "remaining_risk": values["remaining_risk"],
            "next_step": values["next_step"],
            "failure_reasons": values["failure_reasons"],
            "writeback": writeback,
        }
        result["summary"] = {
            "human_summary": (
                f"本次审核已完成，最终决策为{render_review_decision(str(values['final_decision']))}。"
                if str(values["final_decision"]).strip()
                else "本次审核已完成。"
            ),
            "recommended_command": values["recommended_command"],
            "next": values["next_step"],
            "review_state": values["review_state"],
            "recommended_action_kind": values.get("recommended_action_kind", ""),
            "fallback_stage": values.get("fallback_stage", ""),
            "accepted": values["accepted"],
        }
    except Exception as error:
        print_json({"success": False, "error": str(error)}, file=sys.stderr)
        return 1

    print_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
