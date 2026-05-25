import {
  readWorkflow,
  writeWorkflow,
  resolveWorkflowDir,
  findStep,
  writeAudit,
} from "../runtime/artifacts.js";
import { callExecutor } from "../runtime/executor.js";
import { resolveProjectRoot, validateStepPaths } from "../runtime/paths.js";
import { readRouting, classifyPaths } from "../runtime/routing.js";
import type { WorkflowKind } from "../../../shared/types.js";

export interface ContinueArgs {
  kind: WorkflowKind;
  slug: string;
  step_id: string;
  session_id: string;
  cd?: string;
  timeout_seconds?: number;
}

export interface ContinueResult {
  success: boolean;
  kind: WorkflowKind;
  slug: string;
  step_id: string;
  session_id: string;
  new_session_id?: string;
  summary: string;
  recommendation: string;
  error?: string;
}

/**
 * codecgc.continue — 在同一 session_id 内继续执行
 *
 * 用途：
 * - 跨 turn 对话续接：上次执行器返回的 session_id 传入，继续同一对话
 * - 失败重试：保持上下文，让执行器基于之前的对话继续修复
 * - 增量迭代：在同一 session 内多次调整代码
 *
 * 区别于 build/fix：
 * - build/fix 会自动选择下一个 pending 步骤
 * - continue 必须指定 step_id 和 session_id，用于续接已开始的步骤
 *
 * 注意：
 * - 如果 step 已标记 done，continue 会报错（不允许重复执行已完成步骤）
 * - session_id 必须是该 step 之前执行返回的 ID
 */
export async function continueExecution(args: ContinueArgs): Promise<ContinueResult> {
  try {
    // Input validation
    if (!args.kind || !args.slug) {
      throw new Error("kind and slug are required");
    }
    if (!args.step_id || typeof args.step_id !== "string") {
      throw new Error("step_id is required and must be a string");
    }
    if (!args.session_id || typeof args.session_id !== "string") {
      throw new Error("session_id is required and must be a string");
    }
    if (args.timeout_seconds !== undefined) {
      if (typeof args.timeout_seconds !== "number" || args.timeout_seconds <= 0 || args.timeout_seconds > 3600) {
        throw new Error("timeout_seconds must be between 1 and 3600");
      }
    }

    const projectRoot = resolveProjectRoot(args.cd);
    const workflow = await readWorkflow(projectRoot, args.kind, args.slug);
    const step = findStep(workflow, args.step_id);

    if (!step) {
      return {
        success: false,
        kind: args.kind,
        slug: args.slug,
        step_id: args.step_id,
        session_id: args.session_id,
        summary: "",
        recommendation: `Step ${args.step_id} 不存在`,
        error: `Step not found: ${args.step_id}`,
      };
    }

    if (step.status === "done") {
      return {
        success: false,
        kind: args.kind,
        slug: args.slug,
        step_id: args.step_id,
        session_id: args.session_id,
        summary: "",
        recommendation: `Step ${args.step_id} 已完成，不能 continue`,
        error: "Step already done",
      };
    }

    // ✅ 验证 session_id 匹配
    // 只在 step 有非空 session_id 时验证（空字符串表示从未执行或 manual 步骤）
    if (step.session_id !== undefined && step.session_id !== "" && step.session_id !== args.session_id) {
      return {
        success: false,
        kind: args.kind,
        slug: args.slug,
        step_id: args.step_id,
        session_id: args.session_id,
        summary: "",
        recommendation: `Step ${args.step_id} 的 session_id 是 ${step.session_id}，与传入的 ${args.session_id} 不匹配。请使用正确的 session_id 或先调用 build/fix 重新开始。`,
        error: "Session ID mismatch",
      };
    }

    // 如果 step 从未执行过（无 session_id），continue 不合理，应先 build/fix
    if (!step.session_id) {
      return {
        success: false,
        kind: args.kind,
        slug: args.slug,
        step_id: args.step_id,
        session_id: args.session_id,
        summary: "",
        recommendation: `Step ${args.step_id} 从未执行过（无 session_id），请先调用 build/fix 执行。`,
        error: "No existing session to continue",
      };
    }

    // 注入 session_id 到 step（临时覆盖）
    step.session_id = args.session_id;

    validateStepPaths(step.paths);

    // ✅ 修复 P2 问题 #7：前置路径归属检查（在执行器调用前）
    if (step.executor === "backend" || step.executor === "frontend") {
      const routing = await readRouting(projectRoot);
      const classified = classifyPaths(step.paths, routing);
      if (step.executor === "backend" && classified.has("frontend")) {
        return {
          success: false,
          kind: args.kind,
          slug: args.slug,
          step_id: args.step_id,
          session_id: args.session_id,
          summary: "",
          recommendation: `后端步骤包含前端路径，拒绝执行: ${classified.get("frontend")?.join(", ")}`,
          error: "Path ownership violation",
        };
      }
      if (step.executor === "frontend" && classified.has("backend")) {
        return {
          success: false,
          kind: args.kind,
          slug: args.slug,
          step_id: args.step_id,
          session_id: args.session_id,
          summary: "",
          recommendation: `前端步骤包含后端路径，拒绝执行: ${classified.get("backend")?.join(", ")}`,
          error: "Path ownership violation",
        };
      }
    }

    const timeoutMs = (args.timeout_seconds ?? 600) * 1000;
    const result = await callExecutor(step, projectRoot, timeoutMs);

    // ✅ 修复 P1 问题 #2：写入 continue audit 记录
    const workflowDir = resolveWorkflowDir(projectRoot, workflow.kind, workflow.slug);
    const auditFile = await writeAudit(workflowDir, step.id, {
      step_id: step.id,
      executor: step.executor,
      task_id: step.task_id,
      kind: "continue",
      session_id: args.session_id,
      timestamp: new Date().toISOString(),
      result,
    });

    if (!result.success) {
      return {
        success: false,
        kind: args.kind,
        slug: args.slug,
        step_id: args.step_id,
        session_id: args.session_id,
        summary: result.summary,
        recommendation: `执行失败: ${result.error ?? "未知错误"}`,
        error: result.error,
      };
    }

    // 更新 workflow 中的 session_id（不标记 done，等待 review）
    step.session_id = result.sessionId;
    await writeWorkflow(projectRoot, workflow);

    return {
      success: true,
      kind: args.kind,
      slug: args.slug,
      step_id: args.step_id,
      session_id: args.session_id,
      new_session_id: result.sessionId,
      summary: result.summary,
      recommendation: `Continue 成功，新 session_id: ${result.sessionId}。下一步：调用 codecgc.review 审核。`,
    };
  } catch (error) {
    return {
      success: false,
      kind: args.kind,
      slug: args.slug,
      step_id: args.step_id,
      session_id: args.session_id,
      summary: "",
      recommendation: "Continue 失败",
      error: error instanceof Error ? error.message : String(error),
    };
  }
}
