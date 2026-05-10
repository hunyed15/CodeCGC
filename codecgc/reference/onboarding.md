# CodeCGC Onboarding

This document defines the real-project entry experience after `cgc-install`.

## Contract

`cgc-install` is project-local by default. After a successful install, a target project should contain:

```text
codecgc/START_HERE.md
.claude/commands/cgc-start.md
```

`codecgc/START_HERE.md` is generated for the target project and is safe to keep in the project because it uses project-relative paths only. It must not contain the package installation directory or a developer machine path.

## First User Path

Inside Claude:

```text
/cgc-install
/cgc-start
/cgc-status
/cgc-doctor
/cgc 新增一个登录页面，放在 src/components/LoginForm.tsx
```

Outside Claude:

```bash
cgc-install
cgc-start
cgc-status
cgc-doctor
cgc "新增一个登录页面，放在 src/components/LoginForm.tsx"
```

## `/cgc-start`

`/cgc-start` is a read-only entry command. It should call `codecgc.start` and summarize:

- whether `codecgc/START_HERE.md` exists and matches the current onboarding contract
- the project-local onboarding file path
- the shortest next actions for Claude and CLI users
- the fallback action when onboarding is missing, normally `/cgc-install` or `cgc-install`

The CLI equivalent is `cgc-start`.

## Why This Exists

Without an explicit first-run entry, new users can install successfully but still be unsure whether to use `/cgc`, `/cgc-install`, `cgc-plan`, `cgc-build`, or another lower-level command. The onboarding surface keeps ordinary users on the product path:

```text
install -> start -> status/doctor -> /cgc natural-language request
```

Maintainer commands remain available, but they should not be required for the first successful workflow.

## Failure Handling

If `cgc-start` reports missing onboarding, run:

```bash
cgc-install
```

If `cgc-status` reports `onboarding_file` as missing or outdated, the same repair action applies.

If `cgc-doctor` reports `onboarding_file_ready` as failed, reinstall project-local integration before debugging executor availability.
