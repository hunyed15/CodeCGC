#!/usr/bin/env node
import { spawn } from "child_process";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const cliPath = join(__dirname, "..", "dist", "cli", "cgc.js");

const proc = spawn("node", [cliPath, "doctor", ...process.argv.slice(2)], {
  stdio: "inherit",
  env: process.env,
});

proc.on("exit", (code) => process.exit(code || 0));
