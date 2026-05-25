import { spawn } from "child_process";
import type { CodexOptions, ExecutorResult } from "../../shared/types.js";
import { resolveCliCommand, readlines, tryParseJson, wait, killProcessTree } from "../../shared/process.js";

const DEFAULT_TIMEOUT_MS = 600_000; // 10 分钟

/**
 * 执行 Codex CLI 会话
 */
export async function runCodexSession(opts: CodexOptions): Promise<ExecutorResult> {
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

  const cmd = await resolveCliCommand("codex");
  const args = buildCodexArgs(opts);
  const timeoutMs = opts.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  if (typeof timeoutMs !== "number" || timeoutMs <= 0 || timeoutMs > 3600_000) {
    throw new Error("timeoutMs must be between 1 and 3600000 (1 hour)");
  }

  const proc = spawn(cmd[0], [...cmd.slice(1), ...args], {
    cwd: opts.cd,
    stdio: ["pipe", "pipe", "pipe"],
    env: { ...process.env, PYTHON: process.execPath },
    windowsHide: true,
  });

  // 关闭 stdin 避免 CLI 等待输入
  proc.stdin?.end();

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
    for await (const line of readlines(proc.stdout)) {
      const event = tryParseJson(line);
      if (!event) continue;

      if (opts.returnAllMessages) allMessages.push(event);

      // 提取 session_id
      if (event.thread_id && typeof event.thread_id === "string") {
        sessionId = event.thread_id;
      }

      // 提取 agent 消息
      if (event.item && typeof event.item === "object") {
        const item = event.item as Record<string, unknown>;
        if (item.type === "agent_message" && typeof item.text === "string") {
          agentMessages += item.text;
        }
      }

      // 检测错误（排除 Reconnecting 模式）
      if (event.type === "error" && typeof event.message === "string") {
        const msg = event.message;
        if (!/^Reconnecting\.\.\.\s+\d+\/\d+/.test(msg)) {
          errorMessage = msg;
        }
      }
      if (typeof event.type === "string" && event.type.includes("fail")) {
        errorMessage = JSON.stringify(event);
      }

      // 检测终止信号
      if (event.type === "turn.completed") {
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
      error: `Codex 执行超时（${timeoutMs}ms）`,
    };
  }

  const success = !!sessionId && !!agentMessages && !errorMessage;
  return {
    success,
    sessionId,
    agentMessages,
    allMessages: opts.returnAllMessages ? allMessages : undefined,
    error: errorMessage || undefined,
  };
}

/**
 * 构建 Codex CLI 参数
 */
function buildCodexArgs(opts: CodexOptions): string[] {
  const args = [
    "exec",
    "--sandbox",
    opts.sandbox ?? "read-only",
    "--cd",
    opts.cd,
    "--json",
  ];

  if (opts.skipGitRepoCheck) args.push("--skip-git-repo-check");
  if (opts.yolo) args.push("--yolo");
  if (opts.model) args.push("--model", opts.model);
  if (opts.profile) args.push("--profile", opts.profile);
  if (opts.images && opts.images.length > 0) {
    opts.images.forEach((img: string) => args.push("--image", img));
  }
  if (opts.sessionId) args.push("resume", opts.sessionId);

  args.push("--", opts.prompt);
  return args;
}
