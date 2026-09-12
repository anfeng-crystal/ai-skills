# 增强型 Token 鉴权(getToken)

## 版本与认证模式

执行 `SKILL.md` 的目标版本检查。下列版本记录说明能力边界，不证明当前项目已安装对应补丁。若只确认 `7.0`，不能断言 `refreshToken` 已下架或直接使用 V7.0.13 的 UTC 格式；复用目标已支持的取令牌方式/时间戳格式即可继续，不必为未用到的补丁能力停问。版本与实际依赖/环境证据不一致时先报告冲突，不擅自采用新版。

本页对应官方增强型 Token：V6.0.1 起提供，且第三方应用需开启增强型 Token 认证。旧版本或关闭该开关的应用仍按目标版本的 `getAppToken.do` / `login.do` 合同处理；不要用此页替换 Web Cookie/CSRF 登录。

- V7.0.8 起已下架 `refreshToken` 接口；需要续用时重新调用 `getToken`。官方调用流程的旧“刷新令牌”措辞不能覆盖这一版本变更。
- V7.0.13 起支持零时区时间戳，例如 `2025-06-12T00:00:10.009Z`；更早版本按目标文档支持的 `yyyy-MM-dd HH:mm:ss` 及服务时区生成，不默认套用 UTC 格式。

## 端点与请求
- 端点:`POST {api_host}/kapi/oauth2/getToken`
- 请求头：`Content-Type: application/json`。
- 必填请求体字段：`client_id`、`client_secret`、`username`、`accountId`、`nonce`（随机字符串）、`timestamp`（字符串，需在当前时间 ±5 分钟内）；`language` 可选。
- 先检查顶层 `status` / `errorCode` / `message`，成功后从 `data` 取 `access_token`、`token_type`、`expires_in`。`data.expires_in` 是**剩余毫秒**，不能按 OAuth2 的通用秒单位解释；默认 2 小时也不能代替本次返回值。

## 凭据来源(占位)
| 参数 | 说明 | 占位 |
|---|---|---|
| `api_host` | 系统地址 | `{api_host}` |
| `client_id` | 第三方应用编码 | `{client_id}` |
| `client_secret` | 应用密钥 | `{client_secret}` |
| `username` | 代理用户名 | `{username}` |
| `accountId` | 数据中心 id | `{account_id}` |
| `language` | 语言(可选) | `zh_CN` |

## 缓存与刷新
- 依据响应接收时间和 `data.expires_in` 计算缓存期限；可预留最多 5 分钟且小于剩余寿命的提前量重新取 token，避免每次业务调用都取 token。缓存与秘密值仍遵守入口的凭据门禁。
- 官方调用流程使用请求头 `access_token: {token}`；目标网关若已验证使用兼容头 `accesstoken`，按该目标合同生成。旧示例的 `accessToken` 与 `accesstoken` 仅大小写不同；不要据此认定它必然失效，也不要自动修改 Nginx 配置。
- `token_type: Bearer` 不等于业务接口接受 `Authorization: Bearer`；以目标接口实际请求头合同为准。令牌不放 URL。

## 错误解释
- `getToken` 文档中，`401` 为 `client_id` 或 `client_secret` 不正确，`603` 为请求参数错误；结合脱敏 `message` 定位具体字段。
- 不把 `603` 统一翻译为“用户无效”，也不把 `500` 固定映射到时间戳错误。业务 API 的同一错误码可能有不同含义，使用该端点文档和本次脱敏响应。

## 官方依据

- [金蝶AI苍穹OpenAPI增强型Token认证](https://developer.kingdee.com/knowledge/specialDetail/226337046514476288?category=490566498872597760&id=489812471545485056&type=Knowledge&productLineId=29&lang=zh-CN)，更新于 2025-12-19 10:12；版本记录 V6.0.1 / V7.0.8 / V7.0.13。`expires_in` 定义的关键原文：“单位：毫秒”。
- [金蝶AI苍穹OpenAPI调用流程](https://developer.kingdee.com/knowledge/specialDetail/226337046514476288?category=239331354741842688&id=213309216805890816&type=Knowledge&productLineId=29&lang=zh-CN)，更新于 2025-12-19 10:04；V4.0.006 初始、V6.0.1 调整认证。使用其请求头和服务分类说明，续期接口以较新的 Token 变更记录为准。
