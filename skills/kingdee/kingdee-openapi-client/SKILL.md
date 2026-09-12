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
生成或修改调用代码前，沿用任务已确认的产品版本、API 引擎/认证模式，优先使用已允许读取的项目依赖、目标 SDK/声明、目标导出定义或注明目标适用版本的官方合同。未指定版本时先从已允许的项目材料或用户已指定来源自主取证；下列第 1 步对本地 env、config 和 secret store 的读取限制仍完整适用，不因查版本而扩大。仍缺影响实现的关键事实时可继续独立模板/文档核验，仅在必要时询问缺项，已有授权不重复确认。用户版本与实际依赖/页面证据冲突时先报告，不自行升级。

只知道 `7.0` 不能断言 `7.0.8` 的端点变更或 `7.0.13` 的时间戳能力已适用；具体接口已有目标证据时可继续，不为完整补丁号或每个 API 逐项停问。只暂停依赖未知接口的代码/请求，继续独立模板、数据映射、接口发现和已有授权内的准备；最新官方页面和内置 Java/Python 示例不能提高目标版本，也不把其他任务固定为 7.0。

1. 确认目标环境地址、应用凭据来源(client_id/client_secret/username/accountId)与调用目标接口；不主动读取本地 env、config 或 secret store，除非用户指定来源。
2. 鉴权:按 `references/auth.md` 核对目标版本及第三方应用的认证模式；增强型 Token 适用于 V6.0.1 起且开关启用的应用，按返回的剩余毫秒缓存并在到期前重新取 token。
3. 找接口:先用目标接口文档；目标已验证部署 `queryOpenApi` 时，再按 `references/query-and-probe.md` 按名称/编码搜，拿 `urlformat` + `httpmethod`。参数探测默认只做文档/清单推断，真实请求只允许查询类、元数据类或用户明确授权的测试接口。
4. 生成调用代码:按 `references/call-templates.md` 出 Java 或 Python(默认仅这两种),含 token 管理、请求头、幂等键、类型/日期映射。
5. 凭据与地址用占位符,不写死真实值;提交类接口必须带 `Idempotency-Key`。

## References
- 鉴权(getToken/缓存/刷新):`references/auth.md`
- 接口清单查询与参数探测:`references/query-and-probe.md`
- Java / Python 调用模板:`references/call-templates.md`

## 契约与门禁
- 仅 Java 与 Python 两种调用模板;不默认产出 C#/PHP/Go/JS。
- 增强型鉴权请求 `timestamp` 需在当前时间 ±5 分钟内；token 默认有效期 2 小时，实际按 `data.expires_in` 的剩余毫秒计算，留提前量重新调用 `getToken`。V7.0.8 起已下架 `refreshToken`，不因“刷新”一词调用该接口。
- 本客户端约定提交/保存类接口必须带 `Idempotency-Key`；同一逻辑业务操作及其重试复用同一个键，新操作才生成新键。先核对目标防重能力和有效窗口，不把带键等同于已证明业务幂等。
- 金额字段用高精度类型(Java `BigDecimal` / Python `Decimal`),不用 float 直算。
- 不在代码、示例、输出中写死真实地址、`client_secret`、账号、token;一律用 `{api_host}`、`{client_id}` 等占位符。
- 用户只要求示例、模板或请求说明时，不发真实请求；用户已明确要求在指定环境执行，且相应授权与用户指定的凭据来源齐备时，连续完成鉴权、接口发现和获准调用。缺项只询问该项，不重复确认已有授权；凭据存在本身不构成调用授权。
- 保存、提交、删除、审核、反审核等写入动作默认只给请求模板；真实执行必须是用户明确授权的测试/集成环境，生产调用需单独授权。
- 不把 `client_secret`、access token 写入代码、日志、README 或示例输出；缓存位置必须由用户指定，默认使用占位符或当前任务内存。
- 仅文档化调用流程与模板，不内置第三方脚本或接口定义包；`queryOpenApi` 的下列路径尚未核验为官方通用发现接口，必须以目标部署证据为准。不可用时继续使用已有官方或目标 API 文档；导入定义另按该环境变更授权处理。

## Output
使用简体中文:结论 → 是否执行过真实请求(未执行/已授权执行/被拒绝) → 鉴权与接口定位依据 → 调用代码(Java/Python)→ 必填参数与幂等说明 → 风险与未确认项。
