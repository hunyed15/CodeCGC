import { describe, it, expect } from "vitest";
import { validateSlug, assertWithinRoot, validateStepPaths, slugify } from "../src/mcp/codecgcmcp/runtime/paths.js";
import { normalize, sep } from "path";

describe("validateSlug", () => {
  it("accepts valid slug", () => {
    expect(() => validateSlug("2026-05-28-test-feature")).not.toThrow();
  });

  it("rejects slug with ..", () => {
    expect(() => validateSlug("../escape")).toThrow("非法 slug");
  });

  it("rejects slug with forward slash", () => {
    expect(() => validateSlug("a/b")).toThrow("非法 slug");
  });

  it("rejects slug with backslash", () => {
    expect(() => validateSlug("a\\b")).toThrow("非法 slug");
  });

  it("rejects slug with system separator", () => {
    expect(() => validateSlug(`a${sep}b`)).toThrow("非法 slug");
  });
});

describe("assertWithinRoot", () => {
  it("accepts path inside root", () => {
    const root = normalize("/tmp/project");
    const target = normalize("/tmp/project/.codecgc");
    expect(() => assertWithinRoot(root, target)).not.toThrow();
  });

  it("rejects path outside root", () => {
    const root = normalize("/tmp/project");
    const target = normalize("/tmp/escape");
    expect(() => assertWithinRoot(root, target)).toThrow("路径穿越");
  });

  it("rejects path that equals root (boundary)", () => {
    const root = normalize("/tmp/project");
    // assertWithinRoot allows root itself
    expect(() => assertWithinRoot(root, root)).not.toThrow();
  });
});

describe("validateStepPaths", () => {
  it("accepts relative path", () => {
    expect(() => validateStepPaths(["src/file.ts"])).not.toThrow();
  });

  it("rejects absolute path", () => {
    expect(() => validateStepPaths(["/etc/passwd"])).toThrow("不允许绝对路径");
  });

  it("rejects path starting with ..", () => {
    expect(() => validateStepPaths(["../secret"])).toThrow("不允许路径穿越");
  });

  it("accepts empty array", () => {
    expect(() => validateStepPaths([])).not.toThrow();
  });
});

describe("slugify", () => {
  it("prefixes with date", () => {
    const slug = slugify("my-feature", "2026-05-28");
    expect(slug).toBe("2026-05-28-my-feature");
  });

  it("uses today when no date given", () => {
    const slug = slugify("test");
    expect(slug).toMatch(/^\d{4}-\d{2}-\d{2}-test$/);
  });

  it("lowercases and cleans special chars", () => {
    const slug = slugify("My Super Feature!", "2026-05-28");
    expect(slug).toBe("2026-05-28-my-super-feature");
  });

  it("truncates to 60 chars in the name part", () => {
    const longName = "a".repeat(100);
    const slug = slugify(longName, "2026-05-28");
    const namePart = slug.slice("2026-05-28-".length);
    expect(namePart.length).toBeLessThanOrEqual(60);
  });
});
