import { ProviderError } from "./errors.js";
import type { KeyLease } from "./key-pool.js";

export interface JsonRequestOptions {
  provider: string;
  url: string;
  init?: RequestInit;
  timeoutMs: number;
  lease?: KeyLease;
  onRateLimit?: (lease: KeyLease, retryAfterMs: number) => void;
  onUnauthorized?: (lease: KeyLease) => void;
  onQuotaExhausted?: (lease: KeyLease) => void;
}

export async function requestText(url: string, init: RequestInit = {}, timeoutMs = 12_000): Promise<string> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...init, signal: controller.signal });
    if (!response.ok) {
      throw new ProviderError("http", classifyStatus(response.status), `HTTP ${response.status}`);
    }
    return await response.text();
  } finally {
    clearTimeout(timeout);
  }
}

export async function requestJson<T>(options: JsonRequestOptions): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs);
  try {
    const response = await fetch(options.url, { ...options.init, signal: controller.signal });
    if (response.status === 401 || response.status === 403) {
      const body = await responseBody(response);
      if (options.lease) {
        if (looksLikeQuotaExhausted(body)) {
          options.onQuotaExhausted?.(options.lease);
        } else {
          options.onUnauthorized?.(options.lease);
        }
      }
      throw new ProviderError(options.provider, looksLikeQuotaExhausted(body) ? "quota_exhausted" : "unauthorized", `HTTP ${response.status}`);
    }
    if (response.status === 402) {
      if (options.lease) {
        options.onQuotaExhausted?.(options.lease);
      }
      throw new ProviderError(options.provider, "quota_exhausted", "HTTP 402");
    }
    if (response.status === 429) {
      const retryAfterHeader = response.headers.get("retry-after");
      if (!retryAfterHeader && looksLikeQuotaExhausted(await responseBody(response))) {
        if (options.lease) {
          options.onQuotaExhausted?.(options.lease);
        }
        throw new ProviderError(options.provider, "quota_exhausted", "HTTP 429");
      }
      const retryAfterMs = retryAfter(retryAfterHeader);
      if (options.lease) {
        options.onRateLimit?.(options.lease, retryAfterMs);
      }
      throw new ProviderError(options.provider, "rate_limited", "HTTP 429", retryAfterMs);
    }
    if (!response.ok) {
      throw new ProviderError(options.provider, classifyStatus(response.status), `HTTP ${response.status}`);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ProviderError) {
      throw error;
    }
    throw new ProviderError(options.provider, "network", error instanceof Error ? error.message : "network error");
  } finally {
    clearTimeout(timeout);
  }
}

function retryAfter(value: string | null): number {
  if (!value) {
    return 60_000;
  }
  const seconds = Number(value);
  if (Number.isFinite(seconds)) {
    return Math.max(0, seconds * 1000);
  }
  const dateMs = Date.parse(value);
  return Number.isFinite(dateMs) ? Math.max(0, dateMs - Date.now()) : 60_000;
}

function classifyStatus(status: number): "bad_response" | "network" {
  return status >= 500 ? "network" : "bad_response";
}

async function responseBody(response: Response): Promise<string> {
  return response.clone().text().catch(() => "");
}

function looksLikeQuotaExhausted(body: string): boolean {
  return /\b(quota|credit|credits|usage|monthly|month|limit|exceeded|exhausted)\b/i.test(body);
}
