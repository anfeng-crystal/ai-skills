#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { readSourceCount } from './source-count.mjs';
import { readHtmlDeclaredCount } from './html-count.mjs';
import { runVisualChecks } from './visual-checks.mjs';

function parseArgs(argv) {
  const args = { html: null, source: null, out: null, browserPath: null, browserChannel: null };
  for (let i = 2; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--html' || arg === '--source' || arg === '--out') {
      const value = argv[++i];
      if (!value || value.startsWith('--') || value === '-h') throw new Error(`${arg} 缺少参数值`);
      args[arg.slice(2)] = value;
    }
    else if (arg === '--browser-path' || arg === '--browser-channel') {
      const value = argv[++i];
      if (!value || value.startsWith('--')) throw new Error(`${arg} 缺少参数值`);
      args[arg === '--browser-path' ? 'browserPath' : 'browserChannel'] = value;
    }
    else if (arg === '--help' || arg === '-h') {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`未知参数: ${arg}`);
    }
  }
  if (!args.html) throw new Error('缺少必需参数 --html');
  if (args.browserPath && args.browserChannel) throw new Error('--browser-path 与 --browser-channel 不能同时使用');
  args.html = path.resolve(args.html);
  if (args.source) args.source = path.resolve(args.source);
  args.out = path.resolve(args.out || path.dirname(args.html));
  return args;
}

function printHelp() {
  console.log(`Usage:
  node skills/meta/html-output-quality/scripts/check-html.mjs --html <file> [--source <json-or-tsv-or-csv>] [--out <dir>]
    [--browser-path <executable> | --browser-channel <channel>]

Outputs:
  quality-report.json
  quality-report.md
  desktop.png / mobile.png when Playwright is available

Browser environment: HTML_QUALITY_BROWSER_PATH (or WEB_ACCESS_BROWSER_PATH), HTML_QUALITY_BROWSER_CHANNEL`);
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

function getHtmlDeclaredCount(html, findings) {
  const count = readHtmlDeclaredCount(html);
  if (count === null) {
    addFinding(findings, 'Warning', 'html_count_missing', 'HTML 未声明 data-source-count 或 data-record-count，无法与 source 条数比对');
    return null;
  }
  return count;
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
