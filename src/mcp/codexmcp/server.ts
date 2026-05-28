import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema, type Tool } from "@modelcontextprotocol/sdk/types.js";
import type { BackendTaskOptions, CodexOptions } from "../../shared/types.js";
import { runCodexSession } from "./executor.js";
import { executeBackendTask } from "./tools.js";

const TOOLS: Tool[] = [
  {
    name: "codex",
    description: "通用 Codex CLI 会话执行器，支持自然语言驱动的代码生成/调试/自动化",
    inputSchema: {
      type: "object",
      properties: {
        PROMPT: { type: "string", description: "发送给 Codex 的任务指令" },
        cd: { type: "string", description: "工作区根目录" },
        sandbox: {
          type: "string",
          enum: ["read-only", "workspace-write", "danger-full-access"],
          default: "read-only",
          description: "沙箱策略",
        },
        SESSION_ID: { type: "string", default: "", description: "续接已有会话" },
        skip_git_repo_check: { type: "boolean", default: true },
        return_all_messages: { type: "boolean", default: false },
        model: { type: "string", default: "" },
        profile: { type: "string", default: "" },
      },
      required: ["PROMPT", "cd"],
    },
  },
  {
    name: "implement_backend_task",
    description: "带路径策略守卫的后端专用任务执行器，拒绝前端路径（沙箱固定为 workspace-write）",
    inputSchema: {
      type: "object",
      properties: {
        task_id: { type: "string", description: "稳定任务标识符" },
        task_summary: { type: "string", description: "后端实现摘要" },
        target_paths: {
          type: "array",
          items: { type: "string" },
          description: "Codex 允许触碰的后端路径",
        },
        constraints: { type: "array", items: { type: "string" }, default: [] },
        acceptance_criteria: { type: "array", items: { type: "string" }, default: [] },
        cd: { type: "string", default: "." },
        SESSION_ID: { type: "string", default: "" },
        return_all_messages: { type: "boolean", default: false },
        model: { type: "string", default: "" },
        profile: { type: "string", default: "" },
      },
      required: ["task_id", "task_summary", "target_paths"],
    },
  },
];

const server = new Server({ name: "codexmcp", version: "0.1.0" }, { capabilities: { tools: {} } });

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  if (!args) throw new Error("Missing arguments");

  try {
    if (name === "codex") {
      const opts: CodexOptions = {
        prompt: args.PROMPT as string,
        cd: args.cd as string,
        sandbox: (args.sandbox as CodexOptions["sandbox"]) || "workspace-write",
        sessionId: args.SESSION_ID as string | undefined,
        skipGitRepoCheck: args.skip_git_repo_check as boolean,
        returnAllMessages: args.return_all_messages as boolean,
        model: args.model as string | undefined,
        profile: args.profile as string | undefined,
      };
      const result = await runCodexSession(opts);
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

    if (name === "implement_backend_task") {
      const opts: BackendTaskOptions = {
        taskId: args.task_id as string,
        taskSummary: args.task_summary as string,
        targetPaths: args.target_paths as string[],
        constraints: args.constraints as string[] | undefined,
        acceptanceCriteria: args.acceptance_criteria as string[] | undefined,
        cd: args.cd as string | undefined,
        sessionId: args.SESSION_ID as string | undefined,
        sandbox: (args.sandbox as BackendTaskOptions["sandbox"]) || "workspace-write",
        returnAllMessages: args.return_all_messages as boolean,
        model: args.model as string | undefined,
        profile: args.profile as string | undefined,
      };
      const result = await executeBackendTask(opts);
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
  console.error("codexmcp MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});
