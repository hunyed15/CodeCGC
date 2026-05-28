/**
 * Generic CLI HTTP service
 *
 * Purpose: Bypass MCP StdioServerTransport environment limitations
 * Architecture: Independent process + HTTP API, codecgcmcp calls via fetch
 * Support: Gemini, Codex, OpenCode, etc.
 *
 * Usage: node cli-http-service.cjs [port]
 * Default port: 37428
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
const sessions = new Map(); // requestId -> { success, sessionId, agentMessages, error, timestamp }
const progressMap = new Map(); // requestId -> { phase, lastEventTime, lastEventType, isAlive, proc }

// Limits to prevent memory exhaustion
const MAX_BODY_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_BUFFER_SIZE = 1 * 1024 * 1024; // 1MB
const MAX_STDERR_SIZE = 500 * 1024; // 500KB
const MAX_MESSAGE_SIZE = 5 * 1024 * 1024; // 5MB
const SESSION_TTL_MS = 10 * 60 * 1000; // 10 minutes

// Cleanup expired sessions every 5 minutes
setInterval(
  () => {
    const now = Date.now();
    let cleaned = 0;
    for (const [requestId, session] of sessions.entries()) {
      if (now - session.timestamp > SESSION_TTL_MS) {
        sessions.delete(requestId);
        cleaned++;
      }
    }
    for (const [requestId, progress] of progressMap.entries()) {
      if (now - progress.lastEventTime > SESSION_TTL_MS) {
        progressMap.delete(requestId);
        cleaned++;
      }
    }
    if (cleaned > 0) {
      console.error(`[cleanup] Removed ${cleaned} expired sessions/progress`);
    }
  },
  5 * 60 * 1000,
);

function tryParseJson(line) {
  try {
    const parsed = JSON.parse(line.trim());
    if (typeof parsed === "object" && parsed !== null) return parsed;
    return null;
  } catch {
    return null;
  }
}

/**
 * Detect execution phase from event type
 */
function detectPhase(event) {
  if (!event || !event.type) return "unknown";
  const type = event.type;

  // Planning phase
  if (type.includes("plan") || type.includes("thinking") || type.includes("analyze")) {
    return "planning";
  }

  // Reading phase
  if (type === "tool_use" && event.tool) {
    const tool = event.tool.toLowerCase();
    if (tool.includes("read") || tool.includes("grep") || tool.includes("glob") || tool.includes("search")) {
      return "reading";
    }
    if (tool.includes("write") || tool.includes("edit") || tool.includes("create")) {
      return "writing";
    }
  }

  // Writing phase
  if (type.includes("write") || type.includes("edit") || type.includes("create")) {
    return "writing";
  }

  // Completion
  if (type === "turn.completed" || type === "result") {
    return "completed";
  }

  // Default: active
  return "active";
}

/**
 * Generic CLI spawn function
 * @param {object} opts
 * @param {string} opts.cli - CLI type (gemini/codex/opencode)
 * @param {string} opts.cmd - Command path
 * @param {string[]} opts.args - Command arguments
 * @param {string} opts.cd - Working directory
 * @param {object} opts.env - Environment variables
 * @param {number} opts.timeoutMs - Timeout in milliseconds
 */
