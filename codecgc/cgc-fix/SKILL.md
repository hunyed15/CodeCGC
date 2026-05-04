---
name: cgc-fix
description: Entry for issue fixing in CodeCGC. Use when the user wants to diagnose, continue, or apply a scoped bug fix and the code change must be delegated through the forced frontend or backend executor instead of direct Claude editing.
---

# cgc-fix

This skill owns issue repair for CodeCGC.

## Goal

Move a bug fix through:

1. scope confirmation
2. one-executor packaging
3. forced delegated execution
4. fix-note and review handoff

## Read First

Read:

- `codecgc/reference/shared-conventions.md`
- `codecgc/reference/execution-model.md`
- `codecgc/reference/checklist-contract.md`
- `codecgc/reference/fix-flow.md`
- `codecgc/reference/execution-audit.md`
- `codecgc/reference/flow-execution.md`
- `codecgc/reference/operation-guide.md`

Inspect the relevant issue directory under `codecgc/issues/`.

## Hard Rules

- do not directly edit routed business code with Claude
- do not expand a fix into mixed-scope implementation
- if the fix touches shared or mixed scope, split it first
- execute code changes through `scripts/run_codecgc_flow_step.py`

## Exit Rule

This skill ends with:

- a delegated fix result ready for `cgc-review`
- or a return to planning because the fix scope is still mixed or underspecified

When execution succeeds, keep the audit path with the fix result.
