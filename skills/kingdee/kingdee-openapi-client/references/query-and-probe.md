# 接口清单查询与参数探测

## queryOpenApi(查可用接口)
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
- 若该接口返回 404,说明目标环境未部署 `queryOpenApi`,需用户在苍穹后台导入对应接口定义后再用;本 skill 不内置该定义包。

## 参数探测(预置接口推断必填字段)
当 `respentryentity` 为 null(预置接口无显式参数定义)时:
1. 向目标接口发送**空请求体或最小数据**。
2. 捕获返回的**参数校验错误信息**。
3. 从错误信息反推必填字段与数据格式,逐步补全请求体。

## 业务调用约定
- 请求头:`Content-Type: application/json`、`accessToken: {token}`、提交类加 `Idempotency-Key: {uuid}`。
- 请求体包装:`{ "data": { ...业务数据 } }`。
- 错误返回形如 `{ "status": false, "errorCode": "603", "message": "用户无效" }`。
