import { existsSync } from "fs";
import { mkdir } from "fs/promises";
import { isAbsolute, join, normalize, relative, resolve, sep } from "path";

/**
 * 验证 slug 不含路径穿越字符
 */
export function validateSlug(slug: string): void {
  if (slug.includes("..") || slug.includes("/") || slug.includes("\\") || slug.includes(sep)) {
    throw new Error(`非法 slug: "${slug}"，不允许包含 ..、/ 或 \\`);
  }
}

/**
 * 验证路径在 projectRoot 之下（防止路径穿越）
 */
export function assertWithinRoot(projectRoot: string, targetPath: string): void {
  const resolvedRoot = resolve(projectRoot);
  const resolvedTarget = resolve(targetPath);
  if (!resolvedTarget.startsWith(resolvedRoot + sep) && resolvedTarget !== resolvedRoot) {
    throw new Error(`路径穿越: "${targetPath}" 不在项目根 "${projectRoot}" 之下`);
  }
}

/**
 * 验证 step.paths 不含路径穿越
 */
export function validateStepPaths(paths: string[]): void {
  for (const p of paths) {
    if (isAbsolute(p)) {
      throw new Error(`step.paths 不允许绝对路径: "${p}"`);
    }
    const normalized = normalize(p);
    if (normalized.startsWith("..")) {
      throw new Error(`step.paths 不允许路径穿越: "${p}"`);
    }
  }
}

/**
 * 解析项目根目录
 * 优先：env CODECGC_PROJECT_ROOT > 当前工作目录
 */
export function resolveProjectRoot(cd?: string): string {
  if (cd) return resolve(cd);
  if (process.env.CODECGC_PROJECT_ROOT) return resolve(process.env.CODECGC_PROJECT_ROOT);
  return process.cwd();
}

/**
 * CodeCGC 产物根目录（.codecgc 隐藏文件夹）
 */
export function codecgcRoot(projectRoot: string): string {
  return join(projectRoot, ".codecgc");
}

/**
 * Feature workflow 目录
 */
export function featureDir(projectRoot: string, slug: string): string {
  validateSlug(slug);
  const dir = join(codecgcRoot(projectRoot), "features", slug);
  assertWithinRoot(projectRoot, dir);
  return dir;
}

/**
 * Issue workflow 目录
 */
export function issueDir(projectRoot: string, slug: string): string {
  validateSlug(slug);
  const dir = join(codecgcRoot(projectRoot), "issues", slug);
  assertWithinRoot(projectRoot, dir);
  return dir;
}

/**
 * Workflow 文件路径
 */
export function workflowFile(workflowDir: string): string {
  return join(workflowDir, "workflow.yaml");
}

/**
 * Audit 目录
 */
export function auditDir(workflowDir: string): string {
  return join(workflowDir, "audits");
}

/**
 * 路由配置路径（.codecgc/config/routing.yaml）
 */
export function routingFile(projectRoot: string): string {
  return join(codecgcRoot(projectRoot), "config", "routing.yaml");
}

/**
 * 确保目录存在
 */
export async function ensureDir(dirPath: string): Promise<void> {
  if (!existsSync(dirPath)) {
    await mkdir(dirPath, { recursive: true });
  }
}

/**
 * 转换为 POSIX 风格路径（用于跨平台一致性）
 */
export function toPosixPath(p: string): string {
  return p.split(sep).join("/");
}

/**
 * 计算相对项目根的路径
 */
export function relativeToRoot(projectRoot: string, p: string): string {
  const abs = isAbsolute(p) ? p : resolve(projectRoot, p);
  return toPosixPath(relative(projectRoot, abs));
}

/**
 * 生成日期前缀的 slug
 * @example slugify("demo-login", "2026-05-23") → "2026-05-23-demo-login"
 */
export function slugify(name: string, date?: string): string {
  const today = date || new Date().toISOString().slice(0, 10);
  const cleaned = name
    .toLowerCase()
    .replace(/[^\w一-龥-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  return `${today}-${cleaned}`;
}

/**
 * 获取今天的日期字符串（YYYY-MM-DD）
 */
export function today(): string {
  return new Date().toISOString().slice(0, 10);
}
