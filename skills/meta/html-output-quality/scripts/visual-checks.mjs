import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { smokeTestInteraction } from './interaction-checks.mjs';

const SKILLS_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../..');
const finding = (findings, level, code, message, detail = null) => findings.push({ level, code, message, detail });

export function browserLaunchOptions(args = {}, env = process.env) {
  const explicit = args.browserPath || args.browserChannel;
  const executablePath = explicit ? args.browserPath : env.HTML_QUALITY_BROWSER_PATH || env.WEB_ACCESS_BROWSER_PATH;
  const channel = explicit ? args.browserChannel : env.HTML_QUALITY_BROWSER_CHANNEL;
  if (executablePath && channel) throw new Error('浏览器路径和 channel 不能同时配置');
  return { headless: true, ...(executablePath ? { executablePath } : {}), ...(channel ? { channel } : {}) };
}

async function closeResource(resource, findings, code) {
  if (!resource) return;
  try { await resource.close(); }
  catch (error) { finding(findings, 'Warning', code, '浏览器资源关闭失败，已保留完成的检查结果', { error: error.name }); }
}

export async function runVisualChecks(args, findings) {
  const playwrightEntry = path.join(SKILLS_ROOT, 'node_modules', 'playwright', 'index.js');
  if (!fs.existsSync(playwrightEntry)) {
    finding(findings, 'Warning', 'playwright_unavailable', '当前环境缺少 Playwright，已跳过截图和响应式检查');
    return {};
  }
  const playwrightModule = await import(pathToFileURL(playwrightEntry).href);
  const chromium = playwrightModule.chromium || playwrightModule.default?.chromium;
  if (!chromium) {
    finding(findings, 'Warning', 'playwright_browser_unavailable', 'Playwright 模块未暴露 chromium，已跳过截图和响应式检查');
    return {};
  }
  // Launch a fresh browser with temporary state; never attach to a user profile.
  const browser = await chromium.launch(browserLaunchOptions(args));
  const screenshots = {};
  const blockedOrigins = new Set();
  const viewports = [
    { name: 'desktop', width: 1365, height: 900 },
    { name: 'mobile', width: 390, height: 900 },
  ];
  try {
    for (const viewport of viewports) {
      let context;
      let phase = 'context';
      try {
        context = await browser.newContext({ offline: true, serviceWorkers: 'block' });
        await context.route('**/*', async (route) => {
          const url = new URL(route.request().url());
          if (['file:', 'data:', 'blob:', 'about:'].includes(url.protocol)) await route.continue();
          else { blockedOrigins.add(url.origin); await route.abort('blockedbyclient'); }
        });
        if (typeof context.routeWebSocket === 'function') {
          await context.routeWebSocket('**/*', (socket) => {
            blockedOrigins.add(new URL(socket.url()).origin);
            socket.close();
          });
        }
        const page = await context.newPage();
        await page.setViewportSize({ width: viewport.width, height: viewport.height });
        phase = 'navigation';
        await page.goto(pathToFileURL(args.html).href, { waitUntil: 'networkidle', timeout: 15000 });
        phase = 'layout';
        const state = await page.evaluate(() => {
          const main = document.querySelector('main,[role="main"]');
          const rect = main?.getBoundingClientRect();
          const focusable = [...document.querySelectorAll('button,input,select,textarea,summary,a[href]')]
            .filter((item) => !item.disabled && item.getClientRects().length && getComputedStyle(item).visibility === 'visible');
          return {
            bodyTextLength: document.body?.innerText.trim().length || 0,
            mainVisible: Boolean(rect && rect.width > 20 && rect.height > 20),
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth,
            interactiveCount: focusable.length,
          };
        });
        if (state.bodyTextLength < 80) finding(findings, 'High', `${viewport.name}_blank`, `${viewport.name} 视口文本过少，疑似空白页`, state);
        if (!state.mainVisible) finding(findings, 'High', `${viewport.name}_main_invisible`, `${viewport.name} 视口主内容不可见`, state);
        if (state.scrollWidth > state.clientWidth + 4) finding(findings, 'Warning', `${viewport.name}_horizontal_overflow`, `${viewport.name} 视口存在横向溢出`, state);
        phase = 'screenshot';
        const screenshotPath = path.join(args.out, `${viewport.name}.png`);
        await page.screenshot({ path: screenshotPath, fullPage: true, timeout: 15000 });
        screenshots[viewport.name] = screenshotPath;
        const stat = fs.statSync(screenshotPath);
        if (stat.size < 1024) finding(findings, 'High', `${viewport.name}_screenshot_empty`, `${viewport.name} 截图文件过小，疑似空截图`, { bytes: stat.size });
        phase = 'interaction';
        if (state.interactiveCount === 0) {
          finding(findings, 'Warning', `${viewport.name}_interaction_missing`, `${viewport.name} 视口未发现可聚焦交互控件`, state);
        } else {
          const interaction = await smokeTestInteraction(page);
          if (!interaction.ok) finding(findings, 'Warning', `${viewport.name}_interaction_smoke_failed`, `${viewport.name} 视口交互冒烟验证未通过`, interaction);
        }
      } catch (error) {
        // Browser errors can quote page content or URLs. Preserve stage and type only.
        const code = phase === 'interaction' ? 'interaction_smoke_failed' : 'visual_check_failed';
        finding(findings, 'Warning', `${viewport.name}_${code}`, `${viewport.name} 视口检查未完成，已保留完成的截图`, { phase, error: error.name });
      } finally {
        await closeResource(context, findings, `${viewport.name}_context_close_failed`);
      }
    }
  } finally {
    if (blockedOrigins.size) finding(findings, 'High', 'external_requests_blocked', '离线检查已阻止页面网络请求', [...blockedOrigins]);
    await closeResource(browser, findings, 'browser_close_failed');
  }
  return screenshots;
}
