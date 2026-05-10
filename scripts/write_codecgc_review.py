import argparse
import json
import sys
from pathlib import Path
from typing import Any

from codecgc_artifact_roots import flow_root
from codecgc_artifact_roots import normalize_artifact_class
from codecgc_console_io import configure_utf8_stdio
from codecgc_console_io import print_json
from codecgc_path_contract import normalize_persisted_project_path
from codecgc_path_contract import resolve_project_path
from codecgc_review_control import ACTION_KIND_LABELS
from codecgc_review_control import FALLBACK_STAGE_LABELS
from codecgc_review_control import display_policy_reason
from codecgc_review_control import evaluate_review
from codecgc_step_control import update_step_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="把 CodeCGC 审核结果回写到功能验收或问题修复说明产物中。"
    )
    parser.add_argument(
        "--audit-file",
        required=True,
        help="执行审计 JSON 文件路径。",
    )
    parser.add_argument(
        "--decision",
        choices=["accepted", "changes-requested"],
        required=True,
        help="审核决策。",
    )
    parser.add_argument(
        "--risk",
        action="append",
        default=[],
        help="可选：补充剩余风险说明。",
    )
    parser.add_argument(
        "--next-step",
        default="",
        help="可选：未通过或未完成时的下一步说明。",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="允许覆盖已有的非 TODO 审核内容。",
    )
    return parser


