import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";
import { spawn } from "child_process";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { entry, type EntryArgs } from "./tools/entry.js";
import { plan, type PlanArgs } from "./tools/plan.js";
import { build, type BuildArgs } from "./tools/build.js";
import { fix, type FixArgs } from "./tools/fix.js";
import { test, type TestArgs } from "./tools/test.js";
import { review, type ReviewArgs } from "./tools/review.js";
import { explain, type ExplainArgs } from "./tools/explain.js";
import { route, type RouteArgs } from "./tools/route.js";
import { history, type HistoryArgs } from "./tools/history.js";
import { init, type InitArgs } from "./tools/init.js";
import { status, type StatusArgs } from "./tools/status.js";
import { doctor, type DoctorArgs } from "./tools/doctor.js";
import { continueExecution, type ContinueArgs } from "./tools/continue.js";
import { audit, type AuditArgs } from "./tools/audit.js";
import { manual, type ManualArgs } from "./tools/manual.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const TOOLS: Tool[] = [
  {
    name: "codecgc.entry",
    description: "创建或恢复一个 workflow 入口（feature/issue）",
    inputSchema: {
      type: "object",
      properties: {
        description: { type: "string", description: "需求描述" },
        kind: { type: "string", enum: ["feature", "issue"], description: "workflow 类型" },
        slug: { type: "string", description: "自定义 slug（可选，默认自动生成）" },
        artifact_class: { type: "string", enum: ["product", "fixture"], default: "product" },
        cd: { type: "string", description: "项目根目录" },
      },
      required: ["description"],
    },
  },
  {
    name: "codecgc.explain",
    description: "解释当前 workflow 状态和下一步建议",
    inputSchema: {
      type: "object",
      properties: {
        kind: { type: "string", enum: ["feature", "issue"] },
        slug: { type: "string" },
        cd: { type: "string", description: "项目根目录" },
      },
      required: ["kind", "slug"],
    },
  },
  {
    name: "codecgc.route",
    description: "根据路径判断归属（backend/frontend/docs/orchestration），推荐 executor。支持混合路由策略：1) executor_hint 显式声明（优先级最高）；2) 目录约定；3) routing.yaml 规则",
    inputSchema: {
      type: "object",
      properties: {
        paths: { type: "array", items: { type: "string" }, description: "待分类的路径列表" },
        cd: { type: "string", description: "项目根目录" },
        executor_hint: {
          type: "string",
          enum: ["frontend", "backend", "docs", "both"],
          description: "可选。显式声明 executor（优先级最高）。frontend=前端任务，backend=后端任务，docs=文档任务，both=前后端都要改（自动拆分）",
        },
      },
      required: ["paths"],
    },
  },
  {
    name: "codecgc.history",
    description: "查询历史 workflow 和 audit 记录",
    inputSchema: {
      type: "object",
      properties: {
        kind: { type: "string", enum: ["feature", "issue"], description: "可选，过滤 workflow 类型" },
        slug: { type: "string", description: "可选，指定 workflow slug" },
        step_id: { type: "string", description: "可选，指定 step ID 查询其 audits" },
        limit: { type: "number", description: "可选，限制返回的 audit 数量" },
        cd: { type: "string", description: "项目根目录" },
      },
    },
  },
  {
    name: "codecgc.init",
    description: "初始化项目（创建 .codecgc/ 目录、.codecgc/config/routing.yaml、.mcp.json、.claude/CLAUDE.md）",
    inputSchema: {
      type: "object",
      properties: {
        cd: { type: "string", description: "项目根目录" },
        force: { type: "boolean", description: "强制覆盖已存在的文件" },
      },
    },
  },
  {
    name: "codecgc.status",
    description: "显示所有 workflow 状态摘要",
    inputSchema: {
      type: "object",
      properties: {
        cd: { type: "string", description: "项目根目录" },
        filter: { type: "string", enum: ["active", "closed", "all"], description: "过滤条件" },
      },
    },
  },
  {
    name: "codecgc.doctor",
    description: "环境健康检查（Node.js、Codex/Gemini CLI、项目结构、配置文件）",
    inputSchema: {
      type: "object",
      properties: {
        cd: { type: "string", description: "项目根目录" },
      },
    },
  },
  {
    name: "codecgc.continue",
    description: "在同一 session_id 内继续执行（跨 turn 对话续接）",
    inputSchema: {
      type: "object",
      properties: {
        kind: { type: "string", enum: ["feature", "issue"] },
        slug: { type: "string" },
        step_id: { type: "string" },
        session_id: { type: "string", description: "上次执行返回的 session_id" },
        cd: { type: "string", description: "项目根目录" },
        timeout_seconds: { type: "number", default: 600 },
      },
      required: ["kind", "slug", "step_id", "session_id"],
    },
  },
  {
    name: "codecgc.audit",
    description: "工作流完整性审计（检查闭环、半成品、长期阻塞项）",
    inputSchema: {
      type: "object",
      properties: {
        cd: { type: "string", description: "项目根目录" },
        check: {
          type: "string",
          enum: ["completeness", "stale", "all"],
          description: "检查类型：completeness=完整性、stale=陈旧性、all=全部",
        },
        stale_days: { type: "number", description: "陈旧阈值（天），默认 7", default: 7 },
      },
    },
  },
  {
    name: "codecgc.manual",
    description: "手动标记 docs/orchestration 步骤完成（由 Claude 直接处理的步骤）",
    inputSchema: {
      type: "object",
      properties: {
        kind: { type: "string", enum: ["feature", "issue"] },
        slug: { type: "string" },
        step_id: { type: "string" },
        summary: { type: "string", description: "执行摘要（Claude 手动填写）" },
        changed_files: { type: "array", items: { type: "string" }, description: "修改的文件列表" },
        notes: { type: "string", description: "备注" },
        cd: { type: "string", description: "项目根目录" },
      },
      required: ["kind", "slug", "step_id", "summary"],
    },
  },
  {
    name: "codecgc.plan",
    description: "向 workflow 添加 steps（规划阶段）",
    inputSchema: {
      type: "object",
      properties: {
        kind: { type: "string", enum: ["feature", "issue"] },
        slug: { type: "string" },
        steps: {
          type: "array",
          items: {
            type: "object",
            properties: {
              id: { type: "string" },
              title: { type: "string" },
              executor: { type: "string", enum: ["backend", "frontend", "docs", "orchestration"] },
              task_id: { type: "string" },
              summary: { type: "string" },
              paths: { type: "array", items: { type: "string" } },
              constraints: { type: "array", items: { type: "string" } },
              acceptance: { type: "array", items: { type: "string" } },
              cd: { type: "string" },
            },
            required: ["id", "title", "executor", "task_id", "summary", "paths"],
          },
        },
        cd: { type: "string" },
      },
      required: ["kind", "slug", "steps"],
    },
  },
  {
    name: "codecgc.build",
    description: "执行 feature workflow 的下一个 pending 步骤",
    inputSchema: {
      type: "object",
      properties: {
        kind: { type: "string", enum: ["feature", "issue"] },
        slug: { type: "string" },
        step_id: { type: "string", description: "可选，指定步骤 ID" },
        cd: { type: "string" },
        timeout_seconds: { type: "number", default: 600 },
      },
      required: ["kind", "slug"],
    },
  },
  {
    name: "codecgc.fix",
    description: "执行 issue workflow 的下一个 pending 步骤",
    inputSchema: {
      type: "object",
      properties: {
        kind: { type: "string", enum: ["feature", "issue"] },
        slug: { type: "string" },
        step_id: { type: "string", description: "可选，指定步骤 ID" },
        cd: { type: "string" },
        timeout_seconds: { type: "number", default: 600 },
      },
      required: ["kind", "slug"],
    },
  },
  {
    name: "codecgc.test",
    description: "执行测试步骤（必须指定 step_id）",
    inputSchema: {
      type: "object",
      properties: {
        kind: { type: "string", enum: ["feature", "issue"] },
        slug: { type: "string" },
        step_id: { type: "string" },
        cd: { type: "string" },
        timeout_seconds: { type: "number", default: 600 },
      },
      required: ["kind", "slug", "step_id"],
    },
  },
  {
    name: "codecgc.review",
    description: "审核步骤执行结果。两种模式：(1) 不传 decision = prepare 模式，返回审核请求包（代码、验收、历史）供 Claude 分析；(2) 传 decision = 写入审核决定（approved/changes-requested/rejected/reopen），可附带 issues 和 suggestions",
    inputSchema: {
      type: "object",
      properties: {
        kind: { type: "string", enum: ["feature", "issue"] },
        slug: { type: "string" },
        step_id: { type: "string" },
        decision: {
          type: "string",
          enum: ["approved", "changes-requested", "rejected", "reopen"],
          description: "可选。不传则进入 prepare 模式（返回审核请求包）；传则写入审核决定"
        },
        notes: { type: "string", description: "审核备注（总体说明）" },
        issues: {
          type: "array",
          description: "审核发现的具体问题（decision 模式）",
          items: {
            type: "object",
            properties: {
              severity: { type: "string", enum: ["critical", "major", "minor", "info"] },
              category: { type: "string", enum: ["correctness", "security", "performance", "style", "completeness", "other"] },
              file: { type: "string" },
              line: { type: "number" },
              description: { type: "string" },
              suggestion: { type: "string" }
            },
            required: ["severity", "category", "description"]
          }
        },
        suggestions: {
          type: "array",
          items: { type: "string" },
          description: "改进建议清单（decision 模式）"
        },
        acceptance_check: {
          type: "array",
          description: "逐条验收标准检查（decision 模式）",
          items: {
            type: "object",
            properties: {
              criterion: { type: "string" },
              passed: { type: "boolean" },
              note: { type: "string" }
            },
            required: ["criterion", "passed"]
          }
        },
        max_file_size_kb: { type: "number", description: "prepare 模式下单文件最大读取（KB），默认 200" },
        cd: { type: "string" },
      },
      required: ["kind", "slug", "step_id"],
    },
  },
];

