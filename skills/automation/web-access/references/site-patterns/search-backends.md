# Search Backends

## 选路与后端

先遵循入口的宿主能力、用户指定路径和隐私边界。下表按用途区分搜索、取文和浏览器，不要求逐项调用；只有当前路径不可用或结果不足时才回退。

| 后端 | 触发条件 | 命令/用法 | 配置项 |
|------|---------|----------|--------|
| 宿主原生 web/search | 公开事实、文档、网页取文；当前能力可用时优先 | 使用宿主实际提供的工具 | 无 |
| 直接来源 URL | 原生取文不足，或用户指定本地抓取；已知官网、文档、发布页 | `curl -sL --max-time 15 <url>` | 无 |
| jina.ai 提取 | 本地直抓失败，且 URL 公开、非敏感；告知第三方会接收 URL | `r.jina.ai/http://...` | 无 |
| Brave Search API | 需要结构化搜索结果，已配置 key | `scripts/brave-search.mjs` | `BRAVE_SEARCH_API_KEY` |
| Tavily AI Search | 需要 AI-native 搜索，含 AI 摘要和相关性评分 | `scripts/search-aggregator.mjs --backend tavily` | `TAVILY_API_KEY` |
| Google CSE API | 已配置 key，Brave/Tavily 不可用时 | `curl "https://customsearch.googleapis.com/..."` | `GOOGLE_CSE_API_KEY`, `GOOGLE_CSE_ID` |
| Bing API | 已配置 key，前两者不可用时 | `curl "https://api.bing.microsoft.com/..."` | `BING_API_KEY` |
| SerpAPI | 需要通用搜索引擎聚合，已配置 key | `curl "https://serpapi.com/search?..."` | `SERPAPI_KEY` |
| DuckDuckGo HTML | 无 API key 时的兜底 | `curl -sL "https://html.duckduckgo.com/html/?q=..."` | 无 |
| 浏览器访问 + 页内搜索 | 需要真实页面状态、动态内容或已授权登录态；不必等搜索后端全部失败 | 用户指定浏览器或宿主已连接会话，必要时本地 CDP | 按当前浏览器能力 |

## 规则

- 配置 key 不代表已授权付费或扩大范围。仅在已授权的来源、成本和隐私边界内使用后端；有固定来源限制时显式传 `--backend`，不要启动默认的多后端序列。
- Jina 不接收认证、内网、客户系统或含 token/session/query secret 的 URL；页面含 JS 本身不是外发提取的理由。
- 聚合器只在非空结果时停止；空结果继续原后端序列。显式 `--backend` 只查询指定来源，空结果返回失败，不自行扩大来源。
- 聚合器的 `--count` 必须为正整数；缺值、未知参数或未知 preset 会在请求前退出。用 `--help` 查用法，不发搜索请求。
- Brave CLI 的需值选项遇缺值、空值或下一项为选项时返回 `1`，不发请求；`--dry-run` 只输出计划，无 API key 也可执行，不会被前一选项吞作参数值。
- 拿到搜索结果后必须回到来源页核验，不把摘要当最终证据。
- 记录：用了哪个后端、核验落在哪个页面。
- 强时效内容记绝对日期和访问时间。
