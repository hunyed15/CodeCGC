---
doc_type: feature-design
artifact_class: fixture
feature: 2026-05-01-richer-plan-v4
status: draft
summary: Richer plan fixture validation
tags: []
---

# Richer plan fixture validation

## 1. 目标

- 摘要: Richer plan fixture validation
- 用户目标: Validate richer planning output under fixture roots.
- 用户故事: As an operator, I want fixture plans to stay out of product roots.
- 计划执行归属: frontend / Gemini
- 候选目标路径:
  - src/components/RicherPlanFixture.tsx

## 2. 背景

- This checks artifact-class propagation from plan to init.

## 3. 范围内

- Create one frontend-only fixture step.

## 4. 范围外

- 不要改动后端 API。

## 5. 依赖与假设

依赖:
  - Fixture roots already exist.

假设:
  - No product artifact should be created.

## 6. 执行说明

- This artifact is currently scoped to one executor-owned step.
- 验收提示: Frontend fixture step stays in fixture roots.

## 7. 验证计划

- Confirm files are created under codecgc/fixtures/features.

## 8. 回退计划

- Delete the fixture workflow if the root is wrong.

## 9. 开放问题

- Should plan reject fixture/product root drift automatically?

## 10. 计划步骤

- 步骤 1: 定义一个可执行的前端功能开发步骤
  执行归属: 前端 / Gemini
  目标路径: src/components/RicherPlanFixture.tsx
  摘要: Implement only the approved frontend step in src/components/RicherPlanFixture.tsx.
  验收: Frontend fixture step stays in fixture roots.
