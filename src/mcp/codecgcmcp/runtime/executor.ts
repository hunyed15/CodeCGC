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

/**
 * 通过独立 HTTP 服务调用 Gemini CLI
 * 绕过 MCP StdioServerTransport 的环境限制
 */
async function runGeminiViaHttp(opts: {
  cmd: string[];
  args: string[];
  cd: string;
  env: Record<string, string>;
  sessionId: string;
  timeoutMs: number;
}): Promise<{ success: boolean; sessionId: string; agentMessages: string; error?: string }> {
  const HTTP_SERVICE_URL = process.env.GEMINI_HTTP_SERVICE_URL || "http://127.0.0.1:37428";

  // URL 白名单：只允许 localhost
  try {
    const url = new URL(HTTP_SERVICE_URL);
    if (url.hostname !== "127.0.0.1" && url.hostname !== "localhost" && url.hostname !== "::1") {
      return { success: false, sessionId: "", agentMessages: "", error: `不允许的 HTTP 服务地址: ${url.hostname}` };
    }
  } catch (e) {
    return { success: false, sessionId: "", agentMessages: "", error: `无效的 HTTP 服务 URL: ${HTTP_SERVICE_URL}` };
  }

  try {
    console.error(`[runGeminiViaHttp] Calling ${HTTP_SERVICE_URL}/execute`);
    // 提交执行请求
    const executeRes = await fetch(`${HTTP_SERVICE_URL}/execute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
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
    console.error(`[runGeminiViaHttp] Got requestId: ${requestId}`);

    // 轮询结果（每 2 秒）+ 心跳检测（每 60 秒检查进度）
    const startTime = Date.now();
    let lastProgressCheck = startTime;
    const PROGRESS_CHECK_INTERVAL = 60_000; // 每 60 秒检查一次进度

    while (Date.now() - startTime < opts.timeoutMs + 10000) {
      await new Promise(r => setTimeout(r, 2000));

      // 先尝试获取结果
      const resultRes = await fetch(`${HTTP_SERVICE_URL}/result/${requestId}`);
      if (resultRes.ok) {
        console.error(`[runGeminiViaHttp] Got result after ${Date.now() - startTime}ms`);
        return await resultRes.json() as { success: boolean; sessionId: string; agentMessages: string; error?: string };
      }

      // 定期检查进度（心跳探查）
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
            console.error(`[runGeminiViaHttp] Progress check: phase=${progress.phase}, isStuck=${progress.isStuck}, elapsed=${Math.floor(progress.elapsedSinceLastEvent / 1000)}s`);

            // 如果检测到卡死，记录警告（但不中断，让超时机制处理）
            if (progress.isStuck) {
              console.error(`[runGeminiViaHttp] ⚠️ CLI appears stuck (no events for ${Math.floor(progress.elapsedSinceLastEvent / 1000)}s)`);
            }
          }
        } catch (e) {
          console.error(`[runGeminiViaHttp] Progress check failed:`, e);
        }
      }
    }

    console.error(`[runGeminiViaHttp] Polling timeout`);
    return { success: false, sessionId: "", agentMessages: "", error: "HTTP 轮询超时" };
  } catch (e: any) {
    console.error(`[runGeminiViaHttp] Exception:`, e.message);
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
 * 通过 fork worker 调用后端执行器（Codex CLI）
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

  const result = await runViaWorker({
    cmd,
    args,
    cd,
    env: { PYTHON: process.execPath },
    sessionId: step.session_id ?? "",
    timeoutMs,
  });

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
 * 通过 fork worker 调用前端执行器（Gemini CLI）
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

  const result = await runGeminiViaHttp({
    cmd,
    args,
    cd,
    env: { GEMINI_CLI_TRUST_WORKSPACE: "true", NODE_OPTIONS: "" },
    sessionId: step.session_id ?? "",
    timeoutMs,
  });

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
