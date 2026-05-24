#!/usr/bin/env node
/**
 * postinstall.cjs
 *
 * 全局安装后自动释放 cgc 和 cgc-init 两个 skill 到 ~/.claude/skills/<name>/SKILL.md
 * 使用户可以在任何项目的 Claude Code 中直接使用 /cgc-init 初始化项目
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

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

try {
  fs.mkdirSync(skillsTargetBase, { recursive: true });

  // 清理旧的扁平 .md 文件（之前版本遗留）
  for (const name of GLOBAL_SKILLS) {
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
  console.log('\nAvailable globally in Claude Code:');
  console.log('  /cgc-init  - initialize project');
  console.log('  /cgc       - single entry point\n');

} catch (err) {
  console.error('[codecgc] skill release failed:', err.message);
  process.exit(0);
}
