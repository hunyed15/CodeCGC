import { existsSync, readdirSync } from "fs";
import { writeFile, readFile } from "fs/promises";
import { join, dirname } from "path";
import { homedir } from "os";
import { fileURLToPath } from "url";
import { resolveProjectRoot, codecgcRoot, routingFile, ensureDir } from "../runtime/paths.js";
import { writeYaml } from "../../../shared/yaml.js";
import { getLightweightModeConfig, getFullModeConfig } from "../../../shared/executor-config.js";
import type { ExecutorConfig } from "../../../shared/types.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// 全局已有的 skill，不需要释放到项目级
const GLOBAL_ONLY_SKILLS = ["cgc-init", "cgc"];

export interface InitArgs {
  cd?: string;
  force?: boolean;
  mode?: "lightweight" | "full";
  backend?: "claude" | "codex";
  frontend?: "claude" | "gemini" | "opencode";
}

export interface InitResult {
  success: boolean;
  project_root: string;
  created_files: string[];
  skipped_files: string[];
  warnings: string[];
  project_skills: {
    source_dir: string;
    target_dir: string;
    released: string[];
    skipped: string[];
    missing_source: boolean;
  };
  recommendation: string;
  error?: string;
}

export async function init(args: InitArgs): Promise<InitResult> {
  try {
    const projectRoot = resolveProjectRoot(args.cd);
    const force = args.force ?? false;

    // 确定模式和执行器配置
    const mode = args.mode ?? "lightweight";
    const backend = args.backend ?? "claude";
    const frontend = args.frontend ?? "claude";

    const created: string[] = [];
    const skipped: string[] = [];
    const warnings: string[] = [];

    // 1. 创建 .codecgc/ 目录结构
    const root = codecgcRoot(projectRoot);
    const subdirs = ["config", "features", "issues", "execution"];
    for (const sub of subdirs) {
      const dir = join(root, sub);
      if (!existsSync(dir)) {
        await ensureDir(dir);
        created.push(`.codecgc/${sub}/`);
      }
    }

    // 2. 写入 .codecgc/config/routing.yaml
    const routingPath = routingFile(projectRoot);
    if (!existsSync(routingPath) || force) {
      await ensureDir(join(root, "config"));
      await writeYaml(routingPath, getDefaultRouting());
      created.push(".codecgc/config/routing.yaml");
    } else {
      skipped.push(".codecgc/config/routing.yaml (已存在)");
    }

    // 2.5. 写入 .codecgc/config/executors.yaml
    const executorsPath = join(root, "config", "executors.yaml");
    if (!existsSync(executorsPath) || force) {
      await ensureDir(join(root, "config"));
      const executorConfig: ExecutorConfig = mode === "lightweight"
        ? getLightweightModeConfig()
        : getFullModeConfig(backend as "codex" | "claude", frontend as "opencode" | "gemini" | "claude");
      await writeYaml(executorsPath, executorConfig);
      created.push(".codecgc/config/executors.yaml");
    } else {
      skipped.push(".codecgc/config/executors.yaml (已存在)");
    }

    // 3. 写入 .claude/CLAUDE.md（AI 提示词）
    const claudeDir = join(projectRoot, ".claude");
    const claudeMdPath = join(claudeDir, "CLAUDE.md");
    if (!existsSync(claudeMdPath) || force) {
      await ensureDir(claudeDir);
      await writeFile(claudeMdPath, getDefaultClaudeMd(mode, backend, frontend), "utf-8");
      created.push(".claude/CLAUDE.md");
    } else {
      skipped.push(".claude/CLAUDE.md (已存在)");
    }

    // 4. 写入 .mcp.json（根据模式和执行器选择）
    const mcpPath = join(projectRoot, ".mcp.json");
    if (!existsSync(mcpPath) || force) {
      const mcpConfig = generateMcpConfig(mode, backend, frontend);
      await writeFile(mcpPath, JSON.stringify(mcpConfig, null, 2), "utf-8");
      created.push(".mcp.json");
    } else {
      skipped.push(".mcp.json (已存在)");
    }

    // 5. 更新 .gitignore
    const gitignorePath = join(projectRoot, ".gitignore");
    const gitignoreRule = ".codecgc/execution/";
    if (existsSync(gitignorePath)) {
      const content = await readFile(gitignorePath, "utf-8");
      if (!content.includes(gitignoreRule)) {
        await writeFile(
          gitignorePath,
          content + `\n# CodeCGC\n${gitignoreRule}\n`,
          "utf-8"
        );
        created.push(".gitignore (追加 CodeCGC 规则)");
      } else {
        skipped.push(".gitignore (已包含规则)");
      }
    }

    // 6. 释放项目级 skills 到 .claude/skills/<name>/SKILL.md
    const skillsResult = await releaseProjectSkills(projectRoot, force);
    if (skillsResult.released.length > 0) {
      created.push(`.claude/skills/ (${skillsResult.released.length} skills)`);
    }
    if (skillsResult.skipped.length > 0) {
      skipped.push(`.claude/skills/ (${skillsResult.skipped.length} skills 已存在)`);
    }
    if (skillsResult.missing_source) {
      warnings.push(`未找到包内 skills 源目录: ${skillsResult.source_dir}`);
    } else if (skillsResult.released.length === 0 && skillsResult.skipped.length === 0) {
      warnings.push(`未释放任何项目级 skill，请检查包内 skills 目录: ${skillsResult.source_dir}`);
    }

    // 7. 释放 Claude Code 项目级 memory（工作流强制执行规则）
    try {
      const memoryDir = getProjectMemoryDir(projectRoot);
      const memoryFile = join(memoryDir, "codecgc-workflow-enforcement.md");
      const memoryIndex = join(memoryDir, "MEMORY.md");

      if (!existsSync(memoryFile) || force) {
        await ensureDir(memoryDir);
        await writeFile(memoryFile, getMemoryTemplate(), "utf-8");
        await updateMemoryIndex(memoryIndex);
        created.push("Claude Code memory (workflow enforcement)");
      } else {
        skipped.push("Claude Code memory (已存在)");
      }
    } catch (e) {
      warnings.push(`Claude Code memory 释放失败: ${e instanceof Error ? e.message : String(e)}`);
    }

    const totalCreated = created.length;
    const skillSummary = skillsResult.missing_source
      ? "项目级 skills 未释放：未找到包内 skills 源目录。"
      : `项目级 skills：新增 ${skillsResult.released.length} 个，已存在 ${skillsResult.skipped.length} 个，目录 ${skillsResult.target_dir}`;

    // 生成推荐信息
    let recommendation = "";
    if (totalCreated === 0) {
      recommendation = `项目已初始化，无需重复操作。${skillSummary}`;
    } else {
      const modeDesc = mode === "lightweight" ? "轻量模式（Claude 处理所有任务）" : "完全模式";
      const installHints: string[] = [];

      if (mode === "full") {
        if (backend === "codex") installHints.push("npm install -g @openai/codex");
        if (frontend === "gemini") installHints.push("npm install -g @google/gemini-cli");
        if (frontend === "opencode") installHints.push("npm install -g @opencode-ai/opencode");
      }

      const installMsg = installHints.length > 0
        ? `\n\n需要安装执行器：\n${installHints.map(h => `  ${h}`).join("\n")}`
        : "";

      recommendation = `已创建 ${totalCreated} 项。${skillSummary}\n\n工作模式：${modeDesc}${installMsg}\n\n下一步：调用 codecgc.entry 创建第一个 workflow。`;
    }

    return {
      success: true,
      project_root: projectRoot,
      created_files: created,
      skipped_files: skipped,
      warnings,
      project_skills: skillsResult,
      recommendation,
    };
  } catch (error) {
    return {
      success: false,
      project_root: args.cd ?? process.cwd(),
      created_files: [],
      skipped_files: [],
      warnings: [],
      project_skills: {
        source_dir: "",
        target_dir: "",
        released: [],
        skipped: [],
        missing_source: true,
      },
      recommendation: "初始化失败",
      error: error instanceof Error ? error.message : String(error),
    };
  }
}

