export type ProviderName =
  | "brave"
  | "exa"
  | "exa_api"
  | "exa_trial"
  | "tavily"
  | "firecrawl"
  | "searxng"
  | "duckduckgo"
  | "local";

export type ExaMode = "auto" | "api" | "trial" | "off";

export interface SearchMcpConfig {
  searchProviders: ProviderName[];
  fetchProviders: ProviderName[];
  timeoutMs: number;
  cacheTtlSeconds: number;
  defaultMaxResults: number;
  searxngUrl?: string;
  exa: {
    mode: ExaMode;
    trialEnabled: boolean;
    trialMcpUrl: string;
  };
  keys: {
    brave: string[];
    exa: string[];
    tavily: string[];
    firecrawl: string[];
  };
}

export interface ProviderStatus {
  enabled: boolean;
  configured: boolean;
  keyCount: number;
  cooldownCount: number;
  disabledCount: number;
  lastErrorType?: string;
}

export interface SearchRequest {
  query: string;
  max_results?: number;
  freshness?: string | null;
  sites?: string[];
  exclude_sites?: string[];
  locale?: string;
}

export interface SearchResult {
  title: string;
  url: string;
  snippet: string;
  source: string;
  score: number;
  domain?: string;
  published?: string | null;
}

export interface WebSearchResult extends SearchResult {
  id: string;
  domain: string;
}

export interface TraceFallback {
  provider: string;
  reason: string;
}

export interface WebSearchResponse {
  query: string;
  results: WebSearchResult[];
  trace: {
    providers: string[];
    fallbacks: TraceFallback[];
  };
}

export interface FetchRequest {
  url: string;
  query?: string;
  max_chars?: number;
}

export interface FetchEvidence {
  text: string;
  score: number;
}

export interface FetchResult {
  url: string;
  title: string;
  source: string;
  summary: string;
  evidence: FetchEvidence[];
}

export interface SearchProvider {
  name: string;
  kind: "search" | "fetch" | "both";
  configured(): boolean;
  search(request: Required<SearchRequest>): Promise<SearchResult[]>;
  status(): ProviderStatus;
}

export interface FetchProvider {
  name: string;
  kind: "search" | "fetch" | "both";
  configured(): boolean;
  fetch(request: Required<FetchRequest>): Promise<FetchResult>;
  status(): ProviderStatus;
}
