# Unified CLI

统一 CLI 入口：

```bash
python union_search_cli.py <command> [options]
```

也可直接运行：

```bash
python scripts/cli/main.py <command> [options]
```

## Commands

- `search`: 多平台聚合搜索
- `platform`: 单平台搜索
- `image`: 多平台图片搜索/下载
- `download`: 使用 yt-dlp 下载视频/音频（支持从搜索结果文件导入）
- `list`: 列出平台、分组和图片平台
- `doctor`: 环境变量和依赖检查

## Examples

```bash
python union_search_cli.py list --pretty
python union_search_cli.py doctor --env-file .env --pretty
python union_search_cli.py search "LLM" --platforms github duckduckgo --limit 3 --pretty
python union_search_cli.py platform tavily "AI news" --limit 5 --pretty
python union_search_cli.py google "AI news" --limit 5 --pretty
python union_search_cli.py bing "AI news" --limit 5 --pretty
python union_search_cli.py bsearch "AI news" --limit 5 --pretty
python union_search_cli.py search "AI agent" --platforms youtube bilibili --limit 3 -o ./out/search.json --pretty
python union_search_cli.py image "cat" --platforms pixabay --limit 5 --output-dir ./search_output/images --pretty
python union_search_cli.py download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --max-height 1080 --output-dir ./downloads --pretty
python union_search_cli.py download "https://youtu.be/Zh9IscszDQg" --cookies-file /absolute/path/to/cookies.txt --restrict-filenames --continue-download --pretty
python union_search_cli.py download --from-file ./out/search.json --platforms youtube bilibili --select 1,2 --output-dir ./downloads --pretty
```

## Notes

- 默认输出为 `json`，可用 `--format markdown|text` 切换。
- `-o/--output` 使用同目录独有临时文件写入 UTF-8 后原子替换，成功时 stderr 输出目标绝对路径。目录创建、写入或替换发生 I/O 错误时，stderr 返回 JSON 错误信封（`CliRuntimeError`、退出码 `2`），`detail` 仅包含 `errno=EACCES` 等稳定代号（未知为 `errno=UNKNOWN`）；失败只尝试清理本次临时文件，不删除其他既存 `.tmp` 文件。清理也失败时可能留下临时文件，`detail` 追加 `; cleanup_errno=EACCES` 等代号，仍保留原写入错误和退出码。
- `search` 未指定 `--platforms`/`--group` 时使用 `no_api_key_fast`；显式平台优先于分组，所有现有分组均保留。`--group all` 等付费路由须已有费用/配额授权，凭据存在不代表授权。
- `search`、`platform` 和平台快捷命令的 `--limit` 必须为正整数，省略时使用平台默认值；`image --limit <=0` 和 `download --from-file --limit <=0` 保留不限量语义。
- `image` 默认不调用付费 `volcengine`；已获授权后可用 `--platforms volcengine` 显式选择。统一 CLI 总是显式传递其选定图片平台；独立图片脚本仍支持 `IMAGE_SEARCH_PLATFORMS` 配置。
- `search`/`platform` 支持 `--fail-on-platform-error`，在平台失败时返回非零退出码。
- `platform` 支持 `--param key=value` 透传参数给适配层。
- 单平台可直接使用平台名命令（例如 `google`, `bing`），等价于 `platform <name>`.
- `search` 返回中包含 `download_candidates`（稳定索引），可直接用于 `download --from-file --select`。`--platforms` 过滤保留原索引，`--select` 使用搜索输出中显示的编号，`--limit` 在过滤和选择后截断。
- `download` 依赖本机安装 `yt-dlp`；如需音视频合并/转音频，建议同时安装 `ffmpeg`。
- YouTube 403 时优先使用 `--cookies-file`；未显式传入时只读取 `YTDLP_COOKIES_FILE`，不再自动探测宿主目录下的 cookies 文件。
