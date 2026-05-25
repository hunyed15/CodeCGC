import { readFile } from "fs/promises";
import {
  readWorkflow,
  writeWorkflow,
  resolveWorkflowDir,
  listAudits,
  findStep,
  writeAudit,
} from "../runtime/artifacts.js";
import { resolveProjectRoot } from "../runtime/paths.js";
import { readRouting, classifyPaths, hasMixedOwnership } from "../runtime/routing.js";
import type { WorkflowKind } from "../../../shared/types.js";
import {
  findLatestExecAudit,
  readFilesForReview,
  collectPreviousReviews,
  generateRecommendation,
} from "./review-helpers.js";

export type ReviewDecision = "approved" | "changes-requested" | "rejected" | "reopen";

export interface ReviewIssue {
  severity: "critical" | "major" | "minor" | "info";
  category: "correctness" | "security" | "performance" | "style" | "completeness" | "other";
  file?: string;
  line?: number;
  description: string;
  suggestion?: string;
}

export interface ReviewArgs {
  kind: WorkflowKind;
  slug: string;
  step_id: string;
  decision?: ReviewDecision;
  notes?: string;
  issues?: ReviewIssue[];
  suggestions?: string[];
  acceptance_check?: Array<{
    criterion: string;
    passed: boolean;
    note?: string;
  }>;
  cd?: string;
  max_file_size_kb?: number;
}

export interface ReviewRequest {
  mode: "prepare";
  workflow: {
    kind: WorkflowKind;
    slug: string;
    created: string;
  };
  step: {
    id: string;
    title: string;
    executor: string;
    task_id: string;
    summary: string;
    paths: string[];
    constraints: string[];
    acceptance: string[];
    session_id?: string;
  };
  execution: {
    audit_file: string;
    audit_kind: string;
    timestamp: string;
    session_id: string;
    success: boolean;
    summary: string;
    changed_files: string[];
    risks: string[];
    error?: string;
  };
  file_contents: Array<{
    path: string;
    content: string;
    size_bytes: number;
    truncated: boolean;
  }>;
  previous_reviews: Array<{
    timestamp: string;
    decision: ReviewDecision;
    notes?: string;
    issues_count: number;
    issues: ReviewIssue[];
    suggestions: string[];
  }>;
  policy_checks: string[];
  checklist: {
    acceptance_criteria: string[];
    quality_aspects: string[];
    risk_categories: string[];
  };
  recommendation: string;
}

export interface ReviewResult {
  mode: "decision";
  success: boolean;
  kind: WorkflowKind;
  slug: string;
  step_id: string;
  decision: ReviewDecision;
  audit_count: number;
  policy_check_summary: string[];
  issues_summary?: { critical: number; major: number; minor: number; info: number };
  next_action: string;
  error?: string;
}

const QUALITY_ASPECTS = [
  "代码可读性（命名、注释、结构）",
  "正确性（边界情况、错误处理）",
  "安全性（输入验证、敏感信息处理）",
  "性能（避免不必要的开销）",
  "一致性（与现有代码风格保持一致）",
  "可维护性（避免不必要的复杂度）",
];

const RISK_CATEGORIES = [
  "破坏性变更（API 兼容性）",
  "数据丢失风险",
  "安全漏洞（注入、XSS、路径穿越）",
  "性能退化",
  "未处理的异常路径",
  "测试覆盖缺失",
];

