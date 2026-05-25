import { existsSync } from "fs";
import { readdir, readFile, writeFile, unlink } from "fs/promises";
import { join } from "path";
import { randomBytes } from "crypto";
import { readYaml, writeYaml } from "../../../shared/yaml.js";
import type {
  Workflow,
  WorkflowStep,
  WorkflowKind,
  ArtifactClass,
} from "../../../shared/types.js";
import {
  codecgcRoot,
  featureDir,
  issueDir,
  workflowFile,
  auditDir,
  ensureDir,
  today,
} from "./paths.js";

/**
 * 创建一个新的空 workflow
 */
export function createWorkflow(opts: {
  kind: WorkflowKind;
  slug: string;
  artifactClass?: ArtifactClass;
}): Workflow {
  return {
    version: 1,
    kind: opts.kind,
    slug: opts.slug,
    created: today(),
    artifact_class: opts.artifactClass ?? "product",
    steps: [],
  };
}

/**
 * 根据 kind+slug 解析 workflow 目录
 */
export function resolveWorkflowDir(
  projectRoot: string,
  kind: WorkflowKind,
  slug: string
): string {
  return kind === "feature" ? featureDir(projectRoot, slug) : issueDir(projectRoot, slug);
}

/**
 * 读取 workflow.yaml
 */
export async function readWorkflow(
  projectRoot: string,
  kind: WorkflowKind,
  slug: string
): Promise<Workflow> {
  try {
    const dir = resolveWorkflowDir(projectRoot, kind, slug);
    const file = workflowFile(dir);
    if (!existsSync(file)) {
      throw new Error(`Workflow 不存在: ${file}`);
    }
    const wf = await readYaml<Workflow>(file);
    if (!wf || typeof wf !== "object") {
      throw new Error(`无效的 workflow.yaml: ${file}`);
    }
    if (!Array.isArray(wf.steps)) wf.steps = [];
    return wf;
  } catch (error) {
    throw new Error(`读取 workflow 失败: ${error instanceof Error ? error.message : String(error)}`);
  }
}

/**
 * 写入 workflow.yaml（自动创建目录）
 */
export async function writeWorkflow(
  projectRoot: string,
  workflow: Workflow
): Promise<string> {
  try {
    if (!workflow || typeof workflow !== "object") {
      throw new Error("workflow must be a valid object");
    }
    if (!workflow.kind || !workflow.slug) {
      throw new Error("workflow.kind and workflow.slug are required");
    }
    const dir = resolveWorkflowDir(projectRoot, workflow.kind, workflow.slug);
    await ensureDir(dir);
    await ensureDir(auditDir(dir));
    const file = workflowFile(dir);
    await withFileLock(file, async () => {
      await writeYaml(file, workflow);
    });
    return file;
  } catch (error) {
    throw new Error(`写入 workflow 失败: ${error instanceof Error ? error.message : String(error)}`);
  }
}

/**
 * 简易文件锁：防止并发 read-modify-write 覆盖
 * 使用 .lock 文件 + 重试机制
 */
async function withFileLock<T>(filePath: string, fn: () => Promise<T>): Promise<T> {
  const lockFile = filePath + ".lock";
  const maxRetries = 10;
  const retryDelay = 100;

  for (let i = 0; i < maxRetries; i++) {
    try {
      await writeFile(lockFile, String(process.pid), { flag: "wx" });
      break;
    } catch (err: any) {
      if (err.code === "EEXIST") {
        if (i === maxRetries - 1) {
          // 最后一次重试失败，强制获取锁（防止死锁）
          await writeFile(lockFile, String(process.pid));
          break;
        }
        await new Promise((r) => setTimeout(r, retryDelay));
      } else {
        throw err;
      }
    }
  }

  try {
    return await fn();
  } finally {
    try { await unlink(lockFile); } catch { /* ignore */ }
  }
}

/**
 * 添加步骤
 */
export function addStep(workflow: Workflow, step: WorkflowStep): Workflow {
  workflow.steps.push(step);
  return workflow;
}

/**
 * 根据 ID 查找步骤
 */
export function findStep(workflow: Workflow, stepId: string): WorkflowStep | undefined {
  return workflow.steps.find((s) => s.id === stepId);
}

/**
 * 标记步骤完成
 */
export function markStepDone(workflow: Workflow, stepId: string, sessionId?: string): Workflow {
  const step = findStep(workflow, stepId);
  if (!step) throw new Error(`步骤不存在: ${stepId}`);
  step.status = "done";
  if (sessionId) step.session_id = sessionId;
  return workflow;
}

/**
 * 找下一个 pending 的步骤
 *
 * @param skipManual 跳过 docs/orchestration 步骤（这些步骤应使用 codecgc.manual 工具）
 */
export function nextPendingStep(workflow: Workflow, skipManual = false): WorkflowStep | undefined {
  return workflow.steps.find((s) => {
    if (s.status !== "pending") return false;
    if (skipManual && (s.executor === "docs" || s.executor === "orchestration")) return false;
    return true;
  });
}

