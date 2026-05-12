---
name: cgc
description: Root entry for CodeCGC. Use when the user wants to understand the CodeCGC workflow, does not know which cgc-* command to use, or gives an open-ended request that needs routing to installation, planning, feature delivery, issue fixing, or review.
---

# cgc

`cgc` is the product entry for CodeCGC.
It routes the request and does not execute workflow work itself.

## Read First

Before answering:

1. check whether the project already has `codecgc/`
2. read `codecgc/reference/shared-conventions.md`
3. read `codecgc/reference/workflow-scaffold.md`
4. scan `codecgc/features/`, `codecgc/issues/`, `codecgc/roadmap/`, `codecgc/requirements/`, and `codecgc/architecture/`
5. read `codecgc/reference/operation-guide.md`

## Route Table

- installing or repairing CodeCGC in a repo: `cgc-init` and `cgc-onboard`
- shaping or clarifying a request: `cgc-plan`
- starting or continuing feature delivery: `cgc-build`
- starting or continuing issue fixing: `cgc-fix`
- acceptance, audit, write-back, final review: `cgc-review`
- updating durable architecture docs: `cgc-arch`
- updating stable requirement docs: `cgc-req`
- expanding roadmap-scale planning: `cgc-roadmap`
- recording durable decisions: `cgc-decide`
- recording reusable lessons or pitfalls: `cgc-learn`
- behavior-preserving structural improvement: `cgc-refactor`

## Output Rule

Return only:

- the recommended next `cgc-*` command
- one short reason
- one short note on what happens next

Do not write specs, code, or acceptance content here.

When a concrete feature or issue artifact already exists, prefer routing based
on the current artifact state instead of free-form judgment.
