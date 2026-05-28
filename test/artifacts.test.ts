import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtemp, rm, readFile } from "fs/promises";
import { join } from "path";
import { tmpdir } from "os";
import {
  createWorkflow,
  addStep,
  findStep,
  markStepDone,
  nextPendingStep,
  writeWorkflow,
  readWorkflow,
  writeAudit,
  listAudits,
  resolveWorkflowDir,
} from "../src/mcp/codecgcmcp/runtime/artifacts.js";
import type { Workflow, WorkflowStep, WorkflowKind } from "../src/shared/types.js";

let tmpDir: string;

beforeEach(async () => {
  tmpDir = await mkdtemp(join(tmpdir(), "artifacts-test-"));
});

afterEach(async () => {
  await rm(tmpDir, { recursive: true, force: true });
});

function makeStep(id: string, status: "pending" | "done" | "skipped" = "pending"): WorkflowStep {
  return {
    id,
    title: `Step ${id}`,
    status,
    executor: "backend",
    task_id: `task-${id}`,
    summary: `Summary for ${id}`,
    paths: ["src/test.ts"],
  };
}

describe("createWorkflow", () => {
  it("creates feature workflow", () => {
    const wf = createWorkflow({ kind: "feature", slug: "test-feat" });
    expect(wf.version).toBe(1);
    expect(wf.kind).toBe("feature");
    expect(wf.slug).toBe("test-feat");
    expect(wf.steps).toEqual([]);
    expect(wf.artifact_class).toBe("product");
  });

  it("creates issue workflow", () => {
    const wf = createWorkflow({ kind: "issue", slug: "bug-fix" });
    expect(wf.kind).toBe("issue");
  });

  it("uses custom artifact_class", () => {
    const wf = createWorkflow({ kind: "feature", slug: "test", artifactClass: "fixture" });
    expect(wf.artifact_class).toBe("fixture");
  });
});

describe("addStep / findStep", () => {
  it("adds and finds step", () => {
    const wf = createWorkflow({ kind: "feature", slug: "test" });
    addStep(wf, makeStep("s1"));
    addStep(wf, makeStep("s2"));
    expect(wf.steps.length).toBe(2);
    expect(findStep(wf, "s1")?.id).toBe("s1");
    expect(findStep(wf, "s2")?.id).toBe("s2");
    expect(findStep(wf, "missing")).toBeUndefined();
  });
});

describe("markStepDone", () => {
  it("marks step done with session id", () => {
    const wf = createWorkflow({ kind: "feature", slug: "test" });
    addStep(wf, makeStep("s1"));
    markStepDone(wf, "s1", "session-123");
    expect(findStep(wf, "s1")?.status).toBe("done");
    expect(findStep(wf, "s1")?.session_id).toBe("session-123");
  });

  it("marks step done without session id", () => {
    const wf = createWorkflow({ kind: "feature", slug: "test" });
    addStep(wf, makeStep("s1"));
    markStepDone(wf, "s1");
    expect(findStep(wf, "s1")?.status).toBe("done");
    expect(findStep(wf, "s1")?.session_id).toBeUndefined();
  });

  it("throws for missing step", () => {
    const wf = createWorkflow({ kind: "feature", slug: "test" });
    expect(() => markStepDone(wf, "missing")).toThrow("步骤不存在");
  });
});

describe("nextPendingStep", () => {
  it("finds first pending step", () => {
    const wf = createWorkflow({ kind: "feature", slug: "test" });
    addStep(wf, makeStep("s1", "done"));
    addStep(wf, makeStep("s2", "pending"));
    addStep(wf, makeStep("s3", "pending"));
    expect(nextPendingStep(wf)?.id).toBe("s2");
  });

  it("skips docs/orchestration when skipManual=true", () => {
    const wf = createWorkflow({ kind: "feature", slug: "test" });
    const docsStep = makeStep("s1", "pending");
    docsStep.executor = "docs";
    addStep(wf, docsStep);
    addStep(wf, makeStep("s2", "pending"));
    expect(nextPendingStep(wf, true)?.id).toBe("s2");
    expect(nextPendingStep(wf, false)?.id).toBe("s1");
  });

  it("returns undefined when no pending steps", () => {
    const wf = createWorkflow({ kind: "feature", slug: "test" });
    addStep(wf, makeStep("s1", "done"));
    expect(nextPendingStep(wf)).toBeUndefined();
  });
});

