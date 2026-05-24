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
 * codecgc.build — 执行 feature workflow 的下一个 pending 步骤
 *
 * 行为：
 * - 读取 workflow
 * - 找到下一个 pending 步骤（或指定 step_id）
 * - 调用对应执行器（backend/frontend）
 * - 写入 audit
 * - 如果成功，标记步骤 done 并更新 session_id
 * - 写回 workflow.yaml
 */
export async function build(args: BuildArgs): Promise<BuildResult> {
  const projectRoot = resolveProjectRoot(args.cd);
  const workflow = await readWorkflow(projectRoot, args.kind, args.slug);

  if (workflow.kind !== "feature") {
    throw new Error(`build 工具仅用于 feature workflow，当前是 ${workflow.kind}`);
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

  // docs/orchestration 步骤应使用 codecgc.manual 工具
  if (step.executor === "docs" || step.executor === "orchestration") {
    throw new Error(
      `步骤 ${step.id} 的 executor 是 ${step.executor}，应使用 codecgc.manual 工具手动标记完成`
    );
  }

  // 防御性检查：拒绝 step.paths 含 ../ 或绝对路径（plan 已校验，防御直接编辑 workflow.yaml）
  validateStepPaths(step.paths);

  // ✅ 修复 P2 问题 #7：前置路径归属检查（在执行器调用前）
  const routing = await readRouting(projectRoot);
  const classified = classifyPaths(step.paths, routing);
  if (step.executor === "backend" && classified.has("frontend")) {
    throw new Error(
      `后端步骤 ${step.id} 包含前端路径，拒绝执行: ${classified.get("frontend")?.join(", ")}`
    );
  }
  if (step.executor === "frontend" && classified.has("backend")) {
    throw new Error(
      `前端步骤 ${step.id} 包含后端路径，拒绝执行: ${classified.get("backend")?.join(", ")}`
    );
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

  // ✨ Phase 2：自动收集审核上下文（成功执行后）
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
}
