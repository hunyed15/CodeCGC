from __future__ import annotations

from typing import Any

from codecgc_command_surface import to_public_command

EXPECTED_TOOL_BY_TARGET = {
    "frontend": "implement_frontend_task",
    "backend": "implement_backend_task",
}

EXECUTE_COMMAND_BY_ARTIFACT = {
    "feature": "cgc-build",
    "issue": "cgc-fix",
}

BOOLEAN_TEXT = {
    True: "是",
    False: "否",
}

TARGET_LABELS = {
    "frontend": "前端",
    "backend": "后端",
}

TOOL_LABELS = {
    "implement_frontend_task": "前端执行器 / Gemini",
    "implement_backend_task": "后端执行器 / Codex",
}

MODE_LABELS = {
    "dry-run": "仅预演",
    "execute": "真实执行",
}

OUTCOME_LABELS = {
    "done": "完成",
    "blocked": "受阻",
    "failed": "失败",
}

EVIDENCE_SOURCE_LABELS = {
    "audit-result": "执行审计结果",
    "workspace-diff": "工作区文件变更",
    "workspace-snapshot": "工作区快照差异",
    "workspace-diff-snapshot": "工作区快照差异",
    "workspace-unified-diff-snapshot": "工作区统一 diff 证据",
}

RISK_LABELS = {
    "ownership-mismatch": "归属不匹配",
    "out-of-scope-diff": "存在范围外变更",
    "scope-mismatch": "范围不匹配",
    "execution-not-performed": "未真实执行",
    "executor-outcome-failed": "执行器结果失败",
    "no-in-scope-diff": "未观察到范围内变更",
    "missing-change-evidence": "缺少变更证据",
    "reported-without-local-proof": "只有执行器上报，缺少本地证据",
    "local-diff-unreported": "本地变更未被执行器上报",
    "reported-local-mismatch": "执行器上报与本地证据不一致",
    "diff-proof-missing": "缺少可核验的 diff 片段",
    "diff-proof-nontext": "仅有非文本或不可读 diff 证据",
}

EVIDENCE_CONFIDENCE_LABELS = {
    "local-diff-out-of-scope": "本地 diff 存在范围外变更",
    "local-diff-verified": "本地 diff 已验证",
    "local-nontext-diff-verified": "本地非文本 diff 已验证",
    "local-diff-partial-match": "本地 diff 与上报部分匹配",
    "local-diff-mismatch": "本地 diff 与上报不匹配",
    "local-diff-unreported": "本地 diff 未被上报",
    "reported-without-local-proof": "只有上报，缺少本地证据",
    "no-local-diff": "未观察到本地 diff",
    "self-report-only": "仅执行器自报",
    "stronger-than-self-report": "本地证据强于执行器自报",
    "stronger-than-self-report-with-git-history": "本地证据已结合 git/history 增强",
    "unknown": "未知",
}

POLICY_REASON_LABELS = {
    "accepted-with-sufficient-evidence": "证据充分，允许通过",
    "planning-boundary-risk": "存在规划边界风险",
    "execution-not-performed": "尚未真实执行",
    "execution-evidence-risk": "执行证据存在风险",
    "unclassified-review-risk": "存在未分类的审核风险",
}

ACTION_KIND_LABELS = {
    "close-step": "关闭当前执行步骤",
    "repair-plan": "回到规划修正",
    "execute-for-real": "执行一次真实运行",
    "refine-and-rerun": "细化实现并重新执行",
    "re-evaluate": "重新评估当前执行步骤",
}

FALLBACK_STAGE_LABELS = {
    "closed": "已关闭",
    "planning": "规划阶段",
    "execution": "执行阶段",
    "review": "审核阶段",
}

DECISION_LABELS = {
    "accepted": "通过",
    "changes-requested": "需修改",
}


def normalize_path_text(path_text: str) -> str:
    return path_text.replace("\\", "/").strip()


