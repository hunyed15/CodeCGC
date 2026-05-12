# CodeCGC Path Contract

CodeCGC uses two different path classes. They must not be mixed.

## Install-Time Runtime Paths

Runtime configuration may use absolute paths because every machine installs packages in a different location.

Examples:

- MCP server command paths
- package script paths
- hook script command targets
- local Python script entry points

These paths are generated during install and are allowed to be machine-specific.

## Persisted Project Artifact Paths

Workflow artifacts should use project-relative paths whenever they describe project files or execution evidence.

Examples:

- `codecgc/features/...`
- `codecgc/issues/...`
- `codecgc/execution/...`
- `src/components/LoginForm.tsx`
- `backend/src/sync.py`

These files should remain portable across machines and repositories.

## Rule

Use absolute paths for runtime launch configuration.

Use project-relative paths for persisted product state, audits, fixtures, review evidence, and workflow documents.

## Installer Responsibility

`cgc-init` is responsible for writing machine-specific runtime paths into the target project integration files.

It should not hard-code paths from the development machine into reusable templates or persisted workflow artifacts.

## Maintainer Check

Before release, run:

```bash
cgc-package-audit
cgc-release-readiness
```

If a fixture or product artifact contains a stale local path, normalize it before publishing.
