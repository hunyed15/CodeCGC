/**
 * Gemini CLI worker thread — 在独立线程中 spawn Gemini CLI
 * 模仿 Python geminimcp 的 threading.Thread 架构
 *
 * Worker thread 有独立的事件循环，不受主线程 MCP StdioServerTransport 影响
 */
const { parentPort, workerData } = require("worker_threads");
const { spawn } = require("child_process");

function tryParseJson(line) {
  try {
    const parsed = JSON.parse(line.trim());
    if (typeof parsed === "object" && parsed !== null) return parsed;
    return null;
  } catch {
    return null;
  }
}

async function main() {
  const { cmd, args, cd, env, timeoutMs } = workerData;

  // 完全隔离 stdin：使用 null 设备而不是 "ignore"
  const { openSync } = require("fs");
  const nullDevice = process.platform === "win32" ? "\\\\.\\nul" : "/dev/null";
  const stdinFd = openSync(nullDevice, "r");

  const proc = spawn(cmd, args, {
    cwd: cd,
    stdio: [stdinFd, "pipe", "pipe"],
    env: { ...process.env, ...env },
    windowsHide: true,
    detached: false,
  });

  let sessionId = "";
  let agentMessages = "";
  let errorMessage = "";
  let timedOut = false;
  let buffer = "";

  const timeout = setTimeout(() => {
    timedOut = true;
    try {
      if (process.platform === "win32") {
        require("child_process").execFileSync("taskkill", ["/PID", String(proc.pid), "/T", "/F"], { stdio: "ignore" });
      } else {
        process.kill(-proc.pid, "SIGTERM");
      }
    } catch {}
  }, timeoutMs);

  proc.stdout.on("data", (chunk) => {
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
      if (event.item && event.item.type === "agent_message" && typeof event.item.text === "string") {
        agentMessages += event.item.text;
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
        setTimeout(() => {
          try {
            proc.kill();
          } catch {}
        }, 300);
      }
    }
  });

  await new Promise((resolve) => {
    proc.once("exit", () => {
      try {
        require("fs").closeSync(stdinFd);
      } catch {}
      resolve();
    });
    setTimeout(() => {
      try {
        proc.kill();
      } catch {}
      try {
        require("fs").closeSync(stdinFd);
      } catch {}
      resolve();
    }, timeoutMs + 5000);
  });

  clearTimeout(timeout);

  const result = {
    success: timedOut ? false : !!sessionId && !errorMessage,
    sessionId,
    agentMessages,
    error: timedOut ? `执行超时（${timeoutMs}ms）` : errorMessage || undefined,
  };

  parentPort.postMessage(result);
}

main().catch((e) => {
  parentPort.postMessage({ success: false, sessionId: "", agentMessages: "", error: e.message });
});
