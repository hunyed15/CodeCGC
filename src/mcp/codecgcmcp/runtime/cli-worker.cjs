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

function detectPhase(event) {
  if (!event || !event.type) return "unknown";
  const type = event.type;
  if (type === "turn.completed" || type === "result") return "completed";
  if (type === "tool_use" && event.tool) {
    const tool = (typeof event.tool === "string" ? event.tool : "").toLowerCase();
    if (tool.includes("read") || tool.includes("grep") || tool.includes("glob") || tool.includes("search")) return "reading";
    if (tool.includes("write") || tool.includes("edit") || tool.includes("create")) return "writing";
  }
  if (type === "message" && event.role === "assistant") return "thinking";
  return "active";
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
  let lastEventTime = Date.now();
  let heartbeatWarned = false;

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

  // 心跳检测（每 30 秒检查一次，2 分钟无事件 = 可疑）
  const HEARTBEAT_INTERVAL = 30_000;  // 检查间隔 30 秒
  const HEARTBEAT_THRESHOLD = 120_000; // 2 分钟无事件 = 可疑
  const heartbeatCheck = setInterval(() => {
    const elapsed = Date.now() - lastEventTime;
    if (elapsed > HEARTBEAT_THRESHOLD && !heartbeatWarned) {
      heartbeatWarned = true;
      const warning = `[cli-worker] 警告：${Math.floor(elapsed / 1000)}秒 无 stdout 事件，CLI 可能卡死（PID=${proc.pid}）`;
      console.error(warning);
      writeFileSync(resultFile + ".heartbeat-warning", warning + " time=" + new Date().toISOString());
    }
  }, HEARTBEAT_INTERVAL);

  // 事件驱动读取 stdout（不阻塞事件循环）
  proc.stdout.on("data", (chunk) => {
    lastEventTime = Date.now(); // 更新心跳时间
    heartbeatWarned = false;    // 重置警告标志

    buffer += chunk.toString();
    const lines = buffer.split("\n");
    buffer = lines.pop() || ""; // 保留不完整的行

    for (const line of lines) {
      const event = tryParseJson(line);
      if (!event) continue;

      // 写进度文件（供 runViaWorker 读取）
      const phase = detectPhase(event);
      try {
        writeFileSync(resultFile + ".progress", JSON.stringify({
          phase,
          lastEventTime: Date.now(),
          lastEventType: event.type || "unknown",
          isAlive: true,
        }));
      } catch {}

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
  clearInterval(heartbeatCheck);

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

