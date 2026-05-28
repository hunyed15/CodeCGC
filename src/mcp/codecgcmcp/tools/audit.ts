import { readFile } from "fs/promises";
import type { WorkflowKind } from "../../../shared/types.js";
import {
  inferWorkflowState,
  listAudits,
  listWorkflows,
  readWorkflow,
  resolveWorkflowDir,
} from "../runtime/artifacts.js";
import { resolveProjectRoot } from "../runtime/paths.js";

export interface AuditArgs {
  cd?: string;
  check?: "completeness" | "stale" | "all";
  stale_days?: number;
}

export interface AuditIssue {
  type: string;
  severity: "error" | "warn" | "info";
  kind: WorkflowKind;
  slug: string;
  problem: string;
  recommendation: string;
  details?: Record<string, unknown>;
}

export interface AuditResult {
  success: boolean;
  project_root: string;
  total_workflows: number;
  issues: AuditIssue[];
  summary: {
    errors: number;
    warnings: number;
    info: number;
  };
  recommendation: string;
  error?: string;
}

/**
 * codecgc.audit — 工作流完整性审计
 *
 * 检查项：
 * 1. completeness（完整性）：
 *    - 有 plan 但从未 build/fix
 *    - 有 audit 但从未 review（卡在 awaiting-review）
 *    - steps 为空（needs-planning 但长期未规划）
 *
 * 2. stale（陈旧性）：
 *    - awaiting-review 超过 N 天
 *    - awaiting-build/fix 超过 N 天
 *    - needs-planning 超过 N 天
 *
 * 3. all：以上全部检查
 */
