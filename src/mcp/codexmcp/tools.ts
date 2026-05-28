import * as path from "path";
import type { BackendTaskOptions, TaskResult } from "../../shared/types.js";
import { runCodexSession } from "./executor.js";

// 前端路径模式（后端执行器拒绝这些路径）
const FRONTEND_PATTERNS = [
  /\.(tsx|jsx|css|scss|sass|less|vue|svelte)$/i,
  /\/components\//,
  /\/pages\//,
  /\/views\//,
  /\/styles?\//,
  /\/(app|web|frontend|client)\/src\//,
  /\/public\//,
  /\/assets\//,
];

function validateBackendPaths(paths: string[]): void {
  const violations = paths.filter((p) => FRONTEND_PATTERNS.some((re) => re.test(p.replace(/\\/g, "/"))));
  if (violations.length > 0) {
    throw new Error(`后端执行器拒绝以下疑似前端路径：${violations.join(", ")}`);
  }
}

export async function executeBackendTask(opts: BackendTaskOptions): Promise<TaskResult> {
  const policyChecks: string[] = [];
  const risks: string[] = [];

  // Input validation
  if (!opts.taskId || typeof opts.taskId !== "string") {
    return {
      success: false,
      taskId: opts.taskId || "",
      sessionId: "",
      summary: "task_id is required and must be a string",
      agentMessages: "",
      changedFiles: [],
      policyChecks,
      risks,
      error: "task_id is required and must be a string",
    };
  }

  if (!opts.taskSummary || typeof opts.taskSummary !== "string") {
    return {
      success: false,
      taskId: opts.taskId,
      sessionId: "",
      summary: "task_summary is required and must be a string",
      agentMessages: "",
      changedFiles: [],
      policyChecks,
      risks,
      error: "task_summary is required and must be a string",
    };
  }

  // 1. 路径非空校验
  if (!opts.targetPaths || opts.targetPaths.length === 0) {
    return {
      success: false,
      taskId: opts.taskId,
      sessionId: "",
      summary: "target_paths 不能为空",
      agentMessages: "",
      changedFiles: [],
      policyChecks,
      risks,
      error: "target_paths 不能为空",
    };
  }

  if (opts.targetPaths.length > 100) {
    return {
      success: false,
      taskId: opts.taskId,
      sessionId: "",
      summary: "target_paths array too large (max 100)",
      agentMessages: "",
      changedFiles: [],
      policyChecks,
      risks,
      error: "target_paths array too large (max 100)",
    };
  }

  policyChecks.push("target_paths_present");
  policyChecks.push("backend_scope_requested");

  // 2. 前端路径守卫
  try {
    validateBackendPaths(opts.targetPaths);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return {
      success: false,
      taskId: opts.taskId,
      sessionId: "",
      summary: msg,
      agentMessages: "",
      changedFiles: [],
      policyChecks,
      risks,
      error: msg,
    };
  }
  policyChecks.push("frontend_boundary_check_passed");

  // 3. 构建任务 prompt
  const cd = opts.cd ?? ".";
  const prompt = buildBackendPrompt(opts);

  // 4. 调用 Codex（沙箱固定为 workspace-write，不允许调用者提权到 danger-full-access）
  const result = await runCodexSession({
    prompt,
    cd: path.resolve(cd),
    sandbox: "workspace-write",
    sessionId: opts.sessionId,
    returnAllMessages: opts.returnAllMessages,
    model: opts.model,
    profile: opts.profile,
  });

  if (result.success) {
    policyChecks.push("backend_executor_completed");
  }

  return {
    success: result.success,
    taskId: opts.taskId,
    sessionId: result.sessionId,
    summary: result.agentMessages,
    agentMessages: result.agentMessages,
    changedFiles: [], // 由文件快照层填充（Phase 3）
    policyChecks,
    risks,
    error: result.error,
  };
}

function buildBackendPrompt(opts: BackendTaskOptions): string {
  const lines: string[] = [
    `任务 ID：${opts.taskId}`,
    ``,
    `## 任务描述`,
    opts.taskSummary,
    ``,
    `## 目标路径`,
    opts.targetPaths.map((p) => `- ${p}`).join("\n"),
  ];

  if (opts.constraints && opts.constraints.length > 0) {
    lines.push(``, `## 约束条件`);
    opts.constraints.forEach((c) => lines.push(`- ${c}`));
  }

  if (opts.acceptanceCriteria && opts.acceptanceCriteria.length > 0) {
    lines.push(``, `## 验收标准`);
    opts.acceptanceCriteria.forEach((a) => lines.push(`- ${a}`));
  }

  return lines.join("\n");
}