def unique_lines(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def bool_text(value: bool) -> str:
    return BOOLEAN_TEXT[bool(value)]


def display_text(value: str, fallback: str = "未知") -> str:
    cleaned = value.strip()
    return cleaned or fallback


def display_csv(items: list[str], fallback: str = "无") -> str:
    cleaned = [item.strip() for item in items if item.strip()]
    return ", ".join(cleaned) if cleaned else fallback


def display_risk_classes(items: list[str]) -> str:
    cleaned = [RISK_LABELS.get(item, item) for item in items if item.strip()]
    return ", ".join(cleaned) if cleaned else "无"


def display_policy_reason(value: str) -> str:
    cleaned = value.strip()
    return POLICY_REASON_LABELS.get(cleaned, cleaned or "未知")


def display_decision(value: str) -> str:
    cleaned = value.strip()
    return DECISION_LABELS.get(cleaned, cleaned or "未知")


def display_evidence_confidence(value: str) -> str:
    cleaned = value.strip()
    return EVIDENCE_CONFIDENCE_LABELS.get(cleaned, cleaned or "未知")


def display_target(value: str) -> str:
    cleaned = value.strip()
    return TARGET_LABELS.get(cleaned, cleaned or "未知")


def display_tool_name(value: str) -> str:
    cleaned = value.strip()
    return TOOL_LABELS.get(cleaned, cleaned or "未知")


def display_mode(value: str) -> str:
    cleaned = value.strip()
    return MODE_LABELS.get(cleaned, cleaned or "未知")


def display_outcome(value: str) -> str:
    cleaned = value.strip()
    return OUTCOME_LABELS.get(cleaned, cleaned or "未知")


def display_evidence_source(value: str) -> str:
    cleaned = value.strip()
    return EVIDENCE_SOURCE_LABELS.get(cleaned, cleaned or "未知")


def classify_review_risk(
    *,
    ownership_ok: bool,
    scope_ok: bool,
    execution_performed: bool,
    success_ok: bool,
    change_evidence_ok: bool,
    evidence_alignment_ok: bool,
    local_evidence_available: bool,
    out_of_scope_changed_files: list[str],
    verified_changed_files: list[str],
    workspace_changed_files: list[str],
    reported_changed_files: list[str],
    diff_proof_strong: bool,
    diff_proof_nontext_only: bool,
) -> list[str]:
    risk_classes: list[str] = []

    if not ownership_ok:
        risk_classes.append("ownership-mismatch")
    if out_of_scope_changed_files:
        risk_classes.append("out-of-scope-diff")
    elif not scope_ok:
        risk_classes.append("scope-mismatch")
    if not execution_performed:
        risk_classes.append("execution-not-performed")
    if not success_ok:
        risk_classes.append("executor-outcome-failed")
    if local_evidence_available and workspace_changed_files and not verified_changed_files:
        risk_classes.append("no-in-scope-diff")
    elif not change_evidence_ok:
        risk_classes.append("missing-change-evidence")
    if local_evidence_available and verified_changed_files and not diff_proof_strong:
        if not diff_proof_nontext_only:
            risk_classes.append("diff-proof-missing")
    if not evidence_alignment_ok:
        if reported_changed_files and not workspace_changed_files:
            risk_classes.append("reported-without-local-proof")
        elif verified_changed_files and not reported_changed_files:
            risk_classes.append("local-diff-unreported")
        else:
            risk_classes.append("reported-local-mismatch")
    return risk_classes


def resolve_review_policy(
    *,
    final_decision: str,
    requested_decision: str,
    next_step: str,
    execute_command: str,
    risk_classes: list[str],
) -> dict[str, str]:
    if final_decision == "accepted":
        return {
            "recommended_command": "",
            "resolved_next_step": next_step or "当前执行步骤已满足关闭条件，可以结束本轮工作流。",
            "review_state": "accepted",
            "action_kind": "close-step",
            "fallback_stage": "closed",
            "policy_reason": "accepted-with-sufficient-evidence",
        }

    planning_risks = {"ownership-mismatch", "out-of-scope-diff", "scope-mismatch"}
    execution_retry_risks = {
        "execution-not-performed",
        "executor-outcome-failed",
        "missing-change-evidence",
        "diff-proof-missing",
        "no-in-scope-diff",
        "reported-without-local-proof",
        "local-diff-unreported",
        "reported-local-mismatch",
    }

    if any(risk in planning_risks for risk in risk_classes):
        return {
            "recommended_command": "cgc-plan",
            "resolved_next_step": next_step or "请先回到规划阶段，修正执行归属或目标路径范围后，再进入下一轮执行。",
            "review_state": "returned-to-planning",
            "action_kind": "repair-plan",
            "fallback_stage": "planning",
            "policy_reason": "planning-boundary-risk",
        }

    if "execution-not-performed" in risk_classes:
        return {
            "recommended_command": execute_command,
            "resolved_next_step": next_step or "请对同一范围的当前执行步骤进行一次真实执行，再重新申请审核。",
            "review_state": "changes-requested",
            "action_kind": "execute-for-real",
            "fallback_stage": "execution",
            "policy_reason": "execution-not-performed",
        }

    if any(risk in execution_retry_risks for risk in risk_classes):
        return {
            "recommended_command": execute_command,
            "resolved_next_step": next_step or "请细化当前实现，并在同一范围内重新执行当前步骤后，再重新申请审核。",
            "review_state": "changes-requested",
            "action_kind": "refine-and-rerun",
            "fallback_stage": "execution",
            "policy_reason": "execution-evidence-risk",
        }

    return {
        "recommended_command": execute_command if requested_decision == "accepted" else "",
        "resolved_next_step": next_step or "请重新评估当前执行步骤，确认后再重新申请审核。",
        "review_state": "changes-requested",
        "action_kind": "re-evaluate",
        "fallback_stage": "review",
        "policy_reason": "unclassified-review-risk",
    }


def classify_evidence_confidence(
    *,
    evidence_source: str,
    reported_changed_files: list[str],
    workspace_changed_files: list[str],
    verified_changed_files: list[str],
    out_of_scope_changed_files: list[str],
    file_diffs: list[dict[str, Any]],
) -> tuple[str, bool, bool]:
    local_evidence_available = bool(
        workspace_changed_files or verified_changed_files or out_of_scope_changed_files or file_diffs
    )
    reported = set(reported_changed_files)
    observed = set(workspace_changed_files)
    verified = set(verified_changed_files)

    if local_evidence_available:
        diff_kinds = {
            str(item.get("diff_kind", "")).strip()
            for item in file_diffs
            if isinstance(item, dict)
        }
        if out_of_scope_changed_files:
            return "local-diff-out-of-scope", False, True
        if verified and diff_kinds and diff_kinds <= {"binary-or-unreadable"}:
            return "local-nontext-diff-verified", True, True
        if verified and reported:
            if verified == reported:
                return "local-diff-verified", True, True
            if verified.issubset(reported) or reported.issubset(verified):
                return "local-diff-partial-match", True, True
            return "local-diff-mismatch", False, True
        if verified and not reported:
            return "local-diff-unreported", False, True
        if reported and not observed:
            return "reported-without-local-proof", False, True
        if observed and not verified:
            return "local-diff-out-of-scope", False, True
        return "no-local-diff", False, True

    if evidence_source == "audit-result" and reported:
        return "self-report-only", True, False
    return "no-local-diff", False, False


def evaluate_review(audit: dict[str, Any], requested_decision: str, risks: list[str], next_step: str) -> dict[str, Any]:
    result = audit.get("result", {}) if isinstance(audit.get("result"), dict) else {}
    source = audit.get("source", {}) if isinstance(audit.get("source"), dict) else {}
    file_evidence = audit.get("file_evidence", {}) if isinstance(audit.get("file_evidence"), dict) else {}

    artifact_type = str(source.get("artifact_type", ""))
    execute_command = EXECUTE_COMMAND_BY_ARTIFACT.get(artifact_type, "")
    target = str(audit.get("target", ""))
    tool_name = str(audit.get("tool_name", ""))
    mode = str(audit.get("mode", ""))
    outcome = str(result.get("outcome", ""))
    success = bool(result.get("success"))

    target_paths = [normalize_path_text(str(path)) for path in audit.get("target_paths", [])]
    changed_files = [normalize_path_text(str(path)) for path in result.get("changed_files", [])]
    workspace_changed_files = [
        normalize_path_text(str(path)) for path in file_evidence.get("workspace_changed_files", [])
    ]
    verified_changed_files = [
        normalize_path_text(str(path)) for path in file_evidence.get("verified_changed_files", [])
    ]
    out_of_scope_changed_files = [
        normalize_path_text(str(path)) for path in file_evidence.get("out_of_scope_changed_files", [])
    ]
    file_diffs = file_evidence.get("file_diffs", []) if isinstance(file_evidence.get("file_diffs"), list) else []
    git_evidence = file_evidence.get("git_evidence", {}) if isinstance(file_evidence.get("git_evidence"), dict) else {}
    policy_checks = [str(item) for item in result.get("policy_checks", [])]
    result_risks = [str(item) for item in result.get("risks", [])]
    acceptance_criteria = [str(item) for item in audit.get("acceptance_criteria", [])]
    evidence_source = str(file_evidence.get("evidence_source", "audit-result"))
    stored_evidence_confidence = str(file_evidence.get("evidence_confidence", "unknown"))
    git_repository_detected = bool(git_evidence.get("git_repository_detected"))
    git_history_available = bool(git_evidence.get("history_available"))
    git_status = str(git_evidence.get("status", "")).strip() or "unknown"
    tracked_changed_files = [
        normalize_path_text(str(path)) for path in git_evidence.get("tracked_changed_files", [])
    ]
    untracked_changed_files = [
        normalize_path_text(str(path)) for path in git_evidence.get("untracked_changed_files", [])
    ]
    git_changed_files = git_evidence.get("git_changed_files", []) if isinstance(git_evidence.get("git_changed_files"), list) else []

    diff_excerpt_lines: list[str] = []
    in_scope_diff_items: list[dict[str, Any]] = []
    for item in file_diffs:
        if not isinstance(item, dict):
            continue
        path_text = str(item.get("path", "")).strip() or "未知文件"
        scope_match_kind = str(item.get("scope_match_kind", "")).strip() or "unknown"
        diff_excerpt = str(item.get("diff_excerpt", "")).strip()
        if bool(item.get("in_scope")):
            in_scope_diff_items.append(item)
        if diff_excerpt:
            diff_excerpt_lines.append(
                f"[{path_text} | {scope_match_kind}]\n{diff_excerpt}"
            )

    evidence_confidence, evidence_alignment_ok, local_evidence_available = classify_evidence_confidence(
        evidence_source=evidence_source,
        reported_changed_files=changed_files,
        workspace_changed_files=workspace_changed_files,
        verified_changed_files=verified_changed_files,
        out_of_scope_changed_files=out_of_scope_changed_files,
        file_diffs=file_diffs,
    )
    if stored_evidence_confidence not in {"", "unknown"} and evidence_confidence == "self-report-only":
        evidence_confidence = stored_evidence_confidence

    expected_tool = EXPECTED_TOOL_BY_TARGET.get(target, "")
    ownership_ok = bool(expected_tool) and tool_name == expected_tool
    if local_evidence_available:
        effective_changed_files = verified_changed_files
        scope_ok = not out_of_scope_changed_files
    else:
        effective_changed_files = changed_files
        scope_ok = all(path in target_paths for path in changed_files)
    diff_proof_strong = bool(
        [
            item for item in in_scope_diff_items
            if str(item.get("diff_kind", "")).strip() == "unified-text-diff"
            and int(item.get("changed_line_count", 0) or 0) > 0
        ]
    )
    diff_proof_nontext_only = bool(in_scope_diff_items) and all(
        str(item.get("diff_kind", "")).strip() == "binary-or-unreadable"
        for item in in_scope_diff_items
    )
    execution_performed = mode != "dry-run" and "dry_run_only" not in policy_checks and "execution_not_performed" not in result_risks
    success_ok = success and outcome == "done"

    failure_reasons: list[str] = []
    if not ownership_ok:
        failure_reasons.append("执行器归属校验未通过")
    if not scope_ok:
        failure_reasons.append("变更文件超出了 target_paths 范围")
    if local_evidence_available and not effective_changed_files:
        failure_reasons.append("未观察到已验证的范围内文件变更")
    if local_evidence_available and effective_changed_files and not diff_proof_strong:
        if not diff_proof_nontext_only:
            failure_reasons.append("当前只有文件级变化，缺少可核验的统一 diff 片段")
    if not evidence_alignment_ok:
        failure_reasons.append("执行器自报结果与本地文件证据不一致")
    if not execution_performed:
        failure_reasons.append("本次仅进行了预演执行，或尚未发生真实执行")
    if not success_ok:
        failure_reasons.append("执行器未返回成功完成结果")

    change_evidence_ok = bool(effective_changed_files) or not bool(target_paths)
    risk_classes = classify_review_risk(
        ownership_ok=ownership_ok,
        scope_ok=scope_ok,
        execution_performed=execution_performed,
        success_ok=success_ok,
        change_evidence_ok=change_evidence_ok,
        evidence_alignment_ok=evidence_alignment_ok,
        local_evidence_available=local_evidence_available,
        out_of_scope_changed_files=out_of_scope_changed_files,
        verified_changed_files=effective_changed_files,
        workspace_changed_files=workspace_changed_files,
        reported_changed_files=changed_files,
        diff_proof_strong=diff_proof_strong,
        diff_proof_nontext_only=diff_proof_nontext_only,
    )
    ready_for_acceptance = (
        ownership_ok
        and scope_ok
        and execution_performed
        and success_ok
        and change_evidence_ok
        and evidence_alignment_ok
        and (not local_evidence_available or diff_proof_strong or diff_proof_nontext_only)
    )
    final_decision = "accepted" if requested_decision == "accepted" and ready_for_acceptance else "changes-requested"
    resolution = resolve_review_policy(
        final_decision=final_decision,
        requested_decision=requested_decision,
        next_step=next_step,
        execute_command=execute_command,
        risk_classes=risk_classes,
    )
    recommended_command = resolution["recommended_command"]
    resolved_next_step = resolution["resolved_next_step"]
    review_state = resolution["review_state"]

    merged_risks = unique_lines([*risks, *result_risks, *failure_reasons])

    scope_lines = [
        f"请求决策: {display_decision(requested_decision)}",
        f"最终决策: {display_decision(final_decision)}",
        f"执行结果: {display_outcome(outcome)}",
        f"证据来源: {display_evidence_source(evidence_source)}",
        f"风险分类: {display_risk_classes(risk_classes)}",
        f"回退阶段: {FALLBACK_STAGE_LABELS.get(resolution['fallback_stage'], resolution['fallback_stage'])}",
        f"策略原因: {display_policy_reason(resolution['policy_reason'])}",
        f"范围是否满足: {bool_text(scope_ok)}",
        f"变更文件是否落在 target_paths 内: {bool_text(scope_ok)}",
    ]

    executor_lines = [
        f"执行器目标: {display_target(target)}",
        f"预期工具: {display_tool_name(expected_tool)}",
        f"实际工具: {display_tool_name(tool_name)}",
        f"归属是否满足: {bool_text(ownership_ok)}",
        f"执行模式: {display_mode(mode)}",
        f"是否真实执行: {bool_text(execution_performed)}",
        f"策略检查项: {display_csv(policy_checks)}",
    ]

    verification_lines = [
        f"摘要: {display_text(str(result.get('summary', '') or ''), '无')}",
        f"证据置信度: {display_evidence_confidence(evidence_confidence)}",
        f"diff 证据是否足够强: {bool_text(diff_proof_strong)}",
        f"是否属于非文本 diff 证据: {bool_text(diff_proof_nontext_only)}",
        f"是否有本地证据: {bool_text(local_evidence_available)}",
        f"是否检测到 git 仓库: {bool_text(git_repository_detected)}",
        f"git/history 证据是否可用: {bool_text(git_history_available)}",
        f"git 证据状态: {display_text(git_status, '无')}",
        f"执行器上报与本地证据是否一致: {bool_text(evidence_alignment_ok)}",
        f"执行器上报的变更文件: {display_csv(changed_files)}",
        f"工作区变更文件: {display_csv(workspace_changed_files)}",
        f"已验证的范围内变更文件: {display_csv(effective_changed_files)}",
        f"范围外变更文件: {display_csv(out_of_scope_changed_files)}",
        f"git 已跟踪变更文件: {display_csv(tracked_changed_files)}",
        f"git 未跟踪变更文件: {display_csv(untracked_changed_files)}",
        "git 历史摘要: "
        + (
            " | ".join(
                f"{item.get('path', '未知')}:{'tracked' if item.get('tracked') else 'untracked'}"
                + (
                    f":{str(item.get('last_commit_hash', ''))[:10]}"
                    if str(item.get("last_commit_hash", "")).strip()
                    else ""
                )
                + (
                    f":{str(item.get('last_commit_subject', '')).strip()}"
                    if str(item.get("last_commit_subject", "")).strip()
                    else ""
                )
                for item in git_changed_files
                if isinstance(item, dict)
            )
            or "无"
        ),
        "观测到的文件 diff: "
        + (
            " | ".join(
                f"{item.get('path', '未知')}:{item.get('change_type', 'changed')}:{item.get('scope_match_kind', 'unknown')}"
                for item in file_diffs
            )
            or "无"
        ),
        "diff 证据类型: "
        + (
            " | ".join(
                f"{item.get('path', '未知')}:{item.get('diff_kind', 'unknown')}:{item.get('changed_line_count', 0)}"
                for item in file_diffs
            )
            or "无"
        ),
        "观测到的统一 diff 片段: "
        + ("\n\n".join(diff_excerpt_lines) if diff_excerpt_lines else "无"),
        f"验收条件: {' | '.join(acceptance_criteria) or '无'}",
    ]

    return {
        "requested_decision": requested_decision,
        "final_decision": final_decision,
        "accepted": final_decision == "accepted",
        "review_state": review_state,
        "recommended_command": to_public_command(recommended_command),
        "next_step": resolved_next_step,
        "recommended_action_kind": resolution["action_kind"],
        "fallback_stage": resolution["fallback_stage"],
        "policy_reason": resolution["policy_reason"],
        "reviewed_task_id": str(result.get("task_id", "")),
        "reviewed_step_number": int(source.get("step_number", 0) or 0),
        "scope_check": "\n".join(f"- {line}" for line in scope_lines),
        "executor_check": "\n".join(f"- {line}" for line in executor_lines),
        "verification": "\n".join(f"- {line}" for line in verification_lines),
        "remaining_risk": "\n".join(f"- {line}" for line in merged_risks) if merged_risks else "- 无",
        "failure_reasons": failure_reasons,
        "risk_classes": risk_classes,
        "evidence_confidence": evidence_confidence,
    }
