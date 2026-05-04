import json
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
CODECGC_ROOT = WORKSPACE / "codecgc"

SCAN_ROOTS = [
    CODECGC_ROOT / "features",
    CODECGC_ROOT / "issues",
    CODECGC_ROOT / "roadmap",
    CODECGC_ROOT / "fixtures",
    CODECGC_ROOT / "reference",
    CODECGC_ROOT / "requirements",
    CODECGC_ROOT / "architecture",
    CODECGC_ROOT / "compound",
]

EXACT_LINE_REPLACEMENTS = {
    "## 1. Goal": "## 1. 目标",
    "## 1. Initiative Goal": "## 1. 目标",
    "## 2. Context": "## 2. 背景",
    "## 3. In Scope": "## 3. 范围内",
    "## 4. Out Of Scope": "## 4. 范围外",
    "## 5. Dependencies And Assumptions": "## 5. 依赖与假设",
    "## 6. Execution Notes": "## 6. 执行说明",
    "## 7. Validation Plan": "## 7. 验证计划",
    "## 8. Rollback Plan": "## 8. 回退计划",
    "## 9. Open Questions": "## 9. 开放问题",
    "## 10. Planned Steps": "## 10. 计划步骤",
    "## 1. Symptom": "## 1. 现象",
    "## 2. Reproduction": "## 2. 复现方式",
    "## 3. Expected vs Actual": "## 3. 预期与实际",
    "## 5. Planned Steps": "## 5. 计划步骤",
    "## 1. Root Cause": "## 1. 根因",
    "## 2. Scope": "## 2. 范围",
    "## 3. Fix Options": "## 3. 修复方案",
    "## 4. Dependencies And Assumptions": "## 4. 依赖与假设",
    "## 5. Validation Plan": "## 5. 验证计划",
    "## 6. Rollback Plan": "## 6. 回退计划",
    "## 7. Open Questions": "## 7. 开放问题",
    "## 8. Planned Steps": "## 8. 计划步骤",
    "## 1. Scope Check": "## 1. 范围检查",
    "## 2. Executor Check": "## 2. 执行器检查",
    "## 3. Verification": "## 3. 验证结果",
    "## 4. Remaining Risk": "## 4. 剩余风险",
    "## 5. Review Decision": "## 5. 审核结论",
    "## 1. Applied Fix": "## 1. 已应用修复",
    "## 3. Why This Is Roadmap-Sized": "## 3. 为什么需要走 Roadmap",
    "## 4. Scope": "## 4. 范围",
    "## 5. Risks": "## 5. 风险",
    "## 1. Dependencies": "## 1. 依赖",
    "## 2. Assumptions": "## 2. 前提假设",
    "## 3. Validation Strategy": "## 3. 验证策略",
    "## 4. Rollback Strategy": "## 4. 回退策略",
    "## 5. Open Questions": "## 5. 开放问题",
    "## 5. Initialized Child Workflows": "## 5. 已初始化的子工作流",
    "## 6. Workflow Tracking": "## 6. 工作流跟踪",
    "## 7. Governance Source": "## 7. 治理来源",
    "## 5. Review Decision": "## 5. 审核结论",
    "## 4. Review Decision": "## 4. 审核结论",
}

EXACT_BULLET_REPLACEMENTS = {
    "- None yet.": "- 暂无。",
    "- None right now.": "- 当前无。",
    "- No child workflows have been registered yet.": "- 目前还没有登记子工作流。",
    "- accepted": "- 审核结果: 通过",
    "- changes-requested": "- 审核结果: 需修改",
}

EXACT_VALUE_REPLACEMENTS = {
    "to be split": "待拆分",
    "TODO/path": "待补路径",
    "none": "无",
    "unknown": "未知",
}

