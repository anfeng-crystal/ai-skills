#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ACTIVE_ROOT = path.resolve(__dirname, '../../../..');

function parseArgs(argv) {
  const args = { html: null, source: null, out: null };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--html') args.html = argv[++i];
    else if (arg === '--source') args.source = argv[++i];
    else if (arg === '--out') args.out = argv[++i];
    else if (arg === '--help' || arg === '-h') {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`未知参数: ${arg}`);
    }
  }
  if (!args.html) throw new Error('缺少必需参数 --html');
  args.html = path.resolve(args.html);
  if (args.source) args.source = path.resolve(args.source);
  args.out = path.resolve(args.out || path.dirname(args.html));
  return args;
}

function printHelp() {
  console.log(`Usage:
  node skills/meta/html-output-quality/scripts/check-html.mjs --html <file> [--source <json-or-tsv>] [--out <dir>]

Outputs:
  quality-report.json
  quality-report.md
  desktop.png / mobile.png when Playwright is available`);
}

function addFinding(findings, level, code, message, detail = null) {
  findings.push({ level, code, message, detail });
}

function stripTags(html) {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style[\s\S]*?<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')
    .trim();
}

function readSourceCount(sourcePath, findings) {
  if (!sourcePath) {
    addFinding(findings, 'Warning', 'source_missing', '未提供 source，无法校验 HTML 声明条数');
    return null;
  }
  if (!fs.existsSync(sourcePath)) {
    addFinding(findings, 'High', 'source_not_found', 'source 文件不存在', sourcePath);
    return null;
  }

  const content = fs.readFileSync(sourcePath, 'utf8');
  const ext = path.extname(sourcePath).toLowerCase();
  if (ext === '.json') {
    try {
      const data = JSON.parse(content);
      if (Array.isArray(data)) return data.length;
      if (Number.isInteger(data?.recordCount)) return data.recordCount;
      if (Number.isInteger(data?._recordCount)) return data._recordCount;
      const largest = findLargestArray(data);
      if (largest !== null) return largest;
      addFinding(findings, 'Warning', 'source_json_no_array', 'JSON 中未找到可计数数组，跳过条数校验');
      return null;
    } catch (error) {
      addFinding(findings, 'High', 'source_json_invalid', 'source JSON 无法解析', error.message);
      return null;
    }
  }

  if (ext === '.tsv' || ext === '.csv') {
    const lines = content.split(/\r?\n/).filter((line) => line.trim().length > 0);
    return Math.max(0, lines.length - 1);
  }

  addFinding(findings, 'Warning', 'source_type_unknown', 'source 类型不是 JSON/TSV/CSV，跳过条数校验', ext || '(no extension)');
  return null;
}

function findLargestArray(value) {
  if (Array.isArray(value)) return value.length;
  if (!value || typeof value !== 'object') return null;
  let best = null;
  for (const child of Object.values(value)) {
    const count = findLargestArray(child);
    if (count !== null && (best === null || count > best)) best = count;
  }
  return best;
}

