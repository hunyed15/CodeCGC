import { executeStep, type StepExecArgs, type StepExecResult } from "./step-executor.js";
import type { WorkflowKind } from "../../../shared/types.js";

export type BuildArgs = StepExecArgs;
export type BuildResult = StepExecResult;

/**
 * codecgc.build - Execute next pending step of feature workflow
 */
export async function build(args: BuildArgs): Promise<BuildResult> {
  return executeStep(args, "feature" as WorkflowKind);
}
