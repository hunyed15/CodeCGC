import { spawn, execFileSync } from "child_process";
import { createInterface } from "readline";
import * as fs from "fs";
import * as path from "path";
import { Readable } from "stream";
import which from "which";

/**
 * 解析 CLI 命令，优先使用 node + js 入口文件绕过 .cmd shim
 * 参考 codecgc Python 版本的 resolve_cli_command()
 */
export async function resolveCliCommand(name: string): Promise<string[]> {
  try {
    const shimPath = await which(name);
    const jsEntry = findNodeModuleEntry(shimPath, name);
    if (jsEntry) return ["node", jsEntry];
  } catch {
    // which 找不到，继续尝试回退
  }

  // Windows 回退：直接使用 .cmd
  if (process.platform === "win32") return [`${name}.cmd`];
  return [name];
}

/**
 * 从 shim 路径逆推 node_modules 中的 .js 入口
 */
function findNodeModuleEntry(shimPath: string, name: string): string | null {
  // shim 通常在 /usr/local/bin/codex 或 C:\...\npm\codex.cmd
  // node_modules 通常相邻于 shim 所在目录
  const shimDir = path.dirname(shimPath);
  const candidates = [
    // npm 全局安装布局
    path.join(shimDir, "..", "lib", "node_modules", `@openai/${name}`, "bin", `${name}.js`),
    path.join(shimDir, "..", "lib", "node_modules", `@google/${name}-cli`, "bundle", `${name}.js`),
    path.join(shimDir, "..", "lib", "node_modules", `@opencode-ai/${name}`, "bin", `${name}.js`),
    // Windows npm 全局布局
    path.join(shimDir, "node_modules", `@openai/${name}`, "bin", `${name}.js`),
    path.join(shimDir, "node_modules", `@google/${name}-cli`, "bundle", `${name}.js`),
    path.join(shimDir, "node_modules", `@opencode-ai/${name}`, "bin", `${name}.js`),
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) return candidate;
  }
  return null;
}

/**
 * 逐行读取可读流（用于 NDJSON 流处理）
 */
export function readlines(stream: Readable): AsyncIterable<string> {
  const rl = createInterface({ input: stream, crlfDelay: Infinity });
  return rl[Symbol.asyncIterator]();
}

/**
 * 安全 JSON 解析，解析失败返回 null
 */
const MAX_JSON_LINE_BYTES = 1_048_576; // 1 MB

export function tryParseJson(line: string): Record<string, unknown> | null {
  if (line.length > MAX_JSON_LINE_BYTES) return null;
  try {
    const parsed = JSON.parse(line.trim());
    if (typeof parsed === "object" && parsed !== null) {
      return parsed as Record<string, unknown>;
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * 等待指定毫秒数
 */
export function wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * 终止进程树（Windows 用 taskkill，Unix 用 SIGTERM）
 */
export function killProcessTree(pid: number | undefined): void {
  if (!pid || pid <= 0 || !Number.isInteger(pid)) return;
  try {
    if (process.platform === "win32") {
      execFileSync("taskkill", ["/PID", String(pid), "/T", "/F"], { stdio: "ignore" });
    } else {
      process.kill(-pid, "SIGTERM");
    }
  } catch {
    // 进程可能已经退出
    try {
      process.kill(pid, "SIGTERM");
    } catch {
      // 忽略
    }
  }
}