const server = new Server(
  { name: "codecgcmcp", version: "1.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  if (!args) throw new Error("Missing arguments");

  // 输入大小防护（防 DoS）
  validateInputSize(args);

  try {
    let result: unknown;

    switch (name) {
      case "codecgc.entry":
        result = await entry(args as unknown as EntryArgs);
        break;
      case "codecgc.explain":
        result = await explain(args as unknown as ExplainArgs);
        break;
      case "codecgc.route":
        result = await route(args as unknown as RouteArgs);
        break;
      case "codecgc.history":
        result = await history(args as unknown as HistoryArgs);
        break;
      case "codecgc.init":
        result = await init(args as unknown as InitArgs);
        break;
      case "codecgc.status":
        result = await status(args as unknown as StatusArgs);
        break;
      case "codecgc.doctor":
        result = await doctor(args as unknown as DoctorArgs);
        break;
      case "codecgc.continue":
        result = await continueExecution(args as unknown as ContinueArgs);
        break;
      case "codecgc.audit":
        result = await audit(args as unknown as AuditArgs);
        break;
      case "codecgc.manual":
        result = await manual(args as unknown as ManualArgs);
        break;
      case "codecgc.plan":
        result = await plan(args as unknown as PlanArgs);
        break;
      case "codecgc.build":
        result = await build(args as unknown as BuildArgs);
        break;
      case "codecgc.fix":
        result = await fix(args as unknown as FixArgs);
        break;
      case "codecgc.test":
        result = await test(args as unknown as TestArgs);
        break;
      case "codecgc.review":
        result = await review(args as unknown as ReviewArgs);
        break;
      default:
        throw new Error(`Unknown tool: ${name}`);
    }

    return {
      content: [{ type: "text", text: JSON.stringify(result, null, 2) }],
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      content: [{ type: "text", text: JSON.stringify({ success: false, error: message }) }],
      isError: true,
    };
  }
});

