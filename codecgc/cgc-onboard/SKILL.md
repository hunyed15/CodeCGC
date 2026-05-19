---
name: cgc-onboard
description: Initialize or rebuild the CodeCGC workflow layer in a project. Use when a repository needs the new CodeCGC structure, references, and product-level workflow rules instead of older command surfaces.
---

# cgc-onboard

This skill initializes or repairs the CodeCGC project integration layer.

## Goal

Create a project that has:

- `codecgc/` workflow references
- the active `cgc-*` command surface
- routing-aware execution rules
- active artifact storage under `codecgc/`

## Read First

Read:

- `codecgc/reference/shared-conventions.md`
- `codecgc/reference/execution-model.md`
- `codecgc/reference/workflow-scaffold.md`

Also inspect:

- `.mcp.json`
- `.claude/settings.json`
- `.claude/hooks/edit-guard.js`
- `model-routing.yaml`

## Rules

- Do not preserve old `cs-*` command compatibility
- Do not keep active artifact writes under legacy directories
- Do not keep legacy branding in the active workflow layer

## Expected Result

After onboarding, the repo should be ready to use:

- `cgc`
- `cgc-init`
- `cgc-status`
- `cgc-doctor`
- `cgc-plan`
- `cgc-build`
- `cgc-fix`
- `cgc-review`
- `cgc-route`
