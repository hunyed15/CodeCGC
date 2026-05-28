import {
  readRouting,
  classifyPaths,
  hasMixedOwnership,
} from "../runtime/routing.js";
import { resolveProjectRoot } from "../runtime/paths.js";
import { loadExecutorConfig } from "../../../shared/executor-config.js";
import type { PathOwnership, StepExecutor } from "../../../shared/types.js";

export interface RouteArgs {
  paths: string[];
  cd?: string;
  executor_hint?: "frontend" | "backend" | "docs" | "both"; // New: explicit declaration
}

export interface RouteResult {
  success: boolean;
  mode?: "lightweight" | "full";
  paths: string[];
  classification: Record<PathOwnership, string[]>;
  is_mixed: boolean;
  recommended_executor?: StepExecutor;
  actual_provider?: string;
  recommended_split?: Array<{
    executor: StepExecutor;
    paths: string[];
  }>;
  recommendation: string;
  error?: string;
}

/**
 * codecgc.route - Determine path ownership and recommend executor
 *
 * Hybrid routing strategy (priority from high to low):
 * 1. executor_hint (explicit declaration) - Claude judges by semantics
 * 2. Directory convention (frontend/backend paths) - project structure
 * 3. routing.yaml rules (extensions + path patterns) - fallback
 *
 * Usage:
 * - Claude calls this tool during plan phase to infer executor for each step
 * - Detect mixed/shared/unknown paths and suggest splitting
 * - Return split suggestions for auto-generating multiple steps
 */
