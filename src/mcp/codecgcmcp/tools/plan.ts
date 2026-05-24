import {
  readWorkflow,
  writeWorkflow,
  addStep,
  resolveWorkflowDir,
} from "../runtime/artifacts.js";
import { resolveProjectRoot, validateStepPaths } from "../runtime/paths.js";
import { readRouting, classifyPaths, hasMixedOwnership } from "../runtime/routing.js";
import type { WorkflowKind, WorkflowStep, StepExecutor } from "../../../shared/types.js";

export interface PlanArgs {
  kind: WorkflowKind;
  slug: string;
  steps: Array<{
    id: string;
    title: string;
    executor: StepExecutor;
    task_id: string;
    summary: string;
    paths: string[];
    constraints?: string[];
    acceptance?: string[];
    cd?: string;
  }>;
  cd?: string;
}

export interface PlanResult {
  success: boolean;
  kind: WorkflowKind;
  slug: string;
  steps_added: number;
  validation_warnings: string[];
  error?: string;
}

/**
 * codecgc.plan — 向 workflow 添加 steps
 *
 * 行为：
 * - 读取现有 workflow
 * - 验证 steps（路径归属、executor 匹配）
 * - 追加 steps 到 workflow.steps
 * - 写回 workflow.yaml
 */
export async function plan(args: PlanArgs): Promise<PlanResult> {
  const projectRoot = resolveProjectRoot(args.cd);
  const workflow = await readWorkflow(projectRoot, args.kind, args.slug);
  const routing = await readRouting(projectRoot);
  const warnings: string[] = [];

  for (const stepInput of args.steps) {
    // 验证路径安全性
    validateStepPaths(stepInput.paths);

    // 验证路径归属
    if (hasMixedOwnership(stepInput.paths, routing)) {
      warnings.push(
        `步骤 ${stepInput.id} 包含 mixed/shared/unknown 路径，建议拆分：\n${stepInput.paths.join(", ")}`
      );
    }

    // 验证 executor 与路径匹配
    const classified = classifyPaths(stepInput.paths, routing);
    if (stepInput.executor === "backend" && !classified.has("backend")) {
      warnings.push(`步骤 ${stepInput.id} 标记为 backend 但路径不包含后端文件`);
    }
    if (stepInput.executor === "frontend" && !classified.has("frontend")) {
      warnings.push(`步骤 ${stepInput.id} 标记为 frontend 但路径不包含前端文件`);
    }

    // 添加步骤
    const step: WorkflowStep = {
      id: stepInput.id,
      title: stepInput.title,
      status: "pending",
      executor: stepInput.executor,
      task_id: stepInput.task_id,
      summary: stepInput.summary,
      paths: stepInput.paths,
      constraints: stepInput.constraints,
      acceptance: stepInput.acceptance,
      cd: stepInput.cd,
    };
    addStep(workflow, step);
  }

  await writeWorkflow(projectRoot, workflow);

  return {
    success: true,
    kind: args.kind,
    slug: args.slug,
    steps_added: args.steps.length,
    validation_warnings: warnings,
  };
}
