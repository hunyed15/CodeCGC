// 共享类型定义

export type SandboxMode = "read-only" | "workspace-write" | "danger-full-access";

export interface ExecutorResult {
  success: boolean;
  sessionId: string;
  agentMessages: string;
  allMessages?: unknown[];
  error?: string;
}

export interface CodexOptions {
  prompt: string;
  cd: string;
  sandbox?: SandboxMode;
  sessionId?: string;
  skipGitRepoCheck?: boolean;
  returnAllMessages?: boolean;
  images?: string[];
  model?: string;
  yolo?: boolean;
  profile?: string;
  timeoutMs?: number;
}

export interface GeminiOptions {
  prompt: string;
  cd: string;
  sandbox?: boolean;
  sessionId?: string;
  returnAllMessages?: boolean;
  model?: string;
  timeoutMs?: number;
}

export interface BackendTaskOptions {
  taskId: string;
  taskSummary: string;
  targetPaths: string[];
  constraints?: string[];
  acceptanceCriteria?: string[];
  cd?: string;
  sessionId?: string;
  sandbox?: SandboxMode;
  returnAllMessages?: boolean;
  model?: string;
  profile?: string;
}

export interface FrontendTaskOptions {
  taskId: string;
  taskSummary: string;
  targetPaths: string[];
  constraints?: string[];
  acceptanceCriteria?: string[];
  cd?: string;
  sessionId?: string;
  sandbox?: boolean;
  returnAllMessages?: boolean;
  model?: string;
  timeoutMs?: number;
}

export interface TaskResult {
  success: boolean;
  taskId: string;
  sessionId: string;
  summary: string;
  agentMessages: string;
  changedFiles: string[];
  policyChecks: string[];
  risks: string[];
  error?: string;
}

// ========== Workflow 产物类型 ==========

export type WorkflowKind = "feature" | "issue";
export type ArtifactClass = "product" | "fixture";
export type StepStatus = "pending" | "done" | "skipped";
export type StepExecutor = "backend" | "frontend" | "docs" | "orchestration";

export interface WorkflowStep {
  id: string;
  title: string;
  status: StepStatus;
  executor: StepExecutor;
  task_id: string;
  summary: string;
  paths: string[];
  constraints?: string[];
  acceptance?: string[];
  cd?: string;
  session_id?: string;
}

export interface Workflow {
  version: number;
  kind: WorkflowKind;
  slug: string;
  created: string;
  artifact_class: ArtifactClass;
  steps: WorkflowStep[];
}

// ========== Routing 策略类型 ==========

export type PathOwnership = "backend" | "frontend" | "shared" | "docs" | "unknown";

export interface RoutingRule {
  patterns: string[];
  ownership: PathOwnership;
}

export interface ModelRouting {
  version: number;
  rules: RoutingRule[];
}