export async function route(args: RouteArgs): Promise<RouteResult> {
  try {
    // Input validation
    if (!args.paths || !Array.isArray(args.paths)) {
      throw new Error("paths must be a non-empty array");
    }

    if (args.paths.length === 0) {
      throw new Error("paths array cannot be empty");
    }

    if (args.paths.length > 1000) {
      throw new Error("paths array too large (max 1000)");
    }

    // Validate path elements
    for (const path of args.paths) {
      if (typeof path !== "string") {
        throw new Error(`Invalid path type: expected string, got ${typeof path}`);
      }
      if (path.length === 0) {
        throw new Error("Empty path string not allowed");
      }
      if (path.length > 500) {
        throw new Error(`Path too long (max 500 chars): ${path.slice(0, 50)}...`);
      }
    }

    const projectRoot = resolveProjectRoot(args.cd);

    // 读取 executor 配置
    const executorConfig = await loadExecutorConfig(projectRoot);

    // 轻量模式：所有路径都由 Claude 处理
    if (executorConfig.mode === "lightweight") {
      return {
        success: true,
        mode: "lightweight",
        paths: args.paths,
        classification: {
          backend: [],
          frontend: [],
          shared: [],
          docs: [],
          unknown: [],
        },
        is_mixed: false,
        recommended_executor: "orchestration",
        actual_provider: "claude",
        recommendation: "轻量模式：所有路径由 Claude 直接处理",
      };
    }

    // Priority 1: Explicit declaration (executor_hint)
    if (args.executor_hint) {
      if (args.executor_hint === "both") {
        // "both" means both frontend and backend need changes, split required
        return handleBothHint(args.paths, projectRoot);
      }

      // Single executor hint, return directly
      const executor = hintToExecutor(args.executor_hint);
      return {
        success: true,
        mode: "full",
        paths: args.paths,
        classification: buildClassificationFromHint(args.paths, args.executor_hint),
        is_mixed: false,
        recommended_executor: executor,
        actual_provider: resolveProvider(executor, executorConfig),
        recommendation: `Based on executor_hint="${args.executor_hint}", recommend executor: ${executor} (provider: ${resolveProvider(executor, executorConfig)})`,
      };
    }

    // Priority 2 & 3: Directory convention + routing.yaml
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
      // Single ownership: find the non-empty category
      let ownership: PathOwnership | undefined;
      for (const [key, paths] of classified.entries()) {
        if (paths.length > 0) {
          ownership = key;
          break;
        }
      }

      if (!ownership) {
        // All paths are empty or unclassified, default to orchestration
        ownership = "unknown";
      }

      const executor = ownershipToExecutor(ownership);
      return {
        success: true,
        mode: "full",
        paths: args.paths,
        classification,
        is_mixed: false,
        recommended_executor: executor,
        actual_provider: resolveProvider(executor, executorConfig),
        recommendation: `All paths belong to ${ownership}, recommend executor: ${executor} (provider: ${resolveProvider(executor, executorConfig)})`,
      };
    }

    // mixed: generate split suggestions
    const splits: Array<{ executor: StepExecutor; paths: string[] }> = [];
    for (const [ownership, paths] of classified.entries()) {
      if (paths.length === 0) continue;
      if (ownership === "shared" || ownership === "unknown") {
        // shared/unknown cannot be auto-split, need user clarification
        continue;
      }
      splits.push({
        executor: ownershipToExecutor(ownership),
        paths,
      });
    }

    const sharedPaths = classification.shared;
    const unknownPaths = classification.unknown;
    let recommendation = `Mixed path ownership, suggest splitting into ${splits.length} steps.`;

    // Limit output length to prevent excessive strings
    if (sharedPaths.length > 0) {
      const pathList = sharedPaths.length > 5
        ? `${sharedPaths.slice(0, 5).join(", ")} (and ${sharedPaths.length - 5} more)`
        : sharedPaths.join(", ");
      recommendation += ` Shared paths need clarification: ${pathList}`;
    }
    if (unknownPaths.length > 0) {
      const pathList = unknownPaths.length > 5
        ? `${unknownPaths.slice(0, 5).join(", ")} (and ${unknownPaths.length - 5} more)`
        : unknownPaths.join(", ");
      recommendation += ` Unknown paths need routing.yaml update: ${pathList}`;
    }

    return {
      success: true,
      mode: "full",
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
      recommendation: "Route determination failed",
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

/**
 * 根据 executor 类型和配置返回实际 provider 名称
 */
function resolveProvider(executor: StepExecutor, config: { executors: { backend: { provider: string }; frontend: { provider: string } } }): string {
  switch (executor) {
    case "backend":
      return config.executors.backend.provider;
    case "frontend":
      return config.executors.frontend.provider;
    case "docs":
    case "orchestration":
      return "claude";
    default:
      return "claude";
  }
}

/**
 * executor_hint → StepExecutor
 */
function hintToExecutor(hint: "frontend" | "backend" | "docs"): StepExecutor {
  return hint as StepExecutor;
}

/**
 * Build classification from hint (for explicit declaration scenario)
 */
function buildClassificationFromHint(
  paths: string[],
  hint: "frontend" | "backend" | "docs"
): Record<PathOwnership, string[]> {
  const classification: Record<PathOwnership, string[]> = {
    backend: [],
    frontend: [],
    shared: [],
    docs: [],
    unknown: [],
  };
  classification[hint] = paths;
  return classification;
}

/**
 * Handle executor_hint="both" case (both frontend and backend need changes)
 */
async function handleBothHint(
  paths: string[],
  projectRoot: string
): Promise<RouteResult> {
  // Use directory convention + routing.yaml for auto-split
  const routing = await readRouting(projectRoot);
  const classified = classifyPaths(paths, routing);

  const classification: Record<PathOwnership, string[]> = {
    backend: classified.get("backend") ?? [],
    frontend: classified.get("frontend") ?? [],
    shared: classified.get("shared") ?? [],
    docs: classified.get("docs") ?? [],
    unknown: classified.get("unknown") ?? [],
  };

  const splits: Array<{ executor: StepExecutor; paths: string[] }> = [];

  if (classification.frontend.length > 0) {
    splits.push({ executor: "frontend", paths: classification.frontend });
  }
  if (classification.backend.length > 0) {
    splits.push({ executor: "backend", paths: classification.backend });
  }
  if (classification.docs.length > 0) {
    splits.push({ executor: "docs", paths: classification.docs });
  }

  // Edge case: all paths are shared/unknown, cannot auto-split
  if (splits.length === 0) {
    let recommendation = `Cannot auto-split with executor_hint="both": all paths are shared/unknown.`;
    if (classification.shared.length > 0) {
      const pathList = classification.shared.length > 5
        ? `${classification.shared.slice(0, 5).join(", ")} (and ${classification.shared.length - 5} more)`
        : classification.shared.join(", ");
      recommendation += ` Shared paths need clarification: ${pathList}`;
    }
    if (classification.unknown.length > 0) {
      const pathList = classification.unknown.length > 5
        ? `${classification.unknown.slice(0, 5).join(", ")} (and ${classification.unknown.length - 5} more)`
        : classification.unknown.join(", ");
      recommendation += ` Unknown paths need routing.yaml update: ${pathList}`;
    }
    return {
      success: false,
      paths,
      classification,
      is_mixed: true,
      recommendation,
      error: "Cannot determine split: all paths are shared or unknown",
    };
  }

  let recommendation = `Based on executor_hint="both", auto-split into ${splits.length} steps.`;
  if (classification.shared.length > 0) {
    const pathList = classification.shared.length > 5
      ? `${classification.shared.slice(0, 5).join(", ")} (and ${classification.shared.length - 5} more)`
      : classification.shared.join(", ");
    recommendation += ` Shared paths need clarification: ${pathList}`;
  }
  if (classification.unknown.length > 0) {
    const pathList = classification.unknown.length > 5
      ? `${classification.unknown.slice(0, 5).join(", ")} (and ${classification.unknown.length - 5} more)`
      : classification.unknown.join(", ");
    recommendation += ` Unknown paths need routing.yaml update: ${pathList}`;
  }

  return {
    success: true,
    paths,
    classification,
    is_mixed: true,
    recommended_split: splits,
    recommendation,
  };
}
