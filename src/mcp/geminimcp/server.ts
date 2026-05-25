import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";
import { runGeminiSession } from "./executor.js";
import { executeFrontendTask } from "./tools.js";
import type { GeminiOptions, FrontendTaskOptions } from "../../shared/types.js";

const TOOLS: Tool[] = [
  {
    name: "gemini",
    description: "通用 Gemini CLI 会话执行器",
    inputSchema: {
      type: "object",
      properties: {
        PROMPT: { type: "string", description: "发送给 Gemini 的指令" },
        cd: { type: "string", description: "工作区根目录" },
        sandbox: { type: "boolean", default: false, description: "是否开启 Gemini 沙箱" },
        SESSION_ID: { type: "string", default: "", description: "续接会话" },
        return_all_messages: { type: "boolean", default: false },
        model: { type: "string", default: "" },
        timeout_seconds: { type: "number", default: 600 },
      },
      required: ["PROMPT", "cd"],
    },
  },
  {
    name: "implement_frontend_task",
    description: "带路径策略守卫的前端专用任务执行器，拒绝后端路径",
    inputSchema: {
      type: "object",
      properties: {
        task_id: { type: "string", description: "稳定任务标识符" },
        task_summary: { type: "string", description: "前端实现摘要" },
        target_paths: {
          type: "array",
          items: { type: "string" },
          description: "Gemini 允许触碰的前端路径",
        },
        constraints: { type: "array", items: { type: "string" }, default: [] },
        acceptance_criteria: { type: "array", items: { type: "string" }, default: [] },
        cd: { type: "string", default: "." },
        SESSION_ID: { type: "string", default: "" },
        sandbox: { type: "boolean", default: false },
        return_all_messages: { type: "boolean", default: false },
        model: { type: "string", default: "" },
        timeout_seconds: { type: "number", default: 600 },
      },
      required: ["task_id", "task_summary", "target_paths"],
    },
  },
];

const server = new Server(
  { name: "geminimcp", version: "0.1.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  if (!args) throw new Error("Missing arguments");

  try {
    if (name === "gemini") {
      // Input validation
      const timeoutSeconds = (args.timeout_seconds as number) || 600;
      if (typeof timeoutSeconds !== "number" || timeoutSeconds <= 0 || timeoutSeconds > 3600) {
        throw new Error("timeout_seconds must be between 1 and 3600");
      }

      const opts: GeminiOptions = {
        prompt: args.PROMPT as string,
        cd: args.cd as string,
        sandbox: args.sandbox as boolean,
        sessionId: args.SESSION_ID as string | undefined,
        returnAllMessages: args.return_all_messages as boolean,
        model: args.model as string | undefined,
        timeoutMs: timeoutSeconds * 1000,
      };
      const result = await runGeminiSession(opts);
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              success: result.success,
              SESSION_ID: result.sessionId,
              agent_messages: result.agentMessages,
              all_messages: result.allMessages,
              error: result.error,
            }),
          },
        ],
      };
    }

    if (name === "implement_frontend_task") {
      // Input validation
      const timeoutSeconds = (args.timeout_seconds as number) || 600;
      if (typeof timeoutSeconds !== "number" || timeoutSeconds <= 0 || timeoutSeconds > 3600) {
        throw new Error("timeout_seconds must be between 1 and 3600");
      }

      const opts: FrontendTaskOptions = {
        taskId: args.task_id as string,
        taskSummary: args.task_summary as string,
        targetPaths: args.target_paths as string[],
        constraints: args.constraints as string[] | undefined,
        acceptanceCriteria: args.acceptance_criteria as string[] | undefined,
        cd: args.cd as string | undefined,
        sessionId: args.SESSION_ID as string | undefined,
        sandbox: args.sandbox as boolean,
        returnAllMessages: args.return_all_messages as boolean,
        model: args.model as string | undefined,
        timeoutMs: timeoutSeconds * 1000,
      };
      const result = await executeFrontendTask(opts);
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify({
              success: result.success,
              task_id: result.taskId,
              SESSION_ID: result.sessionId,
              summary: result.summary,
              agent_messages: result.agentMessages,
              changed_files: result.changedFiles,
              policy_checks: result.policyChecks,
              risks: result.risks,
              error: result.error,
            }),
          },
        ],
      };
    }

    throw new Error(`Unknown tool: ${name}`);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      content: [{ type: "text", text: JSON.stringify({ success: false, error: message }) }],
      isError: true,
    };
  }
});

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("geminimcp MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
