# CodeCGC MCP Tool Surface

This document defines the stable response contract for CodeCGC orchestrator MCP tools.

## Role

CodeCGC MCP is the preferred Claude-facing capability layer.

The CLI is still available for:

- local debugging
- CI checks
- release checks
- fallback execution when MCP is unavailable

## Response Envelope

Every CodeCGC MCP tool returns a JSON object with this shape:

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

## Fields

- `success`: Overall MCP tool success. This is false if the runtime payload failed or if the MCP wrapper failed before getting a runtime payload.
- `tool`: Fully qualified CodeCGC tool name.
- `payload`: Raw runtime payload returned by the underlying CodeCGC runtime script.
- `error`: Normalized error object, or null.
- `meta.contract_version`: MCP response contract version.
- `meta.payload_success`: Raw runtime payload success flag.
- `meta.response_shape`: Constant response shape identifier.

## Error Object

When `success` is false, `error` uses this shape:

```json
{
  "type": "RuntimeScriptError",
  "category": "runtime-script-failed",
  "message": "Runtime script reported failure.",
  "tool": "codecgc.status",
  "script": "install_codecgc.py",
  "args": ["--mode", "status", "--format", "json"],
  "returncode": 1
}
```

If the runtime script raises or produces invalid JSON before returning a payload, `type` is the exception class name and `payload` contains a minimal failure summary.

## Error Categories

Stable categories currently include:

- `runtime-script-failed`: the runtime script returned a non-zero exit code.
- `runtime-payload-failed`: the runtime script returned JSON with `success: false` but no process return code.
- `runtime-json-invalid`: the MCP wrapper could not parse runtime JSON, or runtime parsing raised a `ValueError`.
- `runtime-timeout`: the runtime process timed out.
- `runtime-script-missing`: the expected runtime script or file was not found.
- `runtime-permission-denied`: the runtime wrapper hit a filesystem permission error.
- `mcp-wrapper-exception`: the MCP wrapper failed for another reason before producing a normal payload.

Runtime payloads may provide a more specific `error_category` or `failure_category`; when present, the MCP wrapper preserves that category.

## Current Tools

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

## Compatibility Rule

The raw runtime result remains available under `payload`.

Claude-facing behavior should consume the envelope first, then inspect `payload` for domain-specific details.

## Argument Mapping Rule

MCP tools must keep argument mapping deterministic.

- User-facing `format` hints do not change the envelope shape.
- `codecgc.install` always calls `install_codecgc.py` with `--format json` internally and records the requested format in `payload.requested_format`.
- `codecgc.start` calls `install_codecgc.py --mode start --format json` and is read-only.
- `workspace` values are normalized before being passed to runtime scripts.
- Repeated list values are emitted as repeated flags, not comma-joined strings.
- Boolean switches are omitted when false and emitted as bare flags when true.
