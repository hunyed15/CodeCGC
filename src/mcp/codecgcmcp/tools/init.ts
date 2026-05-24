import { existsSync, readdirSync } from "fs";
import { writeFile, readFile } from "fs/promises";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { resolveProjectRoot, codecgcRoot, routingFile, ensureDir } from "../runtime/paths.js";
import { writeYaml } from "../../../shared/yaml.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// 全局已有的 skill，不需要释放到项目级
const GLOBAL_ONLY_SKILLS = ["cgc-init", "cgc"];

export interface InitArgs {
  cd?: string;
  force?: boolean;
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

    // 3. 写入 .claude/CLAUDE.md（AI 提示词）
    const claudeDir = join(projectRoot, ".claude");
    const claudeMdPath = join(claudeDir, "CLAUDE.md");
    if (!existsSync(claudeMdPath) || force) {
      await ensureDir(claudeDir);
      await writeFile(claudeMdPath, getDefaultClaudeMd(), "utf-8");
      created.push(".claude/CLAUDE.md");
    } else {
      skipped.push(".claude/CLAUDE.md (已存在)");
    }

    // 4. 写入 .mcp.json
    const mcpPath = join(projectRoot, ".mcp.json");
    if (!existsSync(mcpPath) || force) {
      await writeFile(mcpPath, JSON.stringify(getDefaultMcpConfig(), null, 2), "utf-8");
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

    const totalCreated = created.length;
    const skillSummary = skillsResult.missing_source
      ? "项目级 skills 未释放：未找到包内 skills 源目录。"
      : `项目级 skills：新增 ${skillsResult.released.length} 个，已存在 ${skillsResult.skipped.length} 个，目录 ${skillsResult.target_dir}`;
    return {
      success: true,
      project_root: projectRoot,
      created_files: created,
      skipped_files: skipped,
      warnings,
      project_skills: skillsResult,
      recommendation:
        totalCreated === 0
          ? `项目已初始化，无需重复操作。${skillSummary}`
          : `已创建 ${totalCreated} 项。${skillSummary} 下一步：调用 codecgc.entry 创建第一个 workflow。`,
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
      codecgcmcp: {
        command: "cgc-mcp",
        args: [],
      },
    },
  };
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

function getDefaultClaudeMd(): string {
  return `# CodeCGC 工作流提示词

## 核心分工

- Claude：需求澄清、规划、设计、文档、审核、验收。
- Codex：后端代码执行。
- Gemini：前端代码执行。
- NodeCGC：路由、审计、状态闭环。

## 首选入口

MCP 可用时优先调用 codecgcmcp 工具：

- \`codecgc.entry\` — 创建 workflow
- \`codecgc.plan\` — 生成/更新规划
- \`codecgc.build\` — 执行 feature 步骤
- \`codecgc.fix\` — 执行 issue 修复
- \`codecgc.test\` — 执行测试
- \`codecgc.review\` — 审核执行结果

## 写入边界

\`.codecgc/config/routing.yaml\` 是路径归属策略来源。

Claude 可直接处理：\`.codecgc/**\`、\`.claude/**\`、\`.mcp.json\`、\`docs/**\`、\`README.md\`、\`CHANGELOG.md\`

Claude 不应直接修改产品源码——后端交 Codex，前端交 Gemini。

## 标准流程

\`\`\`
需求 → 规划 → 路由 → Codex/Gemini 执行 → 审计 → Claude 审核 → 关闭
\`\`\`
`;
}
