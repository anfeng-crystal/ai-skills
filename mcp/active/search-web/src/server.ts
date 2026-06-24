import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";

import type { SearchWebService } from "./search-service.js";

export function createMcpServer(service: SearchWebService): Server {
  const server = new Server(
    { name: "search-web-mcp", version: "0.1.0" },
    { capabilities: { tools: {} } },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: [
      {
        name: "web_search",
        description: "Return compact ranked URL candidates for a web query. Use web_fetch for page evidence.",
        inputSchema: {
          type: "object",
          properties: {
            query: { type: "string" },
            max_results: { type: "number", default: 6 },
            freshness: { type: ["string", "null"], default: null },
            sites: { type: "array", items: { type: "string" }, default: [] },
            exclude_sites: { type: "array", items: { type: "string" }, default: [] },
            locale: { type: "string", default: "auto" },
          },
          required: ["query"],
        },
      },
      {
        name: "web_fetch",
        description: "Fetch one URL and return compact evidence chunks related to the query.",
        inputSchema: {
          type: "object",
          properties: {
            url: { type: "string" },
            query: { type: "string", default: "" },
            max_chars: { type: "number", default: 2400 },
          },
          required: ["url"],
        },
      },
      {
        name: "web_status",
        description: "Show provider configuration and key-pool health without exposing key values.",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
    ],
  }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const args = (request.params.arguments ?? {}) as Record<string, unknown>;
    if (request.params.name === "web_search") {
      const result = await service.webSearch({
        query: String(args.query ?? ""),
        max_results: numberArg(args.max_results),
        freshness: nullableString(args.freshness),
        sites: stringArray(args.sites),
        exclude_sites: stringArray(args.exclude_sites),
        locale: String(args.locale ?? "auto"),
      });
      return jsonToolResult(result);
    }
    if (request.params.name === "web_fetch") {
      const result = await service.webFetch({
        url: String(args.url ?? ""),
        query: String(args.query ?? ""),
        max_chars: numberArg(args.max_chars),
      });
      return jsonToolResult(result);
    }
    if (request.params.name === "web_status") {
      return jsonToolResult(service.webStatus());
    }
    throw new Error(`Unknown tool: ${request.params.name}`);
  });

  return server;
}

function jsonToolResult(value: unknown): { content: Array<{ type: "text"; text: string }> } {
  return {
    content: [{ type: "text", text: JSON.stringify(value, null, 2) }],
  };
}

function numberArg(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function nullableString(value: unknown): string | null | undefined {
  if (value === null) {
    return null;
  }
  return typeof value === "string" ? value : undefined;
}

function stringArray(value: unknown): string[] | undefined {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : undefined;
}
