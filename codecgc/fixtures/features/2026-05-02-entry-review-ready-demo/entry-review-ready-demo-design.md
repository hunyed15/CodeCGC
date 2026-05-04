---
doc_type: feature-design
artifact_class: fixture
status: approved
summary: Entry review-ready demo
tags: []
---

# Entry review-ready demo Design

## Goal

Provide a minimal fixture workflow that is already review-ready so `entry` can validate auto review dispatch.

## Scope

- One frontend-only executable step
- One matching non-dry-run audit artifact
- One TODO acceptance file waiting for review write-back

## Success

- `route` returns `cgc-review`
- `entry --mode continue --request "审核一下，如果没问题就通过"` auto-dispatches review
