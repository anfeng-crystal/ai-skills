# Java / Python 调用模板

默认仅 Java 与 Python。所有地址/凭据用占位符。

模板不是目标版本兼容证明。使用前按 `SKILL.md` 和 `auth.md` 绑定当前目标版本、认证模式及该 API 的目标合同；已有依赖/声明或同版本官方证据可复用。补丁未知只影响依赖该补丁的部分，不自动把 7.0 目标改为 7.0.8/7.0.13 或 8.0，也不为每个请求重复询问已有授权。

## 通用规则
| 规则 | 说明 |
|---|---|
| Token 管理 | 增强型 Token 读取 `data.access_token` 与 `data.expires_in`（剩余毫秒），留提前量重新调用 `getToken`；版本与模式见 `auth.md` |
| 请求头 | 官方流程为 `Content-Type`、`access_token`；兼容头按目标证据选择。提交类加 `Idempotency-Key`，同一业务操作的重试复用 |
| 字段命名 | 按选定 API 的精确字段名序列化；不把 snake_case 假定为所有 API 的合同 |
| 金额 | Java `BigDecimal` / Python `Decimal` |
| 日期 | 按选定 API 的类型、格式和时区；不统一重写为固定格式 |

## 幂等键与重试

`Idempotency-Key` 标识一次逻辑业务操作，可用该操作首次创建的 UUID 或合适的业务请求号；在重试循环外生成并保留。不同操作使用不同键。官方防重机制按同一 API 与同一键判重，窗口内后续调用返回 `604`，不保证返回首次业务结果。收到重复或超时结果时，在已授权范围内核对原操作状态，不能换新键盲目重发。

防重初始版本 V5.0.005；自 V6.0.12 可通过 `Idempotency-Timeout` 指定秒数。目标版本、窗口、接口是否支持尚未确认时明确列为缺口；客户端带键约定不等于服务端天然幂等，也不提供额外写授权。

依据：[OpenAPI防止接口重复调用](https://developer.kingdee.com/knowledge/specialDetail/226337046514476288?category=226337340351087360&id=341958917577817856&type=Knowledge&productLineId=29&lang=zh-CN)，更新于 2024-08-22 09:52；关键原文：“只有第一次请求执行”。

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
- `getAccessToken()` 读取有效缓存；`renewAccessToken()` 重新调用 `getToken`，不要将方法名解释为调用已下架的 `refreshToken` 端点。
- 通用 `doPost(url, body, headers)`。
- 金额 `BigDecimal`；日期和报文结构按目标 API；幂等键由逻辑操作提供。

```java
// 伪结构：仅用于目标文档明确为 POST 的已授权调用
String token = getAccessToken();                 // 缓存/重新取 token
String requestId = logicalOperationId;           // 首次创建一次，重试复用
Map<String,String> headers = Map.of(
    "Content-Type", "application/json",
    "access_token", token,                      // 兼容头以目标证据替换
    "Idempotency-Key", requestId);
String body = mapper.writeValueAsString(requestBody); // 已按选定 API 组装
String resp = doPost(apiHost + urlFormat, body, headers);
```

## Python 模板结构
- 依赖:`requests`。
- `get_access_token()` 缓存 + `_renew_access_token()` 重新调用 `getToken`。
- 通用 `_do_post(url, body, headers)`；幂等键由逻辑操作提供。

```python
# 伪结构：仅用于目标文档明确为 POST 的已授权调用
token = get_access_token()                        # 缓存/重新取 token
request_id = logical_operation_id                 # 首次创建一次，重试复用
headers = {
    "Content-Type": "application/json",
    "access_token": token,                       # 兼容头以目标证据替换
    "Idempotency-Key": request_id,
}
resp = _do_post(f"{api_host}{url_format}", request_body, headers)
```

`requestBody` / `request_body` 必须来自选定 API 合同：操作 API 的 POST 常见 `data` 包装，自定义 API 可自定义请求/响应结构。只在该 API 文档要求时包装；GET 等其他方法按其合同生成。这里是结构示例，不会自行发送请求或安装依赖。
