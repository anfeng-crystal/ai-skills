import assert from "node:assert/strict";
import test from "node:test";

import { parseExaTrialSearchResult } from "../src/providers.js";

test("parses Exa trial text search results", () => {
  const result = parseExaTrialSearchResult({
    content: [
      {
        type: "text",
        text: [
          "Title: The official TypeScript SDK for Model Context Protocol ... - GitHub",
          "URL: https://github.com/modelcontextprotocol/typescript-sdk",
          "Published: 2024-09-24T20:45:31.000Z",
          "Author: N/A",
          "Highlights:",
          "# Repository: modelcontextprotocol/typescript-sdk",
          "[...]",
          "The official TypeScript SDK for Model Context Protocol servers and clients",
          "---",
          "",
          "Title: MCP TypeScript SDK - Model Context Protocol",
          "URL: https://ts.sdk.modelcontextprotocol.io/",
          "Published: N/A",
          "Author: N/A",
          "Highlights:",
          "MCP TypeScript SDK",
        ].join("\n"),
      },
    ],
  }, "exa_trial");

  assert.equal(result.length, 2);
  assert.equal(result[0].url, "https://github.com/modelcontextprotocol/typescript-sdk");
  assert.equal(result[0].source, "exa_trial");
  assert.equal(result[0].published, "2024-09-24T20:45:31.000Z");
  assert.equal(result[1].published, null);
});
