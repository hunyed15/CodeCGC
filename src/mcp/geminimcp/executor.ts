import { spawn } from "child_process";
import * as path from "path";
import type { GeminiOptions, ExecutorResult } from "../../shared/types.js";
import { resolveCliCommand, readlines, tryParseJson, wait, killProcessTree } from "../../shared/process.js";

const DEFAULT_TIMEOUT_MS = 600_000;

export async function runGeminiSession(opts: GeminiOptions): Promise<ExecutorResult> {
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

  const cmd = await resolveCliCommand("gemini");
  const args = buildGeminiArgs(opts);
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  if (typeof timeoutMs !== "number" || timeoutMs <= 0 || timeoutMs > 3600_000) {
    throw new Error("timeoutMs must be between 1 and 3600000 (1 hour)");
  }

  console.error("[geminimcp] spawn:", cmd[0], cmd.slice(1).concat(args).join(" ").slice(0, 200));
  console.error("[geminimcp] cwd:", opts.cd);

  const proc = spawn(cmd[0], [...cmd.slice(1), ...args], {
    cwd: opts.cd,
    stdio: ["ignore", "pipe", "pipe"],
    env: {
      ...process.env,
      GEMINI_CLI_TRUST_WORKSPACE: "true",
      NODE_OPTIONS: "",
    },
    windowsHide: true,
  });

  console.error("[geminimcp] PID:", proc.pid);

  // 调试：监听 stderr 看 Gemini 是否把 JSON 输出到了 stderr
  proc.stderr?.on("data", (chunk) => {
    const text = chunk.toString();
    if (text.includes('"type"')) {
      console.error("[geminimcp] JSON ON STDERR!");
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
    // 只读 stdout（不合并 stderr，避免流关闭问题）
    let lineCount = 0;
    for await (const line of readlines(proc.stdout)) {
      lineCount++;
      const event = tryParseJson(line);
      if (!event) {
        console.error("[geminimcp] non-json line:", line.slice(0, 100));
        continue;
      }

      console.error("[geminimcp] event type:", event.type);
      if (!event) continue;

      if (opts.returnAllMessages) allMessages.push(event);

      // 提取 session_id（Gemini 字段名是 session_id，Codex 是 thread_id）
      if (event.session_id && typeof event.session_id === "string") {
        sessionId = event.session_id;
      }

      // 提取 assistant 消息
      if (
        event.type === "message" &&
        event.role === "assistant" &&
        typeof event.content === "string"
      ) {
        agentMessages += event.content;
      }

      // 检测错误
      if (event.type === "error" && typeof event.message === "string") {
        errorMessage = event.message;
      }

      // 检测终止信号（Gemini 用 turn.completed 或 result）
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
      error: `Gemini 执行超时（${timeoutMs}ms）`,
    };
  }

  // Gemini 特殊规则：agent_messages 为空可能是 tool call 导致（不算失败）
  const success = !!sessionId && !errorMessage;
  return {
    success,
    sessionId,
    agentMessages,
    allMessages: opts.returnAllMessages ? allMessages : undefined,
    error: errorMessage || undefined,
  };
}

function buildGeminiArgs(opts: GeminiOptions): string[] {
  const args = [
    "--skip-trust",
    "--approval-mode",
    "yolo",
    "--prompt",
    opts.prompt,
    "-o",
    "stream-json",
    "--allowed-mcp-server-names",
    "__codecgc_none__",
  ];

  if (opts.sandbox) args.push("--sandbox");
  if (opts.model) args.push("--model", opts.model);
  if (opts.sessionId) args.push("--resume", opts.sessionId);

  return args;
}