describe("writeWorkflow / readWorkflow", () => {
  it("round-trips feature workflow", async () => {
    const wf = createWorkflow({ kind: "feature", slug: "test-feat" });
    addStep(wf, makeStep("s1"));
    await writeWorkflow(tmpDir, wf);

    const loaded = await readWorkflow(tmpDir, "feature", "test-feat");
    expect(loaded.kind).toBe("feature");
    expect(loaded.slug).toBe("test-feat");
    expect(loaded.steps.length).toBe(1);
    expect(loaded.steps[0].id).toBe("s1");
  });

  it("round-trips issue workflow", async () => {
    const wf = createWorkflow({ kind: "issue", slug: "bug-fix" });
    await writeWorkflow(tmpDir, wf);
    const loaded = await readWorkflow(tmpDir, "issue", "bug-fix");
    expect(loaded.kind).toBe("issue");
  });

  it("throws for missing workflow", async () => {
    await expect(readWorkflow(tmpDir, "feature", "nonexistent")).rejects.toThrow("不存在");
  });

  it("creates directories automatically", async () => {
    const wf = createWorkflow({ kind: "feature", slug: "new-feat" });
    await writeWorkflow(tmpDir, wf);
    const dir = resolveWorkflowDir(tmpDir, "feature", "new-feat");
    const content = await readFile(join(dir, "workflow.yaml"), "utf-8");
    expect(content).toContain("new-feat");
  });
});

describe("writeAudit / listAudits", () => {
  it("writes and lists audit file", async () => {
    const wf = createWorkflow({ kind: "feature", slug: "test" });
    await writeWorkflow(tmpDir, wf);
    const dir = resolveWorkflowDir(tmpDir, "feature", "test");

    const auditFile = await writeAudit(dir, "s1", { success: true, timestamp: "2026-05-28" });
    expect(auditFile).toContain("s1-");
    expect(auditFile).toContain(".json");

    const audits = await listAudits(dir, "s1");
    expect(audits.length).toBe(1);
  });

  it("filters by step id", async () => {
    const wf = createWorkflow({ kind: "feature", slug: "test" });
    await writeWorkflow(tmpDir, wf);
    const dir = resolveWorkflowDir(tmpDir, "feature", "test");

    await writeAudit(dir, "s1", { success: true });
    await writeAudit(dir, "s2", { success: false });

    expect((await listAudits(dir, "s1")).length).toBe(1);
    expect((await listAudits(dir, "s2")).length).toBe(1);
    expect((await listAudits(dir)).length).toBe(2);
  });

  it("throws for empty stepId", async () => {
    const wf = createWorkflow({ kind: "feature", slug: "test" });
    await writeWorkflow(tmpDir, wf);
    const dir = resolveWorkflowDir(tmpDir, "feature", "test");
    await expect(writeAudit(dir, "", {})).rejects.toThrow("stepId is required");
  });

  it("generates unique filenames for concurrent writes", async () => {
    const wf = createWorkflow({ kind: "feature", slug: "test" });
    await writeWorkflow(tmpDir, wf);
    const dir = resolveWorkflowDir(tmpDir, "feature", "test");

    const files = await Promise.all([
      writeAudit(dir, "s1", { n: 1 }),
      writeAudit(dir, "s1", { n: 2 }),
      writeAudit(dir, "s1", { n: 3 }),
    ]);
    const uniqueFiles = new Set(files);
    expect(uniqueFiles.size).toBe(3);
  });
});

describe("resolveWorkflowDir", () => {
  it("resolves feature dir", () => {
    const dir = resolveWorkflowDir(tmpDir, "feature", "my-feat");
    expect(dir).toContain("features");
    expect(dir).toContain("my-feat");
  });

  it("resolves issue dir", () => {
    const dir = resolveWorkflowDir(tmpDir, "issue", "bug-123");
    expect(dir).toContain("issues");
    expect(dir).toContain("bug-123");
  });
});
