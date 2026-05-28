import { executeStep, type StepExecArgs, type StepExecResult } from "./step-executor.js";
import type { WorkflowKind } from "../../../shared/types.js";

export type FixArgs = StepExecArgs;
export type FixResult = StepExecResult;

/**
 * codecgc.fix — 执行 issue workflow 的下一个 pending 步骤
 */
export async function fix(args: FixArgs): Promise<FixResult> {
  return executeStep(args, "issue" as WorkflowKind);
}
