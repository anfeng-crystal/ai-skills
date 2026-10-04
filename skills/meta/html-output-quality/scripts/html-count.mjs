const SPACE = /[\t\n\f\r ]/;
const TEXT_ELEMENTS = new Set(['script', 'style', 'title', 'textarea', 'xmp', 'iframe', 'noembed', 'noframes', 'noscript']);

// Count extraction needs token boundaries, not a browser or a DOM tree. Keep
// raw text and quoted attribute values opaque so examples cannot declare counts.
function tagEnd(html, start) {
  let quote = null;
  for (let i = start; i < html.length; i += 1) {
    const char = html[i];
    if (quote) {
      if (char === quote) quote = null;
    } else if (char === '"' || char === "'") quote = char;
    else if (char === '>') return i;
  }
  return -1;
}

function attributeCount(html, start, end) {
  let i = start;
  while (i < end) {
    while (i < end && (SPACE.test(html[i]) || html[i] === '/')) i += 1;
    const nameStart = i;
    while (i < end && !SPACE.test(html[i]) && !'/=>'.includes(html[i])) i += 1;
    const name = html.slice(nameStart, i).toLowerCase();
    if (i === nameStart) { i += 1; continue; }
    while (i < end && SPACE.test(html[i])) i += 1;
    if (html[i] !== '=') continue;
    i += 1;
    while (i < end && SPACE.test(html[i])) i += 1;
    let value;
    if (html[i] === '"' || html[i] === "'") {
      const quote = html[i++];
      const valueStart = i;
      while (i < end && html[i] !== quote) i += 1;
      value = html.slice(valueStart, i);
      i += 1;
    } else {
      const valueStart = i;
      while (i < end && !SPACE.test(html[i])) i += 1;
      value = html.slice(valueStart, i);
    }
    // Preserve the established first valid numeric declaration in source order,
    // including when an earlier count has an unsupported value.
    if ((name === 'data-source-count' || name === 'data-record-count') && /^\d+$/.test(value)) {
      return Number.parseInt(value, 10);
    }
  }
  return null;
}

export function readHtmlDeclaredCount(html) {
  let i = 0;
  while (i < html.length) {
    i = html.indexOf('<', i);
    if (i === -1) return null;
    if (html.startsWith('<!--', i)) {
      const end = html.indexOf('-->', i + 4);
      if (end === -1) return null;
      i = end + 3;
      continue;
    }
    if (html[i + 1] === '!' || html[i + 1] === '?') {
      const end = html.indexOf('>', i + 2);
      if (end === -1) return null;
      i = end + 1;
      continue;
    }
    const tag = /^<(\/?)([a-z][^\t\n\f\r />]*)/i.exec(html.slice(i));
    if (!tag) { i += 1; continue; }
    const start = i + tag[0].length;
    const end = tagEnd(html, start);
    if (end === -1) return null;
    i = end + 1;
    if (tag[1]) continue;
    const count = attributeCount(html, start, end);
    if (count !== null) return count;
    const name = tag[2].toLowerCase();
    if (name === 'plaintext') return null;
    if (TEXT_ELEMENTS.has(name)) {
      // HTML text elements close only on the same tag name with a delimiter.
      // A slash on their start tag does not make them HTML void elements.
      const close = new RegExp(`</${name}(?=[\\t\\n\\f\\r />])`, 'gi');
      close.lastIndex = i;
      const match = close.exec(html);
      if (!match) return null;
      const closeEnd = tagEnd(html, close.lastIndex);
      if (closeEnd === -1) return null;
      i = closeEnd + 1;
    }
  }
  return null;
}
