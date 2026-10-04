# CDP API 与脚本约定

`web-access` 自带的脚本只提供最小能力：检查环境、定位标签页、探测已有 CDP 端点、向已有 target 发送单次命令。它们不是浏览器框架替代品，而是宿主原生能力不够时的补充。

## 环境变量
- `WEB_ACCESS_CDP_HOST`：CDP HTTP 端点主机，默认 `127.0.0.1`
- `WEB_ACCESS_CDP_PORT`：CDP HTTP 端口，默认 `9222`
- `WEB_ACCESS_CDP_WS_URL`：直接指定浏览器或 target websocket 端点
- `WEB_ACCESS_ALLOW_REMOTE=1`：显式允许连接非本机 CDP 端点
- `WEB_ACCESS_BROWSER_PATH`：显式指定浏览器可执行文件路径

## `scripts/check-deps.mjs`

用途：检查本机 Node、浏览器路径和默认 CDP 端点是否可达。

```bash
node scripts/check-deps.mjs
node scripts/check-deps.mjs --json
node scripts/check-deps.mjs --dry-run
node scripts/check-deps.mjs --strict
```

关注字段：
- `node.ok`：Node 版本是否满足最小要求
- `browser.found`：是否发现本机浏览器可执行文件
- `cdp.reachable`：默认 CDP 端点是否已可连
- `readyForCdp`：是否具备直接发 CDP 命令的最小条件

说明：
- `--dry-run` 只输出计划检查项，不访问浏览器或端点
- `--strict` 适合需要 CDP 的场景；当 `readyForCdp=false` 时返回非零退出码
- `--host`、`--port`、`--browser-path` 必须有值；端口限定为 `1..65535` 的整数，主机不含协议/路径。IPv6 使用未加方括号的 `::1`。
- `--auto-launch` 只在本地端点不可达且 Node/浏览器条件满足时启动；会保留指定的主机、端口和已检测浏览器路径。远程端点无法通过启动本地浏览器修复。
- 自动启动失败写入 `cdp.launchFailure`，保留返回的 `pid`、`tmpDir` 与清理错误，便于按实际状态恢复。
- HTTP 成功还须返回 JSON 对象及有效的 `ws://`/`wss://` `webSocketDebuggerUrl`（不含 URL fragment），才认作 CDP 发现成功；不要求特定产品名或版本。无效响应返回 `cdp.reason=invalid_cdp_response`、`readyForCdp=false`，不回显响应体，也不触发 `--auto-launch`。此检查不执行 WebSocket 握手。

## `scripts/cdp-launch.mjs`

用途：探测指定 CDP；已有端点可用时返回 `launched=false`，否则为本地端点启动独立临时浏览器。端点和浏览器使用上述环境变量；远程探测仍须显式设置 `WEB_ACCESS_ALLOW_REMOTE=1`。

```bash
node scripts/cdp-launch.mjs --help
node scripts/cdp-launch.mjs
node scripts/cdp-launch.mjs --kill <本次启动返回的pid>
```

- 启动结果保留 `ok`、`launched`、`host`、`port`、`webSocketDebuggerUrl`、`browser`、`pid`、`tmpDir`。首次记录身份须匹配所选浏览器路径及本次唯一 `--user-data-dir`；子进程退出状态或退出事件会阻止成功返回。共享浏览器不会获得所有权记录。
- 复用与启动轮询使用上述 CDP 响应校验。已有端点响应无效时返回 `invalid_cdp_response` 和退出码 `2`，不新开浏览器；启动后的无效响应不能使轮询成功，超时仍按既有所有权规则清理。
- `--kill <pid>` 只查找唯一、当前用户可验证的所有权记录；核对进程身份后发送终止信号，确认退出才删除该目录。已退出实例可清理自己的残留目录，不扫描删除其他实例。
- 缺 PID、非正整数/多余参数返回退出码 `1`。无记录、旧目录、符号链接、重复 PID 记录、身份变化或无法确认退出时返回 `2` 并保留目录；不退回任意 PID 终止或按前缀批量删除。
- 进程身份通过 macOS/Linux 的 `ps` 或 Windows 的 PowerShell/CIM 查询。查询不可用时返回失败并保留 `pid`、`tmpDir`，不能把该结果当作浏览器已退出。超时清理也遵循同一身份校验；仍存活时保留目录。
- 若所选启动脚本会转交另一可执行文件，首次身份可能不匹配；用 `WEB_ACCESS_BROWSER_PATH` 指定实际浏览器二进制后重试，不把未知进程自动认作该实例。`launch_exited` 也会保留本次目录，避免在转交行为不明时误删仍被使用的资料。
- 启动和停止按任务授权执行。已有浏览器的 `pid=null`、`tmpDir=null`，不适用此清理命令。

