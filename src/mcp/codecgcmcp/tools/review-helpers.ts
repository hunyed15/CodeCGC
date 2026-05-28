import { existsSync } from "fs";
import { readFile, stat } from "fs/promises";
import { isAbsolute, join } from "path";
import type { ReviewDecision, ReviewIssue, ReviewRequest } from "./review.js";

/**
 * 找到最新的执行类 audit（非 review）
 */
export async function findLatestExecAudit(auditFiles: string[]): Promise<string | undefined> {
  const sorted = [...auditFiles].sort();
  for (let i = sorted.length - 1; i >= 0; i--) {
    try {
      const c = JSON.parse(await readFile(sorted[i], "utf-8"));
      if (c.kind !== "review") {
        return sorted[i];
      }
    } catch {
      /* skip */
    }
  }
  return undefined;
}

/**
 * 读取文件内容用于审核（限制大小）
 */
export async function readFilesForReview(
  projectRoot: string,
  paths: string[],
  maxSizeKb: number,
): Promise<ReviewRequest["file_contents"]> {
  const results: ReviewRequest["file_contents"] = [];
  const maxBytes = maxSizeKb * 1024;

  for (const p of paths) {
    const absPath = isAbsolute(p) ? p : join(projectRoot, p);
    if (!existsSync(absPath)) {
      results.push({
        path: p,
        content: `[File not found: ${absPath}]`,
        size_bytes: 0,
        truncated: false,
      });
      continue;
    }

    try {
      const stats = await stat(absPath);
      const sizeBytes = stats.size;

      // 如果文件超过限制，只读取前 maxBytes
      if (sizeBytes > maxBytes) {
        const buffer = Buffer.alloc(maxBytes);
        const fd = await import("fs/promises").then((m) => m.open(absPath, "r"));
        try {
          await fd.read(buffer, 0, maxBytes, 0);
          const content = buffer.toString("utf-8");
          results.push({
            path: p,
            content: content + `\n\n[... truncated, total ${sizeBytes} bytes ...]`,
            size_bytes: sizeBytes,
            truncated: true,
          });
        } finally {
          await fd.close();
        }
      } else {
        const content = await readFile(absPath, "utf-8");
        results.push({
          path: p,
          content,
          size_bytes: sizeBytes,
          truncated: false,
        });
      }
    } catch (e: any) {
      results.push({
        path: p,
        content: `[Read error: ${e.message}]`,
        size_bytes: 0,
        truncated: false,
      });
    }
  }

  return results;
}

/**
 * 收集历史 review 记录
 */
export async function collectPreviousReviews(auditFiles: string[]): Promise<ReviewRequest["previous_reviews"]> {
  const reviews: ReviewRequest["previous_reviews"] = [];
  const sorted = [...auditFiles].sort();

  for (const file of sorted) {
    try {
      const content = JSON.parse(await readFile(file, "utf-8"));
      if (content.kind === "review") {
        reviews.push({
          timestamp: content.timestamp || "",
          decision: content.decision || "approved",
          notes: content.notes,
          issues_count: (content.issues ?? []).length,
          issues: content.issues ?? [],
          suggestions: content.suggestions ?? [],
        });
      }
    } catch {
      /* skip */
    }
  }

  return reviews;
}

/**
 * 生成审核推荐
 */
export function generateRecommendation(
  step: any,
  execution: ReviewRequest["execution"],
  previousReviews: ReviewRequest["previous_reviews"],
): string {
  const parts: string[] = [];

  if (!execution.success) {
    parts.push(`⚠️ 执行未成功（error: ${execution.error || "未知"}），建议 changes-requested 或 rejected`);
  }

  if (!execution.session_id && execution.audit_kind !== "manual") {
    parts.push("⚠️ 无 session_id，可能是 dry-run，需谨慎审核");
  }

  if (previousReviews.length > 0) {
    const lastReview = previousReviews[previousReviews.length - 1];
    parts.push(
      `历史已有 ${previousReviews.length} 次审核，最近一次 decision=${lastReview.decision}（${lastReview.issues_count} 个问题）`,
    );
    if (lastReview.decision === "changes-requested") {
      parts.push("请重点检查上次提出的问题是否已修复");
    }
  }

  parts.push(
    `请逐条核对 ${step.acceptance?.length ?? 0} 个验收标准，分析 ${execution.changed_files.length} 个变更文件，给出 decision（approved/changes-requested/rejected）和详细 issues 列表`,
  );

  return parts.join("\n");
}
