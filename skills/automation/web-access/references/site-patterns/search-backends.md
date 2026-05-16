# Search Backends

## 后端清单（按优先级）

| 后端 | 触发条件 | 命令/用法 | 配置项 |
|------|---------|----------|--------|
| 直接来源 URL | 已知官网、文档、发布页 | `curl -sL <url>` | 无 |
| jina.ai 摘要 | 页面需要 JS 渲染但只需文本 | `r.jina.ai/http://...` | 无 |
| 宿主原生搜索 | 宿主（Claude/Codex）搜索可用时 | 直接用宿主搜索工具 | 无 |
| Brave Search API | 需要结构化搜索结果，已配置 key | `scripts/brave-search.mjs` | `BRAVE_SEARCH_API_KEY` |
| Tavily AI Search | 需要 AI-native 搜索，含 AI 摘要和相关性评分 | `scripts/search-aggregator.mjs --backend tavily` | `TAVILY_API_KEY` |
| Google CSE API | 已配置 key，Brave/Tavily 不可用时 | `curl "https://customsearch.googleapis.com/..."` | `GOOGLE_CSE_API_KEY`, `GOOGLE_CSE_ID` |
| Bing API | 已配置 key，前两者不可用时 | `curl "https://api.bing.microsoft.com/..."` | `BING_API_KEY` |
| SerpAPI | 需要通用搜索引擎聚合，已配置 key | `curl "https://serpapi.com/search?..."` | `SERPAPI_KEY` |
| DuckDuckGo HTML | 无 API key 时的兜底 | `curl -sL "https://html.duckduckgo.com/html/?q=..."` | 无 |
| 浏览器访问 + 页内搜索 | 上述全不可用时 | 宿主浏览器或 CDP | 无 |

## 规则

- 有 key 的后端按需轮询，不是默认前提。
- 拿到搜索结果后必须回到来源页核验，不把摘要当最终证据。
- 记录：用了哪个后端、核验落在哪个页面。
- 强时效内容记绝对日期和访问时间。