## `scripts/find-url.mjs`

用途：从当前 CDP 端点枚举标签页并按 URL/标题过滤。

兼容两组参数：
- 旧参数：`--contains`、`--url`、`--title`
- 新参数：`--endpoint`、`--match`、`--mode`、`--value`

```bash
node scripts/find-url.mjs --contains github
node scripts/find-url.mjs --url https://example.com --json
node scripts/find-url.mjs 登录 --title --first
node scripts/find-url.mjs --endpoint http://127.0.0.1:9222 --match dashboard --mode contains --value webSocketDebuggerUrl --first
node scripts/find-url.mjs --dry-run --match example.com
```

常用筛选：
- `--contains`：URL 或标题包含某段文本
- `--url`：按 URL 精确或包含匹配
- `--title`：按标题包含匹配
- `--match + --mode`：通用匹配；支持 `contains|exact|prefix|host|regex|url|title`
- `--value webSocketDebuggerUrl`：直接输出 attachable target 的 websocket 地址
- `--first`：只返回第一条命中
- `--include-devtools`：包含 `devtools://` targets
- `--dry-run`：只输出计划请求

输入约定：`--title` 可不带值（保留 `登录 --title --first`）；其他带值选项不可缺值或吞掉后续开关。`--limit` 为正整数，`--port` 为 `1..65535` 整数，模式、来源、排序和输出字段须为帮助中列出的值。参数或运行失败返回非零退出码；`--json` 时统一输出 `{ "ok": false, "command": "find-url", "error": "..." }`，成功结果数组格式不变。

来源还支持 `--only bookmarks|history|chrome|all`（`chrome` 为书签加历史），可用 `--profile-dir`、`--bookmarks-path`、`--history-path` 显式选文件；读取范围仍须符合任务授权。`--since` 和 `--sort recent|visits` 用于历史筛选与排序。

本地来源失败：显式文件或 `--profile-dir` 下所选 Bookmarks/History 缺失，以及来源发现、读取、解析或查询失败，返回退出码 `1`。默认探测时未安装的浏览器、未存在的可选文件不算失败。`--json` 失败对象仍含 `ok:false`、`command`、`error`，并带 `errors`（来源、路径及错误码）、`results`（其他来源的命中，仍应用匹配与限量）和 `partial`（至少一个来源成功读取，即使没有命中）。全部读取成功仍输出原结果数组；文本模式把诊断写到 stderr、保留命中到 stdout。解析错误不回显书签内容。dry-run 只列计划路径，不确认文件可读。

## `scripts/cdp-proxy.mjs`

用途：对当前 CDP 端点做最小诊断、标签页枚举、打开新页和原始命令透传。

### 诊断与枚举

```bash
node scripts/cdp-proxy.mjs doctor
node scripts/cdp-proxy.mjs probe
node scripts/cdp-proxy.mjs list
node scripts/cdp-proxy.mjs doctor --dry-run
```

- `doctor` 与 `probe` 等价，读取 `/json/version`
- `list` 读取 `/json/list`

输入约定：带值选项缺值、未知长选项和非法数值会在请求前失败；`--json` 时参数失败与运行失败同样输出 `{ "ok": false, "command": "...", "error": "..." }`。`--timeout` 为 `1..2147483647` 毫秒整数（更大会使 Node 定时器溢出）；`--id` 须为 JavaScript 可准确表示的整数，`--x`/`--y` 支持有限负数，`--direction` 仅支持 `bottom`。