PREFIX_REPLACEMENTS = {
    "- Summary:": "- 摘要:",
    "- User goal:": "- 用户目标:",
    "- User story:": "- 用户故事:",
    "- Planned execution owner:": "- 计划执行归属:",
    "- Candidate target paths:": "- 候选目标路径:",
    "- Symptom:": "- 现象:",
    "- User impact:": "- 用户影响:",
    "- Suspected execution owner:": "- 预估执行归属:",
    "- Candidate affected paths:": "- 候选影响路径:",
    "- Current hypothesis owner:": "- 当前假设归属:",
    "- Root cause notes:": "- 根因说明:",
    "- Goal:": "- 目标:",
    "- User story or operator need:": "- 用户故事或操作者诉求:",
    "- Acceptance hint:": "- 验收提示:",
    "- Planning risk:": "- 规划风险:",
    "- Decision note:": "- 决策说明:",
    "- Routing note:": "- 路由说明:",
    "- Reviewed task_id:": "- 审核 task_id:",
    "- Reviewed step_number:": "- 审核 step_number:",
    "- 审核步骤序号:": "- 审核步骤序号:",
    "- Review action kind:": "- 审核动作类型:",
    "- 审核结果:": "- 审核结果:",
    "- Review fallback stage:": "- 审核回退阶段:",
    "- Review policy reason:": "- 审核策略原因:",
    "- Next step:": "- 下一步:",
    "Expected:": "预期:",
    "Actual:": "实际:",
    "Preferred scoped fix:": "首选定点修复:",
    "Rejected broader fix:": "明确不采用的更大范围修复:",
    "Dependencies:": "依赖:",
    "Assumptions:": "假设:",
    "Shared:": "共享范围:",
    "Unknown:": "未知范围:",
    "Requested decision:": "请求决策:",
    "Final decision:": "最终决策:",
    "Outcome:": "执行结果:",
    "Evidence source:": "证据来源:",
    "Risk classes:": "风险分类:",
    "Fallback stage:": "回退阶段:",
    "Policy reason:": "策略原因:",
    "Scope respected:": "范围是否满足:",
    "Changed files inside target_paths:": "变更文件是否落在 target_paths 内:",
    "Executor target:": "执行器目标:",
    "Expected tool:": "预期工具:",
    "Actual tool:": "实际工具:",
    "Ownership respected:": "归属是否满足:",
    "Execution mode:": "执行模式:",
    "Execution performed:": "是否真实执行:",
    "Policy checks:": "策略检查项:",
    "Summary:": "摘要:",
    "Evidence confidence:": "证据置信度:",
    "Local evidence available:": "是否有本地证据:",
    "Reported vs local evidence alignment:": "执行器上报与本地证据是否一致:",
    "Executor reported changed files:": "执行器上报的变更文件:",
    "Workspace changed files:": "工作区变更文件:",
    "Verified in-scope changed files:": "已验证的范围内变更文件:",
    "Out-of-scope changed files:": "范围外变更文件:",
    "Observed file diffs:": "观测到的文件 diff:",
    "Acceptance criteria:": "验收条件:",
    "Planning status:": "规划状态:",
    "Requested decision:": "请求决策:",
    "Final decision:": "最终决策:",
    "Execution mode:": "执行模式:",
    "Review action kind:": "审核动作类型:",
    "Review fallback stage:": "审核回退阶段:",
    "Review policy reason:": "审核策略原因:",
    "Next step:": "下一步:",
}

