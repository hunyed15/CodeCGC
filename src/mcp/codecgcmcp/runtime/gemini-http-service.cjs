/**
 * 独立的 Gemini CLI HTTP 服务
 *
 * 用途：绕过 MCP StdioServerTransport 的环境限制
 * 架构：独立进程 + HTTP API，codecgcmcp 通过 fetch 调用
 *
 * 启动：node gemini-http-service.cjs [port]
 * 默认端口：37428
 */
const http = require("http");
const { spawn } = require("child_process");
const { randomBytes } = require("crypto");

const PORT = parseInt(process.argv[2] || "37428", 10);
const sessions = new Map(); // sessionId -> { proc, buffer, result }

function tryParseJson(line) {
  try {
    const parsed = JSON.parse(line.trim());
    if (typeof parsed === "object" && parsed !== null) return parsed;
    return null;
  } catch { return null; }
}

function spawnGemini(opts) {
  const requestId = randomBytes(8).toString("hex");
  console.error(`[spawnGemini] Starting requestId=${requestId}, cmd=${opts.cmd}, args=${JSON.stringify(opts.args).slice(0, 100)}`);

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
    console.error(`[Gemini stdout] ${data.slice(0, 100)}`);
    buffer += data;
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
        // 立即标记为 resolved 并保存结果
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
    console.error(`[Gemini stderr] ${chunk.toString().slice(0, 100)}`);
  });

  proc.on("exit", () => {
    console.error(`[spawnGemini] Process exited, requestId=${requestId}, resolved=${resolved}, sessionId=${sessionId}, stderr=${stderrOutput.slice(0, 100)}`);
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
        const requestId = spawnGemini(opts);
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
  console.log(`Gemini HTTP service listening on http://127.0.0.1:${PORT}`);
});
