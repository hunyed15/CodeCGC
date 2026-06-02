#!/usr/bin/env node
import { spawn } from "child_process";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export function runCgc(args) {
  const cliPath = join(__dirname, "..", "dist", "cli", "cgc.js");
  const proc = spawn("node", [cliPath, ...args], {
    stdio: "inherit",
    env: process.env,
  });

  proc.on("exit", (code) => process.exit(code || 0));
}
