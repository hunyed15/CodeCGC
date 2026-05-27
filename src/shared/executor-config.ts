import { existsSync } from "fs";
import { readFile } from "fs/promises";
import { join } from "path";
import yaml from "js-yaml";
import type { ExecutorConfig } from "./types.js";

/**
 * 加载 executor 配置
 * 优先级：.codecgc/config/executors.yaml > 默认配置
 */
export async function loadExecutorConfig(projectRoot: string): Promise<ExecutorConfig> {
  const configPath = join(projectRoot, ".codecgc", "config", "executors.yaml");

  // 如果配置文件不存在，返回默认配置（轻量模式）
  if (!existsSync(configPath)) {
    return getDefaultExecutorConfig();
  }

  try {
    const content = await readFile(configPath, "utf-8");
    const config = yaml.load(content) as ExecutorConfig;

    // 验证配置结构
    validateExecutorConfig(config);

    return config;
  } catch (error) {
    console.error(`[executor-config] Failed to load ${configPath}:`, error);
    return getDefaultExecutorConfig();
  }
}

/**
 * 获取默认 executor 配置（轻量模式）
 */
export function getDefaultExecutorConfig(): ExecutorConfig {
  return {
    version: 1,
    mode: "lightweight",
    executors: {
      backend: {
        provider: "claude",
      },
      frontend: {
        provider: "claude",
      },
    },
    fixed: {
      docs: "claude",
      orchestration: "claude",
    },
  };
}

/**
 * 获取轻量模式配置模板
 */
export function getLightweightModeConfig(): ExecutorConfig {
  return {
    version: 1,
    mode: "lightweight",
    executors: {
      backend: {
        provider: "claude",
      },
      frontend: {
        provider: "claude",
      },
    },
    fixed: {
      docs: "claude",
      orchestration: "claude",
    },
  };
}

/**
 * 获取完全模式配置模板
 */
export function getFullModeConfig(backend: "codex" | "claude", frontend: "opencode" | "gemini" | "claude"): ExecutorConfig {
  return {
    version: 1,
    mode: "full",
    executors: {
      backend: {
        provider: backend,
      },
      frontend: {
        provider: frontend,
      },
    },
    fixed: {
      docs: "claude",
      orchestration: "claude",
    },
  };
}

/**
 * 验证 executor 配置结构
 */
function validateExecutorConfig(config: unknown): asserts config is ExecutorConfig {
  if (!config || typeof config !== "object") {
    throw new Error("Invalid executor config: must be an object");
  }

  const c = config as Record<string, unknown>;

  if (typeof c.version !== "number" || c.version !== 1) {
    throw new Error("Invalid executor config: version must be 1");
  }

  if (c.mode !== "lightweight" && c.mode !== "full") {
    throw new Error("Invalid executor config: mode must be 'lightweight' or 'full'");
  }

  if (!c.executors || typeof c.executors !== "object") {
    throw new Error("Invalid executor config: executors must be an object");
  }

  const executors = c.executors as Record<string, unknown>;

  if (!executors.backend || typeof executors.backend !== "object") {
    throw new Error("Invalid executor config: executors.backend must be an object");
  }

  if (!executors.frontend || typeof executors.frontend !== "object") {
    throw new Error("Invalid executor config: executors.frontend must be an object");
  }

  const backend = executors.backend as Record<string, unknown>;
  const frontend = executors.frontend as Record<string, unknown>;

  const validProviders = ["claude", "codex", "gemini", "opencode"];

  if (!validProviders.includes(backend.provider as string)) {
    throw new Error(`Invalid executor config: backend.provider must be one of ${validProviders.join(", ")}`);
  }

  if (!validProviders.includes(frontend.provider as string)) {
    throw new Error(`Invalid executor config: frontend.provider must be one of ${validProviders.join(", ")}`);
  }
}
