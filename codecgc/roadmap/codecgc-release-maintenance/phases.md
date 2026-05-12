# CodeCGC Release Maintenance Phases

## Phase 0: Stable User Entry

Objective:

- Keep the user-facing Claude entry small and predictable.

Deliverables:

- `/cgc` as the primary user entry.
- `/cgc-init`, `/cgc-status`, and `/cgc-doctor` for setup and health checks.
- `/cgc-review` and `/cgc-history` for common control points.
- Documentation that explains when to use CLI fallback.

Exit criteria:

- Users can start without reading internal command mappings.

## Phase 1: Orchestrator MCP First

Objective:

- Make CodeCGC MCP the primary capability layer.

Deliverables:

- Stable tool contracts for install, status, doctor, entry, continue, explain, review, history, and route.
- JSON responses that can be consumed by Claude without text parsing.
- Runtime errors normalized into actionable payloads.

Exit criteria:

- Claude command templates prefer MCP tools and only fall back to CLI when necessary.

## Phase 2: Runtime Contract Hardening

Objective:

- Keep workflow logic in reusable runtime code rather than scattered wrappers.

Deliverables:

- Shared runtime APIs for workflow state, routing, audit, and review writeback.
- CLI wrappers reduced to argument parsing and rendering.
- MCP tools call the same runtime contract.

Exit criteria:

- Behavior does not diverge between MCP and CLI paths.

## Phase 3: Review Trust

Objective:

- Improve confidence in accepted work.

Deliverables:

- Stronger diff and git evidence summaries.
- Explicit ownership and path-scope proof.
- Validation command capture where available.
- Reproducible audit summaries.

Exit criteria:

- Review results can explain why a step was accepted or rejected without relying only on executor claims.

## Phase 4: Release And Maintenance Closure

Objective:

- Keep the package publishable and maintainable.

Deliverables:

- Package runtime audit.
- External capability audit.
- Release readiness audit.
- Reference docs for quickstart, troubleshooting, path contract, and maintainer workflow.

Exit criteria:

- `cgc-release-readiness` passes before release.
