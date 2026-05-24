/**
 * CLI worker — 在独立进程中 spawn CLI 工具
 * 结果写入临时文件（argv[3]），避免 stdout 被父进程干扰
 *
 * 关键修复：使用事件驱动的 stdout.on('data') 而非 readline + for-await
 * 避免阻塞 Node.js 事件循环（MCP server 需要事件循环处理协议心跳）
 */
const { spawn } = require("child_process");
const { writeFileSync } = require("fs");

const opts = JSON.parse(process.argv[2]);
const resultFile = process.argv[3];

// 立即写入启动标记（调试用）
writeFileSync(resultFile + ".started", "pid=" + process.pid + " time=" + new Date().toISOString());

function tryParseJson(line) {
  try {
    const parsed = JSON.parse(line.trim());
    if (typeof parsed === "object" && parsed !== null) return parsed;
    return null;
  } catch { return null; }
}

async function main() {
  const proc = spawn(opts.cmd, opts.args, {
    cwd: opts.cd,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, ...opts.env },
    windowsHide: true,
  });

  writeFileSync(resultFile + ".spawned", "gemini_pid=" + proc.pid + " cmd=" + opts.cmd + " args_len=" + opts.args.length);

  proc.on("error", (e) => {
    writeFileSync(resultFile + ".spawn-error", e.message);
  });

  let sessionId = opts.sessionId || "";
  let agentMessages = "";
  let errorMessage = "";
  let timedOut = false;
  let buffer = "";
  let stderrBuffer = "";

  const timeout = setTimeout(() => {
    timedOut = true;
    writeFileSync(resultFile + ".timeout", "timeout at " + new Date().toISOString() + " stderr=" + stderrBuffer.slice(0, 500));
    try {
      if (process.platform === "win32") {
        require("child_process").execFileSync("taskkill", ["/PID", String(proc.pid), "/T", "/F"], { stdio: "ignore" });
      } else {
        process.kill(-proc.pid, "SIGTERM");
      }
    } catch {}
  }, opts.timeoutMs || 600000);

  // 事件驱动读取 stdout（不阻塞事件循环）
  proc.stdout.on("data", (chunk) => {
    buffer += chunk.toString();
    const lines = buffer.split("\n");
    buffer = lines.pop() || ""; // 保留不完整的行

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
        setTimeout(() => proc.kill(), 300);
      }
    }
  });

  // 捕获 stderr（调试用）
  proc.stderr.on("data", (chunk) => {
    stderrBuffer += chunk.toString();
  });

  await new Promise((resolve) => {
    proc.once("exit", resolve);
    setTimeout(() => { try { proc.kill(); } catch {} resolve(); }, opts.timeoutMs + 5000);
  });

  clearTimeout(timeout);

  const result = {
    success: timedOut ? false : (!!sessionId && !errorMessage),
    sessionId,
    agentMessages,
    error: timedOut ? `执行超时（${opts.timeoutMs}ms）` : (errorMessage || undefined),
  };

  writeFileSync(resultFile, JSON.stringify(result));
}

main().catch(e => {
  writeFileSync(resultFile, JSON.stringify({ success: false, sessionId: "", agentMessages: "", error: e.message }));
});

