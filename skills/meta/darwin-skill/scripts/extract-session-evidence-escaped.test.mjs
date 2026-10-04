import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const script = process.env.EXTRACT_SESSION_EVIDENCE_SCRIPT
  || fileURLToPath(new URL('./extract-session-evidence.mjs', import.meta.url));
const ordinary = '后续普通正文 ordinary words';
const jsonSecret = (field, value) => `前文 ${JSON.stringify({ [field]: value, note: 'keep ordinary text' })} 后文`;
const jsonExpected = (field) => `前文 {"${field}=<redacted>,"note":"keep ordinary text"} 后文`;
const cases = [
  ['JSON password with escaped quote', jsonSecret('password', 'PREFIX"SYNTHETIC_TAIL'), jsonExpected('password')],
  ['JSON access token with escaped quote', jsonSecret('access_token', 'PREFIX"SYNTHETIC_TOKEN_TAIL'), jsonExpected('access_token')],
  ['JSON prefixed password with escaped quote', jsonSecret('DB_PASSWORD', 'PREFIX"SYNTHETIC_DB_TAIL'), jsonExpected('DB_PASSWORD')],
  ['JSON quotes surrounding punctuation', jsonSecret('refresh_token', 'PREFIX", ; : = SYNTHETIC_TAIL"END'), jsonExpected('refresh_token')],
  ['JSON repeated escaped quotes', jsonSecret('api_key', 'PREFIX"MIDDLE"SYNTHETIC_TAIL'), jsonExpected('api_key')],
  ['JSON backslash before escaped quote', jsonSecret('secret', 'PREFIX\\"SYNTHETIC_TAIL'), jsonExpected('secret')],
  ['JSON double backslash before escaped quote', jsonSecret('token', 'PREFIX\\\\"SYNTHETIC_TAIL'), jsonExpected('token')],
  ['single-quoted escaped quote', "前文 secret='PREFIX\\'SYNTHETIC_TAIL' note=keep 后文", '前文 secret=<redacted> note=keep 后文'],
  ['single-quoted backslash and escaped quote', "前文 api-key='PREFIX\\\\\\'SYNTHETIC_TAIL' note=keep 后文", '前文 api-key=<redacted> note=keep 后文'],
  ['plain JSON control', jsonSecret('password', 'SYNTHETIC_SIMPLE'), jsonExpected('password')],
  ['JSON backslash control', jsonSecret('password', 'PREFIX\\SYNTHETIC_BACKSLASH'), jsonExpected('password')],
  ['JSON trailing backslash control', jsonSecret('token', 'SYNTHETIC_TRAILING\\'), jsonExpected('token')],
  ['JSON empty quoted control', jsonSecret('secret', ''), jsonExpected('secret')],
  ['ordinary single-quoted control', "前文 secret='SYNTHETIC_SIMPLE' note=keep 后文", '前文 secret=<redacted> note=keep 后文'],
  ['single-quoted escaped backslash control', "前文 secret='PREFIX\\\\SYNTHETIC_BACKSLASH' note=keep 后文", '前文 secret=<redacted> note=keep 后文'],
  ['unquoted control', '前文 password=SYNTHETIC_UNQUOTED; note=keep 后文', '前文 password=<redacted>; note=keep 后文'],
  ['header controls', 'Authorization: Bearer SYNTHETIC_HEADER\nCookie: sid=SYNTHETIC_COOKIE; tenant=SYNTHETIC_TENANT\n普通正文', 'Authorization=<redacted>\nCookie=<redacted>\n普通正文'],
  ['ordinary quoted text control', '前文 "ordinary\\\" words" and \'other\\\' words\' 后文', '前文 "ordinary\\\" words" and \'other\\\' words\' 后文'],
];

for (const [name, input, expected] of cases) {
  for (const format of ['json', 'jsonl']) {
    test(`${name} keeps whole-value redaction and surrounding text in ${format}`, (t) => {
      const root = fs.mkdtempSync(path.join(os.tmpdir(), 'session-evidence-escaped-'));
      t.after(() => fs.rmSync(root, { recursive: true, force: true }));
      const meta = { id: 'synthetic-session', session_id: 'synthetic-session', thread_source: 'user', timestamp: '2026-10-05T00:00:00Z' };
      const records = [{ type: 'session_meta', payload: meta }];
      for (const [role, text] of [['assistant', input], ['user', input], ['user', ordinary]]) {
        records.push({ type: 'response_item', payload: { type: 'message', role,
          content: [{ type: role === 'user' ? 'input_text' : 'output_text', text }] } });
      }
      fs.writeFileSync(path.join(root, 'synthetic.jsonl'), records.map(JSON.stringify).join('\n') + '\n');
      const result = spawnSync(process.execPath, [script, '--root', root, '--all-user-messages', '--format', format], {
        encoding: 'utf8', timeout: 10000,
      });
      assert.ifError(result.error);
      assert.equal(result.status, 0, result.stderr);
      assert.equal(result.stderr, '');
      const report = format === 'json' ? JSON.parse(result.stdout) : null;
      const candidates = report ? report.candidates : result.stdout.trim().split('\n').map(line => JSON.parse(line));
      if (report) {
        assert.deepEqual(report.errors, []);
        assert.equal(report.stats.userMessages, 2);
        assert.equal(report.stats.candidateMessages, 2);
      }
      assert.equal(candidates.length, 2);
      assert.equal(candidates[0].userText, expected);
      assert.equal(candidates[0].previousAssistantText, expected);
      assert.equal(candidates[1].userText, ordinary);
      assert.equal(candidates[1].previousAssistantText, expected);
      assert.deepEqual(candidates.map(c => c.sourceLine), [3, 4]);
      assert.deepEqual(candidates.map(c => c.userMessageIndex), [1, 2]);
      for (const candidate of candidates) {
        assert.equal(candidate.sourceFile, 'synthetic.jsonl');
        assert.equal(candidate.sessionId, meta.id);
        assert.equal(candidate.rolloutId, meta.id);
        assert.equal(candidate.sessionTimestamp, meta.timestamp);
        assert.equal(candidate.root, 'active');
        assert.equal(candidate.evidenceStatus, 'candidate_requires_context_review');
      }
      assert.ok(!result.stdout.includes('SYNTHETIC_'), 'synthetic secret tail leaked');
    });
  }
}