function getDefaultRouting() {
  return {
    version: 1,
    rules: [
      {
        patterns: ["**/*.py", "**/api/**", "**/server/**", "**/backend/**", "**/*.go", "**/*.rs"],
        ownership: "backend",
      },
      {
        patterns: [
          "**/*.tsx", "**/*.jsx", "**/*.vue", "**/*.svelte",
          "**/*.css", "**/*.scss",
          "**/components/**", "**/pages/**", "**/app/**", "**/frontend/**",
        ],
        ownership: "frontend",
      },
      {
        patterns: ["**/*.md", "**/docs/**", "README*", "CHANGELOG*"],
        ownership: "docs",
      },
      {
        patterns: ["**/shared/**", "**/common/**", "**/utils/**"],
        ownership: "shared",
      },
    ],
  };
}

function getDefaultMcpConfig() {
  return {
    mcpServers: {
      codecgc: {
        command: "cgc-mcp",
        args: ["codecgcmcp"],
      },
      codex: {
        command: "cgc-mcp",
        args: ["codexmcp"],
      },
      gemini: {
        command: "cgc-mcp",
        args: ["geminimcp"],
      },
      opencode: {
        command: "cgc-mcp",
        args: ["opencodemcp"],
      },
    },
  };
}

/**
 * 根据模式和执行器选择生成 .mcp.json 配置
 */
