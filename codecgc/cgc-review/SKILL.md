---
name: cgc-review
description: Final review, acceptance, audit, and write-back for CodeCGC. Use when delegated execution has completed and Claude needs to verify results, summarize risk, update workflow artifacts, and decide whether the work is truly complete.
---

# cgc-review

This skill owns the final control point of CodeCGC.

## Goal

Verify that delegated execution is complete and safe to close.

## Read First

Read:

- `codecgc/reference/shared-conventions.md`
- `codecgc/reference/execution-model.md`
- `codecgc/reference/execution-audit.md`
- `codecgc/reference/review-writeback.md`
- `codecgc/reference/operation-guide.md`

Then inspect:

- delegated execution result
- execution audit artifact
- changed paths
- relevant feature or issue artifact directory

## Responsibilities

- compare result against step acceptance criteria
- verify executor ownership was respected
- identify remaining risk
- prepare summary for artifact write-back
- write the review result back into acceptance or fix-note artifacts

## Hard Rule

Acceptance is not only "code exists".

It must also confirm:

- the correct executor handled the step
- the path scope was respected
- the step actually satisfied its local acceptance target
- follow-up work is clearly separated

## Output

Return a concise review result with:

- accepted or not accepted
- scope and ownership check
- remaining risks
- required next step if not done
