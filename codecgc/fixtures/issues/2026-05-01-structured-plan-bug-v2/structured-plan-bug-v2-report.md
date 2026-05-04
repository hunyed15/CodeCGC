---
doc_type: issue-report
artifact_class: fixture
issue: 2026-05-01-structured-plan-bug-v2
status: draft
severity: P2
summary: Structured plan bug v2
tags: []
---

# Structured plan bug v2 问题报告

## 1. 现象

- 摘要: Structured plan bug v2
- 现象: Sync job exits early when one record is invalid.
- 预估执行归属: backend / Codex
- 候选影响路径:
  - backend/src/sync.py

## 2. 复现方式

- Run the nightly sync with one malformed record in the batch.

## 3. 预期与实际

- Expected: Valid records continue syncing and invalid ones are logged.
- Actual: The entire batch stops after the first invalid record.
