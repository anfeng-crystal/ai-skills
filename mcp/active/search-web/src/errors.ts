export type ProviderErrorType =
  | "not_configured"
  | "unauthorized"
  | "quota_exhausted"
  | "rate_limited"
  | "network"
  | "bad_response"
  | "extract_failed"
  | "no_results"
  | "unknown";

export class ProviderError extends Error {
  constructor(
    public readonly provider: string,
    public readonly type: ProviderErrorType,
    message: string,
    public readonly retryAfterMs?: number,
  ) {
    super(message);
    this.name = "ProviderError";
  }
}

export function errorType(error: unknown): string {
  if (error instanceof ProviderError) {
    return error.type;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "unknown";
}
