# Java / Python 调用模板

默认仅 Java 与 Python。所有地址/凭据用占位符。

先按调用规模选择实现：一次请求只给本次调用，现有客户端局部修改沿用其 HTTP、JSON 和鉴权能力。只有持续调用确有缺口时才补令牌缓存或续取，不默认新建客户端、安装依赖或增加配置。

模板不是目标版本兼容证明。使用前按 `SKILL.md` 和 `auth.md` 绑定当前目标版本、认证模式及该 API 的目标合同；已有依赖/声明或同版本官方证据可复用。补丁未知只影响依赖该补丁的部分，不自动把 7.0 目标改为 7.0.8/7.0.13 或 8.0，也不为每个请求重复询问已有授权。

## 通用规则
| 规则 | 说明 |
|---|---|
| Token 管理 | 取用当前认证上下文的有效 Token；需要持续复用时按 `data.expires_in`（剩余毫秒）管理寿命，版本与模式见 `auth.md` |
| 请求头 | 官方流程为 `Content-Type`、`access_token`；兼容头按目标证据选择。`Idempotency-Key` 仅用于合同要求或已选用目标防重机制的写入调用 |
| 字段命名 | 按选定 API 的精确字段名序列化；不把 snake_case 假定为所有 API 的合同 |
| 金额 | Java `BigDecimal` / Python `Decimal` |
| 日期 | 按选定 API 的类型、格式和时区；不统一重写为固定格式 |

## 幂等键与重试

本节仅用于目标合同要求或本次写入确需采用已支持防重机制的场景；POST 方法本身不代表写入或需要幂等键。普通查询和不支持该机制的接口不增加 `logicalOperationId` 等入参；需要键时优先复用已有业务请求标识。[官方保存接口示例](https://developer.kingdee.com/knowledge/358181128073232896?isKnowledge=2&lang=zh-CN&productLineId=29)将该请求头列为可选，不能由客户端模板自行改成所有接口必填。

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

## Java 单次调用示意

下面的 `mapper`、`doPost` / `_do_post` 表示项目已有 JSON、HTTP 能力，按实际入口替换，不要求新增同名封装。令牌已按目标认证合同取得；金额用 `BigDecimal`，日期和报文结构按目标 API。

```java
// 伪结构：仅用于目标文档明确为 POST 的已授权调用
Map<String,String> headers = new HashMap<>();
headers.put("Content-Type", "application/json");
headers.put("access_token", accessToken);         // 当前有效令牌；兼容头以目标证据替换
String body = mapper.writeValueAsString(requestBody); // 已按选定 API 组装
String resp = doPost(apiHost + urlFormat, body, headers);
```

## Python 单次调用示意

沿用项目已有 HTTP 和 JSON 实现；没有现成实现时，只补当前请求所需能力，不为了示例引入持久缓存或新配置。

```python
# 伪结构：仅用于目标文档明确为 POST 的已授权调用
headers = {
    "Content-Type": "application/json",
    "access_token": access_token,                # 当前有效令牌；兼容头以目标证据替换
}
resp = _do_post(f"{api_host}{url_format}", request_body, headers)
```

以上展示基础请求；适用前述防重合同时，再向请求头加入该操作的稳定 `Idempotency-Key`，不默认改动业务请求体或用户输入。

`requestBody` / `request_body` 必须来自选定 API 合同：操作 API 的 POST 常见 `data` 包装，自定义 API 可自定义请求/响应结构。只在该 API 文档要求时包装；GET 等其他方法按其合同生成。这里是结构示例，不会自行发送请求或安装依赖。
