import { describe, it, expect } from "vitest";
import { classifyPath, classifyPaths, isPureBackend, isPureFrontend, isPureDocs, hasMixedOwnership, pathOwnershipReport } from "../src/mcp/codecgcmcp/runtime/routing.js";
import type { ModelRouting } from "../src/shared/types.js";

const DEFAULT_ROUTING: ModelRouting = {
  version: 1,
  rules: [
    { patterns: ["**/*.py", "**/api/**", "**/server/**", "**/backend/**"], ownership: "backend" },
    { patterns: ["**/*.tsx", "**/*.jsx", "**/*.css", "**/components/**", "**/frontend/**"], ownership: "frontend" },
    { patterns: ["**/*.md", "**/docs/**", "README*"], ownership: "docs" },
    { patterns: ["**/shared/**", "**/utils/**"], ownership: "shared" },
  ],
};

describe("classifyPath", () => {
  it("classifies Python file as backend", () => {
    expect(classifyPath("src/api/handler.py", DEFAULT_ROUTING)).toBe("backend");
  });

  it("classifies TSX as frontend", () => {
    expect(classifyPath("src/components/Button.tsx", DEFAULT_ROUTING)).toBe("frontend");
  });

  it("classifies CSS as frontend", () => {
    expect(classifyPath("src/styles/main.css", DEFAULT_ROUTING)).toBe("frontend");
  });

  it("classifies Markdown as docs", () => {
    expect(classifyPath("README.md", DEFAULT_ROUTING)).toBe("docs");
  });

  it("classifies docs directory as docs", () => {
    expect(classifyPath("docs/architecture.md", DEFAULT_ROUTING)).toBe("docs");
  });

  it("classifies shared as shared", () => {
    expect(classifyPath("src/shared/utils.ts", DEFAULT_ROUTING)).toBe("shared");
  });

  it("returns unknown for unmatched path", () => {
    expect(classifyPath("src/misc/helper.ts", DEFAULT_ROUTING)).toBe("unknown");
  });

  it("first matching rule wins (priority)", () => {
    // backend rule matches *.py first
    expect(classifyPath("api/models.py", DEFAULT_ROUTING)).toBe("backend");
  });

  it("handles dot files", () => {
    expect(classifyPath(".env", DEFAULT_ROUTING)).toBe("unknown");
  });
});

describe("classifyPaths", () => {
  it("groups paths by ownership", () => {
    const result = classifyPaths(
      ["src/api/h.py", "src/components/B.tsx", "README.md", "src/shared/u.ts"],
      DEFAULT_ROUTING
    );
    expect(result.get("backend")).toEqual(["src/api/h.py"]);
    expect(result.get("frontend")).toEqual(["src/components/B.tsx"]);
    expect(result.get("docs")).toEqual(["README.md"]);
    expect(result.get("shared")).toEqual(["src/shared/u.ts"]);
  });

  it("returns empty map for empty input", () => {
    const result = classifyPaths([], DEFAULT_ROUTING);
    expect(result.size).toBe(0);
  });

  it("groups multiple files under same ownership", () => {
    const result = classifyPaths(["a.py", "b.py", "c.py"], DEFAULT_ROUTING);
    expect(result.get("backend")!.length).toBe(3);
  });
});

describe("isPureBackend", () => {
  it("returns true for all backend paths", () => {
    expect(isPureBackend(["src/api/h.py", "src/server/main.py"], DEFAULT_ROUTING)).toBe(true);
  });

  it("returns false if mixed", () => {
    expect(isPureBackend(["src/api/h.py", "src/components/B.tsx"], DEFAULT_ROUTING)).toBe(false);
  });

  it("returns false for empty array", () => {
    expect(isPureBackend([], DEFAULT_ROUTING)).toBe(false);
  });
});

describe("isPureFrontend", () => {
  it("returns true for all frontend paths", () => {
    expect(isPureFrontend(["src/components/A.tsx", "src/styles/B.css"], DEFAULT_ROUTING)).toBe(true);
  });

  it("returns false for mixed", () => {
    expect(isPureFrontend(["src/components/A.tsx", "src/api/h.py"], DEFAULT_ROUTING)).toBe(false);
  });
});

describe("isPureDocs", () => {
  it("returns true for all docs paths", () => {
    expect(isPureDocs(["README.md", "CHANGELOG.md"], DEFAULT_ROUTING)).toBe(true);
  });

  it("returns false for mixed", () => {
    expect(isPureDocs(["README.md", "src/main.ts"], DEFAULT_ROUTING)).toBe(false);
  });
});

describe("hasMixedOwnership", () => {
  it("returns true for mixed paths", () => {
    expect(hasMixedOwnership(["src/api/h.py", "README.md"], DEFAULT_ROUTING)).toBe(true);
  });

  it("returns true for shared paths", () => {
    expect(hasMixedOwnership(["src/shared/utils.ts"], DEFAULT_ROUTING)).toBe(true);
  });

  it("returns true for unknown paths", () => {
    expect(hasMixedOwnership(["random.ts"], DEFAULT_ROUTING)).toBe(true);
  });

  it("returns false for pure backend", () => {
    expect(hasMixedOwnership(["src/api/h.py"], DEFAULT_ROUTING)).toBe(false);
  });
});

describe("pathOwnershipReport", () => {
  it("generates readable report", () => {
    const report = pathOwnershipReport(["src/api/h.py", "README.md"], DEFAULT_ROUTING);
    expect(report).toContain("backend:");
    expect(report).toContain("docs:");
    expect(report).toContain("src/api/h.py");
    expect(report).toContain("README.md");
  });
});
