import type { WorkflowKind } from "../../../shared/types.js";
import {
  inferWorkflowState,
  listAudits,
  listWorkflows,
  readWorkflow,
  resolveWorkflowDir,
} from "../runtime/artifacts.js";
import { resolveProjectRoot } from "../runtime/paths.js";

export interface StatusArgs {
  cd?: string;
  filter?: "active" | "closed" | "all";
}

export interface WorkflowStatusEntry {
  kind: WorkflowKind;
  slug: string;
  state: string;
  total_steps: number;
  done_steps: number;
  pending_step?: {
    id: string;
    title: string;
    executor: string;
    has_audit: boolean;
  };
}

export interface StatusResult {
  success: boolean;
  project_root: string;
  total: number;
  active: number;
  closed: number;
  workflows: WorkflowStatusEntry[];
  recommendation: string;
  error?: string;
}

/**
 * codecgc.status — 显示所有 workflow 状态摘要
 *
 * 用途：
 * - 项目级总览：一眼看清所有 workflow 进展
 * - 找出阻塞项：哪些 workflow 处于 awaiting-review
 * - 失败排查：哪些 workflow 在 needs-planning
 *
 * 区别于 explain：
 * - explain 是单个 workflow 的详细解释
 * - status 是所有 workflow 的批量摘要
 */
export async function status(args: StatusArgs): Promise<StatusResult> {
  try {
    const projectRoot = resolveProjectRoot(args.cd);
    const filter = args.filter ?? "all";

    const allWorkflows = await listWorkflows(projectRoot);
    const entries: WorkflowStatusEntry[] = [];

    for (const { kind, slug } of allWorkflows) {
      const workflow = await readWorkflow(projectRoot, kind, slug);
      const state = await inferWorkflowState(projectRoot, workflow);

      if (filter === "active" && state === "closed") continue;
      if (filter === "closed" && state !== "closed") continue;

      const totalSteps = workflow.steps.length;
      const doneSteps = workflow.steps.filter((s) => s.status === "done").length;
      const pending = workflow.steps.find((s) => s.status === "pending");

      let pendingStepInfo;
      if (pending) {
        const dir = resolveWorkflowDir(projectRoot, kind, slug);
        const audits = await listAudits(dir, pending.id);
        pendingStepInfo = {
          id: pending.id,
          title: pending.title,
          executor: pending.executor,
          has_audit: audits.length > 0,
        };
      }

      entries.push({
        kind,
        slug,
        state,
        total_steps: totalSteps,
        done_steps: doneSteps,
        pending_step: pendingStepInfo,
      });
    }

    const closed = entries.filter((e) => e.state === "closed").length;
    const active = entries.length - closed;

    const recommendation = generateStatusRecommendation(entries);

    return {
      success: true,
      project_root: projectRoot,
      total: entries.length,
      active,
      closed,
      workflows: entries,
      recommendation,
    };
  } catch (error) {
    return {
      success: false,
      project_root: args.cd ?? process.cwd(),
      total: 0,
      active: 0,
      closed: 0,
      workflows: [],
      recommendation: "状态查询失败",
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

function generateStatusRecommendation(entries: WorkflowStatusEntry[]): string {
  if (entries.length === 0) {
    return "项目无 workflow，可调用 codecgc.entry 创建第一个。";
  }

  const needsPlanning = entries.filter((e) => e.state === "needs-planning");
  const awaitingReview = entries.filter((e) => e.state === "awaiting-review");
  const awaitingBuild = entries.filter((e) => e.state === "awaiting-build");
  const awaitingFix = entries.filter((e) => e.state === "awaiting-fix");

  const parts: string[] = [];
  if (awaitingReview.length > 0) {
    parts.push(`${awaitingReview.length} 个待审核（优先处理）`);
  }
  if (awaitingBuild.length > 0) {
    parts.push(`${awaitingBuild.length} 个待执行 (build)`);
  }
  if (awaitingFix.length > 0) {
    parts.push(`${awaitingFix.length} 个待修复 (fix)`);
  }
  if (needsPlanning.length > 0) {
    parts.push(`${needsPlanning.length} 个待规划`);
  }

  return parts.length > 0 ? parts.join("；") : "所有 workflow 已关闭。";
}
