# CodeCGC CLI

## 用途

`codecgc_cli.py` 是 CodeCGC 的统一本地封装入口。

相比逐个调用底层脚本，它更适合作为仓库维护和调试时的统一入口。

## 常用命令

单入口调度：

```bash
python scripts/codecgc_cli.py entry --request "新增一个登录页面，放在 src/components/LoginForm.tsx"
python scripts/codecgc_cli.py entry --request "继续刚刚的工作"
python scripts/codecgc_cli.py entry --request "现在下一步该做什么"
python scripts/codecgc_cli.py entry --mode new --flow feature --slug demo-login-ui --summary "Demo login UI feature" --target-path src/components/LoginForm.tsx --kind frontend
python scripts/codecgc_cli.py entry --mode continue --flow feature --slug 2026-05-01-demo-login-ui
python scripts/codecgc_cli.py entry --mode explain --slug 2026-05-01-demo-login-ui
python scripts/codecgc_cli.py entry --mode continue --latest
python scripts/codecgc_cli.py entry --mode continue --slug 2026-05-01-demo-login-ui --auto-dispatch --dry-run
```

规划并补齐工作流骨架：

```bash
python scripts/codecgc_cli.py plan --flow feature --slug demo-login-ui --summary "Demo login UI feature" --target-path src/components/LoginForm.tsx --kind frontend
python scripts/codecgc_cli.py plan --flow issue --slug demo-sync-bug --summary "Demo sync bug fix" --target-path backend/session/continue.py --kind backend
```

支持结构化 `plan` 输入：

```bash
python scripts/codecgc_cli.py plan --flow feature --slug demo-login-ui --summary "Demo login UI feature" --target-path src/components/LoginForm.tsx --kind frontend --goal "Allow users to sign in from a dedicated login form." --in-scope "Create the login form UI." --acceptance "Login form renders email and password fields."
python scripts/codecgc_cli.py plan --flow issue --slug demo-sync-bug --summary "Demo sync bug fix" --target-path backend/src/sync.py --kind backend --symptom "Sync stops on malformed record." --expected "Valid records still sync." --actual "Whole batch stops." --root-cause "Validation aborts the batch loop." --preferred-fix "Catch per-record validation errors." --acceptance "Malformed records are skipped and logged."
```

也支持更丰富的规划结构：

```bash
python scripts/codecgc_cli.py plan --flow feature --slug demo-login-ui --summary "Demo login UI feature" --target-path src/components/LoginForm.tsx --kind frontend --goal "Allow users to sign in from a dedicated login form." --user-story "As a returning user, I want a focused login entry so I can sign in quickly." --context "This replaces an inline login panel on the landing page." --dependency "Auth API already exists." --assumption "No backend contract changes are needed." --validation "Render the form and submit against the existing auth endpoint." --rollback "Restore the previous inline login entry if the new screen fails review."
```

初始化工作流产物：

```bash
python scripts/codecgc_cli.py init --flow feature --slug demo-login-ui --summary "Demo login UI feature"
```

运行一个高层功能开发或问题修复步骤：

```bash
python scripts/codecgc_cli.py build --slug 2026-05-01-demo-login-ui --step-number 1 --dry-run
python scripts/codecgc_cli.py fix --slug 2026-05-01-demo-sync-bug --step-number 1 --dry-run
```

精确执行一个步骤：

```bash
python scripts/codecgc_cli.py exec --flow feature --slug 2026-05-01-demo-login-ui --step-number 1 --dry-run
```

写回审核结果：

```bash
python scripts/codecgc_cli.py review --audit-file codecgc/execution/demo-login-ui-step-1.json --decision accepted
```

判断当前产物状态的下一步命令：

```bash
python scripts/codecgc_cli.py route --flow feature --slug 2026-05-01-demo-login-ui
```

## 说明

优先把 `codecgc_cli.py` 当作维护和调试时的统一入口。
如果你想用一个明显的开始/继续/解释入口，优先用 `entry`。
日常工作流阶段优先使用 `plan/build/fix/review/route`。
只有在需要更底层控制时，才直接使用 `init/exec`。

`entry` 现已支持通过 `--request` 接收轻量意图优先请求。

`plan` 现在也会返回可机读的 `planning_status`：

- `ready-for-build`
- `ready-for-fix`
- `needs-clarification`
- `needs-roadmap`
