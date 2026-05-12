# CodeCGC Real Workflow Loop

This page describes the repeatable CodeCGC loop after a project has already run `cgc-init`.

The goal is not to make users memorize every command. The goal is to keep one stable control loop where Claude orchestrates state, Codex or Gemini executes scoped code work, and review closes the loop only when there is enough evidence.

## Ownership Model

Claude owns orchestration work:

- Requirements and clarification.
- Feature or issue planning.
- Workflow state explanation.
- Documentation and acceptance notes.
- Review decision writeback.
- Routing recovery when scope or evidence is wrong.

Codex owns backend execution:

- Backend implementation under paths classified as backend.
- Backend tests when the step is explicitly a backend test step.
- Returning execution evidence through the backend executor.

Gemini owns frontend execution:

- Frontend implementation under paths classified as frontend.
- Frontend tests when the step is explicitly a frontend test step.
- Returning execution evidence through the frontend executor.

CodeCGC owns the contract between them:

- Project-local paths and generated artifacts.
- `model-routing.yaml` path classification.
- Step selection from checklist or fix YAML.
- Execution audit files under `codecgc/execution/`.
- Review policy and checklist status writeback.

## Normal Loop

The preferred Claude entry is:

```text
/cgc <your request>
```

For CLI debugging or CI, the same loop maps to:

```bash
cgc "add a backend endpoint under src/server/demo.py"
cgc-route --flow feature --slug 2026-05-10-demo
cgc-build --slug 2026-05-10-demo
cgc-review --audit-file codecgc/execution/demo-step-1.json --decision accepted
cgc-route --flow feature --slug 2026-05-10-demo
```

The stable states are:

- `needs-planning`: Claude must refine or repair the plan before execution.
- `awaiting-build`: a feature step is ready for Codex or Gemini execution.
- `awaiting-fix`: an issue step is ready for Codex or Gemini execution.
- `awaiting-review`: an execution audit is ready for Claude review.
- `closed`: the current workflow has no remaining executable step.

## Dry-Run Behavior

Use dry-run to check routing and payload shape:

```bash
cgc-build --slug 2026-05-10-demo --dry-run
```

A dry-run writes an audit, but it is not execution evidence. If review is requested as `accepted`, the review policy must downgrade it to `changes-requested` and keep the step `pending`.

Expected recovery:

```text
dry-run audit -> cgc-review accepted -> final_decision changes-requested -> route recommends cgc-build again
```

This is intentional. It prevents a workflow from closing when no real executor changed the workspace.

## Successful Execution Behavior

After a real executor run, CodeCGC expects an audit with:

- `mode: execute`
- matching `task_id`
- matching `source.step_number`
- executor success
- `result.outcome: done`
- no `dry_run_only` policy check
- no `execution_not_performed` risk

If those conditions hold, route must recommend `cgc-review` even if the previous review for the same step was `changes-requested`. The newest valid execution evidence should be reviewed instead of being blocked by an older failed review.

Expected recovery:

```text
changes-requested review -> real execute audit -> route recommends cgc-review -> accepted review -> checklist step done -> route closed
```

## Review Writeback

Review writes back to the workflow artifact:

- Feature workflows write to `*-acceptance.md`.
- Issue workflows write to `*-fix-note.md`.
- Accepted review sets the matching checklist step to `done`.
- Changes-requested review keeps the matching checklist step `pending`.

Review is a control point, not a text append helper. It can reject or downgrade a requested acceptance when evidence is missing, out of scope, owned by the wrong executor, or only dry-run.

For detailed recovery behavior after executor failure, review rejection, mixed paths, test steps, or session continue, see [Recovery Loop](recovery-loop.md).

## Machine-Independent Paths

Generated and persisted project paths must stay project-relative:

- Good: `codecgc/execution/demo-step-1.json`
- Good: `src/server/demo.py`
- Bad: `D:\Users\someone\project\codecgc\execution\demo-step-1.json`

Runtime code may resolve absolute paths internally, but package output, audit JSON, and docs should not depend on the install directory of a specific computer.
