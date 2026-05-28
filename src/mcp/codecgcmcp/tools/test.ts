import type { WorkflowKind } from "../../../shared/types.js";
import { markStepDone, readWorkflow, resolveWorkflowDir, writeAudit, writeWorkflow } from "../runtime/artifacts.js";
import { callExecutor } from "../runtime/executor.js";
import { resolveProjectRoot, validateStepPaths } from "../runtime/paths.js";
import { classifyPaths, readRouting } from "../runtime/routing.js";

export interface TestArgs {
  kind: WorkflowKind;
  slug: string;
  step_id: string;
  cd?: string;
  timeout_seconds?: number;
}

export interface TestResult {
  success: boolean;
  kind: WorkflowKind;
  slug: string;
  step_id: string;
  executor: string;
  session_id: string;
  summary: string;
  changed_files: string[];
  policy_checks: string[];
  risks: string[];
  audit_file: string;
  error?: string;
}

/**
 * codecgc.test — 执行测试步骤
 *
 * 与 build/fix 区别：
 * - 必须显式指定 step_id（不从 pending 自动选）
 * - 步骤的 task_id 通常以 "test-" 前缀，summary 描述测试目标
 * - 路径通常指向 tests/ 或 *_test.* 文件
 * - 路由到与代码同侧的执行器（后端测试 → backend，前端测试 → frontend）
 */
export async function test(args: TestArgs): Promise<TestResult> {
  try {
    // Input validation
    if (!args.kind || !args.slug) {
      throw new Error("kind and slug are required");
    }

    if (!args.step_id || typeof args.step_id !== "string") {
      throw new Error("step_id is required and must be a string");
    }

    if (args.timeout_seconds !== undefined) {
      if (typeof args.timeout_seconds !== "number" || args.timeout_seconds <= 0 || args.timeout_seconds > 3600) {
        throw new Error("timeout_seconds must be between 1 and 3600");
      }
    }

    const projectRoot = resolveProjectRoot(args.cd);
    const workflow = await readWorkflow(projectRoot, args.kind, args.slug);

    if (!workflow.steps || workflow.steps.length === 0) {
      throw new Error("workflow has no steps");
    }

    const step = workflow.steps.find((s) => s.id === args.step_id);
    if (!step) {
      throw new Error(`步骤不存在: ${args.step_id}`);
    }

    if (step.status !== "pending") {
      throw new Error(`步骤 ${step.id} 状态为 ${step.status}，不是 pending`);
    }

    // docs/orchestration 步骤应使用 codecgc.manual 工具
    if (step.executor === "docs" || step.executor === "orchestration") {
      throw new Error(`步骤 ${step.id} 的 executor 是 ${step.executor}，应使用 codecgc.manual 工具手动标记完成`);
    }

    validateStepPaths(step.paths);

    // ✅ 修复 P2 问题 #7：前置路径归属检查（在执行器调用前）
    const routing = await readRouting(projectRoot);
    const classified = classifyPaths(step.paths, routing);
    if (step.executor === "backend" && classified.has("frontend")) {
      const frontendPaths = classified.get("frontend") || [];
      throw new Error(
        `后端测试步骤 ${step.id} 包含前端路径，拒绝执行: ${frontendPaths.slice(0, 3).join(", ")}${frontendPaths.length > 3 ? ` (and ${frontendPaths.length - 3} more)` : ""}`,
      );
    }
    if (step.executor === "frontend" && classified.has("backend")) {
      const backendPaths = classified.get("backend") || [];
      throw new Error(
        `前端测试步骤 ${step.id} 包含后端路径，拒绝执行: ${backendPaths.slice(0, 3).join(", ")}${backendPaths.length > 3 ? ` (and ${backendPaths.length - 3} more)` : ""}`,
      );
    }

    const timeoutMs = (args.timeout_seconds ?? 600) * 1000;
    const result = await callExecutor(step, projectRoot, timeoutMs);

    const workflowDir = resolveWorkflowDir(projectRoot, workflow.kind, workflow.slug);
    const auditFile = await writeAudit(workflowDir, step.id, {
      step_id: step.id,
      executor: step.executor,
      task_id: step.task_id,
      kind: "test",
      timestamp: new Date().toISOString(),
      result,
    });

    // ✅ 修复 P0 问题 #1：执行成功后不自动标记 done，等待 review
    // 只更新 session_id，保持 pending 状态
    if (result.success) {
      step.session_id = result.sessionId;
      await writeWorkflow(projectRoot, workflow);
    }

    return {
      success: result.success,
      kind: workflow.kind,
      slug: workflow.slug,
      step_id: step.id,
      executor: step.executor,
      session_id: result.sessionId,
      summary: result.summary,
      changed_files: result.changedFiles,
      policy_checks: result.policyChecks,
      risks: result.risks,
      audit_file: auditFile,
      error: result.error,
    };
  } catch (error) {
    return {
      success: false,
      kind: args.kind,
      slug: args.slug,
      step_id: args.step_id,
      executor: "",
      session_id: "",
      summary: "",
      changed_files: [],
      policy_checks: [],
      risks: [],
      audit_file: "",
      error: error instanceof Error ? error.message : String(error),
    };
  }
}
