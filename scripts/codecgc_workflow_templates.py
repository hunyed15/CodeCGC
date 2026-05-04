from pathlib import Path


def build_feature_paths(flow_dir: Path, slug: str) -> dict[str, Path]:
    return {
        "design": flow_dir / f"{slug}-design.md",
        "checklist": flow_dir / f"{slug}-checklist.yaml",
        "acceptance": flow_dir / f"{slug}-acceptance.md",
    }


def build_issue_paths(flow_dir: Path, slug: str) -> dict[str, Path]:
    return {
        "report": flow_dir / f"{slug}-report.md",
        "analysis": flow_dir / f"{slug}-analysis.md",
        "fix": flow_dir / f"{slug}-fix.yaml",
        "fix_note": flow_dir / f"{slug}-fix-note.md",
    }


def render_bullet_list(items: list[str], indent: str, fallback: str) -> str:
    if not items:
        return f"{indent}- {fallback}"
    return "\n".join(f"{indent}- {item}" for item in items)


def render_optional_bullet_list(items: list[str], indent: str) -> str:
    if not items:
        return ""
    return "\n".join(f"{indent}- {item}" for item in items)


def build_scope_lines(kind: str, target_paths: list[str]) -> list[str]:
    if target_paths:
        return [f"仅修改 `{path}`。" for path in target_paths]
    if kind == "frontend":
        return ["实现一个仅前端范围、且目标文件明确的执行步骤。"]
    if kind == "backend":
        return ["实现一个仅后端范围、且目标文件明确的执行步骤。"]
    return ["在真实执行前，先把工作拆成单执行器可接管的范围。"]


def build_non_goal_lines(kind: str) -> list[str]:
    if kind == "frontend":
        return [
            "不要改动后端 API、持久化或服务端业务逻辑。",
            "不要把这个执行步骤扩展成前后端混合工作。",
        ]
    if kind == "backend":
        return [
            "不要改动页面布局、样式或仅浏览器侧的交互行为。",
            "不要把这个执行步骤扩展成前后端混合工作。",
        ]
    return [
        "不要在一个执行步骤中混合前端和后端执行。",
        "不要把尚未拍板的设计选择留在可执行步骤里。",
    ]


def build_acceptance_lines(kind: str, target_paths: list[str]) -> list[str]:
    lines = ["返回结构化执行结果。"]
    if target_paths:
        lines.append("变更文件必须保持在 target_paths 范围内。")
    if kind == "frontend":
        lines.append("用户可见的前端行为只覆盖当前已批准的范围。")
    elif kind == "backend":
        lines.append("后端行为变更只覆盖当前已批准的修复或功能步骤。")
    return lines


def build_constraint_lines(kind: str) -> list[str]:
    lines = ["不要修改 target_paths 之外的文件。"]
    if kind == "frontend":
        lines.append("不要改动后端 API。")
    elif kind == "backend":
        lines.append("不要改动前端 UI 行为。")
    return lines


def build_test_acceptance_lines(kind: str, target_paths: list[str]) -> list[str]:
    lines = ["返回结构化执行结果。", "只补充或更新当前范围内的测试。"]
    if target_paths:
        lines.append("测试相关变更文件必须保持在 target_paths 范围内。")
    if kind == "frontend":
        lines.append("优先覆盖界面、交互或前端行为回归。")
    elif kind == "backend":
        lines.append("优先覆盖接口、服务或后端行为回归。")
    return lines


def build_test_constraint_lines(kind: str) -> list[str]:
    lines = ["不要修改测试范围外的业务文件。"]
    if kind == "frontend":
        lines.append("不要新增后端 API 逻辑。")
    elif kind == "backend":
        lines.append("不要新增前端 UI 行为。")
    return lines


