import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

export function readUpstreamOriginals(repoRoot) {
  const manifest = JSON.parse(readFileSync(resolve(repoRoot, 'config/skills-manifest.json'), 'utf8'));
  const originals = new Map();
  for (const entry of manifest.skills) {
    if (!Object.hasOwn(entry, 'upstreamOriginal')) continue;
    const { name, upstreamOriginal: original } = entry;
    const parts = typeof original?.path === 'string' ? original.path.split('/') : [];
    if (parts.length !== 2 || parts[1] !== name ||
        !parts.every(part => /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(part)) ||
        typeof original.repository !== 'string' || !original.repository.startsWith('https://') ||
        !/^[a-f0-9]{40}$/.test(original.revision) ||
        typeof original.sourcePath !== 'string' || !original.sourcePath.endsWith('/SKILL.md') ||
        !['SKILL.md', 'LICENSE'].every(file =>
          typeof original.sha256?.[file] === 'string' && /^[a-f0-9]{64}$/.test(original.sha256[file]))) {
      throw new Error(`Invalid upstream original registration for ${name}`);
    }
    const dir = resolve(repoRoot, 'skills', ...parts);
    if (originals.has(dir)) throw new Error(`Duplicate upstream original registration for ${original.path}`);
    originals.set(dir, { ...original, name, dir });
  }
  return originals;
}

export function verifyUpstreamOriginal(original) {
  const files = {};
  for (const file of ['SKILL.md', 'LICENSE']) {
    const path = resolve(original.dir, file);
    let bytes;
    try {
      bytes = readFileSync(path);
    } catch (error) {
      throw new Error(`Cannot read upstream original ${original.path}/${file} (${error.code})`);
    }
    if (createHash('sha256').update(bytes).digest('hex') !== original.sha256[file]) {
      throw new Error(`Upstream original SHA-256 mismatch for ${original.path}/${file}`);
    }
    files[file] = bytes;
  }
  return files['SKILL.md'];
}
