#!/usr/bin/env node
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";

import { createService } from "./app.js";
import { createMcpServer } from "./server.js";

interface CliArgs {
  envFile?: string;
  status: boolean;
  help: boolean;
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    process.stdout.write([
      "Usage: search-web-mcp [stdio] [--env-file <path>] [--status]",
      "",
      "Runs a stdio MCP server by default.",
    ].join("\n") + "\n");
    return;
  }

  const service = createService(args.envFile);
  if (args.status) {
    process.stdout.write(`${JSON.stringify(service.webStatus(), null, 2)}\n`);
    return;
  }

  const server = createMcpServer(service);
  await server.connect(new StdioServerTransport());
}

function parseArgs(argv: string[]): CliArgs {
  const result: CliArgs = { status: false, help: false };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "stdio") {
      continue;
    }
    if (arg === "--env-file") {
      result.envFile = argv[index + 1];
      index += 1;
      continue;
    }
    if (arg === "--status" || arg === "status") {
      result.status = true;
      continue;
    }
    if (arg === "--help" || arg === "-h") {
      result.help = true;
    }
  }
  return result;
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.stack || error.message : String(error)}\n`);
  process.exitCode = 1;
});
