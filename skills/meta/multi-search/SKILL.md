---
name: multi-search
description: "Multi-platform search: 20+ platforms, result filtering/sorting, batch image download. Use web-access for single-URL fetches or CDP login-state reuse."
metadata:
  author: anfeng
  version: "0.2.0"
  license: MIT
  tags: [search, multi-platform, aggregation, web-scraping, social-media, no-api-key, cdp]
---

# 联合搜索技能
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## 触发边界
- 用户需要在多个平台搜索内容（GitHub、Reddit、社交媒体、搜索引擎）时使用。
- 用户需要按时间范围、互动指标或内容类型过滤结果时使用。
- 用户需要无 API 密钥的搜索方案时使用（DuckDuckGo、Brave、Yahoo、Bing、Wikipedia）。
- 只搜索单一平台且已知具体工具时，直接使用对应的 `scripts/{platform}/` 脚本。

## TL;DR 速查

| 用户说的话 | 首选动作 |
|-----------|---------|
| "搜一下 XX""查查 XX" | `python union_search_cli.py search "XX" --preset small` |
| "在 GitHub/Reddit 上搜" | `python union_search_cli.py search "XX" --group dev --limit 5` |
| "在小红书/抖音/B站搜" | `python union_search_cli.py search "XX" --group social --limit 5` |
| "多来源交叉验证" | `python union_search_cli.py search "XX" --group search --limit 10` |
| "搜图片" | `python scripts/union_image_search/union_image_search.py "XX" --limit 20` |
| "提取这个页面内容" | `python union_search_cli.py defuddle <URL> --json` |
| 其他场景见下方工作流 | |

## 决策树

| if 条件 | 动作 | 回退 |
|--------|------|------|
| 用户给模糊关键词 | `search --group search --preset small` | 结果少 → 扩大 `--group dev,social` |
| 提到"开发者""代码""GitHub" | `search --group dev --limit 10` | 结果少 → 加 `--group no_api_key` |
| 提到"社交媒体""小红书""抖音" | `search --group social --limit 5` | 风控 → 建议缩小时间范围 |
| 提到"新闻""最新""最近" | `search --group search --topic news` 或使用 Tavily | 时效不足 → 补 `curl` 直抓 |
| 提到"免费""不用API" | `search --group no_api_key_fast --preset medium` | 结果不足 → 扩展到 `no_api_key` 全量组 |
| 需要下载视频/音频 | `download <URL> --output-dir ./downloads` | 403 → 提示配置 cookies |
| 需要搜图 | `image "XX" --platforms google bing --limit 20` | 下载失败 → 减少线程、加延迟 |
| 提到"登录态""Cookie过期"（微博/知乎） | 复用 web-access CDP → `cdp-launch.mjs && find-url.mjs` | CDP 不可用 → 提示用户手动提供 Cookie |

## 快速工作流

1. **识别搜索需求**：判断用户提供的是具体平台名称（如"GitHub"、"小红书"）、平台组（如"社交媒体"、"无需API"）还是通用搜索关键词。

2. **检查配置**（检查点）：
   - 检查 `<active-root>/skills/meta/union-search-skill/.env` 是否存在。
   - 如果不存在，询问用户："未找到 .env 配置文件，是否需要创建？可参考 ENV_TEMPLATE.txt 模板。"
   - 如果用户选择需要 API key 的平台（Google、Tavily、秘塔等），检查对应的环境变量是否配置。
   - 如果缺少必要配置，提示用户："平台 X 需要 API key，请在 .env 中配置 {KEY_NAME}，或改用无需 API key 的平台组（--group no_api_key_fast 快速 / --group no_api_key 全量）。"

3. **构建搜索命令**（检查点）：
   - 根据步骤1的识别结果，选择命令格式：
     - **多平台搜索**：`python union_search_cli.py search "<关键词>" --group <组名> --preset <数量>`
       - 平台组选项：`dev`（GitHub、Reddit）、`social`（小红书、抖音、Bilibili）、`search`（Google、Tavily）、`no_api_key_fast`（11 个快速免费引擎）、`no_api_key`（18 个全量免费引擎）
     - **单平台搜索**：`python union_search_cli.py platform <平台名> "<关键词>" --limit <数量>`
     - **图片搜索**：`python scripts/union_image_search/union_image_search.py "<关键词>" --sources <平台> --limit <数量>`
     - **网页提取**：`python union_search_cli.py defuddle <URL> --json`
   - 如果用户需求不明确（如"搜索 AI 相关内容"），询问用户："需要搜索哪些平台？可以选择：1) 开发者社区（--group dev）、2) 社交媒体（--group social）、3) 搜索引擎（--group search）、4) 免费快速（--group no_api_key_fast）、5) 免费全量（--group no_api_key）。"

4. **执行搜索**：
   ```bash
   cd <active-root>/skills/meta/union-search-skill
   <步骤3构建的命令>
   ```
   如果执行失败，检查错误类型：
   - **缺少凭据**：提示用户配置 .env 或改用无需 API key 的平台。
   - **API 速率限制**：提示用户降低 `--limit` 或 `--preset` 数量，或稍后重试。
   - **网络超时**：提示用户检查网络连接或增加超时值。
   - **403 Blocked**：提示用户降低请求频率或使用代理。

