import { spawn } from "child_process";
import { Worker } from "worker_threads";
import { resolve, join, dirname } from "path";
import { fileURLToPath } from "url";
import { existsSync, readFileSync, unlinkSync } from "fs";
import { randomBytes } from "crypto";
import { tmpdir } from "os";
import type { StepExecutor, WorkflowStep } from "../../../shared/types.js";
import { resolveCliCommand, tryParseJson } from "../../../shared/process.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * MCP 执行器调用结果
 */
export interface ExecutorCallResult {
  success: boolean;
  sessionId: string;
  summary: string;
  agentMessages: string;
  changedFiles: string[];
  policyChecks: string[];
  risks: string[];
  error?: string;
}

/**
 * 通过 spawn worker + 轮询临时文件执行 CLI（用于 backend）
 * 异步 spawn 不阻塞事件循环（保持 MCP 协议心跳），结果通过临时文件传递
 */
async function runViaWorker(opts: {
  cli?: "codex" | "gemini";
  cmd: string[];
  args: string[];
  cd: string;
  env: Record<string, string>;
  sessionId: string;
  timeoutMs: number;
}): Promise<{ success: boolean; sessionId: string; agentMessages: string; error?: string }> {
  const workerPath = join(__dirname, "cli-worker.cjs");
  const resultFile = join(tmpdir(), `cgc-worker-${randomBytes(6).toString("hex")}.json`);

  return new Promise((res) => {
    const child = spawn("node", [workerPath, JSON.stringify({
      cli: opts.cli || "codex",
      cmd: opts.cmd[0],
      args: [...opts.cmd.slice(1), ...opts.args],
      cd: opts.cd,
      env: opts.env,
      sessionId: opts.sessionId,
      timeoutMs: opts.timeoutMs,
    }), resultFile], {
      stdio: "ignore",
      windowsHide: true,
    });

    let resolved = false;
    let lastProgressWarn = 0;

    const fallbackTimeout = setTimeout(() => {
      if (resolved) return;
      resolved = true;
      try { child.kill(); } catch {}
      res({ success: false, sessionId: "", agentMessages: "", error: "Worker 超时" });
    }, opts.timeoutMs + 15000);

    const pollInterval = setInterval(() => {
      if (resolved) { clearInterval(pollInterval); return; }
      if (existsSync(resultFile)) {
        clearInterval(pollInterval);
        clearTimeout(fallbackTimeout);
        if (resolved) return;
        resolved = true;
        try {
          const content = readFileSync(resultFile, "utf-8");
          const result = JSON.parse(content);
          res(result);
        } catch (e) {
          res({ success: false, sessionId: "", agentMessages: "", error: `结果解析失败: ${e}` });
        } finally {
          try { unlinkSync(resultFile); } catch {}
          try { unlinkSync(resultFile + ".progress"); } catch {}
        }
      } else {
        // 读取进度文件检测卡死（节流 60 秒）
        const progressFile = resultFile + ".progress";
        const now = Date.now();
        if (now - lastProgressWarn > 60_000 && existsSync(progressFile)) {
          try {
            const raw = readFileSync(progressFile, "utf-8");
            const progress = JSON.parse(raw);
            const elapsed = now - progress.lastEventTime;
            if (elapsed > 120_000) {
              lastProgressWarn = now;
              console.error(`[runViaWorker] ⚠️ CLI 可能卡死: phase=${progress.phase}, ${Math.floor(elapsed / 1000)}s 无事件`);
            }
          } catch {}
        }
      }
    }, 2000);

    child.on("exit", () => {
      setTimeout(() => {
        if (resolved) return;
        clearInterval(pollInterval);
        clearTimeout(fallbackTimeout);
        resolved = true;
        if (existsSync(resultFile)) {
          try {
            const content = readFileSync(resultFile, "utf-8");
            const result = JSON.parse(content);
            res(result);
          } catch (e) {
            res({ success: false, sessionId: "", agentMessages: "", error: `结果解析失败: ${e}` });
          } finally {
            try { unlinkSync(resultFile); } catch {}
          }
        } else {
          res({ success: false, sessionId: "", agentMessages: "", error: "Worker 退出但无结果文件" });
        }
      }, 500);
    });

    child.on("error", (err) => {
      if (resolved) return;
      resolved = true;
      clearInterval(pollInterval);
      clearTimeout(fallbackTimeout);
      res({ success: false, sessionId: "", agentMessages: "", error: err.message });
    });
  });
}

