# Codex 宿主适配

Codex 下优先级建议：

1. 最新信息、公开网页、需要引用来源时：优先宿主原生 web/search。
2. 真实浏览器点击、输入、拖拽、上传、视觉确认时：优先 `Computer Use`。
3. 宿主搜索不稳、但又需要可编程搜索后端时：如果已配置 `BRAVE_SEARCH_API_KEY`，可用 `scripts/brave-search.mjs`。
4. 需要现有登录态标签页、批量枚举 targets、发送原始 CDP 命令时：用本 skill 的 `scripts/*.mjs`。

## 推荐路由
- 搜索事实：先 `web.run`
- 宿主搜索不稳但需要结构化搜索结果：`node scripts/brave-search.mjs ...`
- 页面真实交互：先 `Computer Use`
- 调试浏览器状态或读取已打开 tab：`node scripts/find-url.mjs` / `node scripts/cdp-proxy.mjs`

## 典型判断
- 只要网页内容，不需要真实浏览器状态：不要升级到 CDP。
- `web.run` 已经够用时，不要为了统一而强行切到 Brave 后端。
- 要复用用户当前浏览器登录态：优先 CDP，而不是重新开干净浏览器。
- 要做高风险操作：即使用了 `Computer Use` 或 CDP，也应在提交前让用户确认。
