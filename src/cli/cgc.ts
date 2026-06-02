#!/usr/bin/env node
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { Command } from "commander";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const program = new Command();

program.name("cgc").description("CodeCGC 多模型工作流编排 CLI").version("1.0.16");

// ==================== 辅助函数 ====================

async function callMcpTool(toolName: string, args: Record<string, unknown>): Promise<void> {
  // 编译后 CLI 位于 dist/cli/cgc.js，目标位于 dist/mcp/codecgcmcp/server.js
  const serverPath = join(__dirname, "..", "mcp", "codecgcmcp", "server.js");
  const transport = new StdioClientTransport({
    command: "node",
    args: [serverPath],
  });

  const client = new Client({ name: "cgc-cli", version: "0.1.0" }, { capabilities: {} });

  // 从 args 中提取超时（如果有），CLI → codecgcmcp 层的超时应大于内层超时
  const innerTimeout = (args.timeout_seconds as number) || 900;
  const clientTimeout = (innerTimeout + 30) * 1000; // 比内层多 30s 余量

  try {
    await client.connect(transport);

    const result = await client.callTool({ name: toolName, arguments: args }, undefined, { timeout: clientTimeout });
    const resultContent = result as { content?: Array<{ type: string; text?: string }> };
    if (!resultContent.content || resultContent.content.length === 0) {
      console.error("MCP 返回空内容");
      process.exit(1);
    }

    const content = resultContent.content[0];
    if (content.type !== "text" || !content.text) {
      console.error("MCP 返回非文本内容");
      process.exit(1);
    }

    let data: unknown;
    try {
      data = parseJsonPayload(content.text);
    } catch {
      console.error("MCP 返回非 JSON 内容:", content.text.slice(0, 200));
      process.exit(1);
    }
    console.log(JSON.stringify(data, null, 2));

    if (typeof data === "object" && data !== null && "success" in data && !(data as { success?: boolean }).success) {
      process.exit(1);
    }
  } catch (error) {
    console.error("调用失败:", error instanceof Error ? error.message : String(error));
    process.exit(1);
  } finally {
    await client.close();
  }
}

/**
 * 安全解析超时参数
 */
function parseTimeout(value: string): number {
  const n = parseInt(value, 10);
  if (isNaN(n) || n <= 0) return 600;
  return n;
}

function parseJsonPayload(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    const trimmed = text.trim();
    for (let end = trimmed.length; end > 0; end--) {
      const candidate = trimmed.slice(0, end).trimEnd();
      if (!candidate.endsWith("}") && !candidate.endsWith("]")) continue;
      try {
        return JSON.parse(candidate);
      } catch {}
    }
    throw new Error("No JSON payload found");
  }
}

function detectWorkflowKind(description: string): "feature" | "issue" {
  return /修复|错误|报错|故障|bug|fix|error|issue/i.test(description) ? "issue" : "feature";
}

// ==================== 命令定义 ====================

program
  .command("entry <description...>")
  .description("创建或恢复一个 workflow 入口")
  .option("-k, --kind <kind>", "workflow 类型 (feature/issue)")
  .option("-s, --slug <slug>", "自定义 slug")
  .option("--artifact-class <class>", "产物类型 (product/fixture)", "product")
  .option("--cd <dir>", "项目根目录", process.cwd())
  .action(async (descriptionParts, options) => {
    const description = descriptionParts.join(" ").trim();
    await callMcpTool("codecgc.entry", {
      description,
      kind: options.kind ?? detectWorkflowKind(description),
      slug: options.slug,
      artifact_class: options.artifactClass,
      cd: options.cd,
    });
  });

program
  .command("explain <kind> <slug>")
  .description("解释当前 workflow 状态和下一步建议")
  .option("--cd <dir>", "项目根目录", process.cwd())
  .action(async (kind, slug, options) => {
    await callMcpTool("codecgc.explain", {
      kind,
      slug,
      cd: options.cd,
    });
  });

program
  .command("route <paths...>")
  .description("根据路径判断归属，推荐 executor")
  .option("--cd <dir>", "项目根目录", process.cwd())
  .option("--executor-hint <hint>", "显式 executor 提示 (frontend/backend/docs/both)")
  .action(async (paths, options) => {
    await callMcpTool("codecgc.route", {
      paths,
      cd: options.cd,
      executor_hint: options.executorHint,
    });
  });