5. **格式化输出**：
   - **终端输出**：展示 Markdown 表格格式的搜索结果（标题、链接、摘要、互动数据）。
   - **原始响应**：如果使用了 `--save-raw` 参数，提示用户："原始 JSON 响应已保存到 responses/ 目录。"
   - **结果过滤**（检查点）：如果结果过多或不相关，询问用户："是否需要调整搜索参数？可以：缩小时间范围、增加过滤条件、更换平台组。"

## 门禁与降级

以下动作前必须停住确认：

| ⚠️ 动作 | 确认话术 |
|--------|---------|
| 批量搜索 > 5 平台 | "将同时搜索 `{N}` 个平台，可能触发速率限制，确认继续？" |
| 图片批量下载 > 50 张 | "将下载约 `{N}` 张图片，可能耗时较长，确认继续？" |
| 视频下载 | "将下载 `{URL}` 的视频内容，确认继续？" |
| 使用需付费的 API（TikHub/SerpAPI） | "此操作将消耗付费 API 配额（`{platform}`），确认继续？" |
| 用户给模糊关键词 | "请明确搜索关键词和偏好平台，否则默认用 `--group search --preset small`" |
| 涉及 Cookie 登录态平台 | "将使用已配置的 Cookie 访问 `{platform}`，只读不写，确认继续？" |

降级规则：

- 不直接读取或展示完整的原始 JSON 响应（文件过大），必须通过格式化输出或引用 `responses/` 文件路径。
- 平台不明确时，先询问用户选择平台或平台组，不直接猜测。
- 需要 API key 的平台缺少配置时，主动建议降级到无需 API key 的平台组（优先 `--group no_api_key_fast`，不足再 `--group no_api_key`）。
- 执行失败时，展示错误信息并提示用户检查配置或调整参数，不继续执行后续步骤。

## 平台与工具速查

### 平台组映射

| 组名 | 包含平台 | 使用场景 |
|------|---------|---------|
| `dev` | GitHub, Reddit | 开发者社区搜索 |
| `social` | 小红书, 抖音, Bilibili, YouTube | 社交媒体内容搜索 |
| `search` | Google, Tavily, 秘塔, 火山引擎 | AI 驱动搜索引擎 |
| `no_api_key_fast` | 百度, 必应中国/国际, 360, 搜狗, DuckDuckGo, Brave, Yahoo, Google Direct, Ecosia, Startpage | 无需 API key 快速搜索（11 平台，响应<3s） |
| `no_api_key` | 上述全部 + 今日头条, 集思录, Google香港, Qwant, Wolfram, Mojeek | 无需 API key 全量搜索（18 平台） |

### 常用参数速查

- `--preset`: 预设结果数量（`small`=3, `medium`=5, `large`=10, `extra`=20）
- `--limit` / `-l`: 自定义每平台结果数量
- `--platforms` / `-p`: 指定平台（空格分隔）
- `--group` / `-g`: 指定平台组
- `--save-raw`: 保存原始 API 响应到 `responses/` 目录
- `--json` / `--markdown`: 输出格式
- `-o` / `--output`: 保存输出到文件

### 平台特定工具

详细文档见 `scripts/{platform}/README.md`：
- **GitHub**: 仓库、代码、问题/PR 搜索
- **Reddit**: 帖子、子版块、用户搜索
- **小红书**: 笔记搜索，支持过滤排序
- **抖音**: 视频搜索，支持过滤选项
- **Bilibili**: 视频搜索，双 API 支持
- **YouTube**: 视频、评论搜索
- **Twitter**: 帖子和时间线搜索
- **知乎**: 中文问答平台
- **微信**: 公众号文章搜索（JS 版）
- **图片搜索**: 18 平台批量图片下载
- **RSS**: 订阅源内容搜索
- **CDP 浏览器**: 复用 web-access CDP（`../../automation/web-access/scripts/`），用于微博/知乎等需登录态平台的自动 Cookie 复用、动态页面抓取、浏览器历史/书签搜索

## References

- **[API 凭据获取指南](references/api_credentials.md)** - 如何获取各平台的 API 凭据
- **[速率限制说明](references/rate_limits.md)** - 各平台的速率限制和配额信息
- **[平台特定说明](references/platform_notes.md)** - 各平台的特殊说明和注意事项
- **[问题排查指南](references/troubleshooting.md)** - 常见问题的诊断和解决方案
- **[Google 搜索技巧](references/google_search_guide.md)** - Google 搜索高级指令速查
- **[CDP 浏览器自动化](../../automation/web-access/references/cdp-api.md)** - Chrome DevTools Protocol 接口（复用 web-access）
- **[CDP 启动脚本](../../automation/web-access/scripts/cdp-launch.mjs)** - 自动启动 Chrome 远程调试
- **[CDP URL 发现](../../automation/web-access/scripts/find-url.mjs)** - 从浏览器历史/书签查找已访问页面
