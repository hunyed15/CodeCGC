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
 * codecgc.plan - Add steps to workflow
 *
 * Behavior:
 * - Read existing workflow
 * - Validate steps (path ownership, executor matching)
 * - Append steps to workflow.steps
 * - Write back to workflow.yaml
 */
export async function plan(args: PlanArgs): Promise<PlanResult> {
  try {
    // Input validation
    if (!args.steps || !Array.isArray(args.steps)) {
      throw new Error("steps must be a non-empty array");
    }

    if (args.steps.length === 0) {
      throw new Error("steps array cannot be empty");
    }

    if (args.steps.length > 100) {
      throw new Error("steps array too large (max 100)");
    }

    // Validate kind and slug
    if (!args.kind || !args.slug) {
      throw new Error("kind and slug are required");
    }

    const projectRoot = resolveProjectRoot(args.cd);
    const workflow = await readWorkflow(projectRoot, args.kind, args.slug);
    const routing = await readRouting(projectRoot);
    const warnings: string[] = [];

    // Check for duplicate step IDs
    const existingIds = new Set(workflow.steps?.map(s => s.id) || []);
    const newIds = new Set<string>();

    for (const stepInput of args.steps) {
      // Validate step fields
      if (!stepInput.id || typeof stepInput.id !== "string") {
        throw new Error("step.id is required and must be a string");
      }
      if (stepInput.id.length > 50) {
        throw new Error(`step.id too long (max 50 chars): ${stepInput.id}`);
      }
      if (existingIds.has(stepInput.id)) {
        throw new Error(`Duplicate step.id: ${stepInput.id} already exists in workflow`);
      }
      if (newIds.has(stepInput.id)) {
        throw new Error(`Duplicate step.id in input: ${stepInput.id}`);
      }
      newIds.add(stepInput.id);

      if (!stepInput.title || typeof stepInput.title !== "string") {
        throw new Error(`step.title is required for step ${stepInput.id}`);
      }
      if (stepInput.title.length > 200) {
        throw new Error(`step.title too long (max 200 chars) for step ${stepInput.id}`);
      }

      if (!stepInput.executor) {
        throw new Error(`step.executor is required for step ${stepInput.id}`);
      }

      if (!stepInput.task_id || typeof stepInput.task_id !== "string") {
        throw new Error(`step.task_id is required for step ${stepInput.id}`);
      }

      if (!stepInput.summary || typeof stepInput.summary !== "string") {
        throw new Error(`step.summary is required for step ${stepInput.id}`);
      }
      if (stepInput.summary.length > 1000) {
        throw new Error(`step.summary too long (max 1000 chars) for step ${stepInput.id}`);
      }

      if (!Array.isArray(stepInput.paths)) {
        throw new Error(`step.paths must be an array for step ${stepInput.id}`);
      }
      if (stepInput.paths.length > 100) {
        throw new Error(`step.paths too large (max 100) for step ${stepInput.id}`);
      }

      // Validate path safety
      validateStepPaths(stepInput.paths);

      // Validate path ownership
      if (hasMixedOwnership(stepInput.paths, routing)) {
        warnings.push(
          `Step ${stepInput.id} contains mixed/shared/unknown paths, suggest splitting:\n${stepInput.paths.slice(0, 5).join(", ")}${stepInput.paths.length > 5 ? ` (and ${stepInput.paths.length - 5} more)` : ""}`
        );
      }

      // Validate executor matches paths
      const classified = classifyPaths(stepInput.paths, routing);
      if (stepInput.executor === "backend" && !classified.has("backend")) {
        warnings.push(`Step ${stepInput.id} marked as backend but paths don't contain backend files`);
      }
      if (stepInput.executor === "frontend" && !classified.has("frontend")) {
        warnings.push(`Step ${stepInput.id} marked as frontend but paths don't contain frontend files`);
      }

      // Add step
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
  } catch (error) {
    return {
      success: false,
      kind: args.kind,
      slug: args.slug,
      steps_added: 0,
      validation_warnings: [],
      error: error instanceof Error ? error.message : String(error),
    };
  }
}
