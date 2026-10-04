# Union Search

统一多平台搜索编排器。核心目标是：同一关键词并发调用多个平台，输出一份聚合 JSON，并显式标注每个平台成功或失败。

## 核心能力

- 并发调用多个平台，单平台失败不影响整体结果生成。
- 默认透传各平台原始结果结构，不做跨平台去重。
- 支持统一 JSON 输出到文件。
- 每个平台返回 `success/error/total/items/timing_ms`，便于排障。
- 未指定 `--platforms` / `--group` 时使用 `no_api_key_fast`；显式来源保持所选范围，`all` 含付费 API，执行前须有费用授权。凭据存在不是付费授权。

## 快速开始

在 `scripts/union_search` 目录执行：

```bash
python union_search.py --list-platforms
python union_search.py "人工智能" --json --pretty
python union_search.py "人工智能" --group dev --json --pretty
python union_search.py "人工智能" --platforms github reddit wikipedia -o result.json --json --pretty
```

## 支持的平台

### 平台分组

| 分组 | 包含平台 |
|------|----------|
| `dev` | GitHub、Reddit |
| `social` | 抖音、Bilibili、YouTube、Twitter、Weibo、知乎、小宇宙 |
| `search` | Google、Tavily、Jina、DuckDuckGo、Brave、Yahoo、Yandex、Bing、Wikipedia、Metaso、Volcengine、百度千帆、Exa、Serper |
| `tools` | Defuddle URL 提取 |
| `no_api_key_fast` | 默认组：百度、必应中国/国际、360、搜狗、DuckDuckGo HTML、Brave、Yahoo、Google、Ecosia、Startpage 的无 API 路线 |
| `no_api_key` | 快速组 + 今日头条、集思录、Google 香港、Qwant、Wolfram Alpha、Mojeek、DuckDuckGo Instant |
| `preferred` | 无 API 子集：百度、360、搜狗、DuckDuckGo HTML、Startpage、Brave |
| `all` | 所有平台 |

### 无 API 密钥平台

无需配置任何 API 密钥即可直接使用的搜索引擎：

- **中文搜索**: 百度、必应中国、必应国际、搜狗、360、今日头条、集思录
- **国际搜索**: Google、Google香港、DuckDuckGo HTML/Instant、Startpage、Brave、Yahoo、Ecosia、Qwant、Wolfram Alpha、Mojeek

## 常用参数

- `keyword`: 搜索关键词。
- `--platforms -p`: 指定平台列表。
- `--group -g`: 平台组（`dev/social/search/tools/no_api_key_fast/no_api_key/preferred/all`）。
- `--limit -l`: 每个平台返回条数，须为正整数；不指定时使用平台自身默认行为。
- `--max-workers`: 并发数，须为正整数。
- `--timeout`: 总体等待超时，须为正整数秒。
- `--read-timeout`: URL 读取超时，须为正整数秒。
- `--json --pretty`: 以格式化 JSON 输出。
- `--output -o`: 写入输出文件。
- `--verbose -v`: 打开详细日志。

数值参数非法时，CLI 在加载环境变量、创建日志或调用后端前以退出码 `2` 结束，并给出参数用法。此校验不改变 Python 库 API，也不改变图片/下载入口的 `<=0` 不限量语义。

列表、缺少关键词和未知平台不加载环境配置或创建搜索日志。环境配置读取/解码失败时，CLI 在调用后端前以退出码 `1` 结束；诊断只显示错误类型和可用的系统错误码，不回显配置内容。搜索日志无法创建或保存时，在 stderr 提示警告并继续交付已完成的结果；URL 读取不创建搜索日志。

## 输出结构

```json
{
  "keyword": "人工智能",
  "platforms": ["github", "wikipedia"],
  "timestamp": "2026-02-26T22:00:00",
  "results": {
    "github": {
      "success": true,
      "error": null,
      "total": 10,
      "timing_ms": 820,
      "items": []
    },
    "wikipedia": {
      "success": false,
      "error": "...",
      "total": 0,
      "timing_ms": 1040,
      "items": []
    }
  },
  "summary": {
    "total_platforms": 2,
    "successful": 1,
    "failed": 1,
    "total_items": 10
  }
}
```

## 使用建议

- 先用少量平台验证配置，再扩展到全平台。
- 对 API 平台先确认现有授权覆盖费用/配额，再检查对应密钥是否存在；不要输出凭据。
- 结果质量核对时，优先比对单平台独立调用与 union 聚合中的同平台条目。

## 相关文档

- 平台凭据说明：`../../references/api_credentials.md`
- 故障排查：`../../references/troubleshooting.md`
