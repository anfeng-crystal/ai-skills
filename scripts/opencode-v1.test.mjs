import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import pstackManualSkills from './opencode-v1.mjs';

test('V1 manual commands load pinned originals and deny model calls in every agent', async () => {
  const config = {
    permission: {
      skill: { sharpen: 'allow', '*': 'allow', 'other-skill': 'ask' },
      '*': 'allow',
      edit: 'ask',
    },
    agent: {
      build: { permission: { skill: 'allow', bash: 'deny' } },
      review: { permission: 'ask' },
    },
    command: { status: { template: 'Show status' } },
  };
  const plugin = await pstackManualSkills();
  plugin.config(config);

  const denied = [['in-your-own-words', 'deny'], ['sharpen', 'deny']];
  for (const permission of [config.permission, config.agent.build.permission, config.agent.review.permission]) {
    assert.equal(Object.keys(permission).at(-1), 'skill');
    assert.deepEqual(Object.entries(permission.skill).slice(-2), denied);
  }
  assert.deepEqual(Object.entries(config.permission.skill).slice(0, -2), [
    ['other-skill', 'ask'],
    ['*', 'allow'],
  ]);
  assert.equal(config.permission.edit, 'ask');
  assert.equal(config.agent.build.permission.bash, 'deny');
  assert.equal(config.agent.review.permission['*'], 'ask');
  assert.equal(config.command.status.template, 'Show status');
  for (const [name] of denied) {
    const source = new URL(`../skills/core/${name}/SKILL.md`, import.meta.url);
    assert.equal(config.command[name].template, readFileSync(source, 'utf8'));
    assert.equal(config.command[name].subtask, false);
  }
});

test('leaves existing blanket denials and unrelated agent rules effective', async () => {
  const permission = { skill: { 'other-skill': 'allow' }, '*': 'deny' };
  const config = {
    permission,
    agent: {
      build: { permission: { bash: 'allow' } },
      review: { permission: { skill: 'allow', 'sk?ll': { 'other-*': 'ask' } } },
    },
  };
  const plugin = await pstackManualSkills();
  plugin.config(config);

  assert.deepEqual(config.permission, permission);
  assert.deepEqual(config.agent.build.permission, { bash: 'allow' });
  assert.deepEqual(Object.entries(config.agent.review.permission.skill), [
    ['*', 'allow'],
    ['other-*', 'ask'],
    ['in-your-own-words', 'deny'],
    ['sharpen', 'deny'],
  ]);
});

test('launcher rejects a non-V1 binary before activating the adapter', () => {
  const result = spawnSync(process.execPath, [fileURLToPath(new URL('./opencode-v1.mjs', import.meta.url))], {
    encoding: 'utf8',
    env: { ...process.env, AI_OPENCODE_BIN: process.execPath },
  });
  assert.equal(result.status, 1, result.stderr);
  assert.match(result.stderr, /requires OpenCode V1/);
});