CONTAINS_REPLACEMENTS = {
    " Report": " 问题报告",
    " Analysis": " 分析",
    " Acceptance": " 验收",
    " Delivery Plan": " 交付计划",
    "Step contract is ready for delegated execution": "步骤契约已经可以进入委派执行",
    "Implement one frontend feature step": "定义一个可执行的前端功能开发步骤",
    "Implement one backend feature step": "定义一个可执行的后端功能开发步骤",
    "Implement one scoped feature step": "定义一个限定范围的功能开发步骤",
    "Implement one unresolved-path feature step": "定义一个待补目标路径的功能开发步骤",
    "Implement one frontend executor-failure feature step": "定义一个前端执行失败演练功能开发步骤",
    "Shared or mixed paths must be split first": "共享或混合路径必须先拆分",
    "One executor owns this step end to end": "一个执行器必须端到端负责这个执行步骤",
    "Ready to close this step.": "当前执行步骤已满足关闭条件，可以结束本轮工作流。",
    "Do not edit files outside target_paths.": "不要修改 target_paths 之外的文件。",
    "Do not change backend APIs.": "不要改动后端 API。",
    "Do not change frontend UI behavior.": "不要改动前端 UI 行为。",
    "Frontend: browser-visible work is complete and scoped.": "前端：浏览器可见范围内的工作已按限定范围完成。",
    "Backend: API work is complete and scoped.": "后端：API 范围内的工作已按限定范围完成。",
}


def normalize_text(text: str) -> str:
    normalized_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        leading = line[: len(line) - len(line.lstrip())]

        if stripped in EXACT_LINE_REPLACEMENTS:
            normalized_lines.append(f"{leading}{EXACT_LINE_REPLACEMENTS[stripped]}")
            continue

        if stripped in EXACT_BULLET_REPLACEMENTS:
            normalized_lines.append(f"{leading}{EXACT_BULLET_REPLACEMENTS[stripped]}")
            continue

        replaced = line
        for old, new in PREFIX_REPLACEMENTS.items():
            marker = f"{leading}{old}"
            if replaced.startswith(marker):
                replaced = f"{leading}{new}{replaced[len(marker):]}"
                break

        stripped_after_prefix = replaced.strip()
        if stripped_after_prefix in EXACT_VALUE_REPLACEMENTS:
            replaced = f"{leading}{EXACT_VALUE_REPLACEMENTS[stripped_after_prefix]}"
        elif stripped_after_prefix == "- TODO":
            replaced = f"{leading}- 待补充"

        for old, new in CONTAINS_REPLACEMENTS.items():
            if old in replaced:
                replaced = replaced.replace(old, new)

        if stripped.startswith("- Step "):
            replaced = replaced.replace("- Step ", "- 步骤 ")

        if stripped.startswith("Owner:"):
            replaced = f"{leading}执行归属:{stripped[len('Owner:') :]}"
            replaced = replaced.replace("frontend / Gemini", "前端 / Gemini").replace(
                "backend / Codex", "后端 / Codex"
            )
        elif stripped.startswith("Paths:"):
            replaced = f"{leading}目标路径:{stripped[len('Paths:') :]}"
        elif stripped.startswith("Summary:"):
            replaced = f"{leading}摘要:{stripped[len('Summary:') :]}"
        elif stripped.startswith("Acceptance:"):
            replaced = f"{leading}验收:{stripped[len('Acceptance:') :]}"

        replaced = replaced.replace("Requested decision: accepted", "请求决策: 通过")
        replaced = replaced.replace("Requested decision: changes-requested", "请求决策: 需修改")
        replaced = replaced.replace("Final decision: accepted", "最终决策: 通过")
        replaced = replaced.replace("Final decision: changes-requested", "最终决策: 需修改")

        normalized_lines.append(replaced)

    normalized = "\n".join(normalized_lines)
    if text.endswith("\n"):
        normalized += "\n"
    return normalized


def normalize_file(path: Path) -> dict[str, object]:
    original = path.read_text(encoding="utf-8")
    normalized = normalize_text(original)
    updated = normalized != original
    if updated:
        path.write_text(normalized, encoding="utf-8")
    return {"path": str(path), "updated": updated}


def should_scan(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".yaml"}


def main() -> int:
    results: list[dict[str, object]] = []
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and should_scan(path):
                results.append(normalize_file(path))

    updated_count = sum(1 for item in results if item.get("updated"))
    print(
        json.dumps(
            {
                "success": True,
                "scanned": len(results),
                "updated": updated_count,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
