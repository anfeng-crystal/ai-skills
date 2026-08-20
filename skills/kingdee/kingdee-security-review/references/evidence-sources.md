# 安全发现证据来源

## 来源等级

1. 目标版本源码、编译产物、配置和元数据挂载证据。
2. 目标环境在授权范围内取得的脱敏请求/响应、日志和状态证据。
3. 同版本官方安全公告、官方产品/SDK 文档。
4. 项目历史修复、社区文章、论坛、第三方报告或旧版本 POC。

第 4 级只能提供候选漏洞类型、入口或 payload 线索，不能单独确认目标版本存在漏洞。类存在但没有挂载、endpoint 不可达、处理器前已有鉴权/过滤或版本不一致时，必须降级为 `source-only candidate` 或 `unconfirmed`。

## 社区/外部报告处理

- 记录来源类型、目标版本、入口、前置条件和发布日期；缺失项列为证据缺口。
- 先在本地源码和元数据中确认 endpoint、handler、参数、鉴权/过滤链、sink 和 kill switch。
- 只有用户请求动态核验且范围契约完整时，才进入 `verify` 或 `redteam-lite`。
- 不复用报告中的 Cookie、token、账号、租户、客户域名或业务数据；用当前任务授权的凭据来源。
- 外部报告与目标证据冲突时，以目标版本证据为准，并保留差异说明。

输出必须区分：`source-only candidate`、`statically confirmed`、`dynamically verified`、`not reproduced`、`blocked by scope`。
