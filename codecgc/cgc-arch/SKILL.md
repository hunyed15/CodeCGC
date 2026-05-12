---
name: cgc-arch
description: Maintain long-lived current-state architecture assets for CodeCGC or an installed project. Use when accepted work changed system structure, runtime topology, integration boundaries, or durable technical constraints and those changes must be written back into codecgc/architecture/.
---

# cgc-arch

This skill maintains `codecgc/architecture/` as the current-state system map.

## Goal

Produce one of these outcomes:

- update an existing architecture document
- create one missing architecture document
- confirm that no architecture write-back is needed

## Read First

Read:

- `codecgc/architecture/README.md`
- `codecgc/reference/shared-conventions.md`
- `codecgc/reference/workflow-scaffold.md`

Then inspect:

- accepted feature or issue artifacts related to the change
- relevant files under `scripts/`, `bin/`, `.claude/`, `mcp/codexmcp/`, `mcp/geminimcp/`
- existing docs under `codecgc/architecture/`

## What Belongs Here

Write here only when the repository or installed project now has a durable new state:

- module boundaries
- runtime topology
- integration maps
- technical constraints already adopted

Do not write:

- speculative redesign
- one-off implementation notes
- executor audit output
- temporary task checklist detail

## Core Rule

Architecture docs record accepted reality, not future intent.

If the change is still under discussion, keep it out of `codecgc/architecture/`.

## Output Rule

When updating architecture, return:

- which architecture doc was updated or created
- one short summary of the durable system change
- whether requirements or roadmap should also be updated

