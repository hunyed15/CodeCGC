---
name: cgc-req
description: Write back stable current-state product requirements into codecgc/requirements/. Use when accepted feature or issue work changed the durable product surface, command contract, business rule, or scope boundary and that reality should be recorded as a long-lived requirement artifact.
---

# cgc-req

This skill maintains `codecgc/requirements/` as the current-state requirement layer.

## Goal

Produce one of these outcomes:

- update an existing requirement doc
- create one missing requirement doc
- confirm that no requirement write-back is needed

## Read First

Read:

- `codecgc/requirements/README.md`
- `codecgc/reference/shared-conventions.md`
- `codecgc/reference/workflow-scaffold.md`

Then inspect:

- accepted feature or issue artifacts
- user-facing command or capability changes
- existing requirement docs under `codecgc/requirements/`

## What Belongs Here

Write here only when the capability is now part of stable current behavior:

- current user-visible capabilities
- business rules already in force
- stable scope boundaries for established modules
- accepted command-surface behavior

Do not write:

- brainstorming
- temporary bug analysis
- one-off implementation notes
- future roadmap intent

## Core Rule

Requirements docs explain what the product now does and where its stable boundaries are.

They do not explain how one temporary feature step was implemented.

## Output Rule

When updating requirements, return:

- which requirement doc was updated or created
- the stable capability or rule that changed
- whether architecture should also be updated

