# Java / Python 调用模板

默认仅 Java 与 Python。所有地址/凭据用占位符。

## 通用规则
| 规则 | 说明 |
|---|---|
| Token 管理 | 缓存 + 自动刷新,有效期 2h,提前 5min 刷新 |
| 请求头 | `Content-Type`、`accessToken`,提交类加 `Idempotency-Key`(唯一 UUID) |
| 字段命名 | API 用 snake_case ↔ 语言惯用风格 |
| 金额 | Java `BigDecimal` / Python `Decimal` |
| 日期 | `yyyy-MM-dd` 或 `yyyy-MM-dd HH:mm:ss` |

## 类型映射
| 星瀚类型 | Java | Python |
|---|---|---|
| String | String | str |
| Long/Integer | Long/Integer | int |
| Boolean | Boolean | bool |
| Decimal | BigDecimal | Decimal |
| Date/DateTime | String | str |
| Array<String> | List<String> | List[str] |

## Java 模板结构
- 依赖:Apache HttpClient + Jackson。
- `getAccessToken()` 缓存 + `refreshToken()` 刷新。
- 通用 `doPost(url, body, headers)`。
- 金额 `BigDecimal`,日期格式化 `yyyy-MM-dd HH:mm:ss`,幂等键 `UUID.randomUUID()`。

```java
// 伪结构
String token = getAccessToken();                 // 缓存/刷新
Map<String,String> headers = Map.of(
    "Content-Type", "application/json",
    "accessToken", token,
    "Idempotency-Key", UUID.randomUUID().toString());
String body = mapper.writeValueAsString(Map.of("data", payload));
String resp = doPost(apiHost + urlFormat, body, headers);
```

## Python 模板结构
- 依赖:`requests`。
- `get_access_token()` 缓存 + `_refresh_token()` 刷新。
- 通用 `_do_post(url, body, headers)`,`uuid.uuid4()` 幂等键。

```python
token = get_access_token()                        # 缓存/刷新
headers = {
    "Content-Type": "application/json",
    "accessToken": token,
    "Idempotency-Key": str(uuid.uuid4()),
}
resp = _do_post(f"{api_host}{url_format}", {"data": payload}, headers)
```