export async function review(args: ReviewArgs): Promise<ReviewRequest | ReviewResult> {
  try {
    // Input validation
    if (!args.kind || !args.slug) {
      throw new Error("kind and slug are required");
    }

    if (!args.step_id || typeof args.step_id !== "string") {
      throw new Error("step_id is required and must be a string");
    }

    if (args.max_file_size_kb !== undefined) {
      if (typeof args.max_file_size_kb !== "number" || args.max_file_size_kb <= 0 || args.max_file_size_kb > 10240) {
        throw new Error("max_file_size_kb must be between 1 and 10240");
      }
    }

    if (args.issues && Array.isArray(args.issues)) {
      if (args.issues.length > 100) {
        throw new Error("issues array too large (max 100)");
      }
    }

    if (args.suggestions && Array.isArray(args.suggestions)) {
      if (args.suggestions.length > 50) {
        throw new Error("suggestions array too large (max 50)");
      }
    }

    if (args.acceptance_check && Array.isArray(args.acceptance_check)) {
      if (args.acceptance_check.length > 50) {
        throw new Error("acceptance_check array too large (max 50)");
      }
    }

    const projectRoot = resolveProjectRoot(args.cd);
    const workflow = await readWorkflow(projectRoot, args.kind, args.slug);
    const workflowDir = resolveWorkflowDir(projectRoot, workflow.kind, workflow.slug);
    const routing = await readRouting(projectRoot);

    const step = findStep(workflow, args.step_id);
    if (!step) {
      throw new Error(`步骤不存在: ${args.step_id}`);
    }

  if (step.status !== "pending" && step.status !== "skipped") {
    throw new Error(`步骤 ${args.step_id} 状态为 ${step.status}，只能审核 pending 或 skipped 状态的步骤`);
  }
  if (step.status === "skipped" && args.decision !== "reopen") {
    throw new Error(`步骤 ${args.step_id} 状态为 skipped，只能使用 reopen 决策恢复`);
  }
  if (step.status === "pending" && args.decision === "reopen") {
    throw new Error(`步骤 ${args.step_id} 状态为 pending，不需要 reopen`);
  }

  const auditFiles = await listAudits(workflowDir, args.step_id);
  if (args.decision !== "reopen" && auditFiles.length === 0) {
    throw new Error(`步骤 ${args.step_id} 没有 audit 记录，无法审核`);
  }

  const policyChecks: string[] = [];
  if (hasMixedOwnership(step.paths, routing)) {
    policyChecks.push("⚠️ 步骤路径包含 mixed/shared/unknown 路径");
  }
  const classified = classifyPaths(step.paths, routing);
  if (step.executor === "backend" && classified.has("frontend")) {
    policyChecks.push("⚠️ 后端步骤包含前端路径，可能越界");
  }
  if (step.executor === "frontend" && classified.has("backend")) {
    policyChecks.push("⚠️ 前端步骤包含后端路径，可能越界");
  }

  // prepare 模式
  if (args.decision === undefined) {
    return await preparePackage({
      workflow,
      step,
      auditFiles,
      workflowDir,
      projectRoot,
      policyChecks,
      maxFileSizeKb: args.max_file_size_kb ?? 200,
    });
  }

  // decision 模式
  if (args.decision !== "reopen" && auditFiles.length > 0) {
    const latestExec = await findLatestExecAudit(auditFiles);
    if (latestExec) {
      const auditContent = JSON.parse(await readFile(latestExec, "utf-8"));
      if (auditContent.result?.success !== true) {
        policyChecks.push(`⚠️ 最新执行 audit 显示执行未成功: ${auditContent.result?.error ?? "未知错误"}`);
      }
      if (auditContent.kind !== "manual" && !auditContent.result?.sessionId) {
        policyChecks.push("⚠️ 最新执行 audit 缺少 session_id，可能是 dry-run");
      }
    }
  }

  let nextAction = "";
  switch (args.decision) {
    case "approved":
      step.status = "done";
      await writeWorkflow(projectRoot, workflow);
      nextAction = "本步骤通过审核，可继续下一步骤";
      break;
    case "changes-requested":
      nextAction = workflow.kind === "feature"
        ? "调用 codecgc.build 重新执行此步骤"
        : "调用 codecgc.fix 重新执行此步骤";
      break;
    case "rejected":
      step.status = "skipped";
      await writeWorkflow(projectRoot, workflow);
      nextAction = "步骤已驳回，请重新规划替代方案（可用 reopen 恢复）";
      break;
    case "reopen":
      step.status = "pending";
      await writeWorkflow(projectRoot, workflow);
      nextAction = workflow.kind === "feature"
        ? "步骤已恢复为 pending，调用 codecgc.build 重新执行"
        : "步骤已恢复为 pending，调用 codecgc.fix 重新执行";
      break;
  }

  const issues = args.issues ?? [];
  const issuesSummary = {
    critical: issues.filter((i) => i.severity === "critical").length,
    major: issues.filter((i) => i.severity === "major").length,
    minor: issues.filter((i) => i.severity === "minor").length,
    info: issues.filter((i) => i.severity === "info").length,
  };

  await writeAudit(workflowDir, args.step_id, {
    step_id: args.step_id,
    kind: "review",
    decision: args.decision,
    notes: args.notes,
    timestamp: new Date().toISOString(),
    policy_checks: policyChecks,
    issues,
    suggestions: args.suggestions ?? [],
    acceptance_check: args.acceptance_check ?? [],
    issues_summary: issuesSummary,
  });

    return {
      mode: "decision",
      success: true,
      kind: workflow.kind,
      slug: workflow.slug,
      step_id: args.step_id,
      decision: args.decision,
      audit_count: auditFiles.length,
      policy_check_summary: policyChecks,
      issues_summary: issuesSummary,
      next_action: nextAction,
    };
  } catch (error) {
    return {
      mode: "decision",
      success: false,
      kind: args.kind,
      slug: args.slug,
      step_id: args.step_id,
      decision: args.decision || "approved",
      audit_count: 0,
      policy_check_summary: [],
      next_action: "",
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

async function preparePackage(opts: {
  workflow: any;
  step: any;
  auditFiles: string[];
  workflowDir: string;
  projectRoot: string;
  policyChecks: string[];
  maxFileSizeKb: number;
}): Promise<ReviewRequest> {
  const { workflow, step, auditFiles, projectRoot, policyChecks, maxFileSizeKb } = opts;

  const latestExecPath = await findLatestExecAudit(auditFiles);
  let executionInfo = {
    audit_file: "",
    audit_kind: "unknown",
    timestamp: "",
    session_id: "",
    success: false,
    summary: "",
    changed_files: [] as string[],
    risks: [] as string[],
    error: undefined as string | undefined,
  };

  if (latestExecPath) {
    const content = JSON.parse(await readFile(latestExecPath, "utf-8"));
    executionInfo = {
      audit_file: latestExecPath,
      audit_kind: content.kind || "executor",
      timestamp: content.timestamp || "",
      session_id: content.result?.sessionId || "",
      success: content.result?.success || false,
      summary: content.result?.summary || content.result?.agentMessages || "",
      changed_files: content.result?.changedFiles || [],
      risks: content.result?.risks || [],
      error: content.result?.error,
    };
  }

  const filesToRead = executionInfo.changed_files.length > 0
    ? executionInfo.changed_files
    : step.paths;

  const fileContents = await readFilesForReview(projectRoot, filesToRead, maxFileSizeKb);
  const previousReviews = await collectPreviousReviews(auditFiles);
  const recommendation = generateRecommendation(step, executionInfo, previousReviews);

  return {
    mode: "prepare",
    workflow: {
      kind: workflow.kind,
      slug: workflow.slug,
      created: workflow.created,
    },
    step: {
      id: step.id,
      title: step.title,
      executor: step.executor,
      task_id: step.task_id,
      summary: step.summary,
      paths: step.paths,
      constraints: step.constraints ?? [],
      acceptance: step.acceptance ?? [],
      session_id: step.session_id,
    },
    execution: executionInfo,
    file_contents: fileContents,
    previous_reviews: previousReviews,
    policy_checks: policyChecks,
    checklist: {
      acceptance_criteria: step.acceptance ?? [],
      quality_aspects: QUALITY_ASPECTS,
      risk_categories: RISK_CATEGORIES,
    },
    recommendation,
  };
}
