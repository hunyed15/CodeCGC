#!/usr/bin/env node
import { spawn } from "child_process";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const serverMap = {
  codexmcp: join(__dirname, "..", "dist", "mcp", "codexmcp", "server.js"),
  geminimcp: join(__dirname, "..", "dist", "mcp", "geminimcp", "server.js"),
  opencodemcp: join(__dirname, "..", "dist", "mcp", "opencodemcp", "server.js"),
  codecgcmcp: join(__dirname, "..", "dist", "mcp", "codecgcmcp", "server.js"),
};

const serverName = process.argv[2] || "codexmcp";
const serverPath = serverMap[serverName];

if (!serverPath) {
  console.error(`Unknown MCP server: ${serverName}`);
  console.error(`Available: ${Object.keys(serverMap).join(", ")}`);
  process.exit(1);
}

const proc = spawn("node", [serverPath], {
  stdio: "inherit",
  env: process.env,
});

proc.on("exit", (code) => process.exit(code || 0));
