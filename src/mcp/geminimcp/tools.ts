import * as path from "path";
import type { FrontendTaskOptions, TaskResult } from "../../shared/types.js";
import { runGeminiSession } from "./executor.js";

// 后端路径模式（前端执行器拒绝这些路径）
const BACKEND_PATTERNS = [
  /\.(py|go|rs|java|rb|php|cs|cpp|c|h|kt|swift)$/i,
  /\/api\//,
  /\/server\//,
  /\/backend\//,
  /\/services?\//,
  /\/controllers?\//,
  /\/models?\//,
  /\/migrations?\//,
  /\/database\//,
  /\/(apps|src)\/api\//,
];

function validateFrontendPaths(paths: string[]): void {
  const violations = paths.filter((p) => BACKEND_PATTERNS.some((re) => re.test(p.replace(/\\/g, "/"))));
  if (violations.length > 0) {
    throw new Error(`前端执行器拒绝以下疑似后端路径：${violations.join(", ")}`);
  }
}

export async function executeFrontendTask(opts: FrontendTaskOptions): Promise<TaskResult> {
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
  policyChecks.push("frontend_scope_requested");

  try {
    validateFrontendPaths(opts.targetPaths);
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
  policyChecks.push("backend_boundary_check_passed");

  const cd = opts.cd ?? ".";
  const prompt = buildFrontendPrompt(opts);

  const result = await runGeminiSession({
    prompt,
    cd: path.resolve(cd),
    sandbox: opts.sandbox ?? false,
    sessionId: opts.sessionId,
    returnAllMessages: opts.returnAllMessages,
    model: opts.model,
    timeoutMs: opts.timeoutMs,
  });

  if (result.success) {
    policyChecks.push("frontend_executor_completed");
  }

  return {
    success: result.success,
    taskId: opts.taskId,
    sessionId: result.sessionId,
    summary: result.agentMessages,
    agentMessages: result.agentMessages,
    changedFiles: [],
    policyChecks,
    risks,
    error: result.error,
  };
}

function buildFrontendPrompt(opts: FrontendTaskOptions): string {
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
