#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const path = require("node:path");

function shouldRunUserInstall() {
  const globalFlag = String(process.env.npm_config_global || "").toLowerCase();
  const localPrefix = String(process.env.npm_config_local_prefix || "");
  const prefix = String(process.env.npm_config_prefix || "");

  if (globalFlag === "true") {
    return true;
  }
  if (prefix && localPrefix && prefix !== localPrefix) {
    return true;
  }
  return false;
}

function findPython() {
  const override = String(process.env.CODECGC_PYTHON_COMMAND || "").trim();
  const candidates = override
    ? [override]
    : (process.platform === "win32" ? ["python", "py"] : ["python3", "python"]);

  for (const command of candidates) {
    const probe = spawnSync(command, ["--version"], {
      encoding: "utf8",
      shell: false,
    });
    if (probe.status === 0) {
      return command;
    }
  }
  return "";
}

function main() {
  if (!shouldRunUserInstall()) {
    return 0;
  }

  const python = findPython();
  if (!python) {
    console.warn("[codecgc] Skipped automatic Claude integration: Python was not found.");
    console.warn("[codecgc] Run `cgc-install --mode user` after installing Python.");
    return 0;
  }

  const repoRoot = path.resolve(__dirname, "..");
  const installScript = path.join(repoRoot, "scripts", "install_codecgc.py");
  const result = spawnSync(
    python,
    [installScript, "--mode", "user", "--format", "summary"],
    {
      cwd: repoRoot,
      stdio: "inherit",
      shell: false,
      env: {
        ...process.env,
        PYTHONIOENCODING: process.env.PYTHONIOENCODING || "utf-8",
        PYTHONUTF8: process.env.PYTHONUTF8 || "1",
      },
    },
  );

  if (result.status !== 0) {
    console.warn("[codecgc] Automatic Claude integration did not complete during npm install.");
    console.warn("[codecgc] You can retry manually with `cgc-install --mode user`.");
  }

  return 0;
}

process.exit(main());