/**
 * 列出所有 workflow（feature 和 issue）
 */
export async function listWorkflows(
  projectRoot: string
): Promise<Array<{ kind: WorkflowKind; slug: string; dir: string }>> {
  const result: Array<{ kind: WorkflowKind; slug: string; dir: string }> = [];

  for (const kind of ["feature", "issue"] as WorkflowKind[]) {
    const baseDir = kind === "feature"
      ? join(codecgcRoot(projectRoot), "features")
      : join(codecgcRoot(projectRoot), "issues");
    if (!existsSync(baseDir)) continue;

    const entries = await readdir(baseDir, { withFileTypes: true });
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const dir = join(baseDir, entry.name);
      if (existsSync(workflowFile(dir))) {
        result.push({ kind, slug: entry.name, dir });
      }
    }
  }
  return result;
}

/**
 * 写入审计日志（每次执行器调用一份）
 */
export async function writeAudit(
  workflowDir: string,
  stepId: string,
  data: Record<string, unknown>
): Promise<string> {
  try {
    if (!stepId || typeof stepId !== "string") {
      throw new Error("stepId is required and must be a string");
    }
    if (stepId.length > 100) {
      throw new Error("stepId too long (max 100 characters)");
    }
    if (!data || typeof data !== "object") {
      throw new Error("data must be a valid object");
    }

    // Validate data size (prevent DoS)
    const jsonStr = JSON.stringify(data, null, 2);
    const sizeKb = Buffer.byteLength(jsonStr, "utf-8") / 1024;
    if (sizeKb > 10240) {
      throw new Error(`audit data too large (${sizeKb.toFixed(0)}KB, max 10MB)`);
    }

    const dir = auditDir(workflowDir);
    await ensureDir(dir);
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const rand = randomBytes(3).toString("hex");
    const file = join(dir, `${stepId}-${timestamp}-${rand}.json`);
    await writeFile(file, jsonStr, "utf-8");
    return file;
  } catch (error) {
    throw new Error(`写入 audit 失败: ${error instanceof Error ? error.message : String(error)}`);
  }
}

/**
 * 列出某个 step 的所有 audit
 */
export async function listAudits(workflowDir: string, stepId?: string): Promise<string[]> {
  try {
    const dir = auditDir(workflowDir);
    if (!existsSync(dir)) return [];
    const entries = await readdir(dir);
    const filtered = entries
      .filter((f) => f.endsWith(".json"))
      .filter((f) => !stepId || f.startsWith(`${stepId}-`))
      .map((f) => join(dir, f));

    // Limit result size (prevent DoS)
    if (filtered.length > 1000) {
      throw new Error(`Too many audit files (${filtered.length}, max 1000)`);
    }

    return filtered;
  } catch (error) {
    throw new Error(`列出 audit 失败: ${error instanceof Error ? error.message : String(error)}`);
  }
}

/**
 * 推断 workflow 状态
 *
 * ✅ 修复 P0 问题 #4：重新设计状态推断逻辑
 *
 * 新逻辑：
 * 1. 优先检查是否有 pending 步骤且最新 audit 是执行类（awaiting-review）
 * 2. 再检查是否有 pending 步骤但无执行类 audit（awaiting-build/fix）
 * 3. 最后检查是否全部完成（closed）
 */
export type WorkflowState =
  | "needs-planning"
  | "awaiting-build"
  | "awaiting-fix"
  | "awaiting-review"
  | "closed";

export async function inferWorkflowState(
  projectRoot: string,
  workflow: Workflow
): Promise<WorkflowState> {
  if (workflow.steps.length === 0) return "needs-planning";

  const pending = nextPendingStep(workflow);
  if (!pending) return "closed";

  // ✅ 关键修复：检查最新 audit 是否为执行类（非 review）
  // 如果最新 audit 是 review 类型，说明已经审核过，应该回到 awaiting-build/fix
  const dir = resolveWorkflowDir(projectRoot, workflow.kind, workflow.slug);
  const audits = await listAudits(dir, pending.id);

  if (audits.length === 0) {
    return workflow.kind === "feature" ? "awaiting-build" : "awaiting-fix";
  }

  // 按时间排序，取最新的 audit
  const sortedAudits = audits.sort();
  const latestAuditFile = sortedAudits[sortedAudits.length - 1];

  try {
    const content = JSON.parse(await readFile(latestAuditFile, "utf-8"));
    // 如果最新 audit 是 review 类型，说明已审核，回到执行状态
    if (content.kind === "review") {
      return workflow.kind === "feature" ? "awaiting-build" : "awaiting-fix";
    }
    // 如果最新 audit 是执行类型但执行失败，回到执行状态（应重试而非 review）
    if (content.result && content.result.success === false) {
      return workflow.kind === "feature" ? "awaiting-build" : "awaiting-fix";
    }
    // 如果最新 audit 是执行类型且成功（或无 result 字段），等待审核
    return "awaiting-review";
  } catch {
    // 无法解析，默认认为需要执行
    return workflow.kind === "feature" ? "awaiting-build" : "awaiting-fix";
  }
}
