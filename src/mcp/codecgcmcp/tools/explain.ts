import {
  readWorkflow,
  inferWorkflowState,
  nextPendingStep,
  resolveWorkflowDir,
  listAudits,
} from "../runtime/artifacts.js";
import { resolveProjectRoot } from "../runtime/paths.js";
import type { WorkflowKind } from "../../../shared/types.js";

export interface ExplainArgs {
  kind: WorkflowKind;
  slug: string;
  cd?: string;
}

export interface ExplainResult {
  success: boolean;
  kind: WorkflowKind;
  slug: string;
  state: string;
  total_steps: number;
  pending_steps: number;
  done_steps: number;
  next_step?: {
    id: string;
    title: string;
    executor: string;
    has_audit: boolean;
  };
  next_action: string;
  recommendation: string;
  error?: string;
}

/**
 * codecgc.explain — 解释当前 workflow 状态和下一步建议
 *
 * 用途：
 * - Claude 调用此工具获取当前 workflow 状态
 * - 自动判断下一步应该调用哪个工具（plan/build/fix/review）
 * - 失败恢复时查看是否有 audit 但未标记完成
 */
export async function explain(args: ExplainArgs): Promise<ExplainResult> {
  try {
    const projectRoot = resolveProjectRoot(args.cd);
    const workflow = await readWorkflow(projectRoot, args.kind, args.slug);
    const state = await inferWorkflowState(projectRoot, workflow);

    const totalSteps = workflow.steps.length;
    const doneSteps = workflow.steps.filter((s) => s.status === "done").length;
    const pendingSteps = workflow.steps.filter((s) => s.status === "pending").length;

    const nextStep = nextPendingStep(workflow);
    let nextStepInfo;
    if (nextStep) {
      const dir = resolveWorkflowDir(projectRoot, workflow.kind, workflow.slug);
      const audits = await listAudits(dir, nextStep.id);
      nextStepInfo = {
        id: nextStep.id,
        title: nextStep.title,
        executor: nextStep.executor,
        has_audit: audits.length > 0,
      };
    }

    const { nextAction, recommendation } = generateRecommendation(
      state,
      workflow.kind,
      nextStepInfo
    );

    return {
      success: true,
      kind: workflow.kind,
      slug: workflow.slug,
      state,
      total_steps: totalSteps,
      pending_steps: pendingSteps,
      done_steps: doneSteps,
      next_step: nextStepInfo,
      next_action: nextAction,
      recommendation,
    };
  } catch (error) {
    return {
      success: false,
      kind: args.kind,
      slug: args.slug,
      state: "error",
      total_steps: 0,
      pending_steps: 0,
      done_steps: 0,
      next_action: "无法读取 workflow",
      recommendation: "请检查 workflow 是否存在",
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

/**
 * 生成下一步动作建议
 */
function generateRecommendation(
  state: string,
  kind: WorkflowKind,
  nextStep?: { id: string; title: string; executor: string; has_audit: boolean }
): { nextAction: string; recommendation: string } {
  switch (state) {
    case "needs-planning":
      return {
        nextAction: "codecgc.plan",
        recommendation: `Workflow 无步骤，需要调用 codecgc.plan 添加 steps。`,
      };

    case "awaiting-build":
      if (!nextStep) {
        return {
          nextAction: "none",
          recommendation: "所有步骤已完成，workflow 可关闭。",
        };
      }
      return {
        nextAction: "codecgc.build",
        recommendation: `下一步：执行 step "${nextStep.title}" (${nextStep.executor})，调用 codecgc.build。`,
      };

    case "awaiting-fix":
      if (!nextStep) {
        return {
          nextAction: "none",
          recommendation: "所有修复步骤已完成，workflow 可关闭。",
        };
      }
      return {
        nextAction: "codecgc.fix",
        recommendation: `下一步：执行修复 step "${nextStep.title}" (${nextStep.executor})，调用 codecgc.fix。`,
      };

    case "awaiting-review":
      if (!nextStep) {
        return {
          nextAction: "none",
          recommendation: "状态异常：awaiting-review 但无 pending 步骤。",
        };
      }
      return {
        nextAction: "codecgc.review",
        recommendation: `Step "${nextStep.title}" 已有 audit，需要调用 codecgc.review 审核执行结果。`,
      };

    case "closed":
      return {
        nextAction: "none",
        recommendation: "Workflow 已关闭，所有步骤完成。",
      };

    default:
      return {
        nextAction: "unknown",
        recommendation: `未知状态: ${state}`,
      };
  }
}
