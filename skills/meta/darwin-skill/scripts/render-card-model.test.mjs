import assert from 'node:assert/strict';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const root = process.env.DARWIN_CARD_TEST_ROOT || fileURLToPath(new URL('..', import.meta.url));
const python = process.env.PYTHON || (process.platform === 'win32' ? 'python' : 'python3');
const base = { skill_name: '示例 Skill', score_before: '85', score_after: '91', score_delta: '6',
  date: '2026-10-05', dimensions: [], improvements: ['保留能力'], test_results: [] };
const templates = ['minimal.md', 'tech.html', 'business.html'];

function render(template, data) {
  const result = spawnSync(python, [path.join(root, 'scripts/render-result-card.py'),
    path.join(root, `templates/result-card-${template}.template`), JSON.stringify(data)], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr);
  return result.stdout;
}

function escaped(value) {
  return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#x27;');
}

for (const template of templates) {
  for (const [label, extra, expected] of [
    ['actual recorded models', { model_set: 'offline-A / offline-B' }, 'offline-A / offline-B'],
    ['missing model', {}, '-'],
    ['null model', { model_set: null }, '-'],
    ['empty model', { model_set: '' }, '-'],
    ['blank model', { model_set: ' \t\n' }, '-'],
    ['literal special characters', { model_set: '<model>&"\' ${unknown}' }, '<model>&"\' ${unknown}'],
  ]) {
    test(`${template} reports ${label} without inventing an evaluator`, () => {
      const output = render(template, { ...base, ...extra });
      const value = template.endsWith('.md') ? expected : escaped(expected);
      const field = template === 'minimal.md' ? `**评估模型**: ${value}`
        : template === 'tech.html' ? `<span>评估模型: ${value}</span>` : `<span>${value}</span>`;
      assert.ok(output.includes(field), `Missing model field: ${field}`);
      assert.ok(!output.includes('Claude Opus 4.7'));
      assert.ok(output.includes(base.skill_name));
      assert.ok(output.includes(base.date));
      assert.ok(output.includes(base.improvements[0]));
    });
  }
}

test('optional model metadata does not alter the gated card', () => {
  assert.equal(render('gated.html', base), render('gated.html', { ...base, model_set: 'offline-A' }));
});
