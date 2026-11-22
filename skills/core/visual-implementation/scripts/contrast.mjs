// WCAG relative luminance for two sampled, opaque sRGB colors.
import { pathToFileURL } from 'node:url';

function luminance(hex) {
  if (!/^#[\da-f]{6}$/i.test(hex)) {
    throw new Error('Supply a sampled opaque sRGB color in #RRGGBB format.');
  }
  const channels = hex.slice(1).match(/../g).map(pair => {
    const value = Number.parseInt(pair, 16) / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}

export function contrast(foreground, background) {
  const first = luminance(foreground);
  const second = luminance(background);
  const ratio = (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
  return { ratio, meets4_5: ratio >= 4.5, meets3: ratio >= 3 };
}

if (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url) {
  try {
    const colors = process.argv.slice(2);
    if (colors.length !== 2) throw new Error('Expected a foreground and a background color.');
    console.log(JSON.stringify(contrast(...colors)));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
