---
name: cgc-refactor
description: Run a controlled behavior-preserving refactor flow under CodeCGC rules. Use when the request is about structure, readability, maintainability, or performance without changing product behavior, and the work still needs planning, routing, execution, and review discipline.
---

# cgc-refactor

This skill owns controlled refactor work for CodeCGC.

## Goal

Move a refactor through:

1. scope confirmation
2. behavior-preserving plan
3. routed execution
4. review and write-back

## Read First

Read:

- `codecgc/reference/shared-conventions.md`
- `codecgc/reference/execution-model.md`
- `codecgc/reference/operation-guide.md`

Then inspect:

- relevant source files
- current feature or issue artifacts if the refactor is adjacent to accepted work

## Hard Rules

- refactor must not hide a new feature
- refactor must not hide a bug fix requirement
- mixed frontend/backend scope must be split before execution
- code-writing still follows the same routed ownership model

## Exit Rule

This skill ends with one of:

- a routed refactor step ready for execution
- a return to `cgc-plan` because the request is actually feature or issue work
- a refusal because behavior-preserving scope is not credible yet

