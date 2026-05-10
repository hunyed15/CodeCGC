# CodeCGC Capability Matrix

This matrix defines which layer owns each product capability.

## Product Layers

| Capability | Claude | CodeCGC MCP | Runtime | Codex | Gemini | CLI |
| --- | --- | --- | --- | --- | --- | --- |
| User request intake | Owner | Tool surface | Support | No | No | Fallback |
| Project install | Initiates | Owner | Executes | No | No | Fallback |
| Status and doctor | Reads | Owner | Executes | No | No | Fallback |
| Requirement clarification | Owner | Optional state write | Stores artifacts | No | No | Debug |
| Planning | Owner | Entry or plan tool | Builds workflow state | No | No | Fallback |
| Backend implementation | Controller | Routes | Dispatches | Owner | No | Debug |
| Frontend implementation | Controller | Routes | Dispatches | No | Owner | Debug |
| Test execution | Controller | Routes | Dispatches | Backend tests | Frontend tests | Debug |
| Review | Owner | Review tool | Evidence and writeback | Responds to backend fixes | Responds to frontend fixes | Fallback |
| History | Reads | Owner | Scans artifacts | No | No | Fallback |
| Route explanation | Reads | Owner | Evaluates state | No | No | Fallback |
| Release readiness | Reads | Optional tool | Audits repository | No | No | Owner |
| External capability audit | Reads | Optional tool | Audits registry | No | No | Owner |
| Documentation updates | Owner | Optional governance tools | Stores artifacts | No by default | No by default | Debug |

## Boundary Rules

- Claude controls the workflow, but does not directly implement routed product source changes.
- CodeCGC MCP is the preferred product capability surface for Claude.
- Runtime modules own workflow state, routing, audit, and evidence behavior.
- Codex owns backend code and backend tests.
- Gemini owns frontend code and frontend tests.
- CLI remains a compatibility, CI, and maintainer debugging surface.

## Design Direction

Do not add a new slash command for every runtime action.

When a capability becomes stable, expose it through the orchestrator MCP first. Keep CLI access for fallback and automation.
