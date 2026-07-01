#!/usr/bin/env node
/**
 * 跨平台 SKILL.md 验证脚本
 *
 * 检查所有 skill 的 frontmatter 结构、跨平台 header、body 完整性。
 * 用法: node scripts/validate-cross-platform.mjs
 */

import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import { resolve, join, basename } from 'node:path';

const SKILLS_ROOT = resolve(import.meta.dirname, '..', 'skills');
const NEAT_FREAK = resolve(import.meta.dirname, '..', 'neat-freak');

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
  // Add neat-freak
  const neatMd = join(NEAT_FREAK, 'SKILL.md');
  if (existsSync(neatMd)) {
    skills.push({ name: 'neat-freak', path: neatMd, dir: NEAT_FREAK });
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

function check(skill) {
  const issues = [];
  const content = readFileSync(skill.path, 'utf8');
  const type = detectType(skill.dir);

  // 1. Frontmatter exists (all types)
  const fmMatch = content.match(/^---\n([\s\S]*?)\n---/);
  if (!fmMatch) {
    issues.push('Missing YAML frontmatter (--- delimiters)');
    return issues;
  }
  const fmText = fmMatch[1];

  // 2. name field (all types)
  if (!fmText.match(/^name:\s/m)) {
    issues.push('Missing "name" field in frontmatter');
  }

  // 3. description field (all types)
  if (!fmText.match(/^description:\s/m)) {
    issues.push('Missing "description" field in frontmatter');
  }

  // 4. metadata block (required for script/multi-platform, optional for doc)
  if (!fmText.match(/^metadata:\s/m)) {
    if (type !== 'doc') {
      issues.push(`Missing "metadata" block (required for ${type} skills)`);
    }
  } else {
    const metaMatch = fmText.match(/metadata:\n([\s\S]*?)(?=\n\S|\n---|$)/);
    if (metaMatch) {
      const metaText = metaMatch[1];
      if (!metaText.match(/author:\s/m)) issues.push('metadata missing "author"');
      if (!metaText.match(/version:\s/m)) issues.push('metadata missing "version"');
      if (!metaText.match(/license:\s/m)) issues.push('metadata missing "license"');
      if (!metaText.match(/tags:\s/m)) issues.push('metadata missing "tags"');
    }
  }

  // 5. No stray top-level version/author/tags outside metadata
  const lines = fmText.split('\n');
  let inMetadata = false;
  for (const line of lines) {
    if (line.match(/^metadata:\s/)) { inMetadata = true; continue; }
    if (line.match(/^\S/) && !line.match(/^---/)) inMetadata = false;
    if (!inMetadata) {
      if (line.match(/^version:\s/)) issues.push('Stray top-level "version" outside metadata');
      if (line.match(/^author:\s/)) issues.push('Stray top-level "author" outside metadata');
      if (line.match(/^tags:\s/)) issues.push('Stray top-level "tags" outside metadata');
      if (line.match(/^argument-hint:\s/)) issues.push('Stray top-level "argument-hint" (should be in metadata.platforms)');
      if (line.match(/^allowed-tools:\s/)) issues.push('Stray top-level "allowed-tools" (should be in metadata.platforms)');
    }
  }

  // 6. Cross-platform header (required for script/multi-platform, skipped for doc)
  if (type !== 'doc' && !content.includes('Cross-platform Agent Skill')) {
    issues.push('Missing cross-platform header blockquote (required for script/multi-platform skills)');
  }

  // 7. H1 exists (all types)
  if (!content.match(/^# .+$/m)) {
    issues.push('Missing H1 heading');
  }

  // 8. Special: review-code H1 should be "# Review Code"
  if (skill.name === 'review-code' && content.match(/^# Code Review$/m)) {
    issues.push('H1 should be "# Review Code" not "# Code Review"');
  }

  // 9. Special: kingdee-cosmic-login should have platforms in metadata
  if (skill.name === 'kingdee-cosmic-login') {
    if (!content.includes('platforms:')) {
      issues.push('kingdee-cosmic-login missing metadata.platforms');
    }
    if (!content.includes('argument-hint:')) {
      issues.push('kingdee-cosmic-login missing argument-hint in platforms');
    }
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