function getHttpServiceUrl(): string | null {
  const url = process.env.GEMINI_HTTP_SERVICE_URL || "http://127.0.0.1:37428";
  try {
    const u = new URL(url);
    if (u.hostname !== "127.0.0.1" && u.hostname !== "localhost" && u.hostname !== "::1") {
      console.error(`[runCliViaHttp] 不允许的 HTTP 服务地址: ${u.hostname}`);
      return null;
    }
    return url;
  } catch {
    console.error(`[runCliViaHttp] 无效的 HTTP 服务 URL: ${url}`);
    return null;
  }
}

async function isHttpServiceAvailable(): Promise<boolean> {
  const url = getHttpServiceUrl();
  if (!url) return false;
  try {
    const res = await fetch(`${url}/health`, { signal: AbortSignal.timeout(1000) });
    return res.ok;
  } catch {
    return false;
  }
}

/**
 * 通过独立 HTTP 服务调用 CLI（Gemini / Codex）
 * 提交执行请求 → 轮询结果，期间定期查询进度
 */
async function runCliViaHttp(opts: {
  cli: "gemini" | "codex";
  cmd: string[];
  args: string[];
  cd: string;
  env: Record<string, string>;
  sessionId: string;
  timeoutMs: number;
}): Promise<{ success: boolean; sessionId: string; agentMessages: string; error?: string }> {
  const HTTP_SERVICE_URL = getHttpServiceUrl();
  if (!HTTP_SERVICE_URL) {
    return { success: false, sessionId: "", agentMessages: "", error: "HTTP 服务 URL 不合法" };
  }

  try {
    console.error(`[runCliViaHttp:${opts.cli}] Calling ${HTTP_SERVICE_URL}/execute`);
    const executeRes = await fetch(`${HTTP_SERVICE_URL}/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cli: opts.cli,
        cmd: opts.cmd[0],
        args: [...opts.cmd.slice(1), ...opts.args],
        cd: opts.cd,
        env: opts.env,
        timeoutMs: opts.timeoutMs,
      }),
    });

    if (!executeRes.ok) {
      const error = await executeRes.json() as { error?: string };
      return { success: false, sessionId: "", agentMessages: "", error: error.error || "HTTP service error" };
    }

    const { requestId } = await executeRes.json() as { requestId: string };
    console.error(`[runCliViaHttp:${opts.cli}] Got requestId: ${requestId}`);

    const startTime = Date.now();
    let lastProgressCheck = startTime;
    const PROGRESS_CHECK_INTERVAL = 60_000;

    while (Date.now() - startTime < opts.timeoutMs + 10000) {
      await new Promise(r => setTimeout(r, 2000));

      const resultRes = await fetch(`${HTTP_SERVICE_URL}/result/${requestId}`);
      if (resultRes.ok) {
        console.error(`[runCliViaHttp:${opts.cli}] Got result after ${Date.now() - startTime}ms`);
        return await resultRes.json() as { success: boolean; sessionId: string; agentMessages: string; error?: string };
      }

      const now = Date.now();
      if (now - lastProgressCheck > PROGRESS_CHECK_INTERVAL) {
        lastProgressCheck = now;
        try {
          const progressRes = await fetch(`${HTTP_SERVICE_URL}/progress/${requestId}`);
          if (progressRes.ok) {
            const progress = await progressRes.json() as {
              phase: string;
              lastEventTime: number;
              isAlive: boolean;
              isStuck: boolean;
              elapsedSinceLastEvent: number;
            };
            console.error(`[runCliViaHttp:${opts.cli}] Progress: phase=${progress.phase}, isStuck=${progress.isStuck}, elapsed=${Math.floor(progress.elapsedSinceLastEvent / 1000)}s`);
            if (progress.isStuck) {
              console.error(`[runCliViaHttp:${opts.cli}] ⚠️ CLI appears stuck (no events for ${Math.floor(progress.elapsedSinceLastEvent / 1000)}s)`);
            }
          }
        } catch (e) {
          console.error(`[runCliViaHttp:${opts.cli}] Progress check failed:`, e);
        }
      }
    }

    console.error(`[runCliViaHttp:${opts.cli}] Polling timeout`);
    return { success: false, sessionId: "", agentMessages: "", error: "HTTP 轮询超时" };
  } catch (e: any) {
    console.error(`[runCliViaHttp:${opts.cli}] Exception:`, e.message);
    return { success: false, sessionId: "", agentMessages: "", error: `HTTP 服务不可用: ${e.message}` };
  }
}

/**
 * 使用 worker_threads 在独立线程中 spawn Gemini CLI（已废弃，改用 HTTP 服务）
 * 模仿 Python geminimcp 的 threading.Thread 架构，避免主线程 MCP 协议干扰
 */
async function runGeminiInWorkerThread(opts: {
  cmd: string[];
  args: string[];
  cd: string;
  env: Record<string, string>;
  sessionId: string;
  timeoutMs: number;
}): Promise<{ success: boolean; sessionId: string; agentMessages: string; error?: string }> {
  const workerPath = join(__dirname, "gemini-worker-thread.cjs");

  return new Promise((res, rej) => {
    const worker = new Worker(workerPath, {
      workerData: {
        cmd: opts.cmd[0],
        args: [...opts.cmd.slice(1), ...opts.args],
        cd: opts.cd,
        env: opts.env,
        timeoutMs: opts.timeoutMs,
      },
    });

    let resolved = false;

    // 超时保护（worker 内部也有超时，这是双重保险）
    const fallbackTimeout = setTimeout(() => {
      if (resolved) return;
      resolved = true;
      worker.terminate();
      res({ success: false, sessionId: "", agentMessages: "", error: "Worker thread 超时" });
    }, opts.timeoutMs + 20000);

    worker.on("message", (result) => {
      if (resolved) return;
      resolved = true;
      clearTimeout(fallbackTimeout);
      worker.terminate();
      res(result);
    });

    worker.on("error", (err) => {
      if (resolved) return;
      resolved = true;
      clearTimeout(fallbackTimeout);
      res({ success: false, sessionId: "", agentMessages: "", error: err.message });
    });

    worker.on("exit", (code) => {
      if (resolved) return;
      resolved = true;
      clearTimeout(fallbackTimeout);
      if (code !== 0) {
        res({ success: false, sessionId: "", agentMessages: "", error: `Worker thread 退出 code=${code}` });
      } else {
        res({ success: false, sessionId: "", agentMessages: "", error: "Worker thread 退出但无结果" });
      }
    });
  });
}

/**
 * 直接在 MCP server 进程中 spawn Gemini CLI（已废弃，改用 worker_threads）
 * 不用 worker 中转，避免进程树嵌套问题
 */
async function runGeminiDirectly(opts: {
  cmd: string[];
  args: string[];
  cd: string;
  env: Record<string, string>;
  sessionId: string;
  timeoutMs: number;
}): Promise<{ success: boolean; sessionId: string; agentMessages: string; error?: string }> {
  return new Promise((res) => {
    const proc = spawn(opts.cmd[0], [...opts.cmd.slice(1), ...opts.args], {
      cwd: opts.cd,
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, ...opts.env },
      windowsHide: true,
    });

    let sessionId = opts.sessionId || "";
    let agentMessages = "";
    let errorMessage = "";
    let timedOut = false;
    let buffer = "";
    let resolved = false;

    const timeout = setTimeout(() => {
      if (resolved) return;
      timedOut = true;
      resolved = true;
      try {
        if (process.platform === "win32") {
          const { execFileSync } = require("child_process");
          execFileSync("taskkill", ["/PID", String(proc.pid!), "/T", "/F"], { stdio: "ignore" });
        } else {
          process.kill(-proc.pid!, "SIGTERM");
        }
      } catch {}
      res({ success: false, sessionId: "", agentMessages: "", error: `执行超时（${opts.timeoutMs}ms）` });
    }, opts.timeoutMs);

    proc.stdout.on("data", (chunk: Buffer) => {
      buffer += chunk.toString();
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const event = tryParseJson(line);
        if (!event) continue;
        if (event.session_id && typeof event.session_id === "string") {
          sessionId = event.session_id;
        }
        if (event.thread_id && typeof event.thread_id === "string") {
          sessionId = event.thread_id;
        }
        if (event.type === "message" && event.role === "assistant" && typeof event.content === "string") {
          agentMessages += event.content;
        }
        if (event.item && typeof event.item === "object" && event.item !== null) {
          const item = event.item as Record<string, unknown>;
          if (item.type === "agent_message" && typeof item.text === "string") {
            agentMessages += item.text;
          }
        }
        if (event.type === "error" && typeof event.message === "string") {
          if (!/^Reconnecting\.\.\.\s+\d+\/\d+/.test(event.message)) {
            errorMessage = event.message;
          }
        }
        if (typeof event.type === "string" && event.type.includes("fail")) {
          errorMessage = JSON.stringify(event);
        }
        if (event.type === "turn.completed" || event.type === "result") {
          setTimeout(() => { try { proc.kill(); } catch {} }, 300);
        }
      }
    });

    proc.on("exit", () => {
      if (resolved) return;
      clearTimeout(timeout);
      resolved = true;
      res({
        success: timedOut ? false : (!!sessionId && !errorMessage),
        sessionId,
        agentMessages,
        error: timedOut ? `执行超时（${opts.timeoutMs}ms）` : (errorMessage || undefined),
      });
    });

    proc.on("error", (err) => {
      if (resolved) return;
      clearTimeout(timeout);
      resolved = true;
      res({ success: false, sessionId: "", agentMessages: "", error: err.message });
    });
  });
}

/**
 * 通过 HTTP 服务调用后端执行器（Codex CLI），HTTP 不可用时回退到 worker
 */
export async function callBackendExecutor(
  step: WorkflowStep,
  projectRoot: string,
  timeoutMs = 900_000
): Promise<ExecutorCallResult> {
  const cmd = await resolveCliCommand("codex");
  const cd = resolve(step.cd ?? projectRoot);
  const prompt = buildBackendPrompt(step);

  const args = [
    "exec",
    "--sandbox", "workspace-write",
    "--cd", cd,
    "--json",
    "--skip-git-repo-check",
  ];
  if (step.session_id) args.push("resume", step.session_id);
  args.push("--", prompt);

  const env = { PYTHON: process.execPath };
  const sessionId = step.session_id ?? "";

  let result: { success: boolean; sessionId: string; agentMessages: string; error?: string };
  if (await isHttpServiceAvailable()) {
    console.error(`[callBackendExecutor] HTTP service available, using HTTP path`);
    result = await runCliViaHttp({ cli: "codex", cmd, args, cd, env, sessionId, timeoutMs });
  } else {
    console.error(`[callBackendExecutor] HTTP service unavailable, falling back to worker`);
    result = await runViaWorker({ cmd, args, cd, env, sessionId, timeoutMs });
  }

  return {
    success: result.success,
    sessionId: result.sessionId,
    summary: result.agentMessages,
    agentMessages: result.agentMessages,
    changedFiles: [],
    policyChecks: result.success ? ["backend_executor_completed"] : [],
    risks: [],
    error: result.error,
  };
}

/**
 * 通过 HTTP 服务调用前端执行器（Gemini CLI），HTTP 不可用时回退到 worker
 */
export async function callFrontendExecutor(
  step: WorkflowStep,
  projectRoot: string,
  timeoutMs = 900_000
): Promise<ExecutorCallResult> {
  const cmd = await resolveCliCommand("gemini");
  const cd = resolve(step.cd ?? projectRoot);
  const prompt = buildFrontendPrompt(step);

  const args = [
    "--skip-trust",
    "--approval-mode", "yolo",
    "--prompt", prompt,
    "-o", "stream-json",
    "--allowed-mcp-server-names", "__codecgc_none__",
  ];
  if (step.session_id) args.push("--resume", step.session_id);

  const env = { GEMINI_CLI_TRUST_WORKSPACE: "true", NODE_OPTIONS: "" };
  const sessionId = step.session_id ?? "";

  let result: { success: boolean; sessionId: string; agentMessages: string; error?: string };
  if (await isHttpServiceAvailable()) {
    console.error(`[callFrontendExecutor] HTTP service available, using HTTP path`);
    result = await runCliViaHttp({ cli: "gemini", cmd, args, cd, env, sessionId, timeoutMs });
  } else {
    console.error(`[callFrontendExecutor] HTTP service unavailable, falling back to worker`);
    result = await runViaWorker({ cli: "gemini", cmd, args, cd, env, sessionId, timeoutMs });
  }

  return {
    success: result.success,
    sessionId: result.sessionId,
    summary: result.agentMessages,
    agentMessages: result.agentMessages,
    changedFiles: [],
    policyChecks: result.success ? ["frontend_executor_completed"] : [],
    risks: [],
    error: result.error,
  };
}

function buildBackendPrompt(step: WorkflowStep): string {
  const MAX_FIELD_LENGTH = 10000;
  const MAX_ARRAY_LENGTH = 200;

  // 验证字段长度
  if (step.summary.length > MAX_FIELD_LENGTH) {
    throw new Error(`step.summary 超过最大长度 ${MAX_FIELD_LENGTH} 字符`);
  }
  if (step.paths.length > MAX_ARRAY_LENGTH) {
    throw new Error(`step.paths 超过最大数组长度 ${MAX_ARRAY_LENGTH}`);
  }
  if (step.constraints && step.constraints.length > MAX_ARRAY_LENGTH) {
    throw new Error(`step.constraints 超过最大数组长度 ${MAX_ARRAY_LENGTH}`);
  }
  if (step.acceptance && step.acceptance.length > MAX_ARRAY_LENGTH) {
    throw new Error(`step.acceptance 超过最大数组长度 ${MAX_ARRAY_LENGTH}`);
  }

  const lines: string[] = [
    `任务 ID：${step.task_id}`,
    ``,
    `## 任务描述`,
    step.summary,
    ``,
    `## 目标路径`,
    step.paths.map((p) => `- ${p}`).join("\n"),
  ];
  if (step.constraints && step.constraints.length > 0) {
    lines.push(``, `## 约束条件`);
    step.constraints.forEach((c) => lines.push(`- ${c}`));
  }
  if (step.acceptance && step.acceptance.length > 0) {
    lines.push(``, `## 验收标准`);
    step.acceptance.forEach((a) => lines.push(`- ${a}`));
  }
  return lines.join("\n");
}

function buildFrontendPrompt(step: WorkflowStep): string {
  const MAX_FIELD_LENGTH = 10000;
  const MAX_ARRAY_LENGTH = 200;

  // 验证字段长度
  if (step.summary.length > MAX_FIELD_LENGTH) {
    throw new Error(`step.summary 超过最大长度 ${MAX_FIELD_LENGTH} 字符`);
  }
  if (step.paths.length > MAX_ARRAY_LENGTH) {
    throw new Error(`step.paths 超过最大数组长度 ${MAX_ARRAY_LENGTH}`);
  }
  if (step.constraints && step.constraints.length > MAX_ARRAY_LENGTH) {
    throw new Error(`step.constraints 超过最大数组长度 ${MAX_ARRAY_LENGTH}`);
  }
  if (step.acceptance && step.acceptance.length > MAX_ARRAY_LENGTH) {
    throw new Error(`step.acceptance 超过最大数组长度 ${MAX_ARRAY_LENGTH}`);
  }

  const lines: string[] = [
    `任务 ID：${step.task_id}`,
    ``,
    `## 任务描述`,
    step.summary,
    ``,
    `## 目标路径`,
    step.paths.map((p) => `- ${p}`).join("\n"),
  ];
  if (step.constraints && step.constraints.length > 0) {
    lines.push(``, `## 约束条件`);
    step.constraints.forEach((c) => lines.push(`- ${c}`));
  }
  if (step.acceptance && step.acceptance.length > 0) {
    lines.push(``, `## 验收标准`);
    step.acceptance.forEach((a) => lines.push(`- ${a}`));
  }
  return lines.join("\n");
}

/**
 * 根据 executor 类型路由调用
 */
export async function callExecutor(
  step: WorkflowStep,
  projectRoot: string,
  timeoutMs = 900_000
): Promise<ExecutorCallResult> {
  // Input validation
  if (!step || typeof step !== "object") {
    throw new Error("step is required and must be an object");
  }
  if (!projectRoot || typeof projectRoot !== "string") {
    throw new Error("projectRoot is required and must be a string");
  }
  if (typeof timeoutMs !== "number" || timeoutMs <= 0 || timeoutMs > 3600_000) {
    throw new Error("timeoutMs must be between 1 and 3600000 (1 hour)");
  }

  if (step.executor === "backend") {
    return callBackendExecutor(step, projectRoot, timeoutMs);
  }
  if (step.executor === "frontend") {
    return callFrontendExecutor(step, projectRoot, timeoutMs);
  }
  if (step.executor === "docs" || step.executor === "orchestration") {
    // docs 和 orchestration 由 Claude 直接处理，不调用执行器
    throw new Error(`${step.executor} 步骤应由 Claude 直接处理，不应调用执行器`);
  }
  throw new Error(`不支持的 executor: ${step.executor}`);
}
