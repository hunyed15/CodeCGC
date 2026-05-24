import { existsSync } from "fs";
import {
  createWorkflow,
  resolveWorkflowDir,
  writeWorkflow,
  readWorkflow,
  inferWorkflowState,
} from "../runtime/artifacts.js";
import { resolveProjectRoot, slugify, today, workflowFile } from "../runtime/paths.js";
import type { WorkflowKind, ArtifactClass } from "../../../shared/types.js";

export interface EntryArgs {
  description: string;
  kind?: WorkflowKind;
  slug?: string;
  artifact_class?: ArtifactClass;
  cd?: string;
}

export interface EntryResult {
  success: boolean;
  kind: WorkflowKind;
  slug: string;
  workflow_dir: string;
  workflow_file: string;
  state: string;
  is_new: boolean;
  next_action: string;
  error?: string;
}

/**
 * codecgc.entry — 创建或恢复一个 workflow 入口
 *
 * 行为：
 * - 推断 kind（feature / issue），默认 feature
 * - 推断 slug：日期-需求关键词
 * - 如已存在同 slug 的 workflow，直接返回当前状态
 * - 否则创建空 workflow.yaml（无 steps，等待 plan 步骤填充）
 */
export async function entry(args: EntryArgs): Promise<EntryResult> {
  const projectRoot = resolveProjectRoot(args.cd);
  const kind: WorkflowKind = args.kind ?? inferKind(args.description);
  const slug = args.slug ?? slugify(extractKeyword(args.description), today());
  const artifactClass: ArtifactClass = args.artifact_class ?? "product";

  const dir = resolveWorkflowDir(projectRoot, kind, slug);
  const file = workflowFile(dir);
  const isExisting = existsSync(file);

  let workflow;
  if (isExisting) {
    workflow = await readWorkflow(projectRoot, kind, slug);
  } else {
    workflow = createWorkflow({ kind, slug, artifactClass });
    await writeWorkflow(projectRoot, workflow);
  }

  const state = await inferWorkflowState(projectRoot, workflow);
  const nextAction = recommendNextAction(state, kind);

  return {
    success: true,
    kind,
    slug,
    workflow_dir: dir,
    workflow_file: file,
    state,
    is_new: !isExisting,
    next_action: nextAction,
  };
}

/**
 * 启发式推断 workflow 类型
 */
function inferKind(description: string): WorkflowKind {
  const lower = description.toLowerCase();
  const issueHints = ["bug", "fix", "修复", "issue", "问题", "故障", "错误"];
  if (issueHints.some((h) => lower.includes(h))) return "issue";
  return "feature";
}

/**
 * 从需求描述中提取关键词作为 slug 基础
 */
function extractKeyword(description: string): string {
  const cleaned = description
    .replace(/[，。！？、；：""''「」（）()【】\[\]]/g, " ")
    .replace(/\s+/g, "-")
    .replace(/^-+|-+$/g, "");
  // 取前 40 个字符
  return cleaned.slice(0, 40) || "task";
}

/**
 * 根据状态推荐下一步动作
 */
function recommendNextAction(state: string, kind: WorkflowKind): string {
  switch (state) {
    case "needs-planning":
      return `调用 codecgc.plan 添加 steps（${kind} 工作流）`;
    case "awaiting-build":
      return "调用 codecgc.build 执行下一个 pending 步骤";
    case "awaiting-fix":
      return "调用 codecgc.fix 执行下一个修复步骤";
    case "awaiting-review":
      return "调用 codecgc.review 审核执行结果";
    case "closed":
      return "Workflow 已关闭，所有步骤完成";
    default:
      return "未知状态，请检查 workflow.yaml";
  }
}
