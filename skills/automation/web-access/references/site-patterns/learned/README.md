# Learned Site Patterns

按域名存储操作经验，跨 session 复用。每个文件以域名为名（如 `xiaohongshu.com.md`），记录该站点的 URL 模式、平台特征、已知陷阱和有效操作路径。

## 文件命名

`<domain>.md` — 使用完整域名（不含协议和路径）。

## 内容格式

```markdown
# <domain>

## URL 模式
- 文章页：`/<author>/posts/<id>`
- 搜索页：`/search?q=<query>`

## 平台特征
- 需 JS 渲染 / 纯静态
- 登录态要求
- 反爬强度（低/中/高）
- 已知限流策略

## 有效操作路径
- 优先走 jina.ai / 必须 CDP / curl 即可

## 已知陷阱
- 哪些路径会触发风控
- Cookie 过期特征
- 特定 User-Agent 需求
```

## 使用方式

执行 Step 2 前，先 `grep -l "<domain>" references/site-patterns/learned/*.md` 检查是否有该域名的已知经验。有则先读，按经验选择最优路径。