function generateMcpConfig(
  mode: "lightweight" | "full",
  backend: string,
  frontend: string
): { mcpServers: Record<string, { command: string; args: string[] }> } {
  const mcpServers: Record<string, { command: string; args: string[] }> = {
    codecgc: {
      command: "cgc-mcp",
      args: ["codecgcmcp"],
    },
  };

  // 轻量模式：只需要 codecgc
  if (mode === "lightweight") {
    return { mcpServers };
  }

  // 完全模式：根据选择添加 MCP 服务器
  if (backend === "codex") {
    mcpServers.codex = {
      command: "cgc-mcp",
      args: ["codexmcp"],
    };
  }

  if (frontend === "gemini") {
    mcpServers.gemini = {
      command: "cgc-mcp",
      args: ["geminimcp"],
    };
  }

  if (frontend === "opencode") {
    mcpServers.opencode = {
      command: "cgc-mcp",
      args: ["opencodemcp"],
    };
  }

  return { mcpServers };
}

/**
 * 从包的 skills/ 目录读取非全局 skill，写入项目 .claude/skills/<name>/SKILL.md
 */
async function releaseProjectSkills(projectRoot: string, force: boolean): Promise<InitResult["project_skills"]> {
  // 从编译后位置回溯到包根: dist/mcp/codecgcmcp/tools/ → 包根/skills/
  const skillsSourceDir = join(__dirname, "..", "..", "..", "..", "skills");
  const skillsTargetDir = join(projectRoot, ".claude", "skills");
  const result: InitResult["project_skills"] = {
    source_dir: skillsSourceDir,
    target_dir: skillsTargetDir,
    released: [],
    skipped: [],
    missing_source: false,
  };

  if (!existsSync(skillsSourceDir)) {
    result.missing_source = true;
    return result;
  }

  const files = readdirSync(skillsSourceDir).filter(f => f.endsWith(".md"));

  for (const file of files) {
    const name = file.replace(/\.md$/, "");
    if (GLOBAL_ONLY_SKILLS.includes(name)) continue;

    const destDir = join(projectRoot, ".claude", "skills", name);
    const destFile = join(destDir, "SKILL.md");

    if (existsSync(destFile) && !force) {
      result.skipped.push(name);
      continue;
    }

    await ensureDir(destDir);
    const content = await readFile(join(skillsSourceDir, file), "utf-8");
    await writeFile(destFile, content, "utf-8");
    result.released.push(name);
  }

  return result;
}

function getDefaultClaudeMd(
  mode: "lightweight" | "full" = "lightweight",
  backend: string = "claude",
  frontend: string = "claude"
): string {
  const isLightweight = mode === "lightweight";

  // 后端/前端执行器描述
  const backendDesc = backend === "codex" ? "Codex（OpenAI）" : "Claude";
  const frontendDesc = frontend === "opencode" ? "OpenCode" : frontend === "gemini" ? "Gemini（Google）" : "Claude";

  // 核心分工部分
  const coreRoles = isLightweight
    ? `- Claude：所有代码任务（需求澄清、规划、设计、编码、审核、验收）。`
    : `- Claude：需求澄清、规划、设计、文档、审核、验收。
- ${backendDesc}：后端代码执行（需通过 codecgc.build 调用）。
- ${frontendDesc}：前端代码执行（需通过 codecgc.build 调用）。
- NodeCGC：路由、审计、状态闭环。`;

  // 禁止行为部分
  const prohibitions = isLightweight
    ? `1. ❌ 对 P0/bugfix 类需求跳过 "创建 workflow → plan → build/fix" 流程`
    : `1. ❌ 直接用 Edit/Write 工具修改 \`src/\`、\`lib/\`、\`app/\` 等产品源码
2. ❌ 在没有调用 codecgc.build/fix 的情况下提交产品代码
3. ❌ ${backendDesc}/${frontendDesc} 超时后自行编写替代代码（应诊断超时原因或重试）
4. ❌ 对 P0/bugfix 类需求跳过 "创建 workflow → plan → build/fix" 流程`;

  // 超时处理部分
  const timeoutSection = isLightweight ? `` : `
## 超时处理规范

当 ${backendDesc} 或 ${frontendDesc} 执行超时时：
1. 查看超时日志，分析根因
2. 调整 timeout_seconds 后重试
3. **不要**自行编写代码替代——这会破坏工作流闭环`;

  // 混合路由部分
  const routingSection = isLightweight ? `` : `
## 混合路由策略

\`codecgc.route\` 支持三层路由策略（优先级从高到低）：

### 1. executor_hint（显式声明，优先级最高）

根据用户需求的**语义**判断，直接传递 \`executor_hint\` 参数：

- **前端任务**（UI、组件、样式、前端交互）→ \`executor_hint: "frontend"\`
- **后端任务**（API、数据库、服务端逻辑）→ \`executor_hint: "backend"\`
- **文档任务**（README、CHANGELOG、设计文档）→ \`executor_hint: "docs"\`
- **全栈任务**（前后端都要改）→ \`executor_hint: "both"\`（自动拆分）

### 2. 目录约定（次优先级）

- \`**/frontend/**\` → frontend
- \`**/backend/**\` → backend
- \`**/docs/**\` → docs

### 3. routing.yaml 规则（兜底）

使用 \`.codecgc/config/routing.yaml\` 的扩展名和路径模式规则。`;

  return `# CodeCGC 工作流规则

## 工作模式

${isLightweight ? "**轻量模式**：所有代码任务由 Claude 直接处理，无需外部工具。" : `**完全模式**：后端执行器 = ${backendDesc}，前端执行器 = ${frontendDesc}。`}

## 核心分工

${coreRoles}

## 禁止行为（红线）

以下行为会导致工作流断裂、审计缺失、交付质量下降，**绝对不允许**：

${prohibitions}

## 自检触发条件

当以下条件**全部满足**时，你**必须**先调用 codecgc.entry + codecgc.plan：
- 用户要求修改产品代码（非 .codecgc/、.claude/、docs/、README）
- 当前没有活跃的 workflow 覆盖该路径

## 允许直接编辑的路径（白名单）

仅以下路径可由 Claude 直接编辑，无需经过 workflow：

- \`.codecgc/**\` — 工作流配置
- \`.claude/**\` — Claude 配置
- \`.mcp.json\` — MCP 配置
- \`docs/**\` — 文档
- \`README.md\`、\`CHANGELOG.md\` — 项目说明${timeoutSection}

## 首选入口

MCP 可用时优先调用 codecgcmcp 工具：

- \`codecgc.entry\` — 创建 workflow
- \`codecgc.plan\` — 生成/更新规划
- \`codecgc.build\` — 执行 feature 步骤
- \`codecgc.fix\` — 执行 issue 修复
- \`codecgc.test\` — 执行测试
- \`codecgc.review\` — 审核执行结果
- \`codecgc.route\` — 路径归属判断（支持 executor_hint）${routingSection}

## 标准流程

\`\`\`
需求 → 规划 → 路由 → ${isLightweight ? "Claude 执行" : `${backendDesc}/${frontendDesc} 执行`} → 审计 → Claude 审核 → 关闭
\`\`\`
`;
}

