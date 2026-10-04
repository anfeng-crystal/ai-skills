#!/usr/bin/env node
/**
 * Darwin Skill - 高清截图脚本
 *
 * 用法: node scripts/screenshot.mjs [html文件路径] [输出png路径]
 */

import { createRequire } from 'module';
import os from 'os';
import path from 'path';
import { fileURLToPath, pathToFileURL } from 'node:url';
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

async function screenshot() {
  const args = process.argv.slice(2);
  if (args.length === 1 && ['--help', '-h'].includes(args[0])) {
    console.log('Usage: node screenshot.mjs [html-path] [output-png]\n'
      + 'Default output: ./result-card.png (in the current task directory).\n'
      + 'Set DARWIN_BROWSER_CHANNEL or DARWIN_BROWSER_EXECUTABLE to use an installed browser.\n'
      + 'DARWIN_BROWSER_EXECUTABLE takes precedence when both are set.');
    return;
  }
  if (args.length > 2 || args.some(arg => arg.startsWith('--'))) {
    throw new Error('Expected at most an HTML path and an output PNG path; use --help.');
  }
  const htmlPath = args[0] ? path.resolve(args[0])
    : fileURLToPath(new URL('../templates/result-card.html', import.meta.url));
  // Template assets are read-only inputs; the default artifact belongs to the task.
  const outputPath = path.resolve(args[1] || 'result-card.png');
  const launchOptions = process.env.DARWIN_BROWSER_EXECUTABLE
    ? { executablePath: process.env.DARWIN_BROWSER_EXECUTABLE }
    : process.env.DARWIN_BROWSER_CHANNEL ? { channel: process.env.DARWIN_BROWSER_CHANNEL } : {};
  const pw = loadPlaywright();
  const browser = await pw.chromium.launch(launchOptions);
  try {
    const context = await browser.newContext({ viewport: { width: 920, height: 1600 }, deviceScaleFactor: 2 });
    const page = await context.newPage();
    await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'networkidle' });
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