function spawnCLI(opts) {
  const requestId = randomBytes(8).toString("hex");
  const cliType = opts.cli || "gemini";
  console.error(
    `[spawnCLI] Starting requestId=${requestId}, cli=${cliType}, cmd=${opts.cmd}, args=${JSON.stringify(opts.args).slice(0, 100)}`,
  );

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

  // Initialize progress tracking
  progressMap.set(requestId, {
    phase: "starting",
    lastEventTime: Date.now(),
    lastEventType: "spawn",
    isAlive: true,
    proc: proc,
  });

  const timeout = setTimeout(() => {
    if (resolved) return;
    resolved = true;
    try {
      if (proc.pid) {
        if (process.platform === "win32") {
          require("child_process").execFileSync("taskkill", ["/PID", String(proc.pid), "/T", "/F"], {
            stdio: "ignore",
          });
        } else {
          process.kill(-proc.pid, "SIGTERM");
        }
      }
    } catch {}
    sessions.set(requestId, {
      success: false,
      sessionId: "",
      agentMessages: "",
      error: `Execution timeout (${opts.timeoutMs}ms)`,
      timestamp: Date.now(),
    });
  }, opts.timeoutMs);

  proc.stdout.on("data", (chunk) => {
    const data = chunk.toString();
    console.error(`[${cliType} stdout] ${data.slice(0, 100)}`);

    // Prevent buffer overflow
    if (buffer.length + data.length > MAX_BUFFER_SIZE) {
      console.error(`[${cliType}] Buffer overflow, truncating`);
      buffer = buffer.slice(-MAX_BUFFER_SIZE / 2); // Keep last half
    }

    buffer += data;
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const event = tryParseJson(line);
      if (!event) continue;

      // Update progress tracking
      const phase = detectPhase(event);
      const progress = progressMap.get(requestId);
      if (progress) {
        progress.phase = phase;
        progress.lastEventTime = Date.now();
        progress.lastEventType = event.type || "unknown";
        progress.isAlive = true;
      }

      // Extract session_id / thread_id (Gemini uses session_id, Codex uses thread_id)
      if (event.session_id && typeof event.session_id === "string") {
        sessionId = event.session_id;
      }
      if (event.thread_id && typeof event.thread_id === "string") {
        sessionId = event.thread_id;
      }

      // Extract assistant messages (support multiple formats)
      if (event.type === "message" && event.role === "assistant" && typeof event.content === "string") {
        if (agentMessages.length + event.content.length <= MAX_MESSAGE_SIZE) {
          agentMessages += event.content;
        }
      }
      if (event.item && event.item.type === "agent_message" && typeof event.item.text === "string") {
        if (agentMessages.length + event.item.text.length <= MAX_MESSAGE_SIZE) {
          agentMessages += event.item.text;
        }
      }

      // Extract error messages
      if (event.type === "error" && typeof event.message === "string") {
        // Ignore Gemini's "Reconnecting..." messages
        if (!/^Reconnecting\.\.\.\s+\d+\/\d+/.test(event.message)) {
          errorMessage = event.message;
        }
      }
      if (typeof event.type === "string" && event.type.includes("fail")) {
        errorMessage = JSON.stringify(event);
      }

      // Detect completion signal (Gemini: turn.completed, Codex: result)
      if (event.type === "turn.completed" || event.type === "result") {
        if (!resolved) {
          resolved = true;
          clearTimeout(timeout);
          sessions.set(requestId, {
            success: !!sessionId && !errorMessage,
            sessionId,
            agentMessages,
            error: errorMessage || undefined,
            timestamp: Date.now(),
          });
        }
        setTimeout(() => {
          try {
            proc.kill();
          } catch {}
        }, 300);
      }
    }
  });

  proc.stderr.on("data", (chunk) => {
    const data = chunk.toString();

    // Prevent stderr overflow
    if (stderrOutput.length + data.length > MAX_STDERR_SIZE) {
      stderrOutput = stderrOutput.slice(-MAX_STDERR_SIZE / 2); // Keep last half
    }

    stderrOutput += data;
    console.error(`[${cliType} stderr] ${data.slice(0, 100)}`);
  });

  proc.on("exit", () => {
    console.error(
      `[spawnCLI] Process exited, requestId=${requestId}, cli=${cliType}, resolved=${resolved}, sessionId=${sessionId}, stderr=${stderrOutput.slice(0, 100)}`,
    );

    // Mark progress as dead
    const progress = progressMap.get(requestId);
    if (progress) {
      progress.isAlive = false;
      progress.phase = "exited";
    }

    if (resolved) return;
    resolved = true;
    clearTimeout(timeout);
    sessions.set(requestId, {
      success: !!sessionId && !errorMessage,
      sessionId,
      agentMessages,
      error: errorMessage || (stderrOutput ? `Stderr: ${stderrOutput.slice(0, 200)}` : undefined),
      timestamp: Date.now(),
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
      timestamp: Date.now(),
    });
  });

  return requestId;
}

const server = http.createServer((req, res) => {
  if (req.method === "POST" && req.url === "/execute") {
    let body = "";
    let bodySize = 0;

    req.on("data", (chunk) => {
      bodySize += chunk.length;
      if (bodySize > MAX_BODY_SIZE) {
        req.destroy();
        res.writeHead(413, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Request body too large" }));
        return;
      }
      body += chunk.toString();
    });

    req.on("end", () => {
      try {
        const opts = JSON.parse(body);
        // Validate required fields
        if (!opts.cmd || !Array.isArray(opts.args)) {
          throw new Error("Missing required fields: cmd, args");
        }
        // Validate timeoutMs
        if (opts.timeoutMs && (typeof opts.timeoutMs !== "number" || opts.timeoutMs <= 0 || opts.timeoutMs > 3600000)) {
          throw new Error("Invalid timeoutMs: must be between 1 and 3600000");
        }
        const requestId = spawnCLI(opts);
        res.writeHead(202, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ requestId }));
      } catch (e) {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: e.message }));
      }
    });

    req.on("error", (err) => {
      console.error(`[HTTP] Request error:`, err);
      if (!res.headersSent) {
        res.writeHead(500, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Request processing failed" }));
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
  } else if (req.method === "GET" && req.url.startsWith("/progress/")) {
    const requestId = req.url.slice(10);
    if (progressMap.has(requestId)) {
      const progress = progressMap.get(requestId);
      const now = Date.now();
      const elapsed = now - progress.lastEventTime;

      // Detect stuck state (no events for 2+ minutes)
      const isStuck = elapsed > 120_000 && progress.isAlive;

      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(
        JSON.stringify({
          requestId,
          phase: isStuck ? "stuck" : progress.phase,
          lastEventTime: progress.lastEventTime,
          lastEventType: progress.lastEventType,
          isAlive: progress.isAlive,
          elapsedSinceLastEvent: elapsed,
          isStuck,
        }),
      );
    } else {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Progress not found" }));
    }
  } else if (req.method === "POST" && req.url.startsWith("/cancel/")) {
    const requestId = req.url.slice(8);
    if (progressMap.has(requestId)) {
      const progress = progressMap.get(requestId);
      if (progress.proc && progress.isAlive) {
        try {
          if (process.platform === "win32") {
            require("child_process").execFileSync("taskkill", ["/PID", String(progress.proc.pid), "/T", "/F"], {
              stdio: "ignore",
            });
          } else {
            process.kill(-progress.proc.pid, "SIGTERM");
          }
          progress.isAlive = false;
          progress.phase = "cancelled";
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ cancelled: true, requestId }));
        } catch (e) {
          res.writeHead(500, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ error: e.message }));
        }
      } else {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Process not alive or already finished" }));
      }
    } else {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Request not found" }));
    }
  } else {
    res.writeHead(404);
    res.end();
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`CLI HTTP service listening on http://127.0.0.1:${PORT}`);
  console.log(`Supported CLIs: gemini, codex, opencode`);
});