program
  .command("history [kind] [slug] [step-id]")
  .description("查询历史 workflow 和 audit 记录")
  .option("-k, --kind <kind>", "workflow 类型 (feature/issue)")
  .option("-s, --slug <slug>", "workflow slug")
  .option("--step-id <id>", "step ID")
  .option("--limit <n>", "限制返回数量", parseInt)
  .option("--cd <dir>", "项目根目录", process.cwd())
  .action(async (kind, slug, stepId, options) => {
    await callMcpTool("codecgc.history", {
      kind: options.kind ?? kind,
      slug: options.slug ?? slug,
      step_id: options.stepId ?? stepId,
      limit: options.limit,
      cd: options.cd,
    });
  });

program
  .command("init")
  .description("初始化项目（创建 .codecgc/ 目录和配置文件）")
  .option("--cd <dir>", "项目根目录", process.cwd())
  .option("--force", "强制覆盖已存在的文件")
  .option("--refresh-skills", "刷新项目级 skills，不覆盖 workflow 配置")
  .option("--mode <mode>", "工作模式 (lightweight/full)")
  .option("--backend <provider>", "后端执行器 (claude/codex)")
  .option("--frontend <provider>", "前端执行器 (claude/gemini/opencode)")
  .action(async (options) => {
    await callMcpTool("codecgc.init", {
      cd: options.cd,
      force: options.force,
      refresh_skills: options.refreshSkills,
      mode: options.mode,
      backend: options.backend,
      frontend: options.frontend,
    });
  });

program
  .command("status [filter]")
  .description("显示所有 workflow 状态摘要")
  .option("--cd <dir>", "项目根目录", process.cwd())
  .option("--filter <filter>", "过滤条件 (active/closed/all)")
  .action(async (filter, options) => {
    await callMcpTool("codecgc.status", {
      cd: options.cd,
      filter: options.filter ?? filter ?? "active",
    });
  });

program
  .command("doctor")
  .description("环境健康检查")
  .option("--cd <dir>", "项目根目录", process.cwd())
  .action(async (options) => {
    await callMcpTool("codecgc.doctor", {
      cd: options.cd,
    });
  });

program
  .command("continue <kind> <slug> <step-id> <session-id>")
  .description("在同一 session_id 内继续执行")
  .option("--cd <dir>", "项目根目录", process.cwd())
  .option("--timeout <seconds>", "超时时间（秒）", "900")
  .action(async (kind, slug, stepId, sessionId, options) => {
    await callMcpTool("codecgc.continue", {
      kind,
      slug,
      step_id: stepId,
      session_id: sessionId,
      cd: options.cd,
      timeout_seconds: parseTimeout(options.timeout),
    });
  });

program
  .command("audit [check]")
  .description("工作流完整性审计")
  .option("--cd <dir>", "项目根目录", process.cwd())
  .option("--check <type>", "检查类型 (completeness/stale/all)")
  .option("--stale-days <n>", "陈旧阈值（天）", "7")
  .action(async (check, options) => {
    await callMcpTool("codecgc.audit", {
      cd: options.cd,
      check: options.check ?? check ?? "all",
      stale_days: parseInt(options.staleDays, 10),
    });
  });

program
  .command("manual <kind> <slug> <step-id>")
  .description("手动标记 docs/orchestration 步骤完成")
  .requiredOption("--summary <text>", "执行摘要")
  .option("--changed-files <files>", "修改的文件（逗号分隔）")
  .option("--notes <text>", "备注")
  .option("--cd <dir>", "项目根目录", process.cwd())
  .action(async (kind, slug, stepId, options) => {
    const changedFiles = options.changedFiles ? options.changedFiles.split(",").map((f: string) => f.trim()) : [];
    await callMcpTool("codecgc.manual", {
      kind,
      slug,
      step_id: stepId,
      summary: options.summary,
      changed_files: changedFiles,
      notes: options.notes,
      cd: options.cd,
    });
  });