export async function audit(args: AuditArgs): Promise<AuditResult> {
  try {
    // Input validation
    if (args.stale_days !== undefined) {
      if (typeof args.stale_days !== "number" || args.stale_days < 1 || args.stale_days > 365) {
        throw new Error("stale_days must be between 1 and 365");
      }
    }

    const projectRoot = resolveProjectRoot(args.cd);
    const check = args.check ?? "all";
    const staleDays = args.stale_days ?? 7;

    const allWorkflows = await listWorkflows(projectRoot);
    const issues: AuditIssue[] = [];

    for (const { kind, slug } of allWorkflows) {
      const workflow = await readWorkflow(projectRoot, kind, slug);
      const state = await inferWorkflowState(projectRoot, workflow);
      const dir = resolveWorkflowDir(projectRoot, kind, slug);

      // 检查完整性
      if (check === "completeness" || check === "all") {
        // 1. 空 workflow（needs-planning 但长期未规划）
        if (workflow.steps.length === 0) {
          const age = getWorkflowAgeDays(workflow.created);
          if (age > 3) {
            issues.push({
              type: "empty_workflow",
              severity: "warn",
              kind,
              slug,
              problem: `Workflow 创建 ${age} 天，仍无 steps`,
              recommendation: "调用 codecgc.plan 添加步骤，或删除此 workflow",
              details: { created: workflow.created, age_days: age },
            });
          }
        }

        // 2. 有 steps 但从未执行（所有 step 都是 pending，且无 audit）
        if (workflow.steps.length > 0) {
          const allPending = workflow.steps.every((s) => s.status === "pending");
          const hasAnyAudit = (await listAudits(dir)).length > 0;
          if (allPending && !hasAnyAudit) {
            const age = getWorkflowAgeDays(workflow.created);
            if (age > 2) {
              issues.push({
                type: "never_executed",
                severity: "warn",
                kind,
                slug,
                problem: `有 ${workflow.steps.length} 个 steps，但从未执行`,
                recommendation: `调用 codecgc.${kind === "feature" ? "build" : "fix"} 开始执行`,
                details: { total_steps: workflow.steps.length, age_days: age },
              });
            }
          }
        }

        // 3. 有 audit 但未 review（awaiting-review）
        if (state === "awaiting-review") {
          const pendingStep = workflow.steps.find((s) => s.status === "pending");
          if (pendingStep) {
            const audits = await listAudits(dir, pendingStep.id);
            if (audits.length > 0) {
              // 过滤出执行类 audit（非 review）取最新的
              const sortedAudits = audits.sort();
              let latestExecAudit: string | undefined;
              for (let i = sortedAudits.length - 1; i >= 0; i--) {
                try {
                  const c = JSON.parse(await readFile(sortedAudits[i], "utf-8"));
                  if (c.kind !== "review") {
                    latestExecAudit = sortedAudits[i];
                    break;
                  }
                } catch {
                  /* skip */
                }
              }
              if (latestExecAudit) {
                const auditAge = await getFileAgeDays(latestExecAudit);
                issues.push({
                  type: "pending_review",
                  severity: auditAge > staleDays ? "error" : "warn",
                  kind,
                  slug,
                  problem: `Step "${pendingStep.title}" 有 audit 但未 review（${auditAge} 天）`,
                  recommendation: "调用 codecgc.review 审核执行结果",
                  details: {
                    step_id: pendingStep.id,
                    audit_count: audits.length,
                    audit_age_days: auditAge,
                  },
                });
              }
            }
          }
        }
      }

      // 检查陈旧性
      if (check === "stale" || check === "all") {
        const age = getWorkflowAgeDays(workflow.created);

        if (state === "needs-planning" && age > staleDays) {
          issues.push({
            type: "stale_planning",
            severity: "warn",
            kind,
            slug,
            problem: `Workflow 处于 needs-planning 状态 ${age} 天`,
            recommendation: "调用 codecgc.plan 或删除此 workflow",
            details: { age_days: age },
          });
        }

        if ((state === "awaiting-build" || state === "awaiting-fix") && age > staleDays) {
          const pendingStep = workflow.steps.find((s) => s.status === "pending");
          issues.push({
            type: "stale_execution",
            severity: "warn",
            kind,
            slug,
            problem: `Workflow 处于 ${state} 状态 ${age} 天`,
            recommendation: `调用 codecgc.${kind === "feature" ? "build" : "fix"} 继续执行`,
            details: {
              age_days: age,
              next_step: pendingStep?.title,
            },
          });
        }
      }
    }

    const errors = issues.filter((i) => i.severity === "error").length;
    const warnings = issues.filter((i) => i.severity === "warn").length;
    const info = issues.filter((i) => i.severity === "info").length;

    const recommendation = generateAuditRecommendation(issues, allWorkflows.length);

    return {
      success: true,
      project_root: projectRoot,
      total_workflows: allWorkflows.length,
      issues,
      summary: { errors, warnings, info },
      recommendation,
    };
  } catch (error) {
    return {
      success: false,
      project_root: args.cd ?? process.cwd(),
      total_workflows: 0,
      issues: [],
      summary: { errors: 0, warnings: 0, info: 0 },
      recommendation: "审计失败",
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

function getWorkflowAgeDays(created: string): number {
  const createdDate = new Date(created);
  const now = new Date();
  const diffMs = now.getTime() - createdDate.getTime();
  return Math.floor(diffMs / (1000 * 60 * 60 * 24));
}

async function getFileAgeDays(filePath: string): Promise<number> {
  try {
    const content = await readFile(filePath, "utf-8");
    const data = JSON.parse(content);
    const timestamp = data.timestamp || data.created || "";
    if (!timestamp) return 0;
    const fileDate = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - fileDate.getTime();
    return Math.floor(diffMs / (1000 * 60 * 60 * 24));
  } catch {
    return 0;
  }
}

function generateAuditRecommendation(issues: AuditIssue[], totalWorkflows: number): string {
  if (issues.length === 0) {
    return `审计通过，${totalWorkflows} 个 workflow 无异常。`;
  }

  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity === "warn");

  const parts: string[] = [];
  if (errors.length > 0) {
    parts.push(`${errors.length} 个严重问题（需立即处理）`);
  }
  if (warnings.length > 0) {
    parts.push(`${warnings.length} 个警告（建议处理）`);
  }

  return `发现 ${parts.join("、")}。优先处理 pending_review 和 stale_planning。`;
}
