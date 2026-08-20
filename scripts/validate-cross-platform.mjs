#!/usr/bin/env node
/**
 * 跨平台 SKILL.md 验证脚本
 *
 * 按 Agent Skills 公共规范检查 frontmatter，并验证本仓库的跨平台 header 与 body 完整性。
 * 用法: node scripts/validate-cross-platform.mjs
 */

import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import { resolve, join, basename } from 'node:path';

const SKILLS_ROOT = resolve(import.meta.dirname, '..', 'skills');

let total = 0;
let passed = 0;
let failed = 0;
const errors = [];

function findSkills() {
  const skills = [];
  // Scan skills/ subdirectories
  for (const category of readdirSync(SKILLS_ROOT)) {
    const catDir = join(SKILLS_ROOT, category);
    if (!statSync(catDir).isDirectory() || category.startsWith('.')) continue;
    for (const name of readdirSync(catDir)) {
      const skillDir = join(catDir, name);
      const skillMd = join(skillDir, 'SKILL.md');
      if (statSync(skillDir).isDirectory() && existsSync(skillMd)) {
        skills.push({ name, path: skillMd, dir: skillDir });
      }
    }
  }
  return skills;
}

function detectType(skillDir) {
  const hasScripts = existsSync(join(skillDir, 'scripts')) || existsSync(join(skillDir, 'bin'));
  const hasAgents = existsSync(join(skillDir, 'agents'));
  if (hasScripts) return 'script';
  if (hasAgents) return 'multi-platform';
  return 'doc';
}

function topLevelScalar(frontmatter, key) {
  const match = frontmatter.match(new RegExp(`^${key}:\\s*(.+?)\\s*$`, 'm'));
  if (!match) return null;
  const value = match[1].trim();
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

function isStringScalar(rawValue) {
  const value = rawValue.trim();
  if (!value || value.startsWith('[') || value.startsWith('{') || value === '|' || value === '>') {
    return false;
  }
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return true;
  }
  return !/^(?:true|false|null|~|[-+]?\d+(?:\.\d+)?)$/i.test(value);
}

function check(skill) {
  const issues = [];
  const content = readFileSync(skill.path, 'utf8').replace(/\r\n/g, '\n');
  const type = detectType(skill.dir);

  // 1. Public Agent Skills frontmatter
  const fmMatch = content.match(/^---\n([\s\S]*?)\n---(?:\n|$)/);
  if (!fmMatch) {
    issues.push('Missing YAML frontmatter (--- delimiters)');
    return { issues, type };
  }
  const fmText = fmMatch[1];

  const name = topLevelScalar(fmText, 'name');
  if (!name) {
    issues.push('Missing "name" field in frontmatter');
  } else {
    if (name.length > 64 || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name)) {
      issues.push('"name" must be 1-64 lowercase kebab-case characters');
    }
    if (name !== basename(skill.dir)) {
      issues.push(`"name" must match directory name "${basename(skill.dir)}"`);
    }
  }

  const description = topLevelScalar(fmText, 'description');
  if (!description) {
    issues.push('Missing "description" field in frontmatter');
  } else if (description.length > 1024) {
    issues.push('"description" exceeds 1024 characters');
  }

  const license = topLevelScalar(fmText, 'license');
  if (/^license:/m.test(fmText) && !license) {
    issues.push('"license" must be a non-empty string when present');
  }

  const compatibility = topLevelScalar(fmText, 'compatibility');
  if (compatibility && compatibility.length > 500) {
    issues.push('"compatibility" exceeds 500 characters');
  }

  // Agent Skills metadata is optional, but when present it must be string-to-string.
  const fmLines = fmText.split('\n');
  const metadataIndex = fmLines.findIndex((line) => line === 'metadata:');
  if (metadataIndex >= 0) {
    const metadataLines = [];
    for (let i = metadataIndex + 1; i < fmLines.length; i++) {
      const line = fmLines[i];
      if (/^\S/.test(line)) break;
      if (line.trim()) metadataLines.push(line);
    }
    if (metadataLines.length === 0) {
      issues.push('"metadata" must contain at least one string entry');
    }
    for (const line of metadataLines) {
      if (/^(?: {4,}|\t)/.test(line)) {
        issues.push('"metadata" must not contain nested mappings');
        continue;
      }
      const entry = line.match(/^  ([A-Za-z0-9_.-]+):\s*(.+?)\s*$/);
      if (!entry || !isStringScalar(entry[2])) {
        issues.push('"metadata" values must be YAML strings');
      }
    }
  }

  // Host-specific extensions do not belong in the portable public core.
  for (const key of [
    'argument-hint',
    'disable-model-invocation',
    'user-invocable',
    'context',
    'agent',
    'model',
    'effort',
    'hooks',
    'paths',
    'shell',
  ]) {
    if (new RegExp(`^${key}:`, 'm').test(fmText)) {
      issues.push(`Host-specific top-level field "${key}" is not portable`);
    }
  }

  // 2. Local portability and body checks
  if (type !== 'doc' && !content.includes('Cross-platform Agent Skill')) {
    issues.push('Missing cross-platform header blockquote (required for script/multi-platform skills)');
  }

  if (!content.match(/^# .+$/m)) {
    issues.push('Missing H1 heading');
  }

  return { issues, type };
}

// Main
const skills = findSkills();
console.log(`Validating ${skills.length} skills...\n`);

for (const skill of skills.sort((a, b) => a.name.localeCompare(b.name))) {
  total++;
  const { issues, type } = check(skill);
  const typeTag = type === 'doc' ? '' : ` [${type}]`;
  if (issues.length === 0) {
    passed++;
    console.log(`  PASS  ${skill.name}${typeTag}`);
  } else {
    failed++;
    console.log(`  FAIL  ${skill.name}${typeTag}`);
    for (const issue of issues) {
      console.log(`        - ${issue}`);
    }
    errors.push({ name: skill.name, issues });
  }
}

console.log(`\n--- Summary ---`);
console.log(`Total: ${total}  Passed: ${passed}  Failed: ${failed}`);
if (failed === 0) {
  console.log('All skills pass cross-platform validation!');
} else {
  console.log(`${failed} skill(s) need attention.`);
  process.exit(1);
}