/**
 * 计算 Claude Code 项目级 memory 目录路径
 * 格式: ~/.claude/projects/<encoded-project-path>/memory/
 */
function getProjectMemoryDir(projectRoot: string): string {
  const resolved = projectRoot.replace(/:/g, "-").replace(/[/\\]/g, "-");
  return join(homedir(), ".claude", "projects", resolved, "memory");
}

/**
 * 通用 memory 模板（feedback 类型）
 * 随 codecgc.init 释放到项目级 memory，防止 Claude 绕过工作流
 */
function getMemoryTemplate(): string {
  return `---
name: codecgc-workflow-enforcement
description: CodeCGC 项目中必须通过工作流执行产品代码修改，禁止直接 Edit/Write
metadata:
  type: feedback
---

产品代码修改必须通过 CodeCGC 工作流执行，禁止直接用 Edit/Write 工具修改 src/、lib/、app/ 等产品源码。

**Why:** Claude 有绕过工作流直接写代码的倾向，尤其在以下场景：
1. Codex/Gemini 超时后自行编写替代代码（应诊断原因或重试）
2. 连续成功后把"小改动"当例外跳过流程
3. P0/bugfix 被当"紧急修复"直接处理
4. Context 压缩后规则被淡化

**How to apply:**
- 产品代码修改：codecgc.entry → codecgc.plan → codecgc.build/fix
- Codex/Gemini 超时：诊断原因或重试，不要自行替代
- P0/bugfix：即使是"一行改动"也要走 workflow
- 用户说"帮我改 XXX"：默认路由到 /cgc skill
- 允许直接编辑：.codecgc/**、.claude/**、.mcp.json、docs/**、README.md、CHANGELOG.md
`;
}

/**
 * 更新 MEMORY.md 索引，追加 CodeCGC 记忆条目
 * 如果 MEMORY.md 不存在则创建；已包含则跳过
 */
async function updateMemoryIndex(indexPath: string): Promise<void> {
  const entry = "- [CodeCGC 工作流强制执行](codecgc-workflow-enforcement.md) — 产品代码修改必须走 workflow，禁止直接 Edit/Write";

  if (existsSync(indexPath)) {
    const content = await readFile(indexPath, "utf-8");
    if (content.includes("codecgc-workflow-enforcement")) return; // 已包含
    await writeFile(indexPath, content.trimEnd() + "\n" + entry + "\n", "utf-8");
  } else {
    await writeFile(indexPath, entry + "\n", "utf-8");
  }
}
