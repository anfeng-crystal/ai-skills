import assert from 'node:assert/strict';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = process.env.DARWIN_CARD_TEST_ROOT || fileURLToPath(new URL('..', import.meta.url));
const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const styles = ['minimal.md', 'tech.html', 'business.html', 'gated.html'];
const base = { skill_name: '增量展示', score_before: 10, score_after: 11,
  date: '2026-10-05', improvements: ['保持实际增量'], test_results: [] };

function render(style, delta) {
  const data = { ...base, score_delta: delta,
    dimensions: [{ name: '实际维度', before: 20, after: 21, delta }] };
  const result = spawnSync(python, [path.join(root, 'scripts/render-result-card.py'),
    path.join(root, `templates/result-card-${style}.template`), JSON.stringify(data)], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout;
}

function escape(value) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#x27;');
}

// Before/after deliberately differ by 1. The renderer must display the supplied
// delta and must not calculate, round, or invent a score from those other fields.
const cases = [
  ['positive number', 2, '+2'],
  ['negative number', -2, '-2'],
  ['zero number', 0, '0'],
  ['decimal precision', '2.50', '+2.50'],
  ['explicit positive sign', '+2.50', '+2.50'],
  ['explicit negative sign', '-2.50', '-2.50'],
  ['explicit positive zero', '+0', '+0'],
  ['explicit negative zero', '-0', '-0'],
  ['decimal zero', '0.00', '0.00'],
  ['scientific notation', '2e-3', '+2e-3'],
  ['unscored marker', '-', '-'],
  ['unscored wording', '未评分', '未评分'],
  ['literal unsafe text', '<script>"&\'${unknown}</script>', '<script>"&\'${unknown}</script>'],
];

for (const style of styles) {
  for (const [label, delta, expected] of cases) {
    test(`${style} displays ${label} without inventing a second sign`, () => {
      const output = render(style, delta);
      const value = style === 'minimal.md' ? expected : escape(expected);
      const total = style === 'minimal.md' ? `→  Δ ${value}\n`
        : style === 'tech.html' ? `<span class="delta">${value}</span>`
          : style === 'business.html' ? `<div class="score delta">${value}</div>`
            : `<strong data-field="score-delta">${value}</strong>`;
      const dimension = style === 'minimal.md' ? `| 实际维度 | 20 | 21 | ${value} |`
        : `<td class="delta-cell">${value}</td>`;
      assert.ok(output.includes(total), `Missing supplied total delta: ${total}`);
      assert.ok(output.includes(dimension), `Missing supplied dimension delta: ${dimension}`);
      assert.ok(output.includes(base.improvements[0]));
      if (style !== 'minimal.md' && typeof delta === 'string' && delta.includes('<script>')) {
        assert.ok(!output.includes(delta), 'HTML values must remain escaped');
      }
    });
  }
}

test('tech card does not add a second sign through generated CSS content', () => {
  const addsSign = /\.delta::before\s*\{[^}]*content:\s*['"]\+['"]/.test(render('tech.html', -2));
  assert.equal(addsSign, false, 'The total delta already includes its display sign');
});
