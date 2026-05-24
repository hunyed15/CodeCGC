import {
  readWorkflow,
  writeWorkflow,
  resolveWorkflowDir,
  findStep,
  writeAudit,
} from "../runtime/artifacts.js";
import { resolveProjectRoot } from "../runtime/paths.js";
import type { WorkflowKind } from "../../../shared/types.js";

export interface ManualArgs {
  kind: WorkflowKind;
  slug: string;
  step_id: string;
  summary: string;
  changed_files?: string[];
  notes?: string;
  cd?: string;
}

export interface ManualResult {
  success: boolean;
  kind: WorkflowKind;
  slug: string;
  step_id: string;
  summary: string;
  audit_file: string;
  next_action: string;
  error?: string;
}

/**
 * codecgc.manual — 手动标记 docs/orchestration 步骤完成
 *
 * 用途：
 * - docs 步骤：Claude 直接编辑文档后，调用此工具标记完成
 * - orchestration 步骤：Claude 协调多个子任务后，调用此工具标记完成
 *
 * 行为：
 * - 验证步骤 executor 必须是 docs 或 orchestration
 * - 验证步骤状态必须是 pending
 * - 写入 audit（kind: "manual"）
 * - 更新 step.session_id 为空字符串（表示无执行器 session）
 * - 保持 pending 状态，等待 review
 */
export async function manual(args: ManualArgs): Promise<ManualResult> {
  try {
    const projectRoot = resolveProjectRoot(args.cd);
    const workflow = await readWorkflow(projectRoot, args.kind, args.slug);
    const step = findStep(workflow, args.step_id);

    if (!step) {
      return {
        success: false,
        kind: args.kind,
        slug: args.slug,
        step_id: args.step_id,
        summary: "",
        audit_file: "",
        next_action: "",
        error: `步骤不存在: ${args.step_id}`,
      };
    }

    // 验证 executor 类型
    if (step.executor !== "docs" && step.executor !== "orchestration") {
      return {
        success: false,
        kind: args.kind,
        slug: args.slug,
        step_id: args.step_id,
        summary: "",
        audit_file: "",
        next_action: "",
        error: `manual 工具仅用于 docs/orchestration 步骤，当前是 ${step.executor}`,
      };
    }

    // 验证步骤状态
    if (step.status !== "pending") {
      return {
        success: false,
        kind: args.kind,
        slug: args.slug,
        step_id: args.step_id,
        summary: "",
        audit_file: "",
        next_action: "",
        error: `步骤 ${args.step_id} 状态为 ${step.status}，只能标记 pending 状态的步骤`,
      };
    }

    // 写入 audit
    const workflowDir = resolveWorkflowDir(projectRoot, workflow.kind, workflow.slug);
    const auditFile = await writeAudit(workflowDir, step.id, {
      step_id: step.id,
      executor: step.executor,
      task_id: step.task_id,
      kind: "manual",
      timestamp: new Date().toISOString(),
      result: {
        success: true,
        sessionId: "",
        summary: args.summary,
        changedFiles: args.changed_files ?? [],
        policyChecks: [],
        risks: [],
      },
      notes: args.notes,
    });

    // 更新 workflow（保持 pending，等待 review）
    step.session_id = "";
    await writeWorkflow(projectRoot, workflow);

    return {
      success: true,
      kind: args.kind,
      slug: args.slug,
      step_id: args.step_id,
      summary: args.summary,
      audit_file: auditFile,
      next_action: "调用 codecgc.review 审核手动完成的步骤",
    };
  } catch (error) {
    return {
      success: false,
      kind: args.kind,
      slug: args.slug,
      step_id: args.step_id,
      summary: "",
      audit_file: "",
      next_action: "",
      error: error instanceof Error ? error.message : String(error),
    };
  }
}
