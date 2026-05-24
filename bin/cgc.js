#!/usr/bin/env node
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { spawn } from "child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const cliPath = join(__dirname, "..", "dist", "cli", "cgc.js");

const proc = spawn("node", [cliPath, ...process.argv.slice(2)], {
  stdio: "inherit",
  env: process.env,
});

proc.on("exit", (code) => process.exit(code || 0));
