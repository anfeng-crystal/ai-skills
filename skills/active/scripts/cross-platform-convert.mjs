#!/usr/bin/env node
/**
 * 跨平台 SKILL.md 转换脚本
 *
 * 用法:
 *   node scripts/cross-platform-convert.mjs <skill-dir> [options]
 *
 * 选项:
 *   --header-only    仅插入跨平台 header，不改 frontmatter
 *   --tags <json>    指定 tags 数组，如 '["kingdee","cosmic"]'
 *   --dry-run        预览变更，不写入文件
 *   --no-backup      不创建 .bak 备份
 */

import { readFileSync, writeFileSync, copyFileSync, existsSync } from 'node:fs';
import { resolve, basename } from 'node:path';

const HEADER_BLOCK = '> **Cross-platform Agent Skill** — Claude Code · OpenAI Codex · OpenCode · OpenClaw 通用。\n> 跨平台 SKILL.md，遵循开放 Agent Skill 规范。';

function parseArgs(argv) {
  const args = argv.slice(2);
  const opts = { headerOnly: false, tags: null, dryRun: false, noBackup: false, skillDir: null };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--header-only') opts.headerOnly = true;
    else if (args[i] === '--tags') opts.tags = JSON.parse(args[++i]);
    else if (args[i] === '--dry-run') opts.dryRun = true;
    else if (args[i] === '--no-backup') opts.noBackup = true;
    else if (!args[i].startsWith('--')) opts.skillDir = args[i];
  }
  return opts;
}

