import { readFile, writeFile } from "fs/promises";
import yaml from "js-yaml";

// 显式使用 JSON_SCHEMA：只允许 JSON 兼容类型，拒绝 !!js/function 等危险标签
const SAFE_LOAD_OPTIONS = { schema: yaml.JSON_SCHEMA };

/**
 * 读取 YAML 文件并解析为对象
 */
export async function readYaml<T = unknown>(filePath: string): Promise<T> {
  const content = await readFile(filePath, "utf-8");
  return yaml.load(content, SAFE_LOAD_OPTIONS) as T;
}

/**
 * 将对象序列化为 YAML 并写入文件
 */
export async function writeYaml(filePath: string, data: unknown): Promise<void> {
  const content = yaml.dump(data, {
    indent: 2,
    lineWidth: 120,
    noRefs: true,
    sortKeys: false,
    schema: yaml.JSON_SCHEMA,
  });
  await writeFile(filePath, content, "utf-8");
}

/**
 * 解析 YAML 字符串（安全 schema：只允许 JSON 兼容类型）
 */
export function parseYaml<T = unknown>(content: string): T {
  return yaml.load(content, SAFE_LOAD_OPTIONS) as T;
}

/**
 * 序列化对象为 YAML 字符串
 */
export function stringifyYaml(data: unknown): string {
  return yaml.dump(data, {
    indent: 2,
    lineWidth: 120,
    noRefs: true,
    sortKeys: false,
    schema: yaml.JSON_SCHEMA,
  });
}
