---
name: cgc-build
description: Entry for feature delivery in CodeCGC. Use when the user wants to add or continue a feature and the work must move from planning into design, executable step packaging, delegated implementation, and review under forced multi-model routing.
---

# cgc-build

This skill owns feature delivery for CodeCGC.

## Goal

Move a feature through:

1. design readiness
2. step isolation
3. forced delegated execution
4. review handoff

## Read First

Read:

- `codecgc/reference/shared-conventions.md`
- `codecgc/reference/execution-model.md`
- `codecgc/reference/checklist-contract.md`
- `codecgc/reference/build-flow.md`
- `codecgc/reference/execution-audit.md`
- `codecgc/reference/flow-execution.md`
- `codecgc/reference/operation-guide.md`

Inspect the relevant feature directory under `codecgc/features/`.

## Hard Rules

- code-writing steps must not be executed directly by Claude
- every executable code step must have a valid `codecgc` block
- mixed frontend/backend/shared scope must be split before execution
- the workflow wrapper must call `scripts/run_codecgc_flow_step.py`

## Current Product Boundary

This skill must use design and checklist artifacts under `codecgc/features/`
and interpret them through CodeCGC rules.

## Exit Rule

The output of this skill is one of:

- a delegated execution result ready for `cgc-review`
- a request to return to planning or design
- a refusal because the step is not executable yet

When execution succeeds, keep the audit path with the result package.
