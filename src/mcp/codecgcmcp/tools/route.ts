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
  executor_hint?: "frontend" | "backend" | "docs" | "both"; // New: explicit declaration
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
    const projectRoot = resolveProjectRoot(args.cd);

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
        paths: args.paths,
        classification: buildClassificationFromHint(args.paths, args.executor_hint),
        is_mixed: false,
        recommended_executor: executor,
        recommendation: `Based on executor_hint="${args.executor_hint}", recommend executor: ${executor}`,
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
      const ownership = Array.from(classified.keys())[0];
      const executor = ownershipToExecutor(ownership);
      return {
        success: true,
        paths: args.paths,
        classification,
        is_mixed: false,
        recommended_executor: executor,
        recommendation: `All paths belong to ${ownership}, recommend executor: ${executor}`,
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
    if (sharedPaths.length > 0) {
      recommendation += ` Shared paths need clarification: ${sharedPaths.join(", ")}`;
    }
    if (unknownPaths.length > 0) {
      recommendation += ` Unknown paths need routing.yaml update: ${unknownPaths.join(", ")}`;
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

  let recommendation = `Based on executor_hint="both", auto-split into ${splits.length} steps.`;
  if (classification.shared.length > 0) {
    recommendation += ` Shared paths need clarification: ${classification.shared.join(", ")}`;
  }
  if (classification.unknown.length > 0) {
    recommendation += ` Unknown paths need routing.yaml update: ${classification.unknown.join(", ")}`;
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
