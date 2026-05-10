# CodeCGC Policy Routing

CodeCGC uses a single routing policy file as the source of truth:

- `model-routing.yaml`

The policy separates files by owner:

- `orchestration`: CodeCGC workflow state, command surfaces, audits, plans, and routing config.
- `docs`: human-facing documentation.
- `backend`: backend product code owned by Codex.
- `frontend`: frontend product code owned by Gemini.
- `backend-test`: backend tests owned by Codex.
- `frontend-test`: frontend tests owned by Gemini.
- `shared`: shared contracts that must be split before execution.

## Control Flow

Normal writes should go through CodeCGC:

1. Claude receives the user request.
2. CodeCGC plans and routes the task.
3. Codex or Gemini executes the owned implementation step.
4. CodeCGC writes an execution audit.
5. Claude reviews the audit and chooses the next action.

Claude may write orchestration and docs files. Claude must not directly write product source paths.

## Install Boundary

Global npm install only provides the `cgc*` CLI commands. It must not write `~/.claude`, user-level hooks, or user-level slash commands.

Project install is the default integration path:

```bash
cd your-project
cgc-install
```

This creates project-local `.mcp.json`, `.claude/`, `model-routing.yaml`, and the `codecgc/` workflow directories. User-level install modes are explicit escape hatches only.

## Policy Checker

`scripts/codecgc_policy.py` evaluates the policy for every entry point that needs write ownership:

- Claude hook guardrail via `.claude/hooks/route-edit.ps1` for `Edit`, `Write`, and `MultiEdit`
- task payload construction via `scripts/build_codecgc_task.py`
- build/fix/test wrappers before executor dispatch
- status and doctor checks through `model-routing.yaml` validation

The hook is intentionally thin. It only forwards Claude edit requests to the shared policy checker.

## Shared Paths

`shared` paths use `split-first`.

Shared changes must be split into backend and frontend owned tasks, or explicitly redesigned as a compound workflow before implementation. A single executor should not directly own a shared change by default.