function parseFrontmatter(content) {
  const match = content.match(/^---\n([\s\S]*?)\n---/);
  if (!match) return { raw: '', body: content, data: {} };
  const raw = match[0];
  const fmText = match[1];
  const body = content.slice(raw.length);
  const data = {};
  let currentKey = null;
  let inMetadata = false;
  let metadataIndent = 0;

  for (const line of fmText.split('\n')) {
    const topMatch = line.match(/^(\w[\w-]*):\s*(.*)/);
    const indentedMatch = line.match(/^(\s+)(\w[\w-]*):\s*(.*)/);

    if (topMatch && !indentedMatch) {
      const [, key, val] = topMatch;
      if (key === 'metadata') {
        inMetadata = true;
        metadataIndent = line.length - line.trimStart().length;
        data.metadata = {};
        continue;
      }
      inMetadata = false;
      currentKey = key;
      if (key === 'tags' && val.startsWith('[')) {
        data.tags = parseInlineArray(val);
      } else if (val === '' || val === '""' || val === "''") {
        data[key] = '';
      } else {
        data[key] = val.replace(/^["']|["']$/g, '');
      }
    } else if (indentedMatch && inMetadata) {
      const [, indent, key, val] = indentedMatch;
      if (key === 'tags' && val.startsWith('[')) {
        data.metadata.tags = parseInlineArray(val);
      } else if (key === 'platforms') {
        data.metadata.platforms = {};
        currentKey = 'platforms';
      } else if (currentKey === 'platforms' && indent.trimStart().length > metadataIndent) {
        // nested under platforms
        if (!data.metadata.platforms) data.metadata.platforms = {};
        const parentKey = Object.keys(data.metadata.platforms).pop();
        if (parentKey && !data.metadata.platforms[parentKey]) {
          data.metadata.platforms[parentKey] = {};
        }
        // simple key: value under a platform
        const parent = data.metadata.platforms[parentKey] || data.metadata.platforms;
        parent[key] = val.replace(/^["']|["']$/g, '');
      } else {
        data.metadata[key] = val.replace(/^["']|["']$/g, '');
      }
    }
  }
  return { raw, body, data };
}

function parseInlineArray(str) {
  return str.replace(/[\[\]]/g, '').split(',').map(s => s.trim().replace(/^["']|["']$/g, ''));
}

function buildFrontmatter(data) {
  const lines = ['---'];
  lines.push(`name: ${data.name}`);
  // description: preserve original format (may be multiline or quoted)
  if (data.descriptionQuoted) {
    lines.push(`description: "${data.descriptionQuoted}"`);
  } else {
    lines.push(`description: ${data.description}`);
  }

  const meta = data.metadata || {};
  lines.push('metadata:');
  lines.push(`  author: ${meta.author || 'anfeng'}`);
  lines.push(`  version: "${meta.version || '1.0.0'}"`);
  lines.push(`  license: ${meta.license || 'MIT'}`);
  lines.push(`  tags: [${(meta.tags || []).join(', ')}]`);

  // platforms (kingdee-cosmic-login specific)
  if (meta.platforms) {
    lines.push('  platforms:');
    for (const [platform, config] of Object.entries(meta.platforms)) {
      lines.push(`    ${platform}:`);
      for (const [k, v] of Object.entries(config)) {
        lines.push(`      ${k}: "${v}"`);
      }
    }
  }

  lines.push('---');
  return lines.join('\n');
}

function insertHeader(body) {
  // Find the first H1 line and insert header after it (with blank line before header)
  const lines = body.split('\n');
  let inserted = false;
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].startsWith('# ') && !inserted) {
      // Insert blank line + header block after H1
      lines.splice(i + 1, 0, '', HEADER_BLOCK);
      inserted = true;
      break;
    }
  }
  return lines.join('\n');
}

function processSkill(skillDir, opts) {
  const skillMd = resolve(skillDir, 'SKILL.md');
  if (!existsSync(skillMd)) {
    console.error(`  SKIP: ${skillMd} not found`);
    return false;
  }

  const content = readFileSync(skillMd, 'utf8');
  const { raw, body, data } = parseFrontmatter(content);
  const skillName = data.name || basename(skillDir);

  // Backup
  if (!opts.noBackup && !opts.dryRun) {
    copyFileSync(skillMd, skillMd + '.bak');
  }

  if (opts.headerOnly) {
    // Just insert header after H1, don't touch frontmatter
    if (content.includes('Cross-platform Agent Skill')) {
      console.log(`  ${skillName}: header already present, skipping`);
      return true;
    }
    const newContent = content.replace(/^(# .+)$/m, `$1\n\n${HEADER_BLOCK}`);
    if (newContent === content) {
      console.log(`  ${skillName}: no H1 found, skipping`);
      return true;
    }
    if (opts.dryRun) {
      console.log(`  ${skillName}: would insert header`);
    } else {
      writeFileSync(skillMd, newContent);
      console.log(`  ${skillName}: header inserted`);
    }
    return true;
  }

  // Full conversion
  // Preserve description format
  const descRaw = content.match(/description:\s*(.*)/)?.[1] || '';
  const isQuoted = descRaw.startsWith('"') || descRaw.startsWith("'");

  // Build new frontmatter
  // Auto-generate tags from skill name if none provided and none in existing metadata
  const existingTags = opts.tags || data.metadata?.tags || data.tags;
  const autoTags = existingTags?.length ? existingTags : skillName.split('-').filter(Boolean);

  const fmData = {
    name: skillName,
    description: data.description,
    descriptionQuoted: isQuoted ? data.description : null,
    metadata: {
      author: 'anfeng',
      version: '1.0.0',
      license: 'MIT',
      tags: autoTags,
    },
  };

  // Handle kingdee-cosmic-login: move argument-hint/allowed-tools into platforms
  if (data['argument-hint'] || data['allowed-tools']) {
    fmData.metadata.platforms = {
      'claude-code': {
        'argument-hint': data['argument-hint'] || '',
        'allowed-tools': data['allowed-tools'] || '',
      },
    };
  }

  // Handle H1 fix for review-code
  let bodyContent = body;
  if (skillName === 'review-code') {
    bodyContent = bodyContent.replace(/^# Code Review/m, '# Review Code');
  }

  // Insert cross-platform header (skip if already present)
  if (!bodyContent.includes('Cross-platform Agent Skill')) {
    bodyContent = insertHeader(bodyContent);
  }

  // Reconstruct file (body already starts with \n\n after frontmatter)
  const newContent = buildFrontmatter(fmData) + bodyContent;

  if (opts.dryRun) {
    console.log(`  ${skillName}: would convert`);
    console.log(`    frontmatter keys: ${Object.keys(fmData).join(', ')}`);
    if (fmData.metadata.platforms) console.log(`    platforms: ${JSON.stringify(fmData.metadata.platforms)}`);
  } else {
    writeFileSync(skillMd, newContent);
    console.log(`  ${skillName}: converted`);
  }
  return true;
}

// Main
const opts = parseArgs(process.argv);
if (!opts.skillDir) {
  console.error('Usage: node cross-platform-convert.mjs <skill-dir> [--header-only] [--tags \'[...]\' ] [--dry-run]');
  process.exit(1);
}

const dir = resolve(opts.skillDir);
console.log(`Processing: ${dir}`);
processSkill(dir, opts);
