# Search MCP Server

一套偏生产可用的 MCP 搜索服务，目标是替代 Claude Code 默认的 WebSearch / WebFetch，强调三件事：

- 高语义：同义式查询变体、标题/摘要混合重排、域名可信度加权
- 低噪声：域名黑名单、登录页/聚合页过滤、URL/标题/摘要去重
- 低 token：搜索结果精简返回，详细正文抓取拆成第二个工具 `fetch_page`

## 工具设计

### 1. `search_web`
先查候选结果，只返回紧凑结构：
- `title`
- `url`
- `snippet`
- `domain`
- `source`
- `score`

默认最多返回 6 条，避免把大量摘要塞进上下文。

### 2. `fetch_page`
针对单个 URL 抓取正文，并只返回与 query 最相关的片段。

这是为了把“搜索”和“读正文”拆成两步，减少 token 浪费。

### 3. `build_prompt_pack`
把检索结果压成一个证据包，便于继续交给 Claude Code 推理。

## 为什么这套比 Bash CLI 更省 token

- 结构化 tool 输出，避免把整段 stdout 当提示词硬塞进模型
- 搜索和正文抓取拆成两阶段，只有命中的页面才抓正文
- 标题、摘要和分数都做了截断，不会一次性灌太多内容

## 依赖

```bash
pip install -r requirements.txt
```

## 本地直接运行

### 方式一：stdio

适合 Claude Code 直接接 MCP：

```bash
python search_mcp_server.py stdio
```

### 方式二：HTTP / streamable-http

适合用 OrbStack / Docker 跑成常驻服务：

```bash
python search_mcp_server.py http --host 0.0.0.0 --port 8080
```

默认 MCP 地址：

```text
http://localhost:8080/mcp
```

## Claude Code 接入

### 1. 直接添加 stdio MCP

```bash
claude mcp add search-web --transport stdio -- python /ABSOLUTE/PATH/search_mcp_server.py stdio
```

### 2. 添加 HTTP MCP

先启动服务，再执行：

```bash
claude mcp add --transport http search-web http://127.0.0.1:8080/mcp
```

## 建议同时禁掉默认 WebSearch / WebFetch

`.claude/settings.local.json`：

```json
{
  "permissions": {
    "deny": ["WebSearch", "WebFetch"]
  }
}
```

## 环境变量

| 变量 | 说明 | 默认值 |
|---|---|---|
| `SEARCH_ENABLE_SEARXNG` | 是否启用 SearXNG | `false` |
| `SEARCH_SEARXNG_URL` | SearXNG 地址 | 空 |
| `SEARCH_PREFER_DOMAINS` | 域名白名单加权 | 空 |
| `SEARCH_BLOCK_DOMAINS` | 域名黑名单 | 空 |
| `SEARCH_ENABLE_LOCAL_DOCS` | 是否启用本地文档检索 | `false` |
| `SEARCH_LOCAL_DOCS_DIR` | 本地文档目录 | 空 |
| `SEARCH_DEFAULT_MAX_RESULTS` | 默认返回结果数 | `6` |
| `SEARCH_FETCH_MAX_CHARS` | 正文抓取最大字符 | `1800` |

## Docker / OrbStack 运行

### 构建

```bash
docker build -t search-mcp:latest .
```

### 运行

```bash
docker run --rm -p 8080:8080 \
  -e SEARCH_ENABLE_SEARXNG=false \
  -e SEARCH_PREFER_DOMAINS=kingdee.com,kdcloud.com \
  search-mcp:latest
```

### Claude Code 接入容器版 HTTP MCP

```bash
claude mcp add --transport http search-web http://127.0.0.1:8080/mcp
```

## 推荐调用策略

### 省 token 模式

1. `search_web(query, max_results=5)`
2. 只对前 1~2 条调 `fetch_page`
3. 再根据证据回答

### 高准确率模式

1. `search_web(query, sites=[...], prefer_domains=[...], max_results=8)`
2. 对前 2~3 条 `fetch_page`
3. 若还不够，再改 query 重搜

## 设计细节

### 召回
- DuckDuckGo 文本搜索
- 可选 SearXNG
- 可选本地文档目录

### 重排
- 标题 fuzzy 匹配
- 标题+摘要 fuzzy 匹配
- token 覆盖率
- Jaccard 重合度
- 精确短语命中
- 域名可信度加权
- 站点限制命中加权
- 域名偏好加权

### 去噪
- 黑名单域名过滤
- 登录/注册/标签页/聚合页过滤
- 标题+摘要+域名近重复去重

## 注意事项

- stdio 模式下不要向 stdout 打日志，否则会破坏 JSON-RPC。
- 这套服务默认只做“搜索 + 精简抓取”，不会自动替你做网页浏览器级交互。
- DuckDuckGo 和公开网页搜索本身可能受网络环境影响；如果你有稳定的 SearXNG，建议打开。