function getHtmlDeclaredCount(html, findings) {
  const match = html.match(/data-(?:source|record)-count=["'](\d+)["']/i);
  if (!match) {
    addFinding(findings, 'Warning', 'html_count_missing', 'HTML 未声明 data-source-count 或 data-record-count，无法与 source 条数比对');
    return null;
  }
  return Number.parseInt(match[1], 10);
}

function checkStaticHtml(html, args, findings) {
  const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  if (!titleMatch || stripTags(titleMatch[1]).length === 0) {
    addFinding(findings, 'High', 'title_missing', '缺少非空 <title>');
  }

  if (!/<main(?:\s|>)/i.test(html) && !/role=["']main["']/i.test(html)) {
    addFinding(findings, 'High', 'main_missing', '缺少 <main> 或 role="main" 主内容区');
  }

  if (!/(data-generated-at|生成时间|Generated|generated at)/i.test(html)) {
    addFinding(findings, 'High', 'generated_at_missing', '缺少生成时间标记');
  }

  if (!/(data-source|来源|Source)/i.test(html)) {
    addFinding(findings, 'High', 'source_label_missing', '缺少来源说明');
  }

  const bodyText = stripTags(html);
  if (bodyText.length < 80) {
    addFinding(findings, 'High', 'blank_or_sparse', '页面文本过少，疑似空白 HTML', `textLength=${bodyText.length}`);
  }

  checkStaticInteractivity(html, findings);

  const externalPatterns = [
    { code: 'external_script', pattern: /<script\b[^>]*\bsrc=["'](?:https?:)?\/\//i, label: '外链脚本' },
    { code: 'external_stylesheet', pattern: /<link\b[^>]*\bhref=["'](?:https?:)?\/\//i, label: '外链样式/字体' },
    { code: 'external_import', pattern: /@import\s+url\(["']?(?:https?:)?\/\//i, label: 'CSS 外链 import' },
    { code: 'external_image', pattern: /<(?:img|source)\b[^>]*\bsrc=["'](?:https?:)?\/\//i, label: '外链图片' },
  ];
  for (const item of externalPatterns) {
    if (item.pattern.test(html)) addFinding(findings, 'High', item.code, `默认禁止${item.label}`);
  }

  const sensitivePatterns = [
    { code: 'secret_password', pattern: /\b(password|passwd|pwd)\b\s*[:=]/i },
    { code: 'secret_cookie', pattern: /\b(cookie|set-cookie)\b\s*[:=]/i },
    { code: 'secret_token', pattern: /\b(token|secret|api[_-]?key)\b\s*[:=]/i },
    { code: 'secret_authorization', pattern: /\bauthorization\b\s*[:=]/i },
  ];
  for (const item of sensitivePatterns) {
    if (item.pattern.test(html)) addFinding(findings, 'High', item.code, 'HTML 疑似包含敏感字段或凭据形态');
  }

  const sourceCount = readSourceCount(args.source, findings);
  const htmlCount = getHtmlDeclaredCount(html, findings);
  if (sourceCount !== null && htmlCount !== null && sourceCount !== htmlCount) {
    addFinding(findings, 'High', 'count_mismatch', 'HTML 声明条数与 source 条数不一致', { sourceCount, htmlCount });
  }
}

function checkStaticInteractivity(html, findings) {
  const interactivePatterns = [
    /<button\b/i,
    /<input\b/i,
    /<select\b/i,
    /<textarea\b/i,
    /<details\b/i,
    /<summary\b/i,
    /<a\b[^>]*\bhref=["']#/i,
  ];
  const hasInteractiveControl = interactivePatterns.some((pattern) => pattern.test(html));
  if (!hasInteractiveControl) {
    addFinding(findings, 'Warning', 'interaction_missing', '页面缺少搜索、筛选、排序、折叠、跳转或复制等可操作控件');
    return;
  }

  const hasScriptedInteraction = /(addEventListener|onclick\s*=|oninput\s*=|onchange\s*=|aria-pressed|data-tab|data-filter|data-sort)/i.test(html);
  const hasNativeInteraction = /<details\b/i.test(html) || /<a\b[^>]*\bhref=["']#/i.test(html);
  if (!hasScriptedInteraction && !hasNativeInteraction) {
    addFinding(findings, 'Warning', 'interaction_static_controls', '页面有控件但缺少可见状态变化或事件处理');
  }
}

async function runVisualChecks(args, findings) {
  const playwrightEntry = path.join(ACTIVE_ROOT, 'node_modules', 'playwright', 'index.js');
  if (!fs.existsSync(playwrightEntry)) {
    addFinding(findings, 'Warning', 'playwright_unavailable', '当前环境缺少 Playwright，已跳过截图和响应式检查');
    return {};
  }

  const playwrightModule = await import(pathToFileURL(playwrightEntry).href);
  const chromium = playwrightModule.chromium || playwrightModule.default?.chromium;
  if (!chromium) {
    addFinding(findings, 'Warning', 'playwright_browser_unavailable', 'Playwright 模块未暴露 chromium，已跳过截图和响应式检查');
    return {};
  }
  const browser = await chromium.launch({ headless: true });
  const htmlUrl = pathToFileURL(args.html).href;
  const screenshots = {};
  const viewports = [
    { name: 'desktop', width: 1365, height: 900 },
    { name: 'mobile', width: 390, height: 900 },
  ];

  try {
    for (const viewport of viewports) {
      const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height } });
      await page.goto(htmlUrl, { waitUntil: 'networkidle' });
      const state = await page.evaluate(() => {
        const main = document.querySelector('main,[role="main"]');
        const rect = main ? main.getBoundingClientRect() : null;
        const focusable = Array.from(document.querySelectorAll('button,input,select,textarea,summary,a[href]'))
          .filter((item) => !item.disabled && item.offsetParent !== null);
        return {
          bodyTextLength: document.body ? document.body.innerText.trim().length : 0,
          mainVisible: Boolean(rect && rect.width > 20 && rect.height > 20),
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth,
          interactiveCount: focusable.length,
        };
      });

      if (state.bodyTextLength < 80) {
        addFinding(findings, 'High', `${viewport.name}_blank`, `${viewport.name} 视口文本过少，疑似空白页`, state);
      }
      if (!state.mainVisible) {
        addFinding(findings, 'High', `${viewport.name}_main_invisible`, `${viewport.name} 视口主内容不可见`, state);
      }
      if (state.scrollWidth > state.clientWidth + 4) {
        addFinding(findings, 'Warning', `${viewport.name}_horizontal_overflow`, `${viewport.name} 视口存在横向溢出`, state);
      }
      if (state.interactiveCount === 0) {
        addFinding(findings, 'Warning', `${viewport.name}_interaction_missing`, `${viewport.name} 视口未发现可聚焦交互控件`, state);
      } else {
        const interaction = await smokeTestInteraction(page);
        if (!interaction.ok) {
          addFinding(findings, 'Warning', `${viewport.name}_interaction_smoke_failed`, `${viewport.name} 视口交互冒烟验证未通过`, interaction);
        }
      }

      const screenshotPath = path.join(args.out, `${viewport.name}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: true });
      const stat = fs.statSync(screenshotPath);
      screenshots[viewport.name] = screenshotPath;
      if (stat.size < 1024) {
        addFinding(findings, 'High', `${viewport.name}_screenshot_empty`, `${viewport.name} 截图文件过小，疑似空截图`, { bytes: stat.size });
      }
      await page.close();
    }
  } finally {
    await browser.close();
  }

  return screenshots;
}

async function smokeTestInteraction(page) {
  const result = await page.evaluate(() => {
    function visibleRows() {
      return Array.from(document.querySelectorAll('tbody tr')).filter((row) => !row.hidden).length;
    }
    function visiblePanels() {
      return Array.from(document.querySelectorAll('[data-panel]')).filter((panel) => getComputedStyle(panel).display !== 'none').map((panel) => panel.getAttribute('data-panel'));
    }
    const before = {
      rows: visibleRows(),
      panels: visiblePanels(),
      text: document.body.innerText,
    };
    return before;
  });

  const search = page.locator('input[type="search"], input:not([type])').first();
  if (await search.count()) {
    await search.fill('__html_gate_no_match__');
    await page.waitForTimeout(50);
    const changed = await page.evaluate((beforeRows) => {
      const rows = Array.from(document.querySelectorAll('tbody tr'));
      const visible = rows.filter((row) => !row.hidden).length;
      const input = document.querySelector('input[type="search"], input:not([type])');
      return Boolean(input?.value === '__html_gate_no_match__' && (rows.length === 0 || visible !== beforeRows));
    }, result.rows);
    if (changed) return { ok: true, action: 'search' };
    await search.fill('');
  }

  const levelButton = page.locator('button[data-filter-level]').filter({ hasText: /.+/ }).nth(1);
  if (await levelButton.count()) {
    await levelButton.click();
    await page.waitForTimeout(50);
    const changed = await page.evaluate((beforeRows) => {
      const rows = Array.from(document.querySelectorAll('tbody tr'));
      const visible = rows.filter((row) => !row.hidden).length;
      const active = document.querySelector('button[data-filter-level].active');
      return Boolean(active || (rows.length > 0 && visible !== beforeRows));
    }, result.rows);
    if (changed) return { ok: true, action: 'filter-card' };
  }

  const tab = page.locator('button[data-tab]').nth(1);
  if (await tab.count()) {
    await tab.click();
    await page.waitForTimeout(50);
    const changed = await page.evaluate((beforePanels) => {
      const activePressed = document.querySelector('button[data-tab][aria-pressed="true"]');
      const visible = Array.from(document.querySelectorAll('[data-panel]')).filter((panel) => getComputedStyle(panel).display !== 'none').map((panel) => panel.getAttribute('data-panel'));
      return Boolean(activePressed && JSON.stringify(visible) !== JSON.stringify(beforePanels));
    }, result.panels);
    if (changed) return { ok: true, action: 'tab' };
  }

  const sortable = page.locator('th[data-sort]').first();
  if (await sortable.count()) {
    await sortable.click();
    await page.waitForTimeout(50);
    const changed = await sortable.evaluate((node) => Boolean(node.getAttribute('aria-sort')));
    if (changed) return { ok: true, action: 'sort' };
  }

  const summary = page.locator('summary').first();
  if (await summary.count()) {
    const before = await summary.evaluate((node) => node.parentElement?.open);
    await summary.click();
    await page.waitForTimeout(50);
    const after = await summary.evaluate((node) => node.parentElement?.open);
    if (before !== after) return { ok: true, action: 'details' };
  }

  const button = page.locator('button').first();
  if (await button.count()) {
    await button.focus();
    const focused = await button.evaluate((node) => document.activeElement === node);
    if (focused) return { ok: true, action: 'focusable-button' };
  }

  return { ok: false, reason: 'no supported interaction changed visible state' };
}

function statusFromFindings(findings) {
  if (findings.some((item) => item.level === 'High')) return 'fail';
  if (findings.some((item) => item.level === 'Warning' || item.level === 'Medium')) return 'warn';
  return 'pass';
}

function renderMarkdown(report) {
  const lines = [];
  lines.push(`# HTML 质量检查报告`);
  lines.push('');
  lines.push(`**状态**：${report.status}`);
  lines.push(`**HTML**：${report.html}`);
  if (report.source) lines.push(`**Source**：${report.source}`);
  lines.push(`**检查时间**：${report.checkedAt}`);
  lines.push('');

  if (Object.keys(report.screenshots).length > 0) {
    lines.push('## 截图');
    for (const [name, file] of Object.entries(report.screenshots)) {
      lines.push(`- ${name}: ${file}`);
    }
    lines.push('');
  }

  lines.push('## Findings');
  if (report.findings.length === 0) {
    lines.push('- 无 High/Warning 问题。');
  } else {
    for (const item of report.findings) {
      const detail = item.detail ? ` (${typeof item.detail === 'string' ? item.detail : JSON.stringify(item.detail)})` : '';
      lines.push(`- **${item.level}** [${item.code}] ${item.message}${detail}`);
    }
  }
  lines.push('');
  return lines.join('\n');
}

async function main() {
  const args = parseArgs(process.argv);
  if (!fs.existsSync(args.html)) throw new Error(`HTML 文件不存在: ${args.html}`);
  fs.mkdirSync(args.out, { recursive: true });

  const findings = [];
  const html = fs.readFileSync(args.html, 'utf8');
  checkStaticHtml(html, args, findings);

  let screenshots = {};
  try {
    screenshots = await runVisualChecks(args, findings);
  } catch (error) {
    addFinding(findings, 'Warning', 'playwright_check_failed', 'Playwright 截图或响应式检查失败', error.message);
  }

  const report = {
    status: statusFromFindings(findings),
    html: args.html,
    source: args.source,
    checkedAt: new Date().toISOString(),
    findings,
    screenshots,
  };

  const jsonPath = path.join(args.out, 'quality-report.json');
  const mdPath = path.join(args.out, 'quality-report.md');
  fs.writeFileSync(jsonPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  fs.writeFileSync(mdPath, renderMarkdown(report), 'utf8');

  console.log(JSON.stringify({ status: report.status, report: jsonPath, markdown: mdPath, findings: findings.length, screenshots }, null, 2));
  if (report.status === 'fail') process.exitCode = 1;
}

main().catch((error) => {
  console.error(`check-html failed: ${error.message}`);
  process.exit(2);
});
