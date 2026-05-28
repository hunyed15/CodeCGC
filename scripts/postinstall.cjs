#!/usr/bin/env node
/**
 * postinstall.cjs
 *
 * 全局安装后自动释放 cgc 和 cgc-init 两个 skill 到 ~/.claude/skills/<name>/SKILL.md
 * 并注册 codecgcmcp MCP 服务器到全局 Claude Code 配置
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

// 只释放这两个 skill 到全局
const GLOBAL_SKILLS = ['cgc-init', 'cgc'];

function isGlobalInstall() {
  if (process.env.npm_config_global === 'true') return true;

  const installPath = __dirname;
  const globalPaths = [
    path.join(process.env.APPDATA || '', 'npm', 'node_modules'),
    '/usr/local/lib/node_modules',
    path.join(os.homedir(), '.npm-global', 'node_modules'),
  ];
  return globalPaths.some(p => p && installPath.includes(p));
}

if (!isGlobalInstall()) {
  console.log('[codecgc] project-level install, skipping global skill release');
  process.exit(0);
}

console.log('[codecgc] global install detected, releasing skills...\n');

const skillsSourceDir = path.join(__dirname, '..', 'skills');
const skillsTargetBase = path.join(os.homedir(), '.claude', 'skills');

// 所有可能的旧版 skill 名称（用于清理遗留的扁平文件）
const LEGACY_SKILLS = [
  'cgc', 'cgc-init', 'cgc-build', 'cgc-doctor', 'cgc-entry',
  'cgc-explain', 'cgc-fix', 'cgc-history', 'cgc-plan', 'cgc-review',
  'cgc-status', 'cgc-test', 'cgc-continue', 'cgc-audit', 'cgc-manual',
];

try {
  fs.mkdirSync(skillsTargetBase, { recursive: true });

  // 清理旧的扁平 .md 文件（之前版本遗留）
  for (const name of LEGACY_SKILLS) {
    const oldFlat = path.join(skillsTargetBase, `${name}.md`);
    if (fs.existsSync(oldFlat) && fs.statSync(oldFlat).isFile()) {
      fs.unlinkSync(oldFlat);
      console.log(`  - removed legacy flat file: ${name}.md`);
    }
  }

  let successCount = 0;
  for (const name of GLOBAL_SKILLS) {
    const srcFile = path.join(skillsSourceDir, `${name}.md`);
    if (!fs.existsSync(srcFile)) {
      console.warn(`  ! source not found: skills/${name}.md`);
      continue;
    }

    const destDir = path.join(skillsTargetBase, name);
    const destFile = path.join(destDir, 'SKILL.md');

    fs.mkdirSync(destDir, { recursive: true });
    fs.copyFileSync(srcFile, destFile);
    console.log(`  + ${name}/SKILL.md`);
    successCount++;
  }

  console.log(`\n[codecgc] released ${successCount} skill(s) to ~/.claude/skills/`);

  // 注册 codecgcmcp MCP 服务器到全局 Claude Code 配置
  const cgcMcpPath = path.join(__dirname, '..', 'bin', 'cgc-mcp.js');
  try {
    execSync(
      `claude mcp add --scope user codecgcmcp node "${cgcMcpPath}" "codecgcmcp"`,
      { stdio: 'pipe', timeout: 10000 }
    );
    console.log('  + registered codecgcmcp MCP server (global)');
  } catch (mcpErr) {
    // claude CLI 可能不在 PATH，手动写入 ~/.claude.json
    const claudeConfigPath = path.join(os.homedir(), '.claude.json');
    let config = {};
    if (fs.existsSync(claudeConfigPath)) {
      try { config = JSON.parse(fs.readFileSync(claudeConfigPath, 'utf-8')); } catch {}
    }
    if (!config.mcpServers) config.mcpServers = {};
    if (!config.mcpServers.codecgcmcp) {
      config.mcpServers.codecgcmcp = {
        type: 'stdio',
        command: 'node',
        args: [cgcMcpPath, 'codecgcmcp'],
      };
      fs.writeFileSync(claudeConfigPath, JSON.stringify(config, null, 2), 'utf-8');
      console.log('  + registered codecgcmcp MCP server (fallback)');
    } else {
      console.log('  ~ codecgcmcp MCP server already registered');
    }
  }

  console.log('\nAvailable globally in Claude Code:');
  console.log('  /cgc-init  - initialize project');
  console.log('  /cgc       - single entry point\n');

} catch (err) {
  console.error('[codecgc] skill release failed:', err.message);
  process.exit(0);
}
