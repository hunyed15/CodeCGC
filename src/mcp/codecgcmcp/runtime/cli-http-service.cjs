/**
 * 通用 CLI HTTP 服务
 *
 * 用途：绕过 MCP StdioServerTransport 的环境限制
 * 架构：独立进程 + HTTP API，codecgcmcp 通过 fetch 调用
 * 支持：Gemini、Codex、OpenCode 等 CLI
 *
 * 启动：node cli-http-service.cjs [port]
 * 默认端口：37428
 *
 * API:
 *   POST /execute
 *     body: { cli: "gemini"|"codex"|"opencode", cmd: "...", args: [...], cd: "...", env: {...}, timeoutMs: 600000 }
 *     response: { requestId: "..." }
 *   GET /result/:requestId
 *     response: { success: bool, sessionId: "...", agentMessages: "...", error?: "..." }
 *   GET /health
 *     response: { status: "ok", sessions: number }
 */
const http = require("http");
const { spawn } = require("child_process");
const { randomBytes } = require("crypto");

const PORT = parseInt(process.argv[2] || "37428", 10);
const sessions = new Map(); // requestId -> { success, sessionId, agentMessages, error }

function tryParseJson(line) {
  try {
    const parsed = JSON.parse(line.trim());
    if (typeof parsed === "object" && parsed !== null) return parsed;
    return null;
  } catch { return null; }
}

/**
 * 通用 CLI spawn 函数
 * @param {object} opts
 * @param {string} opts.cli - CLI 类型 (gemini/codex/opencode)
 * @param {string} opts.cmd - 命令路径
 * @param {string[]} opts.args - 命令参数
 * @param {string} opts.cd - 工作目录
 * @param {object} opts.env - 环境变量
 * @param {number} opts.timeoutMs - 超时时间
 */
function spawnCLI(opts) {
  const requestId = randomBytes(8).toString("hex");
  const cliType = opts.cli || "gemini";
  console.error(`[spawnCLI] Starting requestId=${requestId}, cli=${cliType}, cmd=${opts.cmd}, args=${JSON.stringify(opts.args).slice(0, 100)}`);

  const proc = spawn(opts.cmd, opts.args, {
    cwd: opts.cd,
    stdio: ["ignore", "pipe", "pipe"],
    env: { ...process.env, ...opts.env },
    windowsHide: true,
  });

  let sessionId = "";
  let agentMessages = "";
  let errorMessage = "";
  let stderrOutput = "";
  let buffer = "";
  let resolved = false;

  const timeout = setTimeout(() => {
    if (resolved) return;
    resolved = true;
    try {
      if (process.platform === "win32") {
        require("child_process").execFileSync("taskkill", ["/PID", String(proc.pid), "/T", "/F"], { stdio: "ignore" });
      } else {
        process.kill(-proc.pid, "SIGTERM");
      }
    } catch {}
    sessions.set(requestId, {
      success: false,
      sessionId: "",
      agentMessages: "",
      error: `执行超时（${opts.timeoutMs}ms）`,
    });
  }, opts.timeoutMs);

  proc.stdout.on("data", (chunk) => {
    const data = chunk.toString();
    console.error(`[${cliType} stdout] ${data.slice(0, 100)}`);
    buffer += data;
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const event = tryParseJson(line);
      if (!event) continue;

      // 提取 session_id / thread_id（Gemini 用 session_id，Codex 用 thread_id）
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
      if (event.item && event.item.type === "agent_message" && typeof event.item.text === "string") {
        agentMessages += event.item.text;
      }

      // 提取错误信息
      if (event.type === "error" && typeof event.message === "string") {
        // 忽略 Gemini 的 "Reconnecting..." 消息
        if (!/^Reconnecting\.\.\.\s+\d+\/\d+/.test(event.message)) {
          errorMessage = event.message;
        }
      }
      if (typeof event.type === "string" && event.type.includes("fail")) {
        errorMessage = JSON.stringify(event);
      }

      // 检测完成信号（Gemini: turn.completed, Codex: result）
      if (event.type === "turn.completed" || event.type === "result") {
        if (!resolved) {
          resolved = true;
          clearTimeout(timeout);
          sessions.set(requestId, {
            success: !!sessionId && !errorMessage,
            sessionId,
            agentMessages,
            error: errorMessage || undefined,
          });
        }
        setTimeout(() => { try { proc.kill(); } catch {} }, 300);
      }
    }
  });

  proc.stderr.on("data", (chunk) => {
    stderrOutput += chunk.toString();
    console.error(`[${cliType} stderr] ${chunk.toString().slice(0, 100)}`);
  });

  proc.on("exit", () => {
    console.error(`[spawnCLI] Process exited, requestId=${requestId}, cli=${cliType}, resolved=${resolved}, sessionId=${sessionId}, stderr=${stderrOutput.slice(0, 100)}`);
    if (resolved) return;
    resolved = true;
    clearTimeout(timeout);
    sessions.set(requestId, {
      success: !!sessionId && !errorMessage,
      sessionId,
      agentMessages,
      error: errorMessage || (stderrOutput ? `Stderr: ${stderrOutput.slice(0, 200)}` : undefined),
    });
  });

  proc.on("error", (err) => {
    if (resolved) return;
    resolved = true;
    clearTimeout(timeout);
    sessions.set(requestId, {
      success: false,
      sessionId: "",
      agentMessages: "",
      error: err.message,
    });
  });

  return requestId;
}

const server = http.createServer((req, res) => {
  if (req.method === "POST" && req.url === "/execute") {
    let body = "";
    req.on("data", chunk => { body += chunk.toString(); });
    req.on("end", () => {
      try {
        const opts = JSON.parse(body);
        // 验证必需字段
        if (!opts.cmd || !Array.isArray(opts.args)) {
          throw new Error("Missing required fields: cmd, args");
        }
        const requestId = spawnCLI(opts);
        res.writeHead(202, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ requestId }));
      } catch (e) {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: e.message }));
      }
    });
  } else if (req.method === "GET" && req.url.startsWith("/result/")) {
    const requestId = req.url.slice(8);
    if (sessions.has(requestId)) {
      const result = sessions.get(requestId);
      sessions.delete(requestId);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(result));
    } else {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Request not found or still running" }));
    }
  } else if (req.method === "GET" && req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok", sessions: sessions.size }));
  } else {
    res.writeHead(404);
    res.end();
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`CLI HTTP service listening on http://127.0.0.1:${PORT}`);
  console.log(`Supported CLIs: gemini, codex, opencode`);
});
