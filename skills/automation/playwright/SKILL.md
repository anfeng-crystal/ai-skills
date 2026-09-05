---
name: playwright
description: "已知页面的 Playwright 交互、截图和表单操作；内容获取、最新事实或 URL 核验转 web-access。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.0.0"
  tags: "playwright, browser, automation, screenshot, scraping"
---

# Playwright CLI
> Cross-platform Agent Skill: use host-neutral paths and current project commands.


用于终端 CLI 或用户要求的 Playwright 自动化代码。用户指定浏览器时使用其专用入口；宿主现有浏览器工具已覆盖任务时不切换后端。跨平台 Node wrapper 使用已安装依赖；确缺依赖时再按当前 CLI 参数和授权准备运行环境。

## 触发与副作用边界
- 已知页面的导航和 snapshot 是只读操作。
- 截图、trace、PDF 是安全的本地写入；执行前从请求或项目约定确定本地路径和隐私范围，不能表述为零副作用。
- 用户明确要求的普通 `click`/`type`/`fill` 可直接执行，前提是不触发最终业务写入。
- 提交、发送、删除、购买、上传、批量写入或改变业务数据的最终动作，需要任务级执行合同；合同已明确目标、范围和允许动作时连续执行，不逐步重复确认。
- 不默认关闭浏览器或 tab，不默认删除 trace；只清理本轮明确生成且用户已授权的产物。含登录态或个人隐私的截图/trace 仅保存到用户指定的本地路径。
- 仅内容抓取、最新信息查询或 URL 核验不触发本 skill，转 `web-access`。

## 执行合同
- 合同从当前请求、已审核计划与项目配置提取，覆盖环境/站点、对象、动作和范围；认证、证据、清理/回滚按动作风险补齐，不要求用户填写内部表格。
- 当前用户请求、已审核测试计划或上游领域 skill 传入的合同都可作为授权来源；只有目标扩张或副作用等级上升时重新确认。
- 当前任务的既有登录态可直接复用；不得把 Cookie、token、storage state 或账号信息复制到报告、fixture、项目配置或无关任务。

## 先决条件

```bash
node <active-root>/scripts/npm-deps.mjs check
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs --help
```

只在当前执行路径缺依赖时运行 `npm-deps.mjs install`；不为检查或已可用的浏览器重复安装。使用当前 `--help` 确认命令，执行失败先核页面及副作用，不因 network 文字盲目重放业务动作。

## 快速工作流

```bash
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs open https://example.com --headed
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs snapshot
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs click e3
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs fill e4 "text"
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs press Enter
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs screenshot
```

**什么时候重刷 snapshot**：导航后、点开 modal/menu 后、tab 切换后、元素引用失效时报错后。

**引用失效恢复**：`snapshot` 重刷后仍找不到 → 检查页面是否跳转到新域名或登录态过期 → 确认任一条件后重新 `open`。

## 常用模式

任务涉及填表、trace、多 tab、等待元素或 fixture/POM/auth 复用时，读取 `references/workflows.md`；上述 Node wrapper 入口保持可直接执行。

## 排障速查

| 现象 | 排查步骤 |
|------|---------|
| snapshot 无输出 | 页面是否加载完成 → 用当前 CLI 的 `run-code` 等待页面条件 → 检查 URL 是否 404 |
| click 后无反应 | 先核对页面/业务结果是否已变化；有副作用或结果不明时不重复提交。确认未执行后再检查遮挡、引用和交互方式 |
| 截图空白 | 页面是否白屏/未加载 → 加 `--full-page` → 检查 headed 模式是否正常 |
| 登录态失效 | 检查 cookie/session 是否过期 → 重新 `open` 登录页 → 更新 storage state |
| npx 命令找不到 | 检查 Node.js/npm 是否安装并在 PATH 中；如网络不稳，先执行 `node <active-root>/scripts/npm-deps.mjs install` 预取本地依赖 |

## 产物与收尾

截图、trace 等产物保存前从请求或项目约定确定路径和隐私范围；仅按用户明确授权清理本轮生成的文件。浏览器和 tab 保持现状，除非用户明确要求关闭。

macOS/Linux 也可以使用 `scripts/playwright_cli.sh`，它会转调同目录下的 Node wrapper。

## 检查点（执行前确认）

| 操作 | 确认内容 |
|------|---------|
| 导航 / snapshot | 只读；导航后或页面状态变化后重刷 snapshot |
| 截图 / PDF / trace | 本地目标路径和隐私范围；这是安全本地写入 |
| 普通 click / type / fill | 用户已明确要求，且不会触发最终业务写入 |
| 提交 / 发送 / 删除 / 购买 / 上传 / 批量写入 | 执行合同覆盖目标、范围、动作和恢复方式 |
| 批量操作（循环点击/填表） | 合同覆盖数量、记录筛选和停止条件 |

当前 CLI 没有统一的 dry-run 模式；按上述动作分类执行门禁。

## 复用现有资产（不重复造轮子）

用户要 Playwright 代码时，按此顺序检查：
1. 查找 `playwright.config.*` — 确认配置和项目结构
2. 查找 `fixtures`、`pages`/`pom`、`auth.setup.*` — 复用 fixtures、POM 和登录态
3. 以上都覆盖不了，才新增最小 helper

## 门禁

- 用元素引用前先 snapshot。
- 引用失效就重刷，不绕过引用直接 `run-code`。
- 产物优先用户指定位置或项目约定，无约定用 `output/playwright/`；截图后检查文件是否生成。
- 默认 CLI 工作流，用户明确要测试文件才切到 `@playwright/test`。
- Node wrapper 为跨平台主入口；shell 仅作可选 POSIX 辅助，Windows 不依赖 bash、`rm` 或 `find`。
- 未建立执行合同时只做只读导航、snapshot 和明确的无业务写入交互；合同建立后按合同连续完成操作、断言和清理。
- 页面状态或数据与合同前置条件不一致时停止当前序列并保留证据，不扩大选择器、记录或操作范围猜测执行。
- 代码/注释/提交署名用 `anfeng`。

## References

- CLI 命令：`references/cli.md`
- 工作流和排障：`references/workflows.md`
- 注释策略：`references/comment-policy.md`

## 输出

报告执行合同、已完成动作、断言结果、产物路径、清理/回滚状态和未验证步骤；敏感会话材料保持脱敏。
