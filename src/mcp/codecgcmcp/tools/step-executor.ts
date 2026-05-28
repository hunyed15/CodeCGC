import { loadExecutorConfig } from "../../../shared/executor-config.js";
import type { WorkflowKind } from "../../../shared/types.js";
import { nextPendingStep, readWorkflow, resolveWorkflowDir, writeAudit, writeWorkflow } from "../runtime/artifacts.js";
import { callExecutor } from "../runtime/executor.js";
import { resolveProjectRoot, validateStepPaths } from "../runtime/paths.js";
import { classifyPaths, readRouting } from "../runtime/routing.js";
import { autoCollectReviewContext } from "./auto-review.js";
import type { ReviewRequest } from "./review.js";

export interface StepExecArgs {
  kind: WorkflowKind;
  slug: string;
  step_id?: string;
  cd?: string;
  timeout_seconds?: number;
  skip_auto_review?: boolean;
}

export interface StepExecResult {
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
  review_request?: ReviewRequest | null;
  error?: string;
}

/**
 * build/fix 共享的执行逻辑
 */
export async function executeStep(args: StepExecArgs, expectedKind: WorkflowKind): Promise<StepExecResult> {
  try {
    if (!args.kind || !args.slug) {
      throw new Error("kind and slug are required");
    }

    if (args.timeout_seconds !== undefined) {
      if (typeof args.timeout_seconds !== "number" || args.timeout_seconds <= 0 || args.timeout_seconds > 3600) {
        throw new Error("timeout_seconds must be between 1 and 3600");
      }
    }

    const projectRoot = resolveProjectRoot(args.cd);
    const workflow = await readWorkflow(projectRoot, args.kind, args.slug);

    if (workflow.kind !== expectedKind) {
      throw new Error(`Expected ${expectedKind} workflow, got ${workflow.kind}`);
    }

    if (!workflow.steps || workflow.steps.length === 0) {
      throw new Error("workflow has no steps");
    }

    const step = args.step_id ? workflow.steps.find((s) => s.id === args.step_id) : nextPendingStep(workflow, true);

    if (!step) {
      throw new Error(args.step_id ? `Step not found: ${args.step_id}` : "No pending steps");
    }

    if (step.status !== "pending") {
      throw new Error(`Step ${step.id} status is ${step.status}, not pending`);
    }

    // 读取 executor 配置
    const executorConfig = await loadExecutorConfig(projectRoot);

    // 完全模式下，docs/orchestration 步骤应使用 codecgc.manual 工具
    if (executorConfig.mode === "full" && (step.executor === "docs" || step.executor === "orchestration")) {
      throw new Error(`Step ${step.id} executor is ${step.executor}, should use codecgc.manual tool to mark as done`);
    }

    // 防御性检查：拒绝 ../ 和绝对路径
    validateStepPaths(step.paths);

    // 路径归属检查（仅完全模式）
    if (executorConfig.mode === "full") {
      const routing = await readRouting(projectRoot);
      const classified = classifyPaths(step.paths, routing);
      if (step.executor === "backend" && classified.has("frontend")) {
        const frontendPaths = classified.get("frontend") || [];
        throw new Error(
          `Backend step ${step.id} contains frontend paths: ${frontendPaths.slice(0, 3).join(", ")}${frontendPaths.length > 3 ? ` (and ${frontendPaths.length - 3} more)` : ""}`,
        );
      }
      if (step.executor === "frontend" && classified.has("backend")) {
        const backendPaths = classified.get("backend") || [];
        throw new Error(
          `Frontend step ${step.id} contains backend paths: ${backendPaths.slice(0, 3).join(", ")}${backendPaths.length > 3 ? ` (and ${backendPaths.length - 3} more)` : ""}`,
        );
      }
    }

    const timeoutMs = (args.timeout_seconds ?? 600) * 1000;
    const result = await callExecutor(step, projectRoot, timeoutMs);

    const workflowDir = resolveWorkflowDir(projectRoot, workflow.kind, workflow.slug);
    const auditFile = await writeAudit(workflowDir, step.id, {
      step_id: step.id,
      executor: step.executor,
      task_id: step.task_id,
      timestamp: new Date().toISOString(),
      result,
    });

    // 执行成功后更新 session_id，保持 pending 状态等待 review
    if (result.success) {
      step.session_id = result.sessionId;
      await writeWorkflow(projectRoot, workflow);
    }

    // 自动收集审核上下文
    let reviewRequest = null;
    if (result.success && !args.skip_auto_review) {
      reviewRequest = await autoCollectReviewContext({
        projectRoot,
        kind: workflow.kind,
        slug: workflow.slug,
        stepId: step.id,
        latestAuditFile: auditFile,
      });
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
      review_request: reviewRequest,
      error: result.error,
    };
  } catch (error) {
    return {
      success: false,
      kind: args.kind,
      slug: args.slug,
      step_id: args.step_id || "",
      executor: "",
      session_id: "",
      summary: "",
      changed_files: [],
      policy_checks: [],
      risks: [],
      audit_file: "",
      review_request: null,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}
