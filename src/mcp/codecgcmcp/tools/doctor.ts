import { existsSync } from "fs";
import { readFile } from "fs/promises";
import { join } from "path";
import which from "which";
import { resolveCliCommand } from "../../../shared/process.js";
import { codecgcRoot, resolveProjectRoot, routingFile } from "../runtime/paths.js";

export interface DoctorArgs {
  cd?: string;
}

export interface CheckResult {
  name: string;
  status: "ok" | "warn" | "error";
  detail: string;
}

export interface DoctorResult {
  success: boolean;
  project_root: string;
  overall: "healthy" | "degraded" | "broken";
  checks: CheckResult[];
  recommendation: string;
  error?: string;
}

/**
 * codecgc.doctor — 环境健康检查
 *
 * 检查项：
 * 1. Node.js 版本（>= 20）
 * 2. CodeCGC CLI 可用性（cgc / cgc-init / cgc-mcp）
 * 3. Codex CLI 可用性
 * 4. Gemini CLI 可用性
 * 5. 项目结构（.codecgc/ 目录）
 * 6. 配置文件（.codecgc/config/routing.yaml / .mcp.json）
 */
export async function doctor(args: DoctorArgs): Promise<DoctorResult> {
  try {
    const projectRoot = resolveProjectRoot(args.cd);
    const checks: CheckResult[] = [];

    checks.push(checkNodeVersion());
    checks.push(await checkPathCommand("cgc", "CodeCGC CLI"));
    checks.push(await checkPathCommand("cgc-init", "CodeCGC init 命令"));
    checks.push(await checkPathCommand("cgc-mcp", "CodeCGC MCP 命令"));
    checks.push(await checkCodexCli());
    checks.push(await checkGeminiCli());
    checks.push(checkProjectStructure(projectRoot));
    checks.push(checkRoutingFile(projectRoot));
    checks.push(await checkMcpConfig(projectRoot));

    const errors = checks.filter((c) => c.status === "error").length;
    const warnings = checks.filter((c) => c.status === "warn").length;

    let overall: DoctorResult["overall"];
    if (errors > 0) overall = "broken";
    else if (warnings > 0) overall = "degraded";
    else overall = "healthy";

    const recommendation = generateDoctorRecommendation(checks, overall);

    return {
      success: true,
      project_root: projectRoot,
      overall,
      checks,
      recommendation,
    };
  } catch (error) {
    return {
      success: false,
      project_root: args.cd ?? process.cwd(),
      overall: "broken",
      checks: [],
      recommendation: "诊断失败",
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

async function checkPathCommand(command: string, label: string): Promise<CheckResult> {
  try {
    const resolved = await which(command);
    return {
      name: label,
      status: "ok",
      detail: resolved,
    };
  } catch (error) {
    return {
      name: label,
      status: "error",
      detail: `未在 PATH 中找到 ${command}。请重新全局安装 @hunyed15/codecgc，或把 npm global bin 目录加入 PATH。`,
    };
  }
}

function checkNodeVersion(): CheckResult {
  const version = process.versions.node;
  const major = parseInt(version.split(".")[0], 10);
  if (major >= 20) {
    return { name: "Node.js 版本", status: "ok", detail: `v${version}` };
  }
  return {
    name: "Node.js 版本",
    status: "error",
    detail: `v${version}（要求 >= 20）`,
  };
}

async function checkCodexCli(): Promise<CheckResult> {
  try {
    const cmd = await resolveCliCommand("codex");
    return {
      name: "Codex CLI",
      status: "ok",
      detail: cmd.join(" "),
    };
  } catch (error) {
    return {
      name: "Codex CLI",
      status: "warn",
      detail: `未找到，后端步骤无法执行（${error instanceof Error ? error.message : String(error)}）`,
    };
  }
}

async function checkGeminiCli(): Promise<CheckResult> {
  try {
    const cmd = await resolveCliCommand("gemini");
    return {
      name: "Gemini CLI",
      status: "ok",
      detail: cmd.join(" "),
    };
  } catch (error) {
    return {
      name: "Gemini CLI",
      status: "warn",
      detail: `未找到，前端步骤无法执行（${error instanceof Error ? error.message : String(error)}）`,
    };
  }
}

function checkProjectStructure(projectRoot: string): CheckResult {
  const root = codecgcRoot(projectRoot);
  if (!existsSync(root)) {
    return {
      name: "项目结构",
      status: "error",
      detail: `.codecgc/ 目录不存在，请运行 codecgc.init`,
    };
  }
  const required = ["features", "issues"];
  const missing = required.filter((sub) => !existsSync(join(root, sub)));
  if (missing.length > 0) {
    return {
      name: "项目结构",
      status: "warn",
      detail: `缺少子目录: ${missing.join(", ")}`,
    };
  }
  return { name: "项目结构", status: "ok", detail: `.codecgc/ 完整` };
}

function checkRoutingFile(projectRoot: string): CheckResult {
  const file = routingFile(projectRoot);
  if (!existsSync(file)) {
    return {
      name: "路由策略",
      status: "warn",
      detail: `.codecgc/config/routing.yaml 不存在，将使用默认策略`,
    };
  }
  return { name: "路由策略", status: "ok", detail: file };
}

async function checkMcpConfig(projectRoot: string): Promise<CheckResult> {
  const file = join(projectRoot, ".mcp.json");
  if (!existsSync(file)) {
    return {
      name: "MCP 配置",
      status: "warn",
      detail: `.mcp.json 不存在`,
    };
  }
  try {
    const content = await readFile(file, "utf-8");
    const config = JSON.parse(content);
    if (!config.mcpServers) {
      return {
        name: "MCP 配置",
        status: "warn",
        detail: `.mcp.json 缺少 mcpServers 字段`,
      };
    }
    const serverCount = Object.keys(config.mcpServers).length;
    return {
      name: "MCP 配置",
      status: "ok",
      detail: `${serverCount} 个 MCP 服务器`,
    };
  } catch (error) {
    return {
      name: "MCP 配置",
      status: "error",
      detail: `.mcp.json 解析失败: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

function generateDoctorRecommendation(checks: CheckResult[], overall: DoctorResult["overall"]): string {
  if (overall === "healthy") {
    return "环境健康，可以正常使用 CodeCGC 工作流。";
  }

  const issues: string[] = [];
  for (const check of checks) {
    if (check.status === "error") {
      issues.push(`[ERROR] ${check.name}: ${check.detail}`);
    } else if (check.status === "warn") {
      issues.push(`[WARN] ${check.name}: ${check.detail}`);
    }
  }

  if (overall === "broken") {
    return `环境异常，需修复后才能使用：\n${issues.join("\n")}`;
  }
  return `环境降级，部分功能可能不可用：\n${issues.join("\n")}`;
}
