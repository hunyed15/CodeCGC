# CodeCGC Reference Index

This directory contains the stable user and maintainer references shipped with CodeCGC.

## Recommended Reading Order

1. [Quickstart](quickstart.md)
2. [Onboarding](onboarding.md)
3. [Operation Guide](operation-guide.md)
4. [Real Workflow Loop](real-workflow-loop.md)
5. [Recovery Loop](recovery-loop.md)
6. [Troubleshooting](troubleshooting.md)
7. [Path Contract](path-contract.md)
8. [MCP Tool Surface](mcp-tool-surface.md)
9. [Maintainer Guide](maintainer-guide.md)

## Core Product Contract

CodeCGC is a Claude-native development orchestration layer.

- Claude owns orchestration, requirements, design, review, acceptance, docs, and workflow state.
- Codex owns backend implementation and backend tests.
- Gemini owns frontend implementation and frontend tests.
- CodeCGC orchestrator MCP owns the user-facing capability surface.
- The CLI remains available for local debugging, CI checks, and fallback execution.

The normal user path is:

```text
Claude /cgc -> CodeCGC MCP tool -> CodeCGC runtime -> Codex or Gemini executor
```

The normal install path is:

```text
npm global install -> project-local cgc-install -> cgc-start -> project .mcp.json / .claude / model-routing.yaml
```

User-level Claude installation is optional and must be explicit.

## Public User Surface

The preferred Claude-facing commands are intentionally small:

- `/cgc`
- `/cgc-install`
- `/cgc-status`
- `/cgc-doctor`
- `/cgc-review`
- `/cgc-history`

Other `cgc-*` commands may remain available as CLI commands, but ordinary users should not need to memorize all of them.

## Maintainer Surface

Maintainers may use lower-level commands directly:

- `cgc-plan`
- `cgc-build`
- `cgc-fix`
- `cgc-test`
- `cgc-route`
- `cgc-package-audit`
- `cgc-external-status`
- `cgc-external-audit`
- `cgc-release-readiness`
- `cgc-lifecycle`

These commands are useful for debugging, CI, release checks, and validating runtime behavior.
