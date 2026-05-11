# CodeCGC Quickstart

This guide shows the shortest path from a clean machine to a working project-local CodeCGC integration.

## 1. Install The CLI

Install the package globally:

```bash
npm install -g @hunyed15/codecgc --registry=https://registry.npmjs.org/
```

This only installs the global `cgc*` commands. It does not write user-level Claude files by default.

## 2. Install Into A Project

Run project-local install from the target project root:

```bash
cd your-project
cgc-install
cgc-start
cgc-status
cgc-doctor
```

Inside Claude, use `/cgc-install` and then `/cgc-start` for the same project-local path.

The project install syncs:

```text
.mcp.json
model-routing.yaml
.claude/settings.local.json
.claude/hooks/route-edit.ps1
.claude/commands/cgc*.md
.codex/codecgcrc.json
.gemini/policies/codecgc-policy.toml
codecgc/START_HERE.md
codecgc/
```

## 3. Read The Project Entry

Run:

```bash
cgc-start
```

This is a read-only first-run guide for the current project. If it reports missing onboarding, run `cgc-install` again from the target project root.

## 4. Start Work From The Single Entry

Prefer the Claude entry:

```text
/cgc 新增一个登录页面，放在 src/components/LoginForm.tsx
```

If you are outside Claude, use the CLI fallback:

```bash
cgc "新增一个登录页面，放在 src/components/LoginForm.tsx"
```

CodeCGC should route frontend implementation to Gemini and backend implementation to Codex.

## 5. Continue Or Explain

Use the same entry instead of memorizing internal commands:

```text
/cgc 继续刚刚的工作
/cgc 现在下一步该做什么
```

The orchestrator should decide whether the next action is planning, execution, review, or closure.

## 6. Review An Execution

When an execution audit is ready, use:

```text
/cgc-review
```

or the CLI fallback:

```bash
cgc-review --audit-file codecgc/execution/example-step-1.json --decision accepted
```

Review is a control point. It may downgrade an `accepted` request to `changes-requested` if local evidence, ownership, or scope checks fail.

For the full state loop, including dry-run downgrade and successful closure, see [Real Workflow Loop](real-workflow-loop.md).

## 7. Use Explicit Commands Only When Needed

Use explicit subcommands only when you already know the workflow phase:

```bash
cgc-plan ...
cgc-build ...
cgc-fix ...
cgc-test ...
cgc-route ...
```

For normal use, `/cgc` and the CodeCGC MCP tools should remain the primary path.
