import fs from 'node:fs';
import path from 'node:path';

// Count logical records, including quoted line breaks, without retaining field values.
export function countDelimitedRecords(content, delimiter) {
  const text = content.replace(/^\uFEFF/, '');
  let records = 0;
  let quoted = false;
  let afterQuote = false;
  let fieldStart = true;
  let hasContent = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') index += 1;
      else if (char === '"') { quoted = false; afterQuote = true; }
      continue;
    }
    if (char === '\r' || char === '\n') {
      if (hasContent) records += 1;
      if (char === '\r' && text[index + 1] === '\n') index += 1;
      afterQuote = false;
      fieldStart = true;
      hasContent = false;
    } else if (char === delimiter) {
      hasContent = true;
      fieldStart = true;
      afterQuote = false;
    } else if (char === '"' && fieldStart) {
      quoted = true;
      hasContent = true;
      fieldStart = false;
    } else {
      if (afterQuote || char === '"') throw new Error('引号字段格式不正确');
      if (!/\s/.test(char)) hasContent = true;
      fieldStart = false;
    }
  }
  if (quoted) throw new Error('引号字段未闭合');
  return Math.max(0, records + Number(hasContent) - 1);
}

function collectArrayCounts(value) {
  const counts = [];
  const pending = [value];
  // Valid JSON can be much deeper than the JavaScript call stack.
  while (pending.length) {
    const current = pending.pop();
    if (Array.isArray(current)) counts.push(current.length);
    else if (current && typeof current === 'object') {
      for (const child of Object.values(current)) pending.push(child);
    }
  }
  return counts;
}

export function readSourceCount(sourcePath, findings) {
  const finding = (level, code, message, detail = null) => findings.push({ level, code, message, detail });
  if (!sourcePath) {
    finding('Warning', 'source_missing', '未提供 source，无法校验 HTML 声明条数');
    return null;
  }
  if (!fs.existsSync(sourcePath)) {
    finding('High', 'source_not_found', 'source 文件不存在', sourcePath);
    return null;
  }
  let content;
  try { content = fs.readFileSync(sourcePath, 'utf8').replace(/^\uFEFF/, ''); }
  catch (error) {
    // Do not include the raw message, path, or an arbitrary code in reports.
    const knownCodes = ['EACCES', 'EPERM', 'ENOENT', 'EIO', 'EISDIR', 'ENOTDIR', 'ELOOP', 'EMFILE', 'ENFILE', 'EINVAL', 'ENOMEM', 'ENAMETOOLONG'];
    const code = knownCodes.includes(error?.code) ? error.code : 'UNKNOWN';
    finding('High', 'source_read_failed', 'source 文件读取失败，已跳过条数比对并继续其余检查', { code });
    return null;
  }
  const ext = path.extname(sourcePath).toLowerCase();
  if (ext === '.json') {
    let data;
    try { data = JSON.parse(content); }
    catch {
      finding('High', 'source_json_invalid', 'source JSON 无法解析');
      return null;
    }
    if (Array.isArray(data)) return data.length;
    const declared = ['recordCount', '_recordCount'].filter((key) => Object.hasOwn(data ?? {}, key)).map((key) => data[key]);
    if (declared.length) {
      if (declared.every((count) => Number.isSafeInteger(count) && count >= 0 && count === declared[0])) return declared[0];
      finding('High', 'source_count_invalid', 'JSON 声明条数必须为一致的非负安全整数');
      return null;
    }
    const counts = collectArrayCounts(data);
    if (counts.length === 1) return counts[0];
    finding('Warning', counts.length ? 'source_json_ambiguous' : 'source_json_no_array',
      counts.length ? 'JSON 含多个数组，无法确定记录集合；请提供记录数组或明确的 recordCount' : 'JSON 中未找到可计数数组，跳过条数校验');
    return null;
  }
  if (ext === '.tsv' || ext === '.csv') {
    try { return countDelimitedRecords(content, ext === '.tsv' ? '\t' : ','); }
    catch {
      finding('High', 'source_delimited_invalid', 'source CSV/TSV 引号字段格式不正确，跳过条数校验');
      return null;
    }
  }
  finding('Warning', 'source_type_unknown', 'source 类型不是 JSON/TSV/CSV，跳过条数校验', ext || '(no extension)');
  return null;
}
