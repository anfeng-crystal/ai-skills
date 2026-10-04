import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const source = fileURLToPath(new URL('./search-aggregator.mjs', import.meta.url));

// Every fetch is replaced before loading the CLI; no real key or network is used.
function run(args, { responses = {}, env = {} } = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'web search 测试 '));
  try {
    const script = path.join(root, 'search-aggregator.mjs');
    const preload = path.join(root, 'fetch-stub.mjs');
    const calls = path.join(root, 'calls.jsonl');
    fs.copyFileSync(source, script);
    fs.writeFileSync(preload, `
      import fs from 'node:fs';
      const responses = JSON.parse(process.env.TEST_RESPONSES);
      globalThis.fetch = async (url) => {
        const host = new URL(url).hostname;
        fs.appendFileSync(process.env.TEST_CALLS, JSON.stringify(host) + '\\n');
        if (!(host in responses)) throw new Error('Unexpected backend');
        const value = responses[host];
        return { ok: true, json: async () => value, text: async () => value };
      };
    `);
    fs.writeFileSync(path.join(root, 'brave-search.mjs'), `
      import fs from 'node:fs';
      fs.appendFileSync(process.env.TEST_CALLS, JSON.stringify('brave-stub') + '\\n');
      console.log(JSON.stringify({ results: [{ title: 'Brave result', url: 'https://example.com/brave' }] }));
    `);
    const result = spawnSync(process.execPath, ['--import', preload, script, ...args], {
      env: {
        ...process.env,
        BRAVE_SEARCH_API_KEY: '', TAVILY_API_KEY: '', GOOGLE_CSE_API_KEY: '',
        GOOGLE_CSE_ID: '', BING_API_KEY: '', SERPAPI_KEY: '',
        TEST_RESPONSES: JSON.stringify(responses), TEST_CALLS: calls, ...env,
      },
      encoding: 'utf8', timeout: 5000,
    });
    return {
      ...result,
      calls: fs.existsSync(calls) ? fs.readFileSync(calls, 'utf8').trim().split('\n').map(JSON.parse) : [],
    };
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

test('help exits without querying a backend', () => {
  const result = run(['--help']);
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /Usage:/);
  assert.deepEqual(result.calls, []);
});

for (const args of [
  ['query', '--count'], ['query', '--count', '0'], ['query', '--count', '-1'],
  ['query', '--count', '1.5'], ['query', '--count', 'NaN'], ['query', '--backend'],
  ['query', '--backend', 'toString'], ['query', '--backend', '__proto__'],
  ['query', '--preset', 'invalid'], ['query', '--unknown'], ['query', 'unexpected'],
]) {
  test(`invalid arguments fail before requests: ${args.join(' ')}`, () => {
    const result = run(args);
    assert.equal(result.status, 1, result.stderr);
    assert.deepEqual(result.calls, []);
  });
}

test('successful structured results retain the existing output shape and stop fallback', () => {
  const result = run(['query', '--json', '--count', '1'], {
    env: { TAVILY_API_KEY: 'test-only' },
    responses: { 'api.tavily.com': { results: [
      { title: 'First', url: 'https://example.com/1', content: 'First summary' },
      { title: 'Second', url: 'https://example.com/2', content: 'Second summary' },
    ] } },
  });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), {
    ok: true, source: 'tavily', results: { query: 'query', answer: null, results: [
      { title: 'First', url: 'https://example.com/1', description: 'First summary' },
    ] },
  });
  assert.deepEqual(result.calls, ['api.tavily.com']);
});

test('empty structured results continue to the next backend', () => {
  const result = run(['query', '--json'], {
    env: { TAVILY_API_KEY: 'test-only' },
    responses: {
      'api.tavily.com': { results: [] },
      'html.duckduckgo.com': '<a class="result__a" href="https://example.com">Fallback result</a>',
    },
  });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).source, 'duckduckgo');
  assert.deepEqual(result.calls, ['api.tavily.com', 'html.duckduckgo.com']);
});

test('explicit backend with empty results reports failure without expanding scope', () => {
  const result = run(['query', '--backend', 'tavily', '--json'], {
    env: { TAVILY_API_KEY: 'test-only' }, responses: { 'api.tavily.com': { results: [] } },
  });
  assert.equal(result.status, 2, result.stderr);
  assert.equal(JSON.parse(result.stdout).ok, false);
  assert.deepEqual(result.calls, ['api.tavily.com']);
});

test('Brave subprocess works from paths containing spaces and Unicode', () => {
  const result = run(['query', '--backend', 'brave', '--json'], { env: { BRAVE_SEARCH_API_KEY: 'test-only' } });
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).source, 'brave');
  assert.deepEqual(result.calls, ['brave-stub']);
});
