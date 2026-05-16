---
name: playwright
description: Playwright 浏览器自动化：截图、点击、填表单、网页操作。
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [playwright, browser, automation, screenshot, scraping]
---

# Playwright CLI

> **Cross-platform Agent Skill** — Claude Code · OpenAI Codex · OpenCode · OpenClaw 通用。
> 跨平台 SKILL.md，遵循开放 Agent Skill 规范。

终端驱动浏览器，用跨平台 Node wrapper 优先调用 `npx --package @playwright/cli`。如果 npm registry、网络或 npm cache 出现解析层错误，并且本地已安装依赖，则自动回退到本地 `node_modules/.bin/playwright-cli`。

## 先决条件

```bash
node <active-root>/scripts/npm-deps.mjs install
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs --help
```

`npm-deps.mjs install` 只需要在有网络时执行一次；之后网络不稳定时 wrapper 会使用本地依赖兜底。

## 快速工作流

```bash
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs open https://example.com --headed
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs snapshot
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs click e3
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs type e4 "text"
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs press Enter
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs screenshot
```

**什么时候重刷 snapshot**：导航后、点开 modal/menu 后、tab 切换后、元素引用失效时报错后。

**引用失效恢复**：`snapshot` 重刷后仍找不到 → 检查页面是否跳转到新域名/登录态过期 → 必要时重新 `open`。

## 常用模式

```bash
# 填表单
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs open https://example.com/form
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs snapshot
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs fill e1 "user@example.com"
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs fill e2 "password123"
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs click e3
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs snapshot

# 带 trace 调试
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs open https://example.com --headed
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs tracing-start
# ...交互...
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs tracing-stop

# 多 tab
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs tab-new https://example.com
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs tab-list
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs tab-select 0
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs snapshot

# 批量/循环（同一页面重复操作）
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs open https://example.com/list
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs snapshot

# 等待元素出现（异步加载）
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs wait-for e5 --timeout 5000
```

## 排障速查

| 现象 | 排查步骤 |
|------|---------|
| snapshot 无输出 | 页面是否加载完成 → 加 `--wait-for-timeout 5000` → 检查 URL 是否 404 |
| click 后无反应 | 元素是否被遮挡 → 先 snapshot 确认引用有效 → 尝试 `press Enter` 替代 |
| 截图空白 | 页面是否白屏/未加载 → 加 `--full-page` → 检查 headed 模式是否正常 |
| 登录态失效 | 检查 cookie/session 是否过期 → 重新 `open` 登录页 → 更新 storage state |
| npx 命令找不到 | 检查 Node.js/npm 是否安装并在 PATH 中；如网络不稳，先执行 `node <active-root>/scripts/npm-deps.mjs install` 预取本地依赖 |

## 结束与清理

```bash
# 1. 验证产物存在
ls output/playwright/*.png

# 2. 关闭当前 tab 或浏览器
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs tab-close 0
# 或退出浏览器进程
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs close

# 3. 清理临时 trace 文件（如开启了 tracing）
rm -f trace.zip
```

macOS/Linux 也可以使用 `scripts/playwright_cli.sh`，它会转调同目录下的 Node wrapper。

## 检查点（执行前确认）

| 操作 | 确认内容 |
|------|---------|
| 点击/填表/提交表单 | 会改变页面状态或涉及用户数据 |
| 批量操作（循环点击/填表） | 操作数量和范围已确认，不会误触 |
| 截图/抓取含个人隐私内容 | 只保存到本地 output/playwright/，不上传 |
| 开启 trace 或录制 | 是否涉及敏感操作，trace 文件路径已确认 |
| 执行非 `--dry-run` | 已在 tab 上执行 snapshot，引用有效 |

## 复用现有资产（不重复造轮子）

用户要 Playwright 代码时，按此顺序检查：
1. `find . -name "playwright.config.*"` — 确认配置和项目结构
2. `find . -path "*/fixtures/*" -o -name "*fixture*"` — 复用 fixtures
3. `find . -path "*/pages/*" -o -path "*/pom/*"` — 复用 page objects
4. `find . -name "auth.setup.*"` — 复用登录态
5. 以上都覆盖不了，才新增最小 helper

## 门禁

- 用元素引用前先 snapshot。
- 引用失效就重刷，不绕过引用直接 `run-code`。
- 抓产物放 `output/playwright/`，不新增顶层目录；截图后检查文件是否生成。
- 默认 CLI 工作流，用户明确要测试文件才切到 `@playwright/test`。
- 代码/注释/提交署名用 `anfeng`。

## References

- CLI 命令：`references/cli.md`
- 工作流和排障：`references/workflows.md`
- 注释策略：`references/comment-policy.md`
