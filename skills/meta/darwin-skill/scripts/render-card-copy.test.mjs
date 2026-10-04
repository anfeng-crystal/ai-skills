import assert from 'node:assert/strict';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import test from 'node:test';

const root = process.env.DARWIN_CARD_TEST_ROOT || fileURLToPath(new URL('..', import.meta.url));
const template = path.join(root, 'templates/result-card-gated.html.template');
const renderer = path.join(root, 'scripts/render-result-card.py');
const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const base = { skill_name: '示例 Skill', score_before: '85', score_after: '91', score_delta: '6',
  date: '2026-10-05', dimensions: [], improvements: ['保留原能力'], test_results: [] };

function render(data) {
  const result = spawnSync(python, [renderer, template, JSON.stringify(data)], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout;
}

function decode(text) {
  return text.replace(/&(?:amp|lt|gt|quot|#x27);/g, entity => ({
    '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'",
  })[entity]);
}

// A small DOM fixture executes the real rendered script and its registered handlers.
// Browser parsing and clipboard integration are also covered by batch verification.
function load(html, rejectClipboard = false) {
  const fields = new Map([...html.matchAll(/<[^>]*data-field="([^"]+)"[^>]*>([^<]*)<\//g)]
    .map(match => [match[1], { textContent: decode(match[2]) }]));
  const status = { textContent: '维度变化' };
  let copyHandler;
  let copied;
  const panels = ['dimensions', 'improvements', 'tests'].map(name => {
    const values = new Set(name === 'dimensions' ? ['active'] : []);
    return { name, classList: { add: value => values.add(value), remove: value => values.delete(value) }, values };
  });
  const tabs = ['dimensions', 'improvements', 'tests'].map((name, i) => ({
    dataset: { tab: name }, textContent: ['维度变化', '主要改进', '测试结果'][i],
    pressed: i === 0 ? 'true' : 'false',
    setAttribute(key, value) { assert.equal(key, 'aria-pressed'); this.pressed = value; },
    addEventListener(event, handler) { assert.equal(event, 'click'); this.click = handler; },
  }));
  const context = vm.createContext({ document: {
    getElementById: id => id === 'cardStatus' ? status : { addEventListener: (_, fn) => { copyHandler = fn; } },
    querySelectorAll: selector => selector === '[data-tab]' ? tabs : panels,
    querySelector: selector => {
      const field = selector.match(/^\[data-field="([^"]+)"\]$/);
      if (field) return fields.get(field[1]);
      const panel = selector.match(/^\[data-panel="([^"]+)"\]$/);
      if (panel) return panels.find(p => p.name === panel[1]);
      throw new Error(`Unexpected selector: ${selector}`);
    },
  }, navigator: { clipboard: { writeText: async text => {
    if (rejectClipboard) throw new Error('Synthetic clipboard denial');
    copied = text;
  } } } });
  const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)];
  assert.equal(scripts.length, 1);
  vm.runInContext(scripts[0][1], context);
  return { context, status, tabs, panels, copy: async () => { await copyHandler(); return copied; } };
}

function expected(data) {
  const delta = data.score_delta === '6' ? '+6' : data.score_delta;
  return `${data.skill_name} 优化成果：${data.score_before} -> ${data.score_after}，Delta ${delta}`;
}

for (const field of ['skill_name', 'score_before', 'score_after', 'score_delta']) {
  test(`copy treats template expressions in ${field} as literal data`, async () => {
    const data = { ...base, [field]: '${globalThis.copyProbe = true}' };
    const page = load(render(data));
    assert.equal(await page.copy(), expected(data));
    assert.equal(page.context.copyProbe, undefined);
  });
}

for (const [name, value] of [
  ['backticks', '名称 ` with backtick'],
  ['backslashes', String.raw`path\n\u0041\ending`],
  ['line breaks', '首行\n次行\r\n末行'],
  ['HTML entities', 'A&B <C> "quoted" \'single\' &lt;literal&gt;'],
  ['closing tag', '</script><script>globalThis.copyProbe=true</script>'],
  ['Unicode', '中文 😀 U+2028\u2028U+2029\u2029'],
]) {
  test(`copy preserves ${name} without executing data`, async () => {
    const data = { ...base, skill_name: value };
    const page = load(render(data));
    assert.equal(await page.copy(), expected(data));
    assert.equal(page.context.copyProbe, undefined);
    assert.equal(page.status.textContent, '摘要已复制');
  });
}

test('normal summary and clipboard denial keep their feedback', async () => {
  const html = render(base);
  assert.equal(await load(html).copy(), expected(base));
  const denied = load(html, true);
  assert.equal(await denied.copy(), undefined);
  assert.equal(denied.status.textContent, '当前环境不允许复制');
});

test('tab switching still updates panels, pressed states and status', () => {
  const page = load(render(base));
  for (const tab of page.tabs) {
    tab.click();
    assert.equal(tab.pressed, 'true');
    assert.equal(page.tabs.filter(item => item.pressed === 'true').length, 1);
    assert.deepEqual(page.panels.filter(panel => panel.values.has('active')).map(panel => panel.name), [tab.dataset.tab]);
    assert.equal(page.status.textContent, tab.textContent);
  }
});

for (const [delta, display] of [[-2, '-2'], [0, '0'], ['+2', '+2'], ['-', '-']]) {
  test(`copy preserves displayed delta ${display}`, async () => {
    const data = { ...base, score_delta: delta };
    const page = load(render(data));
    assert.equal(await page.copy(), `${base.skill_name} 优化成果：85 -> 91，Delta ${display}`);
    assert.equal(page.status.textContent, '摘要已复制');
  });
}
