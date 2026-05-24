import { existsSync } from "fs";
import { readYaml } from "../../../shared/yaml.js";
import type { ModelRouting, PathOwnership, RoutingRule } from "../../../shared/types.js";
import { routingFile } from "./paths.js";
import { minimatch } from "minimatch";

/**
 * 默认路由规则（当 model-routing.yaml 不存在时）
 */
const DEFAULT_ROUTING: ModelRouting = {
  version: 1,
  rules: [
    {
      patterns: ["**/*.py", "**/api/**", "**/server/**", "**/backend/**"],
      ownership: "backend",
    },
    {
      patterns: [
        "**/*.tsx",
        "**/*.jsx",
        "**/*.css",
        "**/*.scss",
        "**/components/**",
        "**/pages/**",
        "**/app/**",
        "**/frontend/**",
      ],
      ownership: "frontend",
    },
    {
      patterns: ["**/*.md", "**/docs/**", "README*", "CHANGELOG*"],
      ownership: "docs",
    },
    {
      patterns: ["**/shared/**", "**/common/**", "**/utils/**"],
      ownership: "shared",
    },
  ],
};

/**
 * 读取 model-routing.yaml
 */
export async function readRouting(projectRoot: string): Promise<ModelRouting> {
  const file = routingFile(projectRoot);
  if (!existsSync(file)) {
    return DEFAULT_ROUTING;
  }
  const routing = await readYaml<ModelRouting>(file);
  if (!routing || typeof routing !== "object" || !Array.isArray(routing.rules)) {
    throw new Error(`无效的 model-routing.yaml: ${file}`);
  }
  return routing;
}

/**
 * 判断单个路径的归属
 */
export function classifyPath(path: string, routing: ModelRouting): PathOwnership {
  // 规则从上到下匹配，第一个匹配的规则决定归属
  for (const rule of routing.rules) {
    for (const pattern of rule.patterns) {
      if (minimatch(path, pattern, { dot: true, matchBase: true })) {
        return rule.ownership;
      }
    }
  }
  return "unknown";
}

/**
 * 批量分类路径
 */
export function classifyPaths(
  paths: string[],
  routing: ModelRouting
): Map<PathOwnership, string[]> {
  const result = new Map<PathOwnership, string[]>();
  for (const path of paths) {
    const ownership = classifyPath(path, routing);
    if (!result.has(ownership)) result.set(ownership, []);
    result.get(ownership)!.push(path);
  }
  return result;
}

/**
 * 检查路径集合是否纯后端
 */
export function isPureBackend(paths: string[], routing: ModelRouting): boolean {
  const classified = classifyPaths(paths, routing);
  return (
    classified.size === 1 &&
    classified.has("backend") &&
    classified.get("backend")!.length === paths.length
  );
}

/**
 * 检查路径集合是否纯前端
 */
export function isPureFrontend(paths: string[], routing: ModelRouting): boolean {
  const classified = classifyPaths(paths, routing);
  return (
    classified.size === 1 &&
    classified.has("frontend") &&
    classified.get("frontend")!.length === paths.length
  );
}

/**
 * 检查路径集合是否纯文档
 */
export function isPureDocs(paths: string[], routing: ModelRouting): boolean {
  const classified = classifyPaths(paths, routing);
  return (
    classified.size === 1 &&
    classified.has("docs") &&
    classified.get("docs")!.length === paths.length
  );
}

/**
 * 检查路径集合是否包含 shared/unknown
 */
export function hasMixedOwnership(paths: string[], routing: ModelRouting): boolean {
  const classified = classifyPaths(paths, routing);
  return classified.has("shared") || classified.has("unknown") || classified.size > 1;
}

/**
 * 生成路径归属报告（用于诊断）
 */
export function pathOwnershipReport(paths: string[], routing: ModelRouting): string {
  const classified = classifyPaths(paths, routing);
  const lines: string[] = [];
  for (const [ownership, pathList] of classified.entries()) {
    lines.push(`${ownership}:`);
    for (const p of pathList) {
      lines.push(`  - ${p}`);
    }
  }
  return lines.join("\n");
}
