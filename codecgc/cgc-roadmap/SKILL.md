---
name: cgc-roadmap
description: Create or expand roadmap-scale planning when a request is too large for one feature or issue flow. Use when work must be decomposed into phases, child tracks, or multiple follow-up workflows under codecgc/roadmap/.
---

# cgc-roadmap

This skill owns roadmap-scale decomposition for CodeCGC.

## Goal

Produce one of these outcomes:

- initialize a new roadmap pack
- expand an existing roadmap with clearer phases or child tracks
- confirm that the request is feature-sized and should return to `cgc-plan`

## Read First

Read:

- `codecgc/roadmap/README.md`
- `codecgc/reference/shared-conventions.md`
- `codecgc/reference/workflow-scaffold.md`
- `codecgc/reference/operation-guide.md`

Then inspect:

- current request
- related feature or issue artifacts
- existing roadmap docs under `codecgc/roadmap/`

## Core Rule

Roadmap is for work that is too large, too mixed, or too long-lived for one executable workflow.

Do not create roadmap just because the task feels important.

## Required Outcomes

A valid roadmap result should make these points clear:

- what the parent problem is
- why one feature or issue flow is not enough
- what phases or tracks exist
- what child workflows should be created next

## Output Rule

When roadmap is the right answer, return:

- roadmap slug or path
- parent problem summary
- next child workflow or next planning step

