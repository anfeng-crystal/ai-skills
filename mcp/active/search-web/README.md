# @anfeng087/search-web-mcp

一个面向 agent 的统一 Web 搜索 MCP。默认输出结构化候选和证据片段，不返回给人看的长说明。

## Tools

| Tool | Purpose |
|---|---|
| `web_search` | 返回候选 URL、标题、域名、短摘要、来源和分数 |
| `web_fetch` | 抓取单个 URL，返回与 query 相关的证据片段 |
| `web_status` | 查看 provider/key 状态，不输出真实 key |

## Run

```bash
npx -y @anfeng087/search-web-mcp --env-file /path/to/.env
```

无 `.env` 或无 API key 时仍可启动：搜索走 DuckDuckGo/SearXNG，抓取走本地 HTML 抽取。

## Claude Code

```bash
claude mcp add search-web -- npx -y @anfeng087/search-web-mcp --env-file /Users/anfeng/AI/mcp/active/search-web/.env
```

建议在 Claude Code 本地权限里禁用原生 `WebSearch` / `WebFetch`，让搜索统一经过本 MCP。

## Config

复制 `.env.example` 为 `.env` 后按需填 key。每家 provider 可填多个 key，逗号分隔。

```dotenv
BRAVE_SEARCH_API_KEYS=brv_key_1,brv_key_2
EXA_API_KEYS=exa_key_1,exa_key_2
TAVILY_API_KEYS=tvly_key_1,tvly_key_2
FIRECRAWL_API_KEYS=fc_key_1,fc_key_2

SEARCH_PROVIDERS=brave,exa,tavily,searxng,duckduckgo
FETCH_PROVIDERS=local,firecrawl,exa,tavily

EXA_MODE=auto
EXA_TRIAL_ENABLED=false
EXA_TRIAL_MCP_URL=https://mcp.exa.ai/mcp?tools=web_search_exa,web_fetch_exa,web_search_advanced_exa

SEARCH_SEARXNG_URL=
SEARCH_TIMEOUT_SECONDS=12
SEARCH_CACHE_TTL_SECONDS=1800
```

`EXA_MODE`:

- `auto`: 有 `EXA_API_KEYS` 用 REST API；无 key 且 `EXA_TRIAL_ENABLED=true` 用 Exa remote MCP；否则跳过 Exa。
- `api`: 只用 Exa REST API。
- `trial`: 只用 Exa remote MCP。
- `off`: 禁用 Exa。

## Provider Behavior

- 每个 provider 独立维护 key 池，多个 key 按 round-robin 使用。
- 普通 `429` 按 `Retry-After` 冷却当前 key；没有 `Retry-After` 且不是额度耗尽文案时短冷却后再试。
- `401` / `403`、`402`、以及明确写着 quota/monthly/credits exhausted 的 `429` 会禁用当前 key 到下个自然月月初，并立即尝试同 provider 的下一个 key；进入下个月后自动恢复参与轮询。
- `web_status` 只展示 `keyCount`、`cooldownCount`、`disabledCount` 和错误类型，不打印真实 key。

## Development

```bash
npm install
npm run build
npm test
node dist/cli.js --status --env-file .env.example
npm pack --dry-run
```

发布 scoped public 包：

```bash
npm publish --access public
```
