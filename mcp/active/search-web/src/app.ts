import { loadConfig } from "./config.js";
import { buildProviders } from "./providers.js";
import { SearchWebService } from "./search-service.js";

export function createService(envFile?: string): SearchWebService {
  const config = loadConfig({ envFile });
  const providers = buildProviders(config);
  return new SearchWebService({ ...providers, defaultMaxResults: config.defaultMaxResults });
}