def load_json(path: Path) -> dict[str, Any]:
    path = resolve_project_path(path)
    if not path.exists():
        raise FileNotFoundError(f"未找到审计文件：{path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("审计文件必须包含一个 JSON 对象。")
    return data


def resolve_artifact_path(audit: dict[str, Any]) -> tuple[str, Path]:
    source = audit.get("source")
    if not isinstance(source, dict):
        raise ValueError("审计文件缺少有效的 source 区块。")

    artifact_type = str(source.get("artifact_type", ""))
    artifact_class = normalize_artifact_class(str(source.get("artifact_class", "product")))
    artifact_slug = str(source.get("artifact_slug", ""))
    if not artifact_type or not artifact_slug:
        raise ValueError("审计 source 缺少 artifact_type 或 artifact_slug。")

    if artifact_type == "feature":
        base_slug = artifact_slug[11:] if len(artifact_slug) > 11 and artifact_slug[4] == "-" else artifact_slug
        return artifact_type, flow_root("feature", artifact_class) / artifact_slug / f"{base_slug}-acceptance.md"

    if artifact_type == "issue":
        base_slug = artifact_slug[11:] if len(artifact_slug) > 11 and artifact_slug[4] == "-" else artifact_slug
        return artifact_type, flow_root("issue", artifact_class) / artifact_slug / f"{base_slug}-fix-note.md"

    raise ValueError(f"不支持的产物类型：{artifact_type}")


def resolve_checklist_path_from_audit(audit: dict[str, Any]) -> Path:
    source = audit.get("source")
    if not isinstance(source, dict):
        raise ValueError("审计文件缺少有效的 source 区块。")
    artifact_file = str(source.get("artifact_file", ""))
    if not artifact_file:
        raise ValueError("审计 source 缺少 artifact_file。")
    return resolve_project_path(artifact_file)


def resolve_step_number_from_audit(audit: dict[str, Any]) -> int:
    source = audit.get("source")
    if not isinstance(source, dict):
        raise ValueError("审计文件缺少有效的 source 区块。")
    step_number = int(source.get("step_number", 0))
    if step_number < 1:
        raise ValueError("审计 source 缺少有效的 step_number。")
    return step_number


def extract_review_values(audit: dict[str, Any], decision: str, risks: list[str], next_step: str) -> dict[str, str]:
    return evaluate_review(audit, decision, risks, next_step)


def ensure_overwrite_allowed(text: str, force: bool) -> None:
    if force:
        return
    if "TODO" not in text:
        raise ValueError("目标产物已经包含非 TODO 审核内容。如需覆盖，请使用 --force。")


def render_review_decision(value: str) -> str:
    return {
        "accepted": "通过",
        "changes-requested": "需修改",
    }.get(value.strip(), value.strip() or "未知")


def render_action_kind(value: str) -> str:
    cleaned = value.strip()
    return ACTION_KIND_LABELS.get(cleaned, cleaned or "未知")


def render_fallback_stage(value: str) -> str:
    cleaned = value.strip()
    return FALLBACK_STAGE_LABELS.get(cleaned, cleaned or "未知")


def render_feature_acceptance(original: str, values: dict[str, str]) -> str:
    frontmatter, body = split_frontmatter(original)
    title = extract_title(body)
    return "\n".join(
        [
            frontmatter.strip(),
            "",
            title,
            "",
            "## 1. 范围检查",
            "",
            values["scope_check"],
            "",
            "## 2. 执行器检查",
            "",
            values["executor_check"],
            "",
            "## 3. 验证结果",
            "",
            values["verification"],
            "",
            "## 4. 剩余风险",
            "",
            values["remaining_risk"],
            "",
            "## 5. 审核结论",
            "",
            f"- 审核结果: {render_review_decision(str(values['final_decision']))}",
            f"- 审核 task_id: {values['reviewed_task_id'] or '未知'}",
            f"- 审核步骤序号: {values['reviewed_step_number'] or '未知'}",
            f"- 审核动作类型: {render_action_kind(str(values.get('recommended_action_kind', '')))}",
            f"- 审核回退阶段: {render_fallback_stage(str(values.get('fallback_stage', '')))}",
            f"- 审核策略原因: {display_policy_reason(str(values.get('policy_reason', '')))}",
            f"- 下一步: {values['next_step']}",
            "",
        ]
    )


def render_issue_fix_note(original: str, values: dict[str, str]) -> str:
    frontmatter, body = split_frontmatter(original)
    title = extract_title(body)
    return "\n".join(
        [
            frontmatter.strip(),
            "",
            title,
            "",
            "## 1. 已应用修复",
            "",
            values["verification"],
            "",
            "## 2. 验证结果",
            "",
            values["scope_check"],
            "",
            "## 3. 执行器检查",
            "",
            values["executor_check"],
            "",
            "## 4. 剩余风险",
            "",
            values["remaining_risk"],
            "",
            "## 5. 审核结论",
            "",
            f"- 审核结果: {render_review_decision(str(values['final_decision']))}",
            f"- 审核 task_id: {values['reviewed_task_id'] or '未知'}",
            f"- 审核步骤序号: {values['reviewed_step_number'] or '未知'}",
            f"- 审核动作类型: {render_action_kind(str(values.get('recommended_action_kind', '')))}",
            f"- 审核回退阶段: {render_fallback_stage(str(values.get('fallback_stage', '')))}",
            f"- 审核策略原因: {display_policy_reason(str(values.get('policy_reason', '')))}",
            f"- 下一步: {values['next_step']}",
            "",
        ]
    )


def split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    end = text.find("\n---\n", 4)
    if end == -1:
        return "", text
    return text[: end + 5], text[end + 5 :].lstrip("\n")


def extract_title(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line
    return "# 审核结果"


def write_review(audit_path: Path, decision: str, risks: list[str], next_step: str, force: bool) -> dict[str, str]:
    audit_path = resolve_project_path(audit_path)
    audit = load_json(audit_path)
    artifact_type, artifact_path = resolve_artifact_path(audit)
    checklist_path = resolve_checklist_path_from_audit(audit)
    step_number = resolve_step_number_from_audit(audit)
    if not artifact_path.exists():
        raise FileNotFoundError(f"未找到目标产物：{artifact_path}")

    original = artifact_path.read_text(encoding="utf-8")
    if not force:
        ensure_overwrite_allowed(original, force=False)

    values = extract_review_values(audit, decision, risks, next_step)
    if artifact_type == "feature":
        rendered = render_feature_acceptance(original, values)
    else:
        rendered = render_issue_fix_note(original, values)

    artifact_path.write_text(rendered, encoding="utf-8")
    update_step_status(
        checklist_path,
        step_number,
        "done" if values["final_decision"] == "accepted" else "pending",
    )
    return {
        "artifact_type": artifact_type,
        "artifact_path": normalize_persisted_project_path(artifact_path),
        "checklist_path": normalize_persisted_project_path(checklist_path),
        "step_number": str(step_number),
        "step_status": "done" if values["final_decision"] == "accepted" else "pending",
    }


def main() -> int:
    configure_utf8_stdio()
    parser = build_parser()
    args = parser.parse_args()

    try:
        result = write_review(
            audit_path=Path(args.audit_file),
            decision=args.decision,
            risks=args.risk,
            next_step=args.next_step,
            force=args.force,
        )
    except Exception as error:
        print_json(
            {
                "success": False,
                "error": str(error),
            },
            file=sys.stderr,
        )
        return 1

    print_json(
        {
            "success": True,
            **result,
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
