---
doc_type: feature-design
artifact_class: fixture
feature: 2026-05-02-entry-executor-failure-demo
status: draft
summary: Entry executor-failure demo
tags: []
---

# Entry executor-failure demo

## 1. 目标

- 摘要: Entry executor-failure demo
- 计划执行归属: backend / Codex
- 候选目标路径:
  - backend/src/executor_failure_demo.py

## 2. In Scope

- Change only `backend/src/executor_failure_demo.py`.

## 3. Out Of Scope

- Do not change unrelated backend or frontend files.

## 4. Execution Notes

- This fixture is used to validate executor-side failure recovery paths via an invalid Codex profile.
