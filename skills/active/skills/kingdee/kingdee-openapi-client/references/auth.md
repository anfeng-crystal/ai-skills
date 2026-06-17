# OAuth2 鉴权(getToken)

## 端点与请求
- 端点:`POST {api_host}/kapi/oauth2/getToken`
- 请求体字段:`client_id`、`client_secret`、`username`、`accountId`、`language`、`nonce`(随机数)、`timestamp`(当前时间,需在 ±5 分钟内)。
- 返回:`access_token`、`token_type`、`expires_in`(7200 秒)、`language`。

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
- token 有效期 2 小时;缓存到期前 5 分钟,提前刷新,避免每次调用都取 token。
- 调用业务接口时把 token 放在请求头 `accessToken`。

## 常见错误
- `401`:凭证错误(client_id/secret/username)。
- `603`:用户无效。
- `500` + 时间戳相关:`timestamp` 超出 ±5 分钟。
