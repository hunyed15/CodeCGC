import {
  readRouting,
  classifyPaths,
  hasMixedOwnership,
} from "../runtime/routing.js";
import { resolveProjectRoot } from "../runtime/paths.js";
import type { PathOwnership, StepExecutor } from "../../../shared/types.js";

export interface RouteArgs {
  paths: string[];
  cd?: string;
}

export interface RouteResult {
  success: boolean;
  paths: string[];
  classification: Record<PathOwnership, string[]>;
  is_mixed: boolean;
  recommended_executor?: StepExecutor;
  recommended_split?: Array<{
    executor: StepExecutor;
    paths: string[];
  }>;
  recommendation: string;
  error?: string;
}

/**
 * codecgc.route — 根据路径判断归属，推荐 executor
 *
 * 用途：
 * - Claude 在 plan 阶段调用此工具，自动推断每个 step 的 executor
 * - 检测 mixed/shared/unknown 路径，提示拆分
 * - 返回拆分建议，便于自动生成多个 step
 */
export async function route(args: RouteArgs): Promise<RouteResult> {
  try {
    const projectRoot = resolveProjectRoot(args.cd);
    const routing = await readRouting(projectRoot);
    const classified = classifyPaths(args.paths, routing);

    const classification: Record<PathOwnership, string[]> = {
      backend: classified.get("backend") ?? [],
      frontend: classified.get("frontend") ?? [],
      shared: classified.get("shared") ?? [],
      docs: classified.get("docs") ?? [],
      unknown: classified.get("unknown") ?? [],
    };

    const isMixed = hasMixedOwnership(args.paths, routing);

    if (!isMixed) {
      const ownership = Array.from(classified.keys())[0];
      const executor = ownershipToExecutor(ownership);
      return {
        success: true,
        paths: args.paths,
        classification,
        is_mixed: false,
        recommended_executor: executor,
        recommendation: `所有路径归属 ${ownership}，建议使用 executor: ${executor}`,
      };
    }

    // mixed：生成拆分建议
    const splits: Array<{ executor: StepExecutor; paths: string[] }> = [];
    for (const [ownership, paths] of classified.entries()) {
      if (paths.length === 0) continue;
      if (ownership === "shared" || ownership === "unknown") {
        // shared/unknown 不能自动拆分，需要用户澄清
        continue;
      }
      splits.push({
        executor: ownershipToExecutor(ownership),
        paths,
      });
    }

    const sharedPaths = classification.shared;
    const unknownPaths = classification.unknown;
    let recommendation = `路径归属混合，建议拆成 ${splits.length} 个 step。`;
    if (sharedPaths.length > 0) {
      recommendation += ` shared 路径需要澄清归属: ${sharedPaths.join(", ")}`;
    }
    if (unknownPaths.length > 0) {
      recommendation += ` unknown 路径需要更新 .codecgc/config/routing.yaml: ${unknownPaths.join(", ")}`;
    }

    return {
      success: true,
      paths: args.paths,
      classification,
      is_mixed: true,
      recommended_split: splits,
      recommendation,
    };
  } catch (error) {
    return {
      success: false,
      paths: args.paths,
      classification: {
        backend: [],
        frontend: [],
        shared: [],
        docs: [],
        unknown: [],
      },
      is_mixed: false,
      recommendation: "路由判断失败",
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

/**
 * PathOwnership → StepExecutor
 */
function ownershipToExecutor(ownership: PathOwnership): StepExecutor {
  switch (ownership) {
    case "backend":
      return "backend";
    case "frontend":
      return "frontend";
    case "docs":
      return "docs";
    case "shared":
    case "unknown":
    default:
      return "orchestration";
  }
}
