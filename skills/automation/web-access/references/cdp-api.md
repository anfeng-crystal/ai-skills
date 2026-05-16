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
4. 真正发送 CDP 命令前先 `--dry-run`
5. 只有在 DOM/快照不够用时，才显式升级到 `--allow-unsafe`
6. 如果页面上高层封装命令持续超时，但 `/json/list` 与页面级 websocket 可达，回退到原始 WebSocket CDP 调用，不要误判为页面或登录态不可用

如果只是获取页面公开信息，不要绕到 CDP；直接用宿主原生联网能力更轻更稳。
