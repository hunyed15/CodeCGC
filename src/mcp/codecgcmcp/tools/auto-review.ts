import { readFile } from "fs/promises";
import { existsSync } from "fs";
import {
  resolveWorkflowDir,
  listAudits,
  readWorkflow,
} from "../runtime/artifacts.js";
import { resolveProjectRoot } from "../runtime/paths.js";
import { readRouting, classifyPaths, hasMixedOwnership } from "../runtime/routing.js";
import type { WorkflowKind } from "../../../shared/types.js";
import type { ReviewRequest, ReviewIssue } from "./review.js";
import {
  readFilesForReview,
  collectPreviousReviews,
  findLatestExecAudit,
  generateRecommendation,
} from "./review-helpers.js";

/**
 * 自动收集审核上下文（在 build/fix/test 成功后调用）
 *
 * 与 review prepare 模式的区别：
 * - 不需要重新读取 workflow（已在内存中）
 * - 不需要重新检查步骤状态（刚执行完）
 * - 直接使用最新的 audit 文件路径
 */
export async function autoCollectReviewContext(opts: {
  projectRoot: string;
  kind: WorkflowKind;
  slug: string;
  stepId: string;
  latestAuditFile: string;
  maxFileSizeKb?: number;
}): Promise<ReviewRequest | null> {
  const { projectRoot, kind, slug, stepId, latestAuditFile, maxFileSizeKb = 200 } = opts;

  try {
    const workflow = await readWorkflow(projectRoot, kind, slug);
    const workflowDir = resolveWorkflowDir(projectRoot, kind, slug);
    const routing = await readRouting(projectRoot);

    const step = workflow.steps.find((s: any) => s.id === stepId);
    if (!step) {
      console.warn(`[autoCollectReviewContext] 步骤不存在: ${stepId}`);
      return null;
    }

    // 路径策略检查
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

    // 读取最新执行 audit
    const auditContent = JSON.parse(await readFile(latestAuditFile, "utf-8"));
    const executionInfo = {
      audit_file: latestAuditFile,
      audit_kind: auditContent.kind || "executor",
      timestamp: auditContent.timestamp || "",
      session_id: auditContent.result?.sessionId || "",
      success: auditContent.result?.success || false,
      summary: auditContent.result?.summary || auditContent.result?.agentMessages || "",
      changed_files: auditContent.result?.changedFiles || [],
      risks: auditContent.result?.risks || [],
      error: auditContent.result?.error,
    };

    // 读取变更文件内容
    const filesToRead = executionInfo.changed_files.length > 0
      ? executionInfo.changed_files
      : step.paths;

    const fileContents = await readFilesForReview(projectRoot, filesToRead, maxFileSizeKb);

    // 收集历史 review 记录
    const auditFiles = await listAudits(workflowDir, stepId);
    const previousReviews = await collectPreviousReviews(auditFiles);

    // 生成推荐
    const recommendation = generateRecommendation(step, executionInfo, previousReviews);

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
  } catch (e: any) {
    console.warn(`[autoCollectReviewContext] 收集失败: ${e.message}`);
    return null;
  }
}
