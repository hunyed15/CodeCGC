# CodeCGC Release Maintenance Overview

This roadmap tracks the productization work required to keep CodeCGC releasable and maintainable.

## Goal

Make CodeCGC reliable as a Claude-native orchestration layer, not just as a collection of CLI wrappers.

The release maintenance track focuses on:

- Project-local installation correctness
- Orchestrator MCP tool surface stability
- Runtime and review evidence quality
- Package completeness
- External capability governance
- Documentation clarity for users and maintainers

## Current Baseline

The current baseline is:

- Global npm install provides CLI commands.
- Project-local install writes `.mcp.json`, `.claude`, `model-routing.yaml`, and `codecgc/`.
- CodeCGC MCP exposes the primary orchestrator tools.
- Codex and Gemini remain executor MCPs.
- Hook enforcement remains a guardrail, not the main orchestration layer.
- Release readiness is checked through `cgc-release-readiness`.

## Non-Goals

- Do not remove the CLI before the MCP path is stable.
- Do not wrap Codex or Gemini in a redundant executor layer.
- Do not make ordinary users memorize every internal `cgc-*` command.
- Do not publish raw design progress logs as user documentation.

## Success Criteria

- A new user can install and start from `/cgc-init` and `/cgc`.
- A maintainer can verify release readiness with one documented command chain.
- Published docs explain install modes, path rules, troubleshooting, and maintainer checks.
- Package audits catch missing runtime and reference files before publication.
