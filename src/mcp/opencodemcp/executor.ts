import { spawn } from "child_process";
import { createDebugLogger } from "../../shared/debug.js";
import { killProcessTree, readlines, resolveCliCommand, tryParseJson, wait } from "../../shared/process.js";
import type { ExecutorResult, OpenCodeOptions } from "../../shared/types.js";

const debug = createDebugLogger("opencodemcp");

const DEFAULT_TIMEOUT_MS = 600_000; // 10 分钟

/**
 * 执行 OpenCode CLI 会话
 */
export async function runOpenCodeSession(opts: OpenCodeOptions): Promise<ExecutorResult> {
  // Input validation
  if (!opts.prompt || typeof opts.prompt !== "string") {
    throw new Error("prompt is required and must be a string");
  }
  if (opts.prompt.length > 50000) {
    throw new Error("prompt too long (max 50000 characters)");
  }
  if (!opts.cd || typeof opts.cd !== "string") {
    throw new Error("cd is required and must be a string");
  }

  const cmd = await resolveCliCommand("opencode");
  const args = buildOpenCodeArgs(opts);
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  if (typeof timeoutMs !== "number" || timeoutMs <= 0 || timeoutMs > 3600_000) {
    throw new Error("timeoutMs must be between 1 and 3600000 (1 hour)");
  }

  debug.log("spawn:", cmd[0], cmd.slice(1).concat(args).join(" ").slice(0, 200));
  debug.log("cwd:", opts.cd);

  const proc = spawn(cmd[0], [...cmd.slice(1), ...args], {
    cwd: opts.cd,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      NODE_OPTIONS: "",
    },
    windowsHide: true,
  });

  debug.log("PID:", proc.pid);

  // 调试：监听 stderr
  proc.stderr?.on("data", (chunk) => {
    const text = chunk.toString();
    if (text.includes('"type"')) {
      debug.warn("JSON ON STDERR!");
    }
  });

  let sessionId = opts.sessionId ?? "";
  let agentMessages = "";
  const allMessages: unknown[] = [];
  let errorMessage = "";
  let timedOut = false;

  const timeout = setTimeout(() => {
    timedOut = true;
    killProcessTree(proc.pid);
  }, timeoutMs);

  try {
    // 只读 stdout
    let lineCount = 0;
    for await (const line of readlines(proc.stdout)) {
      lineCount++;
      const event = tryParseJson(line);
      if (!event) {
        debug.log("non-json line:", line.slice(0, 100));
        continue;
      }

      debug.log("event type:", event.type);

      if (opts.returnAllMessages) allMessages.push(event);

      // 提取 session_id（OpenCode 可能使用 session_id 或 thread_id）
      if (event.session_id && typeof event.session_id === "string") {
        sessionId = event.session_id;
      }
      if (event.thread_id && typeof event.thread_id === "string") {
        sessionId = event.thread_id;
      }

      // 提取 assistant 消息（支持多种格式）
      if (event.type === "message" && event.role === "assistant" && typeof event.content === "string") {
        agentMessages += event.content;
      }
      // Codex 格式
      if (event.item && typeof event.item === "object") {
        const item = event.item as Record<string, unknown>;
        if (item.type === "agent_message" && typeof item.text === "string") {
          agentMessages += item.text;
        }
      }

      // 检测错误
      if (event.type === "error" && typeof event.message === "string") {
        errorMessage = event.message;
      }
      if (typeof event.type === "string" && event.type.includes("fail")) {
        errorMessage = JSON.stringify(event);
      }

      // 检测终止信号（支持多种格式）
      if (event.type === "turn.completed" || event.type === "result") {
        await wait(300);
        proc.kill();
        break;
      }
    }
  } finally {
    clearTimeout(timeout);
  }

  await new Promise<void>((resolve) => {
    proc.once("exit", () => resolve());
    setTimeout(() => {
      killProcessTree(proc.pid);
      resolve();
    }, 5000);
  });

  if (timedOut) {
    return {
      success: false,
      sessionId,
      agentMessages,
      error: `OpenCode 执行超时（${timeoutMs}ms）`,
    };
  }

  const success = !!sessionId && !errorMessage;
  return {
    success,
    sessionId,
    agentMessages,
    allMessages: opts.returnAllMessages ? allMessages : undefined,
    error: errorMessage || undefined,
  };
}

/**
 * 构建 OpenCode CLI 参数
 * 注意：这里的参数需要根据 OpenCode 实际 CLI 接口调整
 */
function buildOpenCodeArgs(opts: OpenCodeOptions): string[] {
  const args = [
    "--json", // 假设 OpenCode 支持 JSON 输出
    "--prompt",
    opts.prompt,
  ];

  if (opts.sandbox) args.push("--sandbox");
  if (opts.model) args.push("--model", opts.model);
  if (opts.sessionId) args.push("--resume", opts.sessionId);

  return args;
}
