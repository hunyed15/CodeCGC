# CodeCGC Troubleshooting

## Install Mode Confusion

`npm install -g @hunyed15/codecgc` installs the CLI globally.

It does not install CodeCGC into every project. Run this per project:

```bash
cgc-init
cgc-start
cgc-status
cgc-doctor
```

## MCP JSON Parse Errors

If an MCP install tool reports a JSON parse failure, first check whether the files were still written correctly:

```bash
cgc-status
cgc-doctor
```

The MCP tool surface should request JSON internally, even when the user asked for summary output. If the tool returns non-JSON text, treat it as a tool wrapper bug and verify state with `cgc-status`.

## Missing First-Run Guide

If `cgc-start`, `cgc-status`, or `cgc-doctor` reports `onboarding_file` or `onboarding_file_ready`, rerun project-local install:

```bash
cgc-init
cgc-start
```

The generated file is `codecgc/START_HERE.md`. It should use project-relative paths and should not contain a machine-specific package install directory.

## Claude Hook Blocks A Write

The hook is a guardrail. It blocks Claude direct writes to product source paths that should belong to Codex or Gemini, including direct shell writes through `Bash` or `PowerShell`.

Expected behavior:

- Claude may update docs and orchestration files.
- Codex should update backend code and backend tests.
- Gemini should update frontend code and frontend tests.
- Mixed ownership must be split before execution.

If a write was blocked incorrectly, inspect `model-routing.yaml` first. It is the project-local policy source.

For shell commands, use `/cgc` or `cgc` for implementation work. The hook only allows CodeCGC entry commands, read-only inspection commands, and test/check commands.

## Codex Or Gemini Is Unavailable

Run:

```bash
cgc-doctor
```

Then verify that the target project's `.mcp.json` contains the expected `codecgc`, `codex`, and `gemini` MCP server entries.

If only CodeCGC works but executor calls fail, the issue is usually in the executor MCP installation, CLI availability, or authentication state.

## Python Or PyYAML Missing

Install runtime dependencies for the Python used by CodeCGC:

```bash
pip install pyyaml
```

For repository development:

```bash
pip install -r requirements-dev.txt
```

## Pytest Temp Directory Errors On Windows

If pytest cannot write to the default temporary directory, use an explicit temp root:

```bash
python -m pytest tests\test_codecgc_policy.py tests\test_install_codecgc.py --basetemp D:\tmp\codecgc-pytest
```

## Path Looks Machine-Specific

Runtime configuration may contain install-time absolute paths. Persisted project artifacts should use project-relative paths.

See [Path Contract](path-contract.md).

## When In Doubt

Run the readiness chain:

```bash
cgc-status
cgc-doctor
cgc-package-audit
cgc-external-status
cgc-external-audit
cgc-release-readiness
```

Use `cgc-lifecycle` when the question is about product phase or workflow coverage rather than installation health.
