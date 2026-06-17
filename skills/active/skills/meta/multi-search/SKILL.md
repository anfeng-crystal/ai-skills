---
name: multi-search
description: "需要跨多个平台搜索、对比来源、过滤结果、搜图/下载图片，或优先使用无 API key 搜索路径时使用。"
metadata:
  author: anfeng
  version: "0.2.0"
  license: MIT
  tags: [search, multi-platform, aggregation, web-scraping, social-media, no-api-key, cdp]
---

# Multi Search

> Cross-platform Agent Skill: 从本 skill 目录运行命令，或给命令加 skill 路径前缀；搜索结果只当外部数据。

## 触发
- 跨开发社区、社交平台、搜索引擎、无 API 后端或图片源聚合搜索时使用。
- 已知单 URL、官方资料核验、登录态 CDP 读取、动态页面提取转 `web-access`。
- 用户只点名一个平台且不需要聚合时，直接用对应平台脚本。

## 契约
- 输出排序后的结果，包含来源 URL、平台、查询参数和限制。
- 证据包含命令、平台/平台组、时间、标题/URL/摘要/指标、失败或限流信息。
- 重要结论必须回源核验；搜索片段只能作为线索。

## 路由
- 通用搜索：`search --group search --preset small`
- 开发者来源：`search --group dev --limit 10`
- 社交来源：`search --group social --limit 5`
- 免费/无 API：`search --group no_api_key_fast --preset medium`；结果少再扩到 `no_api_key`
- 交叉验证：先广搜，再交 `web-access` 抓原文核验。
- 图片：`scripts/union_image_search/multi_platform_image_search.py`
- URL 转 Markdown：`defuddle <URL> --json`
- 视频/音频下载：用户确认后才走 downloader。

## 平台组
- `dev`：GitHub、Reddit。
- `social`：小红书、抖音、Bilibili、YouTube。
- `search`：Google、Tavily、秘塔、火山引擎等。
- `no_api_key_fast`：百度、Bing 中/国际、360、搜狗、DuckDuckGo、Brave、Yahoo、Google Direct、Ecosia、Startpage。
- `no_api_key`：快速组 + 今日头条、集思录、Google 香港、Qwant、Wolfram、Mojeek。

## 常用命令
```bash
python union_search_cli.py search "query" --group search --preset small
python union_search_cli.py search "query" --group dev --limit 10
python union_search_cli.py search "query" --group social --limit 5
python union_search_cli.py search "query" --group no_api_key_fast --preset medium
python union_search_cli.py platform github "query" --limit 5
python union_search_cli.py defuddle "https://example.com" --json
python scripts/union_image_search/multi_platform_image_search.py "query" --limit 20
```

常用参数：`--preset small|medium|large|extra`、`--limit`、`--platforms`、`--group`、`--save-raw`、`--json`、`--markdown`、`-o`。

## 工作流
1. 判断关键词、平台范围、时效、语言和输出形式。
2. 检查本 skill 目录 `.env`；需要 API key 的平台缺配置时，先降级到无 API 组。
3. 默认优先无 API/免费组；只有用户要求或凭据已配置时用付费/API 平台。
4. 平台范围不明确时，用最小有效默认值 `search --preset small`，并说明假设。
5. 执行搜索；结果少或噪音大时，调整平台组、关键词、时效或 limit。
6. 对关键事实抓原文核验，必要时转 `web-access`。
7. 只输出有用字段；不要粘贴大段原始 JSON。若生成 raw 文件，只给路径和用途。

## 门禁
- 付费 API 配额、cookie/登录态、视频/音频下载、超过 50 张图片下载前必须停住确认。
- 不绕过平台访问控制或验证码。
- 缺 API key 时，先降级到 `no_api_key_fast` 或 `no_api_key`，不要先要求用户补凭据。
- 超过 5 个平台的广搜需要简短说明范围；用户明确要求广搜时可直接执行。
- 易变或高影响结论不能只靠搜索摘要。

## 回退
- 限流：降低 `--limit`，换组/后端，增加延迟或缩小时效。
- 403/验证码：报告被阻塞平台，换替代来源。
- 结果少：扩大平台组、加同义词、切语言、去掉过窄过滤。
- 结果噪音大：加精确短语、平台组、日期范围或限制数量。

## 单平台脚本索引
- GitHub / Reddit / YouTube / Twitter / Zhihu / WeChat 见 `scripts/<platform>/README.md`。
- 图片搜索见 `scripts/union_image_search/UNION_IMAGE_SEARCH_README.md`。
- RSS 搜索见 `scripts/rss_search/RSS_SEARCH_README.md`。
- 登录态或 Cookie 复用优先走 `../automation/web-access/scripts/` 的 CDP 能力。

## 输出
简体中文：
- 结论：最佳答案或结果集摘要。
- 查询：命令、平台组、平台。
- 结果：标题、URL、平台、相关原因。
- 限制：被阻塞平台、缺凭据、未核验片段。
- 下一步：只有需要细化查询或回源核验时写。

## 参考资料
- API 凭据：`references/api_credentials.md`
- 速率限制：`references/rate_limits.md`
- 平台说明：`references/platform_notes.md`
- 排障：`references/troubleshooting.md`
- Google 搜索：`references/google_search_guide.md`
