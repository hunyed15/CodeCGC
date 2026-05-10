#!/usr/bin/env node

function isGlobalInstall() {
  const globalFlag = String(process.env.npm_config_global || "").toLowerCase();
  const localPrefix = String(process.env.npm_config_local_prefix || "");
  const prefix = String(process.env.npm_config_prefix || "");

  if (globalFlag === "true") {
    return true;
  }
  return Boolean(prefix && localPrefix && prefix !== localPrefix);
}

function main() {
  if (!isGlobalInstall()) {
    return 0;
  }

  console.warn("[codecgc] Global CLI installed.");
  console.warn("[codecgc] CodeCGC no longer writes Claude user-level files during npm install.");
  console.warn("[codecgc] Run `cgc-install` from each target project to create project-local .mcp.json, .claude/, and model-routing.yaml.");
  return 0;
}

process.exit(main());
