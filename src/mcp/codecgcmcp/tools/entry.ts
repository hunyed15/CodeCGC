import { existsSync } from "fs";
import type { ArtifactClass, WorkflowKind } from "../../../shared/types.js";
import {
  createWorkflow,
  inferWorkflowState,
  readWorkflow,
  resolveWorkflowDir,
  writeWorkflow,
} from "../runtime/artifacts.js";
import { resolveProjectRoot, slugify, today, workflowFile } from "../runtime/paths.js";

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
 * codecgc.entry - Create or restore a workflow entry
 *
 * Behavior:
 * - Infer kind (feature / issue), default feature
 * - Infer slug: date-requirement-keywords
 * - If workflow with same slug exists, return current state
 * - Otherwise create empty workflow.yaml (no steps, waiting for plan phase)
 */
export async function entry(args: EntryArgs): Promise<EntryResult> {
  try {
    // Input validation
    if (!args.description || typeof args.description !== "string") {
      throw new Error("description is required and must be a string");
    }

    const trimmed = args.description.trim();
    if (trimmed.length === 0) {
      throw new Error("description cannot be empty");
    }

    if (trimmed.length > 500) {
      throw new Error("description too long (max 500 characters)");
    }

    // Validate slug if provided
    if (args.slug) {
      if (typeof args.slug !== "string" || args.slug.length === 0) {
        throw new Error("slug must be a non-empty string");
      }
      if (args.slug.length > 100) {
        throw new Error("slug too long (max 100 characters)");
      }
      if (!/^[a-z0-9-]+$/.test(args.slug)) {
        throw new Error("slug must contain only lowercase letters, numbers, and hyphens");
      }
    }

    const projectRoot = resolveProjectRoot(args.cd);
    const kind: WorkflowKind = args.kind ?? inferKind(trimmed);
    const slug = args.slug ?? slugify(extractKeyword(trimmed), today());
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
  } catch (error) {
    return {
      success: false,
      kind: args.kind ?? "feature",
      slug: args.slug ?? "unknown",
      workflow_dir: "",
      workflow_file: "",
      state: "error",
      is_new: false,
      next_action: "",
      error: error instanceof Error ? error.message : String(error),
    };
  }
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
 * Extract keywords from requirement description as slug base
 */
function extractKeyword(description: string): string {
  const cleaned = description
    .replace(/[，。！？、；：""''「」（）()【】[\]]/g, " ")
    .replace(/\s+/g, "-")
    .replace(/^-+|-+$/g, "");

  // Take first 40 characters, fallback to "task" if empty
  const result = cleaned.slice(0, 40).trim();
  return result.length > 0 ? result : "task";
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
