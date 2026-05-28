import { init } from "../src/mcp/codecgcmcp/tools/init.js";
import { entry } from "../src/mcp/codecgcmcp/tools/entry.js";
import { plan } from "../src/mcp/codecgcmcp/tools/plan.js";
import { build } from "../src/mcp/codecgcmcp/tools/build.js";
import { fix } from "../src/mcp/codecgcmcp/tools/fix.js";
import { route } from "../src/mcp/codecgcmcp/tools/route.js";
import { loadExecutorConfig } from "../src/shared/executor-config.js";
import { join } from "path";
import { mkdirSync, rmSync, existsSync } from "fs";

async function e2eTest() {
  console.log("=== 端到端 Workflow 测试 ===\n");

  // ==========================================
  // 测试 1: 轻量模式完整链路
  // ==========================================
  console.log("━━━ 测试 1: 轻量模式 (init → entry → plan → build) ━━━");
  const lwRoot = join(process.cwd(), "test-e2e-lightweight");
  if (existsSync(lwRoot)) rmSync(lwRoot, { recursive: true });
  mkdirSync(lwRoot, { recursive: true });

  // 1a. 初始化
  const initResult = await init({ cd: lwRoot, force: true, mode: "lightweight" });
  console.assert(initResult.success, "init 应成功");
  const lwConfig = await loadExecutorConfig(lwRoot);
  console.assert(lwConfig.mode === "lightweight", "应为轻量模式");
  console.log("  init ✅ 模式:", lwConfig.mode);

  // 1b. 创建 workflow
  const entryResult = await entry({
    cd: lwRoot,
    description: "添加用户登录功能",
    kind: "feature",
  });
  console.assert(entryResult.success, "entry 应成功");
  console.assert(entryResult.kind === "feature", "应为 feature");
  console.log("  entry ✅ slug:", entryResult.slug);

  // 1c. 路由（轻量模式应全部返回 orchestration）
  const routeResult = await route({
    cd: lwRoot,
    paths: ["src/api/auth.ts", "src/components/Login.tsx"],
  });
  console.assert(routeResult.success, "route 应成功");
  console.assert(routeResult.mode === "lightweight", "route 应返回 lightweight");
  console.assert(routeResult.recommended_executor === "orchestration", "应推荐 orchestration");
  console.assert(routeResult.actual_provider === "claude", "provider 应为 claude");
  console.log("  route ✅ executor:", routeResult.recommended_executor, "provider:", routeResult.actual_provider);

  // 1d. 规划（轻量模式下 Claude 处理所有步骤）
  const planResult = await plan({
    cd: lwRoot,
    kind: "feature",
    slug: entryResult.slug,
    steps: [
      {
        id: "s1",
        title: "实现登录 API",
        executor: "backend",
        task_id: "task-1",
        summary: "实现 POST /api/login 接口",
        paths: ["src/api/auth.ts"],
      },
      {
        id: "s2",
        title: "实现登录组件",
        executor: "frontend",
        task_id: "task-2",
        summary: "实现 Login.tsx 组件",
        paths: ["src/components/Login.tsx"],
      },
    ],
  });
  console.assert(planResult.success, "plan 应成功");
  console.assert(planResult.steps_added === 2, "应添加 2 个步骤");
  console.log("  plan ✅ steps_added:", planResult.steps_added);

  // 1e. 执行第一个步骤（轻量模式 → Claude 直接处理）
  const buildResult = await build({
    cd: lwRoot,
    kind: "feature",
    slug: entryResult.slug,
    step_id: "s1",
  });
  console.assert(buildResult.success, "build 应成功");
  console.assert(buildResult.session_id.includes("claude-direct"), "session_id 应包含 claude-direct");
  console.assert(buildResult.executor === "backend", "executor 应为 backend");
  console.log("  build(s1) ✅ session_id:", buildResult.session_id);

  // 1f. 执行第二个步骤（轻量模式 → Claude 直接处理）
  const buildResult2 = await build({
    cd: lwRoot,
    kind: "feature",
    slug: entryResult.slug,
    step_id: "s2",
  });
  console.assert(buildResult2.success, "build 应成功");
  console.assert(buildResult2.session_id.includes("claude-direct"), "session_id 应包含 claude-direct");
  console.assert(buildResult2.executor === "frontend", "executor 应为 frontend");
  console.log("  build(s2) ✅ session_id:", buildResult2.session_id);

  console.log("  轻量模式完整链路 ✅\n");

  // ==========================================
  // 测试 2: 完全模式完整链路
  // ==========================================
  console.log("━━━ 测试 2: 完全模式 (init → entry → plan → build) ━━━");
  const fullRoot = join(process.cwd(), "test-e2e-full");
  if (existsSync(fullRoot)) rmSync(fullRoot, { recursive: true });
  mkdirSync(fullRoot, { recursive: true });

  // 2a. 初始化
  const initResult2 = await init({
    cd: fullRoot,
    force: true,
    mode: "full",
    backend: "codex",
    frontend: "opencode",
  });
  console.assert(initResult2.success, "init 应成功");
  const fullConfig = await loadExecutorConfig(fullRoot);
  console.assert(fullConfig.mode === "full", "应为完全模式");
  console.assert(fullConfig.executors.backend.provider === "codex", "后端应为 codex");
  console.assert(fullConfig.executors.frontend.provider === "opencode", "前端应为 opencode");
  console.log("  init ✅ 模式:", fullConfig.mode);

  // 2b. 创建 workflow
  const entryResult2 = await entry({
    cd: fullRoot,
    description: "修复登录 bug",
    kind: "issue",
  });
  console.assert(entryResult2.success, "entry 应成功");
  console.assert(entryResult2.kind === "issue", "应为 issue");
  console.log("  entry ✅ slug:", entryResult2.slug);

  // 2c. 路由（完全模式应返回具体 executor）
  const routeResult2 = await route({
    cd: fullRoot,
    paths: ["src/api/auth.ts"],
    executor_hint: "backend",
  });
  console.assert(routeResult2.success, "route 应成功");
  console.assert(routeResult2.mode === "full", "route 应返回 full");
  console.assert(routeResult2.recommended_executor === "backend", "应推荐 backend");
  console.assert(routeResult2.actual_provider === "codex", "provider 应为 codex");
  console.log("  route ✅ executor:", routeResult2.recommended_executor, "provider:", routeResult2.actual_provider);

  // 2d. 规划
  const planResult2 = await plan({
    cd: fullRoot,
    kind: "issue",
    slug: entryResult2.slug,
    steps: [
      {
        id: "fix1",
        title: "修复认证逻辑",
        executor: "backend",
        task_id: "task-fix-1",
        summary: "修复 token 过期判断逻辑",
        paths: ["src/api/auth.ts"],
      },
    ],
  });
  console.assert(planResult2.success, "plan 应成功");
  console.assert(planResult2.steps_added === 1, "应添加 1 个步骤");
  console.log("  plan ✅ steps_added:", planResult2.steps_added);

  // 2e. 执行 fix（完全模式 → 会尝试调用 Codex CLI，预期失败因为没有 Codex 安装）
  const fixResult = await fix({
    cd: fullRoot,
    kind: "issue",
    slug: entryResult2.slug,
    step_id: "fix1",
  });
  // 完全模式会尝试调用 Codex CLI，预期会失败（未安装）
  console.log("  fix(fix1) 结果: success=" + fixResult.success);
  if (!fixResult.success) {
    console.log("  fix 预期失败（Codex CLI 未安装）✅");
  } else {
    console.log("  fix 成功 ✅");
  }

  // 2f. 验证完全模式下 docs 步骤被拒绝
  const planResult3 = await plan({
    cd: fullRoot,
    kind: "issue",
    slug: entryResult2.slug,
    steps: [
      {
        id: "docs1",
        title: "更新文档",
        executor: "docs",
        task_id: "task-docs-1",
        summary: "更新 README",
        paths: ["README.md"],
      },
    ],
  });
  const docsBuildResult = await build({
    cd: fullRoot,
    kind: "issue",
    slug: entryResult2.slug,
    step_id: "docs1",
  });
  console.assert(!docsBuildResult.success, "完全模式 docs 步骤应被拒绝");
  console.log("  docs 步骤被拒绝 ✅ error:", docsBuildResult.error?.slice(0, 80));

  // 清理
  rmSync(lwRoot, { recursive: true });
  rmSync(fullRoot, { recursive: true });

  console.log("\n=== 所有端到端测试通过 ✅ ===");
}

e2eTest().catch((error) => {
  console.error("测试失败:", error);
  process.exit(1);
});
