---
name: cgc-decide
description: Record durable technical or product decisions after they have been accepted. Use when a choice about architecture, workflow policy, command surface, model routing, or long-lived convention must be written back into codecgc/compound/ or a related durable asset.
---

# cgc-decide

This skill records durable accepted decisions for future humans and models.

## Goal

Produce one of these outcomes:

- append or create a durable decision artifact
- update an existing durable decision section
- confirm that the choice is not final yet and should not be archived

## Read First

Read:

- `codecgc/compound/README.md`
- `codecgc/reference/shared-conventions.md`
- accepted design, review, or architecture artifacts that contain the final choice

## What Counts As A Decision

Good candidates:

- command-surface policy
- routing or ownership convention
- architecture constraint
- product-level workflow choice
- long-lived migration rule

Bad candidates:

- tentative brainstorming
- unreviewed implementation preference
- one-step local workaround

## Core Rule

Only archive decisions that are already accepted.

If the team is still debating, do not write a durable decision note.

## Output Rule

When recording a decision, return:

- where it was recorded
- the decision itself in one line
- what future behavior it constrains

