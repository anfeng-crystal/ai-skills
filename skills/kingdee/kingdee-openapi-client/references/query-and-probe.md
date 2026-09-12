# 接口清单查询与参数探测

## queryOpenApi(查可用接口)

下列 `openapi_scriptapi/queryOpenApi` 是待目标部署证据核验的集成约定；本轮未取得证明其为跨版本官方通用发现接口的正文。先使用目标 API 文档、导出的接口定义或已验证部署，不能因名称类似就假定存在。不可用只阻断此发现路径，已有接口文档可继续支持获准工作。

- 端点:`POST {api_host}/kapi/v2/{biz}/open/openapi_scriptapi/queryOpenApi`
- 入参:按名称模糊搜(如 `费用-对公报销单_提交`)或按编码搜(如 `er_publicreimbursebill_submit`);`biz` 为业务模块标识(如 `base`、`em`),可选。
- 关键返回字段:
  | 字段 | 说明 |
  |---|---|
  | `urlformat` | API 请求路径(如 `/kapi/v2/em/er_publicreimbursebill/submit`) |
  | `httpmethod_title` | 请求方式(GET/POST) |
  | `version_title` | 版本(1.0/2.0) |
  | `headerentryentity` | 自定义请求头定义 |
  | `respentryentity` | 返回参数定义(预置 API 常为 null) |
  | `errorcodeentity` | 错误码定义 |
- 若该接口返回 404，先核对目标地址、网关路由、模块与部署证据，不能仅凭 404 断言未部署。本 skill 不内置定义包；需要导入时，按目标环境变更授权处理，不把接口发现请求当成导入授权。

## 参数探测(预置接口推断必填字段)
`respentryentity` 为空只说明该清单未提供返回定义，不能据此断言请求参数缺失或预置接口可安全试写。先读该接口的请求字段/示例。仍需探测时，仅在入口允许的查询类、元数据类或用户明确授权测试接口范围内：
1. 确认端点、副作用、请求结构和环境后，发送**空请求体或最小数据**；提交、保存等接口不因“探测”绕过写授权。
2. 捕获返回的**参数校验错误信息**。
3. 从错误信息反推必填字段与数据格式,逐步补全请求体。

## 业务调用约定
- 请求头：按 `auth.md` 选定 `Content-Type: application/json` 与 `access_token: {token}` 或目标已验证兼容头；提交类的 `Idempotency-Key` 按 `call-templates.md` 在同一逻辑操作重试间复用。
- 请求方法、字段和报文结构以该接口文档为准；操作 API 的 POST 常见 `{ "data": { ...业务数据 } }`，自定义 API 可完全自定义，不能强制统一包装。
- 按 HTTP 状态及响应中该端点定义的 `status`、`errorCode`、`message` 判断；`603` 可能是请求参数或操作权限等错误，不统一解释为“用户无效”。

通用服务分类、请求头和自定义参数依据见 `auth.md` 的官方调用流程；保存权限错误示例见 [保存操作API权限增强校验](https://developer.kingdee.com/knowledge/specialDetail/226337046514476288?category=226337340351087360&id=685450223417566464&type=Knowledge&productLineId=29&lang=zh-CN)（更新于 2025-03-10 11:05，V7.0.7）。以上来源未证实本页 `queryOpenApi` 的部署及字段合同。
