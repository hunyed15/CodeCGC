import {
  readWorkflow,
  writeWorkflow,
  nextPendingStep,
  markStepDone,
  resolveWorkflowDir,
  writeAudit,
} from "../runtime/artifacts.js";
import { resolveProjectRoot, validateStepPaths } from "../runtime/paths.js";
import { callExecutor } from "../runtime/executor.js";
import { readRouting, classifyPaths } from "../runtime/routing.js";
import { loadExecutorConfig } from "../../../shared/executor-config.js";
import { autoCollectReviewContext } from "./auto-review.js";
import type { ReviewRequest } from "./review.js";
import type { WorkflowKind } from "../../../shared/types.js";

export interface BuildArgs {
  kind: WorkflowKind;
  slug: string;
  step_id?: string;
  cd?: string;
  timeout_seconds?: number;
  skip_auto_review?: boolean;
}

export interface BuildResult {
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
 * codecgc.build - Execute next pending step of feature workflow
 *
 * Behavior:
 * - Read workflow
 * - Find next pending step (or specified step_id)
 * - Call corresponding executor (backend/frontend)
 * - Write audit
 * - If successful, mark step done and update session_id
 * - Write back workflow.yaml
 */
export async function build(args: BuildArgs): Promise<BuildResult> {
  try {
    // Input validation
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

    if (workflow.kind !== "feature") {
      throw new Error(`build tool is only for feature workflows, current is ${workflow.kind}`);
    }

    if (!workflow.steps || workflow.steps.length === 0) {
      throw new Error("workflow has no steps");
    }

    const step = args.step_id
      ? workflow.steps.find((s) => s.id === args.step_id)
      : nextPendingStep(workflow, true);

    if (!step) {
      throw new Error(
        args.step_id ? `Step not found: ${args.step_id}` : "No pending steps"
      );
    }

    if (step.status !== "pending") {
      throw new Error(`Step ${step.id} status is ${step.status}, not pending`);
    }

    // 读取 executor 配置
    const executorConfig = await loadExecutorConfig(projectRoot);

    // 完全模式下，docs/orchestration 步骤应使用 codecgc.manual 工具
    // 轻量模式下，Claude 可以处理所有步骤类型
    if (executorConfig.mode === "full" && (step.executor === "docs" || step.executor === "orchestration")) {
      throw new Error(
        `Step ${step.id} executor is ${step.executor}, should use codecgc.manual tool to mark as done`
      );
    }

    // Defensive check: reject step.paths containing ../ or absolute paths
    validateStepPaths(step.paths);

    // Pre-execution path ownership check（仅完全模式）
    if (executorConfig.mode === "full") {
      const routing = await readRouting(projectRoot);
      const classified = classifyPaths(step.paths, routing);
      if (step.executor === "backend" && classified.has("frontend")) {
        const frontendPaths = classified.get("frontend") || [];
        throw new Error(
          `Backend step ${step.id} contains frontend paths, refusing to execute: ${frontendPaths.slice(0, 3).join(", ")}${frontendPaths.length > 3 ? ` (and ${frontendPaths.length - 3} more)` : ""}`
        );
      }
      if (step.executor === "frontend" && classified.has("backend")) {
        const backendPaths = classified.get("backend") || [];
        throw new Error(
          `Frontend step ${step.id} contains backend paths, refusing to execute: ${backendPaths.slice(0, 3).join(", ")}${backendPaths.length > 3 ? ` (and ${backendPaths.length - 3} more)` : ""}`
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

    // After successful execution, update session_id but keep pending status (wait for review)
    if (result.success) {
      step.session_id = result.sessionId;
      await writeWorkflow(projectRoot, workflow);
    }

    // Auto-collect review context (after successful execution)
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