两个脚本的 HTTP 端点支持 `http://`、`https://` 及省略协议的形式；IPv6 回环可写 `--endpoint http://[::1]:9222` 或 `--host ::1`。显式 WebSocket 端点须为 `ws://` 或 `wss://`。真实连接远程 HTTP/WS 仍须 `WEB_ACCESS_ALLOW_REMOTE=1`；dry-run 只检查输入并展示计划，不代表端点已连通。

显式 `--endpoint` 优先于 `--host`/`--port` 默认值；`doctor`/`probe`/`send` 选择 WebSocket 覆盖时不使用默认 HTTP 主机和端口。`list` 等 HTTP 命令不校验未使用的 WebSocket 默认值；`find-url --only bookmarks|history|chrome` 不校验未使用的 HTTP 端点。只校验实际使用的路线，所有带值选项缺值仍会在任何读取前失败。

WebSocket 在收到当前请求的响应前关闭时，命令返回退出码 `1`；`--json` 使用上述失败对象并报告 `WebSocket closed before CDP response.`，文本模式写入 stderr，不回显远端关闭原因。收到结果后的正常关闭不改变成功结果。

### 打开新标签页

```bash
node scripts/cdp-proxy.mjs open https://example.com --allow-unsafe
node scripts/cdp-proxy.mjs open https://example.com --dry-run
```

说明：
- `open` 会改变浏览器状态，真实执行必须显式加 `--allow-unsafe`
- `--dry-run` 只显示计划请求，不真正打开标签页
- 在较新的 Chrome（例如 Chrome 147）上，底层 `/json/new` 端点可能要求使用 `PUT` 而不是 `GET`；若遇到 `Using unsafe HTTP verb GET to invoke /json/new`，应切换为 `PUT` 请求

### 发送原始 CDP 命令

支持两种方式：

```bash
node scripts/cdp-proxy.mjs send github DOM.getDocument '{"depth":1}'
node scripts/cdp-proxy.mjs send --ws-url ws://127.0.0.1:9222/devtools/page/xxx --method DOM.getDocument --params '{"depth":1}'
node scripts/cdp-proxy.mjs send github Runtime.evaluate '{"expression":"document.title","returnByValue":true}' --allow-unsafe
node scripts/cdp-proxy.mjs send --ws-url ws://127.0.0.1:9222/devtools/page/xxx --method Runtime.evaluate --params '{"expression":"document.title","returnByValue":true}' --dry-run
```

目标解析顺序：
1. 目标 `id` 前缀
2. URL 精确匹配
3. URL 或标题包含匹配

如果命令是 `Browser.*`，脚本会优先尝试浏览器级 websocket；页面级命令则优先使用 target websocket。

## 方法安全分级

### 默认允许
偏读取、偏观察的命令，例如：
- `Browser.getVersion`
- `DOM.getDocument`
- `DOM.describeNode`
- `Page.getFrameTree`
- `Page.captureSnapshot`

### 需要 `--allow-unsafe`
这些命令可能执行页面脚本、触发导航或改变浏览器/页面状态：
- `Runtime.evaluate`
- `Runtime.callFunctionOn`
- `Page.navigate`
- `Input.*`
- `DOM.set*`
- `Storage.*`
- `Fetch.*`
- `Network.set*`
- `Emulation.set*`
- `Target.createTarget`
- `Target.closeTarget`
- `Browser.grantPermissions`
- `open` 子命令

### 硬阻断
这些命令默认拒绝真实执行：
- `Browser.close`
- `Browser.crash`
- `Page.crash`

`--dry-run` 可以预演这些命令的请求结构，但不会实际发送。

## 推荐顺序
1. 先 `check-deps`
2. 再 `cdp-proxy doctor` 或 `probe`
3. 需要找 tab 时用 `find-url`
4. 首次构造不熟悉或有副作用的请求时可用 `--dry-run` 核对结构；已有验证且范围未变的只读调用无需逐次预演。dry-run 不是授权，也不能证明业务执行成功。
5. 只有在 DOM/快照不够用时，才显式升级到 `--allow-unsafe`
6. 如果页面上高层封装命令持续超时，但 `/json/list` 与页面级 websocket 可达，回退到原始 WebSocket CDP 调用，不要误判为页面或登录态不可用

如果只是获取页面公开信息，不要绕到 CDP；直接用宿主原生联网能力更轻更稳。
