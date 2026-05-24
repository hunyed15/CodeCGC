import { readFile } from "fs/promises";
import {
  readWorkflow,
  resolveWorkflowDir,
  listAudits,
  listWorkflows,
} from "../runtime/artifacts.js";
import { resolveProjectRoot } from "../runtime/paths.js";
import type { WorkflowKind } from "../../../shared/types.js";

export interface HistoryArgs {
  kind?: WorkflowKind;
  slug?: string;
  step_id?: string;
  limit?: number;
  cd?: string;
}

export interface AuditRecord {
  file: string;
  step_id: string;
  timestamp: string;
  content: Record<string, unknown>;
}

export interface WorkflowSummary {
  kind: WorkflowKind;
  slug: string;
  created: string;
  total_steps: number;
  done_steps: number;
  state: string;
}

export interface HistoryResult {
  success: boolean;
  mode: "single_workflow" | "all_workflows" | "step_audits";
  workflow?: WorkflowSummary;
  workflows?: WorkflowSummary[];
  audits?: AuditRecord[];
  recommendation: string;
  error?: string;
}

/**
 * codecgc.history — 查询历史 workflow 和 audit 记录
 *
 * 用途：
 * - 失败恢复：查看上次执行的 audit 和错误信息
 * - 状态回溯：查看所有 workflow 的历史状态
 * - 审计追踪：查看某个 step 的所有执行记录
 *
 * 模式：
 * 1. 指定 kind+slug：返回单个 workflow 的详细信息和最近的 audits
 * 2. 指定 kind+slug+step_id：返回该 step 的所有 audits
 * 3. 不指定参数：返回所有 workflow 的摘要列表
 */
export async function history(args: HistoryArgs): Promise<HistoryResult> {
  try {
    const projectRoot = resolveProjectRoot(args.cd);

    // 模式 1：查询单个 workflow
    if (args.kind && args.slug && !args.step_id) {
      return await querySingleWorkflow(projectRoot, args.kind, args.slug, args.limit);
    }

    // 模式 2：查询特定 step 的 audits
    if (args.kind && args.slug && args.step_id) {
      return await queryStepAudits(
        projectRoot,
        args.kind,
        args.slug,
        args.step_id,
        args.limit
      );
    }

    // 模式 3：查询所有 workflows
    return await queryAllWorkflows(projectRoot, args.kind);
  } catch (error) {
    return {
      success: false,
      mode: "single_workflow",
      recommendation: "查询失败",
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

/**
 * 查询单个 workflow 的详细信息和最近的 audits
 */
async function querySingleWorkflow(
  projectRoot: string,
  kind: WorkflowKind,
  slug: string,
  limit?: number
): Promise<HistoryResult> {
  const workflow = await readWorkflow(projectRoot, kind, slug);
  const dir = resolveWorkflowDir(projectRoot, kind, slug);

  const doneSteps = workflow.steps.filter((s) => s.status === "done").length;
  const summary: WorkflowSummary = {
    kind: workflow.kind,
    slug: workflow.slug,
    created: workflow.created,
    total_steps: workflow.steps.length,
    done_steps: doneSteps,
    state: doneSteps === workflow.steps.length ? "closed" : "in-progress",
  };

  // 收集所有 audits（按时间倒序）
  const allAuditFiles = await listAudits(dir);
  const sortedAudits = allAuditFiles.sort().reverse();
  const limitedAudits = limit ? sortedAudits.slice(0, limit) : sortedAudits.slice(0, 10);

  const audits: AuditRecord[] = [];
  for (const file of limitedAudits) {
    const content = JSON.parse(await readFile(file, "utf-8"));
    const filename = file.split(/[/\\]/).pop() || "";
    const match = filename.match(/^(.+?)-(\d{4}-\d{2}-\d{2}T.+)\.json$/);
    const stepId = match ? match[1] : "unknown";
    const timestamp = match ? match[2].replace(/-/g, ":") : "";
    audits.push({ file, step_id: stepId, timestamp, content });
  }

  return {
    success: true,
    mode: "single_workflow",
    workflow: summary,
    audits,
    recommendation: `Workflow ${slug} 共 ${workflow.steps.length} 步，已完成 ${doneSteps} 步，最近 ${audits.length} 条 audit 记录。`,
  };
}

/**
 * 查询特定 step 的所有 audits
 */
async function queryStepAudits(
  projectRoot: string,
  kind: WorkflowKind,
  slug: string,
  stepId: string,
  limit?: number
): Promise<HistoryResult> {
  const workflow = await readWorkflow(projectRoot, kind, slug);
  const dir = resolveWorkflowDir(projectRoot, kind, slug);
  const step = workflow.steps.find((s) => s.id === stepId);

  if (!step) {
    return {
      success: false,
      mode: "step_audits",
      recommendation: `Step ${stepId} 不存在于 workflow ${slug}`,
      error: `Step not found: ${stepId}`,
    };
  }

  const auditFiles = await listAudits(dir, stepId);
  const sortedAudits = auditFiles.sort().reverse();
  const limitedAudits = limit ? sortedAudits.slice(0, limit) : sortedAudits;

  const audits: AuditRecord[] = [];
  for (const file of limitedAudits) {
    const content = JSON.parse(await readFile(file, "utf-8"));
    const filename = file.split(/[/\\]/).pop() || "";
    const match = filename.match(/^(.+?)-(\d{4}-\d{2}-\d{2}T.+)\.json$/);
    const timestamp = match ? match[2].replace(/-/g, ":") : "";
    audits.push({ file, step_id: stepId, timestamp, content });
  }

  return {
    success: true,
    mode: "step_audits",
    audits,
    recommendation: `Step "${step.title}" (${stepId}) 共 ${audits.length} 条 audit 记录。`,
  };
}

/**
 * 查询所有 workflows 的摘要
 */
async function queryAllWorkflows(
  projectRoot: string,
  kindFilter?: WorkflowKind
): Promise<HistoryResult> {
  const allWorkflows = await listWorkflows(projectRoot);
  const filtered = kindFilter
    ? allWorkflows.filter((w) => w.kind === kindFilter)
    : allWorkflows;

  const summaries: WorkflowSummary[] = [];
  for (const { kind, slug } of filtered) {
    const workflow = await readWorkflow(projectRoot, kind, slug);
    const doneSteps = workflow.steps.filter((s) => s.status === "done").length;
    summaries.push({
      kind: workflow.kind,
      slug: workflow.slug,
      created: workflow.created,
      total_steps: workflow.steps.length,
      done_steps: doneSteps,
      state: doneSteps === workflow.steps.length ? "closed" : "in-progress",
    });
  }

  return {
    success: true,
    mode: "all_workflows",
    workflows: summaries,
    recommendation: `共 ${summaries.length} 个 workflow${kindFilter ? ` (${kindFilter})` : ""}。`,
  };
}
