from __future__ import annotations


def render_bullet_list(items: list[str], indent: str, fallback: str) -> str:
    values = [item.strip() for item in items if item.strip()]
    if not values:
        return f"{indent}- {fallback}"
    return "\n".join(f"{indent}- {item}" for item in values)


def render_overview(
    *,
    initiative: str,
    summary: str,
    user_story: str,
    goal: str,
    context: list[str],
    scope: list[str],
    risks: list[str],
    reasons: list[str],
    artifact_class: str,
) -> str:
    return f"""---
doc_type: roadmap-overview
artifact_class: {artifact_class}
initiative: {initiative}
status: draft
summary: {summary}
tags: []
---

# {summary}

## 1. 目标

- 摘要: {summary}
- 目标: {goal or '待补充'}
- 用户故事或操作者诉求: {user_story or '待补充'}

## 2. 背景

{render_bullet_list(context, '', '待补充')}

## 3. 为什么需要走 Roadmap

{render_bullet_list(reasons, '', '待补充')}

## 4. 范围

{render_bullet_list(scope, '', '待补充')}

## 5. 风险

{render_bullet_list(risks, '', '待补充')}
"""


def render_phases(
    *,
    initiative: str,
    grouped_paths: dict[str, list[str]],
    artifact_class: str,
) -> str:
    frontend_paths = grouped_paths.get("frontend", [])
    backend_paths = grouped_paths.get("backend", [])
    shared_paths = grouped_paths.get("shared", [])
    unknown_paths = grouped_paths.get("unknown", [])
    return f"""---
doc_type: roadmap-phases
artifact_class: {artifact_class}
initiative: {initiative}
status: draft
tags: []
---

# {initiative} 阶段拆分

## 1. 阶段说明

- 第 1 阶段：澄清范围、依赖和成功标准
- 第 2 阶段：把 initiative 拆成可执行的 feature 或 issue track
- 第 3 阶段：按正常 CodeCGC 流程交付前端和后端 track

## 2. 候选前端 Track

{render_bullet_list(frontend_paths, '', '暂未识别。')}

## 3. 候选后端 Track

{render_bullet_list(backend_paths, '', '暂未识别。')}

## 4. 共享或未知范围

共享范围:
{render_bullet_list(shared_paths, '  ', '无。')}

未知范围:
{render_bullet_list(unknown_paths, '  ', '无。')}

## 5. 已初始化的子工作流

- 暂无。
"""


def render_delivery_plan(
    *,
    initiative: str,
    dependencies: list[str],
    assumptions: list[str],
    validation: list[str],
    rollback: list[str],
    open_questions: list[str],
    artifact_class: str,
) -> str:
    return f"""---
doc_type: roadmap-delivery-plan
artifact_class: {artifact_class}
initiative: {initiative}
status: draft
tags: []
---

# {initiative} 交付计划

## 1. 依赖

{render_bullet_list(dependencies, '', '待补充')}

## 2. 前提假设

{render_bullet_list(assumptions, '', '待补充')}

## 3. 验证策略

{render_bullet_list(validation, '', '待补充')}

## 4. 回退策略

{render_bullet_list(rollback, '', '待补充')}

## 5. 开放问题

{render_bullet_list(open_questions, '', '当前无。')}

## 6. 工作流跟踪

- 目前还没有登记子工作流。
"""