def render_feature_design(
    directory_name: str,
    summary: str,
    kind: str,
    target_paths: list[str],
    artifact_class: str = "product",
) -> str:
    owner = "前端 / Gemini" if kind == "frontend" else "后端 / Codex" if kind == "backend" else "待拆分"
    return f"""---
doc_type: feature-design
artifact_class: {artifact_class}
feature: {directory_name}
status: draft
summary: {summary}
tags: []
---

# {summary}

## 1. 目标

- 摘要: {summary}
- 计划执行归属: {owner}
- 候选目标路径:
{render_bullet_list(target_paths, "  ", "待补路径")}

## 2. 范围内

{render_bullet_list(build_scope_lines(kind, target_paths), "", "待补充")}

## 3. 范围外

{render_bullet_list(build_non_goal_lines(kind), "", "待补充")}

## 4. 执行说明

- 该产物应作为单一归属的执行步骤处理。
- 如果当前执行步骤仍然过于模糊，应先补齐验收条件，再进行非“仅预演”执行。
- 如果目标路径或归属变成混合状态，应重新拆分工作。
"""


def render_feature_checklist(
    directory_name: str,
    slug: str,
    created_date: str,
    kind: str,
    target_paths: list[str],
    artifact_class: str = "product",
) -> str:
    return render_feature_checklist_steps(
        directory_name,
        created_date,
        artifact_class,
        [
            {
                "action": "定义一个可执行的功能开发步骤",
                "exit_signal": "步骤契约已经可以进入委派执行",
                "status": "pending",
                "codecgc": {
                    "kind": kind,
                    "task_id": f"{slug}-step-1",
                    "task_summary": "只实现当前已批准的功能开发步骤。",
                    "target_paths": target_paths or ["待补路径"],
                    "constraints": build_constraint_lines(kind),
                    "acceptance": build_acceptance_lines(kind, target_paths),
                    "cd": ".",
                },
            }
        ],
    )


def render_feature_acceptance(summary: str, artifact_class: str = "product") -> str:
    return f"""---
doc_type: feature-acceptance
artifact_class: {artifact_class}
status: draft
summary: {summary}
tags: []
---

# {summary} 验收

## 1. 范围检查

待补充

## 2. 执行器检查

待补充

## 3. 剩余风险

待补充
"""


def render_issue_report(
    directory_name: str,
    summary: str,
    kind: str,
    target_paths: list[str],
    artifact_class: str = "product",
) -> str:
    owner = "前端 / Gemini" if kind == "frontend" else "后端 / Codex" if kind == "backend" else "待拆分"
    return f"""---
doc_type: issue-report
artifact_class: {artifact_class}
issue: {directory_name}
status: draft
severity: P2
summary: {summary}
tags: []
---

# {summary} 问题报告

## 1. 现象

- 摘要: {summary}
- 预估执行归属: {owner}
- 候选影响路径:
{render_bullet_list(target_paths, "  ", "待补路径")}

## 2. 复现方式

- 待补充：描述这个问题的最小复现路径。

## 3. 预期与实际

- 预期: 待补充
- 实际: 待补充
"""


def render_issue_analysis(
    directory_name: str,
    summary: str,
    kind: str,
    target_paths: list[str],
    artifact_class: str = "product",
) -> str:
    owner = "前端 / Gemini" if kind == "frontend" else "后端 / Codex" if kind == "backend" else "待拆分"
    return f"""---
doc_type: issue-analysis
artifact_class: {artifact_class}
issue: {directory_name}
status: draft
summary: {summary}
tags: []
---

# {summary} 分析

## 1. 根因

- 当前假设归属: {owner}
- 根因说明: 待补充

## 2. 范围

{render_bullet_list(build_scope_lines(kind, target_paths), "", "待补充")}

## 3. 修复方案

- 首选定点修复: 待补充
- 明确不采用的更大范围修复: 待补充
"""


def render_issue_fix(
    directory_name: str,
    slug: str,
    created_date: str,
    kind: str,
    target_paths: list[str],
    artifact_class: str = "product",
) -> str:
    return render_issue_fix_steps(
        directory_name,
        created_date,
        artifact_class,
        [
            {
                "action": "执行一个定点问题修复步骤",
                "exit_signal": "修复步骤已经可以进入委派执行",
                "status": "pending",
                "codecgc": {
                    "kind": kind,
                    "task_id": f"{slug}-fix-step-1",
                    "task_summary": "只执行当前已批准的问题修复步骤。",
                    "target_paths": target_paths or ["待补路径"],
                    "constraints": build_constraint_lines(kind),
                    "acceptance": build_acceptance_lines(kind, target_paths),
                    "cd": ".",
                },
            }
        ],
    )


