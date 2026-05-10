# CodeCGC Recovery Loop

This page defines how CodeCGC should recover when a workflow cannot move straight from execution to acceptance.

The recovery loop is part of normal product behavior. It is not an exceptional maintainer-only path.

## Recovery States

CodeCGC uses structured command results to make recovery machine-readable:

- `state`: where the workflow stopped.
- `failure_type`: why the workflow stopped.
- `recommended_command`: the next command to run, if there is a safe one.
- `next`: human-facing recovery instruction.
- `replan_payload`: structured planning payload when the workflow must return to `cgc-plan`.
- `reused_session_id`: executor session reused for the same task, when available.

## Executor Failure

If an executor returns invalid output, fails, or cannot complete the task, the workflow must not pretend that the step is ready for review.

Expected behavior:

```text
executor failure -> state blocked -> failure_type executor-failure -> inspect executor output before retry
```

The retry command may be empty when CodeCGC cannot safely prove that a simple rerun is enough. In that case the operator must inspect the audit and executor logs first.

## Review Rejection

When review writes `changes-requested`, the matching checklist step remains `pending`.

Expected behavior:

```text
review changes-requested -> route recommends cgc-build/cgc-fix/cgc-test again
```

If the previous executor audit contains a reusable `session_id`, the next execution command should include `--session-id <id>` for the same task. This keeps the executor conversation continuous without changing the workflow step.

## Mixed Path Recovery

A single executable step must not mix frontend, backend, shared, docs, or orchestration ownership.

Expected behavior:

```text
mixed ownership -> route recommends cgc-plan -> split_suggestion/replan_payload describes smaller steps
```

The structured split payload should include:

- `grouped_paths`
- `path_classification`
- `suggested_split_steps`
- `target_paths`
- `in_scope`

Claude uses this payload to rewrite the plan into narrower executable steps.

## Test Step Recovery

Test steps are routed through `cgc-test`.

The stable marker is:

```yaml
codecgc:
  step_type: test
```

`task_id` naming may still contain `-test-step-` for readability, but routing must not depend on that naming convention.

Expected behavior:

```text
step_type test -> route recommends cgc-test
cgc-test --dry-run -> state executed-dry-run -> retry cgc-test without dry-run
```

## Session Continue

Session continue is scoped to the current task id and artifact class.

CodeCGC resolves reusable session ids from:

1. `audit.result.session_id`
2. `audit.requested_session_id`

Expected behavior:

```text
same task_id + existing audit session_id -> next build/fix/test includes --session-id
```

Session ids must not be copied across unrelated task ids or unrelated artifact classes.

## Verification

Maintainers should keep recovery behavior covered by tests that do not call real Codex or Gemini. The recovery contract can be validated with synthetic audits and temporary workspaces.

Minimum coverage:

- executor failure classification
- review rejection and retry
- mixed path split payload
- explicit `step_type: test`
- session continue command arguments
