import assert from 'node:assert/strict';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = process.env.DARWIN_CARD_TEST_ROOT || fileURLToPath(new URL('..', import.meta.url));
const renderer = path.join(root, 'scripts/render-result-card.py');
const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const styles = ['minimal.md', 'tech.html', 'business.html', 'gated.html'];
const base = { skill_name: '维度评分', score_before: '71', score_after: '89', score_delta: '18',
  date: '2026-10-05', dimensions: [], improvements: ['保留实际评分'], test_results: [] };

function render(style, dimensions) {
  const template = path.join(root, `templates/result-card-${style}.template`);
  const result = spawnSync(python, [renderer, template, JSON.stringify({ ...base, dimensions })], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout;
}

function dimensionScores(output, style) {
  if (style === 'minimal.md') {
    return [...output.matchAll(/^\| ([^\n]+) \| ([^\n]+) \| ([^\n]+) \| ([^\n]+) \|$/gm)]
      .filter(match => match[1] !== '维度')
      .map(match => [match[2], match[3]]);
  }
  return [...output.matchAll(/<tr>\s*<td>[^<]*<\/td>\s*<td>([^<]*)<\/td>\s*<td>([^<]*)<\/td>/g)]
    .map(match => [match[1], match[2]]);
}

// The rubric permits different dimension maxima, but the input has no max field.
// Rendering must therefore preserve the supplied score without inventing a scale.
const scores = [
  { name: '触发精度', before: 7, after: 9, delta: 2 },
  { name: '任务与完成条件', before: 11, after: 14, delta: 3 },
  { name: '完成质量与真实性', before: 12.5, after: 19.5, delta: 7 },
  { name: '未评分', before: '-', after: '-', delta: '-' },
  { name: '已写明口径', before: '11/15', after: '14/15', delta: 3 },
  { name: '零分', before: 0, after: 0, delta: 0 },
];

for (const style of styles) {
  test(`${style} preserves supplied dimension scores without a fabricated /10`, () => {
    const output = render(style, scores);
    assert.deepEqual(dimensionScores(output, style), scores.map(dim => [String(dim.before), String(dim.after)]));
    assert.ok(output.includes(base.skill_name));
    assert.ok(output.includes(base.improvements[0]));
  });

  test(`${style} still renders an empty dimension list`, () => {
    assert.deepEqual(dimensionScores(render(style, []), style), []);
  });
}

for (const style of styles.filter(style => style.endsWith('.html'))) {
  test(`${style} retains HTML escaping for dimension fields`, () => {
    const output = render(style, [{ name: '<b>名称</b>', before: '<i>1</i>', after: '2 & 3', delta: '"4"' }]);
    assert.ok(output.includes('&lt;b&gt;名称&lt;/b&gt;'));
    assert.ok(output.includes('&lt;i&gt;1&lt;/i&gt;'));
    assert.ok(output.includes('2 &amp; 3'));
    assert.ok(output.includes('&quot;4&quot;'));
    assert.ok(!output.includes('<b>名称</b>'));
    assert.ok(!output.includes('<i>1</i>'));
  });
}