def render_issue_fix_note(
    directory_name: str,
    summary: str,
    fix_date: str,
    artifact_class: str = "product",
) -> str:
    return f"""---
doc_type: issue-fix
artifact_class: {artifact_class}
issue: {directory_name}
path: standard
fix_date: {fix_date}
tags: []
---

# {summary} 修复说明

## 1. 已应用修复

待补充

## 2. 验证结果

待补充

## 3. 剩余风险

待补充
"""


def render_step_entry(step: dict[str, object]) -> str:
    lines = [
        f'  - action: "{step["action"]}"',
        f'    exit_signal: "{step["exit_signal"]}"',
        f'    status: {step.get("status", "pending")}',
    ]

    owner_hint = str(step.get("owner_hint", "")).strip()
    planning_note = str(step.get("planning_note", "")).strip()
    if owner_hint:
        lines.append(f"    owner_hint: {owner_hint}")
    if planning_note:
        lines.append(f"    planning_note: {planning_note}")

    codecgc = step.get("codecgc")
    if isinstance(codecgc, dict):
        lines.append("    codecgc:")
        lines.append(f"      kind: {codecgc['kind']}")
        if codecgc.get("step_type"):
            lines.append(f"      step_type: {codecgc['step_type']}")
        lines.append(f"      task_id: {codecgc['task_id']}")
        lines.append(f'      task_summary: "{codecgc["task_summary"]}"')
        lines.append("      target_paths:")
        lines.append(render_bullet_list(codecgc.get("target_paths", []), "        ", "待补路径"))
        lines.append("      constraints:")
        lines.append(render_bullet_list(codecgc.get("constraints", []), "        ", "待补充"))
        lines.append("      acceptance:")
        lines.append(render_bullet_list(codecgc.get("acceptance", []), "        ", "返回结构化执行结果。"))
        lines.append(f"      cd: {codecgc.get('cd', '.')}")
    return "\n".join(lines)


def render_feature_checklist_steps(
    directory_name: str,
    created_date: str,
    artifact_class: str,
    steps: list[dict[str, object]],
) -> str:
    rendered_steps = "\n".join(render_step_entry(step) for step in steps)
    return f"""feature: {directory_name}
artifact_class: {artifact_class}
created: {created_date}

steps:
{rendered_steps}

checks:
  - item: "共享或混合路径必须先拆分"
    source: scope-guard
    status: pending
  - item: "一个执行器必须端到端负责这个执行步骤"
    source: owner-guard
    status: pending
"""


def render_issue_fix_steps(
    directory_name: str,
    created_date: str,
    artifact_class: str,
    steps: list[dict[str, object]],
) -> str:
    rendered_steps = "\n".join(render_step_entry(step) for step in steps)
    return f"""issue: {directory_name}
artifact_class: {artifact_class}
created: {created_date}

steps:
{rendered_steps}

checks:
  - item: "混合或共享范围必须先拆分"
    source: scope-guard
    status: pending
  - item: "一个执行器必须端到端负责这个执行步骤"
    source: owner-guard
    status: pending
"""


def build_test_step(
    *,
    slug: str,
    flow: str,
    kind: str,
    target_paths: list[str],
    step_index: int,
) -> dict[str, object]:
    target_label = "前端" if kind == "frontend" else "后端" if kind == "backend" else "当前"
    flow_label = "问题修复" if flow == "issue" else "功能开发"
    return {
        "action": f"执行一个{target_label}测试补充步骤",
        "exit_signal": "测试步骤已可进入委派执行",
        "status": "pending",
        "codecgc": {
            "kind": kind,
            "step_type": "test",
            "task_id": f"{slug}-test-step-{step_index}",
            "task_summary": f"只补充当前已批准的{flow_label}{target_label}测试步骤。",
            "target_paths": target_paths or ["待补路径"],
            "constraints": build_test_constraint_lines(kind),
            "acceptance": build_test_acceptance_lines(kind, target_paths),
            "cd": ".",
        },
    }
