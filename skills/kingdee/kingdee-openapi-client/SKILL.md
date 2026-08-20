---
name: kingdee-openapi-client
description: "Kingdee Cosmic OpenAPI client: OAuth2 getToken, queryOpenApi discovery, request param probing, Java/Python call code. Use for 调用金蝶云苍穹/星瀚 OpenAPI、getToken 鉴权与刷新、queryOpenApi 查接口清单、参数探测、生成 Java/Python 调用代码;服务端 OpenAPI 开发用 kingdee-cosmic,接口安全审计用 kingdee-security-review,Web 登录态用 kingdee-cosmic-login。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.0.0"
  tags: "kingdee, cosmic, openapi, oauth2, client, integration"
---

# Kingdee OpenAPI Client
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

从外部客户端调用苍穹/星瀚 OpenAPI(kapi)的助手:OAuth2 取 token、查接口清单、探测参数、生成 Java/Python 调用代码。只做"调用客户端/探测",不做服务端接口开发。

## 触发边界
- **适用**:调用苍穹/星瀚 OpenAPI;`getToken` 鉴权与缓存刷新;`queryOpenApi` 查可用接口清单;参数探测;生成 Java/Python 调用代码。
- **不适用(转交)**:
  - 服务端 OpenAPI/自定义 API 开发(写接口、`AbstractApiPlugin`)→ `kingdee-cosmic`。
  - 接口安全审计、越权/SSRF 验证 → `kingdee-security-review`。
  - 苍穹 Web 测试环境登录态(Cookie/CSRF、RSA 登录)→ `kingdee-cosmic-login`。
  - 字段/实体证据 → `kingdee-metadata-analyzer`。

## 快速工作流
1. 确认目标环境地址、应用凭据来源(client_id/client_secret/username/accountId)与调用目标接口；不主动读取本地 env、config 或 secret store，除非用户指定来源。
2. 鉴权:按 `references/auth.md` 走 `getToken`(token 缓存,过期前 5 分钟刷新)。
3. 找接口:按 `references/query-and-probe.md` 用 `queryOpenApi` 按名称/编码搜,拿 `urlformat` + `httpmethod`;参数探测默认只做文档/清单推断，真实请求只允许查询类、元数据类或用户明确授权的测试接口。
4. 生成调用代码:按 `references/call-templates.md` 出 Java 或 Python(默认仅这两种),含 token 管理、请求头、幂等键、类型/日期映射。
5. 凭据与地址用占位符,不写死真实值;提交类接口必须带 `Idempotency-Key`。

## References
- 鉴权(getToken/缓存/刷新):`references/auth.md`
- 接口清单查询与参数探测:`references/query-and-probe.md`
- Java / Python 调用模板:`references/call-templates.md`

## 契约与门禁
- 仅 Java 与 Python 两种调用模板;不默认产出 C#/PHP/Go/JS。
- 鉴权请求 `timestamp` 需在当前时间 ±5 分钟内;token 有效期 2 小时,提前 5 分钟刷新。
- 提交/保存类接口必须带 `Idempotency-Key`(每次唯一 UUID),防重复提交。
- 金额字段用高精度类型(Java `BigDecimal` / Python `Decimal`),不用 float 直算。
- 不在代码、示例、输出中写死真实地址、`client_secret`、账号、token;一律用 `{api_host}`、`{client_id}` 等占位符。
- 默认只生成模板和请求说明，不执行真实 `getToken`、`queryOpenApi` 或业务接口调用；执行前必须确认目标环境和授权。
- 保存、提交、删除、审核、反审核等写入动作默认只给请求模板；真实执行必须是用户明确授权的测试/集成环境，生产调用需单独授权。
- 不把 `client_secret`、access token 写入代码、日志、README 或示例输出；缓存位置必须由用户指定，默认使用占位符或当前任务内存。
- 仅文档化调用流程与模板,不内置第三方脚本或接口定义包;接口清单依赖目标环境已部署 `queryOpenApi`,未部署时按返回提示由用户在后台导入。

## Output
使用简体中文:结论 → 是否执行过真实请求(未执行/已授权执行/被拒绝) → 鉴权与接口定位依据 → 调用代码(Java/Python)→ 必填参数与幂等说明 → 风险与未确认项。
