#!/usr/bin/env node

import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { readUpstreamOriginals, verifyUpstreamOriginal } from './upstream-originals.mjs';

const repoRoot = fileURLToPath(new URL('..', import.meta.url));
const names = ['in-your-own-words', 'sharpen'];

function readCommands() {
  const originals = readUpstreamOriginals(repoRoot);
  return Object.fromEntries(names.map(name => {
    const original = originals.get(resolve(repoRoot, 'skills', 'core', name));
    if (!original) throw new Error(`Missing upstream original registration for ${name}`);
    return [name, {
      description: `Run the original pstack ${name} skill on demand`,
      template: verifyUpstreamOriginal(original).toString('utf8'),
      subtask: false,
    }];
  }));
}

function matchesSkill(tool) {
  let pattern = tool.replace(/[.+^${}()|[\]\\]/g, '\\$&').replaceAll('*', '.*').replaceAll('?', '.');
  if (pattern.endsWith(' .*')) pattern = `${pattern.slice(0, -3)}( .*)?`;
  return new RegExp(`^${pattern}$`, process.platform === 'win32' ? 'si' : 's').test('skill');
}

function withManualSkills(permission, { inherited = false } = {}) {
  const result = typeof permission === 'string' ? { '*': permission } : { ...permission };
  const matching = Object.entries(result).filter(([tool]) => matchesSkill(tool));
  if (inherited && matching.length === 0) return permission;

  // Replay the existing order for the skill tool before adding the two denials.
  // Otherwise moving the skill entry past a wildcard can change other skills' access.
  const skill = new Map();
  for (const [, rules] of matching) {
    for (const [pattern, action] of typeof rules === 'string' ? [['*', rules]] : Object.entries(rules)) {
      skill.delete(pattern);
      skill.set(pattern, action);
    }
  }
  const last = [...skill].at(-1);
  if (last?.[0] === '*' && last[1] === 'deny') return permission;
  for (const name of names) {
    skill.delete(name);
    skill.set(name, 'deny');
  }
  delete result.skill;
  result.skill = Object.fromEntries(skill);
  return result;
}

// OpenCode loads this module as a V1 plugin. Its config hook sees the merged
// rules, including per-agent overrides that take precedence over global ones.
export default async function pstackManualSkills() {
  const commands = readCommands();
  return {
    config(config) {
      config.permission = withManualSkills(config.permission);
      for (const agent of Object.values(config.agent ?? {})) {
        if (agent.permission !== undefined) {
          agent.permission = withManualSkills(agent.permission, { inherited: true });
        }
      }
      config.command = { ...config.command, ...commands };
    },
  };
}

function loadInlineConfig() {
  const inline = process.env.OPENCODE_CONFIG_CONTENT;
  if (!inline) return {};

  let config;
  try {
    config = JSON.parse(inline);
  } catch {
    throw new Error('OPENCODE_CONFIG_CONTENT must be JSON for this launcher. Use OPENCODE_CONFIG for a JSONC file.');
  }
  if (!config || typeof config !== 'object' || Array.isArray(config) ||
      (config.plugin !== undefined && !Array.isArray(config.plugin))) {
    throw new Error('OPENCODE_CONFIG_CONTENT must contain an object with an optional plugin array.');
  }
  return config;
}

function run() {
  const binary = process.env.AI_OPENCODE_BIN || (process.platform === 'win32' ? 'opencode.exe' : 'opencode');
  const observed = spawnSync(binary, ['--version'], { encoding: 'utf8', timeout: 10000 });
  if (observed.error || observed.status !== 0) {
    throw new Error(`Cannot detect OpenCode version (${observed.error?.code ?? observed.status}). Set AI_OPENCODE_BIN to the executable path.`);
  }
  const version = observed.stdout.trim();
  if (!/^1\.\d+\.\d+(?:[-+]\S+)?$/.test(version)) {
    throw new Error('The pstack manual adapter requires OpenCode V1. OpenCode V2 can read the original field.');
  }

  readCommands();
  const config = loadInlineConfig();
  config.plugin = [...(config.plugin ?? []).filter(plugin => plugin !== import.meta.url), import.meta.url];
  const child = spawnSync(binary, process.argv.slice(2), {
    env: { ...process.env, OPENCODE_CONFIG_CONTENT: JSON.stringify(config) },
    stdio: 'inherit',
  });
  if (child.error) throw new Error(`Cannot start OpenCode V1 (${child.error.code})`);
  process.exitCode = child.signal === 'SIGINT' ? 130 : child.status ?? 1;
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  try {
    run();
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
