#!/usr/bin/env node
/**
 * postinstall.cjs
 *
 * 全局安装后自动释放 CodeCGC skills 到 ~/.claude/skills/
 * 使用户可以在任何项目中直接使用 /cgc-init、/cgc-entry 等命令
 */

const fs = require('fs');
const path = require('path');
const os = require('os');

// 检测是否为全局安装
function isGlobalInstall() {
  // npm 全局安装时 npm_config_global 为 true
  if (process.env.npm_config_global === 'true') {
    return true;
  }

  // 检查安装路径是否在全局 node_modules 中
  const installPath = __dirname;
  const globalPaths = [
    path.join(process.env.APPDATA || '', 'npm', 'node_modules'),  // Windows
    '/usr/local/lib/node_modules',                                  // macOS/Linux
    path.join(os.homedir(), '.npm-global', 'node_modules'),        // 自定义全局路径
  ];

  return globalPaths.some(p => installPath.includes(p));
}

// 只在全局安装时执行
if (!isGlobalInstall()) {
  console.log('📦 项目级安装，跳过 skill 释放');
  process.exit(0);
}

console.log('🚀 检测到全局安装，开始释放 CodeCGC skills...\n');

const skillsSourceDir = path.join(__dirname, '..', 'skills');
const skillsTargetDir = path.join(os.homedir(), '.claude', 'skills');

try {
  // 确保目标目录存在
  fs.mkdirSync(skillsTargetDir, { recursive: true });

  // 读取所有 skill 文件
  const skillFiles = fs.readdirSync(skillsSourceDir).filter(f => f.endsWith('.md'));

  if (skillFiles.length === 0) {
    console.warn('⚠️  未找到 skill 文件');
    process.exit(0);
  }

  // 复制每个 skill
  let successCount = 0;
  for (const skillFile of skillFiles) {
    const src = path.join(skillsSourceDir, skillFile);
    const dest = path.join(skillsTargetDir, skillFile);

    try {
      fs.copyFileSync(src, dest);
      console.log(`  ✓ ${skillFile}`);
      successCount++;
    } catch (err) {
      console.error(`  ✗ ${skillFile}: ${err.message}`);
    }
  }

  console.log(`\n✅ 成功释放 ${successCount}/${skillFiles.length} 个 skills 到 ~/.claude/skills/`);
  console.log('\n现在可以在任何项目的 Claude Code 中使用：');
  console.log('  /cgc-init   - 初始化项目配置');
  console.log('  /cgc-entry  - 创建工作流');
  console.log('  /cgc-status - 查看状态');
  console.log('  /cgc        - 单入口命令\n');

} catch (err) {
  console.error('❌ skill 释放失败:', err.message);
  // 不阻止安装流程
  process.exit(0);
}
