import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';

const script = process.env.DARWIN_SCREENSHOT_TEST_TARGET || fileURLToPath(new URL('./screenshot.mjs', import.meta.url));

function fixture(t) {
  const dir = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'darwin-shot-')));
  t.after(() => fs.rmSync(dir, { recursive: true, force: true }));
  const calls = path.join(dir, 'calls.jsonl');
  const module = path.join(dir, 'fake-playwright.cjs');
  fs.writeFileSync(module, `
    const fs = require('node:fs');
    const record = (kind, value) => fs.appendFileSync(process.env.SHOT_CALLS, JSON.stringify({kind, value})+'\\n');
    module.exports = {chromium: {launch: async options => {
      record('launch', options);
      return {
        newContext: async options => {
          record('context', options);
          return {newPage: async () => ({
            goto: async (url, options) => {record('goto', {url, options}); if(process.env.SHOT_FAIL) throw Error('fixture navigation failure');},
            evaluate: async () => {}, waitForTimeout: async () => {},
            locator: selector => {record('selector', selector); return {screenshot: async options => record('screenshot', options)};}
          })};
        },
        close: async () => record('close', true)
      };
    }}};
  `);
  return {dir, calls, module};
}

function run(f, args=[], extraEnv={}) {
  const result = spawnSync(process.execPath, [script, ...args], {cwd:f.dir, encoding:'utf8',
    env: {...process.env, DARWIN_PLAYWRIGHT_CANDIDATES:f.module, DARWIN_BROWSER_CHANNEL:'',
      DARWIN_BROWSER_EXECUTABLE:'', SHOT_CALLS:f.calls, SHOT_FAIL:'', ...extraEnv}});
  return {...result, calls:fs.existsSync(f.calls) ? fs.readFileSync(f.calls,'utf8').trim().split('\n').map(JSON.parse) : []};
}

test('default screenshot writes a task artifact without overwriting the skill template', t => {
  const f=fixture(t); const r=run(f);
  assert.equal(r.status,0,r.stderr);
  assert.equal(r.calls.find(x=>x.kind==='screenshot').value.path,path.join(f.dir,'result-card.png'));
  assert.equal(r.calls.filter(x=>x.kind==='close').length,1);
  assert.deepEqual(r.calls.find(x=>x.kind==='context').value,{viewport:{width:920,height:1600},deviceScaleFactor:2});
  assert.equal(r.calls.find(x=>x.kind==='selector').value,'.card');
});

test('relative HTML and reserved path characters use a proper file URL', t => {
  const f=fixture(t);const filename='报告 # 100%.html';fs.writeFileSync(path.join(f.dir,filename),'<div class="card">fixture</div>');
  const r=run(f,[filename,'output.png']);
  assert.equal(r.status,0,r.stderr);
  assert.equal(r.calls.find(x=>x.kind==='goto').value.url,pathToFileURL(path.join(f.dir,filename)).href);
  assert.equal(r.calls.find(x=>x.kind==='screenshot').value.path,path.join(f.dir,'output.png'));
});

test('existing browser channel or executable can be explicitly selected', t => {
  const f=fixture(t);let r=run(f,[],{DARWIN_BROWSER_CHANNEL:'chrome'});
  assert.equal(r.status,0,r.stderr);
  assert.deepEqual(r.calls.find(x=>x.kind==='launch').value,{channel:'chrome'});
  fs.unlinkSync(f.calls);
  r=run(f,[],{DARWIN_BROWSER_CHANNEL:'chrome',DARWIN_BROWSER_EXECUTABLE:'/fixture/browser'});
  assert.equal(r.status,0,r.stderr);
  assert.deepEqual(r.calls.find(x=>x.kind==='launch').value,{executablePath:'/fixture/browser'});
});

test('failed navigation closes the browser and returns failure', t => {
  const f=fixture(t);const r=run(f,[],{SHOT_FAIL:'1'});
  assert.equal(r.status,1);
  assert.match(r.stderr,/fixture navigation failure/);
  assert.equal(r.calls.filter(x=>x.kind==='close').length,1);
  assert.ok(!r.calls.some(x=>x.kind==='screenshot'));
});

test('help and excess positional arguments do not launch a browser', t => {
  const f=fixture(t);let r=run(f,['--help']);
  assert.equal(r.status,0,r.stderr);
  assert.match(r.stdout,/Usage:/);
  assert.deepEqual(r.calls,[]);
  if(fs.existsSync(f.calls))fs.unlinkSync(f.calls);
  r=run(f,['a','b','c']);
  assert.equal(r.status,1);
  assert.deepEqual(r.calls,[]);
});
