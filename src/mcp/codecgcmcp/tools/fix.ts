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

export interface FixArgs {
  kind: WorkflowKind;
  slug: string;
  step_id?: string;
  cd?: string;
  timeout_seconds?: number;
  skip_auto_review?: boolean;
}

export interface FixResult {
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
 * codecgc.fix — 执行 issue workflow 的下一个 pending 步骤
 *
 * 与 build 区别：
 * - 仅接受 issue 类型的 workflow
 * - 语义上是修复，但调用流程相同
 */
export async function fix(args: FixArgs): Promise<FixResult> {
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

    if (workflow.kind !== "issue") {
      throw new Error(`fix 工具仅用于 issue workflow，当前是 ${workflow.kind}`);
    }

    if (!workflow.steps || workflow.steps.length === 0) {
      throw new Error("workflow has no steps");
    }

    const step = args.step_id
      ? workflow.steps.find((s) => s.id === args.step_id)
      : nextPendingStep(workflow, true);

    if (!step) {
      throw new Error(
        args.step_id ? `步骤不存在: ${args.step_id}` : "没有 pending 步骤"
      );
    }

    if (step.status !== "pending") {
      throw new Error(`步骤 ${step.id} 状态为 ${step.status}，不是 pending`);
    }

    // 读取 executor 配置
    const executorConfig = await loadExecutorConfig(projectRoot);

    // 完全模式下，docs/orchestration 步骤应使用 codecgc.manual 工具
    // 轻量模式下，Claude 可以处理所有步骤类型
    if (executorConfig.mode === "full" && (step.executor === "docs" || step.executor === "orchestration")) {
      throw new Error(
        `步骤 ${step.id} 的 executor 是 ${step.executor}，应使用 codecgc.manual 工具手动标记完成`
      );
    }

    validateStepPaths(step.paths);

    // ✅ 前置路径归属检查（仅完全模式）
    if (executorConfig.mode === "full") {
      const routing = await readRouting(projectRoot);
      const classified = classifyPaths(step.paths, routing);
      if (step.executor === "backend" && classified.has("frontend")) {
        const frontendPaths = classified.get("frontend") || [];
        throw new Error(
          `后端步骤 ${step.id} 包含前端路径，拒绝执行: ${frontendPaths.slice(0, 3).join(", ")}${frontendPaths.length > 3 ? ` (and ${frontendPaths.length - 3} more)` : ""}`
        );
      }
      if (step.executor === "frontend" && classified.has("backend")) {
        const backendPaths = classified.get("backend") || [];
        throw new Error(
          `前端步骤 ${step.id} 包含后端路径，拒绝执行: ${backendPaths.slice(0, 3).join(", ")}${backendPaths.length > 3 ? ` (and ${backendPaths.length - 3} more)` : ""}`
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

    // ✅ 修复 P0 问题 #1：执行成功后不自动标记 done，等待 review
    // 只更新 session_id，保持 pending 状态
    if (result.success) {
      step.session_id = result.sessionId;
      await writeWorkflow(projectRoot, workflow);
    }

    // ✨ Phase 2：自动收集审核上下文
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
