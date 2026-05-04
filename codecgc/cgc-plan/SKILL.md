---
name: cgc-plan
description: Clarify, shape, and split work before execution in CodeCGC. Use when a request is still fuzzy, too large, mixed across frontend and backend, or not yet ready to become a one-executor coding step.
---

# cgc-plan

This skill replaces the old split between vague brainstorming and feature entry.

## Goal

Produce one of these outcomes:

- ready for `cgc-build`
- ready for `cgc-fix`
- needs roadmap-level decomposition
- needs more user clarification

## Read First

Read:

- `codecgc/reference/shared-conventions.md`
- `codecgc/reference/execution-model.md`
- `codecgc/reference/checklist-contract.md`
- `codecgc/reference/workflow-scaffold.md`
- `codecgc/reference/operation-guide.md`

Inspect relevant existing artifacts if they exist.

## Core Rule

Do not let mixed execution scope leak into implementation.

If a request mixes frontend, backend, or shared change, split it before it can
be executed by CodeCGC.

## Exit Rule

A request may leave this skill only when it is clear:

- what problem is being solved
- whether it is build or fix work
- whether it is feature-sized or roadmap-sized
- whether the next executable step has one-model ownership

When the artifact directory does not exist yet, create the minimal scaffold
before handing work to `cgc-build` or `cgc-fix`.