/**
 * 输入大小防护：防止超长输入导致 DoS
 */
function validateInputSize(args: Record<string, unknown>): void {
  const MAX_STRING = 5000;
  const MAX_ARRAY = 100;

  for (const [key, value] of Object.entries(args)) {
    if (typeof value === "string" && value.length > MAX_STRING) {
      throw new Error(`参数 ${key} 超过最大长度 ${MAX_STRING} 字符`);
    }
    if (Array.isArray(value)) {
      if (value.length > MAX_ARRAY) {
        throw new Error(`参数 ${key} 超过最大数组长度 ${MAX_ARRAY}`);
      }
      for (const item of value) {
        if (typeof item === "string" && item.length > MAX_STRING) {
          throw new Error(`参数 ${key} 中的元素超过最大长度 ${MAX_STRING} 字符`);
        }
      }
    }
  }
}

/**
 * Start CLI HTTP service (background process)
 */
async function startCliHttpService(): Promise<void> {
  const HTTP_PORT = 37428;
  const servicePath = join(__dirname, "runtime", "cli-http-service.cjs");

  try {
    // Check if service is already running
    const response = await fetch(`http://127.0.0.1:${HTTP_PORT}/health`, {
      signal: AbortSignal.timeout(1000),
    });
    if (response.ok) {
      console.error(`[codecgcmcp] CLI HTTP service already running on port ${HTTP_PORT}`);
      return;
    }
  } catch {
    // Service not running, start it
  }

  try {
    console.error(`[codecgcmcp] Starting CLI HTTP service on port ${HTTP_PORT}...`);
    const proc = spawn("node", [servicePath, String(HTTP_PORT)], {
      detached: true,
      stdio: "ignore",
      windowsHide: true,
    });
    proc.unref(); // Let child process run independently
    console.error(`[codecgcmcp] CLI HTTP service started (PID: ${proc.pid})`);
  } catch (error) {
    console.error(`[codecgcmcp] Failed to start CLI HTTP service:`, error);
  }
}

async function main() {
  // Start CLI HTTP service
  await startCliHttpService();

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("codecgcmcp MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
