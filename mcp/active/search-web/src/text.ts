import type { FetchEvidence } from "./types.js";

export function normalizeSpace(text: string): string {
  return (text || "").replace(/\s+/g, " ").trim();
}

export function trimText(text: string, maxChars: number): string {
  const cleaned = normalizeSpace(text);
  if (cleaned.length <= maxChars) {
    return cleaned;
  }
  return `${cleaned.slice(0, Math.max(0, maxChars - 1)).trimEnd()}…`;
}

export function canonicalizeUrl(rawUrl: string): string {
  try {
    const url = new URL(rawUrl);
    url.hash = "";
    for (const key of [...url.searchParams.keys()]) {
      if (key.toLowerCase().startsWith("utm_") || ["fbclid", "gclid", "spm"].includes(key.toLowerCase())) {
        url.searchParams.delete(key);
      }
    }
    return url.toString().replace(/\/$/, "");
  } catch {
    return rawUrl;
  }
}

export function domainOf(rawUrl: string): string {
  try {
    const hostname = new URL(rawUrl).hostname.toLowerCase();
    return hostname.startsWith("www.") ? hostname.slice(4) : hostname;
  } catch {
    return "";
  }
}

export function htmlToText(html: string): string {
  return normalizeSpace(
    html
      .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, " ")
      .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, " ")
      .replace(/<[^>]+>/g, " ")
      .replace(/&nbsp;/g, " ")
      .replace(/&quot;/g, "\"")
      .replace(/&#39;/g, "'")
      .replace(/&amp;/g, "&")
      .replace(/&lt;/g, "<")
      .replace(/&gt;/g, ">"),
  );
}

export function extractTitle(html: string, fallback: string): string {
  const match = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  return trimText(match ? htmlToText(match[1]) : fallback, 160);
}

export function scoreText(query: string, text: string): number {
  const queryTokens = tokenize(query);
  if (queryTokens.length === 0) {
    return 0;
  }
  const lower = text.toLowerCase();
  const hits = queryTokens.filter((token) => lower.includes(token)).length;
  return hits / queryTokens.length;
}

export function evidenceFromText(text: string, query: string, maxChars: number): { summary: string; evidence: FetchEvidence[] } {
  const sentences = normalizeSpace(text).split(/(?<=[.!?。！？])\s+/).filter(Boolean);
  const ranked = sentences
    .map((sentence) => ({ text: sentence, score: scoreText(query, sentence) }))
    .sort((a, b) => b.score - a.score || b.text.length - a.text.length);
  const selected = (ranked.length ? ranked : [{ text, score: 0 }]).slice(0, 5);
  const evidence: FetchEvidence[] = [];
  let remaining = maxChars;
  for (const item of selected) {
    const piece = trimText(item.text, Math.min(remaining, 500));
    if (!piece) {
      continue;
    }
    evidence.push({ text: piece, score: Number(item.score.toFixed(4)) });
    remaining -= piece.length;
    if (remaining <= 0) {
      break;
    }
  }
  return {
    summary: trimText(evidence.map((item) => item.text).join(" "), maxChars),
    evidence,
  };
}

function tokenize(text: string): string[] {
  return normalizeSpace(text.toLowerCase())
    .split(/[^\p{L}\p{N}_-]+/u)
    .map((token) => token.trim())
    .filter((token) => token.length > 1);
}
