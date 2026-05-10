# CodeCGC Maintainer Guide

This guide is for people changing CodeCGC itself.

## Development Setup

Install Node.js and Python dependencies:

```bash
npm install
pip install -r requirements-dev.txt
```

If `npm install` is not needed for the current change, you can still run the package scripts directly with the checked-in files.

## Focused Verification

Run these checks before publishing or tagging:

```bash
python scripts\install_codecgc.py --mode status --format json
python scripts\install_codecgc.py --mode doctor --format json
python scripts\audit_codecgc_package_runtime.py --format json
node --check bin\codecgc.js
python -m pytest tests\test_codecgc_policy.py tests\test_install_codecgc.py --basetemp D:\tmp\codecgc-pytest
```

Add broader tests when changing workflow routing, step execution, review policy, or installer behavior.

## Release Readiness Chain

Use:

```bash
cgc-status
cgc-doctor
cgc-package-audit
cgc-external-status
cgc-external-audit
cgc-release-readiness
cgc-lifecycle
```

This checks installation readiness, package contents, external capability registration, release signals, and lifecycle coverage.

## Command Surface Rule

Do not add a new slash command for every runtime action.

Preferred layering:

- Claude slash commands are a small user entry surface.
- CodeCGC MCP tools are the product capability surface.
- CLI commands are fallback, CI, and maintainer debugging surface.
- Python scripts are internal runtime implementation.

## Runtime Change Rule

When adding runtime behavior, prefer a stable callable function first, then attach CLI and MCP wrappers to it.

Shared runtime logic belongs in `scripts/codecgc_runtime/`. Keep top-level `scripts/*.py` files as command entry points or compatibility shims when an existing import path is already public inside this repository.

Avoid duplicating business logic separately in:

- Claude command markdown
- Node CLI wrappers
- Python scripts
- MCP tool functions

## Review Policy Rule

Review output must be evidence-based. Do not mark an execution accepted only because the executor said it completed.

At minimum, review should consider:

- executor ownership
- target scope
- local diff evidence
- reported files versus observed files
- test or validation evidence when available
- review writeback consistency

## Dirty Worktree Rule

The repository may contain local project files such as `.claude/settings.local.json`.

Do not commit user-local settings. Do not delete unrelated user changes while preparing a release.

## Documentation Rule

Published docs should be stable references, not raw progress logs.

Use the parent design documents as source material, then publish only the user-facing or maintainer-facing contract needed for the release.