program
  .command("plan <kind> <slug>")
  .description("向 workflow 添加 steps")
  .requiredOption("--steps <json>", "步骤 JSON 数组")
  .option("--cd <dir>", "项目根目录", process.cwd())
  .action(async (kind, slug, options) => {
    let steps;
    try {
      steps = JSON.parse(options.steps);
    } catch (e) {
      console.error("--steps 必须是有效的 JSON 数组");
      process.exit(1);
    }

    await callMcpTool("codecgc.plan", {
      kind,
      slug,
      steps,
      cd: options.cd,
    });
  });

program
  .command("build <kind-or-slug> [slug]")
  .description("执行 feature workflow 的下一个 pending 步骤")
  .option("--step-id <id>", "指定步骤 ID")
  .option("--cd <dir>", "项目根目录", process.cwd())
  .option("--timeout <seconds>", "超时时间（秒）", "900")
  .action(async (kindOrSlug, slug, options) => {
    const kind = kindOrSlug === "feature" || kindOrSlug === "issue" ? kindOrSlug : "feature";
    const workflowSlug = slug ?? kindOrSlug;
    await callMcpTool("codecgc.build", {
      kind,
      slug: workflowSlug,
      step_id: options.stepId,
      cd: options.cd,
      timeout_seconds: parseTimeout(options.timeout),
    });
  });

program
  .command("fix <kind-or-slug> [slug]")
  .description("执行 issue workflow 的下一个 pending 步骤")
  .option("--step-id <id>", "指定步骤 ID")
  .option("--cd <dir>", "项目根目录", process.cwd())
  .option("--timeout <seconds>", "超时时间（秒）", "900")
  .action(async (kindOrSlug, slug, options) => {
    const kind = kindOrSlug === "feature" || kindOrSlug === "issue" ? kindOrSlug : "issue";
    const workflowSlug = slug ?? kindOrSlug;
    await callMcpTool("codecgc.fix", {
      kind,
      slug: workflowSlug,
      step_id: options.stepId,
      cd: options.cd,
      timeout_seconds: parseTimeout(options.timeout),
    });
  });

program
  .command("test <kind> <slug> <step-id>")
  .description("执行测试步骤")
  .option("--cd <dir>", "项目根目录", process.cwd())
  .option("--timeout <seconds>", "超时时间（秒）", "900")
  .action(async (kind, slug, stepId, options) => {
    await callMcpTool("codecgc.test", {
      kind,
      slug,
      step_id: stepId,
      cd: options.cd,
      timeout_seconds: parseTimeout(options.timeout),
    });
  });

program
  .command("review <kind> <slug> <step-id> [decision]")
  .description(
    "审核步骤执行结果。不传 decision = prepare 模式（返回审核请求包）；传 decision = 写入决定（approved/changes-requested/rejected/reopen）",
  )
  .option("--notes <text>", "审核备注")
  .option("--issues <json>", "问题清单（JSON 数组）")
  .option("--suggestions <json>", "改进建议（JSON 数组）")
  .option("--acceptance-check <json>", "验收检查（JSON 数组）")
  .option("--max-file-size-kb <n>", "prepare 模式下单文件最大读取（KB）", "200")
  .option("--cd <dir>", "项目根目录", process.cwd())
  .action(async (kind, slug, stepId, decision, options) => {
    const args: any = {
      kind,
      slug,
      step_id: stepId,
      cd: options.cd,
    };

    if (decision) {
      args.decision = decision;
      args.notes = options.notes;
      if (options.issues) args.issues = JSON.parse(options.issues);
      if (options.suggestions) args.suggestions = JSON.parse(options.suggestions);
      if (options.acceptanceCheck) args.acceptance_check = JSON.parse(options.acceptanceCheck);
    } else {
      // prepare 模式
      args.max_file_size_kb = parseInt(options.maxFileSizeKb, 10);
    }

    await callMcpTool("codecgc.review", args);
  });

program
  .argument("[description...]", "自然语言需求，等价于 cgc entry <description>")
  .action(async (descriptionParts: string[]) => {
    const description = descriptionParts.join(" ").trim();
    if (!description) {
      program.help();
      return;
    }

    await callMcpTool("codecgc.entry", {
      description,
      kind: detectWorkflowKind(description),
      cd: process.cwd(),
    });
  });

program.parse();
