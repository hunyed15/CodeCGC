import { describe, it, expect } from "vitest";
import { loadExecutorConfig, getDefaultExecutorConfig, getLightweightModeConfig, getFullModeConfig } from "../src/shared/executor-config.js";
import { join } from "path";
import { tmpdir } from "os";
import { mkdtemp, writeFile, mkdir } from "fs/promises";

describe("loadExecutorConfig", () => {
  it("returns default config when no file exists", async () => {
    const config = await loadExecutorConfig("/nonexistent/path");
    expect(config.mode).toBe("lightweight");
    expect(config.executors.backend.provider).toBe("claude");
    expect(config.executors.frontend.provider).toBe("claude");
  });

  it("loads valid config from file", async () => {
    const tmpDir = await mkdtemp(join(tmpdir(), "executor-test-"));
    const configDir = join(tmpDir, ".codecgc", "config");
    await mkdir(configDir, { recursive: true });

    const configContent = `version: 1
mode: full
executors:
  backend:
    provider: codex
  frontend:
    provider: opencode
`;
    await writeFile(join(configDir, "executors.yaml"), configContent, "utf-8");

    const config = await loadExecutorConfig(tmpDir);
    expect(config.mode).toBe("full");
    expect(config.executors.backend.provider).toBe("codex");
    expect(config.executors.frontend.provider).toBe("opencode");
  });

  it("falls back to default on invalid config", async () => {
    const tmpDir = await mkdtemp(join(tmpdir(), "executor-test-"));
    const configDir = join(tmpDir, ".codecgc", "config");
    await mkdir(configDir, { recursive: true });

    await writeFile(join(configDir, "executors.yaml"), "invalid: yaml: content:", "utf-8");

    const config = await loadExecutorConfig(tmpDir);
    expect(config.mode).toBe("lightweight");
  });
});

describe("getDefaultExecutorConfig", () => {
  it("returns version 1 lightweight config", () => {
    const config = getDefaultExecutorConfig();
    expect(config.version).toBe(1);
    expect(config.mode).toBe("lightweight");
    expect(config.fixed?.docs).toBe("claude");
    expect(config.fixed?.orchestration).toBe("claude");
  });
});

describe("getLightweightModeConfig", () => {
  it("returns lightweight config with claude providers", () => {
    const config = getLightweightModeConfig();
    expect(config.mode).toBe("lightweight");
    expect(config.executors.backend.provider).toBe("claude");
    expect(config.executors.frontend.provider).toBe("claude");
  });
});

describe("getFullModeConfig", () => {
  it("creates full mode with specified providers", () => {
    const config = getFullModeConfig("codex", "opencode");
    expect(config.mode).toBe("full");
    expect(config.executors.backend.provider).toBe("codex");
    expect(config.executors.frontend.provider).toBe("opencode");
  });

  it("creates full mode with claude frontend", () => {
    const config = getFullModeConfig("codex", "claude");
    expect(config.mode).toBe("full");
    expect(config.executors.backend.provider).toBe("codex");
    expect(config.executors.frontend.provider).toBe("claude");
  });
});
