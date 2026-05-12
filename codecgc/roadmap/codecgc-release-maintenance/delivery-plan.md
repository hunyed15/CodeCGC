# CodeCGC Release Maintenance Delivery Plan

This delivery plan turns the release maintenance roadmap into concrete work items.

## Immediate Work

1. Keep project-local install as the only install path (no user-level global writes).
2. Keep `/cgc` and `codecgc.entry` as the primary user path.
4. Keep the hook as a write guardrail, not as the orchestration engine.
5. Keep release docs stable and user-facing.

## Near-Term Work

1. Stabilize MCP tool schemas and response payloads.
2. Normalize MCP errors so Claude can decide the next action without parsing logs.
3. Extract workflow state access behind a runtime API.
4. Reduce duplicate logic between CLI wrappers and MCP tools.
5. Add focused tests for MCP tool argument mapping.

## Review Trust Work

1. Preserve local diff evidence in audit summaries.
2. Record validation commands and outcomes when available.
3. Distinguish missing evidence from failed evidence.
4. Keep ownership mismatch and out-of-scope changes as blocking review risks.
5. Ensure old fixtures do not silently bypass new review policy fields.

## Documentation Work

1. Keep `codecgc/reference/README.md` as the reference index.
2. Keep `quickstart.md` focused on first successful use.
3. Keep `troubleshooting.md` focused on real install/runtime failures.
4. Keep `path-contract.md` focused on absolute runtime paths versus project-relative artifacts.
5. Keep `maintainer-guide.md` focused on checks, release, and contribution rules.

## Verification

Before release, run:

```bash
cgc-status
cgc-doctor
cgc-package-audit
cgc-external-audit
cgc-release-readiness
```

For repository changes, also run the focused test suite documented in `codecgc/reference/maintainer-guide.md`.
