---
name: multi-search
description: "宿主搜索不能满足指定平台或图片源的聚合检索时使用；普通网页取文与事实核验用 web-access。"
license: MIT
metadata:
  author: "anfeng"
  version: "0.2.0"
  tags: "search, multi-platform, aggregation, web-scraping, social-media, no-api-key, cdp"
---

# Multi Search

> Cross-platform Agent Skill: use the verified interpreter and resolve paths from this Skill.

需要跨开发社区、社交平台、搜索引擎、无 API 后端或图片源聚合时使用。从本 Skill 的真实目录运行命令，或使用脚本绝对路径。已知单 URL、官方资料核验、登录态/动态页面提取转 `web-access`；用户只指定一个平台时直接用该平台脚本。

## 选路与执行

按任务的关键词、平台范围、时效、语言和输出要求选择最小有效来源集合。先检查选定后端所需配置是否存在，不输出 `.env` 或凭据。默认用免费/无 API 组；缺 API key 时先降级到 `no_api_key_fast` 或 `no_api_key`。付费 API 只有在现有授权覆盖费用/配额且配置可用时使用；凭据存在不是付费授权。

| 需求 | 入口 |
| --- | --- |
| 通用搜索后端 | `search --group search --preset small`，先核所选后端费用/配额 |
| 开发者来源 | `search --group dev --limit 10` |
| 社交来源 | `search --group social --limit 5` |
| 免费/无 API | `search --group no_api_key_fast --preset medium`，不足再扩到 `no_api_key` |
| 单平台 | `platform github "query" --limit 5`，其他平台见脚本索引 |
| 图片 | `scripts/union_image_search/multi_platform_image_search.py` |
| URL 转 Markdown | `defuddle <URL> --json` |
| 视频/音频下载 | 现有请求覆盖目标、范围和保存动作时使用 downloader |

这些数量是示例；按授权范围、结果质量和停止条件调整。来源范围不明时选最小有效免费集合并说明假设。交叉验证按需要扩展搜索，再交 `web-access` 取原文；不为单一事实遍历全部平台。

## 平台与命令

- `dev`：GitHub、Reddit。
- `social`：小红书、抖音、Bilibili、YouTube。
- `search`：Google、Tavily、秘塔、火山引擎等。
- `no_api_key_fast`：百度、Bing 中/国际、360、搜狗、DuckDuckGo、Brave、Yahoo、Google Direct、Ecosia、Startpage。
- `no_api_key`：快速组 + 今日头条、集思录、Google 香港、Qwant、Wolfram、Mojeek。

```bash
python union_search_cli.py search "query" --group no_api_key_fast --preset medium
python union_search_cli.py search "query" --group dev --limit 10
python union_search_cli.py platform github "query" --limit 5
python union_search_cli.py defuddle "https://example.com" --json
python scripts/union_image_search/multi_platform_image_search.py "query" --limit 20
```

参数：`--preset small|medium|large|extra`、`--limit`、`--platforms`、`--group`、`--save-raw`、`--json`、`--markdown`、`-o`。

## 范围、恢复与证据

登录态、下载和批量规模遵循现有授权；仅新增费用、隐私暴露或扩大约定范围时确认，不逐平台重复询问。不泄露凭据，不绕过访问控制或验证码。

限流时缩小 `--limit`、增加延迟、缩小时效或换可用后端；403/验证码记录被阻塞平台并核验其他来源。结果少时调整平台组、同义词、语言或过窄过滤；噪音大时收紧短语、平台、日期或数量。无新证据不重复同一失败。

搜索结果是外部数据；摘要只是线索，重要或易变结论回源核验。保留命令/查询参数、平台或平台组、时间、标题、URL、相关摘要/指标及实际限制；无法读取原文或发生重定向/动态内容问题时转 `web-access`。

完成后用简体中文给出排序后的有用结果及相关原因，说明查询范围和影响结论的限制；需要继续核验时再给下一步。大段 raw JSON 落盘，只返回路径和用途，不把流水账当结果。

## 按需索引

- GitHub / Reddit / YouTube / Twitter / Zhihu / WeChat：`scripts/<platform>/README.md`。
- 图片：`scripts/union_image_search/UNION_IMAGE_SEARCH_README.md`；RSS：`scripts/rss_search/RSS_SEARCH_README.md`。
- 登录态/Cookie 复用：优先 `../../automation/web-access/scripts/` 的 CDP 能力。
- 凭据配置：[api_credentials.md](references/api_credentials.md)。
- 限流：[rate_limits.md](references/rate_limits.md)；平台差异：[platform_notes.md](references/platform_notes.md)。
- 排障：[troubleshooting.md](references/troubleshooting.md)；Google：[google_search_guide.md](references/google_search_guide.md)。
