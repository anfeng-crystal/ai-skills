---
name: playwright
description: "用 Playwright 操作已知页面或编写自动化代码；网页取文用 web-access。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.0.0"
  tags: "playwright, browser, automation, screenshot, scraping"
---

# Playwright CLI

> Cross-platform Agent Skill: use the current host capability and verified Node wrapper.

用于终端 CLI 和用户要求的 Playwright 自动化代码。用户指定浏览器时使用其专用入口；宿主现有浏览器能力已覆盖任务时不切换后端。纯网页取文和事实核验转 `web-access`。

## 授权与资源

从当前请求、已审核计划、上游领域 Skill 和项目配置提取环境/站点、对象、动作和范围；按实际副作用补齐认证、证据及恢复方式，不要求用户填写内部合同。既有授权覆盖时连续完成操作、断言和约定清理，仅目标扩张或副作用增加时确认。

- 导航、snapshot 和任务必需且无业务写入的普通 click/type/fill 可连续执行。自动保存也属于业务写入，不能只看操作名称。
- 提交、发送、删除、购买、上传或批量业务写入须在已授权目标、动作和范围内；批量操作还要有记录筛选、数量与停止条件。
- 截图、trace、PDF 是本地写入；从请求或项目约定确定路径和隐私范围，无约定时用 `output/playwright/`。含登录态或个人隐私的截图/trace 仅保存到用户指定的本地路径。
- 复用当前任务有效登录态，不把 Cookie、token、storage state 或账号信息复制到报告、fixture、项目配置或无关任务。
- 不默认关闭浏览器/tab 或删除 trace；只清理本轮生成且任务授权覆盖的产物。

当前 CLI 没有统一 dry-run；按实际动作及页面副作用判断。页面状态或数据不符合授权前置条件时暂停依赖它的序列并保留证据，不扩大记录或选择器范围猜测执行。

## 入口与交互

使用本 Skill 的真实路径或当前源仓库 `<active-root>`。Node wrapper 为 Windows/macOS/Linux 主入口，POSIX 可选 `scripts/playwright_cli.sh`。只有选定执行路径缺依赖时才安装，不为已可用浏览器重复准备环境。

```bash
node <active-root>/scripts/npm-deps.mjs check
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs --help
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs open https://example.com --headed
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs snapshot
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs click e3
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs fill e4 "text"
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs press Enter
node <active-root>/skills/automation/playwright/scripts/playwright_cli.mjs screenshot
```

命令参数以当前 `--help` 为准；需要依赖时使用 `npm-deps.mjs install`。示例元素引用必须换成当前 snapshot 的真实引用。导航、modal/menu 打开、切换 tab 或引用失效后重刷 snapshot；若仍找不到，核实 URL、页面结构与登录态再选恢复动作。只有已观察到目标和状态时才使用语义 locator 或 `run-code`，不以它们绕过失效引用猜测操作。

执行失败先核页面和业务结果，可能已产生副作用或结果不明时不重复提交；确认未执行后再检查遮挡、引用、等待条件或交互方式。网络错误本身不是重放业务动作的依据。

## 按需工作流

- 需要具体 CLI 命令、跨平台 helper 或 session 配置：读 [CLI](references/cli.md)。Windows 不依赖 Bash 或 POSIX 命令。
- 填表、trace、多 tab、等待元素、排障和 fixture/POM/auth 复用：读 [工作流](references/workflows.md)。
- 用户要代码时，按任务需要定位现有 `playwright.config.*`、fixture、POM、登录态与 helper，优先复用；已有资产不足才补最小 helper。CLI 为默认交互方式；用户要求测试文件时使用项目已有测试方案或 `@playwright/test`。
- 注释和署名：读 [注释策略](references/comment-policy.md)；代码、注释与提交署名用 `anfeng`。

## 完成

核实授权范围内的操作结果和必要断言；截图等产物检查文件确实生成。报告已完成动作、验证结果、产物路径、清理/回滚状态及未验证步骤，只保留影响结论的合同信息，敏感会话材料保持脱敏。
