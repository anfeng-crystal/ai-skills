#!/usr/bin/env node
/**
 * Darwin Skill - 高清截图脚本
 *
 * 用法: node scripts/screenshot.mjs [html文件路径] [输出png路径]
 */

import { createRequire } from 'module';
import os from 'os';
import path from 'path';
const require = createRequire(import.meta.url);

function envCandidates() {
  return (process.env.DARWIN_PLAYWRIGHT_CANDIDATES || '')
    .split(path.delimiter)
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function loadPlaywright() {
  const candidates = [
    ...envCandidates(),
    'playwright-core',
    'playwright',
    path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core'),
    path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright'),
    path.join(os.homedir(), '.hermes/hermes-agent/node_modules/playwright-core'),
    path.join(os.homedir(), '.hermes/hermes-agent/node_modules/playwright'),
  ];

  for (const candidate of candidates) {
    try {
      return require(candidate);
    } catch {
      continue;
    }
  }

  throw new Error(
    '未找到 playwright/playwright-core。请先安装 Playwright，或通过 DARWIN_PLAYWRIGHT_CANDIDATES 提供可解析模块。'
  );
}

const pw = loadPlaywright();

const htmlPath = process.argv[2] || new URL('../templates/result-card.html', import.meta.url).pathname;
const outputPath = process.argv[3] || new URL('../templates/result-card.png', import.meta.url).pathname;

async function screenshot() {
  const browser = await pw.chromium.launch();
  try {
    const context = await browser.newContext({ viewport: { width: 920, height: 1600 }, deviceScaleFactor: 2 });
    const page = await context.newPage();
    await page.goto(`file://${htmlPath}`, { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(2000);
    const card = await page.locator('.card');
    await card.screenshot({ path: outputPath, type: 'png' });
    console.log(`截图完成: ${outputPath}`);
  } finally {
    await browser.close();
  }
}

screenshot().catch(err => {
  console.error('截图失败:', err.message);
  process.exit(1);
});
