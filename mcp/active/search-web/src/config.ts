import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import dotenv from "dotenv";

import type { ExaMode, ProviderName, SearchMcpConfig } from "./types.js";

export interface LoadConfigOptions {
  envFile?: string;
  env?: NodeJS.ProcessEnv | Record<string, string | undefined>;
}

const DEFAULT_EXA_TRIAL_URL =
  "https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa,web_search_advanced_exa";

function csv(value: string | undefined, fallback: string[] = []): string[] {
  if (!value || !value.trim()) {
    return fallback;
  }
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function bool(value: string | undefined, fallback = false): boolean {
  if (value === undefined || value === "") {
    return fallback;
  }
  return ["1", "true", "yes", "on"].includes(value.toLowerCase());
}

function numberValue(value: string | undefined, fallback: number): number {
  if (!value) {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function providerList(value: string | undefined, fallback: ProviderName[]): ProviderName[] {
  return csv(value, fallback) as ProviderName[];
}

function exaMode(value: string | undefined): ExaMode {
  if (value === "api" || value === "trial" || value === "off") {
    return value;
  }
  return "auto";
}

function resolveEnvFile(explicit?: string): string | undefined {
  if (explicit) {
    return explicit;
  }
  const cwdEnv = join(process.cwd(), ".env");
  return existsSync(cwdEnv) ? cwdEnv : undefined;
}

export function loadConfig(options: LoadConfigOptions = {}): SearchMcpConfig {
  const envFile = resolveEnvFile(options.envFile);
  const fileEnv = envFile && existsSync(envFile) ? dotenv.parse(readFileSync(envFile)) : {};
  const env = { ...fileEnv, ...(options.env ?? process.env) };

  return {
    searchProviders: providerList(env.SEARCH_PROVIDERS, ["brave", "exa", "tavily", "searxng", "duckduckgo"]),
    fetchProviders: providerList(env.FETCH_PROVIDERS, ["local", "firecrawl", "exa", "tavily"]),
    timeoutMs: numberValue(env.SEARCH_TIMEOUT_SECONDS, 12) * 1000,
    cacheTtlSeconds: numberValue(env.SEARCH_CACHE_TTL_SECONDS, 1800),
    defaultMaxResults: numberValue(env.SEARCH_DEFAULT_MAX_RESULTS, 6),
    searxngUrl: env.SEARCH_SEARXNG_URL?.trim() || undefined,
    exa: {
      mode: exaMode(env.EXA_MODE),
      trialEnabled: bool(env.EXA_TRIAL_ENABLED, false),
      trialMcpUrl: env.EXA_TRIAL_MCP_URL?.trim() || DEFAULT_EXA_TRIAL_URL,
    },
    keys: {
      brave: csv(env.BRAVE_SEARCH_API_KEYS),
      exa: csv(env.EXA_API_KEYS),
      tavily: csv(env.TAVILY_API_KEYS),
      firecrawl: csv(env.FIRECRAWL_API_KEYS),
    },
  };
}
