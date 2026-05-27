import { runOpenCodeSession } from "./executor.js";
import type { FrontendTaskOptions, TaskResult } from "../../shared/types.js";

/**
 * 前端任务执行器（OpenCode 专用）
 * 与 Gemini 类似，用于前端代码生成
 */
export async function executeFrontendTask(opts: FrontendTaskOptions): Promise<TaskResult> {
  // 路径守卫：拒绝后端路径
  const backendPatterns = [/\.py$/, /\.go$/, /\.rs$/, /\/api\//, /\/server\//, /\/backend\//];
  for (const path of opts.targetPaths) {
    if (backendPatterns.some((p) => p.test(path))) {
      return {
        success: false,
        taskId: opts.taskId,
        sessionId: "",
        summary: "",
        agentMessages: "",
        changedFiles: [],
        policyChecks: [],
        risks: [],
        error: `路径守卫拒绝：OpenCode 不应处理后端路径 ${path}`,
      };
    }
  }

  // 构建 prompt
  const prompt = buildFrontendPrompt(opts);

  // 调用 OpenCode executor
  const result = await runOpenCodeSession({
    prompt,
    cd: opts.cd ?? ".",
    sandbox: opts.sandbox,
    sessionId: opts.sessionId,
    returnAllMessages: opts.returnAllMessages,
    model: opts.model,
    timeoutMs: opts.timeoutMs,
  });

  if (!result.success) {
    return {
      success: false,
      taskId: opts.taskId,
      sessionId: result.sessionId,
      summary: "",
      agentMessages: result.agentMessages,
      changedFiles: [],
      policyChecks: [],
      risks: [],
      error: result.error,
    };
  }

  // 解析执行结果
  return {
    success: true,
    taskId: opts.taskId,
    sessionId: result.sessionId,
    summary: `OpenCode 完成前端任务: ${opts.taskSummary}`,
    agentMessages: result.agentMessages,
    changedFiles: opts.targetPaths,
    policyChecks: ["路径守卫通过"],
    risks: [],
  };
}

function buildFrontendPrompt(opts: FrontendTaskOptions): string {
  let prompt = `# 前端任务\n\n`;
  prompt += `**任务 ID**: ${opts.taskId}\n`;
  prompt += `**摘要**: ${opts.taskSummary}\n\n`;
  prompt += `**目标路径**:\n${opts.targetPaths.map((p) => `- ${p}`).join("\n")}\n\n`;

  if (opts.constraints && opts.constraints.length > 0) {
    prompt += `**约束条件**:\n${opts.constraints.map((c) => `- ${c}`).join("\n")}\n\n`;
  }

  if (opts.acceptanceCriteria && opts.acceptanceCriteria.length > 0) {
    prompt += `**验收标准**:\n${opts.acceptanceCriteria.map((a) => `- ${a}`).join("\n")}\n\n`;
  }

  prompt += `请实现上述前端任务，确保代码质量和可维护性。`;
  return prompt;
}
