# CodeCGC MCP Server

This package contains the CodeCGC orchestrator MCP server.

The server is the preferred Claude-facing capability layer. The CLI remains available for fallback, CI, and local debugging.

## Current Tool Surface

- `codecgc.install`
- `codecgc.start`
- `codecgc.status`
- `codecgc.doctor`
- `codecgc.entry`
- `codecgc.continue`
- `codecgc.explain`
- `codecgc.review`
- `codecgc.history`
- `codecgc.route`
- `codecgc.plan`
- `codecgc.build`
- `codecgc.fix`
- `codecgc.test`
- `codecgc.package_audit`
- `codecgc.external_audit`
- `codecgc.external_status`
- `codecgc.release_readiness`
- `codecgc.lifecycle`

## Runtime Boundary

This server currently reuses the existing CodeCGC runtime scripts rather than replacing them.

The contract is:

- MCP tools expose product capabilities to Claude.
- Runtime scripts own workflow behavior.
- CLI commands stay as compatibility and maintainer surfaces.
- MCP responses should be machine-readable JSON payloads.
- `codecgc.external_status` is the concise panel view; `codecgc.external_audit` is the deeper consistency check.

## Response Contract

Every tool returns a stable envelope:

```json
{
  "success": true,
  "tool": "codecgc.status",
  "payload": {},
  "error": null,
  "meta": {
    "contract_version": "1.0",
    "payload_success": true,
    "response_shape": "codecgc.mcp.tool_result"
  }
}
```

The raw runtime response remains available under `payload`.

See `codecgc/reference/mcp-tool-surface.md` for the full contract.

Errors include a stable `error.category` field so Claude can distinguish runtime failures, invalid JSON, permission issues, missing scripts, and MCP wrapper exceptions without parsing text.
